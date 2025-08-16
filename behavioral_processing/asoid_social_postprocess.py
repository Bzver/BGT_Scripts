import os
import numpy as np
import pandas as pd

def asoid_post_process(pred_filepath, *args):
    """
    Post-process prediction CSV based on pose data and optional behavioral logic.

    Args:
        pred_filepath (str): Path to the prediction CSV file.
        *args (str): Any number of operations to apply. Supported: 
                     'update_idle', 'update_social'
    """
    folder = os.path.dirname(pred_filepath)
    pred_filename_no_ext = os.path.basename(pred_filepath).split(".csv")[0]
    for file in os.listdir(folder):
        if pred_filename_no_ext in file and "_processed.csv" in file:
            pose_filepath = os.path.join(folder, file)
            break
    
    if pose_filepath is None:
        print(f"Warning: No matching _processed.csv file found for {pred_filepath}")
        return

    df_pred = pd.read_csv(pred_filepath, header=0)
    df_pose = pd.read_csv(pose_filepath, header=[0,1,2])

    df_pose, df_pred = check_df_length(df_pose, df_pred)

    # Apply all requested operations
    valid_ops = {
        "update_idle": diff_between_other_and_idle,
        "update_social": diff_between_sniff_and_anogenital,
    }
    
    for op in args:
        if op in valid_ops:
            print(f"Running '{op}'...")
            valid_ops[op](df_pose, df_pred)
        else:
            print(f"Warning: Unknown operation '{op}'. Skipping. "
                  f"Valid options: {list(valid_ops.keys())}")
    output_path = os.path.join(folder, f"{pred_filename_no_ext}_ppcs.csv")

    df_pred.to_csv(output_path, index=False)
    print(f"Successfully post processed {pred_filename_no_ext}.")

def check_df_length(df_pose, df_pred):
    """Adjusts the lengths of df_pose and df_pred to match by truncating to the shorter length."""
    if len(df_pose) != len(df_pred):
        print(f"Warning: Length mismatch! df_pose: {len(df_pose)}, df_pred: {len(df_pred)}")
        min_len = min(len(df_pose), len(df_pred))
        df_pose = df_pose.iloc[:min_len]
        df_pred = df_pred.iloc[:min_len].copy()
    else:
        print("Pose and prediction data lengths match.")
        df_pred = df_pred.copy()

    return df_pose, df_pred

def diff_between_other_and_idle(df_pose, df_pred):
    """
    Adjusts 'other' and 'idle' behavior labels based on missing pose data (marked as 99999).
    
    Rules:
        - If a frame has any pose value == 99999 (missing), it should be labeled as 'other', not 'idle'.
        - Adds an 'idle' column if not present, initialized to the value of 'other'.
        - Then, for frames with missing pose, sets 'other' = 1 and 'idle' = 0.
    
    Parameters:
        df_pose (pd.DataFrame): Pose data (with 99999 indicating missing detection).
        df_pred (pd.DataFrame): Prediction DataFrame (will be modified in place).
    """
    indices_for_other = df_pose.index[df_pose.isin([99999]).any(axis=1)].tolist()

    if "idle" in df_pred.columns:
        print("'idle' column already exists. Updating values based on missing pose data.")
    else:
        print("Adding 'idle' column initialized to values of 'other'.")
        df_pred["idle"] = df_pred["other"].copy()

    if indices_for_other:
        df_pred.loc[indices_for_other, "other"] = 1
        df_pred.loc[indices_for_other, "idle"] = 0

