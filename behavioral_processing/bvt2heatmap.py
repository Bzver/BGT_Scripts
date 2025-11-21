import os
import pickle
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

class Bvt2Heatmap:
    def __init__(self, filepath: str):
        self.fp = filepath
        self.blob_array = None
        self.canvas_dim = None
        self.roi = None

    def bvt_plot_workflow(self):
        try:
            self.read_bvt_workspace()
            self.process_blob_array()
            self.plot_centroids_heatmap()
        except Exception as e:
            print(f"Error: {e}")
            return

    def process_blob_array(self):
        single_animal_mask = self.blob_array[:, 0] == 1
        roi_offset_x = 0 if self.roi is None else self.roi[0]
        roi_offset_y = 0 if self.roi is None else self.roi[1]
        x_coords = self.blob_array[single_animal_mask][:, 2::2] - roi_offset_x
        y_coords = self.blob_array[single_animal_mask][:, 3::2] - roi_offset_y
        self.centroids = np.column_stack((np.mean(x_coords,axis=1), np.mean(y_coords, axis=1)))

    def plot_centroids_heatmap(self):
        height, width = self.canvas_dim
        heatmap = np.zeros((height, width), dtype=np.float32)
        xs = np.clip(self.centroids[:, 0].astype(int), 0, width - 1)
        ys = np.clip(self.centroids[:, 1].astype(int), 0, height - 1)

        np.add.at(heatmap, (ys, xs), 1)
        heatmap = cv2.GaussianBlur(heatmap, (21, 21), sigmaX=10, sigmaY=10)

        if heatmap.max() > 0:
            heatmap = (255 * (heatmap - heatmap.min()) / (heatmap.max() - heatmap.min())).astype(np.uint8)
        else:
            heatmap = heatmap.astype(np.uint8)

        heatmap_color = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)

        output_path = os.path.splitext(self.fp)[0] + "_heatmap.jpg"
        success = cv2.imwrite(output_path, heatmap_color)
        if success:
            print(f"Heatmap saved to: {output_path}")
        else:
            print("Failed to save heatmap.")

    def read_bvt_workspace(self) -> np.ndarray:
        with open(self.fp, 'rb') as f:
            bvtf = Safe_Unpickler(f).load()

        blob_array = bvtf.get('blob_array')
        blob_config = bvtf.get('blob_config')
        roi = bvtf.get('roi')
        video_file = bvtf.get('video_file')

        if roi is None and blob_config["roi"] is None:
            self.get_canvas_dim(video_file)
        else:
            self.roi = blob_config["roi"] if roi is None else roi
            x1, y1, x2, y2 = self.roi
            self.canvas_dim = (abs(y2-y1), abs(x2-x1))

        if blob_array is not None and np.sum(blob_array) != 0:
            self.blob_array = blob_array
        else:
            raise RuntimeError("Blob array missing!")

    def get_canvas_dim(self, video_file):
        if not os.path.isfile(video_file):
            raise FileNotFoundError(f"{video_file} does not exist!")
        
        cap = cv2.VideoCapture(video_file)
        ret, frame = cap.read()
        cap.release()
        if ret:
            self.canvas_dim = frame.shape[:2]
        else:
            raise RuntimeError(f"Could not read frame from {video_file}")


if __name__ == "__main__":
    print("Please select the animal workspace file (.pkl)")
    bvtpkl = filedialog.askopenfilename(
        title="Select Animal Workspace (.pkl)",
        filetypes=[("Pickle files", "*.pkl")]
    )
    if not bvtpkl:
        print("No file selected. Exiting.")
        exit()

    b2m = Bvt2Heatmap(filepath=bvtpkl)
    b2m.bvt_plot_workflow()