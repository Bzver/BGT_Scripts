import os
import re
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from typing import Dict, Tuple, List, Optional


def find_bannotator_labels(root_path:str) -> Tuple[List[str], List[str]]:
    nex_files = []
    ctrl_files = []

    for root, _, files in os.walk(root_path):
        for f in files:
            if not f.endswith(".txt"):
                continue
            if "nex" in f or "NEX" in f:
                nex_files.append(os.path.join(root, f))
                continue
            if "ctrl" in f or "CTRL" in f:
                ctrl_files.append(os.path.join(root, f))

    return nex_files, ctrl_files

def annot_to_array(input_file, cutoff=None) -> Tuple[np.ndarray, Dict[str, int]]:
    if not os.path.isfile(input_file):
        print(f"{input_file} does not exist!")
        return None, {}
    text_content = read_text_file(input_file)
    if text_content is None:
        return None, {}
    config, data = parse_annotation(text_content)

    behavior_map = {}
    behavior_map["other"] = 0

    i = 1
    for beh in sorted(config.keys()):
        if beh == "other":
            continue
        behavior_map[beh] = i
        i += 1

    max_frame = data[-1]["end"] if data else 0
    if cutoff and cutoff < max_frame:
        max_frame = cutoff

    annot_array = np.zeros(max_frame, dtype=np.uint8)
    
    for seg in data:
        original_type = seg["type"]
        if original_type not in behavior_map:
            continue
        beh_idx = behavior_map[original_type]

        start = max(0, seg["start"] - 1)
        end = min(max_frame, seg["end"] - 1)
        
        if end > start:
            annot_array[start:end] = beh_idx

    return annot_array, behavior_map

def read_text_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        print(f"Error: The file at {file_path} was not found.")
        return None
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return None

def parse_annotation(text_content):
    config = {}
    s1_data = []
    lines = text_content.strip().split('\n')
    
    config_start_index = -1
    for i, line in enumerate(lines):
        if "Configuration file:" in line:
            config_start_index = i + 1
            break
    
    if config_start_index != -1:
        for i in range(config_start_index, len(lines)):
            line = lines[i].strip()
            if not line:
                continue
            if "S1:" in line:
                break
            
            parts = re.split(r'\s+', line)
            if len(parts) == 2:
                config[parts[0]] = parts[1]

    s1_start_index = -1
    for i, line in enumerate(lines):
        if "S1:" in line:
            s1_start_index = i + 2
            break

    if s1_start_index != -1:
        for i in range(s1_start_index, len(lines)):
            line = lines[i].strip()
            if not line:
                continue
            
            parts = re.split(r'\s+', line)
            parts = [part for part in parts if part]

            if len(parts) == 3:
                try:
                    start = int(parts[0])
                    end = int(parts[1])
                    type_ = parts[2]
                    s1_data.append({"start": start, "end": end, "type": type_})
                except ValueError:
                    continue
    return config, s1_data


