import os
import json
import numpy as np
import pandas as pd
from collections import defaultdict
from typing import Dict, Tuple, Optional
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox

# =============================================================================
# CONFIGURATION (Updated)
# =============================================================================
class Config:
    """Centralized configuration for data processing"""
    SPEED_SMOOTHING_WINDOW = 5  # frames for speed smoothing
    SPEED_UNITS = 'body_lengths_per_second'  # 'pixel_per_second', 'body_lengths_per_second', or 'cm_per_second'
    
    # Speed bins in BL/s (biologically interpretable)
    # Based on literature: mice typically move 0-5 BL/s during social interaction
    SPEED_BINS_BL = [0, 0.5, 1.5, 3.0, float('inf')]  # BL/s
    
    # If you have physical calibration, override here
    PIXEL_TO_CM = None  # Set to actual value if known (e.g., 0.1)
    EXPECTED_MOUSE_BODY_LENGTH_CM = 9.5  # Adult C57BL/6 typical length (nose to tailbase)
    
    SPEED_BINNING = False  # Set True for discrete bins, False for continuous
    OUTPUT_FORMAT = 'npz'
    MIN_OVERLAP_FRAMES = 1000
    FPS = 10  # Confirm this matches your recording

# =============================================================================
# MAIN WORKFLOW
# =============================================================================
def aa2m_workflow(root_path: str, asoid_dir: str, pose_dir: str, output_dir: str):
    """
    Main processing workflow for HSMM data preparation.
    
    Args:
        root_path: BVT export JSON root folder
        asoid_dir: A-SOiD prediction CSV folder
        pose_dir: DeepLabCut pose tracking CSV folder
        output_dir: Output folder for processed HSMM-ready data
    """
    fpd = find_bvt_export_meta(root_path)
    os.makedirs(output_dir, exist_ok=True)
    
    processed_count = 0
    skipped_count = 0
    
    for id in fpd.keys():
        idd = fpd[id]
        print(f"\n--- Processing ID: {id} ---")

        if idd["dom"] is None or idd["sub"] is None:
            print(f"  ⊗ Missing dom/sub pair → skipping")
            skipped_count += 1
            continue
            
        dom_meta_path = idd["dom"]
        dom_asoid_pred = find_corresponding_asoid_pred(dom_meta_path, asoid_dir)
        if not dom_asoid_pred:
            print(f"  ⊗ No ASOID prediction found for DOM → skipping")
            skipped_count += 1
            continue

        sub_meta_path = idd["sub"]
        sub_asoid_pred = find_corresponding_asoid_pred(sub_meta_path, asoid_dir)
        if not sub_asoid_pred:
            print(f"  ⊗ No ASOID prediction found for SUB → skipping")
            skipped_count += 1
            continue
            
        # Find corresponding pose files for speed calculation
        dom_pose = find_corresponding_pose(dom_meta_path, pose_dir)
        sub_pose = find_corresponding_pose(sub_meta_path, pose_dir)

        # Process each side separately
        dom_data = process_side(dom_meta_path, dom_asoid_pred, dom_pose, side='dom')
        sub_data = process_side(sub_meta_path, sub_asoid_pred, sub_pose, side='sub')
        
        if dom_data is None or sub_data is None:
            print(f"  ⊗ Processing failed for one side → skipping")
            skipped_count += 1
            continue

        # Align frame counts (truncate to minimum overlap)
        min_len = min(len(dom_data['behavior']), len(sub_data['behavior']))
        if min_len < Config.MIN_OVERLAP_FRAMES:
            print(f"  ⊗ Insufficient overlap frames ({min_len}) → skipping")
            skipped_count += 1
            continue
            
        dom_data['behavior'] = dom_data['behavior'][:min_len]
        dom_data['female_speed'] = dom_data['female_speed'][:min_len]
        dom_data['male_speed'] = dom_data['male_speed'][:min_len]
        
        sub_data['behavior'] = sub_data['behavior'][:min_len]
        sub_data['female_speed'] = sub_data['female_speed'][:min_len]
        sub_data['male_speed'] = sub_data['male_speed'][:min_len]
        
        # Save as HSMM-ready npz file
        output_path = Path(output_dir) / f"{id}_hsmm_ready.npz"
        save_to_npz(output_path, id, dom_data, sub_data)
        print(f"  ✓ Successfully saved to {output_path}")
        processed_count += 1
    
    print(f"\n{'='*60}")
    print(f"Processing complete! | Processed: {processed_count} | Skipped: {skipped_count}")
    print(f"{'='*60}")


