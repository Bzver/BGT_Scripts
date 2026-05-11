import os
import json
import glob
import h5py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from hmmlearn.hmm import CategoricalHMM
from scipy import stats
from statsmodels.stats.multitest import multipletests
from joblib import Parallel, delayed
from typing import Dict

from asoid_bout_cleaner import refine_bouts_parallel


def load_dual_role_full_10hz(h5_dir, min_start=None, min_end=None):

    h5_files = sorted(glob.glob(os.path.join(h5_dir, "*.h5")))
    if not h5_files: raise ValueError("No .h5 files found.")
    
    with h5py.File(h5_files[0], 'r') as f:
        ref_map = json.loads(f['/meta/behavior_map'][()])
        fps = f['/meta'].attrs.get('fps', 10.0)
        
    # Build role vocabulary
    base_behaviors = sorted(set(name[4:] for name in ref_map if name.startswith(('dom_', 'sub_'))))

    vocab = base_behaviors
    if 'other' in ref_map: 
        vocab.append('transit')
        vocab.append('avoidance')
        vocab.append('ptvcham')
    vocab = sorted(list(set(vocab)))
    vocab_map = {v: i for i, v in enumerate(vocab)}
    idx_to_name = {i: n for n, i in vocab_map.items()}
    
    # Precompute remap arrays
    dom_remap = np.full(len(ref_map), -1, dtype=int)
    sub_remap = np.full(len(ref_map), -1, dtype=int)
    for orig_idx, name in enumerate(ref_map):
        if name.startswith('dom_'):
            dom_remap[orig_idx] = vocab_map.get(f"{name[4:]}", -1)
            sub_remap[orig_idx] = vocab_map.get('ptvcham', -1)
        elif name.startswith('sub_'):
            dom_remap[orig_idx] = vocab_map.get('ptvcham', -1)
            sub_remap[orig_idx] = vocab_map.get(f"{name[4:]}", -1)
        elif name == 'other':
            dom_remap[orig_idx] = vocab_map.get('transit', -1)
            sub_remap[orig_idx] = vocab_map.get('transit', -1)
            
    dom_seqs, sub_seqs, file_ids = [], [], []
    
    for f in h5_files:
        with h5py.File(f, 'r') as hf:
            arr = hf['/data/behaviors'][:].flatten()
            fid = hf['/meta'].attrs.get('session_id', os.path.basename(f))
            
        total = len(arr)
        s = int((min_start or 0) * 60 * fps)
        e = int((min_end or total / 60 / fps) * 60 * fps)
        arr = arr[max(0,s):min(total,e)]

        dom_arr = dom_remap[arr].astype(int)
        sub_arr = sub_remap[arr].astype(int)

        other_id = vocab_map['transit']
        dom_arr = split_other_by_duration(
            dom_arr, other_id, 
            min_long_frames=3000,  # 5 min @ 10Hz
            long_label_name="avoidance",
            vocab_map=vocab_map,
            idx_to_name=idx_to_name
        )
        sub_arr = split_other_by_duration(
            sub_arr, other_id,
            min_long_frames=3000,
            long_label_name="avoidance",
            vocab_map=vocab_map,
            idx_to_name=idx_to_name
        )

        dom_seqs.append(dom_arr)
        sub_seqs.append(sub_arr)
        file_ids.append(fid)

        if len(file_ids) >= 99:
            break 
        
    return dom_seqs, sub_seqs, file_ids, idx_to_name, vocab_map, fps 