def fdr_bh(p_vals: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    p_vals = np.asarray(p_vals).flatten().copy()
    m = len(p_vals)
    
    # Handle NaN values
    valid_mask = ~np.isnan(p_vals)
    valid_p = p_vals[valid_mask].copy()
    
    if len(valid_p) == 0:
        h = np.zeros(m, dtype=bool)
        s = np.zeros(m)
        adj_p = np.ones(m)
        adj_p[~valid_mask] = np.nan
        return h, s, adj_p
    
    # Sort p-values with original indices
    sort_idx = np.argsort(valid_p)
    sorted_p = valid_p[sort_idx]
    m_valid = len(sorted_p)
    
    # Calculate adjusted p-values (step-up procedure)
    adj_p_sorted = np.zeros(m_valid)
    adj_p_sorted[-1] = sorted_p[-1]
    for i in range(m_valid - 2, -1, -1):
        adj_p_sorted[i] = min(sorted_p[i] * m_valid / (i + 1), adj_p_sorted[i + 1])
    adj_p_sorted = np.minimum(adj_p_sorted, 1.0)
    
    # Map back to original order
    adj_p = np.ones(m)
    adj_p[valid_mask] = adj_p_sorted[np.argsort(sort_idx)]
    adj_p[~valid_mask] = np.nan
    
    h = adj_p < 0.05
    s = h.astype(float)
    
    return h, s, adj_p


def pval_to_sig_label(p: float) -> str:
    """Convert p-value to significance label string (MATLAB-style)."""
    if np.isnan(p):
        return 'N/A'
    elif p < 0.001:
        return f'{p:.3f}\n***'
    elif p < 0.01:
        return f'{p:.3f}\n**'
    elif p < 0.05:
        return f'{p:.3f}\n*'
    else:
        return f'{p:.3f}\nns'


def _bin_annotation_to_time_series(annot_array: np.ndarray, behavior_map: Dict[str, int],
                                    time_bins: np.ndarray, frame_to_sec: float = 1/30) -> np.ndarray:
    """
    Convert 1D annotation array to time-binned behavior duration matrix.
    
    Parameters:
    -----------
    annot_array : ndarray
        1D array where each element is a behavior index
    behavior_map : dict
        Mapping from behavior name to index
    time_bins : ndarray
        Time bin edges in minutes
    frame_to_sec : float
        Conversion factor from frames to minutes
    
    Returns:
    --------
    behavior_time_matrix : ndarray
        Shape: (n_behaviors, n_time_bins-1), values in minutes
    """
    n_beh = len(behavior_map)
    n_time = len(time_bins) - 1
    result = np.zeros((n_beh, n_time))
    
    for beh_name, beh_idx in behavior_map.items():
        print(f"{beh_name}: {beh_idx}")
        mask = (annot_array == beh_idx)
        for ti in range(n_time):
            start_frame = int(time_bins[ti] / frame_to_sec)
            end_frame = int(time_bins[ti + 1] / frame_to_sec)
            end_frame = min(end_frame, len(annot_array))
            
            if end_frame > start_frame:
                dur_frames = np.sum(mask[start_frame:end_frame])
                result[beh_idx, ti] = dur_frames * frame_to_sec
    
    return result


def _aggregate_group_time_series(file_list: List[str], behavior_map: Dict[str, int],
                                  time_bins: np.ndarray, cutoff: Optional[int] = None,
                                  frame_to_sec: float = 1/30) -> np.ndarray:
    """
    Aggregate time series data across multiple annotation files.
    
    Returns:
    --------
    group_data : ndarray
        Shape: (n_files, n_behaviors, n_time_bins-1)
    """
    if not file_list:
        return np.array([])
    
    valid_files = []
    all_series = []
    
    for f in file_list:
        annot_arr, f_bmap = annot_to_array(f, cutoff)
        if annot_arr is None or len(annot_arr) == 0:
            continue
        
        # Align behavior map
        aligned_bmap = {k: v for k, v in behavior_map.items() if k in f_bmap}
        if not aligned_bmap:
            continue
            
        series = _bin_annotation_to_time_series(annot_arr, aligned_bmap, time_bins, frame_to_sec)
        all_series.append(series)
        valid_files.append(f)
    
    if not all_series:
        return np.array([])
    
    return np.stack(all_series, axis=0)  # (n_files, n_beh, n_time)

def plot_grouped_bar(nex_files: List[str], ctrl_files: List[str], 
                     output_path: Optional[str] = None, cutoff: Optional[int] = None,
                     frame_to_sec: float = 1/30, show_all_pvals: bool = True,
                     show_raw_data: bool = True):
    """
    Plot 1: Grouped bar chart comparing total duration of each behavior.
    
    Parameters:
    -----------
    show_raw_data : bool
        If True, overlay individual data points as scatter plots
    """
    print("  Computing behavior durations...")
    
    # Get unified behavior map (excluding 'other')
    all_behaviors = set()
    for f in nex_files + ctrl_files:
        _, bmap = annot_to_array(f, cutoff)
        if bmap:
            all_behaviors.update(k for k in bmap.keys() if k != 'other')
    
    if not all_behaviors:
        print("  Warning: No behaviors found to plot")
        return None
    
    behavior_labels = sorted(all_behaviors)
    n_beh = len(behavior_labels)
    
    # Compute total durations per file per behavior
    def get_durations(file_list):
        durations = []
        for f in file_list:
            arr, bmap = annot_to_array(f, cutoff)
            if arr is None:
                continue
            file_durs = []
            for beh in behavior_labels:
                if beh in bmap:
                    dur = np.sum(arr == bmap[beh]) * frame_to_sec
                else:
                    dur = 0.0
                file_durs.append(dur)
            durations.append(file_durs)
        return np.array(durations) if durations else np.array([])
    
    nex_durs = get_durations(nex_files)
    ctrl_durs = get_durations(ctrl_files)
    
    if nex_durs.size == 0 or ctrl_durs.size == 0:
        print("  Warning: Insufficient data for plotting")
        return None
    
    # Compute statistics
    nex_mean = np.mean(nex_durs, axis=0)
    nex_sem = stats.sem(nex_durs, axis=0, nan_policy='omit')
    ctrl_mean = np.mean(ctrl_durs, axis=0)
    ctrl_sem = stats.sem(ctrl_durs, axis=0, nan_policy='omit')
    
    # Statistical testing (UNPAIRED t-test - independent groups)
    p_values = []
    for i in range(n_beh):
        nex_vals = nex_durs[:, i]
        ctrl_vals = ctrl_durs[:, i]
        if len(nex_vals) > 1 and len(ctrl_vals) > 1:
            # ttest_ind = unpaired/independent t-test (correct for different subjects)
            _, p = stats.ttest_ind(nex_vals, ctrl_vals, equal_var=False, nan_policy='omit')
        else:
            p = np.nan
        p_values.append(p)
    p_values = np.array(p_values)

    # Create plot
    print("  Generating grouped bar plot...")
    x = np.arange(n_beh)
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(max(12, n_beh * 1.8), 7), facecolor='white')
    
    # Plot bars first (so scatter points appear on top)
    bars_nex = ax.bar(x - width/2, nex_mean, width, yerr=nex_sem, 
                      capsize=5, label='NEX', color='#4E79A7', 
                      edgecolor='black', linewidth=0.5, alpha=0.8, zorder=2)
    bars_ctrl = ax.bar(x + width/2, ctrl_mean, width, yerr=ctrl_sem, 
                       capsize=5, label='CTRL', color='#F28E2B', 
                       edgecolor='black', linewidth=0.5, alpha=0.8, zorder=2)
    
    # Add scatter points for raw data
    if show_raw_data:
        np.random.seed(42)  # For reproducible jitter
        jitter_width = width * 0.3  # Jitter as fraction of bar width
        
        # NEX data points
        for i in range(n_beh):
            n_points = len(nex_durs[:, i])
            # Add random jitter to x-position to avoid overlap
            x_jitter = (x[i] - width/2) + np.random.uniform(-jitter_width, jitter_width, n_points)
            y_values = nex_durs[:, i]
            
            ax.scatter(x_jitter, y_values, 
                      color='#4E79A7', edgecolor='white', linewidth=0.8,
                      s=50, alpha=0.7, zorder=3, 
                      marker='o', label='_nolegend_')
        
        # CTRL data points
        for i in range(n_beh):
            n_points = len(ctrl_durs[:, i])
            # Add random jitter to x-position to avoid overlap
            x_jitter = (x[i] + width/2) + np.random.uniform(-jitter_width, jitter_width, n_points)
            y_values = ctrl_durs[:, i]
            
            ax.scatter(x_jitter, y_values, 
                      color='#F28E2B', edgecolor='white', linewidth=0.8,
                      s=50, alpha=0.7, zorder=3, 
                      marker='o', label='_nolegend_')
    
    # Add p-value labels (for all comparisons)
    for i in range(n_beh):
        p_raw_val = p_values[i]
        
        # Calculate position for p-value text (above all data points)
        y_max_data = max(np.max(nex_durs[:, i]), np.max(ctrl_durs[:, i]))
        y_max_bar = max(nex_mean[i] + nex_sem[i], ctrl_mean[i] + ctrl_sem[i])
        y_pos = max(y_max_data, y_max_bar) * 1.15 if max(y_max_data, y_max_bar) > 0 else 1.0
        
        if show_all_pvals:
            # Show p-value with significance indicator
            if np.isnan(p_raw_val):
                p_label = 'N/A'
            elif p_raw_val < 0.001:
                p_label = f'p<{0.001:.3f}***'
            elif p_raw_val < 0.01:
                p_label = f'{p_raw_val:.3f}**'
            elif p_raw_val < 0.05:
                p_label = f'{p_raw_val:.3f}*'
            else:
                p_label = f'{p_raw_val:.3f} ns'
            
            # Draw bracket
            ax.plot([x[i]-width/2, x[i]+width/2], [y_pos, y_pos], 'k-', linewidth=1.0, alpha=0.7)
            ax.plot([x[i]-width/2, x[i]-width/2], [y_pos, y_pos*1.02], 'k-', linewidth=1.0, alpha=0.7)
            ax.plot([x[i]+width/2, x[i]+width/2], [y_pos, y_pos*1.02], 'k-', linewidth=1.0, alpha=0.7)
            
            # Add p-value text
            ax.text(x[i], y_pos*1.04, p_label, ha='center', va='bottom', 
                   fontsize=8, fontweight='bold' if p_raw_val < 0.05 else 'normal', 
                   color='black' if p_raw_val < 0.05 else 'gray')
        else:
            # Only show significance markers for p < 0.05 (original behavior)
            if not np.isnan(p_raw_val) and p_raw_val < 0.05:
                # Draw bracket
                ax.plot([x[i]-width/2, x[i]+width/2], [y_pos, y_pos], 'k-', linewidth=1.2)
                ax.plot([x[i]-width/2, x[i]-width/2], [y_pos, y_pos*1.03], 'k-', linewidth=1.2)
                ax.plot([x[i]+width/2, x[i]+width/2], [y_pos, y_pos*1.03], 'k-', linewidth=1.2)
                
                # Add significance label
                if p_raw_val < 0.001:
                    sig = '***'
                elif p_raw_val < 0.01:
                    sig = '**'
                else:
                    sig = '*'
                ax.text(x[i], y_pos*1.05, sig, ha='center', va='bottom', 
                       fontsize=11, fontweight='bold', color='black')
    
    ax.set_xlabel('Behavior', fontsize=11, fontweight='bold')
    ax.set_ylabel('Total Duration (sec)', fontsize=11, fontweight='bold')
    ax.set_title('Behavior Duration Comparison: NEX vs CTRL', fontsize=13, fontweight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(behavior_labels, rotation=45, ha='right', fontsize=9)
    ax.legend(fontsize=10, frameon=True, edgecolor='gray', loc='upper left')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    # Set y-limit to accommodate all data points + p-value labels
    all_y_max = max(np.max(nex_durs), np.max(ctrl_durs))
    y_limit = all_y_max * 1.25 if all_y_max > 0 else 10
    ax.set_ylim([0, y_limit])
    
    plt.tight_layout()
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"  ✓ Saved: {output_path}")
    
    plt.show()
    
    stats_summary = {
        'behavior_labels': behavior_labels,
        'nex_mean': nex_mean, 'nex_sem': nex_sem, 'nex_n': len(nex_durs),
        'ctrl_mean': ctrl_mean, 'ctrl_sem': ctrl_sem, 'ctrl_n': len(ctrl_durs),
        'nex_raw': nex_durs, 'ctrl_raw': ctrl_durs,  # Added raw data
        'p_raw': p_values,
        'test_type': 'unpaired_ttest'  # Explicitly document test type
    }
    
    return fig, ax, stats_summary


