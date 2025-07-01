import os
import re
import deepof.data
import pickle
from IPython import display
from networkx import draw 
import deepof.visuals
import matplotlib.pyplot as plt

project_path = os.path.join("/mnt", "d", "Project", "DeepOF", "deepof_project")
results_dir = os.path.join(project_path, "Results") # Define results directory path
conditions_path = os.path.join(project_path, "conditions.csv")
my_deepof_project = deepof.data.load_project(project_path)
my_deepof_project.load_exp_conditions(conditions_path)

# --- Configuration ---
# Define the path to the saved pickle file (make sure the name matches the one saved)
pickle_path = None
newest_pickle_filename = None

print(f"\nSearching for the newest unsupervised results pickle file in: {results_dir}")
try:
    if not os.path.isdir(results_dir):
        raise FileNotFoundError(f"Results directory not found: {results_dir}")

    # Find all .pkl files matching the expected pattern (adjust if needed)
    potential_files = [
        f for f in os.listdir(results_dir)
        if f.startswith("unsupervised_results_") and f.endswith(".pkl")
    ]

    if not potential_files:
        raise FileNotFoundError(f"No 'unsupervised_results_*.pkl' files found in {results_dir}")

    # Find the newest file based on modification time
    # We create full paths here to ensure getmtime works correctly, especially if the script
    # is run from a different working directory.
    newest_pickle_filename = max(
        potential_files,
        key=lambda f: os.path.getmtime(os.path.join(results_dir, f))
    )
    pickle_path = os.path.join(results_dir, newest_pickle_filename)
    print(f"Found newest file: {newest_pickle_filename}")

except FileNotFoundError as e:
    print(f"Error finding pickle file: {e}")
    print("Make sure 'unsupervised.py' was run successfully and saved a results file.")
    exit()
except Exception as e:
    print(f"An unexpected error occurred while searching for the pickle file: {e}")
    exit()

# --- Load Data from Pickle ---
print(f"\nLoading unsupervised results from {pickle_path}...")
with open(pickle_path, 'rb') as f:
    loaded_data = pickle.load(f)
print("Results loaded successfully.")

# Extract data from the loaded dictionary
embeddings = loaded_data['embeddings']
soft_counts = loaded_data['soft_counts']

#UMAP clustering
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
deepof.visuals.plot_embeddings(
    my_deepof_project,
    embeddings,
    soft_counts,
    aggregate_experiments=None,
    samples=100,
    colour_by="cluster",
    ax=ax1,
    save=False,  # Set to True, or give a custom name, to save the plot
)
deepof.visuals.plot_embeddings(
    my_deepof_project,
    embeddings,
    soft_counts,
    aggregate_experiments="time on cluster",  # Can also be set to 'mean' and 'median'
    exp_condition="SS2",
    show_aggregated_density=True,
    ax=ax2,
    save=False,  # Set to True, or give a custom name, to save the plot,
)
ax2.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.0)
plt.tight_layout()
plt.show()

#Gantt
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
deepof.visuals.plot_gantt(
    my_deepof_project,
    soft_counts=soft_counts,
    instance_id="NS-SS2-1-toe7-HOM-conv",
    ax=ax1,
)
deepof.visuals.plot_gantt(
    my_deepof_project,
    soft_counts=soft_counts,
    instance_id="NS-SS2-2-toe4-wt-conv",
    ax=ax2,
)
plt.tight_layout()
plt.show()

#Global separation 
fig, ax = plt.subplots(1, 1, figsize=(12, 4))
deepof.visuals.plot_distance_between_conditions(
    my_deepof_project,
    embeddings,
    soft_counts,
    "SS2binH",
    distance_metric="wasserstein",
    n_jobs=1,
)
plt.show()
fig, ax = plt.subplots(1, 1, figsize=(12, 4))
deepof.visuals.plot_distance_between_conditions(
    my_deepof_project,
    embeddings,
    soft_counts,
    "SS2binW",
    distance_metric="wasserstein",
    n_jobs=1,
)
plt.show()

best_binsize = input("Optimal bin:")
best_binsize = int(re.sub('\D', '', best_binsize))
worst_binsize = input("Worst bin:")
worst_binsize = int(re.sub('\D', '', worst_binsize))

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
deepof.visuals.plot_embeddings(
    my_deepof_project,
    embeddings,
    soft_counts,
    aggregate_experiments="time on cluster",
    bin_size=best_binsize, # This parameter controls the size of the time bins. We set it to match the optimum reported above
    bin_index=0, # This parameter controls the index of the bins to select, we take the first one here
    ax=ax1,
)
deepof.visuals.plot_embeddings(
    my_deepof_project,
    embeddings,
    soft_counts,
    aggregate_experiments="time on cluster",
    exp_condition="SS2",
    show_aggregated_density=True,
    bin_size=worst_binsize, # This parameter controls the size of the time bins. We set it to match the optimum reported above
    bin_index=0, # This parameter controls the index of the bins to select, we take the fourth one here
    ax=ax2,
)
ax2.legend(
    bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.0
)
ax1.legend().remove()
ax1.set_title('deepOF - optimal aggregated embedding')
ax2.set_title('deepOF - worst aggregated embedding')
plt.tight_layout()
plt.show()

#Cluster enrichment
fig, (ax, ax2) = plt.subplots(2, 1, figsize=(12, 5))
deepof.visuals.plot_enrichment(
    my_deepof_project,
    embeddings,
    soft_counts,
    normalize=True,
    bin_size=best_binsize,
    bin_index=0,
    add_stats="Kruskal",#"Mann-Whitney for dual-conditional comparison",
    exp_condition="SS2",
    verbose=False,
    ax=ax,
)
deepof.visuals.plot_enrichment(
    my_deepof_project,
    embeddings,
    soft_counts,
    normalize=True,
    bin_size=worst_binsize,
    bin_index=0,
    add_stats="Kruskal",#"Mann-Whitney for dual-conditional comparison",
    exp_condition="SS2",
    verbose=False,
    ax=ax2,
)
ax.tick_params(
    axis='x',
    which='both',
    bottom=False,
    top=False,
    labelbottom=False)
ax.set_xlabel("")
ax2.legend().remove()
handles, labels = ax.get_legend_handles_labels()
ax.legend(handles[3:6], labels[3:6])
plt.title("")
plt.tight_layout()
plt.show()

#Cluster transition
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
deepof.visuals.plot_transitions(
    my_deepof_project,
    embeddings.filter_videos(my_deepof_project.get_exp_conditions.keys()),
    soft_counts.filter_videos(my_deepof_project.get_exp_conditions.keys()),
    visualization="networks",
    silence_diagonal=True,
    bin_size=best_binsize,
    bin_index=0,
    exp_condition="SS2binH",
    ax=axes,
)
plt.tight_layout()
plt.show()

# Entropy plots
fig, ax = plt.subplots(1, 1, figsize=(12, 2))
deepof.visuals.plot_stationary_entropy(
    my_deepof_project,
    embeddings,
    soft_counts,
    exp_condition="SS2binH",
    ax=ax,
)

#Cluster visualization
video = deepof.visuals.animate_skeleton(
    my_deepof_project,
    embeddings=embeddings,
    soft_counts=soft_counts,
    experiment_id="20250117-OFT-test8-toe1-con-conv",
    bin_index=0,
    bin_size=5,
    sampling_rate=25,
    selected_cluster=8,
    dpi=60,
    center="arena",
)
html = display.HTML(video)
display.display(html)
plt.close()