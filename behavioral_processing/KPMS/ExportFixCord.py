import keypoint_moseq as kpms
import os
import numpy as np
import jax.numpy as jnp
from jax_moseq.utils import unbatch
from jax_moseq.models.keypoint_slds import estimate_coordinates

# load the model (change project_dir and model_name as needed)
project_dir = "/home/pedrov/kpms_project"
allmodels = set()
for entry in os.listdir(project_dir):
    if os.path.isdir(os.path.join(project_dir, entry)) and entry.startswith("2025_"):
        allmodels.add(entry)
model_name = max(allmodels)
model, _, metadata, _ = kpms.load_checkpoint(project_dir, model_name)

# compute the estimated coordinates
Y_est = estimate_coordinates(
    jnp.array(model['states']['x']),
    jnp.array(model['states']['v']),
    jnp.array(model['states']['h']),
    jnp.array(model['params']['Cd'])
)

# generate a dictionary with reconstructed coordinates for each recording
coordinates_est = unbatch(Y_est, *metadata)

config = lambda: kpms.load_config(project_dir)
keypoint_data_path = "/mnt/d/Project/deepof/Tables/" # can be a file, a directory, or a list of files
coordinates, confidences, bodyparts = kpms.load_keypoints(keypoint_data_path, 'sleap')

recording_name = 'NS-SS2-1-toe5-wt-conv.analysis'
video_path = "/mnt/d/Project/deepof/Videos/NS-SS2-1-toe5-wt-conv.mp4"

output_path = os.path.splitext(video_path)[0]+'.reconstructed_keypoints.mp4'
start_frame, end_frame = 0, 3600

kpms.overlay_keypoints_on_video(
    video_path,
    coordinates_est[recording_name],
    skeleton = config()['skeleton'],
    bodyparts = config()['use_bodyparts'],
    output_path = output_path,
    frames = range(start_frame, end_frame)
)