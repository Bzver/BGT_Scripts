import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from scipy.ndimage import median_filter
from hmmlearn import hmm
from typing import List, Tuple, Dict, Literal
import warnings
warnings.filterwarnings("ignore")


def load_annot_pose_pair(asoid_dir, pose_dir, max_files=100):
    file_pairs = []
    for f in os.listdir(asoid_dir):
        if not f.endswith(".csv") or "_annotated_iteration-" not in f:
            continue
        pf = f"{f.split('_annotated_iteration')[0]}.csv"
        pf_path = os.path.join(pose_dir, pf)
        if not os.path.isfile(pf_path):
            continue
        file_pairs.append((os.path.join(asoid_dir, f), pf_path))

        if len(file_pairs) >= max_files:
            break

    return file_pairs

def indices_to_spans(indices: np.ndarray) -> List[Tuple[int, int]]:
    if len(indices) == 0:
        return []
    if isinstance(indices, list):
        indices = np.asarray(indices, dtype=np.int32)
    indices = np.sort(indices)
    n = indices.size
    if n == 1:
        i0 = int(indices[0])
        return [(i0, i0)]
    split_at = np.where(np.diff(indices) > 1)[0] + 1
    if split_at.size == 0:
        return [(int(indices[0]), int(indices[-1]))]
    chunks = np.split(indices, split_at)
    return [(int(chunk[0]), int(chunk[-1])) for chunk in chunks]

def extract_behavior_mask(asoid_file, selected_behavior):
    # ASOID DFs are always 1 frame shorter than actual pose
    df = pd.read_csv(asoid_file, sep=",")
    return np.hstack(([False], np.array(df[selected_behavior] == 1)))

def get_individual_columns(df, individual_name):
    individuals = df.columns.get_level_values(0).unique()
    for ind in individuals:
        if individual_name.lower() in str(ind).lower():
            return ind
    raise ValueError(f"Individual {individual_name} not found")

def calculate_valid_body_mask(df, individuals=['1', '2'], min_angle_deg=90.0):
    n_frames = len(df)
    valid_mask = np.ones(n_frames, dtype=bool)
    min_angle_rad = np.radians(min_angle_deg)
    
    for ind_name in individuals:
        try:
            ind_label = get_individual_columns(df, ind_name)
            
            snout_x = df[(ind_label, 'Snout', 'x')]
            snout_y = df[(ind_label, 'Snout', 'y')]
            center_x = df[(ind_label, 'Center', 'x')]
            center_y = df[(ind_label, 'Center', 'y')]
            tail_x = df[(ind_label, 'Tail(base)', 'x')]
            tail_y = df[(ind_label, 'Tail(base)', 'y')]
            
            vec_cs_x = snout_x - center_x
            vec_cs_y = snout_y - center_y
            vec_ct_x = tail_x - center_x
            vec_ct_y = tail_y - center_y
            
            dot_prod = vec_cs_x * vec_ct_x + vec_cs_y * vec_ct_y
            mag_cs = np.sqrt(vec_cs_x**2 + vec_cs_y**2)
            mag_ct = np.sqrt(vec_ct_x**2 + vec_ct_y**2)
            
            denom = mag_cs * mag_ct
            denom = denom.replace(0, np.nan)
            
            cos_angle = dot_prod / denom
            cos_angle = cos_angle.clip(-1.0, 1.0)
            angles = np.arccos(cos_angle)

            is_invalid = angles < min_angle_rad
            is_invalid |= (denom < 1e-3)

            valid_mask &= ~is_invalid.values

        except Exception as e:
            print(f"Warning: Could not calculate body mask for {ind_name}: {e}")
            
    return valid_mask

