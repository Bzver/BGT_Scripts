import keypoint_moseq as kpms
import numpy as np

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

kappas = np.logspace(8,11,4)
decrease_kappa_factor = 10
num_ar_iters = 50
num_full_iters = 200

prefix = 'my_kappa_scan'

for kappa in kappas:
    print(f"Fitting model with kappa={kappa}")
    model_name = f'{prefix}-{kappa}'
    model = kpms.init_model(data, pca=pca, **config())

    # stage 1: fit the model with AR only
    model = kpms.update_hypparams(model, kappa=kappa)
    model = kpms.fit_model(
        model,
        data,
        metadata,
        project_dir,
        model_name,
        ar_only=True,
        num_iters=num_ar_iters,
        save_every_n_iters=25
    )[0]

    # stage 2: fit the full model
    model = kpms.update_hypparams(model, kappa=kappa/decrease_kappa_factor)
    kpms.fit_model(
        model,
        data,
        metadata,
        project_dir,
        model_name,
        ar_only=False,
        start_iter=num_ar_iters,
        num_iters=num_full_iters,
        save_every_n_iters=25
    )

kpms.plot_kappa_scan(kappas, project_dir, prefix)

