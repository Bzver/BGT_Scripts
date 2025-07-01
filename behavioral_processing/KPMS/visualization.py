import keypoint_moseq as kpms
import os

project_dir = "/home/pedrov/kpms_project"
config = lambda: kpms.load_config(project_dir)

# load data (e.g. from Sleap)
keypoint_data_path = "/mnt/d/Project/deepof/Tables/"  # can be a file, a directory, or a list of files
coordinates, confidences, bodyparts = kpms.load_keypoints(keypoint_data_path, "sleap")

allmodels = set()
for entry in os.listdir(project_dir):
    if os.path.isdir(os.path.join(project_dir, entry)) and entry.startswith("2025_"):
        allmodels.add(entry)
model_name = max(allmodels)

results = kpms.load_results(project_dir, model_name)

kpms.generate_trajectory_plots(coordinates, results, project_dir, model_name, **config())

kpms.generate_grid_movies(results, project_dir, model_name, coordinates=coordinates, **config())

kpms.plot_similarity_dendrogram(coordinates, results, project_dir, model_name, **config())