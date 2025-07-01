import keypoint_moseq as kpms
import re

project_dir = "/home/pedrov/kpms_project"
config = lambda: kpms.load_config(project_dir)

sleap_file = "/mnt/d/Project/deepof/Tables/20250117-OFT-test1-toe1-con-conv.analysis.h5"  # any .slp or .h5 file with predictions for a single video
kpms.setup_project(project_dir, sleap_file=sleap_file)

kpms.update_config(
    project_dir,
    video_dir="/mnt/d/Project/deepof/Videos/",
    anterior_bodyparts=["Nose"],
    posterior_bodyparts=["Tail_base"],
    use_bodyparts=['Nose', 'Left_ear', 'Right_ear', 'Tail_base', 'Spine_1', 'Center', 'Spine_2', 'Left_fhip', 'Right_fhip', 'Left_bhip', 'Right_bhip'],
)

# load data (e.g. from Sleap)
keypoint_data_path = "/mnt/d/Project/deepof/Tables/"  # can be a file, a directory, or a list of files
coordinates, confidences, bodyparts = kpms.load_keypoints(keypoint_data_path, "sleap")

# format data for modeling
data, metadata = kpms.format_data(coordinates, confidences, **config())

# Fit PCA
pca = kpms.fit_pca(**data, **config())
kpms.save_pca(pca, project_dir)

kpms.print_dims_to_explain_variance(pca, 0.9)
kpms.plot_scree(pca, project_dir=project_dir)
kpms.plot_pcs(pca, project_dir=project_dir, **config())
# use the following to load an already fit model
# pca = kpms.load_pca(project_dir)

latentdim = input("Num of components:")
latentdim = int(re.sub('\D', '', latentdim))
kpms.update_config(project_dir, latent_dim=latentdim)