import os
import json
import glob
import h5py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Tuple, Optional, Iterable
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from scipy import stats
from statsmodels.stats.multitest import multipletests

# =============================================================================
# 1. SEGMENTATION & LOADING
# =============================================================================

def array_to_iterable_runs(arr:np.ndarray) -> Iterable[Tuple[int, int, int]]:
    if len(arr) == 0:
        return zip([], [], [])
    change_points = np.where(arr[1:] != arr[:-1])[0] + 1 
    starts = np.concatenate(([0], change_points))
    ends = np.concatenate((change_points - 1, [len(arr) - 1]))
    values = arr[starts]
    return zip(starts, ends, values)

def split_by_neutral(seq: np.ndarray, neutral_ids: List[int], min_gap:int=10, max_length: int=3000) -> List[Tuple[int, int]]:
    """Split sequence into active segments bounded by neutral behaviors."""
    for start, end, val in array_to_iterable_runs(seq):
        if val not in neutral_ids:
            continue
        if end - start + 1 > min_gap:
            continue
        if start > 0:
            seq[start:end+1] = seq[start-1]

    is_neutral = np.isin(seq, neutral_ids)

    boundaries = np.where(np.diff(is_neutral.astype(int)) != 0)[0] + 1
    segments = []
    start = 0
    for b in boundaries:
        if is_neutral[start]:
            start = b
            continue
        len_seg = b - start
        if len_seg <= max_length:
            segments.append((start, b))
        else:
            n_chunks = len_seg // max_length + 1
            chunk_edges = np.linspace(start, b, n_chunks + 1, dtype=int)
            for j in range(len(chunk_edges) - 1):
                st = int(chunk_edges[j])
                ed = int(chunk_edges[j + 1])
                if st < ed:
                    segments.append((st, ed))
        start = b
    if start < len(seq) and not is_neutral[start]:
        len_seg = len(seq) - start
        if len_seg <= max_length:
            segments.append((start, len(seq)))
        else:
            n_chunks = len_seg // max_length + 1
            chunk_edges = np.linspace(start, len(seq), n_chunks + 1, dtype=int)
            for j in range(len(chunk_edges) - 1):
                st = int(chunk_edges[j])
                ed = int(chunk_edges[j + 1])
                if st < ed:
                    segments.append((st, ed))
    return segments


def load_dual_role_full_10hz(h5_dir: str, min_start: Optional[float] = None, 
                            min_end: Optional[float] = None) -> Tuple:
    """Load sessions and remap to role-agnostic vocabulary."""
    h5_files = sorted(glob.glob(os.path.join(h5_dir, "*.h5")))
    if not h5_files: raise ValueError("No .h5 files found.")
    
    with h5py.File(h5_files[0], 'r') as f:
        ref_map = json.loads(f['/meta/behavior_map'][()])
        fps = float(f['/meta'].attrs.get('fps', 10.0))
        
    # Build vocabulary: base behaviors + 'other'
    base_behaviors = sorted(set(name[4:] for name in ref_map if name.startswith(('dom_', 'sub_'))))
    vocab = sorted(list(set(base_behaviors + ['other'])))
    vocab_map = {v: i for i, v in enumerate(vocab)}
    idx_to_name = {i: n for n, i in vocab_map.items()}
    
    dom_seqs, sub_seqs, file_ids = [], [], []
    other_id = vocab_map['other']
    
    # Precompute remap arrays
    dom_remap = np.full(len(ref_map), -1, dtype=int)
    sub_remap = np.full(len(ref_map), -1, dtype=int)
    for orig_idx, name in enumerate(ref_map):
        if name.startswith('dom_'):
            dom_remap[orig_idx] = vocab_map.get(name[4:], -1)
            sub_remap[orig_idx] = other_id
        elif name.startswith('sub_'):
            dom_remap[orig_idx] = other_id
            sub_remap[orig_idx] = vocab_map.get(name[4:], -1)
        else:
            dom_remap[orig_idx] = other_id
            sub_remap[orig_idx] = other_id
            
    for f in h5_files:
        with h5py.File(f, 'r') as hf:
            arr = hf['/data/behaviors'][:].flatten()
            fid = os.path.basename(f)
            
        total = len(arr)
        s = int((min_start or 0) * 60 * fps)
        e = int((min_end or total / 60 / fps) * 60 * fps)
        arr = arr[max(0,s):min(total,e)]
        
        dom_seqs.append(dom_remap[arr].astype(int))
        sub_seqs.append(sub_remap[arr].astype(int))
        file_ids.append(fid)
        
        if len(file_ids) >= 99: break  # Limit for testing
        
    return dom_seqs, sub_seqs, file_ids, idx_to_name, vocab_map, fps, other_id

