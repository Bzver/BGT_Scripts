import os
import csv
import numpy as np
import scipy.io as sio
from scipy import stats
import warnings

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

warnings.filterwarnings('ignore', category=RuntimeWarning)

# ============================================================
# User configuration
# ============================================================

SKELE = r"D:\Repository\Label3D-mod\skeletons\rat16.mat"
ROOT = r"D:\MQQ\260803s"

OUTPUT_DIR = os.path.join(ROOT, "analysis_output_wt_baseline")
FIG_DIR = os.path.join(OUTPUT_DIR, "figs")
TABLE_DIR = os.path.join(OUTPUT_DIR, "tables")

FIGURE_DPI = 200
FIGURE_FORMATS = ["png"]

PLATE_HALF_SCALE = 0.75

COMPUTE_FOURPOINT_PLANE_ANGLE = True

METRICS_TO_PLOT = [
    ("head_trunk_yaw_signed", "Head-trunk yaw (deg, relative to WT)"),
    ("fourpoint_plane_angle", "Four-point plane angle (deg, relative to WT)"),
]

ALL_FRAME_METRICS = [
    "head_trunk_bend_3d", "head_trunk_yaw_signed", "fourpoint_plane_angle"
]

# ============================================================
# Basic helpers
# ============================================================

def ensure_dirs():
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(TABLE_DIR, exist_ok=True)

def parse_folder(folder):
    folder_lower = folder.lower()
    sex = "female" if "female" in folder_lower else ("male" if "male" in folder_lower else "unknown")
    geno = "homo" if "homo" in folder_lower else ("fet" if "fet" in folder_lower else ("wt" if "wt" in folder_lower else "unknown"))
    return sex, geno

def finite_rows(points):
    points = np.asarray(points)
    if points.size == 0: return points
    return points[np.all(np.isfinite(points), axis=1)]

def save_figure(fig, base_path_no_ext):
    for fmt in FIGURE_FORMATS:
        fig.savefig(f"{base_path_no_ext}.{fmt}", dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)

def clean_value(v):
    if isinstance(v, (np.floating, float)):
        return float(v) if np.isfinite(v) else ""
    if isinstance(v, (np.integer, int)):
        return int(v)
    return v

def write_csv(filename, rows):
    if not rows: return
    fieldnames = []
    for row in rows:
        for k in row.keys():
            if k not in fieldnames: fieldnames.append(k)
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: clean_value(v) for k, v in row.items()})


# ============================================================
# Geometry helpers
# ============================================================

def get_anatomical_scale(pred, snout_idx, tail_base_idx):
    if snout_idx is None or tail_base_idx is None: return 100.0
    snout = pred[:, :, snout_idx]
    tail = pred[:, :, tail_base_idx]
    lengths = np.linalg.norm(snout - tail, axis=1)
    lengths = lengths[np.isfinite(lengths)]
    if len(lengths) == 0: return 100.0
    return float(np.percentile(lengths, 95))

def fit_ground_plane_lower_envelope(points, body_points):
    pts = finite_rows(points)
    if len(pts) < 10: return None, None

    rng = np.random.default_rng(0)
    if len(pts) > 50000:
        fit_pts = rng.choice(pts, 50000, replace=False)
    else:
        fit_pts = pts

    body_pts = finite_rows(body_points)
    if len(body_pts) > 0:
        up_vec = np.mean(body_pts, axis=0) - np.mean(fit_pts, axis=0)
    else:
        up_vec = np.array([0.0, 0.0, 1.0])
        
    up_vec_norm = np.linalg.norm(up_vec)
    if up_vec_norm < 1e-8:
        up_vec = np.array([0.0, 0.0, 1.0])
    else:
        up_vec = up_vec / up_vec_norm

    heights = fit_pts @ up_vec
    n_pts = len(heights)
    n_discard = max(1, int(0.01 * n_pts))
    n_keep = max(10, int(0.30 * n_pts))
    k = n_discard + n_keep
    
    if k >= n_pts:
        lowest_indices = np.arange(n_pts)
    else:
        partitioned_indices = np.argpartition(heights, k)[:k]
        sorted_sub_indices = partitioned_indices[np.argsort(heights[partitioned_indices])]
        lowest_indices = sorted_sub_indices[n_discard:]

    lowest_pts = fit_pts[lowest_indices]
    centroid = np.mean(lowest_pts, axis=0)
    centered = lowest_pts - centroid
    
    try:
        _, _, Vt = np.linalg.svd(centered)
        normal = Vt[-1, :]
        nrm = np.linalg.norm(normal)
        if nrm < 1e-12:
            normal = up_vec
        else:
            normal = normal / nrm
    except np.linalg.LinAlgError:
        normal = up_vec
        
    if np.dot(normal, up_vec) < 0:
        normal = -normal

    return centroid, normal

def fit_plane_normal(points):
    pts = finite_rows(points)
    if len(pts) < 3: return None, None, np.nan
    centroid = np.mean(pts, axis=0)
    try:
        _, _, Vt = np.linalg.svd(pts - centroid)
    except np.linalg.LinAlgError:
        return None, None, np.nan
    normal = Vt[-1, :]
    nrm = np.linalg.norm(normal)
    if nrm < 1e-12: return None, None, np.nan
    return centroid, normal / nrm, np.median(np.abs((pts - centroid) @ normal))


# ============================================================
# Metric helpers
# ============================================================

def signed_angle_projected(a, b, normal, valid_frames):
    angle = np.full(a.shape[0], np.nan)
    a_proj = a - ((a @ normal)[:, None] * normal)
    b_proj = b - ((b @ normal)[:, None] * normal)
    a_norm, b_norm = np.linalg.norm(a_proj, axis=1), np.linalg.norm(b_proj, axis=1)
    valid = valid_frames & np.all(np.isfinite(a_proj), axis=1) & np.all(np.isfinite(b_proj), axis=1) & (a_norm > 1e-8) & (b_norm > 1e-8)
    if np.any(valid):
        cross = np.cross(a_proj[valid], b_proj[valid])
        angle[valid] = np.degrees(np.arctan2(cross @ normal, np.einsum("ij,ij->i", a_proj[valid], b_proj[valid])))
    return angle

