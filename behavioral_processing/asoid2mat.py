import os
import pandas as pd
import scipy.io as sio

def csvs_to_mat_annotation(folder:str, dom_id:str, *csv_names: str):
    list_df = []
    for csv in csv_names:
        csv_filepath = os.path.join(folder, csv)
        df = csv_loader(csv_filepath)
        if dom_id in csv:
            df = prefix_dominance_adder(df, dom=True)
        else:
            df = prefix_dominance_adder(df)
        list_df.append(df)

    behavioral_dict, annotation = behavior_sorter(list_df)
    if behavioral_dict is None or annotation is None:
        return
    
    mat_filepath = csv_filepath.replace("D.csv", ".mat").replace("S.csv", ".mat")
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

def behavior_sorter(list_df:list):
    try:
        df_combined = pd.concat(list_df, axis=1)
        df_combined = df_combined.fillna(0.0)

        behavioral_dict = {"other": 0}
        column_list = df_combined.columns

        for i in range(len(column_list)):
            behavioral_dict[f"{column_list[i]}"] = i + 1

        annotation = pd.Series(0.0, index=df_combined.index)
        for col in column_list:
            annotation += df_combined[col] * behavioral_dict[col]

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
    except Exception as e:
        print(f"Failed to save {mat_filepath}, Exception: {e}")

if __name__ == "__main__":
    folder = "D:/Project/A-SOID/250720-Social/videos"
    csv_dom = "20250626C1-first3h-D.csv"
    csv_sub = "20250626C1-first3h-S.csv"
    dom_id = "-D."
    csvs_to_mat_annotation(folder, dom_id, csv_dom, csv_sub)