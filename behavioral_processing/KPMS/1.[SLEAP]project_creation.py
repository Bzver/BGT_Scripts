import os
import keypoint_moseq as kpms

PROJECT_DIR = "/mnt/d/Project/KPMS-Models/20260125/models"
VIDEO_DIR = ""
KEYPOINT_DATA = "/mnt/d/Project/SDANNCE-Models/"  # can be a file, a directory, or a list of files
SLEAP_FILE = "/mnt/d/Project/deepof/Tables/20250117-OFT-test1-toe1-con-conv.analysis.h5"  # any .slp or .h5 file with predictions for a single video

ANTERIOR_BP = ["Snout"]
POSTERIOR_BP = ["Tail(base)"]

os.makedirs(PROJECT_DIR, exist_ok=True)

kpms.setup_project(project_dir=PROJECT_DIR, sleap_file=SLEAP_FILE)
kpms.update_config(project_dir=PROJECT_DIR, video_dir=VIDEO_DIR, 
    anterior_bodyparts=ANTERIOR_BP, posterior_bodyparts=POSTERIOR_BP)

coordinates, confidences, bodyparts = kpms.load_keypoints(filepath_pattern=KEYPOINT_DATA, format="sleap")
config = lambda: kpms.load_config(project_dir=PROJECT_DIR)

# format data for modeling
data, metadata = kpms.format_data(coordinates, confidences, **config())

if os.path.isfile(os.path.join(PROJECT_DIR, "pca.p")):  # Load existing PCA if there is one
    pca = kpms.load_pca(project_dir=PROJECT_DIR)
else: # Fit PCA if none exist
    pca = kpms.fit_pca(**data, **config())
    kpms.save_pca(pca, project_dir=PROJECT_DIR)
    kpms.print_dims_to_explain_variance(pca, 0.9)
    kpms.plot_scree(pca, project_dir=PROJECT_DIR)
    kpms.plot_pcs(pca, project_dir=PROJECT_DIR, **config())

latentdim = int(input("Num of components:"))
kpms.update_config(project_dir=PROJECT_DIR, latent_dim=latentdim)