import os
import difflib
import pickle
import scipy.io as sio
import numpy as np
import cv2
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()

class Generic_Object:
    def __init__(self, *args, **kwargs):
        pass
    def __call__(self, *args, **kwargs):
        return self
    def __getattr__(self, item):
        return self

class Safe_Unpickler(pickle.Unpickler):
    def find_class(self, module, name):
        try:
            return super().find_class(module, name)
        except (AttributeError, ModuleNotFoundError, KeyError):
            return Generic_Object

class Bvt2Mat:
    def __init__(self, dom_filepath: str, sub_filepath: str, min_count: int = 1, max_count: int = 2):
        self.dfp = dom_filepath
        self.sfp = sub_filepath
        self.min_count = min_count
        self.max_count = max_count

        self.behavior_dict = {
            "other": 1,
            "dom_in_cage": 2,
            "dom_interaction": 3,
            "sub_in_cage": 4,
            "sub_interaction": 5,
        }

        self.dom = Bvt_Process(dom_filepath)
        self.sub = Bvt_Process(sub_filepath)

    def bvt_to_mat_workflow(self):

        dm_beh_array = self._blob_to_beh(self.dom.blob_array, True)
        sb_beh_array = self._blob_to_beh(self.sub.blob_array, False)

        final_len = min(dm_beh_array.shape[0], sb_beh_array.shape[0])
        dm_beh_array = dm_beh_array[:final_len]
        sb_beh_array = sb_beh_array[:final_len]

        beh_array = dm_beh_array.copy()
        beh_array[dm_beh_array == 1] = sb_beh_array[dm_beh_array == 1]

        mat_filename = self._determine_mat_name()
        mat_filepath = os.path.join(os.path.dirname(self.dfp), mat_filename)

        self._save_to_mat(mat_filepath, beh_array)

    def _blob_to_beh(self, blob_array, is_dom: bool) -> np.ndarray:
        lower_threshold_mask = blob_array[:, 0] < self.min_count
        higher_threshold_mask = blob_array[:, 0] > self.max_count

        blob_array[lower_threshold_mask, 0] = self.min_count
        blob_array[higher_threshold_mask, 0] = self.max_count
        blob_array[higher_threshold_mask, 1] = 0  # 1 means merged, 0 means no merge

        behav_array = blob_array[:, 0] + blob_array[:, 1]
        if not is_dom:
            behav_array[behav_array != 1] += 2

        return behav_array

    def _determine_mat_name(self) -> str:
        str1 = os.path.basename(self.dfp).replace("_workspace.pkl", "")
        str2 = os.path.basename(self.sfp).replace("_workspace.pkl", "")
        matcher = difflib.SequenceMatcher(None, str1, str2)
        matches = matcher.get_matching_blocks()
        mat_filename = ""
        for match in matches:
            mat_filename += str1[match.a:match.a + match.size]
        if not mat_filename:
            mat_filename = str1
        mat_filename += ".mat"
        return mat_filename

    def _save_to_mat(self, mat_filepath: str, behav_struct: np.ndarray):
        try:
            annotation_struct = {
                "streamID": 1,
                "annotation": behav_struct.reshape(-1, 1),
                "behaviors": self.behavior_dict,
            }
            heatmap_struct = {
                "dom": self.dom.heatmap,
                "sub": self.sub.heatmap,
            }
            locomotion_struct = {
                "dom_td": self.dom.total_distance,
                "sub_td": self.sub.total_distance,
                "dom_loco": self.dom.get_loco_for_saving(),
                "sub_loco": self.sub.get_loco_for_saving(),
            }
            mat_to_save = {
                "annotation": annotation_struct,
                "heatmap": heatmap_struct,
                "locomotion": locomotion_struct,
                }
            sio.savemat(mat_filepath, mat_to_save)
            print(f"Successfully saved to {mat_filepath}")
        except Exception as e:
            print(f"Failed to save {mat_filepath}, Exception: {e}")