def plot_trend_figure(nex_files: List[str], ctrl_files: List[str], 
                      beh_map: Dict[str, int], output_path: Optional[str] = None,
                      cutoff: Optional[int] = None, frame_to_sec: float = 1/30,
                      bin_size_min: float = 5.0):
    """
    Plot 2: Trend plot showing mean behavior expression over time.
    
    Matches MATLAB reference style:
    - Line plots with shaded ±SEM regions
    - Significance stars at time points with p<0.05 (FDR-corrected)
    - Subplot grid based on number of behaviors
    """
    print("  Computing time-series data...")
    
    color_nex = [0.2, 0.4, 0.6]
    color_ctrl = [0.9, 0.6, 0.1]
    
    # Unified behavior map
    behavior_map = beh_map
    n_beh = len(behavior_map)
    
    # Time axis: 0 to 720 min
    time_min = np.arange(0, 720 + bin_size_min/2, bin_size_min)
    n_time = len(time_min) - 1
    
    # Aggregate data for each group
    nex_data = _aggregate_group_time_series(nex_files, behavior_map, time_min, cutoff, frame_to_sec)
    ctrl_data = _aggregate_group_time_series(ctrl_files, behavior_map, time_min, cutoff, frame_to_sec)
    
    if nex_data.size == 0 or ctrl_data.size == 0:
        print("  Warning: Insufficient data for trend plot")
        return None
    
    # Compute group statistics: mean ± SEM
    m_nex = np.nanmean(nex_data, axis=0)  # (n_beh, n_time)
    s_nex = stats.sem(nex_data, axis=0, nan_policy='omit')
    m_ctrl = np.nanmean(ctrl_data, axis=0)
    s_ctrl = stats.sem(ctrl_data, axis=0, nan_policy='omit')
    
    # Statistical testing at each time point per behavior
    print("  Running statistical tests...")
    p_raw = np.full((n_beh, n_time), np.nan)
    
    for beh_idx in behavior_map.values():
        for t_idx in range(n_time):
            nex_vals = nex_data[:, beh_idx, t_idx]
            ctrl_vals = ctrl_data[:, beh_idx, t_idx]
            nex_vals = nex_vals[~np.isnan(nex_vals)]
            ctrl_vals = ctrl_vals[~np.isnan(ctrl_vals)]
            
            if len(nex_vals) >= 2 and len(ctrl_vals) >= 2:
                _, p = stats.ttest_ind(nex_vals, ctrl_vals, equal_var=False)
                p_raw[beh_idx, t_idx] = p
    
    # FDR correction per behavior (across time points)
    p_adj = np.full_like(p_raw, np.nan)
    for beh_idx in behavior_map.values():
        valid = ~np.isnan(p_raw[beh_idx, :])
        if np.sum(valid) > 1:
            _, _, adj = fdr_bh(p_raw[beh_idx, valid].copy())
            p_adj[beh_idx, valid] = adj
        else:
            p_adj[beh_idx, :] = p_raw[beh_idx, :]
    
    # Create subplot grid
    n_rows = int(np.ceil(np.sqrt(n_beh)))
    n_cols = int(np.ceil(n_beh / n_rows))
    
    print(f"  Generating trend plot ({n_rows}x{n_cols} grid)...")
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(10*n_cols, 4.2*n_rows), 
                             facecolor='white', constrained_layout=True)
    
    if n_beh == 1:
        axes = np.array([axes])
    axes = axes.flatten()
    
    time_centers = (time_min[:-1] + time_min[1:]) / 2
    
    for label, beh_idx in behavior_map.items():
        if beh_idx >= len(axes):
            break
        ax = axes[beh_idx]
        ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.5)
        ax.set_axisbelow(True)
        
        # Plot NEX group
        ax.plot(time_centers, m_nex[beh_idx, :], '-', color=color_nex, 
               linewidth=2.2, label='NEX', zorder=3)
        ax.fill_between(time_centers, 
                       np.maximum(0, m_nex[beh_idx, :] - s_nex[beh_idx, :]),
                       m_nex[beh_idx, :] + s_nex[beh_idx, :],
                       color=color_nex, alpha=0.15, edgecolor='none', zorder=2, label='_nolegend_')
        
        # Plot CTRL group
        ax.plot(time_centers, m_ctrl[beh_idx, :], '-', color=color_ctrl, 
               linewidth=2.2, label='CTRL', zorder=3)
        ax.fill_between(time_centers, 
                       np.maximum(0, m_ctrl[beh_idx, :] - s_ctrl[beh_idx, :]),
                       m_ctrl[beh_idx, :] + s_ctrl[beh_idx, :],
                       color=color_ctrl, alpha=0.15, edgecolor='none', zorder=2, label='_nolegend_')
        
        # Add significance markers (stars)
        sig_mask = (p_adj[beh_idx, :] < 0.05) & ~np.isnan(p_adj[beh_idx, :])
        sig_idx = np.where(sig_mask)[0]
        
        for si in sig_idx:
            y_max = max(m_nex[beh_idx, si] + s_nex[beh_idx, si], 
                       m_ctrl[beh_idx, si] + s_ctrl[beh_idx, si])
            if np.isfinite(y_max) and y_max > 0:
                ax.plot(time_centers[si], y_max, '*', color='black', 
                       markersize=16, markerfacecolor='black', zorder=4)
        
        # Labels and formatting
        ax.set_xlabel('Time (sec)', fontsize=9)
        ax.set_ylabel('Duration (sec)', fontsize=9)
        ax.set_title(label, fontsize=10, fontweight='bold', pad=8)
        
        # Dynamic y-limit
        max_val = np.max([m_nex[beh_idx, :] + s_nex[beh_idx, :], 
                         m_ctrl[beh_idx, :] + s_ctrl[beh_idx, :]])
        y_max = max(max_val * 1.15, 1) if np.isfinite(max_val) and max_val > 0 else 10
        ax.set_ylim([0, y_max])
        ax.set_xlim([0, 600])
        
        # Legend
        if len(sig_idx) > 0:
            ax.legend(['NEX', 'CTRL', '★ p<0.05'], loc='best', fontsize=7, 
                     frameon=True, edgecolor='lightgray')
        else:
            ax.legend(['NEX', 'CTRL'], loc='best', fontsize=7, 
                     frameon=True, edgecolor='lightgray')
    
    # Hide unused subplots
    for i in range(n_beh, len(axes)):
        axes[i].set_visible(False)
    
    fig.suptitle('Behavior Trends Over Time', fontsize=15, fontweight='bold', y=1.01)
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"  ✓ Saved: {output_path}")
    
    plt.show()
    
    stats_summary = {
        'time_min': time_centers,
        'p_raw': p_raw, 'p_adj': p_adj,
        'nex_mean': m_nex, 'nex_sem': s_nex, 'nex_n': len(nex_data),
        'ctrl_mean': m_ctrl, 'ctrl_sem': s_ctrl, 'ctrl_n': len(ctrl_data)
    }
    
    return fig, axes, stats_summary


