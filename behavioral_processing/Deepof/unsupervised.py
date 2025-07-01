import os
import pickle
import deepof.data

project_path = os.path.join("/mnt", "d", "Project", "DeepOF", "deepof_project")
my_deepof_project = deepof.data.load_project(project_path)

# coords = my_deepof_project.get_coords(selected_id="track_0", center="Center", align="Spine_1")
# preprocessed_coords, shapes, global_scaler = coords.preprocess(
#     coordinates=my_deepof_project,
#     window_size=25, # Sliding window length
#     window_step=2, # Sliding window stride
#     test_videos=1, # Number of videos in the validation set
#     scale="standard", # Scaling method
#     save_as_paths=True,
# )

# print("Features in the training set have shape {}".format(shapes[0]))
# print("Features in the validation set have shape {}".format(shapes[1]))

graph_preprocessed_coords, shapes, adj_matrix, to_preprocess, global_scaler = my_deepof_project.get_graph_dataset(
    animal_id="track_0", # Comment out for multi-animal embeddings
    center="Center",
    align="Spine_1",
    window_size=25,
    window_step=2,
    test_videos=5,
    preprocess=True,
    scale="standard",
)

# print("Node features in the training set have shape {}".format(shapes[0]))
# print("Edge features in the training set have shape {}".format(shapes[1]))
# print("Node features in the validation set have shape {}".format(shapes[2]))
# print("Edge features in the validation set have shape {}".format(shapes[3]))

# plt.figure(figsize=(3, 3))
# draw(Graph(adj_matrix))
# plt.show()

trained_model = my_deepof_project.deep_unsupervised_embedding(
    # preprocessed_object=preprocessed_coords, # Change to preprocessed_coords to use non-graph embeddings
    preprocessed_object=graph_preprocessed_coords, # Change to preprocessed_coords to use non-graph embeddings
    adjacency_matrix=adj_matrix,
    embedding_model="VaDE", # Can also be set to 'VQVAE' and 'Contrastive'
    epochs=20,
    encoder_type="recurrent", # Can also be set to 'TCN' and 'transformer'
    n_components=10,
    latent_dim=6,
    batch_size=1024,
    verbose=True, # Set to True to follow the training loop
    interaction_regularization=0.0,
    pretrained=False, # Set to False to train a new model!
)

# Get embeddings, soft_counts, and breaks per video
embeddings, soft_counts = deepof.model_utils.embedding_per_video(
    coordinates=my_deepof_project,
    to_preprocess=to_preprocess,
    model=trained_model,
    animal_id="track_0",
    global_scaler=global_scaler,
)

soft_counts = deepof.post_hoc.recluster(
    soft_counts=soft_counts, # Previously learned soft counts, used as prior information
    coordinates=my_deepof_project, # Coordinates object
    embeddings=embeddings, # Previously learned unsupervised embeddings to cluster
    min_confidence=0.75, # Minimum confidence to count soft_counts as prior information
    states=10, # Number of states to cluster. If used for cluster selection, set to 'aic'
    min_states=2, # Minimum number of states to cluster for cluster selection
    max_states=25, # Maximum number of states to cluster for cluster selection
)

print("\nSaving unsupervised results to pickle file...")

# --- Define parameters used for naming (ensure these match the training) ---
# You might want to fetch these dynamically from the run if possible,
# but defining them explicitly based on the run settings is also common.
embedding_model_name = "VaDE"        # As used in deep_unsupervised_embedding
encoder_type_name = "recurrent"      # As used in deep_unsupervised_embedding
latent_dim_val = 6                   # As used in deep_unsupervised_embedding
n_components_val = 10                # As used in deep_unsupervised_embedding
window_size_val = 25                 # As used in get_graph_dataset
# Add other key parameters if they affect the results significantly

# --- Construct the path to the saved model weights (.h5 file) ---
# DeepOF saves weights in project_path/Trained_models/trained_weights/
# The exact filename includes a timestamp. We need to find it or construct it.
# Option 1: Construct based on known parameters (less robust if timestamp varies)
# Option 2: Find the latest matching file (more robust)