# =============================================================================
# SIDE PROCESSING
# =============================================================================
def process_side(meta_path: str, asoid_path: str, pose_path: Optional[str], side: str) -> Optional[Dict]:
    """
    Process a single side (dom or sub) and extract all features.
    
    Returns:
        Dictionary containing behavior array, speeds, and metadata
    """
    # Load behavior data
    behav_array, behav_dict, color_dict = remap_trunc_df(meta_path, asoid_path)
    
    # Load and calculate speed from pose data
    if pose_path:
        female_speed, male_speed, calib_factor = calculate_speeds_from_pose(pose_path, len(behav_array))
    else:
        print(f"  ⚠ No pose file found for {side} → using zero speeds")
        female_speed = np.zeros(len(behav_array))
        male_speed = np.zeros(len(behav_array))
    
    # Apply speed smoothing
    female_speed = smooth_speed(female_speed, Config.SPEED_SMOOTHING_WINDOW)
    male_speed = smooth_speed(male_speed, Config.SPEED_SMOOTHING_WINDOW)
    
    # Optional: bin speeds if configured
    if Config.SPEED_BINNING:
        female_speed = bin_speed(female_speed, Config.SPEED_BINS_BL)
        male_speed = bin_speed(male_speed, Config.SPEED_BINS_BL)
    
    return {
        'behavior': behav_array,
        'female_speed': female_speed,
        'male_speed': male_speed,
        'behav_map': behav_dict,
        'color_map': color_dict,
        'side': side,
        'n_frames': len(behav_array),
        'body_length_px': calib_factor, 
    }
    

