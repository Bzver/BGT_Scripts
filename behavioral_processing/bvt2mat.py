import os
import difflib
import joblib
import scipy.io as sio
import numpy as np
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()


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

        self.dom_array = self._load_bvtf(dom_filepath)
        self.sub_array = self._load_bvtf(sub_filepath)

    def bvt_to_mat_workflow(self):
        dm_beh_array = self._blob_to_beh(self.dom_array, True)
        sb_beh_array = self._blob_to_beh(self.sub_array, False)

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
        str1 = os.path.basename(self.dfp).replace("_workspace", "").replace(".joblib", "")
        str2 = os.path.basename(self.sfp).replace("_workspace", "").replace(".joblib", "")
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
            mat_to_save = {
                "annotation": annotation_struct
                }
            sio.savemat(mat_filepath, mat_to_save)
            print(f"Successfully saved to {mat_filepath}")

        except Exception as e:
            print(f"Failed to save {mat_filepath}, Exception: {e}")

    @staticmethod
    def _load_bvtf(filepath):
        bvtf = joblib.load(filepath)
        return bvtf.get('blob_array')


if __name__ == "__main__":
    print("Please select the DOMINANT animal workspace file (.joblib)")
    dom_joblib = filedialog.askopenfilename(
        title="Select Dominant Animal Workspace (.joblib)",
        filetypes=[("Pickle files", "*.joblib")]
    )
    if not dom_joblib:
        print("No dominant file selected. Exiting.")
        exit()

    print("Please select the SUBORDINATE animal workspace file (.joblib)")
    sub_joblib = filedialog.askopenfilename(
        title="Select Subordinate Animal Workspace (.joblib)",
        filetypes=[("Pickle files", "*.joblib")]
    )
    if not sub_joblib:
        print("No subordinate file selected. Exiting.")
        exit()

    b2m = Bvt2Mat(dom_filepath=dom_joblib, sub_filepath=sub_joblib)
    b2m.bvt_to_mat_workflow()