weights_dir = os.path.join(project_path, "Trained_models", "trained_weights")
weights_path = None
try:
    # Find the most recent .h5 file matching the model type and parameters
    prefix = f"deepof_unsupervised_{embedding_model_name}_{encoder_type_name}"
    suffix = f"encoding={latent_dim_val}_k={n_components_val}" # Adjust if naming changes
    matching_files = []
    for f in os.listdir(weights_dir):
        if f.startswith(prefix) and suffix in f and f.endswith(".h5"):
             # Extract timestamp for sorting (assuming format like _YYYYMMDD-HHMMSS_)
             try:
                 timestamp_str = f.split(suffix)[1].split('_final_weights.h5')[0].strip('_')
                 # Basic check for date-time format
                 if len(timestamp_str) == 15 and timestamp_str[8] == '-':
                     matching_files.append((timestamp_str, os.path.join(weights_dir, f)))
             except:
                 # Fallback if parsing fails, just add the file path
                 matching_files.append(("0", os.path.join(weights_dir, f))) # Assign old timestamp

    if matching_files:
        matching_files.sort(key=lambda x: x[0], reverse=True) # Sort by timestamp descending
        weights_path = matching_files[0][1] # Get the latest one
        print(f"Found weights file: {weights_path}")
    else:
        print(f"Warning: Could not automatically find weights file matching prefix '{prefix}' and suffix '{suffix}' in {weights_dir}")

except FileNotFoundError:
    print(f"Warning: Weights directory not found: {weights_dir}")
except Exception as e:
    print(f"Warning: Error finding weights file: {e}")

if weights_path is None:
     print("Proceeding without a weights path in the saved results. Loading will require manual path specification.")

# --- Define the output pickle filename ---
# Include key parameters in the filename for clarity
pickle_filename = f"unsupervised_results_{embedding_model_name}_{encoder_type_name}_k{n_components_val}_enc{latent_dim_val}_ws{window_size_val}_{timestamp_str}.pkl"
# Save it in a dedicated 'Results' directory within the project
results_dir = os.path.join(project_path, "Results")
os.makedirs(results_dir, exist_ok=True) # Create directory if it doesn't exist
pickle_path = os.path.join(results_dir, pickle_filename)

# --- Gather all necessary data to save ---
# We save results (embeddings, counts) and info needed to reload/reconstruct
# (preprocessing info, model config, path to weights)
results_to_save = {
    # Results
    'embeddings': embeddings,
    'soft_counts': soft_counts,

    # Preprocessing info (obtained from get_graph_dataset)
    #'to_preprocess': to_preprocess,
    # 'global_scaler': global_scaler,

    # Model Structure Info (obtained from get_graph_dataset)
    #'adj_matrix': adj_matrix,
    'shapes': shapes, # Contains input_shape and edge_feature_shape

    # Path to saved weights (obtained above)
    'weights_path': weights_path,

    # Key model configuration parameters (explicitly defined or fetched)
    'model_config': {
        'embedding_model': embedding_model_name,
        'encoder_type': encoder_type_name,
        'n_components': n_components_val,
        'latent_dim': latent_dim_val,
        # Add any other parameters needed to instantiate the VaDE model correctly
        # e.g., interaction_regularization if it was non-zero
        'interaction_regularization': 0.0, # From your training call
    },

    # Other relevant run parameters
    'run_params': {
         'window_size': window_size_val,
         'window_step': 1, # From get_graph_dataset
         'animal_id': "track_0", # From get_graph_dataset
         'center': "Center", # From get_graph_dataset
         'align': "Spine_1", # From get_graph_dataset
         'scale': "standard", # From get_graph_dataset
    }
    # Note: We are NOT saving the 'trained_model' object itself
}

# --- Save to pickle file ---
try:
    with open(pickle_path, 'wb') as f:
        pickle.dump(results_to_save, f)
    print(f"Successfully saved results to {pickle_path}")
except Exception as e:
    print(f"Error saving results to pickle file: {e}")