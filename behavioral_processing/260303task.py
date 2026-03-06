import os
import json
import scipy.io as sio

import numpy as np
import pandas as pd
from typing import Dict, Tuple, List


def onehot_to_mat_workflow(root_path:str, meta_path:str):
    mat_folder = os.path.join(root_path, "mat")
    os.makedirs(mat_folder, exist_ok=True)

    csv_list = []
    for f in os.listdir(root_path):
        if f.endswith(".csv"):
            csv_list.append(os.path.join(root_path, f))

    for csv_path in csv_list:
        array, behav, color = read_one_hot(meta_path, csv_path)
        csv_name = os.path.splitext(os.path.basename(csv_path))[0]

        mat_path = os.path.join(mat_folder, f"{csv_name}.mat")
        save_to_mat(mat_path, array, behav, color)

def save_to_mat(mat_path, behav_array, behav_dict, color_dict):
    try:
        annotation_struct = {
            "streamID": 1,
            "annotation": behav_array.reshape(-1, 1),
            "behaviors": behav_dict,
        }
        mat_to_save = {
            "annotation": annotation_struct,
            "color": color_dict,
            }

        sio.savemat(mat_path, mat_to_save)
        print(f"Successfully saved to {mat_path}")

    except Exception as e:
        print(f"Failed to save {mat_path}, Exception: {e}")

def read_one_hot(
        json_path:str,
        csv_path:str,
    ) -> Tuple[np.ndarray, Dict[str, int], Dict[str, str]]:
    
    with open(json_path) as f:
        meta = json.load(f)

    df = pd.read_csv(csv_path, sep=",")

    behav_map = meta["behav_map"]

    behav_dict = {}
    color_dict = {}

    behav_cols = sorted([col for col in df.columns if col != "time" and col != "other"])
    forced_behav_dict = {
        "other": 0,
        "ABT": 1,
        "BAT": 2,
        "HTH": 3,
    }

    if "other" in behav_map.keys():
        _, other_color = behav_map["other"]
    else:
        other_color = "#A6A6A6"

    behav_array = np.zeros(df.shape[0], dtype=np.int16)

    behav_dict["other"] = 0
    color_dict["other"] = hex_to_rgb_triplet(other_color)

    for i, behav in enumerate(behav_cols):
        # behav_dict[behav] = i + 1
        # _, color = behav_map[behav]
        # color_dict[behav] = hex_to_rgb_triplet(color)

        # active_series = df[behav]
        # active_mask = (active_series.values == 1)

        # behav_array[active_mask] = i + 1
        if behav in ["ABT", "BAT"]:
            _, color = behav_map[behav]
            color_dict[behav] = hex_to_rgb_triplet(color)
            active_series = df[behav]
            active_mask = (active_series.values == 1)
            behav_array[active_mask] = forced_behav_dict[behav]
        elif behav in ["ABH", "BAH"]:
            _, color = behav_map[behav]
            color_dict["HTH"] = hex_to_rgb_triplet(color)
            active_series = df[behav]
            active_mask = (active_series.values == 1)
            behav_array[active_mask] = forced_behav_dict["HTH"]

    return behav_array, forced_behav_dict, color_dict

def hex_to_rgb_triplet(hex_color:str) -> Tuple[float, float, float]:
    return tuple(int(hex_color[i : i + 2], 16)/255 for i in (1, 3, 5))

def log_prefix_to_json(root_path: str, prefix: List[str], output_file: str = "mapping.json"):
    result_dict = {}

    for f in os.listdir(root_path):
        full_path = os.path.join(root_path, f)
        if not os.path.isfile(full_path):
            continue

        matched_prefix = None

        for p in prefix:
            if f.startswith(p):
                matched_prefix = p
                break

        if matched_prefix:
            rest_of_name = f[len(matched_prefix):]
            result_dict[rest_of_name] = matched_prefix

    output_path = os.path.join(root_path, output_file)
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json.dump(result_dict, json_file, indent=4)
        
    return result_dict

def restore_prefix_from_json(root_path: str, json_file: str = "mapping.json", dry_run: bool = False):
    json_path = os.path.join(root_path, json_file)
    
    with open(json_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    
    renamed_files = {}
    
    for rest_name, prefix in mapping.items():
        old_path = os.path.join(root_path, rest_name)
        new_name = prefix + rest_name
        new_path = os.path.join(root_path, new_name)
        
        if os.path.isfile(old_path):
            if dry_run:
                print(f"[DRY RUN] Would rename: {rest_name} -> {new_name}")
            else:
                os.rename(old_path, new_path)
                print(f"Renamed: {rest_name} -> {new_name}")
            renamed_files[rest_name] = new_name
        else:
            print(f"Warning: File not found - {rest_name}")
    
    return renamed_files


if __name__ == "__main__":
    root_path = r"D:\Project\ASOID-Models\Mar-03-2026\videos\mat"
    meta_path = r"D:\CLP\20260209\TD\192.168.1.168_8000_34_3E309EC0D2DB49AA9A7334C703306281_\111.json"
    # onehot_to_mat_workflow(root_path, meta_path)
    # log_prefix_to_json(root_path, ["NEX_", "ctrl_"])
    restore_prefix_from_json(root_path, dry_run=False)