# =============================================================================
# 2. SEGMENT → VECTOR CONVERSION
# =============================================================================

def compute_segment_vectors(dom_seqs, sub_seqs, file_ids, neutral_ids, fps, vocab_size):
    """Convert active segments to proportion vectors + metadata."""
    vectors = []
    meta_rows = []
    
    for seq, fid, track in zip(dom_seqs + sub_seqs, file_ids*2, ['dom']*len(file_ids) + ['sub']*len(file_ids)):
        segments = split_by_neutral(seq, neutral_ids)
        for start, end in segments:
            seg = seq[start:end]
            if len(seg) < 20: continue
            
            # Compute proportions
            counts = np.bincount(seg, minlength=vocab_size)
            props = counts / len(seg)
            
            vectors.append(props)
            meta_rows.append({
                'session_id': fid,
                'track': track,
                'start_frame': start,
                'end_frame': end,
                'duration_sec': len(seg) / fps,
                'start_min': start / (60 * fps),
                'end_min': end / (60 * fps)
            })
            
    X = np.array(vectors)
    meta = pd.DataFrame(meta_rows)
    return X, meta
 
# =============================================================================
# 3. CLUSTERING
# =============================================================================

def optimize_and_cluster(X: np.ndarray, k_range: range = range(3, 10), 
                         silhouette_sample=15000, random_state=42):
    """
    Find optimal k using silhouette on a subsample, then fit KMeans on full data.
    Returns: final_labels, best_k, silhouette_scores_dict
    """
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # 1. Subsample for efficient silhouette optimization
    if len(X_scaled) > silhouette_sample:
        rng = np.random.RandomState(random_state)
        sub_idx = rng.choice(len(X_scaled), silhouette_sample, replace=False)
        X_sub = X_scaled[sub_idx]
    else:
        X_sub = X_scaled
        
    best_k, best_score = None, -1.0
    silhouette_scores = {}
    
    for k in k_range:
        km = KMeans(n_clusters=k, init='k-means++', n_init=10, max_iter=300, 
                    random_state=random_state)
        km.fit(X_sub)
        score = silhouette_score(X_sub, km.labels_)
        silhouette_scores[k] = score
        print(f"  k={k:2d} | Silhouette (n={silhouette_sample}) = {score:.4f}")
        if score > best_score:
            best_score, best_k = score, k
            
    print(f"✅ Optimal k = {best_k} (Silhouette = {best_score:.4f})")
    
    # 2. Fit final model on FULL dataset
    final_km = KMeans(n_clusters=best_k, init='k-means++', n_init=10, max_iter=300,
                      random_state=random_state)
    final_labels = final_km.fit_predict(X_scaled)
    
    return final_labels, best_k, silhouette_scores

# =============================================================================
# 4. STATISTICAL ANALYSIS WITH FILTERS
# =============================================================================