def plot_cumulative_figure(nex_files: List[str], ctrl_files: List[str], 
                           beh_map: Dict[str, int], output_path: Optional[str] = None,
                           cutoff: Optional[int] = None, frame_to_sec: float = 1/30,
                           bin_size_min: float = 5.0):
    """
    Plot 3: Cumulative plot showing accumulated behavior duration over time.
    
    Matches MATLAB reference:
    - Cumulative sum of behavior durations
    - Cumulative error propagation: sqrt(cumsum(std²))
    - Significance testing on cumulative values
    """
    print("  Computing cumulative time-series data...")
    
    color_nex = [0.2, 0.4, 0.6]
    color_ctrl = [0.9, 0.6, 0.1]
    
    behavior_map = beh_map
    
    n_beh = len(behavior_map)

    if n_beh == 0:
        print("  Warning: No behavior labels provided")
        return None
    
    time_min = np.arange(0, 720 + bin_size_min/2, bin_size_min)
    n_time = len(time_min) - 1
    
    # Get binned time series
    nex_data = _aggregate_group_time_series(nex_files, behavior_map, time_min, cutoff, frame_to_sec)
    ctrl_data = _aggregate_group_time_series(ctrl_files, behavior_map, time_min, cutoff, frame_to_sec)
    
    if nex_data.size == 0 or ctrl_data.size == 0:
        print("  Warning: Insufficient data for cumulative plot")
        return None
    
    # Cumulative sums
    nex_cum = np.cumsum(nex_data, axis=2)  # (n_files, n_beh, n_time)
    ctrl_cum = np.cumsum(ctrl_data, axis=2)
    
    # Cumulative SEM: sqrt of cumsum of squared SEMs (error propagation)
    nex_sem = stats.sem(nex_data, axis=0, nan_policy='omit')
    ctrl_sem = stats.sem(ctrl_data, axis=0, nan_policy='omit')
    nex_cum_sem = np.sqrt(np.cumsum(nex_sem**2, axis=1))
    ctrl_cum_sem = np.sqrt(np.cumsum(ctrl_sem**2, axis=1))
    
    # Means of cumulative
    m_nex_cum = np.nanmean(nex_cum, axis=0)
    m_ctrl_cum = np.nanmean(ctrl_cum, axis=0)
 
    # Statistical testing on cumulative values
    print("  Running statistical tests on cumulative data...")
    p_raw = np.full((n_beh, n_time), np.nan)
    
    for beh_idx in range(n_beh):
        for t_idx in range(n_time):
            nex_vals = nex_cum[:, beh_idx, t_idx]
            ctrl_vals = ctrl_cum[:, beh_idx, t_idx]
            nex_vals = nex_vals[~np.isnan(nex_vals)]
            ctrl_vals = ctrl_vals[~np.isnan(ctrl_vals)]
            
            if len(nex_vals) >= 2 and len(ctrl_vals) >= 2:
                _, p = stats.ttest_ind(nex_vals, ctrl_vals, equal_var=False)
                p_raw[beh_idx, t_idx] = p
    
    # FDR correction
    p_adj = np.full_like(p_raw, np.nan)
    for beh_idx in range(n_beh):
        valid = ~np.isnan(p_raw[beh_idx, :])
        if np.sum(valid) > 1:
            _, _, adj = fdr_bh(p_raw[beh_idx, valid].copy())
            p_adj[beh_idx, valid] = adj
    
    # Create plot
    n_rows = int(np.ceil(np.sqrt(n_beh)))
    n_cols = int(np.ceil(n_beh / n_rows))
    
    print(f"  Generating cumulative plot ({n_rows}x{n_cols} grid)...")
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(10*n_cols, 4.2*n_rows), 
                             facecolor='white', constrained_layout=True)
    
    if n_beh == 1:
        axes = np.array([axes])
    axes = axes.flatten()
    
    time_centers = (time_min[:-1] + time_min[1:]) / 2
    
    for label, beh_idx in behavior_map.items():
        if beh_idx >= len(axes):
            break
        ax = axes[beh_idx]
        ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.5)
        ax.set_axisbelow(True)
        
        # Plot NEX cumulative
        ax.plot(time_centers, m_nex_cum[beh_idx, :], '-', color=color_nex, 
               linewidth=2.2, label='NEX', zorder=3)
        ax.fill_between(time_centers,
                       np.maximum(0, m_nex_cum[beh_idx, :] - nex_cum_sem[beh_idx, :]),
                       m_nex_cum[beh_idx, :] + nex_cum_sem[beh_idx, :],
                       color=color_nex, alpha=0.15, edgecolor='none', zorder=2, label='_nolegend_')
        
        # Plot CTRL cumulative
        ax.plot(time_centers, m_ctrl_cum[beh_idx, :], '-', color=color_ctrl, 
               linewidth=2.2, label='CTRL', zorder=3)
        ax.fill_between(time_centers,
                       np.maximum(0, m_ctrl_cum[beh_idx, :] - ctrl_cum_sem[beh_idx, :]),
                       m_ctrl_cum[beh_idx, :] + ctrl_cum_sem[beh_idx, :],
                       color=color_ctrl, alpha=0.15, edgecolor='none', zorder=2, label='_nolegend_')
        
        # Significance markers
        sig_mask = (p_adj[beh_idx, :] < 0.05) & ~np.isnan(p_adj[beh_idx, :])
        sig_idx = np.where(sig_mask)[0]
        
        for si in sig_idx:
            y_max = max(m_nex_cum[beh_idx, si] + nex_cum_sem[beh_idx, si], 
                       m_ctrl_cum[beh_idx, si] + ctrl_cum_sem[beh_idx, si])
            if np.isfinite(y_max) and y_max > 0:
                ax.plot(time_centers[si], y_max, '*', color='black', 
                       markersize=16, markerfacecolor='black', zorder=4)
        
        # Formatting
        ax.set_xlabel('Time (sec)', fontsize=9)
        ax.set_ylabel('Cumulative Duration (sec)', fontsize=9)
        ax.set_title(label, fontsize=10, fontweight='bold', pad=8)
        
        max_val = np.max([m_nex_cum[beh_idx, :] + nex_cum_sem[beh_idx, :], 
                         m_ctrl_cum[beh_idx, :] + ctrl_cum_sem[beh_idx, :]])
        y_max = max(max_val * 1.05, 1) if np.isfinite(max_val) and max_val > 0 else 10
        ax.set_ylim([0, y_max])
        ax.set_xlim([0, 600])
        
        if len(sig_idx) > 0:
            ax.legend(['NEX', 'CTRL', '★ p<0.05'], loc='best', fontsize=7, 
                     frameon=True, edgecolor='lightgray')
        else:
            ax.legend(['NEX', 'CTRL'], loc='best', fontsize=7, 
                     frameon=True, edgecolor='lightgray')
    
    for i in range(n_beh, len(axes)):
        axes[i].set_visible(False)
    
    fig.suptitle('Cumulative Behavior Duration', fontsize=15, fontweight='bold', y=1.01)
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"  ✓ Saved: {output_path}")
    
    plt.show()
    
    stats_summary = {
        'time_min': time_centers,
        'p_raw': p_raw, 'p_adj': p_adj,
        'nex_cum_mean': m_nex_cum, 'nex_cum_sem': nex_cum_sem,
        'ctrl_cum_mean': m_ctrl_cum, 'ctrl_cum_sem': ctrl_cum_sem
    }
    
    return fig, axes, stats_summary


