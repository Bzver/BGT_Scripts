import os
import keypoint_moseq as kpms

import numpy as np
from scipy.io import loadmat, savemat

MODE = "dannce"   # "dannce" or "sleap"
PROJECT_DIR = "/mnt/d/Project/Keypoint-Moseq/"
VIDEO_DIR = ""
KEYPOINT_DATA = "/mnt/d/Project/SDANNCE-Models/"  # can be a file, a directory, or a list of files

# SDANNCE Config
SELECTION = "SD-20250620"
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

# SLEAP Config
SLEAP_FILE = "/mnt/d/Project/deepof/Tables/20250117-OFT-test1-toe1-con-conv.analysis.h5"  # any .slp or .h5 file with predictions for a single video

def split_path(path):
    parts = []
    while True:
        path, folder = os.path.split(path)
        if folder:
            parts.append(folder)
        elif path:
            parts.append(path)
            break
        else:
            break
    return list(reversed(parts))

def preprocess_sdannce(filepath_pattern, project_prefix=None):
    processed_list=[]

    if isinstance(filepath_pattern, list):
        file_list = filepath_pattern
    elif os.path.isfile(filepath_pattern):
        file_list = [filepath_pattern]
    elif os.path.isdir(filepath_pattern):
        file_list = [
            os.path.join(root, filename)
            for root, dirs, files in os.walk(filepath_pattern)
            for filename in files
            if filename == "save_data_AVG0.mat"
            and "merged" in root
            and (not project_prefix or project_prefix in root) 
        ]
    else:
        raise ValueError(f"Invalid filepath_pattern: {filepath_pattern}. Must be file, dir, or list.")

    if not file_list:
        print(f"No matching 'save_data_AVG0.mat' files found.")
        return processed_list

    for file in file_list:
        kp_mat = loadmat(file)
        name, ext = os.path.splitext(os.path.basename(file))
        prefix = [block for block in split_path(file) if block.startswith(SELECTION)][0]
        n_animal = kp_mat["pred"].shape[1]
        for i in range(n_animal):
            new_kp_data = os.path.join(PROJECT_DIR, f"{prefix}_{name}_instance{i}{ext}")
            pred = kp_mat["pred"][:, i, :, :]
            savemat(new_kp_data,{'pred': pred})
            processed_list.append(new_kp_data)
    
    return processed_list

os.makedirs(PROJECT_DIR, exist_ok=True)

if MODE == "sleap":    # Sleap setup
    kpms.setup_project(project_dir=PROJECT_DIR, sleap_file=SLEAP_FILE)

elif MODE == "dannce":    # Setup (for 3D SDANNCE)
    KEYPOINT_DATA = preprocess_sdannce(KEYPOINT_DATA, SELECTION)
        
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