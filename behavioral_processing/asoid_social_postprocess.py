import os
import pandas as pd

def asoid_post_process(pred_filepath):
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

    # Ensure lengths match
    if len(df_pose) != len(df_pred):
        print(f"Warning: Length mismatch! df_pose: {len(df_pose)}, df_pred: {len(df_pred)}")
        # Truncate to the shorter one (usually df_pose is longer due to padding)
        min_len = min(len(df_pose), len(df_pred))
        df_pose = df_pose.iloc[:min_len]
        df_pred = df_pred.iloc[:min_len].copy()
    else:
        df_pred = df_pred.copy()  # Safe copy for modifications

    indices_for_other = df_pose.index[df_pose.isin([99999]).any(axis=1)].tolist()

    df_pred["idle"] = 0
    df_pred["idle"] = df_pred["other"]

    if indices_for_other:
        df_pred.loc[indices_for_other, "other"] = 1
        df_pred.loc[indices_for_other, "idle"] = 0

    output_path = os.path.join(folder, f"{pred_filename_no_ext}_ppcs.csv")

    df_pred.to_csv(output_path, index=False)
    print(f"Successfully post processed {pred_filename_no_ext}.")

if __name__ == "__main__":
    folder = "D:/Project/A-SOID/250720-Social/videos"
    for file in os.listdir(folder):
        if "-first3h-D.csv" in file or "-first3h-S.csv" in file:
            filepath = os.path.join(folder, file)
            asoid_post_process(filepath)