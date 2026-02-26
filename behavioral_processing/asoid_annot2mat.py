import os
import json
import scipy.io as sio

import numpy as np
import pandas as pd
from collections import defaultdict
from typing import Dict, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox


def aa2m_workflow(root_path:str, asoid_dir:str):
    fpd = find_bvt_export_meta(root_path)
    for id in fpd.keys():
        idd = fpd[id]
        print(f"\n--- Processing ID: {id} ---")

        if idd["dom"] is None or idd["sub"] is None:
            continue
        dom_meta_path = idd["dom"]
        dom_asoid_pred = find_corresponding_asoid_pred(dom_meta_path, asoid_dir)
        if not dom_asoid_pred:
            print(f"No ASOID prediction found for DOM → skipping {id}")
            continue

        sub_meta_path = idd["sub"]
        sub_asoid_pred = find_corresponding_asoid_pred(sub_meta_path, asoid_dir)
        if not sub_asoid_pred:
            print(f"No ASOID prediction found for SUB → skipping {id}")
            continue

        dom_array, dom_behav, dom_color, dom_ins, dom_int = remap_trunc_df(dom_meta_path, dom_asoid_pred)
        sub_array, sub_behav, sub_color, sub_ins, sub_int = remap_trunc_df(sub_meta_path, sub_asoid_pred)

        if dom_behav != sub_behav:
            print(f"Behavior mappings differ between DOM and SUB → skipping {id}")
            continue

        combined_behav = {}
        combined_color = {}
        combined_stat = {
            "neither": 1 - dom_ins - sub_ins,
            "ins_dom": dom_ins,
            "ins_sub": sub_ins,
            "int_dom": dom_int,
            "int_sub": sub_int
        }
        combined_array = dom_array.copy()

        combined_behav["other"] = 0
        combined_color["other"] = dom_color.get("color", (0.65, 0.65, 0.65))

        max_idx = 0

        for key, idx in dom_behav.items():
            if key == "other":
                continue

            combined_behav[f"dom_{key}"] = idx
            combined_color[f"dom_{key}"] = lighten_rgb_triplet(dom_color[key])

            max_idx = max(max_idx, idx)

        new_sub = sub_array.copy()
        new_sub[new_sub!=0] += max_idx

        new_len = min(len(combined_array), len(new_sub))
        combined_array = combined_array[0:new_len]
        new_sub = new_sub[0:new_len]

        combined_array[combined_array==0] = new_sub[combined_array==0]

        for key, idx in sub_behav.items():
            if key == "other":
                continue

            combined_behav[f"sub_{key}"] = idx + max_idx
            combined_color[f"sub_{key}"] = darken_rgb_triplet(sub_color[key])

        mat_path = os.path.join(os.path.dirname(idd["dom"]), f"{id}.mat")
        save_to_mat(mat_path, combined_array, combined_behav, combined_color, combined_stat)

def onehot_to_mat_workflow(root_path:str):
    fpd = find_bvt_export_meta(root_path)
    for id in fpd.keys():
        idd = fpd[id]
        print(f"\n--- Processing ID: {id} ---")

        if idd["dom"] is None or idd["sub"] is None:
            print(f"No complete dom/sub pair → skipping {id}")
            continue
        dom_meta_path = idd["dom"]
        dom_asoid_pred = find_corresponding_bvt_onehot(dom_meta_path)
        if not dom_asoid_pred:
            print(f"No onehot found for DOM → skipping {id}")
            continue

        sub_meta_path = idd["sub"]
        sub_asoid_pred = find_corresponding_bvt_onehot(sub_meta_path)
        if not sub_asoid_pred:
            print(f"No onehot found for SUB → skipping {id}")
            continue

        dom_array, dom_behav, dom_color, dom_ins, dom_int = remap_trunc_df(dom_meta_path, dom_asoid_pred, True)
        sub_array, sub_behav, sub_color, sub_ins, sub_int = remap_trunc_df(sub_meta_path, sub_asoid_pred, True)

        if dom_behav != sub_behav:
            print(f"Behavior mappings differ between DOM and SUB → skipping {id}")
            continue

        combined_behav = {}
        combined_color = {}
        combined_stat = {
            "neither": 1 - dom_ins - sub_ins,
            "ins_dom": dom_ins,
            "ins_sub": sub_ins,
            "int_dom": dom_int,
            "int_sub": sub_int
        }
        combined_array = dom_array.copy()

        combined_behav["other"] = 0
        combined_color["other"] = dom_color.get("color", (0.65, 0.65, 0.65))

        max_idx = 0

        for key, idx in dom_behav.items():
            if key == "other":
                continue

            combined_behav[f"dom_{key}"] = idx
            combined_color[f"dom_{key}"] = lighten_rgb_triplet(dom_color[key])

            max_idx = max(max_idx, idx)

        new_sub = sub_array.copy()
        new_sub[new_sub!=0] += max_idx

        new_len = min(len(combined_array), len(new_sub))
        combined_array = combined_array[0:new_len]
        new_sub = new_sub[0:new_len]

        combined_array[combined_array==0] = new_sub[combined_array==0]

        for key, idx in sub_behav.items():
            if key == "other":
                continue

            combined_behav[f"sub_{key}"] = idx + max_idx
            combined_color[f"sub_{key}"] = darken_rgb_triplet(sub_color[key])

        mat_path = os.path.join(os.path.dirname(idd["dom"]), f"{id}.mat")
        save_to_mat(mat_path, combined_array, combined_behav, combined_color, combined_stat)