def extract_features(pose_file, mask):
    df = pd.read_csv(pose_file, header=[0, 1, 2])
    n_frames = len(df)

    if len(mask) != n_frames:
        if len(mask) == n_frames + 1:
            mask = mask[1:]
        elif len(mask) > n_frames:
            mask = mask[:n_frames]
        else:
            raise ValueError(f"Mask length mismatch")

    bio_valid_mask = calculate_valid_body_mask(df, individuals=['1', '2'], min_angle_deg=90.0)
    final_mask = mask & bio_valid_mask
    
    print(f"Behavior Frames: {np.sum(mask)} | Valid Bio Frames: {np.sum(final_mask)} | Filtered Outliers: {np.sum(mask) - np.sum(final_mask)}")

    def get_centroid_series(df_full, individual_name):
        matched_individual = get_individual_columns(df_full, individual_name)
        x_cols = [col for col in df_full.columns if col[0] == matched_individual and col[2] == 'x']
        y_cols = [col for col in df_full.columns if col[0] == matched_individual and col[2] == 'y']
        cx = df_full[x_cols].mean(axis=1)
        cy = df_full[y_cols].mean(axis=1)
        return cx, cy

    fem_cx, fem_cy = get_centroid_series(df, '2')
    male_cx, male_cy = get_centroid_series(df, '1')

    fem_vx = fem_cx.diff().fillna(0)
    fem_vy = fem_cy.diff().fillna(0)
    male_vx = male_cx.diff().fillna(0)
    male_vy = male_cy.diff().fillna(0)

    rel_vx = male_vx - fem_vx
    rel_vy = male_vy - fem_vy
    rel_ax = rel_vx.diff().fillna(0)
    rel_ay = rel_vy.diff().fillna(0)

    basic_feats = np.column_stack([rel_vx.values, rel_vy.values, rel_ax.values, rel_ay.values])
    base_feature_names = ['rel_vx', 'rel_vy', 'rel_ax', 'rel_ay']

    WINDOW_SIZE = 5
    n_frames, _ = basic_feats.shape
    padded = np.pad(basic_feats, ((WINDOW_SIZE-1, 0), (0, 0)), mode='edge')

    window_feats_list = []
    for i in range(n_frames):
        window = padded[i:i+WINDOW_SIZE]
        w_mean = window.mean(axis=0)
        w_std = window.std(axis=0)
        w_trend = window[-1] - window[0]
        combined = np.concatenate([basic_feats[i], w_mean, w_std, w_trend])
        window_feats_list.append(combined)

    final_features = np.array(window_feats_list)
    
    temporal_feature_names = []
    for name in base_feature_names:
        temporal_feature_names.extend([f"{name}_raw", f"{name}_win_mean", f"{name}_win_std", f"{name}_win_trend"])

    masked_features = final_features[final_mask]
    df_masked_visual = df[final_mask].reset_index(drop=True)

    return masked_features, df_masked_visual, temporal_feature_names, final_mask

def visualize_clustering_2d(features, labels, feature_names, x_feat=0, y_feat=1, save_path="clustering_plot.png"):
    X_raw = features
    y_labels = labels
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    
    hb = ax.hexbin(X_raw[:, x_feat], X_raw[:, y_feat], C=y_labels, gridsize=50, cmap='viridis', mincnt=1)
    cb = fig.colorbar(hb, ax=ax)
    cb.set_label('Cluster Label')

    ax.set_title(f'Clustering: {feature_names[x_feat]} vs {feature_names[y_feat]}', fontsize=14)
    ax.set_xlabel(f'{feature_names[x_feat]}', fontsize=12)
    ax.set_ylabel(f'{feature_names[y_feat]}', fontsize=12)
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.set_aspect('equal', adjustable='box')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"Plot saved to {save_path}")

def visualize_cluster_distributions(
    features, 
    labels, 
    feature_names, 
    save_path="cluster_distributions.png", 
    top_n_features=8, 
    outlier_percentile: float = 99.0
):
    unique_labels = np.unique(labels)
    n_clusters = len(unique_labels)
    
    if n_clusters < 2:
        print("Need at least 2 clusters to plot distributions.")
        return

    discriminative_scores = []
    global_std = features.std(axis=0)
    global_std[global_std == 0] = 1
    
    for i in range(features.shape[1]):
        feat_col = features[:, i]
        means = [feat_col[labels == lbl].mean() for lbl in unique_labels]
        max_diff = np.max(means) - np.min(means)
        score = max_diff / global_std[i]
        discriminative_scores.append(score)
        
    top_feat_indices = np.argsort(discriminative_scores)[::-1][:top_n_features]
    n_rows = (top_n_features + 1) // 2
    fig, axes = plt.subplots(n_rows, 2, figsize=(14, 4 * n_rows))
    axes = axes.flatten()
    colors = plt.cm.Set1(np.linspace(0, 1, n_clusters))
    
    for idx, feat_idx in enumerate(top_feat_indices):
        ax = axes[idx]
        feat_name = feature_names[feat_idx]

        feat_all = features[:, feat_idx]
        lower_bound = np.percentile(feat_all, (100-outlier_percentile))
        upper_bound = np.percentile(feat_all, outlier_percentile)
        
        for lbl, color in zip(unique_labels, colors):
            mask = labels == lbl
            data = features[mask, feat_idx]

            plot_data = data[(data >= lower_bound) & (data <= upper_bound)]
            
            if len(plot_data) > 0:
                ax.hist(plot_data, bins=50, alpha=0.6, density=True,
                       label=f'Cluster {lbl} (n={np.sum(mask)}, plotted={len(plot_data)})', 
                       color=color)

                mean_val = plot_data.mean()
                ax.axvline(mean_val, color=color, linestyle='--', linewidth=1.5)
            
        ax.set_title(f'{feat_name}\n(Diff Score: {discriminative_scores[feat_idx]:.2f})', fontsize=10)
        ax.set_xlabel('Value')
        ax.set_ylabel('Density')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.5)

        ax.set_xlim(lower_bound, upper_bound)

    for j in range(idx + 1, len(axes)):
        axes[j].set_visible(False)

    plt.suptitle(
        f'Feature Distributions by Cluster (Top Discriminative Features)\n'
        f'Outliers >{outlier_percentile}th percentile removed for visualization', 
        fontsize=14, y=0.98
    )
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"Distribution plot saved to {save_path}")

