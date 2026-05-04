import os
import json
import h5py

import numpy as np
import pandas as pd
from collections import defaultdict
from typing import Dict, Tuple

import tkinter as tk
from tkinter import filedialog


def a2h5_workflow(root_path:str, asoid_dir:str):
    fpd = find_bvt_export_meta(root_path)

    for fp, idd in fpd.items():
        print(f"\n--- Processing ID: {fp} ---")

        if idd["dom"] is None or idd["sub"] is None:
            continue
        dom_meta_path = idd["dom"]
        dom_asoid_pred = find_corresponding_asoid_pred(dom_meta_path, asoid_dir)
        if not dom_asoid_pred:
            print(f"No ASOID prediction found for DOM, skipping {fp}")
            continue

        sub_meta_path = idd["sub"]
        sub_asoid_pred = find_corresponding_asoid_pred(sub_meta_path, asoid_dir)
        if not sub_asoid_pred:
            print(f"No ASOID prediction found for SUB → skipping {fp}")
            continue

        dom_array, dom_behav, dom_color = remap_trunc_df(dom_meta_path, dom_asoid_pred)
        sub_array, sub_behav, _ = remap_trunc_df(sub_meta_path, sub_asoid_pred)

        combined_array = dom_array.copy()

        combined_behav = {}
        combined_behav["other"] = 0

        max_idx = 0
        for key, idx in dom_behav.items():
            if key == "other":
                continue

            combined_behav[f"dom_{key}"] = idx
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

        h5_path = os.path.join(os.path.dirname(idd["dom"]), f"{fp}.h5")

        save_to_h5(h5_path, combined_array, combined_behav, dom_color, fp)

def save_to_h5(h5_path: str, behav_array: np.ndarray, behav_dict: Dict[str, int], color_dict: dict, fpid: str, fps: int=10):
    try:
        sorted_items = sorted(behav_dict.items(), key=lambda x: x[1])
        behavior_map_list = [name for name, _ in sorted_items]
        color_map = {k: list(v) for k, v in color_dict.items()}
        
        session_id = fpid[:8]
        floor = fpid[9]
        day = fpid[-3]
        se = fpid[-2:]

        with h5py.File(h5_path, 'w') as f:
            grp_meta = f.create_group('meta')
            grp_meta.attrs['session_id'] = str(session_id)
            grp_meta.attrs['day'] = day
            grp_meta.attrs['floor'] = floor
            grp_meta.attrs['se_status'] = se == "SE"
            grp_meta.attrs['fps'] = fps
            grp_meta.attrs['total_frames'] = len(behav_array)
            grp_meta.create_dataset('behavior_map', data=json.dumps(behavior_map_list))
            grp_meta.create_dataset('color_map', data=json.dumps(color_map))
            
            grp_data = f.create_group('data')
            grp_data.create_dataset('behaviors', data=behav_array.reshape(-1, 1))

        print(f"Successfully saved to {h5_path}")

    except Exception as e:
        print(f"Failed to save {h5_path}. Exception: {e}")
        raise

def find_corresponding_asoid_pred(json_path:str, asoid_dir:str) -> str:
    json_name = os.path.basename(json_path)
    asoid_pred = os.path.join(asoid_dir, json_name.replace(".json", "_pred_annotated_iteration-0.csv"))
    if not os.path.isfile(asoid_pred):
        print(f"File not found at {asoid_pred}")
        i = 1
        while i < 100:
            asoid_pred = os.path.join(asoid_dir, json_name.replace(".json", f"_pred_annotated_iteration-{i}.csv"))
            if os.path.isfile(asoid_pred):
                return asoid_pred
            i += 1
        return
    return asoid_pred

def find_bvt_export_meta(root_path:str) -> Dict[str, Dict[str, str]]:
    file_pair_dict = defaultdict(lambda: defaultdict(str))
    for root, _, files in os.walk(root_path):
        for f in files:
            if len(f) < 23:
                continue
            if not f[:8].isdigit():
                continue
            if f[9:12] not in ("dom", "sub"):
                continue
            if f[13:16] != "day":
                continue
            if not f[18].isdigit() or int(f[18]) < 0 or int(f[18]) > 4:
                continue
            if f[22:24] not in ["SE", "VG"]:
                continue
            if not f.endswith(".json"):
                continue

            date_id = f[:8]
            dom_status = f[9:12] == "dom"
            se_status = f[22:24]
            day_info = f[13:17]
            floor_info = "F" + f[18]

            unique_id = f"{date_id}{floor_info}{day_info}{se_status}"

            if dom_status:
                file_pair_dict[unique_id]["dom"] = os.path.join(root, f)
            else:
                file_pair_dict[unique_id]["sub"] = os.path.join(root, f)

    return file_pair_dict

def remap_trunc_df(
        json_path:str,
        csv_path:str
        ) -> Tuple[np.ndarray, Dict[str, int], Dict[str, str], np.ndarray]:
    
    with open(json_path) as f:
        meta = json.load(f)

    df = pd.read_csv(csv_path, sep=",")

    total_frames = meta["total_frames"]
    used_frames = meta["used_frames"]
    behav_map = meta["behav_map"]

    behav_dict = {}
    color_dict = {}

    behav_cols = sorted([col for col in df.columns if col != "time" and col != "other"])

    extra_behav = []
    if len(behav_map.keys()) - 1 > len(behav_cols):
        extra_behav = [beh for beh in behav_map.keys() if beh not in behav_cols and beh != "other"]

    behav_dict["other"] = 0

    behav_array = np.zeros(total_frames, dtype=np.int8)

    behav_dict["idle"] = 1
    behav_array[used_frames] = 1
    color_dict["idle"] = "#EED771"

    current_id = 2 

    for behav in behav_cols:
        behav_dict[behav] = current_id
        _, color = behav_map[behav]
        color_dict[behav] = color

        active_series = df[behav]
        active_mask = (active_series.values == 1)

        if len(active_mask) == total_frames:
            behav_array[active_mask] = current_id
        else:
            min_len = min(len(used_frames), len(active_mask))
            u_frames = np.array(used_frames)[:min_len]
            a_mask = active_mask[:min_len]

            valid_frames = u_frames[a_mask]
            behav_array[valid_frames] = current_id
        
        current_id += 1

    if extra_behav:
        for behav in extra_behav:
            behav_dict[behav] = current_id
            _, color = behav_map[behav]
            color_dict[behav] = color
            current_id += 1

    return behav_array, behav_dict, color_dict


if __name__ == "__main__":
    tk.Tk().withdraw()

    print("Select the ROOT folder containing BVT export JSONs...")
    root_path = filedialog.askdirectory(title="Select BVT Export Root Folder")
    if root_path:
        print("Select the ASOID predictions folder (with CSVs)...")
        asoid_dir = filedialog.askdirectory(title="Select ASOID Predictions Folder")
        if asoid_dir:
            print(f"\nProcessing:\n  Root: {root_path}\n  ASOID: {asoid_dir}\n")
            a2h5_workflow(root_path, asoid_dir)
            print("\nProcessing complete!")