def save_to_mat(mat_path, behav_array, behav_dict, color_dict, stat_dict):
    try:
        annotation_struct = {
            "streamID": 1,
            "annotation": behav_array.reshape(-1, 1),
            "behaviors": behav_dict,
        }
        mat_to_save = {
            "annotation": annotation_struct,
            "stat": stat_dict,
            "color": color_dict,
            }

        sio.savemat(mat_path, mat_to_save)
        print(f"Successfully saved to {mat_path}")

    except Exception as e:
        print(f"Failed to save {mat_path}, Exception: {e}")

def find_corresponding_asoid_pred(json_path:str, asoid_dir:str) -> str:
    json_name = os.path.basename(json_path)
    asoid_pred = os.path.join(asoid_dir, json_name.replace(".json", "_pred_annotated_iteration-0.csv"))
    if not os.path.isfile(asoid_pred):
        return
    return asoid_pred

def find_corresponding_bvt_onehot(json_path:str) -> str:
    onehot_filepath = json_path.replace(".json", ".csv")
    if not os.path.isfile(onehot_filepath):
        return
    return onehot_filepath

def find_bvt_export_meta(root_path:str) -> Dict[str, Dict[str, str]]:
    file_pair_dict = defaultdict(lambda: defaultdict(str))
    for root, _, files in os.walk(root_path):
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

            uniqu_id = f"{date_id}{floor_info}{day_info}"

            if dom_status:
                file_pair_dict[uniqu_id]["dom"] = os.path.join(root, f)
            else:
                file_pair_dict[uniqu_id]["sub"] = os.path.join(root, f)

    return file_pair_dict

def remap_trunc_df(
        json_path:str,
        csv_path:str,
        skip_remapping:bool=False
        ) -> Tuple[np.ndarray, Dict[str, int], Dict[str, str]]:
    
    with open(json_path) as f:
        meta = json.load(f)

    df = pd.read_csv(csv_path, sep=",")

    total_frames = meta["total_frames"]
    used_frames = meta["used_frames"]
    behav_map = meta["behav_map"]

    used_perc = len(used_frames) / total_frames
    used_frames = np.array(used_frames, dtype=int)
    behav_dict = {}
    color_dict = {}

    behav_cols = sorted([col for col in df.columns if col != "time" and col != "other"])

    if "other" in behav_map.keys():
        _, other_color = behav_map["other"]
    else:
        other_color = "#A6A6A6"

    extra_behav = []
    if len(behav_map.keys()) - 1 > len(behav_cols):
        extra_behav = [beh for beh in behav_map.keys() if beh not in behav_cols]

    behav_dict["other"] = 0
    color_dict["other"] = hex_to_rgb_triplet(other_color)

    behav_array = np.zeros((total_frames,))
    
    for i, behav in enumerate(behav_cols):
        behav_dict[behav] = i + 1
        _, color = behav_map[behav]
        color_dict[behav] = hex_to_rgb_triplet(color)

        active_series = df[behav]
        active_mask = (active_series.values == 1)

        if skip_remapping:
            behav_array[active_mask] = i + 1
            continue

        active_mask = np.concatenate([[False], active_mask])
        active_original_frames = used_frames[active_mask].tolist()
        behav_array[active_original_frames] = i + 1
        next_i = i + 2

    if extra_behav:
        for j, behav in enumerate(extra_behav):
            behav_dict[behav] = next_i + j
            _, color = behav_map[behav]
            color_dict[behav] = hex_to_rgb_triplet(color)

    activ_perc = 1 - np.sum(behav_array==0)/total_frames
    
    return behav_array, behav_dict, color_dict, used_perc, activ_perc

def hex_to_rgb_triplet(hex_color:str) -> Tuple[float, float, float]:
    return tuple(int(hex_color[i : i + 2], 16)/255 for i in (1, 3, 5))

def lighten_rgb_triplet(rgb_triplet:Tuple[float, float, float], percentage:int=20) -> Tuple[float, float, float]:
    factor = 1 + percentage / 100
    lightened_rgb = []
    for num in rgb_triplet:
        lightened_rgb.append(min(num*factor, 1))

    return tuple(lightened_rgb)

def darken_rgb_triplet(rgb_triplet:Tuple[float, float, float], percentage:int=20) -> Tuple[float, float, float]:
    return lighten_rgb_triplet(rgb_triplet, -percentage)


# def main():
#     tk.Tk().withdraw()

#     print("Select the ROOT folder containing BVT export JSONs...")
#     root_path = filedialog.askdirectory(title="Select BVT Export Root Folder")
#     if not root_path:
#         print("No root folder selected. Exiting.")
#         return

#     print("Select the ASOID predictions folder (with CSVs)...")
#     asoid_dir = filedialog.askdirectory(title="Select ASOID Predictions Folder")
#     if not asoid_dir:
#         print("No ASOID folder selected. Exiting.")
#         return

#     if not os.path.isdir(root_path) or not os.path.isdir(asoid_dir):
#         messagebox.showerror("Error", "Invalid folder selection.")
#         return

#     print(f"\nProcessing:\n  Root: {root_path}\n  ASOID: {asoid_dir}\n")
#     aa2m_workflow(root_path, asoid_dir)
#     print("\nProcessing complete!")

def main():
    tk.Tk().withdraw()

    print("Select the ROOT folder containing BVT export JSONs...")
    root_path = filedialog.askdirectory(title="Select BVT Export Root Folder")
    if not root_path:
        print("No root folder selected. Exiting.")
        return

    if not os.path.isdir(root_path):
        messagebox.showerror("Error", "Invalid folder selection.")
        return

    print(f"\nProcessing:\n  Root: {root_path}\n")
    onehot_to_mat_workflow(root_path)
    print("\nProcessing complete!")

if __name__ == "__main__":
    main()