def angle_between_vectors_3d(a, b, valid_frames):
    angle = np.full(a.shape[0], np.nan)
    a_norm, b_norm = np.linalg.norm(a, axis=1), np.linalg.norm(b, axis=1)
    valid = valid_frames & np.all(np.isfinite(a), axis=1) & np.all(np.isfinite(b), axis=1) & (a_norm > 1e-8) & (b_norm > 1e-8)
    if np.any(valid):
        cosang = np.clip(np.einsum("ij,ij->i", a[valid], b[valid]) / (a_norm[valid] * b_norm[valid]), -1.0, 1.0)
        angle[valid] = np.degrees(np.arccos(cosang))
    return angle

def summarize_metric_array(arr):
    vals = arr[np.isfinite(arr)] if arr.size > 0 else np.array([])
    summary = {"n_valid": int(len(vals)), "signed_mean": np.nan, "signed_median": np.nan, "abs_mean": np.nan, 
               "abs_median": np.nan, "sd": np.nan, "iqr": np.nan, "p5": np.nan, "p95": np.nan, 
               "laterality_index": np.nan, "sign_consistency": np.nan}
    if len(vals) == 0: return summary

    signed_mean, signed_median = float(np.mean(vals)), float(np.median(vals))
    abs_vals = np.abs(vals)
    abs_mean, abs_median = float(np.mean(abs_vals)), float(np.median(abs_vals))
    sd, iqr = float(np.std(vals)), float(np.percentile(vals, 75) - np.percentile(vals, 25))
    p5, p95 = np.percentile(vals, [5, 95])

    lat_idx = abs(signed_mean) / abs_mean if abs_mean > 1e-12 else np.nan
    sign_con = float(np.mean(np.sign(vals) == np.sign(signed_mean))) if signed_mean != 0 else np.nan
    
    summary.update({"signed_mean": signed_mean, "signed_median": signed_median, "abs_mean": abs_mean, 
                    "abs_median": abs_median, "sd": sd, "iqr": iqr, "p5": float(p5), "p95": float(p95),
                    "laterality_index": float(lat_idx) if np.isfinite(lat_idx) else np.nan, "sign_consistency": sign_con})
    return summary


# ============================================================
# Analyzer
# ============================================================

class GroundedTiltAnalyzer:
    def __init__(self):
        mat = sio.loadmat(SKELE)
        self.skeleton = {bp[0]: idx for idx, bp in enumerate(mat["joint_names"][0])}
        print("Skeleton mapping:", self.skeleton)

        self.joints_idx = mat.get('joints_idx', np.array([])).astype(int) - 1 
        self.joint_colors = mat.get('color', np.array([]))

        required = ["ForepawL", "ForepawR", "HindpawL", "HindpawR", "EarL", "EarR", "SpineF", "SpineM"]
        missing = [k for k in required if k not in self.skeleton]
        if missing: raise RuntimeError(f"Skeleton missing: {missing}")

        self.idx = {k: self.skeleton[k] for k in required}
        self.foot_idx = [self.idx[k] for k in ["ForepawL", "ForepawR", "HindpawL", "HindpawR"]]
        self.upper_idx = [self.skeleton[k] for k in ["EarL", "EarR", "SpineF", "SpineM"]]
        
        self.opt = {k: self.skeleton[k] for k in ["ForelimbL", "ForelimbR", "HindlimbL", "HindlimbR", "Snout", "Tail(base)"] if k in self.skeleton}

    def load_3d_data(self, d3d_file):
        return sio.loadmat(d3d_file)["pred"][:, 0, :, :]

    def analyze_file(self, mat_file):
        pred = self.load_3d_data(mat_file)
        total_frames = int(pred.shape[0])
        if total_frames == 0: return None

        body_scale = get_anatomical_scale(pred, self.opt.get("Snout"), self.opt.get("Tail(base)"))
        foot_pts = np.transpose(pred[:, :, self.foot_idx], (0, 2, 1))
        body_pts = np.transpose(pred[:, :, self.upper_idx], (0, 2, 1)).reshape(-1, 3)
        centroid, normal = fit_ground_plane_lower_envelope(foot_pts.reshape(-1, 3), body_pts)
        if centroid is None: return None

        all_frames_mask = np.ones(total_frames, dtype=bool)

        spineF = pred[:, :, self.idx["SpineF"]]
        spineM = pred[:, :, self.idx["SpineM"]]
        snout = pred[:, :, self.opt["Snout"]] if "Snout" in self.opt else None

        head_trunk_bend_3d, head_trunk_yaw_signed = (np.full(total_frames, np.nan) for _ in range(2))
        if "Snout" in self.opt:
            raw_angle = angle_between_vectors_3d(snout - spineF, spineM - spineF, all_frames_mask)
            head_trunk_bend_3d[np.isfinite(raw_angle)] = 180.0 - raw_angle[np.isfinite(raw_angle)]
            head_trunk_yaw_signed = signed_angle_projected(spineF - spineM, snout - spineF, normal, all_frames_mask)

        fourpoint_plane_angle = np.full(total_frames, np.nan)
        if COMPUTE_FOURPOINT_PLANE_ANGLE:
            upper_frames = np.transpose(pred[:, :, self.upper_idx], (0, 2, 1))
            cand_idx = np.where(all_frames_mask & np.all(np.isfinite(foot_pts), axis=(1,2)) & np.all(np.isfinite(upper_frames), axis=(1,2)))[0]
            for i in cand_idx:
                _, n_paw, _ = fit_plane_normal(foot_pts[i])
                _, n_upper, _ = fit_plane_normal(upper_frames[i])
                if n_paw is None or n_upper is None: continue
                if np.dot(n_paw, normal) < 0: n_paw = -n_paw
                if np.dot(n_upper, n_paw) < 0: n_upper = -n_upper
                
                f_mid, h_mid = 0.5*(foot_pts[i,0]+foot_pts[i,1]), 0.5*(foot_pts[i,2]+foot_pts[i,3])
                fwd = f_mid - h_mid
                fwd -= np.dot(fwd, n_paw)*n_paw
                if np.linalg.norm(fwd) < 1e-8: continue
                fwd /= np.linalg.norm(fwd)
                
                rgt = 0.5*((foot_pts[i,1]-foot_pts[i,0]) + (foot_pts[i,3]-foot_pts[i,2]))
                rgt -= np.dot(rgt, n_paw)*n_paw
                rgt -= np.dot(rgt, fwd)*fwd
                if np.linalg.norm(rgt) < 1e-8: continue
                lat = rgt / np.linalg.norm(rgt)
                
                fourpoint_plane_angle[i] = np.degrees(np.arctan2(np.dot(n_upper, lat), np.dot(n_upper, n_paw)))

        metric_arrays = {
            "head_trunk_bend_3d": head_trunk_bend_3d, 
            "head_trunk_yaw_signed": head_trunk_yaw_signed, 
            "fourpoint_plane_angle": fourpoint_plane_angle
        }

        return {
            "total_frames": total_frames,
            "body_scale": body_scale,
            "ground_normal_x": normal[0], "ground_normal_y": normal[1], "ground_normal_z": normal[2],
            "metric_arrays": metric_arrays,
            "metric_summary": {k: summarize_metric_array(v) for k, v in metric_arrays.items()}
        }