def split_other_by_duration(
    seq: np.ndarray, 
    other_id: int, 
    min_long_frames: int = 3000,  # 5 min @ 10Hz
    long_label_name: str = "avoidance",
    vocab_map: Dict[str, int] = None,
    idx_to_name: Dict[int, str] = None
) -> np.ndarray:

    is_other = (seq == other_id)
    if not np.any(is_other):
        return seq, vocab_map, idx_to_name
        
    new_seq = seq.copy()
    
    diff = np.diff(is_other.astype(int))
    starts = np.concatenate(([0] if is_other[0] else [], np.where(diff == 1)[0] + 1))
    ends = np.concatenate((np.where(diff == -1)[0] + 1, [len(new_seq)] if is_other[-1] else []))
    
    new_label_id = vocab_map[long_label_name]
    
    for start, end in zip(starts, ends):
        start = int(start)
        end = int(end)
        duration = end - start
        if duration >= min_long_frames:
            new_seq[start:end] = new_label_id
    
    return new_seq

# =============================================================================
# 2. MEDIAN FILTER + BOUT EXTRACTION
# =============================================================================

def process_tracks_to_bouts(
    dom_seqs, sub_seqs, file_ids, 
    neutral_ids,
    eps_frames=25,
    min_cluster_size=3,
    n_jobs=-1
):
    
    all_bout_seqs, all_bout_meta = [], []
    
    def process_track(seqs, track_label):
        for seq, fid in zip(seqs, file_ids):
            refined = refine_bouts_parallel(seq, neutral_ids, eps_frames, min_cluster_size, n_jobs)
            
            ids, lengths, starts = extract_sustained_bouts_simple(refined, min_bout_frames=10)
            if len(ids) < 2: continue
            
            all_bout_seqs.append(np.array(ids, dtype=int))
            all_bout_meta.append({
                'session_id': fid, 'track': track_label,
                'bout_ids': ids, 'bout_lengths': lengths, 'bout_starts': starts
            })
            
    process_track(dom_seqs, 'dom')
    process_track(sub_seqs, 'sub')
    return all_bout_seqs, pd.DataFrame(all_bout_meta)

def extract_sustained_bouts_simple(labels, min_bout_frames=5):
    if len(labels) == 0:
        return [], [], []
    diff = np.diff(labels)
    starts = np.concatenate(([0], np.where(diff != 0)[0] + 1))
    ends = np.concatenate((starts[1:], [len(labels)]))
    
    ids = labels[starts].tolist()
    lengths = (ends - starts).tolist()
    
    keep = [l >= min_bout_frames for l in lengths]
    ids = [i for i, k in zip(ids, keep) if k]
    lengths = [l for l, k in zip(lengths, keep) if k]
    
    if not ids:
        return [], [], []
    
    # Merge adjacent identical
    merged_ids, merged_lengths = [ids[0]], [lengths[0]]
    for i in range(1, len(ids)):
        if ids[i] == merged_ids[-1]:
            merged_lengths[-1] += lengths[i]
        else:
            merged_ids.append(ids[i])
            merged_lengths.append(lengths[i])
    
    starts = []
    curr = 0
    for l in merged_lengths:
        starts.append(curr)
        curr += l
        
    return merged_ids, merged_lengths, starts

# =============================================================================
# 3. CATEGORICAL HMM TRAINING
# =============================================================================
def train_bout_cat_hmm(sequences, state_range=range(4, 9), max_iter=300, tol=1e-2, random_state=42):
    valid_seqs = [np.array(s, dtype=np.int32) for s in sequences if len(s) > 1]
    valid_seqs = [s for s in valid_seqs if len(np.unique(s)) > 1]
    
    if not valid_seqs: 
        raise ValueError("No valid bout sequences. Median filtering may have removed all transitions.")
        
    X_concat = np.concatenate(valid_seqs).reshape(-1, 1)  # Shape: (total_bouts, 1)
    lengths = [len(s) for s in valid_seqs]
    n_features = int(X_concat.max()) + 1
    
    print(f"   Inferred n_features (vocab size): {n_features}")
    print(f"   Total bouts: {len(X_concat)}, Sequences: {len(lengths)}")
    
    def train_and_score(n):
        try:
            model = CategoricalHMM(
                n_components=n,
                n_features=n_features,
                n_iter=max_iter,
                tol=tol,
                init_params='ste',
                params='ste',
                random_state=random_state,
                verbose=False
            )
            # Pass concatenated array + lengths
            model.fit(X_concat, lengths=lengths)
            bic = model.bic(X_concat, lengths=lengths)
            return n, bic, model
        except Exception as e:
            print(f"\nFailed for n_states={n}: {type(e).__name__}: {e}")
            return n, np.inf, None
            
    print(f"BIC sweep over n_states = {list(state_range)}...")
    results = Parallel(n_jobs=-1, verbose=10)(
        delayed(train_and_score)(n) for n in state_range
    )
    valid_results = [r for r in results if r[2] is not None]
    if not valid_results: 
        raise RuntimeError("All HMM training failed.")
        
    best_n, best_bic, best_model = min(valid_results, key=lambda x: x[1])
    print(f"Optimal n_states = {best_n} (BIC = {best_bic:.1f})")
    return best_model

