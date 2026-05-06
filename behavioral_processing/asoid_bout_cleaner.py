
import math
import numpy as np
from sklearn.cluster import DBSCAN
from joblib import Parallel, delayed
from tqdm import tqdm
from typing import List, Tuple, Iterable


def custom_round(value):
    return math.floor(value + 0.5)

def array_to_iterable_runs(arr:np.ndarray) -> Iterable[Tuple[int, int, int]]:
    if len(arr) == 0:
        return zip([], [], [])
    change_points = np.where(arr[1:] != arr[:-1])[0] + 1 
    starts = np.concatenate(([0], change_points))
    ends = np.concatenate((change_points - 1, [len(arr) - 1]))
    values = arr[starts]
    return zip(starts, ends, values)

def split_by_neutral(seq: np.ndarray, neutral_ids: List[int]) -> List[Tuple[int, int]]:
    is_neutral = np.isin(seq, neutral_ids)
    boundaries = np.where(np.diff(is_neutral.astype(int)) != 0)[0] + 1
    segments = []
    start = 0
    for b in boundaries:
        if not is_neutral[start]:
            segments.append((start, b))
        start = b
    if start < len(seq) and not is_neutral[start]:
        segments.append((start, len(seq)))
    return segments

def process_segment(
    seq:np.ndarray,
    eps_frames: int = 5,
    min_cluster_size: int = 3,
    ) -> np.ndarray:

    n = len(seq)
    if n < 3:
        return seq
    
    wseq = seq.copy()
    
    counts = np.bincount(wseq)
    rare_vals = np.where(counts < 3)[0]
    
    for val in rare_vals:
        mask = wseq == val
        indices = np.where(mask)[0]
        for idx in indices:
            if idx > 0:
                wseq[idx] = wseq[idx-1]
            elif idx < n-1:
                wseq[idx] = wseq[idx+1]
                
    clusters = []
    unique_vals = np.unique(wseq)

    for val in unique_vals:
        indices = np.where(wseq == val)[0].reshape(-1, 1)
        clustering = DBSCAN(eps=eps_frames, min_samples=1).fit(indices)
        labels = clustering.labels_
        
        for lbl in set(labels):
            cluster_idx = indices[labels == lbl].flatten()
            size = len(cluster_idx)
            com = np.mean(cluster_idx)

            start = int(custom_round(com)) - size // 2
            end = int(custom_round(com)) + size // 2 - (1 if size % 2 == 0 else 0)
            if end >= n:
                delta = end + 1 - n
                start -= delta
                end -= delta
            if start < 0:
                end += start
                start = 0

            clusters.append({
                'val': val,
                'com': com,
                'size': size,
                'start': start,
                'end': end
            })
        
    clusters.sort(key=lambda x: x['size'])
    
    assigned = -np.ones(n, dtype=np.int8)
    reserved = []
    
    for c in clusters:
        if c['size'] < min_cluster_size:
            reserved.append(c)
            continue
        s, e = c['start'], c['end']
        if np.all(assigned[s:e+1] == -1):
            assigned[s:e+1] = c['val']
        elif assigned[s] != -1 and assigned[e] != -1:
            reserved.append(c)
        elif assigned[s] == -1:
            delta = e - np.where(assigned[s:e+1] != -1)[0][0] + 1
            if np.all(assigned[s-delta:e+1-delta] == -1) and s-delta > 0:
                assigned[s-delta:e+1-delta] = c['val']
            else:
                reserved.append(c)
        elif assigned[e] == -1:
            delta = np.where(assigned[s:e+1] != -1)[0][0] + 1
            if np.all(assigned[s+delta:e+1+delta] == -1) and e+delta < n:
                assigned[s+delta:e+1+delta] = c['val']
            else:
                reserved.append(c)
        else:
            reserved.append(c)

    reserved.sort(key=lambda x: x['com']) 
    reserved_vals = []

    for rc in reserved:
        reserved_vals.extend([rc['val']]*rc['size'])

    assigned[assigned==-1] = reserved_vals

    for start, end, val in array_to_iterable_runs(assigned):
        if start > 0 and val == assigned[start-1]:
            continue
        if end - start + 1 < min_cluster_size:
            if start > 0:
                assigned[start:end+1] = assigned[start-1]
            else:
                assigned[start:end+1] = assigned[end+2]

    return assigned

def refine_bouts_parallel(
    seq: np.ndarray,
    neutral_ids: List[int],
    eps_frames: int = 5,
    min_cluster_size: int = 3,
    n_jobs: int = -1
) -> np.ndarray:

    segments = split_by_neutral(seq, neutral_ids)
    
    if not segments:
        return seq.copy()
    
    def process_one(seg_bounds):
        start, end = seg_bounds
        segment = seq[start:end]
        refined = process_segment(segment, eps_frames, min_cluster_size)
        return start, end, refined
    
    results = Parallel(n_jobs=n_jobs, verbose=0)(
        delayed(process_one)(seg) for seg in tqdm(segments, total=len(segments), desc="Stitching Bouts")
    )

    refined_seq = seq.copy()
    for start, end, refined_segment in results:
        refined_seq[start:end] = refined_segment
    
    return refined_seq

if __name__ == "__main__":
    seq_input = "3333777667667624444422222676277678776676672222111111111122211223333"
    seq = np.array([int(c) for c in seq_input])
    aaa = refine_bouts_parallel(seq, [1])
    print(aaa)