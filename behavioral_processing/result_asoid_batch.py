import os
import json
import glob
import h5py
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches 
from scipy import stats
from statsmodels.stats.multitest import multipletests
import brokenaxes


_original_standardize = brokenaxes.BrokenAxes.standardize_ticks
def _patched_standardize_ticks(self, xbase=None, ybase=None):
    return _original_standardize(self, xbase=1, ybase=10000)
brokenaxes.BrokenAxes.standardize_ticks = _patched_standardize_ticks

DOM_COLOR = '#2E86AB'
SUB_COLOR = '#E94F37'


def load_h5_file(h5_path, min_start=None, min_end=None, fps=None):
    with h5py.File(h5_path, 'r') as f:
        behav_array = f['/data/behaviors'][:].flatten()
        behavior_map = json.loads(f['/meta/behavior_map'][()])
        color_map = json.loads(f['/meta/color_map'][()])
        meta = {k: v for k, v in f['/meta'].attrs.items()}

    fps = fps or meta.get('fps', 30.0)
    total_frames = len(behav_array)
    
    # Time range filtering (minutes -> frames)
    if min_start is not None or min_end is not None:
        start_frame = int((min_start or 0) * 60 * fps)
        end_frame = int((min_end or total_frames / 60 / fps) * 60 * fps)
        start_frame = max(0, min(start_frame, total_frames))
        end_frame = max(start_frame, min(end_frame, total_frames))
        behav_array = behav_array[start_frame:end_frame]
        
    return behav_array, behavior_map, color_map, fps

def bin_behavior_array(behav_array, behavior_map, bin_size_min, fps):
    bin_frames = int(bin_size_min * 60 * fps)
    beh_len = len(behav_array)
    n_bins = (beh_len - 1) // bin_frames + 1
    n_behavs = len(behavior_map)

    padded = np.zeros(n_bins * bin_frames, dtype=int)
    padded[:beh_len] = behav_array
    padded = padded.reshape(n_bins, bin_frames)
    
    counts = np.zeros((n_bins, n_behavs), dtype=int)
    for b in range(n_bins):
        counts[b] = np.bincount(padded[b], minlength=n_behavs)
    return counts

def apply_filter_per_pair(behav_array, behavior_map, threshold_frames):
    counts = np.bincount(behav_array, minlength=len(behavior_map))
    mask = counts < threshold_frames
    filtered = behav_array.copy()
    for idx in np.where(mask)[0]:
        filtered[behav_array == idx] = 0
    return filtered

def aggregate_all_files(h5_dir, min_start, min_end, filter_thresh, filter_date, filter_se, behaviors_to_exclude, bin_size_min):
    h5_files = sorted(glob.glob(os.path.join(h5_dir, "*.h5")))
    if not h5_files:
        raise ValueError("No .h5 files found.")
    
    if filter_date:
        h5_files_filtered = []
        for f in h5_files:
            with h5py.File(f, 'r') as h5f:
                meta = {k: v for k, v in h5f['/meta'].attrs.items()}
                day = meta["day"]
                if int(day) in filter_date:
                    h5_files_filtered.append(f)
        h5_files = h5_files_filtered

    if filter_se is not None:
        h5_files_filtered = []
        for f in h5_files:
            with h5py.File(f, 'r') as h5f:
                meta = {k: v for k, v in h5f['/meta'].attrs.items()}
                se = meta["se_status"]
                if se and filter_se == "SE":
                    h5_files_filtered.append(f)
                elif not se and filter_se == "VG":
                    h5_files_filtered.append(f)
        h5_files = h5_files_filtered

    _, ref_map, color_map, fps = load_h5_file(h5_files[0], min_start, min_end)
    base_names = sorted(set(n.split('_', 1)[1] for n in ref_map  if '_' in n and n != 'other'))
    for bn in base_names:
        if bn in behaviors_to_exclude:
            base_names.remove(bn)
    dom_src = {b: ref_map.index(f"dom_{b}") if f"dom_{b}" in ref_map else None for b in base_names}
    sub_src = {b: ref_map.index(f"sub_{b}") if f"sub_{b}" in ref_map else None for b in base_names}

    n_files = len(h5_files)
    n_behav = len(base_names)
    aligned_list = []

    max_bins = 0
    for f in h5_files:
        arr, _, _, _ = load_h5_file(f, min_start, min_end, fps)
        if filter_thresh > 0:
            arr = apply_filter_per_pair(arr, ref_map, filter_thresh)

        full_binned = bin_behavior_array(arr, ref_map, bin_size_min, fps)
        n_bins_local = full_binned.shape[0]

        file_aligned = np.zeros((n_bins_local,n_behav,2), dtype=int)
        for j, base in enumerate(base_names):
            if dom_src[base] is not None:
                file_aligned[:, j, 0] = full_binned[:, dom_src[base]]
            if sub_src[base] is not None:
                file_aligned[:, j, 1] = full_binned[:, sub_src[base]]

        aligned_list.append(file_aligned)
        max_bins = max(max_bins, n_bins_local)

    binned_array = np.zeros((n_files,max_bins,n_behav,2), dtype=int)
    for i, file_aligned in enumerate(aligned_list):
        n_bins_local = file_aligned.shape[0]
        binned_array[i, :n_bins_local, :, :] = file_aligned

    return {
        'fps': fps,
        'n_files': n_files,
        'base_names': base_names,
        'color_map': {beh : "".join(raw_color) for beh, raw_color in color_map.items()},
        'behav_dict': {b: idx for idx, b in enumerate(base_names)},
        'binned_array': binned_array,
        'bin_size_min': bin_size_min
    }