def diff_between_sniff_and_anogenital(df_pose, df_pred, min_pow_length=105):
    """
    Classifies continuous 'initiative' segments as 'sniff', 'anogenital', or
    'mixed' (POW exchange) based on anogenital percentage.

    For 'mixed' segments, applies a post-processing rule to clean up short
    consecutive blocks of a minority classification.
    
    Args:
        df_pose (pd.DataFrame): DataFrame with pose coordinates.
        df_pred (pd.DataFrame): DataFrame with 'initiative' predictions.
        min_pow_length (int): The minimum length for a block to be considered stable and not "exchanged".
    """
    # Define thresholds
    INIT_THRESHOLD_FACTOR = 0.25
    ANOGENITAL_PERCENT_HIGH = 80
    ANOGENITAL_PERCENT_LOW = 20

    # Ensure 'initiative' column exists
    if "initiative" not in df_pred.columns or not df_pred["initiative"].any():
        print("Warning: 'initiative' column not found or no initiative frames. Skipping classification.")
        return

    try:
        # Extract coordinates
        nose0_x = df_pose[('1', 'Snout', 'x')].astype(float)
        nose0_y = df_pose[('1', 'Snout', 'y')].astype(float)
        tail0_x = df_pose[('1', 'Tail(base)', 'x')].astype(float)
        tail0_y = df_pose[('1', 'Tail(base)', 'y')].astype(float)
        nose1_x = df_pose[('2', 'Snout', 'x')].astype(float)
        nose1_y = df_pose[('2', 'Snout', 'y')].astype(float)

    except KeyError as e:
        print(f"Pose data missing required keys: {e}")
        return

    # Calculate average body length and anogenital threshold
    body_lengths = np.sqrt((nose0_x - tail0_x)**2 + (nose0_y - tail0_y)**2)
    avg_body_length = body_lengths.mean()
    anogenital_threshold = INIT_THRESHOLD_FACTOR * avg_body_length

    # Calculate distance from mouse1's nose to mouse0's tail base
    dist_to_tail = np.sqrt((nose1_x - tail0_x)**2 + (nose1_y - tail0_y)**2)
    
    # Identify frames that satisfy the anogenital condition
    is_anogenital = dist_to_tail <= anogenital_threshold

    # Initialize new columns
    df_pred["init_sniff"] = 0
    df_pred["init_anogenital"] = 0

    # Find the start and end of continuous 'initiative' segments
    initiative_series = df_pred["initiative"]
    diff = initiative_series.diff().fillna(initiative_series).ne(0)
    segments = initiative_series.loc[diff].index.tolist()

    for i in range(len(segments)):
        start_idx = segments[i]
        end_idx = segments[i+1] - 1 if i+1 < len(segments) else df_pred.index[-1]
        
        if df_pred.loc[start_idx, "initiative"] == 1:
            segment_slice = slice(start_idx, end_idx)
            # Check the anogenital condition for the current segment
            anogenital_count = is_anogenital.loc[segment_slice].sum()
            total_frames = (end_idx - start_idx) + 1
            anogenital_percentage = (anogenital_count / total_frames) * 100

            # Apply classification rules
            if anogenital_percentage > ANOGENITAL_PERCENT_HIGH:
                df_pred.loc[segment_slice, "init_anogenital"] = 1
            elif anogenital_percentage < ANOGENITAL_PERCENT_LOW:
                df_pred.loc[segment_slice, "init_sniff"] = 1
            else: # "POW exchange" case
                sub_segment_classifications = pd.Series(0, index=df_pred.index)
                sub_segment_classifications.loc[is_anogenital[segment_slice].index] = is_anogenital[segment_slice].astype(int)
                
                # Identify continuous blocks of classifications within the mixed segment
                diff_sub = sub_segment_classifications.diff().fillna(sub_segment_classifications).ne(0)
                sub_segments_starts = sub_segment_classifications.loc[diff_sub].index.tolist()
                
                # Loop through these sub-segments
                for j in range(len(sub_segments_starts)):
                    sub_start = sub_segments_starts[j]
                    sub_end = sub_segments_starts[j+1] - 1 if j+1 < len(sub_segments_starts) else end_idx
                    
                    sub_segment_length = (sub_end - sub_start) + 1
                    
                    # If the sub-segment is too short, re-classify it.
                    if sub_segment_length < min_pow_length:
                        if j > 0 and (sub_segments_starts[j-1] - start_idx) > 0:
                            # Re-classify based on the previous segment's value
                            # This is a simple 'Majority Wins' exchange
                            prev_val = sub_segment_classifications.loc[sub_segments_starts[j-1]]
                            df_pred.loc[sub_start:sub_end, "init_anogenital"] = prev_val
                            df_pred.loc[sub_start:sub_end, "init_sniff"] = 1 - prev_val
                        elif j < len(sub_segments_starts) - 1:
                            # Re-classify based on the next segment's value
                            next_val = sub_segment_classifications.loc[sub_segments_starts[j+1]]
                            df_pred.loc[sub_start:sub_end, "init_anogenital"] = next_val
                            df_pred.loc[sub_start:sub_end, "init_sniff"] = 1 - next_val
                        else:
                            # Fallback: keep the original classification if no surrounding context exists
                            df_pred.loc[sub_start:sub_end, "init_anogenital"] = sub_segment_classifications.loc[sub_start]
                            df_pred.loc[sub_start:sub_end, "init_sniff"] = 1 - sub_segment_classifications.loc[sub_start]
                    else:
                        # Keep the original classification for long enough segments
                        is_anogenital_val = is_anogenital.loc[sub_start]
                        df_pred.loc[sub_start:sub_end, "init_anogenital"] = int(is_anogenital_val)
                        df_pred.loc[sub_start:sub_end, "init_sniff"] = int(not is_anogenital_val)

    df_pred.drop("initiative", axis=1, inplace=True)

if __name__ == "__main__":
    folder = "D:/Project/A-SOID/250720-Social/videos"
    for file in os.listdir(folder):
        if "-first3h-D.csv" in file or "-first3h-S.csv" in file:
            filepath = os.path.join(folder, file)
            asoid_post_process(filepath, "update_idle", "update_social")