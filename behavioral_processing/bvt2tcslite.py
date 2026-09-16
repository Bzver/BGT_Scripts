import joblib
import numpy as np
import tkinter as tk
from tkinter import filedialog
import csv

root = tk.Tk()
root.withdraw()


class Bvt2Mat:
    def __init__(self, dom_filepath: str, sub_filepath: str):
        self.dfp = dom_filepath
        self.sfp = sub_filepath

        self.behavior_dict = {
            "other": 1,
            "dom_in_cage": 2,
            "dom_interaction": 3,
            "sub_in_cage": 4,
            "sub_interaction": 5,
        }

        self.dom_array = self._load_bvtf(dom_filepath)
        self.sub_array = self._load_bvtf(sub_filepath)

        self.anglemap = self._load_anglemap(dom_filepath)

    def bvt_to_mat_workflow(self):
        mice_length = self._get_mice_length()

        dm_beh_array = self._coords_to_beh(self.dom_array, True, mice_length)
        sb_beh_array = self._coords_to_beh(self.sub_array, False, mice_length)

        final_len = min(dm_beh_array.shape[0], sb_beh_array.shape[0])
        dm_beh_array = dm_beh_array[:final_len]
        sb_beh_array = sb_beh_array[:final_len]

        beh_array = dm_beh_array.copy()
        beh_array[dm_beh_array == 1] = sb_beh_array[dm_beh_array == 1]

        # Prompt user for where to save the CSV
        output_filepath = filedialog.asksaveasfilename(
            title="Save Binned Behavior Matrix",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not output_filepath:
            print("No save location selected. Exiting workflow.")
            return

        # Call the output method to write the binned array to the CSV
        self._output_binned_array(beh_array, output_filepath)

    def _output_binned_array(self, beh_array: np.ndarray, output_filepath: str):
        """
        output the binned array (600 frames per bin) into a CSV file.
        Di = dom_interaction, Si = sub_int... Do = dom_in_cage, So = sub_in_..., 
        fill pre and the last four cols with 0
        """
        n_bins = 60
        frames_per_bin = 600
        
        # Map behavior codes to prefixes
        codes = {'Di': 3, 'Do': 2, 'Si': 5, 'So': 4}
        counts = {k: [] for k in codes}
        
        # Calculate counts for each bin
        for i in range(n_bins):
            start = i * frames_per_bin
            end = start + frames_per_bin
            
            if start >= len(beh_array):
                for k in counts:
                    counts[k].append(0.0)
            else:
                end = min(end, len(beh_array))
                bin_data = beh_array[start:end]
                for k, code in codes.items():
                    counts[k].append(float(np.sum(bin_data == code)/10))
                    
        # Build headers
        headers = []
        for prefix in ['Di', 'Do', 'Si', 'So']:
            headers.append(f"{prefix}_pre")
            for i in range(1, n_bins + 1):
                headers.append(f"{prefix}_{i}min")
            headers.append(f"{prefix}_Sum")
            
        # Add metadata headers
        headers.extend(['Estrous', 'Virgin', 'Exp', 'Fem', 'Male', 'FTU', 'Slice'])
        
        # Build values
        values = []
        for prefix in ['Di', 'Do', 'Si', 'So']:
            values.append(0.0)  # pre
            values.extend(counts[prefix])
            values.append(sum(counts[prefix]))  # Sum
            
        # Fill the last metadata columns with 0
        values.extend([0.0] * 7) 
        
        # Format values to match the example style (remove .0 for integers)
        def fmt(v):
            if isinstance(v, (int, float)) and float(v).is_integer():
                return str(int(v))
            return f"{v:.1f}" if isinstance(v, float) else str(v)
            
        formatted_values = [fmt(v) for v in values]

        # Write to CSV
        with open(output_filepath, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerow(formatted_values)
            
        print(f"Successfully saved binned array to: {output_filepath}")

    def _get_mice_length(self) -> float:
        head_idx = self.anglemap["head_idx"]
        all_head = self.dom_array[..., head_idx * 3:head_idx * 3 + 2]
        tail_idx = self.anglemap["tail_idx"]
        all_tail = self.dom_array[..., tail_idx * 3:tail_idx * 3 + 2]
        return np.nanmedian(np.linalg.norm(all_head - all_tail, axis=-1))

    def _coords_to_beh(self, pred_data_array: np.ndarray, dom: bool = True, threshold: float = 50.0) -> np.ndarray:
        F, I, _ = pred_data_array.shape
        coords = pred_data_array.reshape(F, I, -1, 3)
        centroids = np.mean(coords, axis=2)[:, :, :2]
        
        nan_mask = np.isnan(centroids).any(axis=2)
        either_nan = nan_mask.any(axis=1)

        dist = np.linalg.norm(centroids[:, 0, :] - centroids[:, 1, :], axis=1)
        result = np.zeros(F, dtype=int)
        
        result[either_nan] = 1
        valid_mask = ~either_nan
        
        far_mask = valid_mask & (dist > threshold)
        result[far_mask] = 2 if dom else 4
        
        close_mask = valid_mask & (dist <= threshold)
        result[close_mask] = 3 if dom else 5
        
        return result

    @staticmethod
    def _load_bvtf(filepath):
        bvtf = joblib.load(filepath)
        return bvtf.get('dlc_data')["pred_data_array"]
    
    @staticmethod
    def _load_anglemap(filepath):
        bvtf = joblib.load(filepath)
        return bvtf.get('angle_map_data')


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