def generate_prototype_animations(df, labels, probs, output_dir="./prototypes", fps=10, n_prototypes=5):
    if labels is None or df is None:
        return
    os.makedirs(output_dir, exist_ok=True)
    unique_clusters = np.unique(labels)
    unique_clusters = unique_clusters[unique_clusters != -1]
    print(f"Generating {n_prototypes} prototypes per cluster for: {unique_clusters}")

    individuals = df.columns.get_level_values(0).unique()
    SPINE_CHAIN = ['Snout', 'Center', 'Tail(base)']
    xy_cols = [col for col in df.columns if col[2] in ['x', 'y']]

    for cluster_id in unique_clusters:
        cluster_mask = (labels == cluster_id)
        cluster_indices = np.where(cluster_mask)[0]
        if len(cluster_indices) == 0:
            continue

        cluster_probs = probs[cluster_indices, cluster_id]
        sorted_local_indices = np.argsort(cluster_probs)[::-1]
        top_n_candidates = sorted_local_indices[:n_prototypes * 10]
        
        selected_global_indices = []
        min_frame_distance = int(fps * 3)

        for local_idx in top_n_candidates:
            global_idx = cluster_indices[local_idx]
            is_distinct = all(abs(global_idx - prev_idx) >= min_frame_distance for prev_idx in selected_global_indices)
            if is_distinct:
                selected_global_indices.append(global_idx)
            if len(selected_global_indices) >= n_prototypes:
                break
        
        if len(selected_global_indices) < n_prototypes:
            for local_idx in sorted_local_indices:
                global_idx = cluster_indices[local_idx]
                if global_idx not in selected_global_indices:
                    selected_global_indices.append(global_idx)
                    if len(selected_global_indices) >= n_prototypes:
                        break

        print(f"Cluster {cluster_id}: Selected {len(selected_global_indices)} prototypes")

        for proto_idx, center_idx in enumerate(selected_global_indices):
            prob_val = probs[center_idx, cluster_id]
            window_frames = int(fps * 1.5) 
            start_frame = max(0, center_idx - window_frames)
            end_frame = min(len(df), center_idx + window_frames)
            
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.set_title(f"Cluster {cluster_id} | Proto #{proto_idx+1} | Conf: {prob_val:.3f}")
            
            subset = df.iloc[start_frame:end_frame][xy_cols]
            all_vals = subset.values.flatten()
            all_vals = all_vals[~np.isnan(all_vals)]
            if len(all_vals) == 0: 
                plt.close(fig)
                continue

            margin = 50
            min_x, max_x = np.min(all_vals[::2]) - margin, np.max(all_vals[::2]) + margin
            min_y, max_y = np.min(all_vals[1::2]) - margin, np.max(all_vals[1::2]) + margin
            
            ax.set_xlim(min_x, max_x)
            ax.set_ylim(max_y, min_y)
            ax.set_aspect('equal')
            
            lines, texts = {}, {}
            for ind in individuals:
                valid_parts = [bp for bp in SPINE_CHAIN if (ind, bp, 'x') in df.columns and (ind, bp, 'y') in df.columns]
                if len(valid_parts) < 2:
                    continue
                xs_init = [df[(ind, bp, 'x')].iloc[start_frame] for bp in valid_parts]
                ys_init = [df[(ind, bp, 'y')].iloc[start_frame] for bp in valid_parts]
                line, = ax.plot(xs_init, ys_init, 'o-', label=str(ind), markersize=5, linewidth=2)
                lines[ind] = {'line': line, 'parts': valid_parts}
                cx, cy = np.nanmean(xs_init), np.nanmean(ys_init)
                texts[ind] = ax.text(cx, cy, str(ind), fontsize=10, bbox=dict(facecolor='white', alpha=0.7))

            def animate(frame_i):
                current_global_idx = start_frame + frame_i
                for ind, obj in lines.items():
                    valid_parts, line = obj['parts'], obj['line']
                    xs = [df[(ind, bp, 'x')].iloc[current_global_idx] for bp in valid_parts]
                    ys = [df[(ind, bp, 'y')].iloc[current_global_idx] for bp in valid_parts]
                    line.set_data(xs, ys)
                    cx, cy = np.nanmean(xs), np.nanmean(ys)
                    if not np.isnan(cx):
                        texts[ind].set_position((cx, cy))
                return list(obj['line'] for obj in lines.values()) + list(texts.values())

            ani = animation.FuncAnimation(fig, animate, frames=end_frame-start_frame, interval=1000/fps, blit=True)
            out_path = os.path.join(output_dir, f"cluster_{cluster_id}_proto_{proto_idx+1:02d}.gif")
            try:
                ani.save(out_path, writer='pillow', fps=fps)
            except Exception as e:
                print(f"Error saving {out_path}: {e}")
            finally:
                plt.close(fig)
        print(f"Saved {len(selected_global_indices)} prototypes for Cluster {cluster_id}")