def analyze_cluster_preference(meta, cluster_labels, h5_dir, out_dir, vocab, 
                              min_start=None, min_end=None,
                              filter_dates=None, filter_se=None, X=None):
    """Compute track preference per cluster, respecting all filters."""
    
    # Load session metadata
    session_meta = {}
    for f in sorted(glob.glob(os.path.join(h5_dir, "*.h5"))):
        with h5py.File(f, 'r') as hf:
            attrs = dict(hf['/meta'].attrs)
            sid = os.path.basename(f)
            session_meta[sid] = {
                'day': int(attrs.get('day', 0)),
                'se': attrs.get('se_status', False)
            }
            
    # Attach metadata
    df = meta.copy()
    df['cluster'] = cluster_labels
    df['day'] = df['session_id'].map(lambda x: session_meta.get(x, {}).get('day'))
    df['se_status'] = df['session_id'].map(lambda x: session_meta.get(x, {}).get('se'))
    
    # Apply filters
    mask = pd.Series(True, index=df.index)
    if filter_dates is not None:
        mask &= df['day'].isin(filter_dates)
    if filter_se == "SE":
        mask &= df['se_status'] == True
    elif filter_se == "VG":
        mask &= df['se_status'] == False
    if min_start is not None:
        mask &= df['start_min'] >= min_start
    if min_end is not None:
        mask &= df['end_min'] <= min_end
        
    df = df[mask]
    n_before = meta['session_id'].nunique()
    n_after = df['session_id'].nunique()
    print(f"🔍 Filters applied: {n_after}/{n_before} sessions | {len(df):,}/{len(meta):,} segments retained")
    
    if len(df) == 0:
        print("⚠️ No segments passed filters.")
        return pd.DataFrame()
        
    # Compute session-level cluster proportions per track
    session_usage = df.groupby(['session_id', 'track', 'cluster'])['duration_sec'].sum().unstack(fill_value=0)
    session_total = session_usage.sum(axis=1)
    session_props = session_usage.div(session_total, axis=0)
    
    # Paired Wilcoxon test per cluster
    results = []
    for c in sorted(session_props.columns.unique()):
        dom_vals = session_props.xs('dom', level='track')[c].dropna()
        sub_vals = session_props.xs('sub', level='track')[c].dropna()
        
        # Align sessions
        common_idx = dom_vals.index.intersection(sub_vals.index)
        d, s = dom_vals.loc[common_idx], sub_vals.loc[common_idx]
        stat, p = stats.wilcoxon(d, s, alternative='two-sided')
        
        results.append({
            'cluster': f"C{c}",
            'n_sessions': len(common_idx),
            'dom_med': d.median(),
            'sub_med': s.median(),
            'PI': (d.median() - s.median()),
            'p': p
        })
        
    comp_df = pd.DataFrame(results)
    if len(comp_df) == 0: return comp_df
    
    comp_df['p_adj'] = multipletests(comp_df['p'], method='fdr_bh')[1]
    comp_df = comp_df.sort_values('p_adj')
    
    # Plot
    plt.figure(figsize=(8, 5))
    x = np.arange(len(comp_df)); w = 0.35
    plt.bar(x-w/2, comp_df['dom_med'], w, label='Dominant Track', alpha=0.8, color='#2ca02c')
    plt.bar(x+w/2, comp_df['sub_med'], w, label='Subordinate Track', alpha=0.8, color='#1f77b4')
    plt.xlabel('Cluster'); plt.ylabel('Proportion of Active Time')
    plt.title('Segment Cluster Preference (Filtered)')
    plt.xticks(x, comp_df['cluster'], rotation=0)
    plt.legend(); plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'cluster_preference.png'), dpi=300)
    plt.close()
    
    comp_df.to_csv(os.path.join(out_dir, 'cluster_preference_stats.csv'), index=False)
    print("\n📊 Filtered Cluster Preference Results:")
    print(comp_df.round(3).to_string(index=False))
    
    # Save cluster emission profiles for interpretation
    profiles = {}
    for c in sorted(range(cluster_labels.max() + 1)):
        mask_c = cluster_labels == c
        props = X[mask_c].mean(axis=0)
        top_idx = np.argsort(props)[::-1][:3]
        top_names = [vocab[i] for i in top_idx]
        top_props = props[top_idx]
        profiles[f"C{c}"] = dict(zip(top_names, top_props))
    pd.DataFrame(profiles).to_csv(os.path.join(out_dir, 'cluster_profiles.csv'))
    print("\n📋 Cluster Profiles (Top 3 Behaviors):")
    print(pd.DataFrame(profiles).round(3).to_string())
    
    return comp_df

# =============================================================================
# 5. CLUSTER PROTOTYPE VISUALIZATION
# =============================================================================