class Bvt_Process:
    def __init__(self, filepath):
        self.fp = filepath
        self.blob_array = None
        self.roi = None
        self.canvas_dim = None
        self.centroids = None
        self.heatmap = None
        self.locomotion = None 
        self.total_distance = 0.0
        self.mobile_percentage = 0.0

        with open(self.fp, 'rb') as f:
            bvtf = Safe_Unpickler(f).load()

        blob_array = bvtf.get('blob_array')
        blob_config = bvtf.get('blob_config')
        roi = bvtf.get('roi')

        if blob_array is not None and np.sum(blob_array) != 0:
            self.blob_array = blob_array
        else:
            raise RuntimeError("Blob array missing!")

        if roi is None and blob_config["roi"] is None:
            self.roi = self._get_canvas_dim_from_blob_array(blob_array)
            x1, y1, x2, y2 = self.roi
            self.canvas_dim = (abs(y2-y1), abs(x2-x1))
        else:
            self.roi = blob_config["roi"] if roi is None else roi
            x1, y1, x2, y2 = self.roi
            self.canvas_dim = (abs(y2-y1), abs(x2-x1))

        self._get_centroid()
        self._get_heatmap()
        self._get_locomotion()

    def _get_canvas_dim_from_blob_array(self, blob_array, buffer=20):
        min_x = np.min(blob_array[:, 2]) - buffer
        min_y = np.min(blob_array[:, 3]) - buffer
        max_x = np.max(blob_array[:, 4]) + buffer
        max_y = np.max(blob_array[:, 5]) + buffer
        
        return min_x, min_y, max_x, max_y
    
    def _get_centroid(self):
        self.centroids = np.full((self.blob_array.shape[0], 2), -1)
        single_animal_mask = self.blob_array[:, 0] == 1
        roi_offset_x = 0 if self.roi is None else self.roi[0]
        roi_offset_y = 0 if self.roi is None else self.roi[1]
        self.centroids[single_animal_mask, 0] = np.mean(self.blob_array[single_animal_mask, 2::2], axis=1) - roi_offset_x
        self.centroids[single_animal_mask, 1] = np.mean(self.blob_array[single_animal_mask, 3::2], axis=1) - roi_offset_y

    def _get_heatmap(self):
        centroids_trimmed = self.centroids[np.all(self.centroids != -1, axis=1)]
        height, width = self.canvas_dim
        heatmap = np.zeros((height, width), dtype=np.float32)
        xs = np.clip(centroids_trimmed[:, 0].astype(int), 0, width - 1)
        ys = np.clip(centroids_trimmed[:, 1].astype(int), 0, height - 1)

        np.add.at(heatmap, (ys, xs), 1)
        heatmap = cv2.GaussianBlur(heatmap, (21, 21), sigmaX=10, sigmaY=10)

        if heatmap.max() > 0:
            heatmap = (255 * (heatmap - heatmap.min()) / (heatmap.max() - heatmap.min())).astype(np.uint8)
        else:
            heatmap = heatmap.astype(np.uint8)

        self.heatmap = heatmap

    def _get_locomotion(self):
        self.locomotion = np.full((self.blob_array.shape[0],), -1)

        changed_indices = np.where(np.diff(self.blob_array[:, 0], 1) != 0)[0]
        start_indices = np.concatenate(([0], changed_indices+1))
        end_indices = np.concatenate((changed_indices, [self.blob_array.shape[0]-1]))

        total_dist = 0.0

        for i in range(len(start_indices)):
            start_idx, end_idx = start_indices[i], end_indices[i]

            if self.blob_array[start_indices[i], 0] != 1: # No need to increment centroid idx because all centroids were recorded when self.blob_array[n, 0] == 1
                continue
            if end_idx - start_idx == 0:
                continue

            steps = np.linalg.norm(np.diff(self.centroids[start_idx:end_idx+1]), axis=1)

            block_distance = np.sum(steps)
            total_dist += block_distance

            self.locomotion[start_idx:end_idx+1] = steps
            
        self.total_distance = total_dist

    def get_loco_for_saving(self) -> np.ndarray:
        return self.locomotion[self.locomotion != -1]
    

if __name__ == "__main__":
    print("Please select the DOMINANT animal workspace file (.pkl)")
    dom_pkl = filedialog.askopenfilename(
        title="Select Dominant Animal Workspace (.pkl)",
        filetypes=[("Pickle files", "*.pkl")]
    )
    if not dom_pkl:
        print("No dominant file selected. Exiting.")
        exit()

    print("Please select the SUBMISSIVE animal workspace file (.pkl)")
    sub_pkl = filedialog.askopenfilename(
        title="Select Submissive Animal Workspace (.pkl)",
        filetypes=[("Pickle files", "*.pkl")]
    )
    if not sub_pkl:
        print("No submissive file selected. Exiting.")
        exit()

    b2m = Bvt2Mat(dom_filepath=dom_pkl, sub_filepath=sub_pkl)
    b2m.bvt_to_mat_workflow()