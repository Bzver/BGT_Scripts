import os
import json
import glob
import h5py
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Tuple, Optional, Iterable
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from ssm import HMM

# =============================================================================
# 1. SEGMENTATION & LOADING (UNCHANGED FROM YOUR PIPELINE)
# =============================================================================

def array_to_iterable_runs(arr: np.ndarray) -> Iterable[Tuple[int, int, int]]:
    if len(arr) == 0:
        return zip([], [], [])
    change_points = np.where(arr[1:] != arr[:-1])[0] + 1 
    starts = np.concatenate(([0], change_points))
    ends = np.concatenate((change_points - 1, [len(arr) - 1]))
    values = arr[starts]
    return zip(starts, ends, values)


def split_by_neutral(seq: np.ndarray, neutral_ids: List[int], 
                     min_gap: int = 10, max_length: int = 3000) -> List[Tuple[int, int]]:
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
                st, ed = int(chunk_edges[j]), int(chunk_edges[j + 1])
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
                st, ed = int(chunk_edges[j]), int(chunk_edges[j + 1])
                if st < ed:
                    segments.append((st, ed))
    return segments


def load_dual_role_full_10hz(h5_dir: str, min_start: Optional[float] = None, 
                            min_end: Optional[float] = None) -> Tuple:
    """Load sessions and remap to role-agnostic vocabulary."""
    h5_files = sorted(glob.glob(os.path.join(h5_dir, "*.h5")))
    if not h5_files: 
        raise ValueError("No .h5 files found.")
    
    with h5py.File(h5_files[0], 'r') as f:
        ref_map = json.loads(f['/meta/behavior_map'][()])
        fps = float(f['/meta'].attrs.get('fps', 10.0))
        
    base_behaviors = sorted(set(name[4:] for name in ref_map if name.startswith(('dom_', 'sub_'))))
    vocab = sorted(list(set(base_behaviors + ['other'])))
    vocab_map = {v: i for i, v in enumerate(vocab)}
    idx_to_name = {i: n for n, i in vocab_map.items()}
    
    dom_seqs, sub_seqs, file_ids = [], [], []
    other_id = vocab_map['other']
    
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
        if len(file_ids) >= 2:  # For testing
            break
    return dom_seqs, sub_seqs, file_ids, idx_to_name, vocab_map, fps, other_id

# =============================================================================
# 2. SEGMENT → VECTOR CONVERSION (UNCHANGED)
# =============================================================================

def compute_segment_vectors(dom_seqs, sub_seqs, file_ids, neutral_ids, fps, vocab_size):
    """Convert active segments to proportion vectors + metadata."""
    vectors, meta_rows = [], []
    for seq, fid, track in zip(dom_seqs + sub_seqs, file_ids*2, ['dom']*len(file_ids) + ['sub']*len(file_ids)):
        segments = split_by_neutral(seq, neutral_ids)
        for start, end in segments:
            seg = seq[start:end]
            if len(seg) < 20: 
                continue
            counts = np.bincount(seg, minlength=vocab_size)
            props = counts / len(seg)
            vectors.append(props)
            meta_rows.append({
                'session_id': fid, 'track': track, 'start_frame': start, 'end_frame': end,
                'duration_sec': len(seg) / fps, 'start_min': start / (60 * fps), 'end_min': end / (60 * fps)
            })
    return np.array(vectors), pd.DataFrame(meta_rows)

# =============================================================================
# 3. CLUSTERING (UNCHANGED)
# =============================================================================

def optimize_and_cluster(X: np.ndarray, k_range: range = range(3, 10), 
                         silhouette_sample=15000, random_state=42):
    """Find optimal k using silhouette on a subsample, then fit KMeans on full data."""
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    if len(X_scaled) > silhouette_sample:
        rng = np.random.RandomState(random_state)
        sub_idx = rng.choice(len(X_scaled), silhouette_sample, replace=False)
        X_sub = X_scaled[sub_idx]
    else:
        X_sub = X_scaled
    best_k, best_score, silhouette_scores = None, -1.0, {}
    for k in k_range:
        km = KMeans(n_clusters=k, init='k-means++', n_init=10, max_iter=300, random_state=random_state)
        km.fit(X_sub)
        score = silhouette_score(X_sub, km.labels_)
        silhouette_scores[k] = score
        print(f"  k={k:2d} | Silhouette (n={silhouette_sample}) = {score:.4f}")
        if score > best_score:
            best_score, best_k = score, k
    print(f"✅ Optimal k = {best_k} (Silhouette = {best_score:.4f})")
    final_km = KMeans(n_clusters=best_k, init='k-means++', n_init=10, max_iter=300, random_state=random_state)
    final_labels = final_km.fit_predict(X_scaled)
    return final_labels, best_k, silhouette_scores