def calculate_speeds_from_pose(pose_path: str, target_length: int, 
                                animal_id: str = None) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Calculate centroid speeds with automatic body-length calibration.
    
    Returns:
        Tuple of (female_speed, male_speed, pixel_to_body_length_ratio)
        Speed units depend on Config.SPEED_UNITS
    """
    df = pd.read_csv(pose_path, header=[0, 1, 2])  # DLC multi-index header
    
    # =========================================================================
    # Step 1: Extract body landmarks for length estimation
    # =========================================================================
    # Typical DLC output: (individual, bodypart, x/y/likelihood)
    # We need nose and tailbase for body length
    
    def get_landmarks(df, individual_name):
        """Extract nose and tailbase coordinates for an individual"""
        # Try to find the individual in the dataframe
        individuals = df.columns.get_level_values(0).unique()
        
        # Match individual (adjust naming based on your DLC output)
        matched_individual = None
        for ind in individuals:
            if individual_name.lower() in str(ind).lower():
                matched_individual = ind
                break
        
        if matched_individual is None:
            # Fallback: use first two individuals
            matched_individual = individuals[0] if 'female' in individual_name.lower() else individuals[1]
        
        # Extract coordinates
        nose_x = df[(matched_individual, 'Snout', 'x')]
        nose_y = df[(matched_individual, 'Snout', 'y')]
        tailbase_x = df[(matched_individual, 'Tail(base)', 'x')]
        tailbase_y = df[(matched_individual, 'Tail(base)', 'y')]
    
        return nose_x, nose_y, tailbase_x, tailbase_y
    
    # Get landmarks for both animals
    fem_nose_x, fem_nose_y, fem_tail_x, fem_tail_y = get_landmarks(df, '2')
    male_nose_x, male_nose_y, male_tail_x, male_tail_y = get_landmarks(df, '1')
    
    # =========================================================================
    # Step 2: Calculate body length (pixels)
    # =========================================================================
    def calc_body_length(nose_x, nose_y, tail_x, tail_y, individual_name):
        """Calculate median body length in pixels"""
        dx = tail_x - nose_x
        dy = tail_y - nose_y
        lengths = np.sqrt(dx**2 + dy**2)
        
        # Filter out low-likelihood frames if available
        try:
            likelihood = df[(individual_name, 'nose', 'likelihood')]
            lengths = lengths[likelihood > 0.8]
        except:
            pass
        
        # Remove outliers (too short or too long)
        lengths = lengths[(lengths > lengths.quantile(0.1)) & (lengths < lengths.quantile(0.9))]
        
        return np.median(lengths) if len(lengths) > 0 else None
    
    fem_body_length_px = calc_body_length(fem_nose_x, fem_nose_y, fem_tail_x, fem_tail_y, '2')
    male_body_length_px = calc_body_length(male_nose_x, male_nose_y, male_tail_x, male_tail_y, '1')
    
    # Use average if both available
    avg_body_length_px = np.nanmean([fem_body_length_px, male_body_length_px])
    
    if avg_body_length_px is None or np.isnan(avg_body_length_px) or avg_body_length_px < 10:
        print(f"  ⚠ Body length estimation failed for {animal_id}. Using default 50 pixels.")
        avg_body_length_px = 50.0  # Fallback
    
    print(f"  ℹ Estimated body length: {avg_body_length_px:.1f} pixels")
    
    # =========================================================================
    # Step 3: Calculate centroid positions and speeds
    # =========================================================================
    def get_centroid(df, individual_name):
        """Get centroid or calculate from landmarks"""
        individuals = df.columns.get_level_values(0).unique()
        matched_individual = None
        for ind in individuals:
            if individual_name.lower() in str(ind).lower():
                matched_individual = ind
                break
        
        if matched_individual is None:
            matched_individual = individuals[0] if 'female' in individual_name.lower() else individuals[1]
        
        try:
            cx = df[(matched_individual, 'spine_M', 'x')]
            cy = df[(matched_individual, 'spine_M', 'y')]
        except KeyError:
            # Calculate centroid from available body parts
            bodyparts = df.columns.get_level_values(1).unique()
            x_cols = [col for col in df.columns if col[0] == matched_individual and col[2] == 'x']
            y_cols = [col for col in df.columns if col[0] == matched_individual and col[2] == 'y']
            
            cx = df[x_cols].mean(axis=1)
            cy = df[y_cols].mean(axis=1)
        
        return cx, cy
    
    fem_cx, fem_cy = get_centroid(df, '2')
    male_cx, male_cy = get_centroid(df, '1')
    
    # Calculate speed (pixels/frame)
    fem_dx = fem_cx.diff().fillna(0)
    fem_dy = fem_cy.diff().fillna(0)
    female_speed_px_per_frame = np.sqrt(fem_dx**2 + fem_dy**2)
    
    male_dx = male_cx.diff().fillna(0)
    male_dy = male_cy.diff().fillna(0)
    male_speed_px_per_frame = np.sqrt(male_dx**2 + male_dy**2)
    
    # =========================================================================
    # Step 4: Convert to desired units
    # =========================================================================
    fps = Config.FPS
    
    if Config.SPEED_UNITS == 'pixel_per_second':
        female_speed = female_speed_px_per_frame.values * fps
        male_speed = male_speed_px_per_frame.values * fps
        calibration_factor = 1.0
        
    elif Config.SPEED_UNITS == 'body_lengths_per_second':
        # Convert: (px/frame) × (frame/s) ÷ (px/BL) = BL/s
        female_speed = (female_speed_px_per_frame.values * fps) / avg_body_length_px
        male_speed = (male_speed_px_per_frame.values * fps) / avg_body_length_px
        calibration_factor = avg_body_length_px
        print(f"  ℹ Speed units: Body Lengths/second (1 BL = {avg_body_length_px:.1f} px)")
        
    elif Config.SPEED_UNITS == 'cm_per_second':
        if Config.PIXEL_TO_CM is not None:
            # Use provided calibration
            female_speed = female_speed_px_per_frame.values * fps * Config.PIXEL_TO_CM
            male_speed = male_speed_px_per_frame.values * fps * Config.PIXEL_TO_CM
            calibration_factor = 1.0 / Config.PIXEL_TO_CM
        else:
            # Estimate from expected body length
            estimated_pixel_to_cm = avg_body_length_px / Config.EXPECTED_MOUSE_BODY_LENGTH_CM
            female_speed = female_speed_px_per_frame.values * fps * estimated_pixel_to_cm
            male_speed = male_speed_px_per_frame.values * fps * estimated_pixel_to_cm
            calibration_factor = 1.0 / estimated_pixel_to_cm
            print(f"  ℹ Estimated pixel_to_cm: {estimated_pixel_to_cm:.3f} (from body length)")
    
    # =========================================================================
    # Step 5: Handle length mismatch and smooth
    # =========================================================================
    if len(female_speed) > target_length:
        female_speed = female_speed[:target_length]
        male_speed = male_speed[:target_length]
    elif len(female_speed) < target_length:
        female_speed = np.pad(female_speed, (0, target_length - len(female_speed)), mode='edge')
        male_speed = np.pad(male_speed, (0, target_length - len(male_speed)), mode='edge')
    
    return female_speed, male_speed, calibration_factor


def smooth_speed(speed: np.ndarray, window: int = 5) -> np.ndarray:
    """Apply moving average smoothing to speed signal"""
    if window < 2:
        return speed
    kernel = np.ones(window) / window
    return np.convolve(speed, kernel, mode='same')


def bin_speed(speed: np.ndarray, bins: list) -> np.ndarray:
    """Discretize continuous speed into bins"""
    return np.digitize(speed, bins) - 1


# =============================================================================
# FILE I/O
# =============================================================================
def find_corresponding_asoid_pred(json_path: str, asoid_dir: str) -> Optional[str]:
    """Find matching A-SOiD prediction CSV"""
    json_name = os.path.basename(json_path)
    asoid_pred = os.path.join(asoid_dir, json_name.replace(".json", "_pred_annotated_iteration-0.csv"))
    if not os.path.isfile(asoid_pred):
        return None
    return asoid_pred


def find_corresponding_pose(json_path: str, pose_dir: str) -> Optional[str]:
    """Find matching DeepLabCut pose CSV"""
    json_name = os.path.basename(json_path)
    # Adjust pattern based on your DLC output naming
    pose_patterns = [
        json_name.replace(".json", "_pred.csv")
    ]
    
    for pattern in pose_patterns:
        pose_path = os.path.join(pose_dir, pattern.replace("*", ""))
        if os.path.isfile(pose_path):
            return pose_path
    
    # Fallback: find any CSV with matching date ID
    date_id = json_name[:4]
    for f in os.listdir(pose_dir):
        if f.startswith(date_id) and f.endswith('.csv'):
            return os.path.join(pose_dir, f)
    
    return None


def find_bvt_export_meta(root_path: str) -> Dict[str, Dict[str, str]]:
    """Find paired dom/sub JSON metadata files"""
    file_pair_dict = defaultdict(lambda: defaultdict(str))
    
    for root, _, files in os.walk(root_path):
        print(files)
        for f in files:
            if len(f) < 16:
                continue
            if not f[:4].isdigit():
                continue
            if f[5:8] not in ("dom", "sub"):
                continue
            if f[9:12] != "day":
                continue
            if not f[14].isdigit() or int(f[14]) < 0 or int(f[14]) > 4:
                continue
            if not f.endswith(".json"):
                continue

            date_id = f[:4]
            dom_status = f[5:8] == "dom"
            day_info = f[9:13]
            floor_info = "F" + f[14]
            unique_id = f"{date_id}{floor_info}{day_info}"

            if dom_status:
                file_pair_dict[unique_id]["dom"] = os.path.join(root, f)
            else:
                file_pair_dict[unique_id]["sub"] = os.path.join(root, f)

    return file_pair_dict


def remap_trunc_df(json_path: str, csv_path: str) -> Tuple[np.ndarray, Dict[str, int], Dict[str, str]]:
    """Remap behavior labels and create integer-encoded array"""
    
    with open(json_path) as f:
        meta = json.load(f)

    df = pd.read_csv(csv_path, sep=",")

    total_frames = meta["total_frames"]
    used_frames = meta["used_frames"]
    behav_map = meta["behav_map"]

    used_frames = np.array(used_frames, dtype=int)
    behav_dict = {}
    color_dict = {}

    behav_cols = ["in_cage"]
    behav_cols.extend(sorted([col for col in df.columns if col not in ("time", "other")]))

    other_color = behav_map.get("other", (None, "#A6A6A6"))[1] if "other" in behav_map else "#A6A6A6"

    extra_behav = []
    if len(behav_map.keys()) - 1 > len(behav_cols):
        extra_behav = [beh for beh in behav_map.keys() if beh not in behav_cols]

    behav_dict["other"] = 0
    color_dict["other"] = hex_to_rgb_triplet(other_color)
    
    behav_array = np.zeros(total_frames, dtype=int)
    
    for i, behav in enumerate(behav_cols):
        behav_dict[behav] = i + 1
        color = "#114514" if behav == "in_cage" else behav_map.get(behav, (None, "#808080"))[1]
        color_dict[behav] = hex_to_rgb_triplet(color)

        active_series = df["other"] if behav == "in_cage" else df[behav]
        active_mask = (active_series.values == 1)

        try:
            behav_array[active_mask] = i + 1
        except IndexError:
            if len(active_mask) == len(used_frames) - 1:
                active_mask = np.append([False], active_mask)
            min_len = min(len(active_mask), len(used_frames))
            active_mask = active_mask[:min_len]
            used_frames = used_frames[:min_len]
            active_original_frames = used_frames[active_mask].tolist()
            behav_array[active_original_frames] = i + 1
            next_i = i + 2

    if extra_behav:
        for j, behav in enumerate(extra_behav):
            behav_dict[behav] = next_i + j
            _, color = behav_map[behav]
            color_dict[behav] = hex_to_rgb_triplet(color)
    
    return behav_array, behav_dict, color_dict


def save_to_npz(output_path: Path, animal_id: str, dom_data: Dict, sub_data: Dict):
    """Save processed data with calibration metadata"""
    
    metadata = {
        'animal_id': animal_id,
        'dom_behav_map': json.dumps(dom_data['behav_map']),
        'sub_behav_map': json.dumps(sub_data['behav_map']),
        'dom_color_map': json.dumps(dom_data['color_map']),
        'sub_color_map': json.dumps(sub_data['color_map']),
        'n_frames': dom_data['n_frames'],
        'fps': Config.FPS,
        'speed_units': Config.SPEED_UNITS,
        'speed_binned': Config.SPEED_BINNING,
        'speed_bins': json.dumps(Config.SPEED_BINS_BL),
        'body_length_pixels': dom_data.get('body_length_px', np.nan),
        'pixel_to_cm_estimated': dom_data.get('pixel_to_cm', np.nan),
        'processing_date': pd.Timestamp.now().isoformat()
    }
    
    np.savez(
        output_path,
        dom_behavior=dom_data['behavior'],
        sub_behavior=sub_data['behavior'],
        dom_female_speed=dom_data['female_speed'],
        dom_male_speed=dom_data['male_speed'],
        sub_female_speed=sub_data['female_speed'],
        sub_male_speed=sub_data['male_speed'],
        **{k: np.array(v) for k, v in metadata.items()}
    )

def load_hsmm_data(npz_path: str) -> Dict:
    """Helper function to load HSMM-ready data downstream"""
    data = np.load(npz_path, allow_pickle=True)
    return {
        'animal_id': str(data['animal_id']),
        'dom_behavior': data['dom_behavior'],
        'sub_behavior': data['sub_behavior'],
        'dom_female_speed': data['dom_female_speed'],
        'dom_male_speed': data['dom_male_speed'],
        'sub_female_speed': data['sub_female_speed'],
        'sub_male_speed': data['sub_male_speed'],
        'behav_map': json.loads(str(data['dom_behav_map'])),
        'n_frames': int(data['n_frames']),
        'fps': int(data['fps'])
    }


# =============================================================================
# UTILITIES
# =============================================================================
def hex_to_rgb_triplet(hex_color: str) -> Tuple[float, float, float]:
    """Convert hex color to RGB triplet (0-1 range)"""
    return tuple(int(hex_color[i:i+2], 16)/255 for i in (1, 3, 5))


def lighten_rgb_triplet(rgb_triplet: Tuple[float, float, float], percentage: int = 20) -> Tuple[float, float, float]:
    """Lighten RGB color by percentage"""
    factor = 1 + percentage / 100
    return tuple(min(num * factor, 1) for num in rgb_triplet)


def darken_rgb_triplet(rgb_triplet: Tuple[float, float, float], percentage: int = 20) -> Tuple[float, float, float]:
    """Darken RGB color by percentage"""
    return lighten_rgb_triplet(rgb_triplet, -percentage)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main():
    tk.Tk().withdraw()

    print("="*60)
    print("HSMM Data Preparation Pipeline")
    print("="*60)

    print("\n1. Select the ROOT folder containing BVT export JSONs...")
    root_path = filedialog.askdirectory(title="Select BVT Export Root Folder")
    if not root_path:
        print("  ⊗ No root folder selected. Exiting.")
        return

    print("\n4. Select OUTPUT folder for processed HSMM-ready data...")
    output_dir = filedialog.askdirectory(title="Select Output Folder")
    if not output_dir:
        print("  ⊗ No output folder selected. Exiting.")
        return

    if not os.path.isdir(root_path):
        messagebox.showerror("Error", "Invalid folder selection.")
        return

    print(f"\n{'='*60}")
    print(f"Configuration:")
    print(f"  Root:     {root_path}")
    print(f"  ASOID:    {root_path}")
    print(f"  Pose:     {root_path}")
    print(f"  Output:   {output_dir}")
    print(f"  Speed bins: {Config.SPEED_BINNING}")
    print(f"{'='*60}\n")
    
    aa2m_workflow(root_path, root_path, root_path, output_dir)
    
    print("\n✓ All processing complete!")


if __name__ == "__main__":
    main()