# =============================================================================
# 2. PLOTTING FUNCTIONS
# =============================================================================

def plot_raw_duration_grouped(data, behavior_order, output_path):
    binned_array = data['binned_array']
    behav_dict = data["behav_dict"]
    color_map = data["color_map"]
    
    dom_totals = binned_array[..., 0].sum(axis=1) # (n_files, n_behav)
    sub_totals = binned_array[..., 1].sum(axis=1)
    
    plot_labels = ["Chamber", "Interaction"]
    dom_vals, sub_vals = [], []
    
    dom_vals.append(dom_totals.sum(axis=1))
    sub_vals.append(sub_totals.sum(axis=1))
    
    idle_idx = np.array(behav_dict["idle"])
    dom_interact = np.sum(np.delete(dom_totals, idle_idx, axis=1), axis=1)
    sub_interact = np.sum(np.delete(sub_totals, idle_idx, axis=1), axis=1)
    dom_vals.append(dom_interact)
    sub_vals.append(sub_interact)
    
    for name in behavior_order:
        if name not in behav_dict.keys() or name in ['other', 'idle']:
            continue
        idx = behav_dict[name]
        dom_vals.append(dom_totals[:, idx])
        sub_vals.append(sub_totals[:, idx])
        plot_labels.append(name.capitalize())
        
    dom_vals = np.array(dom_vals).T
    sub_vals = np.array(sub_vals).T
    n_cats = dom_vals.shape[1]
    
    def safe_paired_ttest(x, y):
        if np.all(x == x[0]) and np.all(y == y[0]): return 1.0
        try: return stats.ttest_rel(x, y).pvalue
        except: return 1.0

    dom_mean, sub_mean = dom_vals.mean(0), sub_vals.mean(0)
    dom_sem, sub_sem = stats.sem(dom_vals, 0), stats.sem(sub_vals, 0)
    p_vals = np.array([safe_paired_ttest(dom_vals[:,i], sub_vals[:,i]) for i in range(n_cats)])
    
    markers = ['***' if p<0.001 else '**' if p<0.01 else '*' if p<0.05 else '' for p in p_vals]
    
    plt.figure(figsize=(11, 7))

    max_mean = max(np.max(dom_mean[1:]), np.max(sub_mean[1:]))
    max_max = max(np.max(dom_vals), np.max(sub_vals))

    bax = brokenaxes.brokenaxes(ylims=((0, max_mean*1.15), (max_mean*1.15, max_max*1.05)), hspace=0.05, height_ratios=[1, 3])
    
    def adjust_hex_color(hex_color: str, factor: float) -> str:
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        if factor > 0:
            r = int(r + (255 - r) * factor)
            g = int(g + (255 - g) * factor)
            b = int(b + (255 - b) * factor)
        elif factor < 0:
            r = int(r * (1 + factor))
            g = int(g * (1 + factor))
            b = int(b * (1 + factor))
        
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))

        return f"#{r:02X}{g:02X}{b:02X}"

    x = np.arange(n_cats)
    dom_colors = []
    sub_colors = []
    for label in plot_labels:
        llabel = label.lower()
        if llabel == "chamber":
            raw_color = "#35C03C"
        elif llabel == "interaction":
            raw_color = "#6A9E86"
        else:
            raw_color = color_map.get(llabel, "#6A5ACD")
        dom_colors.append(adjust_hex_color(raw_color, 0.1))
        sub_colors.append(adjust_hex_color(raw_color, -0.1))

    w = 0.35
    bax.bar(x-w/2, dom_mean, w, yerr=dom_sem, color=dom_colors, capsize=3, alpha=0.33)
    bax.bar(x+w/2, sub_mean, w, yerr=sub_sem, color=sub_colors, capsize=3, alpha=0.33)
    
    for i in range(n_cats):
        jit_d = np.random.normal(x[i]-w/2, 0.01, dom_vals.shape[0])
        jit_s = np.random.normal(x[i]+w/2, 0.01, sub_vals.shape[0])
        bax.scatter(jit_d, dom_vals[:,i], color=dom_colors[i], alpha=0.8, s=10, zorder=3, label='_nolegend_')
        bax.scatter(jit_s, sub_vals[:,i], color=sub_colors[i], alpha=0.8, s=10, zorder=3, label='_nolegend_')
        for j in range(dom_vals.shape[0]):
            bax.plot([x[i]-w/2, x[i]+w/2], [dom_vals[j,i], sub_vals[j,i]], color='black', alpha=0.8, lw=0.8, label='_nolegend_')

        if markers[i]:
            y_pos = max(dom_mean[i], sub_mean[i]) + max(dom_sem[i], sub_sem[i])+2500
            bax.text(x[i], y_pos, markers[i], ha='center', va='bottom', fontsize=11, fontweight='bold')

    for ax in bax.axs:
        ax.axvline(x=1.5, color='black', linestyle='-', linewidth=1.2, alpha=1, zorder=2, label='_nolegend_')

    proxy_dom = mpatches.Patch(color="#BBBBBB", label='Dominant', alpha=0.8)
    proxy_sub = mpatches.Patch(color="#7C7C7C", label='Subordinate', alpha=0.8)
    bax.axs[0].legend(handles=[proxy_dom, proxy_sub], loc='upper right', frameon=True, fancybox=True, framealpha=0.9)

    bax.set_ylabel('Duration (frames)')
    bax.set_title('Raw Frame Counts: Dominant vs Subordinate')
    bax.axs[1].set_xticks(x)
    bax.axs[1].set_xticklabels(plot_labels, rotation=45, ha='right')
    bax.axs[0].tick_params(axis='y', labelleft=False)
    bax.grid(axis='y', alpha=0.3)

    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