# =============================================================================
# 8. GLM-HMM: CHAMBER-AWARE INPUT BUILDING
# =============================================================================

def build_chamber_aware_inputs(segments: np.ndarray, choices: np.ndarray, 
                               num_segment_types: int, max_lag: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build chamber-aware lagged input features for GLM-HMM.
    
    For each trial t, create a one-hot vector encoding the (chamber, behavior) 
    combination for each of the previous max_lag entries.
    
    Parameters:
    -----------
    segments : np.ndarray, shape (T,)
        Segment type labels (0 to num_segment_types-1) for each entry
    choices : np.ndarray, shape (T,)
        Binary choices: 1 = dominant chamber, 0 = subordinate chamber
    num_segment_types : int
        Number of distinct segment behavior types from clustering
    max_lag : int, default=5
        Number of past entries to include as history
        
    Returns:
    --------
    inputs : np.ndarray, shape (T-max_lag, input_dim)
        Input matrix where input_dim = max_lag * 2 * num_segment_types
    choices_trimmed : np.ndarray, shape (T-max_lag,)
        Choices aligned with inputs (first max_lag entries removed)
    """
    input_dim = max_lag * 2 * num_segment_types  # 2 chambers × M behaviors × L lags
    T = len(segments)
    inputs = np.zeros((T - max_lag, input_dim), dtype=float)
    
    for t in range(max_lag, T):
        for lag in range(1, max_lag + 1):
            idx = t - lag  # index of the past entry
            chamber = int(choices[idx])  # 0 or 1
            behav = int(segments[idx])   # 0 to M-1
            # Position in one-hot vector: [lag][chamber][behavior]
            pos = (lag - 1) * (2 * num_segment_types) + chamber * num_segment_types + behav
            inputs[t - max_lag, pos] = 1.0
    
    return inputs, choices[max_lag:]


def pool_sessions_for_glmhmm(segment_labels_list: List[np.ndarray], 
                            choice_list: List[np.ndarray],
                            num_segment_types: int, 
                            max_lag: int = 5) -> Tuple[List[np.ndarray], List[np.ndarray]]:
    """
    Pool multiple sessions/nights into format suitable for GLM-HMM fitting.
    
    Parameters:
    -----------
    segment_labels_list : list of np.ndarray
        Each element is segment labels for one session
    choice_list : list of np.ndarray
        Each element is binary choices for one session
    num_segment_types : int
        Number of distinct segment behavior types
    max_lag : int
        Number of past entries to include as history
        
    Returns:
    --------
    all_inputs : list of np.ndarray
        Each element is input matrix for one session, shape (T_session-max_lag, input_dim)
    all_choices : list of np.ndarray
        Each element is trimmed choices for one session, shape (T_session-max_lag,)
    """
    all_inputs, all_choices = [], []
    for segs, chs in zip(segment_labels_list, choice_list):
        if len(segs) <= max_lag:
            continue  # Skip sessions too short
        inputs, choices_trimmed = build_chamber_aware_inputs(segs, chs, num_segment_types, max_lag)
        all_inputs.append(inputs)
        all_choices.append(choices_trimmed)
    print(f"✅ Pooled {len(all_inputs)} sessions for GLM-HMM")
    return all_inputs, all_choices

# =============================================================================
# 9. GLM-HMM: MODEL FITTING & CROSS-VALIDATION
# =============================================================================

def fit_glmhmm(all_choices: List[np.ndarray], all_inputs: List[np.ndarray], 
              num_states: int, input_dim: int, 
              method: str = 'em', prior_sigma: Optional[float] = None,
              prior_alpha: Optional[float] = None,
              num_iters: int = 200, tolerance: float = 1e-4,
              random_state: int = 42) -> 'HMM':
    """
    Fit a GLM-HMM using the ssm package.
    
    Parameters:
    -----------
    all_choices : list of np.ndarray
        Binary choice arrays for each session
    all_inputs : list of np.ndarray
        Input feature arrays for each session
    num_states : int
        Number of latent strategy states
    input_dim : int
        Dimensionality of input features
    method : str, default='em'
        Fitting method: 'em' for Expectation-Maximization
    prior_sigma : float, optional
        Standard deviation for Gaussian prior on GLM weights (for MAP estimation)
    prior_alpha : float, optional
        Concentration parameter for Dirichlet prior on transition matrix
    num_iters : int, default=200
        Maximum EM iterations
    tolerance : float, default=1e-4
        Convergence tolerance for EM
    random_state : int, default=42
        Random seed for reproducibility
        
    Returns:
    --------
    model : HMM
        Fitted GLM-HMM model
    """
    np.random.seed(random_state)
    
    # Configure observation and transition models
    obs_kwargs = dict(C=2)  # Binary choice
    if prior_sigma is not None:
        obs_kwargs['prior_sigma'] = prior_sigma
    
    if prior_alpha is not None:
        # Use "sticky" transitions with kappa=0 to get Dirichlet prior without stickiness
        trans_type, trans_kwargs = "sticky", dict(alpha=prior_alpha, kappa=0)
    else:
        trans_type, trans_kwargs = "standard", {}
    
    # Instantiate model
    model = HMM(
        num_states, 1, input_dim,
        observations="input_driven_obs", observation_kwargs=obs_kwargs,
        transitions=trans_type, transition_kwargs=trans_kwargs
    )
    
    # Fit model
    ll_trace = model.fit(
        all_choices, inputs=all_inputs, method=method,
        num_iters=num_iters, tolerance=tolerance
    )
    
    print(f"✅ GLM-HMM fitted: {num_states} states, final log-likelihood = {ll_trace[-1]:.2f}")
    return model, ll_trace


def cross_validate_glmhmm(all_choices: List[np.ndarray], all_inputs: List[np.ndarray],
                         num_states: int, input_dim: int, 
                         num_folds: int = 5, random_state: int = 42,
                         prior_sigma: Optional[float] = None,
                         prior_alpha: Optional[float] = None) -> Tuple[float, float]:
    """
    Leave-one-session-out cross-validation for GLM-HMM hyperparameter selection.
    
    Returns:
    --------
    mean_test_ll : float
        Mean test log-likelihood across folds
    std_test_ll : float
        Standard deviation of test log-likelihood
    """
    np.random.seed(random_state)
    n_sessions = len(all_choices)
    cv_scores = []
    
    # Simple leave-one-out if num_folds >= n_sessions
    if num_folds >= n_sessions:
        fold_indices = [(list(set(range(n_sessions)) - {i}), [i]) for i in range(n_sessions)]
    else:
        # Random fold assignment
        rng = np.random.RandomState(random_state)
        fold_assignments = rng.randint(0, num_folds, n_sessions)
        fold_indices = [
            (np.where(fold_assignments != f)[0].tolist(), np.where(fold_assignments == f)[0].tolist())
            for f in range(num_folds)
        ]
    
    for train_idx, test_idx in fold_indices:
        # Skip if test set is empty
        if len(test_idx) == 0:
            continue
            
        # Train model
        model, _ = fit_glmhmm(
            [all_choices[i] for i in train_idx],
            [all_inputs[i] for i in train_idx],
            num_states, input_dim,
            prior_sigma=prior_sigma, prior_alpha=prior_alpha,
            num_iters=100, random_state=random_state
        )
        
        # Evaluate on test set
        if len(test_idx) > 0:
            test_ll = model.log_likelihood(
                [all_choices[i] for i in test_idx],
                inputs=[all_inputs[i] for i in test_idx]
            )
            cv_scores.append(test_ll)
    
    if len(cv_scores) == 0:
        return -np.inf, np.inf
    return np.mean(cv_scores), np.std(cv_scores)

# =============================================================================
# 10. GLM-HMM: VISUALIZATION & INTERPRETATION
# =============================================================================

def plot_state_probabilities_over_time(model: 'HMM', all_choices: List[np.ndarray],
                                       all_inputs: List[np.ndarray], 
                                       timestamps_list: List[np.ndarray],
                                       out_dir: str, bin_width_hours: float = 0.5,
                                       highlight_hour: Optional[float] = 3.0):
    """
    Plot posterior state probabilities aligned to clock time across all sessions.
    
    Parameters:
    -----------
    model : HMM
        Fitted GLM-HMM model
    all_choices, all_inputs : lists of arrays
        Data used for fitting
    timestamps_list : list of np.ndarray
        Each element contains timestamps (in minutes from recording start) 
        for the corresponding session's choices
    out_dir : str
        Directory to save output figures
    bin_width_hours : float, default=0.5
        Time bin width for averaging state probabilities
    highlight_hour : float, optional
        Hour to highlight with vertical line (e.g., 3.0 for hypothesis test)
    """
    
    # Compute posterior state probabilities for each session
    posteriors = []
    for ch, inp in zip(all_choices, all_inputs):
        post = model.expected_states(data=ch, input=inp)[0]  # shape (T, num_states)
        posteriors.append(post)
    
    # Align all sessions to common time axis (hours since start)
    all_times = np.concatenate([ts / 60 for ts in timestamps_list])  # convert to hours
    all_posts = np.concatenate(posteriors)
    
    time_bins = np.arange(0, 12 + bin_width_hours, bin_width_hours)
    avg_posts = np.zeros((len(time_bins) - 1, model.K))
    
    for i in range(len(time_bins) - 1):
        mask = (all_times >= time_bins[i]) & (all_times < time_bins[i + 1])
        if mask.sum() > 0:
            avg_posts[i] = all_posts[mask].mean(axis=0)
    
    time_centers = time_bins[:-1] + bin_width_hours / 2
    
    # Plot
    plt.figure(figsize=(12, 6))
    colors = plt.cm.tab10(np.linspace(0, 1, model.K))
    for k in range(model.K):
        plt.plot(time_centers, avg_posts[:, k], label=f'State {k+1}', 
                color=colors[k], linewidth=2.5, marker='o', markersize=4)
    
    if highlight_hour is not None:
        plt.axvline(x=highlight_hour, color='red', linestyle='--', 
                   alpha=0.6, linewidth=2, label=f'{highlight_hour}h hypothesis')
    
    plt.xlabel('Hours Since Recording Start', fontsize=13)
    plt.ylabel('Posterior Probability', fontsize=13)
    plt.title('Population-Average Strategy Usage Over Night', fontsize=15, fontweight='bold')
    plt.legend(loc='best', fontsize=11)
    plt.grid(alpha=0.3, linestyle='--')
    plt.xlim(0, 12)
    plt.ylim(0, 1.05)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'strategy_shift_over_time.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # Save state occupancy data
    occupancy_df = pd.DataFrame(avg_posts, columns=[f'State_{k+1}' for k in range(model.K)])
    occupancy_df['time_hours'] = time_centers
    occupancy_df.to_csv(os.path.join(out_dir, 'state_occupancy_by_hour.csv'), index=False)
    
    print(f"📈 Strategy shift plot saved: strategy_shift_over_time.png")
    return time_centers, avg_posts


def plot_transition_matrix(model: 'HMM', out_dir: str):
    """Visualize the learned state transition matrix."""
    trans_mat = np.exp(model.transitions.log_Ps)  # Convert log-probs to probabilities
    
    plt.figure(figsize=(6, 5))
    plt.imshow(trans_mat, cmap='Blues', vmin=0, vmax=1, aspect='auto')
    
    # Add value labels
    for i in range(model.K):
        for j in range(model.K):
            plt.text(j, i, f'{trans_mat[i,j]:.2f}', ha='center', va='center', fontsize=11)
    
    plt.xticks(np.arange(model.K), [f'S{k+1}' for k in range(model.K)], fontsize=12)
    plt.yticks(np.arange(model.K), [f'S{k+1}' for k in range(model.K)], fontsize=12)
    plt.xlabel('Next State', fontsize=12)
    plt.ylabel('Current State', fontsize=12)
    plt.title('Strategy Transition Probabilities', fontsize=14, fontweight='bold')
    plt.colorbar(label='Probability', fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'transition_matrix.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # Save transition matrix to CSV
    trans_df = pd.DataFrame(trans_mat, 
                           index=[f'State_{k+1}' for k in range(model.K)],
                           columns=[f'State_{k+1}' for k in range(model.K)])
    trans_df.to_csv(os.path.join(out_dir, 'transition_matrix.csv'))
    
    print(f"📊 Transition matrix saved: transition_matrix.png")


def plot_state_weights(model: 'HMM', num_segment_types: int, max_lag: int,
                      idx_to_name: dict, out_dir: str, top_n_behaviors: int = 6):
    """
    Visualize GLM weights for each state, showing how past (chamber, behavior) 
    combinations influence choice probability.
    
    Parameters:
    -----------
    model : HMM
        Fitted GLM-HMM model
    num_segment_types : int
        Number of distinct segment behavior types
    max_lag : int
        Number of lags used in input construction
    idx_to_name : dict
        Mapping from behavior index to name
    out_dir : str
        Output directory
    top_n_behaviors : int, default=6
        Number of top behaviors to display per lag
    """
    # Extract weights: shape (num_states, input_dim, 1) for binary case
    weights = model.observations.params.reshape(model.K, -1)
    
    # Reshape to (num_states, max_lag, 2 chambers, num_segment_types)
    weights_reshaped = weights.reshape(model.K, max_lag, 2, num_segment_types)
    
    # Get behavior names, excluding 'other'
    behavior_names = [name for name in idx_to_name.values() if name not in ['other', 'ejaculation']]
    behavior_indices = [idx for idx, name in idx_to_name.items() if name not in ['other', 'ejaculation']]
    
    # Average weights across lags for a summary view
    avg_weights = weights_reshaped.mean(axis=1)  # (num_states, 2, num_segment_types)
    
    # Select top behaviors by overall weight magnitude
    global_weight_magnitude = np.abs(avg_weights).mean(axis=0).sum(axis=0)  # (num_segment_types,)
    top_behavior_idx = np.argsort(global_weight_magnitude)[::-1][:top_n_behaviors]
    top_behavior_names = [idx_to_name[i] for i in behavior_indices if i in top_behavior_idx]
    top_behavior_idx = [i for i in top_behavior_idx if i in behavior_indices]
    
    # Plot weights for each state
    fig, axes = plt.subplots(1, model.K, figsize=(6 * model.K, 5), constrained_layout=True)
    if model.K == 1:
        axes = [axes]
    
    chamber_labels = ['Subordinate', 'Dominant']
    
    for k, ax in enumerate(axes):
        # Extract weights for this state and top behaviors
        state_weights = avg_weights[k][:, top_behavior_idx]  # (2 chambers, top_n_behaviors)
        
        im = ax.imshow(state_weights, cmap='RdBu_r', vmin=-3, vmax=3, aspect='auto')
        ax.set_xticks(np.arange(len(top_behavior_names)))
        ax.set_xticklabels(top_behavior_names, rotation=45, ha='right', fontsize=9)
        ax.set_yticks(np.arange(2))
        ax.set_yticklabels(chamber_labels, fontsize=10)
        ax.set_title(f'State {k+1} Weights (avg across lags)', fontsize=11, fontweight='bold')
        ax.set_xlabel('Behavior', fontsize=10)
        ax.set_ylabel('Chamber Context', fontsize=10)
        plt.colorbar(im, ax=ax, label='Log Odds Weight', fraction=0.046, pad=0.04)
        ax.grid(False)
    
    plt.suptitle('Strategy Signatures: How Past Behaviors Influence Choice', 
                fontsize=15, fontweight='bold', y=1.02)
    plt.savefig(os.path.join(out_dir, 'state_weight_heatmaps.png'), dpi=300, bbox_inches='tight')
    plt.close()

    # Save detailed weights to CSV for further analysis
    weight_df = pd.DataFrame(
        weights, 
        columns=[f'lag{l+1}_{"dom" if c else "sub"}_{idx_to_name[b]}' 
                for l in range(max_lag) for c in [1, 0] for b in range(num_segment_types)]
    )
    weight_df['state'] = [f'State_{k+1}' for k in range(model.K) for _ in range(weights.shape[1] // model.K)]
    weight_df.to_csv(os.path.join(out_dir, 'state_weights_detailed.csv'), index=False)
    
    print(f"🎨 Weight visualization saved: state_weight_heatmaps.png")


def test_strategy_shift_significance(posteriors: List[np.ndarray], 
                                    timestamps_list: List[np.ndarray],
                                    split_hour: float = 3.0, 
                                    n_perm: int = 1000,
                                    random_state: int = 42) -> Tuple[float, float]:
    """
    Permutation test for significance of strategy shift at specified hour.
    
    Tests whether the change in state occupancy before vs. after split_hour
    is greater than expected by chance.
    
    Returns:
    --------
    obs_stat : float
        Observed test statistic (max absolute change in state probability)
    p_value : float
        Empirical p-value from permutation test
    """
    np.random.seed(random_state)
    
    # Compute observed difference
    early_posts = np.concatenate([p[ts/60 < split_hour] for p, ts in zip(posteriors, timestamps_list)])
    late_posts = np.concatenate([p[ts/60 >= split_hour] for p, ts in zip(posteriors, timestamps_list)])
    obs_diff = late_posts.mean(axis=0) - early_posts.mean(axis=0)
    obs_stat = np.max(np.abs(obs_diff))  # max absolute change across states
    
    # Permutation test: shuffle trial order within each session
    perm_stats = []
    for _ in range(n_perm):
        perm_posts = []
        for p, ts in zip(posteriors, timestamps_list):
            idx = np.random.permutation(len(p))
            perm_posts.append(p[idx])
        perm_early = np.concatenate([pp[ts/60 < split_hour] for pp, ts in zip(perm_posts, timestamps_list)])
        perm_late = np.concatenate([pp[ts/60 >= split_hour] for pp, ts in zip(perm_posts, timestamps_list)])
        perm_diff = perm_late.mean(axis=0) - perm_early.mean(axis=0)
        perm_stats.append(np.max(np.abs(perm_diff)))
    
    p_value = np.mean(np.array(perm_stats) >= obs_stat)
    return obs_stat, p_value

def assess_model_reliability(model, all_choices, all_inputs, 
                           timestamps_list, out_dir, 
                           max_lag=5, num_seg_types=8):
    """Quick diagnostic summary."""
    print("\n" + "="*60)
    print("🔍 MODEL RELIABILITY ASSESSMENT")
    print("="*60)
    
    # 2. Transition matrix sanity
    trans = np.exp(model.transitions.log_Ps)
    diag_mean = np.mean(np.diag(trans))
    print(f"✅ Transition persistence (mean diagonal): {diag_mean:.3f} {'(good)' if diag_mean > 0.8 else '(check)'}")
    
    # 3. Weight magnitude (regularization check)
    weights = model.observations.params.reshape(model.K, -1)
    weight_std = np.std(weights)
    print(f"✅ Weight dispersion (std): {weight_std:.3f} {'(regularized)' if weight_std < 3 else '(may be overfit)'}")
    
    # 4. Posterior state clarity
    posteriors = [model.expected_states(data=ch, input=inp)[0] for ch, inp in zip(all_choices, all_inputs)]
    avg_max_post = np.mean([np.max(p, axis=1).mean() for p in posteriors])
    print(f"✅ Posterior confidence (avg max prob): {avg_max_post:.3f} {'(clear)' if avg_max_post > 0.7 else '(uncertain)'}")
    
    # 5. Temporal structure (quick visual)
    time_centers, avg_posts = plot_state_probabilities_over_time(
        model, all_choices, all_inputs, timestamps_list, out_dir, highlight_hour=3.0)
    
    print("\n📊 Next steps:")
    print("   • Inspect state_weight_heatmaps.png for interpretable patterns")
    print("   • Check strategy_shift_test.txt for p-value of 3h shift")
    print("   • If any 'check' flags above, try stronger prior_sigma (e.g., 5.0)")
    print("="*60 + "\n")

# =============================================================================
# 11. MAIN PIPELINE WITH GLM-HMM INTEGRATION
# =============================================================================

def main():
    # ==================== CONFIGURATION ====================
    h5_dir = r"D:\Data\Videos\ASOiD Predict"
    out_dir = os.path.join(h5_dir, "output_segment_clusters_glmhmm")
    os.makedirs(out_dir, exist_ok=True)
    
    # Segmentation parameters
    neutral_ids = None  # Will be set after loading
    vocab_size = None   # Will be set after loading
    
    # Clustering parameters
    k_range = range(9,10)
    silhouette_sample = 15000
    
    # GLM-HMM parameters
    max_lag = 40                   # Number of past entries to include as history
    num_states_range = [1,2,3]  # Test different numbers of latent strategies
    prior_sigma = 2.0             # Gaussian prior std for MAP estimation (None for MLE)
    prior_alpha = 2.0             # Dirichlet prior concentration for transitions
    glmhmm_iters = 200            # EM iterations for GLM-HMM
    
    # Analysis parameters
    min_start, min_end = 0, 721   # Minutes to include in analysis
    filter_dates = [1]            # Which days to include
    filter_se = "SE"              # "SE", "VG", or None
    
    # ==================== STEP 1: LOAD & SEGMENT ====================
    print("📥 Loading sessions & remapping roles...")
    dom_s, sub_s, fids, idx_name, vocab_map, fps, other_id = load_dual_role_full_10hz(h5_dir)
    print(f"   ✅ {len(dom_s)} sessions | {len(vocab_map)} behaviors | {fps}Hz")
    
    neutral_ids = [other_id]
    vocab_size = len(vocab_map)
    
    print("⏱️ Computing segment proportion vectors...")
    X, meta = compute_segment_vectors(dom_s, sub_s, fids, neutral_ids, fps, vocab_size)
    print(f"   ✅ {len(X)} active segments extracted")
    
    print("🔍 Optimizing clusters (silhouette score)...")
    cluster_labels, best_k, silhouette_scores = optimize_and_cluster(X, k_range=k_range, silhouette_sample=silhouette_sample)
    meta['cluster'] = cluster_labels
    

    # ==================== STEP 3: PREPARE DATA FOR GLM-HMM ====================
    print("\n🧠 Preparing data for GLM-HMM analysis...")
    
    # Extract segment labels and choices per session for GLM-HMM
    # We need: for each entry, which chamber was chosen (binary) and what segment type occurred
    segment_labels_list, choice_list, timestamps_list = [], [], []
    
    # Load session metadata for timestamps
    session_meta = {}
    for f in sorted(glob.glob(os.path.join(h5_dir, "*.h5"))):
        with h5py.File(f, 'r') as hf:
            attrs = dict(hf['/meta'].attrs)
            sid = os.path.basename(f)
            session_meta[sid] = {
                'day': int(attrs.get('day', 0)),
                'se': attrs.get('se_status', False),
                'fps': float(attrs.get('fps', fps))
            }
    
    # Process each session
    for dom_seq, sub_seq, fid in zip(dom_s, sub_s, fids):
        # Apply same filters as in cluster analysis
        if filter_dates is not None:
            day = session_meta.get(fid, {}).get('day')
            if day not in filter_dates:
                continue
        if filter_se == "SE" and not session_meta.get(fid, {}).get('se'):
            continue
        elif filter_se == "VG" and session_meta.get(fid, {}).get('se'):
            continue

        fps = session_meta[fid]['fps']
        
        # Get segments for this session from meta
        session_meta_df = meta[meta['session_id'] == fid]
        
        # Extract choices and segment labels per entry
        dom_entries = session_meta_df[session_meta_df['track'] == 'dom']
        sub_entries = session_meta_df[session_meta_df['track'] == 'sub']
        
        # Create arrays: choices (1=dom, 0=sub) and segment labels
        choices = np.concatenate([np.ones(len(dom_entries)), np.zeros(len(sub_entries))])
        segments = np.concatenate([dom_entries['cluster'].values, sub_entries['cluster'].values])
        timestamps = np.concatenate([dom_entries['start_min'].values, sub_entries['start_min'].values])
        
        # Sort by timestamp to get chronological order
        sort_idx = np.argsort(timestamps)
        choices = choices[sort_idx]
        segments = segments[sort_idx]
        timestamps = timestamps[sort_idx]
        
        # Apply time filters
        time_mask = (timestamps >= min_start) & (timestamps <= min_end)
        choices = choices[time_mask]
        segments = segments[time_mask]
        timestamps = timestamps[time_mask]
        
        if len(choices) > max_lag:
            segment_labels_list.append(segments.astype(int))
            choice_list.append(choices.reshape(-1, 1).astype(int))
            timestamps_list.append(timestamps[max_lag:])
    
    print(f"✅ Prepared {len(segment_labels_list)} sessions for GLM-HMM")
    
    # Pool sessions into GLM-HMM format
    num_segment_types = best_k  # Number of clusters from K-means
    input_dim = max_lag * 2 * num_segment_types
    
    print(f"🔧 Building chamber-aware inputs (lag={max_lag}, behaviors={num_segment_types})...")
    all_inputs, all_choices = pool_sessions_for_glmhmm(
        segment_labels_list, choice_list, num_segment_types, max_lag
    )
    
    if len(all_inputs) == 0:
        print("⚠️ No valid sessions for GLM-HMM after filtering. Skipping GLM-HMM analysis.")
        return
    
    # ==================== STEP 4: SELECT NUMBER OF STATES VIA CROSS-VALIDATION ====================
    print("\n🔍 Selecting optimal number of GLM-HMM states via cross-validation...")
    
    cv_results = {}
    for K in num_states_range:
        mean_ll, std_ll = cross_validate_glmhmm(
            all_choices, all_inputs, K, input_dim,
            prior_sigma=prior_sigma, prior_alpha=prior_alpha,
            num_folds=min(5, len(all_inputs)), random_state=42
        )
        cv_results[K] = (mean_ll, std_ll)
        print(f"  K={K}: CV Log-Likelihood = {mean_ll:.2f} ± {std_ll:.2f}")
    
    # Select best K
    best_glmhmm_K = max(cv_results, key=lambda k: cv_results[k][0])
    print(f"✅ Selected K={best_glmhmm_K} states for GLM-HMM based on cross-validated likelihood")
    
    # Save CV results
    cv_df = pd.DataFrame([
        {'num_states': K, 'mean_test_ll': ll[0], 'std_test_ll': ll[1]}
        for K, ll in cv_results.items()
    ])
    cv_df.to_csv(os.path.join(out_dir, 'glmhmm_cross_validation.csv'), index=False)
    
    # ==================== STEP 5: FIT FINAL GLM-HMM ====================
    print(f"\n🧠 Fitting final GLM-HMM with K={best_glmhmm_K} states...")
    
    model, ll_trace = fit_glmhmm(
        all_choices, all_inputs, best_glmhmm_K, input_dim,
        prior_sigma=prior_sigma, prior_alpha=prior_alpha,
        num_iters=glmhmm_iters, random_state=42
    )
    
    # Save model
    with open(os.path.join(out_dir, 'glmhmm_model.pkl'), 'wb') as f:
        pickle.dump(model, f)
    print(f"💾 Model saved to glmhmm_model.pkl")
    
    # Plot convergence
    plt.figure(figsize=(8, 5))
    plt.plot(ll_trace, label='EM', linewidth=2)
    plt.xlabel('EM Iteration', fontsize=12)
    plt.ylabel('Log Likelihood', fontsize=12)
    plt.title(f'GLM-HMM Convergence (K={best_glmhmm_K})', fontsize=14, fontweight='bold')
    plt.grid(alpha=0.3, linestyle='--')
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'glmhmm_convergence.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    assess_model_reliability(model, all_choices, all_inputs, timestamps_list, out_dir, max_lag, num_segment_types)

    # ==================== STEP 6: VISUALIZE STRATEGY SHIFT ====================
    print("\n📈 Visualizing strategy shift over time...")
    
    # Compute posteriors for permutation test
    posteriors = [model.expected_states(data=ch, input=inp)[0] for ch, inp in zip(all_choices, all_inputs)]
    
    # Plot state probabilities over time
    time_centers, avg_posts = plot_state_probabilities_over_time(
        model, all_choices, all_inputs, timestamps_list, out_dir,
        bin_width_hours=0.5, highlight_hour=3.0
    )
    
    # Test significance of 3-hour shift
    print(f"🧪 Testing significance of strategy shift at 3 hours...")
    obs_stat, p_value = test_strategy_shift_significance(
        posteriors, timestamps_list, split_hour=3.0, n_perm=1000, random_state=42
    )
    print(f"   Observed shift statistic: {obs_stat:.3f}")
    print(f"   Permutation test p-value: {p_value:.3f}")
    
    # Save test results
    with open(os.path.join(out_dir, 'strategy_shift_test.txt'), 'w') as f:
        f.write(f"Strategy Shift Significance Test (split at 3 hours)\n")
        f.write(f"Observed statistic (max |Δstate prob|): {obs_stat:.4f}\n")
        f.write(f"Permutation test p-value (n=1000): {p_value:.4f}\n")
        f.write(f"Conclusion: {'Significant shift detected' if p_value < 0.05 else ' No significant shift'}\n")
    
    # ==================== STEP 7: VISUALIZE TRANSITIONS & WEIGHTS ====================
    print("🎨 Visualizing transition matrix and state weights...")
    
    plot_transition_matrix(model, out_dir)
    plot_state_weights(model, num_segment_types, max_lag, idx_name, out_dir, top_n_behaviors=6)
    
    # ==================== STEP 8: EXAMPLE INDIVIDUAL TRAJECTORY ====================
    print("📊 Plotting example individual strategy trajectory...")
    
    if len(all_choices) > 0:
        example_idx = 0
        viterbi_states = model.most_likely_states(data=all_choices[example_idx], input=all_inputs[example_idx])
        
        plt.figure(figsize=(12, 4))
        plt.plot(timestamps_list[example_idx] / 60, viterbi_states + 1, 
                drawstyle='steps-post', linewidth=2, color='#2ca02c')
        plt.axvline(x=3, color='red', linestyle='--', alpha=0.5, label="3h hypothesis")
        plt.xlabel("Hours Since Recording Start", fontsize=12)
        plt.ylabel("Most Likely Strategy State", fontsize=12)
        plt.yticks(np.arange(1, best_glmhmm_K+1), [f'State {k+1}' for k in range(best_glmhmm_K)], fontsize=10)
        plt.title(f"Example Session: Strategy Trajectory", fontsize=14, fontweight='bold')
        plt.legend(loc='best', fontsize=10)
        plt.grid(alpha=0.3, linestyle='--')
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'example_strategy_trajectory.png'), dpi=300, bbox_inches='tight')
        plt.close()
    
    # ==================== STEP 9: SUMMARY & INTERPRETATION ====================
    print(f"\n{'='*70}")
    print(f"✅ GLM-HMM PIPELINE COMPLETE")
    print(f"{'='*70}")
    print(f"📁 Outputs saved to: {out_dir}")
    print(f"📊 Key files:")
    print(f"   • strategy_shift_over_time.png  → Population strategy usage across night")
    print(f"   • transition_matrix.png         → How strategies switch between entries")
    print(f"   • state_weight_heatmaps.png     → What behaviors drive choices in each state")
    print(f"   • glmhmm_model.pkl              → Fitted model for reuse")
    print(f"   • strategy_shift_test.txt       → Statistical test of 3h shift hypothesis")
    print(f"\n🔍 Interpretation guide:")
    print(f"   • If State 1 dominates early (0-3h) with weights favoring subordinate chamber,")
    print(f"     and State 2 dominates late with weights favoring dominant chamber → hypothesis supported ✅")
    print(f"   • Check transition matrix: high S1→S2 probability with low S2→S1 → unidirectional shift")
    print(f"   • p-value < 0.05 in strategy_shift_test.txt → shift is statistically significant")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()