def analyze_transitions(labels):
    unique_labels = np.unique(labels)
    n = len(labels)
    trans_counts = np.zeros((len(unique_labels), len(unique_labels)))
    for i in range(n - 1):
        if labels[i] in unique_labels and labels[i+1] in unique_labels:
            idx_i = np.where(unique_labels == labels[i])[0][0]
            idx_j = np.where(unique_labels == labels[i+1])[0][0]
            trans_counts[idx_i, idx_j] += 1
    
    row_sums = trans_counts.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    trans_probs = trans_counts / row_sums
    
    print("\n" + "="*50 + "\nTRANSITION ANALYSIS\n" + "="*50)
    for i, lbl_i in enumerate(unique_labels):
        for j, lbl_j in enumerate(unique_labels):
            print(f"  State {lbl_i} → State {lbl_j}: {trans_probs[i,j]:.3f} ({trans_counts[i,j]:.0f} transitions)")

def show_cluster_summary(labels, probs, feature_names=None, fps=30):
    unique_labels = np.unique(labels)
    print("\n" + "="*60)
    print("CLUSTER SUMMARY")
    print("="*60)
    
    for lbl in unique_labels:
        mask = labels == lbl
        n_frames = np.sum(mask)
        duration_sec = n_frames / fps
        mean_conf = probs[mask, lbl].mean()
        print(f"\nCluster {lbl}:")
        print(f"  Frames: {n_frames} ({duration_sec:.1f} seconds at {fps}fps)")
        print(f"  Mean Confidence: {mean_conf:.3f}")
        if feature_names:
            print(f"  Top discriminative features (by mean difference):")
    print("\n" + "="*60)

def interactive_cluster_selection(labels, probs, feature_names=None, fps=30):
    show_cluster_summary(labels, probs, feature_names, fps)
    
    unique_labels = np.unique(labels)
    unique_labels = unique_labels[unique_labels != -1]
    
    selections = {}
    
    print("\n" + "-"*60)
    print("INTERACTIVE SELECTION")
    print("-"*60)
    print("You can select one or more clusters to export as new behaviors.")
    print("Enter cluster IDs separated by commas (e.g., '0' or '0,1'), or 'done' to finish.\n")
    
    while True:
        user_input = input(f"\nSelect cluster(s) to export (available: {list(unique_labels)}), or 'done' or 'd': ").strip()
        
        if user_input.lower() in ('done', 'd', 'д'):
            break
            
        try:
            selected_clusters = [int(x.strip()) for x in user_input.split(',') if x.strip()]

            for cluster_id in selected_clusters:
                if cluster_id not in unique_labels:
                    print(f" Cluster {cluster_id} not found. Available: {list(unique_labels)}")
                    continue
                    
                behavior_name = input(f"  Enter behavior name for Cluster {cluster_id}: ").strip()
                if not behavior_name:
                    print(" Behavior name cannot be empty. Skipping.")
                    continue
                    
                selections[cluster_id] = behavior_name
                print(f" Cluster {cluster_id} → '{behavior_name}'")
                
        except ValueError:
            print(" Invalid input. Please enter cluster IDs as integers.")
    
    return selections

