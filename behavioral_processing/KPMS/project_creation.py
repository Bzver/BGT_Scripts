import os
import re
import keypoint_moseq as kpms

PROJECT_DIR = "/home/bezver/project/SD-20250714"
MODE = "SDANNCE"   # "SDANNCE" or "SLEAP"

if MODE == "SLEAP":    # Sleap setup
    sleap_file = "/mnt/d/Project/deepof/Tables/20250117-OFT-test1-toe1-con-conv.analysis.h5"  # any .slp or .h5 file with predictions for a single video
    kpms.setup_project(PROJECT_DIR, sleap_file=sleap_file)

elif MODE == "SDANNCE":    # Custom Setup (for 3D SDANNCE)
    bodyparts = [
        "EarL",
        "EarR",
        "Snout",
        "SpineF",
        "SpineM",
        "Tail(base)",
        "Tail(mid)",
        "Tail(end)",
        "ForePawL",
        "ForeLimbL",
        "ForePawR",
        "ForeLimbR",
        "HindPawL",
        "HindLimbL",
        "HindPawR",
        "HindLimbR",
    ]
    skeleton = [
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

    video_dir = "/home/bezver/project/SD-20250714"

    kpms.setup_project(project_dir=PROJECT_DIR, video_dir=video_dir, bodyparts=bodyparts, skeleton=skeleton, overwrite=True)

kpms.update_config(
    project_dir=PROJECT_DIR,
    video_dir=video_dir,
    anterior_bodyparts=["Snout"],
    posterior_bodyparts=["Tail(base)"],
    use_bodyparts=['Snout', 'EarL', 'EarR', 'Tail(base)', 'SpineF', 'SpineM', '', 'Left_fhip', 'Right_fhip', 'Left_bhip', 'Right_bhip'],
)

if MODE == "SLEAP":
    keypoint_data_path = "/mnt/d/Project/deepof/Tables/"  # can be a file, a directory, or a list of files
    coordinates, confidences, bodyparts = kpms.load_keypoints(keypoint_data_path, "sleap")

elif MODE == "SDANNCE":
    keypoint_data_path = "/home/bezver/project/SD-20250714/save_data_AVG0.mat"  # can be a file, a directory, or a list of files
    coordinates, confidences, bodyparts = kpms.load_keypoints(keypoint_data_path, "dannce")

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

latentdim = input("Num of components:")
latentdim = int(re.sub('\D', '', latentdim))
kpms.update_config(project_dir=PROJECT_DIR, latent_dim=latentdim)