# ============================================================
# Data gathering
# ============================================================

def get_group_metric(categories, sexes, genos, metric_key, baseline=0.0):
    frame_values, signed_means, abs_means = [], [], []
    for sex in sexes:
        for geno in genos:
            for animal in categories[sex][geno]:
                arr = animal["metric_arrays"].get(metric_key, np.array([]))
                if len(arr) > 0:
                    vals = arr[np.isfinite(arr)] - baseline
                    if len(vals) > 0: 
                        frame_values.append(vals)
                        sm = np.mean(vals)
                        if np.isfinite(sm):
                            signed_means.append(sm)
                            abs_means.append(abs(sm))

    frames = np.concatenate(frame_values) if frame_values else np.array([])
    signed_means = np.asarray(signed_means, dtype=float)
    abs_means = np.asarray(abs_means, dtype=float)

    return frames[np.isfinite(frames)], signed_means[np.isfinite(signed_means)], abs_means[np.isfinite(abs_means)]


# ============================================================
# Statistical Formatting & Annotations
# ============================================================

def format_pval(p):
    if np.isnan(p): return "p=NA"
    stars = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
    if p >= 0.001:
        return f"{stars}\n(p={p:.3f})"
    else:
        return f"{stars}\n(p={p:.2e})" if p < 0.0001 else f"{stars}\n(p={p:.4f})"

def add_pval_annotation_1samp(ax, x_center, y_base, p_value, y_range):
    if np.isnan(p_value): return
    y_top = y_base + y_range * 0.05
    label = format_pval(p_value)
    ax.plot([x_center-0.15, x_center+0.15], [y_top, y_top], color='black', lw=1.5, zorder=4)
    ax.text(x_center, y_top, label, 
            ha='center', va='bottom', fontsize=9, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='gray', alpha=0.9),
            zorder=5)

def add_pval_annotation_ind(ax, x1, x2, y_base, p_value, y_range):
    if np.isnan(p_value): return
    y_top = y_base + y_range * 0.05
    label = format_pval(p_value)
    h = y_range * 0.02
    ax.plot([x1, x1, x2, x2], [y_top, y_top+h, y_top+h, y_top], color='black', lw=1.5, zorder=4)
    ax.text((x1 + x2) / 2, y_top + h, label, 
            ha='center', va='bottom', fontsize=9, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='gray', alpha=0.9),
            zorder=5)

def get_wt_index(label, wt_indices, all_labels):
    if len(wt_indices) == 1:
        return wt_indices[0]
    is_male = 'male' in label.lower()
    is_female = 'female' in label.lower()
    for w_idx in wt_indices:
        wt_label = all_labels[w_idx].lower()
        if is_male and 'male' in wt_label: return w_idx
        if is_female and 'female' in wt_label: return w_idx
    return wt_indices[0] if wt_indices else None

def find_sex_pairs(labels):
    clean_labels = [str(lbl).split("\n")[0].strip() for lbl in labels]
    pairs = []
    for i, lbl in enumerate(clean_labels):
        low = lbl.lower()
        if low.startswith("male"):
            suffix = lbl[4:].strip()
            for j, lbl2 in enumerate(clean_labels):
                low2 = lbl2.lower()
                if low2.startswith("female"):
                    suffix2 = lbl2[6:].strip()
                    if suffix == suffix2:
                        pairs.append((i, j, suffix))
    return pairs

def annotate_sex_pair_tests(ax, labels, data):
    pairs = find_sex_pairs(labels)
    if len(pairs) == 0: return

    y_min, y_max = ax.get_ylim()
    y_range = y_max - y_min if y_max > y_min else 1.0
    current_top = y_max

    for i, j, _suffix in pairs:
        if i >= len(data) or j >= len(data): continue
        a = np.asarray(data[i], dtype=float)
        b = np.asarray(data[j], dtype=float)
        a = a[np.isfinite(a)]
        b = b[np.isfinite(b)]

        if len(a) > 1 and len(b) > 1:
            t, p = stats.ttest_ind(a, b, equal_var=False)
            y_base = max(np.max(a), np.max(b), current_top)
            add_pval_annotation_ind(ax, i + 1, j + 1, y_base, p, y_range)
            current_top = y_base + y_range * 0.18

    ax.set_ylim(y_min, current_top + y_range * 0.1)

