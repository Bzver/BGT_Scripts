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

def diff_between_sniff_and_anogenital(df_pose, df_pred):
    """
    For frames labeled as 'initiative', classify into 'init_sniff' or 'init_anogenital'
    based on relative nose-to-tail distance.

    Uses:
        - Mouse 1's nose (initiator) position
        - Mouse 0's tail base (target)
        - Average body length of mouse 0 (nose to tail base)

    Adds:
        - 'init_sniff'
        - 'init_anogenital' columns to df_pred
    """
    INIT_THRESHOLD_FACTOR = 0.25  # Within 1/4 of avg body length → anogenital

    if "initiative" not in df_pred.columns:
        print("Warning: 'initiative' column not found. Skipping sniff vs anogenital classification.")
        return

    try: # Extract coordinates from DLC-style multi-index: ['instance']['bodypart']['x' or 'y']
        nose0_x = df_pose['1']['Snout']['x'].astype(float)
        nose0_y = df_pose['1']['Snout']['y'].astype(float)
        tail0_x = df_pose['1']['Tail(base)']['x'].astype(float)
        tail0_y = df_pose['1']['Tail(base)']['y'].astype(float)

        nose1_x = df_pose['2']['Snout']['x'].astype(float)
        nose1_y = df_pose['2']['Snout']['y'].astype(float)

    except KeyError as e:
        print(f"Pose data missing required keys: {e}")
        return

    body_lengths = np.sqrt((nose0_x - tail0_x)**2 + (nose0_y - tail0_y)**2)
    avg_body_length = body_lengths.mean()
    threshold = INIT_THRESHOLD_FACTOR * avg_body_length

    # Distance from mouse1's nose to mouse0's tail base
    dist_to_tail = np.sqrt((nose1_x - tail0_x)**2 + (nose1_y - tail0_y)**2)

    # Initialize new columns
    df_pred["init_sniff"] = 0
    df_pred["init_anogenital"] = 0

    # Only process frames where 'initiative' == 1
    initiative_frames = df_pred.index[df_pred["initiative"] == 1].tolist()

    for idx in initiative_frames:
        if dist_to_tail[idx] <= threshold:
            df_pred.loc[idx, "init_anogenital"] = 1
            df_pred.loc[idx, "init_sniff"] = 0
        else:
            df_pred.loc[idx, "init_sniff"] = 1
            df_pred.loc[idx, "init_anogenital"] = 0

    print(f"Classified {len(initiative_frames)} 'initiative' frames into sniff/anogenital.")
    
if __name__ == "__main__":
    folder = "D:/Project/A-SOID/250720-Social/videos"
    for file in os.listdir(folder):
        if "-first3h-D.csv" in file or "-first3h-S.csv" in file:
            filepath = os.path.join(folder, file)
            asoid_post_process(filepath, "update_idle", "update_social")