def plot_preference_index(data, behavior_order, output_path):
    binned_array = data['binned_array']
    behav_dict = data["behav_dict"]
    color_map = data["color_map"]

    dom_totals = binned_array[..., 0].sum(axis=1) # (n_files, n_behav)
    sub_totals = binned_array[..., 1].sum(axis=1)

    labels = ["Chamber", "Interaction"]
    d = dom_totals.sum(axis=1)
    s = sub_totals.sum(axis=1)
    pi_list = [(d-s)/(d+s)]

    idle_idx = np.array(behav_dict["idle"])
    dom_interact = np.sum(np.delete(dom_totals, idle_idx, axis=1), axis=1)
    sub_interact = np.sum(np.delete(sub_totals, idle_idx, axis=1), axis=1)
    pi_list.append((dom_interact-sub_interact)/(dom_interact+sub_interact))

    for name in behavior_order:
        if name not in behav_dict.keys() or name in ['other', 'idle']:
            continue
        idx = behav_dict[name]
        d, s = dom_totals[:, idx], sub_totals[:, idx]
        pi = np.zeros_like(d, dtype=float)

        mask = d+s > 0
        pi[mask] = (d-s)[mask]/(d+s)[mask]
        pi_list.append(pi)
        labels.append(name.capitalize())

    if not pi_list:
        return
    pi_vals = np.array(pi_list).T
    
    pi_mean = pi_vals.mean(0)
    pi_sem = stats.sem(pi_vals, 0)
    p_vals = np.array([stats.ttest_1samp(pi_vals[:,i], 0).pvalue for i in range(pi_vals.shape[1])])
    markers = ['***' if p<0.001 else '**' if p<0.01 else '*' if p<0.05 else '' for p in p_vals]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(labels))

    color = []
    for label in labels:
        llabel = label.lower()
        if llabel == "chamber":
            color.append("#35C03C")
        elif llabel == "interaction":
            color.append("#6A9E86")
        else:
            color.append(color_map.get(llabel, "#6A5ACD"))
    
    ax.bar(x, pi_mean, yerr=pi_sem, color=color, capsize=3, alpha=0.3)
    ax.axvline(x=1.5, color='black', linestyle='-', linewidth=1.2, alpha=1, zorder=2, label='_nolegend_')
    
    for i in range(len(labels)):
        jit = np.random.normal(x[i], 0.04, pi_vals.shape[0])
        ax.scatter(jit, pi_vals[:,i], color=color[i], alpha=1, s=10, zorder=3)
        if markers[i]:
            ax.text(x[i], pi_mean[i]+pi_sem[i]+0.02, markers[i], ha='center', va='bottom', fontsize=10, fontweight='bold')
            
    ax.axhline(0, color='gray', linestyle='--', lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Preference Index (Dom-Sub)/(Dom+Sub)')
    ax.set_title('Preference Index by Behavior')
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

def plot_trends(data, behavior_order, cumulative=False, plot_individual=False, output_dir=None):
    binned_array = np.cumsum(data['binned_array'], axis=1) if cumulative else data['binned_array'].copy()
    behav_dict = data["behav_dict"]

    n_files, n_bins, n_behav = binned_array.shape[:3]
    time_axis = np.arange(n_bins) * data['bin_size_min']

    chamber_dom = binned_array[:, :, :, 0].sum(axis=2)
    chamber_sub = binned_array[:, :, :, 1].sum(axis=2)
    
    idle_idx = behav_dict.get("idle")
    interact_dom = np.sum(np.delete(binned_array[:, :, :, 0], idle_idx, axis=2), axis=2)
    interact_sub = np.sum(np.delete(binned_array[:, :, :, 1], idle_idx, axis=2), axis=2)

    beh_to_plot = []
    beh_to_plot.append(("Chamber", None, chamber_dom, chamber_sub))
    beh_to_plot.append(("Interaction", None, interact_dom, interact_sub))

    for name in behavior_order:
        if name not in behav_dict.keys() or name == 'other':
            continue
        idx = behav_dict[name]
        beh_to_plot.append((name, idx, None, None))

    if plot_individual:
        ind_dir = os.path.join(output_dir, "individual_trends")
        os.makedirs(ind_dir, exist_ok=True)
        for i in range(n_files):
            fig, axes = plt.subplots(len(beh_to_plot), 1, figsize=(10, 3*len(beh_to_plot)), sharex=True)
            if len(beh_to_plot)==1:
                axes=[axes]
            for ax, (base, idx, dom_data, sub_data) in zip(axes, beh_to_plot):
                if idx is None:
                    ax.plot(time_axis, dom_data[i], color=DOM_COLOR, lw=1, label='Dominant')
                    ax.plot(time_axis, sub_data[i], color=SUB_COLOR, lw=1, label='Subordinate')
                else:
                    ax.plot(time_axis, binned_array[i,:,idx,0], color=DOM_COLOR, lw=1, label='Dominant')
                    ax.plot(time_axis, binned_array[i,:,idx,1], color=SUB_COLOR, lw=1, label='Subordinate')
                ax.set_title(base.capitalize())
                ax.grid(alpha=0.3)
                step = max(1, n_bins//10)
                ax.set_ylim(0, None)
                ax.set_xlim(0, n_bins)
    
            axes[0].legend(fontsize=8, frameon=True)
            axes[-1].set_xlabel('Time (minutes)')
            axes[-1].set_xticks(time_axis[::step])
            axes[-1].set_xticklabels([str(int(t)) for t in time_axis[::step]], rotation=45, ha='right')
            plt.tight_layout()
            cumsum_label = "cumsum" if cumulative else "discrete"
            plt.savefig(os.path.join(ind_dir, f"trace_{i}_{cumsum_label}.png"), dpi=150)
            plt.close()
        return

    fig, axes = plt.subplots(len(beh_to_plot), 1, figsize=(10, 3*len(beh_to_plot)), sharex=True)
    if len(beh_to_plot)==1:
        axes=[axes]
    
    for ax, (base, idx, dom_data, sub_data) in zip(axes, beh_to_plot):
        if idx is None:
            d_series = dom_data
            s_series = sub_data
        else:
            d_series = binned_array[:,:,idx,0]
            s_series = binned_array[:,:,idx,1]
            
        if cumulative:
            for i in range(n_files): ax.plot(time_axis, d_series[i], color=DOM_COLOR, lw=0.6, alpha=0.3, zorder=1)
            for i in range(n_files): ax.plot(time_axis, s_series[i], color=SUB_COLOR, lw=0.6, alpha=0.3, zorder=1)
            
        d_mean = d_series.mean(0)
        d_sem = stats.sem(d_series, 0)
        ax.plot(time_axis, d_mean, color=DOM_COLOR, lw=1.3, marker='o', ms=3, label='Dominant', zorder=3)
        ax.fill_between(time_axis, d_mean-d_sem, d_mean+d_sem, color=DOM_COLOR, alpha=0.2, zorder=2)
            
        s_mean = s_series.mean(0)
        s_sem = stats.sem(s_series, 0)
        ax.plot(time_axis, s_mean, color=SUB_COLOR, lw=1.3, marker='s', ms=3, label='Subordinate', zorder=3)
        ax.fill_between(time_axis, s_mean-s_sem, s_mean+s_sem, color=SUB_COLOR, alpha=0.2, zorder=2)
            
        p_vals = [stats.ttest_rel(d_series[:,t], s_series[:,t]).pvalue for t in range(n_bins)]
        sig = multipletests(p_vals, alpha=0.05, method='fdr_bh')[0]
        for t in np.where(sig)[0]:
            y_max = max(d_series[:,t].mean(), s_series[:,t].mean())
            y_offset = max(stats.sem(d_series[:,t]), stats.sem(s_series[:,t])) * 0.5
            ax.text(time_axis[t], y_max + y_offset + 1, '★', color='red', ha='center', fontsize=10, zorder=4)
        
        y_max = max(d_series.mean(axis=0).max(), s_series.mean(axis=0).max())
        y_offset = max(stats.sem(d_series.max(axis=0)), stats.sem(s_series.max(axis=0)))
        ax.set_ylabel(f'{base.capitalize()}\nDuration (frames)')
        ax.grid(axis='y', alpha=0.3, ls='--', lw=0.5)
        ax.tick_params(axis='x', length=0)
        step = max(1, n_bins//10)
        ax.set_ylim(0, max(10, (y_max + y_offset)*1.15))
        ax.set_xlim(0, n_bins)
        
        if base.lower() == "interaction":
            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8, alpha=0.5)

    axes[0].legend(fontsize=9, frameon=True)
    axes[-1].set_xlabel('Time (minutes)')
    axes[-1].set_xticks(time_axis[::step])
    axes[-1].set_xticklabels([str(int(t)) for t in time_axis[::step]], rotation=45, ha='right')
    title = 'Cumulative' if cumulative else 'Raw'
    fig.suptitle(f'{title} Duration Trend: Mean ± SEM with Individual Traces', fontsize=13, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.98])
    plt.savefig(os.path.join(output_dir, f"plot_{3 if not cumulative else 4}_trend.png"), dpi=300, bbox_inches='tight')
    plt.close()

def plot_pi_trends(data, behavior_order, plot_individual=False, output_dir=None):
    binned_array = data['binned_array']
    behav_dict = data["behav_dict"]
    color_map = data["color_map"]
    bin_size_min = data['bin_size_min']
    
    n_files, n_bins, n_behav = binned_array.shape[:3]
    time_axis = np.arange(n_bins) * bin_size_min
    
    dom_data = binned_array[..., 0]
    sub_data = binned_array[..., 1]
    
    total = dom_data + sub_data
    pi_array = np.zeros_like(dom_data, dtype=float)
    mask = total > 0
    pi_array[mask] = (dom_data[mask] - sub_data[mask]) / total[mask]
    beh_to_plot = []
    
    chamber_dom = dom_data.sum(axis=2)
    chamber_sub = sub_data.sum(axis=2)
    chamber_total = chamber_dom + chamber_sub
    chamber_pi = np.zeros_like(chamber_dom, dtype=np.float32)
    mask_ch = chamber_total > 0
    chamber_pi[mask_ch] = (chamber_dom[mask_ch] - chamber_sub[mask_ch]) / chamber_total[mask_ch]
    beh_to_plot.append(("Chamber", None, chamber_pi))
    
    idle_idx = behav_dict.get("idle")
    if idle_idx is not None and idle_idx < n_behav:
        interact_dom = np.sum(np.delete(dom_data, idle_idx, axis=2), axis=2)
        interact_sub = np.sum(np.delete(sub_data, idle_idx, axis=2), axis=2)
    else:
        interact_dom = dom_data.sum(axis=2)
        interact_sub = sub_data.sum(axis=2)
    interact_total = interact_dom + interact_sub
    interact_pi = np.zeros_like(interact_dom, dtype=np.float32)
    mask_int = interact_total > 0
    interact_pi[mask_int] = (interact_dom[mask_int] - interact_sub[mask_int]) / interact_total[mask_int]
    beh_to_plot.append(("Interaction", None, interact_pi))
    
    for name in behavior_order:
        if name not in behav_dict.keys() or name == "other":
            continue
        idx = behav_dict[name]
        if idx < n_behav:
            beh_to_plot.append((name, idx, pi_array[:, :, idx]))
    
    if not beh_to_plot:
        print("No behaviors to plot for PI trends")
        return

    color = {
        "chamber": "#35C03C",
        "interaction": "#6A9E86",
        **color_map
    }

    if plot_individual and output_dir:
        ind_dir = os.path.join(output_dir, "individual_pi_trends")
        os.makedirs(ind_dir, exist_ok=True)
        for i in range(n_files):
            fig, axes = plt.subplots(len(beh_to_plot), 1, figsize=(10, 3*len(beh_to_plot)), sharex=True)
            if len(beh_to_plot) == 1:
                axes = [axes]
            for ax, (base, idx, pi_data) in zip(axes, beh_to_plot):
                ax.plot(time_axis, pi_data[i], color=color.get(base.lower(), DOM_COLOR), lw=1, label='PI')
                ax.set_title(f'{base.capitalize()} - PI Trace')
                ax.grid(alpha=0.3, linestyle='--')
                ax.axhline(0, color='gray', linestyle='--', lw=0.5)
                ax.set_ylim(-1.1, 1.1)
                ax.set_xlim(0, time_axis[-1])
            axes[-1].set_xlabel('Time (minutes)')
            step = max(1, n_bins // 10)
            axes[-1].set_xticks(time_axis[::step])
            axes[-1].set_xticklabels([str(int(t)) for t in time_axis[::step]], rotation=45, ha='right')
            plt.tight_layout()
            plt.savefig(os.path.join(ind_dir, f"pi_trace_file_{i}.png"), dpi=150, bbox_inches='tight')
            plt.close()
        return
    
    fig, axes = plt.subplots(len(beh_to_plot), 1, figsize=(10, 3.5*len(beh_to_plot)), sharex=True)
    if len(beh_to_plot) == 1:
        axes = [axes]
    
    for ax, (base, idx, pi_data) in zip(axes, beh_to_plot):
        for i in range(n_files):
            ax.plot(time_axis, pi_data[i], color='lightgray', lw=0.4, alpha=0.25, zorder=1)
        
        pi_mean = pi_data.mean(axis=0)
        pi_sem = stats.sem(pi_data, axis=0)
        
        ax.plot(time_axis, pi_mean, color=color.get(base.lower(), DOM_COLOR), lw=1.8, marker='o', ms=4, 
                label='Mean PI', zorder=3, markerfacecolor='white', markeredgewidth=0.8)
        ax.fill_between(time_axis, pi_mean - pi_sem, pi_mean + pi_sem, 
                       color=color.get(base.lower(), DOM_COLOR), alpha=0.25, label='± SEM', zorder=2)
        
        p_vals = np.zeros(n_bins)
        for t in range(n_bins):
            valid_vals = pi_data[:, t][~np.isnan(pi_data[:, t])]
            if len(valid_vals) >= 2 and np.std(valid_vals) > 0:
                _, p_vals[t] = stats.ttest_1samp(valid_vals, 0)
            else:
                p_vals[t] = 1.0
        
        sig = multipletests(p_vals, alpha=0.05, method='fdr_bh')[0]
        for t in np.where(sig)[0]:
            y_val = pi_mean[t]
            y_offset = max(pi_sem[t] * 0.6 + 0.04, 0.06)
            marker_y = y_val + y_offset if y_val >= 0 else y_val - y_offset
            marker_y = np.clip(marker_y, -1.05, 1.05)  # Keep within bounds
            ax.text(time_axis[t], marker_y, '★', color='red', ha='center', 
                   va='center', fontsize=10, fontweight='bold', zorder=4)
        
        ax.axhline(0, color='black', linestyle='--', lw=0.9, alpha=0.6, zorder=0)
        ax.set_ylabel(f'{base.capitalize()}\nPreference Index', fontsize=9)
        ax.grid(axis='y', alpha=0.25, linestyle='--', lw=0.4)
        ax.set_ylim(-1.1, 1.1)
        ax.set_xlim(0, time_axis[-1])
        ax.tick_params(axis='y', labelsize=8)
        
        if ax == axes[0]:
            ax.legend(fontsize=8, frameon=True, fancybox=True, framealpha=0.9, loc='upper right')
    
    axes[-1].set_xlabel('Time (minutes)', fontsize=10)
    step = max(1, n_bins // 12)
    axes[-1].set_xticks(time_axis[::step])
    axes[-1].set_xticklabels([str(int(t)) for t in time_axis[::step]], rotation=45, ha='right', fontsize=8)
    
    fig.suptitle('Preference Index (PI) Trend Over Time: Mean ± SEM\nPI = (Dominant − Subordinate) / (Dominant + Subordinate)', 
                fontsize=12, fontweight='bold', y=1.02)
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    output_path = os.path.join(output_dir, "plot_5_pi_trend.png") if output_dir else "plot_5_pi_trend.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


def main():
    h5_dir = r"D:\\Data\Videos\ASOiD Predict"
    min_start = 0
    min_end = 720
    filter_thresh = 100
    filter_date = [1]
    filter_se = "SE"
    bin_size_min = 30
    plot_individual = False
    behaviors_to_exclude = ["ejaculation"]

    behavior_order = None
    out_dir = h5_dir
    
    print("Loading & aggregating data...")
    data = aggregate_all_files(h5_dir, min_start, min_end, filter_thresh, filter_date, filter_se, behaviors_to_exclude, bin_size_min)
    if behavior_order is None:
        behavior_order = sorted(set(data["base_names"]))

    print("Generating Plot 1...")
    plot_raw_duration_grouped(data, behavior_order, os.path.join(out_dir, "plot_1_raw_duration.png"))

    print("Generating Plot 2...")
    plot_preference_index(data, behavior_order, os.path.join(out_dir, "plot_2_preference_index.png"))
    
    print("Generating Trend Plots...")
    plot_trends(data, behavior_order, cumulative=False, plot_individual=plot_individual, output_dir=out_dir)
    plot_trends(data, behavior_order, cumulative=True, plot_individual=plot_individual, output_dir=out_dir)

    print("Generating PI Trends...")
    plot_pi_trends(data, behavior_order, plot_individual=plot_individual, output_dir=out_dir)

    print("All plots saved successfully.")

if __name__ == "__main__":
    main()