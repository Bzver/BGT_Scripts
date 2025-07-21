import os
import pandas as pd

#################   W   ##################   I   ##################   P   ##################   

def asoid_preprocess(pose_file, annot_file, inst_count, fps):
    df_inst_list, df_frame, header = parse_dlc_prediction_csv(pose_file, inst_count)
    df_pose = df_frame.copy()
    indices_to_remove = set()
    for df in df_inst_list:
        consecutive_indices = get_nan_frame_for_inst(df)
        df_interpol, indices_killer = smash_or_pass_consecutive_nan(df, consecutive_indices)
        df_pose = pd.concat([df_pose, df_interpol], axis=1)
        indices_to_remove.update(indices_killer)
    df_pose = df_pose.drop(indices_to_remove)
    processed_annot_path = remove_corresponding_annotation_idx(annot_file, indices_to_remove, fps)
    processed_pose_path = save_processed_pose(df_pose, pose_file, header)
    print(f"ASOID social preprocessing completed successfully.")
    print(f"Processed annotation file saved to: {processed_annot_path}")
    print(f"Processed pose file saved to: {processed_pose_path}")

def parse_dlc_prediction_csv(csv_path, inst_count):
    df_get_header = pd.read_csv(csv_path, header=None, low_memory=False)
    header = df_get_header.iloc[0:4,:]
    df = pd.read_csv(csv_path, header=[1, 2, 3])
    df.columns = ['_'.join(col).strip() for col in df.columns.values]
    header.columns = df.columns
    num_frames, num_cols = df.shape
    df_frame = df.iloc[:,0]
    df_inst_list = []
    num_cols_per_inst = (num_cols - 1) // inst_count
    for i in range(inst_count):
        df_inst = df.iloc[:,i*num_cols_per_inst+1:(i+1)*num_cols_per_inst+1]
        df_inst_list.append(df_inst)
    return df_inst_list, df_frame, header

def get_nan_frame_for_inst(df):
    nan_rows_mask = df.isna().all(axis=1)
    nan_rows_idx = df[nan_rows_mask].index.tolist()
    if not nan_rows_idx:
        return []
    consecutive_indices = []
    current_consecutive_block = [nan_rows_idx[0]]

    for i in range(1, len(nan_rows_idx)):
        if nan_rows_idx[i] == nan_rows_idx[i-1] + 1:
            current_consecutive_block.append(nan_rows_idx[i])
        else:
            consecutive_indices.append(current_consecutive_block)
            current_consecutive_block = [nan_rows_idx[i]]
    consecutive_indices.append(current_consecutive_block) # Add the last block
    return consecutive_indices

def smash_or_pass_consecutive_nan(df, consecutive_indices):
    """Determine whether to interpolate the nan frame or remove it"""
    indices_to_remove = set()
    for block in consecutive_indices:
        if len(block) <= 20:
            start_idx = block[0]
            end_idx = block[-1]
            df.loc[start_idx:end_idx] = df.loc[start_idx:end_idx].interpolate(method='linear', limit_direction='both')
        else:
            indices_to_remove.update([idx for idx in block])
    return df, list(indices_to_remove)

def remove_corresponding_annotation_idx(annot_file, indices_to_remove, fps):
    df = pd.read_csv(annot_file, header=[0])
    df = df.drop(indices_to_remove)
    base, ext = os.path.splitext(annot_file)
    output_path = f"{base}_processed{ext}"
    df.to_csv(output_path, index=False)
    return output_path

def save_processed_pose(df_pose, pose_file, header):
    base, ext = os.path.splitext(pose_file)
    output_path = f"{base}_processed{ext}"
    df_pose = pd.concat([header, df_pose], axis=0)
    df_pose.to_csv(output_path, index=False, header=None)
    return output_path

if __name__ == "__main__":
    folder = "D:/Project/DLC-Models/NTD/videos/jobs/sdaawa"
    pose_file_name = "2-20250626C1-first3h-SDLC_HrnetW32_bezver-SD-20250605M-cam52025-06-26shuffle1_detector_090_snapshot_080_el_tr_track_refiner_modified_4.csv"
    annot_file_name = "2-20250626_annot_R.csv"

    pose_file = os.path.join(folder, pose_file_name)
    annot_file = os.path.join(folder, annot_file_name)

    inst_count, fps = 2, 10

    asoid_preprocess(pose_file, annot_file, inst_count, fps)