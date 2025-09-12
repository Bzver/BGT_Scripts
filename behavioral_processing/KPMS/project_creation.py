import os
import keypoint_moseq as kpms

import numpy as np
from scipy.io import loadmat, savemat

MODE = "dannce"   # "dannce" or "sleap"
PROJECT_DIR = "/mnt/d/Project/Keypoint_Moseq/SD-20250620-toe1/"
VIDEO_DIR = ""
KEYPOINT_DATA = "/mnt/d/Project/SDANNCE-Models/4CAM-250620/SD-20250620-toe1/DANNCE/predict00/merged/save_data_AVG0.mat"  # can be a file, a directory, or a list of files

# SDANNCE Config
BP = [  # KPMS's native dannce config suppot is obsolete, had to do it all manually
    "EarL", "EarR", "Snout", "SpineF", "SpineM",
    "Tail(base)", "Tail(mid)", "Tail(end)",
    "ForePawL", "ForeLimbL", "ForePawR", "ForeLimbR",
    "HindPawL", "HindLimbL", "HindPawR", "HindLimbR",
]
SKELETON = [
    ["EarL", "EarR"],
    ["EarR", "Snout"],
    ["EarL", "Snout"],
    ["EarL", "SpineM"],
    ["SpineM", "Tail(base)"],
    ["Tail(base)", "Tail(mid)"],
    ["Tail(mid)", "Tail(end)"],
    ["ForePawL", "ForeLimbL"],
    ["SpineF", "ForeLimbL"],
    ["ForePawR", "ForeLimbR"],
    ["ForeLimbR", "SpineF"],
    ["HindPawL", "HindLimbL"],
    ["HindLimbL", "Tail(base)"],
    ["HindPawR", "HindLimbR"],
    ["HindLimbR", "Tail(base)"],
]
ANTERIOR_BP = ["Snout"]
POSTERIOR_BP = ["Tail(base)"]
USED_BP = [bp for bp in BP if bp not in ("Tail(mid)","Tail(end)")]
N_ANIMALS = 1

# SLEAP Config
SLEAP_FILE = "/mnt/d/Project/deepof/Tables/20250117-OFT-test1-toe1-con-conv.analysis.h5"  # any .slp or .h5 file with predictions for a single video

if MODE == "sleap":    # Sleap setup
    kpms.setup_project(project_dir=PROJECT_DIR, sleap_file=SLEAP_FILE)

elif MODE == "dannce":    # Setup (for 3D SDANNCE)
    kp_mat = loadmat(KEYPOINT_DATA)
    new_kp_data = os.path.join(os.path.dirname(KEYPOINT_DATA), "processed.mat")
    if N_ANIMALS == 1:
        pred = np.squeeze(kp_mat["pred"])
        savemat(new_kp_data,{'pred': pred})
    else:
        new_pred = kp_mat["pred"][:, 0, :, :]
        for i in range(1, N_ANIMALS):
            new_pred = np.concatenate((new_pred, kp_mat["pred"][:, i, :, :]), axis=0)
        savemat(new_kp_data,{'pred': new_pred})
    KEYPOINT_DATA = new_kp_data
        
    kpms.setup_project(
        project_dir=PROJECT_DIR,
        video_dir=VIDEO_DIR,
        bodyparts=BP,
        skeleton=SKELETON,
        overwrite=True)

kpms.update_config(
    project_dir=PROJECT_DIR,
    video_dir=VIDEO_DIR,
    anterior_bodyparts=ANTERIOR_BP,
    posterior_bodyparts=POSTERIOR_BP,
    use_bodyparts=USED_BP,
)

coordinates, confidences, bodyparts = kpms.load_keypoints(filepath_pattern=KEYPOINT_DATA, format=MODE)
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