def convert_cluster_labels_to_annotation(
    clustered_labels: np.ndarray,
    original_mask_indices: np.ndarray,
    total_frames: int,
    target_cluster: int,
    src_segments: List[Tuple[int, int]],
    window_size: int = 5
) -> np.ndarray:

    annotation = np.zeros(total_frames, dtype=int)
    for idx, label in zip(original_mask_indices, clustered_labels):
        if label == target_cluster:
            annotation[idx] = 1

    for start, end in src_segments:
        seg_len = end - start + 1
        if seg_len < 3:
            continue 

        w = min(window_size, seg_len)
        seg_data = annotation[start:end+1].astype(float)
        smoothed = median_filter(seg_data, size=w, mode='nearest').astype(int)
        annotation[start:end+1] = smoothed

    return annotation

def check_behavior_exists(asoid_file: str, behavior_name: str) -> bool:
    try:
        df = pd.read_csv(asoid_file, sep=",")
        return behavior_name in df.columns
    except:
        return False

def save_annotated_csv_with_new_behavior(
    original_asoid_path: str,
    output_asoid_path: str,
    behavior_name: str,
    src_behavior_name: str,
    new_annotation: np.ndarray,
    on_exists: Literal['overwrite', 'skip', 'iteration']
) -> bool:

    df = pd.read_csv(original_asoid_path, sep=",")

    if behavior_name in df.columns:
        if on_exists == 'skip':
            print(f"Behavior '{behavior_name}' already exists. Skipping.")
            return False
        elif on_exists == 'iteration':
            iteration = 2
            while f"{behavior_name}_iteration-{iteration}" in df.columns:
                iteration += 1
            behavior_name = f"{behavior_name}_iteration-{iteration}"
    
    if len(new_annotation) != len(df):
        if len(new_annotation) == len(df) - 1:
            new_annotation = np.hstack(([0], new_annotation))
        else:
            print(f"Annotation length ({len(new_annotation)}) doesn't match DF length ({len(df)})")
            return False
    
    df[behavior_name] = new_annotation

    if behavior_name != src_behavior_name:
        df[src_behavior_name][new_annotation == 1] = 0
    
    os.makedirs(os.path.dirname(output_asoid_path), exist_ok=True)
    df.to_csv(output_asoid_path, sep=",", index=False)
    print(f"Saved: {output_asoid_path}")
    return True

def export_clusters_to_asoid(
    pairs: List[Tuple[str, str]],
    clustered_labels: np.ndarray,
    original_mask_indices: List[np.ndarray],
    src_behavior: str,
    selections: Dict[int, str],
    output_subdir: str = "cluster_exports",
    on_exists: str = 'ask', 
    fps: int = 10
):

    if not selections:
        print("No clusters selected for export.")
        return
    
    print(f"\n{'='*60} \nEXPORTING CLUSTERS TO ASOID FORMAT \n{'='*60}")
    print(f"Selections: {selections}")
    print(f"Output directory: {output_subdir}")
    print(f"On existing behavior: {on_exists}")

    start_idx = 0
    for i, (asoid_file, pose_file) in enumerate(pairs):
        df_asoid = pd.read_csv(asoid_file, sep=",")
        src_mask = (df_asoid[src_behavior].values == 1)
        src_segments = indices_to_spans(np.where(src_mask)[0])

        used_indices = original_mask_indices[i] - 1
        used_length = len(used_indices)
        end_idx = start_idx + used_length

        file_labels = clustered_labels[start_idx:end_idx]

        df_pose = pd.read_csv(pose_file, header=[0, 1, 2])
        total_frames = len(df_pose) - 1
    
        print(f"\nProcessing: {os.path.basename(asoid_file)}")
        for cluster_id, behavior_name in selections.items():
            annotation = convert_cluster_labels_to_annotation(
                file_labels, 
                used_indices, 
                total_frames,
                cluster_id,
                src_segments
            )

            n_positive = np.sum(annotation)
            if n_positive < 10:
                print(f"'{behavior_name}': Only {n_positive} frames. Too sparse (likely noise), dropping.")
                continue
            
            output_dir = os.path.join(os.path.dirname(asoid_file), output_subdir)
            output_path = os.path.join(output_dir, os.path.basename(asoid_file))
            
            success = save_annotated_csv_with_new_behavior(
                asoid_file, 
                output_path, 
                behavior_name,
                src_behavior,
                annotation, 
                on_exists=on_exists
            )
            
            if success:
                n_positive = np.sum(annotation)
                print(f"  → '{behavior_name}': {n_positive} frames ({n_positive/fps:.1f}s)")

        start_idx = end_idx