def interpret_bout_motifs(model, idx_to_name, top_n=3):
    """Print motif emission profiles."""
    print(f"\nBout-Based Motif Profiles:")
    print("   " + "─" * 80)
    labels = {}
    for s in range(model.n_components):
        probs = model.emissionprob_[s]
        top_idx = np.argsort(probs)[::-1][:top_n]
        top_names = [idx_to_name[i] for i in top_idx]
        top_probs = probs[top_idx]
        summary = " + ".join([f"{n}({p:.0%})" for n, p in zip(top_names, top_probs)])
        labels[s] = f"M{s}_{top_names[0].replace('_',' ')}"
        print(f"   M{s:2d}: {summary}")
    print("   " + "─" * 80)
    return labels

# =============================================================================
# 4. DECODE & EXPAND TO FRAME LEVEL
# =============================================================================
def decode_and_expand_frames(model, bout_meta, idx_to_name, out_dir, fps):
    """Predict motifs per bout, expand to original frames, save CSVs."""
    # 1. Predict motifs for each bout sequence
    predicted_motifs = []
    for _, row in bout_meta.iterrows():
        bout_seq = np.array(row['bout_ids'], dtype=int)
        # CategoricalHMM expects (n_samples, 1)
        states = model.predict(bout_seq.reshape(-1, 1))
        predicted_motifs.append(states)
        
    # Safely assign array column
    bout_meta = bout_meta.copy()
    bout_meta['motif_id'] = predicted_motifs
    
    # 2. Expand to frame-level & save per track
    frame_dfs = {'dom': [], 'sub': []}
    for track in ['dom', 'sub']:
        track_data = bout_meta[bout_meta['track'] == track]
        records = []
        for _, row in track_data.iterrows():
            fid = row['session_id']
            motif_ids = row['motif_id']
            lengths = row['bout_lengths']
            starts = row['bout_starts']
            
            for b_idx in range(len(motif_ids)):
                m_id = int(motif_ids[b_idx])
                m_label = f"M{m_id}_{idx_to_name.get(m_id, 'unknown')}"
                length = int(lengths[b_idx])
                start_f = int(starts[b_idx])
                
                for f in range(start_f, start_f + length):
                    records.append({
                        'session_id': fid, 'track': track,
                        'frame': f, 'time_sec': f / fps,
                        'bout_idx': b_idx, 'motif_id': m_id, 'motif_label': m_label
                    })
        df = pd.DataFrame(records)
        out_path = os.path.join(out_dir, f"decoded_{track}_frames.csv")
        df.to_csv(out_path, index=False)
        print(f"Saved {out_path} ({len(df)} frames)")
        frame_dfs[track] = df
        
    return frame_dfs

# =============================================================================
# 5. TRACK COMPARISON & STATS
# =============================================================================