def annotate_vs_wt_tests(ax, labels, data):
    clean_labels = [str(lbl).split("\n")[0].strip() for lbl in labels]
    wt_idx = None
    for i, lbl in enumerate(clean_labels):
        if lbl.lower() == "wt" or lbl.lower().endswith("wt"):
            wt_idx = i
            break
    if wt_idx is None: return

    wt_vals = np.asarray(data[wt_idx], dtype=float)
    wt_vals = wt_vals[np.isfinite(wt_vals)]
    if len(wt_vals) < 2: return

    y_min, y_max = ax.get_ylim()
    y_range = y_max - y_min if y_max > y_min else 1.0
    current_top = y_max

    for i, vals in enumerate(data):
        if i == wt_idx: continue
        vals = np.asarray(vals, dtype=float)
        vals = vals[np.isfinite(vals)]

        if len(vals) > 1:
            t, p = stats.ttest_ind(vals, wt_vals, equal_var=False)
            y_base = max(np.max(vals), np.max(wt_vals), current_top)
            add_pval_annotation_ind(ax, i + 1, wt_idx + 1, y_base, p, y_range)
            current_top = y_base + y_range * 0.18

    ax.set_ylim(y_min, current_top + y_range * 0.1)

# ============================================================
# Plot helpers
# ============================================================

def get_color(label):
    label_lower = label.lower()
    if "female" in label_lower: return "hotpink"
    if "male" in label_lower: return "dodgerblue"
    if "hom" in label_lower: return "red"
    if "fet" in label_lower: return "orange"
    if "wt" in label_lower: return "blue"
    return "gray"

def plot_box_scatter_axis(ax, data_list, ylabel, title, test_type='vs_wt'):
    rng = np.random.default_rng(0)
    plot_data, plot_labels, plot_colors = [], [], []
    for label, vals in data_list:
        vals = vals[np.isfinite(vals)]
        if len(vals) > 0:
            plot_data.append(vals)
            plot_labels.append(f"{label}\nN={len(vals)}")
            plot_colors.append(get_color(label))
    if len(plot_data) == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(title); ax.set_ylabel(ylabel); ax.grid(True, alpha=0.3); return

    bp = ax.boxplot(plot_data, labels=plot_labels, patch_artist=True, widths=0.5, showmeans=True, meanline=True,
                    medianprops=dict(color="black", linewidth=1.5), meanprops=dict(color="green", linestyle="--", linewidth=2))
    for patch, c in zip(bp["boxes"], plot_colors): patch.set_facecolor(c); patch.set_alpha(0.5)
    for i, vals in enumerate(plot_data):
        x = rng.normal(i + 1, 0.04, size=len(vals))
        ax.scatter(x, vals, color="black", alpha=0.7, s=30)
        
    ax.axhline(0, color="black", linestyle=":", linewidth=1)
    ax.set_title(title); ax.set_ylabel(ylabel); ax.grid(True, alpha=0.3, axis="y")
    
    y_min, y_max = ax.get_ylim()
    y_range = y_max - y_min if y_max > y_min else 1.0
    current_max = y_max
    
    if test_type == 'vs_zero':
        for i, vals in enumerate(plot_data):
            if len(vals) > 1:
                t, p = stats.ttest_1samp(vals, 0)
                add_pval_annotation_1samp(ax, i + 1, np.max(vals), p, y_range)
                current_max = max(current_max, np.max(vals) + y_range * 0.2)
    elif test_type == 'vs_wt':
        wt_indices = [i for i, label in enumerate(plot_labels) if 'wt' in label.lower()]
        for i, vals in enumerate(plot_data):
            if 'wt' in plot_labels[i].lower(): continue
            wt_idx = get_wt_index(plot_labels[i], wt_indices, plot_labels)
            if wt_idx is not None:
                wt_vals = plot_data[wt_idx]
                if len(vals) > 1 and len(wt_vals) > 1:
                    t, p = stats.ttest_ind(vals, wt_vals, equal_var=False)
                    y_base = max(np.max(vals), np.max(wt_vals))
                    add_pval_annotation_ind(ax, i + 1, wt_idx + 1, y_base, p, y_range)
                    current_max = max(current_max, y_base + y_range * 0.2)
                    
    ax.set_ylim(y_min, current_max + y_range * 0.1)

