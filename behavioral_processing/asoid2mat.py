import os
import pandas as pd
import scipy.io as sio

def csvs_to_mat_annotation(dom_csv_filepath:str, dom_id:str, sub_id:str):
    sub_csv_filepath = dom_csv_filepath.replace(dom_id, sub_id)

    if not os.path.isfile(sub_csv_filepath):
        print(f"Cannot find corresponding file for {dom_csv_filepath}.")
        return

    df_dom = csv_loader(dom_csv_filepath)
    df_sub = csv_loader(sub_csv_filepath)

    df_dom = prefix_dominance_adder(df_dom, True)
    df_sub = prefix_dominance_adder(df_sub, False)

    df_pair = [df_dom, df_sub]
    behavioral_dict, annotation = behavior_sorter(df_pair)
    
    if behavioral_dict is None or annotation is None:
        return
    
    mat_filepath = dom_csv_filepath.replace(f"{dom_id}csv", ".mat")
    save_to_mat(mat_filepath, behavioral_dict, annotation)

def csv_loader(csv_filepath: str):
    try:
        df = pd.read_csv(csv_filepath)
        return df
    except Exception as e:
        print(f"Failed to load {csv_filepath}, Exception: {e}.")
        return None
        
def prefix_dominance_adder(df:pd.DataFrame, dom=False):
    cols_to_drop = [col for col in ['time', 'other'] if col in df.columns]
    df = df.drop(columns=cols_to_drop)
    prefix = "dom_" if dom else "sub_"
    df = df.add_prefix(prefix)
    return df

def behavior_sorter(df_pair:list):
    try:
        df_combined = pd.concat(df_pair, axis=1)
        df_combined = df_combined.fillna(0.0)

        # Assign 1-based codes: 'other' = 1, behaviors start at 2
        behavioral_dict = {"other": 0}
        column_list = df_combined.columns

        for i in range(len(column_list)):
            behavioral_dict[f"{column_list[i]}"] = i + 1

        # Initialize annotation with 'other' (1) everywhere
        annotation = pd.Series(0.0, index=df_combined.index)

        # Overlay behavior codes where active
        for col in column_list:
            code = behavioral_dict[col]
            annotation[df_combined[col] != 0] = code

        return behavioral_dict, annotation

    except Exception as e:
        print(f"behavior_sorter exception: {e}")

def save_to_mat(mat_filepath, behavioral_dict, annotation):
    try:
        annotation_struct = {
            "streamID": 1,
            "annotation": annotation.values.reshape(-1, 1),
            "behaviors": behavioral_dict
        }
        mat_to_save = {"annotation": annotation_struct}
        sio.savemat(mat_filepath, mat_to_save)
        print(f"Successfully saved to {mat_filepath}")
    except Exception as e:
        print(f"Failed to save {mat_filepath}, Exception: {e}")

if __name__ == "__main__":
    folder = "D:/Project/A-SOID/250720-Social/videos"
    dom_id = "-D_ppcs."
    sub_id = "-S_ppcs."

    for file in os.listdir(folder):
        if dom_id in file:
            dom_csv_filepath = os.path.join(folder, file)
            csvs_to_mat_annotation(dom_csv_filepath, dom_id, sub_id)