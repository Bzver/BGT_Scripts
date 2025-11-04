import os
import difflib
import pickle
import scipy.io as sio
import numpy as np
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

    def bvt_to_mat_workflow(self):
        dm_blob_array = self.read_bvt_workspace(self.dfp)
        dm_beh_array = self.process_blob_array(dm_blob_array, domi=True)

        sb_blob_array = self.read_bvt_workspace(self.sfp)
        sb_beh_array = self.process_blob_array(sb_blob_array, domi=False)

        final_len = min(dm_beh_array.shape[0], sb_beh_array.shape[0])
        dm_beh_array = dm_beh_array[:final_len]
        sb_beh_array = sb_beh_array[:final_len]

        beh_array = dm_beh_array.copy()
        beh_array[dm_beh_array == 1] = sb_beh_array[dm_beh_array == 1]

        mat_filename = self.determine_mat_name()
        mat_filepath = os.path.join(os.path.dirname(self.dfp), mat_filename)

        self.save_to_mat(mat_filepath, beh_array)

    def process_blob_array(self, blob_array, domi: bool) -> np.ndarray:
        lower_threshold_mask = blob_array[:, 0] < self.min_count
        higher_threshold_mask = blob_array[:, 0] > self.max_count

        blob_array[lower_threshold_mask, 0] = self.min_count
        blob_array[higher_threshold_mask, 0] = self.max_count
        blob_array[higher_threshold_mask, 1] = 0  # 1 means merged, 0 means no merge

        behav_array = blob_array[:, 0] + blob_array[:, 1]
        if not domi:
            behav_array[behav_array != 1] += 2

        return behav_array

    def determine_mat_name(self) -> str:
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

    def save_to_mat(self, mat_filepath: str, behav_struct: np.ndarray):
        try:
            annotation_struct = {
                "streamID": 1,
                "annotation": behav_struct.reshape(-1, 1),
                "behaviors": self.behavior_dict
            }
            mat_to_save = {"annotation": annotation_struct}
            sio.savemat(mat_filepath, mat_to_save)
            print(f"Successfully saved to {mat_filepath}")
        except Exception as e:
            print(f"Failed to save {mat_filepath}, Exception: {e}")

    @staticmethod
    def read_bvt_workspace(file_path) -> np.ndarray:
        with open(file_path, 'rb') as f:
            bvtf = Safe_Unpickler(f).load()

        blob_array = bvtf.get('blob_array')
        if blob_array is not None and np.sum(blob_array) != 0:
            return blob_array
        else:
            print("Blob array is empty or missing!")
            return np.array([])  # fallback to avoid None


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