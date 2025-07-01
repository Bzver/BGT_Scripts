import keypoint_moseq as kpms

project_dir = "/home/pedrov/kpms_project"
config = lambda: kpms.load_config(project_dir)

# load data (e.g. from Sleap)
keypoint_data_path = "/mnt/d/Project/deepof/Tables/"  # can be a file, a directory, or a list of files
coordinates, confidences, bodyparts = kpms.load_keypoints(keypoint_data_path, "sleap")

# format data for modeling
data, metadata = kpms.format_data(coordinates, confidences, **config())

pca = kpms.load_pca(project_dir)

from jax_moseq.utils import set_mixed_map_iters
set_mixed_map_iters(4)

# initialize the model
model = kpms.init_model(data, pca=pca, **config())
# optionally modify kappa
model = kpms.update_hypparams(model, kappa=1e10)
num_ar_iters = 50
model, model_name = kpms.fit_model(
    model, data, metadata, project_dir, ar_only=True, num_iters=num_ar_iters
)

# load model checkpoint
model, data, metadata, current_iter = kpms.load_checkpoint(
    project_dir, model_name, iteration=num_ar_iters
)
# modify kappa to maintain the desired syllable time-scale
model = kpms.update_hypparams(model, kappa=1e8)
# run fitting for an additional 500 iters
model = kpms.fit_model(
    model,
    data,
    metadata,
    project_dir,
    model_name,
    ar_only=False,
    start_iter=current_iter,
    num_iters=current_iter + 500,
)[0]

# modify a saved checkpoint so syllables are ordered by frequency
kpms.reindex_syllables_in_checkpoint(project_dir, model_name)

# load the most recent model checkpoint
model, data, metadata, current_iter = kpms.load_checkpoint(project_dir, model_name)

# extract results
results = kpms.extract_results(model, metadata, project_dir, model_name)