def plot_cluster_prototypes(cluster_labels: np.ndarray, X: np.ndarray, 
                           idx_to_name: dict, out_dir: str, figsize: Tuple[int, int] = (14, 50)):
    """Generate composition plots showing the representative behavior profile for each cluster prototype."""
    import seaborn as sns
    
    n_clusters = len(np.unique(cluster_labels))
    
    # Compute mean proportion vector for each cluster (the "prototype")
    prototypes = {}
    for c in range(n_clusters):
        mask = cluster_labels == c
        if mask.sum() > 0:
            prototypes[c] = X[mask].mean(axis=0)
        else:
            prototypes[c] = np.zeros(X.shape[1])
    
    # Convert to DataFrame for easier sorting/plotting
    proto_df = pd.DataFrame(prototypes).T
    proto_df.columns = [idx_to_name[i] for i in range(X.shape[1])]
    
    # Identify top behaviors across ALL clusters to keep plot consistent
    global_mean = X.mean(axis=0)
    top_behaviors_global = np.argsort(global_mean)[::-1]
    top_behaviors_global = [i for i in top_behaviors_global if idx_to_name[i] not in ["other", "ejaculation"]]
    top_behavior_names = [idx_to_name[i] for i in top_behaviors_global]
    
    # === PLOT 1: Horizontal bar chart for each cluster ===
    fig, axes = plt.subplots(n_clusters, 1, figsize=figsize, constrained_layout=True)
    if n_clusters == 1:
        axes = [axes]
    
    colors = plt.cm.Set2(np.linspace(0, 1, len(top_behavior_names)))
    
    for idx, c in enumerate(sorted(prototypes.keys())):
        ax = axes[idx]
        props = prototypes[c]
        
        # Extract values for top behaviors only
        values = [props[i] for i in top_behaviors_global]
        y_pos = np.arange(len(top_behavior_names))
        
        bars = ax.barh(y_pos, values, color=colors, edgecolor='black', alpha=0.85)
        
        # Add value labels on bars
        for i, (bar, val) in enumerate(zip(bars, values)):
            if val > 0.02:
                ax.text(val + 0.01, i, f'{val:.2f}', va='center', fontsize=9)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(top_behavior_names, fontsize=10)
        ax.set_xlabel('Proportion', fontsize=11)
        ax.set_title(f'Cluster {c} Prototype (n={(cluster_labels==c).sum()} segments)', 
                    fontsize=12, fontweight='bold')
        ax.set_xlim(0, max(1.0, max(values) * 1.3))
        ax.grid(axis='x', alpha=0.3, linestyle='--')
        ax.invert_yaxis()
    
    plt.suptitle('Cluster Segment Prototypes: Behavior Composition', 
                fontsize=16, fontweight='bold', y=1.02)
    plt.savefig(os.path.join(out_dir, 'cluster_prototypes_bars.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # === PLOT 2: Heatmap of all behaviors × clusters ===
    plt.figure(figsize=(max(12, n_clusters * 1.5), max(6, len(idx_to_name) * 0.3)))
    
    sorted_proto = proto_df.iloc[:, top_behaviors_global].T
    
    sns.heatmap(sorted_proto, cmap='YlOrRd', annot=False, fmt='.2f',
                cbar_kws={'label': 'Mean Proportion'}, linewidths=0.3)
    
    plt.xlabel('Cluster', fontsize=12)
    plt.ylabel('Behavior', fontsize=12)
    plt.title('Cluster Prototype Heatmap: Behavior Proportions', fontsize=14, fontweight='bold')
    plt.yticks(rotation=0, fontsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'cluster_prototypes_heatmap.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # === PLOT 3: Radar/Spider plot for top 3-5 clusters (optional) ===
    if n_clusters <= 8:
        _plot_radar_prototypes(prototypes, idx_to_name, top_behavior_names, out_dir, n_clusters)
    
    # Save prototype data to CSV for reference
    proto_df.to_csv(os.path.join(out_dir, 'cluster_prototypes.csv'))
    print(f"📊 Cluster prototype plots saved to {out_dir}")
    
    return proto_df

def _plot_radar_prototypes(prototypes: dict, idx_to_name: dict, 
                          top_behavior_names: List[str], 
                          out_dir: str, n_clusters: int):
    """Helper: Create radar chart comparing cluster prototypes."""
    import matplotlib.pyplot as plt
    import numpy as np
    
    n_behaviors = len(top_behavior_names)
    angles = np.linspace(0, 2 * np.pi, n_behaviors, endpoint=False).tolist()
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
    
    colors = plt.cm.tab10(np.linspace(0, 1, n_clusters))
    
    for c in range(n_clusters):
        props = prototypes[c]
        values = [props[idx_to_name.index(name)] if name in idx_to_name.values() else 0 
                 for name in top_behavior_names]
        values += values[:1]
        
        ax.plot(angles, values, 'o-', linewidth=2, label=f'Cluster {c}', 
               color=colors[c], markersize=4)
        ax.fill(angles, values, alpha=0.15, color=colors[c])
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(top_behavior_names, size=10)
    ax.set_ylim(0, 1.0)
    ax.set_title('Cluster Prototype Comparison (Top Behaviors)', 
                size=14, fontweight='bold', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=9)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'cluster_prototypes_radar.png'), dpi=300, bbox_inches='tight')
    plt.close()

# =============================================================================
# 6. CLUSTER SCATTER PLOT (2D PROJECTION)
# =============================================================================

def plot_cluster_scatter(X_scaled: np.ndarray, cluster_labels: np.ndarray, 
                        meta: pd.DataFrame, out_dir: str,
                        max_samples: int = 10000, 
                        method: str = 'pca',
                        random_state: int = 42,
                        figsize: Tuple[int, int] = (10, 8)):
    """Create a 2D scatter plot of segments colored by cluster assignment."""
    from sklearn.decomposition import PCA
    from sklearn.manifold import TSNE
    
    n_total = len(cluster_labels)
    if n_total > max_samples:
        rng = np.random.RandomState(random_state)
        sampled_idx = []
        unique_clusters, counts = np.unique(cluster_labels, return_counts=True)
        for c, count in zip(unique_clusters, counts):
            cluster_idx = np.where(cluster_labels == c)[0]
            n_sample = max(1, int(count / n_total * max_samples))
            sampled = rng.choice(cluster_idx, size=min(n_sample, len(cluster_idx)), replace=False)
            sampled_idx.extend(sampled)
        sampled_idx = np.array(sampled_idx)
        X_plot = X_scaled[sampled_idx]
        labels_plot = cluster_labels[sampled_idx]
        meta_plot = meta.iloc[sampled_idx].copy()
        print(f"📊 Subsampled {len(sampled_idx):,} segments (stratified by cluster) for visualization")
    else:
        X_plot = X_scaled
        labels_plot = cluster_labels
        meta_plot = meta.copy()
        print(f"📊 Using all {len(labels_plot):,} segments for visualization")
    
    print(f"🔄 Reducing dimensions with {method.upper()}...")
    if method == 'pca':
        reducer = PCA(n_components=2, random_state=random_state)
        X_2d = reducer.fit_transform(X_plot)
        variance_explained = reducer.explained_variance_ratio_.sum()
        axis_labels = [f'PC1 ({variance_explained*100:.1f}%)', f'PC2 ({variance_explained*100:.1f}%)']
    elif method == 'tsne':
        perplexity = min(30, len(X_plot) // 3)
        reducer = TSNE(n_components=2, perplexity=perplexity, init='pca', 
                      random_state=random_state, n_iter=1000, learning_rate='auto')
        X_2d = reducer.fit_transform(X_plot)
        axis_labels = ['t-SNE 1', 't-SNE 2']
    elif method == 'umap':
        try:
            import umap
            reducer = umap.UMAP(n_components=2, random_state=random_state, n_neighbors=15, min_dist=0.1)
            X_2d = reducer.fit_transform(X_plot)
            axis_labels = ['UMAP 1', 'UMAP 2']
        except ImportError:
            print("⚠️ UMAP not installed. Falling back to PCA.")
            reducer = PCA(n_components=2, random_state=random_state)
            X_2d = reducer.fit_transform(X_plot)
            axis_labels = ['PC1', 'PC2']
    else:
        raise ValueError(f"Unknown method: {method}. Use 'pca', 'tsne', or 'umap'.")
    
    fig, ax = plt.subplots(figsize=figsize)
    n_clusters = len(np.unique(labels_plot))
    
    scatter = ax.scatter(X_2d[:, 0], X_2d[:, 1], c=labels_plot, cmap=plt.cm.tab20, 
                        s=8, alpha=0.6, edgecolors='white', linewidth=0.3)
    
    ax.set_xlabel(axis_labels[0], fontsize=11)
    ax.set_ylabel(axis_labels[1], fontsize=11)
    ax.set_title(f'Cluster Visualization ({method.upper()})\n{n_clusters} clusters | {len(labels_plot):,} segments', 
                fontsize=13, fontweight='bold')
    
    unique, counts = np.unique(labels_plot, return_counts=True)
    legend_labels = [f'C{c} (n={cnt:,})' for c, cnt in zip(unique, counts)]
    if n_clusters <= 20:
        handles, _ = scatter.legend_elements()
        ax.legend(handles, legend_labels, loc='best', fontsize=8, ncol=2, framealpha=0.8)
        
    ax.grid(alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    plt.tight_layout()
    
    plot_path = os.path.join(out_dir, f'cluster_scatter_{method}.png')
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    plot_data = pd.DataFrame({
        'dim1': X_2d[:, 0], 'dim2': X_2d[:, 1], 'cluster': labels_plot,
        'session_id': meta_plot['session_id'].values, 'track': meta_plot['track'].values,
        'duration_sec': meta_plot['duration_sec'].values
    })
    plot_data.to_csv(os.path.join(out_dir, f'cluster_scatter_{method}_coordinates.csv'), index=False)
    print(f"📈 Cluster scatter plot saved: {plot_path}")
    return fig, X_2d, labels_plot

# =============================================================================
# 7. SILHOUETTE SCORE PLOT
# =============================================================================

def plot_silhouette_analysis(silhouette_scores: dict, best_k: int, out_dir: str):
    """Plot silhouette scores across tested k values to justify cluster selection."""
    ks = list(silhouette_scores.keys())
    scores = list(silhouette_scores.values())
    
    plt.figure(figsize=(10, 6))
    
    # Plot line
    plt.plot(ks, scores, 'o-', color='#2ca02c', linewidth=2, markersize=8, label='Silhouette Score')
    
    # Highlight best k
    best_score = silhouette_scores[best_k]
    plt.axvline(x=best_k, color='red', linestyle='--', alpha=0.7, label=f'Optimal k={best_k}')
    plt.scatter([best_k], [best_score], color='red', s=100, zorder=5, edgecolors='white', linewidth=2)
    
    # Annotations
    plt.xlabel('Number of Clusters (k)', fontsize=12)
    plt.ylabel('Silhouette Score', fontsize=12)
    plt.title('Cluster Optimization: Silhouette Score Analysis', fontsize=14, fontweight='bold')
    plt.xticks(ks)
    plt.grid(True, alpha=0.3, linestyle='--')
    plt.legend(loc='best', fontsize=11)
    
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'silhouette_analysis.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"📈 Silhouette analysis plot saved to {out_dir}")

# =============================================================================
# 8. MAIN PIPELINE
# =============================================================================

def main():
    h5_dir = r"D:\Data\Videos\ASOiD Predict"
    out_dir = os.path.join(h5_dir, "output_segment_clusters")
    os.makedirs(out_dir, exist_ok=True)
    
    print("📥 Loading sessions & remapping roles...")
    dom_s, sub_s, fids, idx_name, vocab_map, fps, other_id = load_dual_role_full_10hz(h5_dir)
    print(f"   ✅ {len(dom_s)} sessions | {len(vocab_map)} behaviors | {fps}Hz")
    
    neutral_ids = [other_id]
    vocab_size = len(vocab_map)
    
    print("⏱️ Computing segment proportion vectors...")
    X, meta = compute_segment_vectors(dom_s, sub_s, fids, neutral_ids, fps, vocab_size)
    print(f"   ✅ {len(X)} active segments extracted")
    
    print("🔍 Optimizing clusters (silhouette score)...")
    cluster_labels, best_k, silhouette_scores = optimize_and_cluster(X, k_range=range(4, 15))
    meta['cluster'] = cluster_labels

    print("📊 Plotting silhouette analysis...")
    plot_silhouette_analysis(silhouette_scores, best_k, out_dir)

    print("🎯 Creating cluster scatter plot (2D projection)...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    plot_cluster_scatter(
        X_scaled=X_scaled,
        cluster_labels=cluster_labels,
        meta=meta,
        out_dir=out_dir,
        max_samples=10000,
        method='umap'
    )
    
    print("🎨 Generating cluster prototype visualizations...")
    plot_cluster_prototypes(cluster_labels, X, idx_name, out_dir)

    print("📊 Analyzing filtered cluster preference...")
    comp_df = analyze_cluster_preference(
        meta, cluster_labels, h5_dir, out_dir, idx_name,
        min_start=0, min_end=481,
        filter_dates=[1],
        filter_se="SE",
        X=X
    )
    
    print(f"\n✅ Pipeline complete. Outputs in {out_dir}")

if __name__ == "__main__":
    main()