if __name__ == "__main__":
    asoid_dir = r"D:\Project\ASOID-Models\May-01-2026\videos"
    pose_dir = r"D:\Data\Videos\ASOiD Predict"
    fps = 10
    n_clusters = 2
    behavior = "m2f_anogenital"

    pairs = load_annot_pose_pair(asoid_dir, pose_dir, max_files=999)
    if not pairs:
        print("No files found.")
    else:
        print(f"Loaded {len(pairs)} file pairs.")

        features_all = []
        df_vis_list = []
        feature_names = None
        all_mask_indices = []
        
        for asoid_file, pose_file in pairs:
            mask = extract_behavior_mask(asoid_file, behavior)
            
            try:
                feats, df_raw_vis, fnames, final_mask = extract_features(pose_file, mask)
                
                if feats.shape[0] > 0:
                    valid_indices = np.where(final_mask)[0]
                    all_mask_indices.append(valid_indices)
                    
                    features_all.append(feats)
                    df_vis_list.append(df_raw_vis)
                    if feature_names is None:
                        feature_names = fnames
            except Exception as e:
                print(f"Error processing {pose_file}: {e}")
            
        if not features_all:
            print("No valid features extracted.")
        else:
            features_all = np.vstack(features_all)
            df_vis = pd.concat(df_vis_list, ignore_index=True)
            
            features_all = np.nan_to_num(features_all, nan=0.0, posinf=0.0, neginf=0.0)
            
            print(f"Total Valid Behavior Frames: {features_all.shape[0]}")
            print(f"Feature Dimension: {features_all.shape[1]}")

            print(f"\n{'='*50} \nRunning HMM Clustering (n_components={n_clusters}) \n{'='*50}")

            mean_vec = features_all.mean(axis=0)
            std_vec = features_all.std(axis=0)
            std_vec[std_vec == 0] = 1
            features_norm = (features_all - mean_vec) / std_vec
            features_norm = features_norm.astype(np.float64)

            model = hmm.GaussianHMM(
                n_components=n_clusters,
                covariance_type='diag',
                n_iter=300,
                random_state=42,
                init_params='mc',
                verbose=False
            )
            model.reg_covar = 1e-4 
            model.fit(features_norm)
            labels = model.predict(features_norm)
            probs = model.predict_proba(features_norm)

            analyze_transitions(labels)

            visualize_clustering_2d(
                features_all, labels, 
                feature_names,
                x_feat=0, y_feat=1, 
                save_path=f"clustering_{n_clusters}_hmm_pca.png"
            )

            visualize_cluster_distributions(
                features_all, 
                labels, 
                feature_names,
                save_path="cluster_feature_dists.png",
                top_n_features=8
            )

            generate_prototype_animations(
                df_vis, 
                labels, 
                probs, 
                n_prototypes=5
            )

            selections = interactive_cluster_selection(
                labels, 
                probs, 
                feature_names, 
                fps=fps
            )
            
            if selections:
                on_exists = 'overwrite'
                output_subdir = input("Enter output subfolder name (default: 'cluster_exports'): ").strip()
                if not output_subdir:
                    output_subdir = "cluster_exports"
                
                export_clusters_to_asoid(
                    pairs=pairs,
                    clustered_labels=labels,
                    original_mask_indices=all_mask_indices,
                    src_behavior=behavior,
                    selections=selections,
                    output_subdir=output_subdir,
                    on_exists=on_exists,
                    fps=fps
                )
                
                print("Export complete! Check your ASOID directory for the new subfolder.")
            else:
                print("No clusters selected. Exiting without export.")