def bavis_workflow(root_path: str, output_dir: Optional[str] = None, 
                   cutoff: Optional[int] = None, fps: int=10, 
                   output_format: str = 'png'):

    frame_to_sec = 1 / fps
    print(f"\n{'='*60}")
    print(f"BAVIS Workflow: Behavioral Annotation Visualization")
    print(f"{'='*60}\n")

    if output_dir is None:
        output_dir = root_path
    
    # Create output directory if needed
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        print(f"Output directory: {output_dir}\n")
    
    # Step 1: Find annotation files
    print("Step 1: Scanning for annotation files...")
    nex_files, ctrl_files = find_bannotator_labels(root_path)
    print(f"  ✓ Found {len(nex_files)} NEX files")
    print(f"  ✓ Found {len(ctrl_files)} CTRL files\n")

    if not nex_files and not ctrl_files:
        print("ERROR: No annotation files found! Check root_path.")
        return
    
    # Step 2: Extract behavior labels
    for f in nex_files + ctrl_files:
        _, bmap = annot_to_array(f, cutoff)
    
    # Step 3: Generate Plot 1 - Grouped Bar
    print("Step 3: Generating Plot 1 - Grouped Bar Chart")
    bar_path = os.path.join(output_dir, f'plot1_behavior_duration.{output_format}')
    bar_results = plot_grouped_bar(nex_files, ctrl_files, output_path=bar_path, 
                                   cutoff=cutoff, frame_to_sec=frame_to_sec)
    print()
    
    # Step 4: Generate Plot 2 - Trend
    print("Step 4: Generating Plot 2 - Trend Over Time")
    trend_path = os.path.join(output_dir, f'plot2_behavior_trends.{output_format}')
    trend_results = plot_trend_figure(nex_files, ctrl_files, bmap, 
                                      output_path=trend_path, cutoff=cutoff, 
                                      frame_to_sec=frame_to_sec, bin_size_min=5.0)
    print()
    
    # Step 5: Generate Plot 3 - Cumulative
    print("Step 5: Generating Plot 3 - Cumulative Duration")
    cum_path = os.path.join(output_dir, f'plot3_behavior_cumulative.{output_format}')
    cum_results = plot_cumulative_figure(nex_files, ctrl_files, bmap, 
                                         output_path=cum_path, cutoff=cutoff, 
                                         frame_to_sec=frame_to_sec, bin_size_min=5.0)
    print()
    
    # Summary
    print(f"{'='*60}")
    print("Workflow Complete!")
    print(f"{'='*60}")

    print(f"Plots saved to: {output_dir}")
    print("  • plot1_behavior_duration.png")
    print("  • plot2_behavior_trends.png") 
    print("  • plot3_behavior_cumulative.png")
    print(f"{'='*60}\n")
    
    return {
        'bar_plot': bar_results,
        'trend_plot': trend_results,
        'cumulative_plot': cum_results,
        'behavior_labels': bmap,
        'nex_files': nex_files,
        'ctrl_files': ctrl_files
    }


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    bavis_workflow(root_path=r"E:\CLP\20260413 free social test mannul mark", fps=10, output_format='png')