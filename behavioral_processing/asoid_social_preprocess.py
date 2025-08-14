import os
import pandas as pd

def asoid_preprocess(pose_filepath, inst_count=2):
    df_inst_list, df_frame, header = parse_dlc_prediction_csv(pose_filepath, inst_count)
    df_pose = df_frame.copy()

    for df in df_inst_list:
        consecutive_indices = get_nan_frame_for_inst(df)
        df_interpol = smash_or_pass_consecutive_nan(df, consecutive_indices)
        df_pose = pd.concat([df_pose, df_interpol], axis=1)

    df_pose = ensure_no_df_nan(df_pose)

    processed_pose_filepath = save_processed_pose(df_pose, pose_filepath, header)
    print(f"ASOID social preprocessing completed successfully.")
    print(f"Processed pose file saved to: {processed_pose_filepath}")

def parse_dlc_prediction_csv(csv_path, inst_count):
    df_get_header = pd.read_csv(csv_path, header=None, low_memory=False)
    header = df_get_header.iloc[1:4,:] # Byebye scorer row
    df = pd.read_csv(csv_path, header=[1, 2, 3])
    df.columns = ['_'.join(col).strip() for col in df.columns.values]
    header.columns = df.columns
    num_cols = df.shape[1]
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
    """Determine whether to interpolate the nan frame or process it"""
    for block in consecutive_indices:
        if len(block) <= 20:
            start_idx = block[0]
            end_idx = block[-1]
            df.loc[start_idx-1:end_idx+1] = df.loc[start_idx-1:end_idx+1].interpolate(method='linear', limit_direction='both')
        else:
            df.loc[block, :] = 99999
    return df

def ensure_no_df_nan(df):
    # First interpolate, then ffill / bfill, at last check nan in file, if still any raise warning
    df_processed = df.interpolate(method='linear', limit_direction='both')
    df_processed = df_processed.ffill().bfill()
    if df_processed.isnull().any().any():
        print("Warning: NaN values still present in DataFrame after interpolation and fill operations.")
    return df_processed

def save_processed_pose(df_pose, pose_file, header):
    base, ext = os.path.splitext(pose_file)
    output_path = f"{base}_processed{ext}"
    df_pose = pd.concat([header, df_pose], axis=0)
    df_pose.to_csv(output_path, index=False, header=None)
    return output_path

if __name__ == "__main__":
    folder_list = [
        "D:/Project/A-SOID/Data/20250626",
        "D:/Project/A-SOID/Data/20250709",
        "D:/Project/A-SOID/Data/20250716"
    ]
    for folder in folder_list:
        print(folder)
        csv_list = [file for file in os.listdir(folder) if file.endswith(".csv")]

        for csv in csv_list:
            if "_processed" not in csv:
                csv_filepath = os.path.join(folder, csv)
                asoid_preprocess(csv_filepath)