def plot_group_comparison(data_list, title, ylabel, save_base_path, panel4_stats="vs_wt"):
    filtered = [(l, f[np.isfinite(f)], s[np.isfinite(s)], a[np.isfinite(a)]) for l, f, s, a in data_list if len(f[np.isfinite(f)]) > 0 or len(s[np.isfinite(s)]) > 0]
    if not filtered: return
    labels = [d[0] for d in filtered]
    colors = [get_color(lbl) for lbl in labels]
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    rng = np.random.default_rng(0)

    ax = axes[0, 0]
    all_frames = np.concatenate([d[1] for d in filtered if len(d[1]) > 0]) if any(len(d[1]) > 0 for d in filtered) else np.array([])
    if len(all_frames) > 0:
        bins = np.linspace(-50, 50, 50) 
        for (label, frames, _, _), c in zip(filtered, colors):
            if len(frames) > 0: ax.hist(frames, bins=bins, alpha=0.5, color=c, density=True, label=f"{label} frames={len(frames)}")
        ax.legend()
    else: ax.text(0.5, 0.5, "No frame data", ha="center", va="center", transform=ax.transAxes)
    ax.set_title("Signed frame distribution (Relative to WT=0)"); ax.set_xlabel(ylabel); ax.set_ylabel("Density")
    ax.axvline(0, color="black", linestyle=":", linewidth=1); ax.grid(True, alpha=0.3)
    ax.set_xlim(-50, 50) 

    ax = axes[0, 1]
    plotted = False
    for (label, frames, _, _), c in zip(filtered, colors):
        if len(frames) > 0:
            frames_sorted = np.sort(frames)
            cdf = np.arange(1, len(frames_sorted) + 1) / len(frames_sorted)
            ax.plot(frames_sorted, cdf, color=c, linewidth=2, label=label)
            plotted = True
    if plotted: ax.legend()
    else: ax.text(0.5, 0.5, "No frame data", ha="center", va="center", transform=ax.transAxes)
    ax.set_title("Signed frame CDF (Relative to WT=0)"); ax.set_xlabel(ylabel); ax.set_ylabel("Cumulative probability")
    ax.axvline(0, color="black", linestyle=":", linewidth=1); ax.grid(True, alpha=0.3)
    ax.set_xlim(-50, 50) 

    ax = axes[1, 0]
    xticks, xticklabels = [], []
    for i, (label, _, signed, _) in enumerate(filtered):
        xticks.append(i + 1); xticklabels.append(f"{label}\nN={len(signed)}")
        if len(signed) > 0:
            x = rng.normal(i + 1, 0.04, size=len(signed))
            ax.scatter(x, signed, color=colors[i], alpha=0.75, edgecolor="black", s=45)
            ax.plot([i + 0.75, i + 1.25], [np.median(signed), np.median(signed)], color="black", linewidth=2)
    ax.axhline(0, color="black", linestyle=":", linewidth=1)
    ax.set_xticks(xticks); ax.set_xticklabels(xticklabels)
    ax.set_title("Panel 3: Individual animal signed mean (Relative to WT=0)"); ax.set_ylabel(f"Signed mean {ylabel}"); ax.grid(True, alpha=0.3, axis="y")

    ax = axes[1, 1]
    abs_data, abs_labels, abs_colors = [], [], []
    for i, (label, _, _, abs_means) in enumerate(filtered):
        if len(abs_means) > 0:
            abs_data.append(abs_means)
            abs_labels.append(f"{label}\nN={len(abs_means)}")
            abs_colors.append(colors[i])
            
    if len(abs_data) > 0:
        bp = ax.boxplot(abs_data, labels=abs_labels, patch_artist=True, widths=0.5, showmeans=True, meanline=True,
                        medianprops=dict(color="black", linewidth=1.5), meanprops=dict(color="green", linestyle="--", linewidth=2))
        for patch, c in zip(bp["boxes"], abs_colors): patch.set_facecolor(c); patch.set_alpha(0.5)
        for i, vals in enumerate(abs_data):
            x = rng.normal(i + 1, 0.04, size=len(vals))
            ax.scatter(x, vals, color="black", alpha=0.7, s=35)

        if panel4_stats == "vs_wt":
            annotate_vs_wt_tests(ax, abs_labels, abs_data)
        elif panel4_stats == "sex_pairs":
            annotate_sex_pair_tests(ax, abs_labels, abs_data)
    else: ax.text(0.5, 0.5, "No animal mean data", ha="center", va="center", transform=ax.transAxes)
    ax.axhline(0, color="black", linestyle=":", linewidth=1)
    ax.set_title("Panel 4: Absolute deviation from WT baseline"); ax.set_ylabel(f"Absolute mean {ylabel}"); ax.grid(True, alpha=0.3, axis="y")

    fig.suptitle(title, fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    save_figure(fig, save_base_path)

def make_metric_figures(categories, metric_key, metric_label, global_bl, male_bl, female_bl):
    fig1_data = []
    for geno, label in [("homo", "HOM"), ("fet", "FET"), ("wt", "WT")]:
        frames, signed, abs_means = get_group_metric(categories, ["male", "female"], [geno], metric_key, baseline=global_bl)
        fig1_data.append((label, frames, signed, abs_means))
    plot_group_comparison(fig1_data, f"Figure 1: All animals by genotype | {metric_label}", metric_label, os.path.join(FIG_DIR, f"fig1_all_{metric_key}"), panel4_stats="vs_wt")

    fig2_data = []
    for geno, label in [("homo", "HOM"), ("fet", "FET"), ("wt", "WT")]:
        frames, signed, abs_means = get_group_metric(categories, ["male"], [geno], metric_key, baseline=male_bl)
        fig2_data.append((label, frames, signed, abs_means))
    plot_group_comparison(fig2_data, f"Figure 2: Male only by genotype | {metric_label}", metric_label, os.path.join(FIG_DIR, f"fig2_male_{metric_key}"), panel4_stats="vs_wt")

    fig3_data = []
    for geno, label in [("homo", "HOM"), ("fet", "FET"), ("wt", "WT")]:
        frames, signed, abs_means = get_group_metric(categories, ["female"], [geno], metric_key, baseline=female_bl)
        fig3_data.append((label, frames, signed, abs_means))
    plot_group_comparison(fig3_data, f"Figure 3: Female only by genotype | {metric_label}", metric_label, os.path.join(FIG_DIR, f"fig3_female_{metric_key}"), panel4_stats="vs_wt")

    fig4_data = []
    for geno, geno_label in [("homo", "HOM"), ("fet", "FET"), ("wt", "WT")]:
        frames_m, signed_m, abs_m = get_group_metric(categories, ["male"], [geno], metric_key, baseline=male_bl)
        frames_f, signed_f, abs_f = get_group_metric(categories, ["female"], [geno], metric_key, baseline=female_bl)
        fig4_data.append((f"Male {geno_label}", frames_m, signed_m, abs_m))
        fig4_data.append((f"Female {geno_label}", frames_f, signed_f, abs_f))
    plot_group_comparison(fig4_data, f"Figure 4: Male vs female by genotype | {metric_label}", metric_label, os.path.join(FIG_DIR, f"fig4_sex_by_genotype_{metric_key}"), panel4_stats="sex_pairs")

def build_animal_summary_rows(categories):
    rows = []
    for sex in ["male", "female"]:
        for geno in ["homo", "fet", "wt"]:
            for animal in categories[sex][geno]:
                row = {"folder": animal.get("folder", ""), "sex": sex, "genotype": geno, "total_frames": animal.get("total_frames", np.nan),
                       "body_scale": animal.get("body_scale", np.nan), "baseline_adjusted": True}
                for metric_name, summary in animal.get("metric_summary", {}).items():
                    for stat_name, stat_val in summary.items(): row[f"{metric_name}__{stat_name}"] = stat_val
                rows.append(row)
    return rows

# ============================================================
# 3D Visualization Helpers
# ============================================================

def plot_skeleton_3d(frame_pts, joints_idx, joint_colors, ax, title):
    for i, (j1, j2) in enumerate(joints_idx):
        if j1 >= len(frame_pts) or j2 >= len(frame_pts): continue
        p1 = frame_pts[j1]
        p2 = frame_pts[j2]
        if np.all(np.isfinite(p1)) and np.all(np.isfinite(p2)):
            c = joint_colors[i] if i < len(joint_colors) else [0.5, 0.5, 0.5]
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]], color=c, linewidth=3)
    
    valid_joints = frame_pts[np.all(np.isfinite(frame_pts), axis=1)]
    if len(valid_joints) > 0:
        ax.scatter(valid_joints[:,0], valid_joints[:,1], valid_joints[:,2], color='black', s=15, depthshade=True)
    ax.set_title(title)
