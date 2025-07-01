import cv2
cv2.imshow("test",1)
cv2.waitKey(1000)
cv2.destroyAllWindows()

import os
import deepof.data

my_deepof_project = deepof.data.Project(
    # project_path=os.path.join("d:\\","Project","DeepOF"),
    # video_path=os.path.join("d:\\","Project","DeepOF","Videos"),
    # table_path=os.path.join("d:\\","Project","DeepOF","Tables"),
    project_path=os.path.join("/mnt","d","Project","DeepOF"),
    video_path=os.path.join("/mnt","d","Project","DeepOF","Videos"),
    table_path=os.path.join("/mnt","d","Project","DeepOF","Tables"),
    project_name="deepof_project",
    arena='polygonal-autodetect',
    animal_ids="track_0",
    video_format=".mp4",
    table_format='analysis.h5',
    bodypart_graph='deepof_11',  # Can also be set to 'deepof_14' (default), 'deepof_11' or take a custom graph
    video_scale=400,
    iterative_imputation="partial",
    smooth_alpha=1,
    exp_conditions=None,
)

my_deepof_project = my_deepof_project.create(force=True)

graph_preprocessed_coords, shape, adj_matrix, to_preprocess, global_scaler = my_deepof_project.get_graph_dataset(
    animal_id="track_0", # Comment out for multi-animal embeddings
    center="Center",
    align="Spine_1",
    window_size=25,
    window_step=2,
    test_videos=1,
    preprocess=True,
    scale="standard",
)

# plt.figure(figsize=(3, 3))
# draw(Graph(adj_matrix))
# plt.show()