def compare_tracks_frame_level(track_dfs, out_dir, alpha=0.05):
    """Compare motif proportions between tracks using paired Wilcoxon + FDR."""
    if 'dom' not in track_dfs or 'sub' not in track_dfs: return None
    
    stats_list = []
    for track, df in track_dfs.items():
        props = df.groupby(['session_id', 'motif_label']).size().unstack(fill_value=0)
        props = props.div(props.sum(axis=1), axis=0)
        props = props.reset_index().melt(id_vars='session_id', var_name='motif', value_name='prop')
        props['track'] = track
        stats_list.append(props)
        
    combined = pd.concat(stats_list, ignore_index=True)
    comparisons = {}
    
    for motif in combined['motif'].unique():
        m_data = combined[combined['motif'] == motif]
        paired = m_data.pivot(index='session_id', columns='track', values='prop')
        if 'dom' not in paired.columns or 'sub' not in paired.columns: continue
        paired = paired.dropna()
        if len(paired) < 5: continue
        
        stat, p = stats.wilcoxon(paired['dom'], paired['sub'], alternative='two-sided')
        comparisons[motif] = {'dom_med': paired['dom'].median(), 'sub_med': paired['sub'].median(), 'p': p}
        
    comp_df = pd.DataFrame(comparisons).T
    if len(comp_df) == 0: return comp_df
    
    comp_df['p_adj'] = multipletests(comp_df['p'], method='fdr_bh')[1]
    comp_df = comp_df.sort_values('p_adj')
    
    # Plot
    plt.figure(figsize=(10, 6))
    x = np.arange(len(comp_df)); w = 0.35
    plt.bar(x-w/2, comp_df['dom_med'], w, label='Dom Track (syz=dom)', alpha=0.8)
    plt.bar(x+w/2, comp_df['sub_med'], w, label='Sub Track (syz=sub)', alpha=0.8)
    plt.xlabel('Motif'); plt.ylabel('Proportion of Time')
    plt.title('Bout-Based Motif Usage: Dom vs Sub')
    plt.xticks(x, [m[:12]+'...' if len(m)>12 else m for m in comp_df.index], rotation=45, ha='right')
    plt.legend(); plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'bout_motif_comparison.png'), dpi=300)
    plt.close()
    
    return comp_df

# =============================================================================
# 6. MAIN PIPELINE
# =============================================================================

def run_bout_cat_hmm(h5_dir, out_dir, state_range=range(4,9)):
    os.makedirs(out_dir, exist_ok=True)
    
    print("Loading full 10Hz sessions with role remapping...")
    dom_s, sub_s, fids, idx_name, vocab_map, fps = load_dual_role_full_10hz(h5_dir)
    print(f"   {len(dom_s)} sessions | {len(idx_name)} role-behaviors | {fps}Hz")

    bout_seqs, bout_meta = process_tracks_to_bouts(dom_s, sub_s, fids, neutral_ids=[vocab_map['transit'], vocab_map['avoidance']])
    print(f"   {len(bout_seqs)} bout sequences prepared for HMM")
    
    print("Training Bout-based Categorical HMM...")
    model = train_bout_cat_hmm(bout_seqs, state_range=state_range)
    labels = interpret_bout_motifs(model, idx_name)
    
    print("Decoding motifs & expanding to frames...")
    track_dfs = decode_and_expand_frames(model, bout_meta, idx_name, out_dir, fps)
    
    print("Comparing tracks...")
    comp_df = compare_tracks_frame_level(track_dfs, out_dir)
    if comp_df is not None and len(comp_df) > 0:
        comp_df.to_csv(os.path.join(out_dir, "bout_motif_stats.csv"))
        print("\nTop Significant Differences:")
        print(comp_df.head())
        
    print(f"\nPipeline complete. Outputs in {out_dir}")
    return model, track_dfs, comp_df

def main():
    h5_dir = r"D:\Data\Videos\ASOiD Predict"
    n_states_min = 10
    n_states_max = 20
    
    out_dir = os.path.join(h5_dir, "output")
    os.makedirs(out_dir, exist_ok=True)

    state_range = list(range(n_states_min, n_states_max + 1))
    
    print(f"\nBout-Based Categorical HMM Pipeline")
    
    model, dfs, comp = run_bout_cat_hmm(h5_dir, out_dir, state_range)

if __name__ == "__main__":
    main()