def add_expanded_plane(ax, points, normal, color, half_extent, alpha=0.18):
    """
    Adds a large rectangular plane patch to a 3D axis.

    Parameters
    ----------
    ax : matplotlib 3D axis
    points : (N, 3) array
        Points belonging to the plane, e.g. 4 paws or 4 upper-body points.
    normal : (3,) array
        Plane normal.
    color : str
        Plane color.
    half_extent : float
        Half-width/height of the plate. Larger means bigger plate.
    alpha : float
        Transparency.
    """
    pts = points[np.all(np.isfinite(points), axis=1)]
    normal = np.asarray(normal, dtype=float)

    nrm = np.linalg.norm(normal)
    if nrm < 1e-12 or len(pts) < 3:
        return None

    normal = normal / nrm
    center = np.mean(pts, axis=0)
    centered = pts - center

    # Get a preferred in-plane direction from the actual landmark spread
    try:
        _, _, Vt = np.linalg.svd(centered)
        u = Vt[0]
    except np.linalg.LinAlgError:
        tmp = np.array([1.0, 0.0, 0.0]) if abs(normal[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        u = np.cross(normal, tmp)

    # Force u to lie in the plane
    u = u - np.dot(u, normal) * normal
    u_norm = np.linalg.norm(u)

    if u_norm < 1e-8:
        tmp = np.array([1.0, 0.0, 0.0]) if abs(normal[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        u = np.cross(normal, tmp)
        u_norm = np.linalg.norm(u)

    u = u / u_norm

    # Second in-plane direction
    v = np.cross(normal, u)
    v_norm = np.linalg.norm(v)
    if v_norm < 1e-8:
        return None
    v = v / v_norm

    # Large plate corners
    corners = np.array([
        center + u * half_extent + v * half_extent,
        center - u * half_extent + v * half_extent,
        center - u * half_extent - v * half_extent,
        center + u * half_extent - v * half_extent,
    ])

    poly = Poly3DCollection(
        [corners],
        alpha=alpha,
        facecolor=color,
        edgecolor=color,
        linewidth=2
    )

    ax.add_collection3d(poly)
    return corners

def process_animal_3d(animal, metric_key, metric_label, group_label, joints_idx, joint_colors, analyzer):
    folder = animal["folder"]
    mat_file = os.path.join(ROOT, folder, "DANNCE", "predict00", "save_data_AVG.mat")
    if not os.path.exists(mat_file):
        return

    pred = analyzer.load_3d_data(mat_file)

    metric_arr = animal["metric_arrays"][metric_key]
    valid_vals = metric_arr[np.isfinite(metric_arr)]
    if len(valid_vals) == 0:
        return

    median_val = np.median(valid_vals)
    diffs = np.abs(metric_arr - median_val)
    diffs[~np.isfinite(diffs)] = np.inf
    best_frame_idx = np.argmin(diffs)

    # Shape: (num_joints, 3)
    frame_pts = pred[best_frame_idx, :, :].T

    normal = np.array([
        animal["ground_normal_x"],
        animal["ground_normal_y"],
        animal["ground_normal_z"]
    ])

    foot_pts = np.transpose(pred[:, :, analyzer.foot_idx], (0, 2, 1))
    body_pts = np.transpose(pred[:, :, analyzer.upper_idx], (0, 2, 1)).reshape(-1, 3)

    centroid, _ = fit_ground_plane_lower_envelope(foot_pts.reshape(-1, 3), body_pts)
    if centroid is None:
        centroid = np.mean(frame_pts[np.all(np.isfinite(frame_pts), axis=1)], axis=0)

    fig = plt.figure(figsize=(16, 8))

    # ==================================================
    # Plot 1: Head-Trunk Yaw
    # ==================================================
    ax1 = fig.add_subplot(121, projection="3d")
    plot_skeleton_3d(
        frame_pts,
        joints_idx,
        joint_colors,
        ax1,
        f"{group_label} - {folder}\n{metric_label} (Yaw)"
    )

    if "Snout" in analyzer.opt and "SpineF" in analyzer.idx and "SpineM" in analyzer.idx:
        snout = frame_pts[analyzer.opt["Snout"]]
        spineF = frame_pts[analyzer.idx["SpineF"]]
        spineM = frame_pts[analyzer.idx["SpineM"]]

        if np.all(np.isfinite([snout, spineF, spineM])):
            ax1.plot(
                [spineF[0], spineM[0]],
                [spineF[1], spineM[1]],
                [spineF[2], spineM[2]],
                "g-",
                linewidth=4,
                label="Trunk (SpineF -> SpineM)"
            )

            ax1.plot(
                [spineF[0], snout[0]],
                [spineF[1], snout[1]],
                [spineF[2], snout[2]],
                "r-",
                linewidth=4,
                label="Head (SpineF -> Snout)"
            )

            def project_to_plane(pt, centroid, normal):
                v = pt - centroid
                return pt - np.dot(v, normal) * normal

            snout_proj = project_to_plane(snout, centroid, normal)
            spineF_proj = project_to_plane(spineF, centroid, normal)
            spineM_proj = project_to_plane(spineM, centroid, normal)

            ax1.plot(
                [spineF_proj[0], spineM_proj[0]],
                [spineF_proj[1], spineM_proj[1]],
                [spineF_proj[2], spineM_proj[2]],
                "g--",
                linewidth=2,
                alpha=0.6
            )

            ax1.plot(
                [spineF_proj[0], snout_proj[0]],
                [spineF_proj[1], snout_proj[1]],
                [spineF_proj[2], snout_proj[2]],
                "r--",
                linewidth=2,
                alpha=0.6
            )

            ax1.legend(loc="upper left")

    # ==================================================
    # Plot 2: Four-point plane angle with expanded planes
    # ==================================================
    ax2 = fig.add_subplot(122, projection="3d")
    plot_skeleton_3d(
        frame_pts,
        joints_idx,
        joint_colors,
        ax2,
        f"{group_label} - {folder}\nFour-point plane angle"
    )

    valid_skel = frame_pts[np.all(np.isfinite(frame_pts), axis=1)]

    if len(valid_skel) > 0:
        skel_min = np.min(valid_skel, axis=0)
        skel_max = np.max(valid_skel, axis=0)
        skel_range = float(np.max(skel_max - skel_min))
    else:
        skel_range = 100.0

    plate_half = skel_range * PLATE_HALF_SCALE
    normal_arrow_len = skel_range * 0.35
    plane_corners = []

    paw_idx = [analyzer.idx[k] for k in ["ForepawL", "ForepawR", "HindpawL", "HindpawR"]]
    paws = frame_pts[paw_idx]

    upper_idx = [analyzer.idx[k] for k in ["EarL", "EarR", "SpineF", "SpineM"]]
    upper = frame_pts[upper_idx]

    # -------------------------
    # Paw / ground plane plate
    # -------------------------
    if np.all(np.isfinite(paws)):
        _, n_paw_display, _ = fit_plane_normal(paws)

        if n_paw_display is None:
            n_paw_display = normal.copy()

        if np.dot(n_paw_display, normal) < 0:
            n_paw_display = -n_paw_display

        paw_corners = add_expanded_plane(
            ax2,
            paws,
            n_paw_display,
            color="blue",
            half_extent=plate_half,
            alpha=0.18
        )

        if paw_corners is not None:
            plane_corners.append(paw_corners)

        paw_centroid = np.mean(paws, axis=0)

        ax2.quiver(
            paw_centroid[0],
            paw_centroid[1],
            paw_centroid[2],
            n_paw_display[0],
            n_paw_display[1],
            n_paw_display[2],
            color="blue",
            length=normal_arrow_len,
            normalize=True,
            label="Paw plane normal"
        )

    # -------------------------
    # Upper-body plane plate
    # -------------------------
    if np.all(np.isfinite(upper)):
        _, n_upper, _ = fit_plane_normal(upper)

        if n_upper is not None:
            if np.dot(n_upper, normal) < 0:
                n_upper = -n_upper

            upper_corners = add_expanded_plane(
                ax2,
                upper,
                n_upper,
                color="purple",
                half_extent=plate_half,
                alpha=0.18
            )

            if upper_corners is not None:
                plane_corners.append(upper_corners)

            upper_centroid = np.mean(upper, axis=0)

            ax2.quiver(
                upper_centroid[0],
                upper_centroid[1],
                upper_centroid[2],
                n_upper[0],
                n_upper[1],
                n_upper[2],
                color="purple",
                length=normal_arrow_len,
                normalize=True,
                label="Upper-body plane normal"
            )

    ax2.legend(loc="upper left")

    # ==================================================
    # Axis limits
    # ==================================================
    def set_3d_limits(ax, pts):
        pts = np.asarray(pts)
        if len(pts) == 0:
            return

        min_xyz = np.min(pts, axis=0)
        max_xyz = np.max(pts, axis=0)
        center = (min_xyz + max_xyz) / 2.0
        max_range = float(np.max(max_xyz - min_xyz)) / 2.0

        ax.set_xlim(center[0] - max_range, center[0] + max_range)
        ax.set_ylim(center[1] - max_range, center[1] + max_range)
        ax.set_zlim(center[2] - max_range, center[2] + max_range)

    # Left panel: skeleton-sized view
    if len(valid_skel) > 0:
        set_3d_limits(ax1, valid_skel)

    # Right panel: include expanded plane corners
    display_pts = []

    if len(valid_skel) > 0:
        display_pts.append(valid_skel)

    for corners in plane_corners:
        display_pts.append(corners)

    if display_pts:
        set_3d_limits(ax2, np.vstack(display_pts))

    for ax in [ax1, ax2]:
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")

    fig.suptitle(
        f"3D Visualization: {metric_label} | Frame {best_frame_idx}",
        fontsize=14
    )

    fig.tight_layout(rect=[0, 0, 1, 0.95])

    # Interactive: rotate manually and save using the toolbar
    plt.show()

def create_3d_visualizations(categories, metric_key, metric_label, joints_idx, joint_colors, analyzer):
    hom_animals = categories["male"]["homo"] + categories["female"]["homo"]
    wt_animals = categories["male"]["wt"] + categories["female"]["wt"]
    
    if not hom_animals or not wt_animals:
        print(f"Skipping 3D vis for {metric_label}: missing HOM or WT animals.")
        return
        
    hom_animals = [a for a in hom_animals if metric_key in a["metric_summary"] and np.isfinite(a["metric_summary"][metric_key].get("signed_mean", np.nan))]
    wt_animals = [a for a in wt_animals if metric_key in a["metric_summary"] and np.isfinite(a["metric_summary"][metric_key].get("signed_mean", np.nan))]
    
    if not hom_animals or not wt_animals:
        print(f"Skipping 3D vis for {metric_label}: no valid metric data.")
        return

    sig_hom = max(hom_animals, key=lambda a: abs(a["metric_summary"][metric_key]["signed_mean"]))
    best_wt = min(wt_animals, key=lambda a: abs(a["metric_summary"][metric_key]["signed_mean"]))
    
    print(f"\n--- 3D Visualization for {metric_label} ---")
    print(f"Most significant HOM: {sig_hom['folder']} (signed_mean: {sig_hom['metric_summary'][metric_key]['signed_mean']:.2f})")
    print(f"Best WT: {best_wt['folder']} (signed_mean: {best_wt['metric_summary'][metric_key]['signed_mean']:.2f})")
    
    process_animal_3d(sig_hom, metric_key, metric_label, "HOM", joints_idx, joint_colors, analyzer)
    process_animal_3d(best_wt, metric_key, metric_label, "WT", joints_idx, joint_colors, analyzer)

# ============================================================
# Main Execution
# ============================================================

if __name__ == "__main__":
    ensure_dirs()
    analyzer = GroundedTiltAnalyzer()
    categories = {"male": {"homo": [], "wt": [], "fet": []}, "female": {"homo": [], "wt": [], "fet": []}}

    print("Loading and analyzing all animals...")
    for folder in os.listdir(ROOT):
        folder_path = os.path.join(ROOT, folder)
        if not os.path.isdir(folder_path): continue
        sex, geno = parse_folder(folder)
        if sex == "unknown" or geno == "unknown": continue
        mat_file = os.path.join(folder_path, "DANNCE", "predict00", "save_data_AVG.mat")
        if not os.path.exists(mat_file): continue
        try:
            record = analyzer.analyze_file(mat_file)
            if record is None: continue
            record["folder"] = folder
            categories[sex][geno].append(record)
            print(f"Done: {folder} | total_frames={record['total_frames']}")
        except Exception as e:
            print(f"Error analyzing {folder}: {e}")

    print("\n--- Calculating WT Baselines ---")
    global_wt_baselines = {}
    male_wt_baselines = {}
    female_wt_baselines = {}
    
    for metric in ALL_FRAME_METRICS:
        wt_vals_all, wt_vals_m, wt_vals_f = [], [], []
        
        for animal in categories["male"]["wt"]:
            vals = animal["metric_arrays"][metric][np.isfinite(animal["metric_arrays"][metric])]
            wt_vals_all.extend(vals)
            wt_vals_m.extend(vals)
            
        for animal in categories["female"]["wt"]:
            vals = animal["metric_arrays"][metric][np.isfinite(animal["metric_arrays"][metric])]
            wt_vals_all.extend(vals)
            wt_vals_f.extend(vals)
            
        global_wt_baselines[metric] = np.mean(wt_vals_all) if len(wt_vals_all) > 0 else 0.0
        male_wt_baselines[metric] = np.mean(wt_vals_m) if len(wt_vals_m) > 0 else 0.0
        female_wt_baselines[metric] = np.mean(wt_vals_f) if len(wt_vals_f) > 0 else 0.0
        
        print(f"Frame Metric {metric:25} : Global WT={global_wt_baselines[metric]:+.4f} | Male WT={male_wt_baselines[metric]:+.4f} | Female WT={female_wt_baselines[metric]:+.4f}")

    print("\nSaving posture metric figures...")
    for metric_key, metric_label in METRICS_TO_PLOT:
        make_metric_figures(categories, metric_key, metric_label, 
                            global_wt_baselines[metric_key], 
                            male_wt_baselines[metric_key], 
                            female_wt_baselines[metric_key])

    print("\nGenerating 3D Visualizations...")
    print("Note: 3D plots will open interactively. You can rotate them and save them manually using the matplotlib toolbar.")
    for metric_key, metric_label in METRICS_TO_PLOT:
        create_3d_visualizations(categories, metric_key, metric_label, analyzer.joints_idx, analyzer.joint_colors, analyzer)

    print("\nApplying Global WT baselines for final CSV summaries...")
    for sex in ["male", "female"]:
        for geno in ["homo", "fet", "wt"]:
            for animal in categories[sex][geno]:
                for metric in ALL_FRAME_METRICS:
                    animal["metric_arrays"][metric] -= global_wt_baselines[metric]
                animal["metric_summary"] = {k: summarize_metric_array(v) for k, v in animal["metric_arrays"].items()}

    print("Saving tables...")
    write_csv(os.path.join(TABLE_DIR, "animal_summary.csv"), build_animal_summary_rows(categories))

    print("\nFinished.")
    print(f"Figures saved to: {FIG_DIR}")
    print(f"Tables saved to: {TABLE_DIR}")