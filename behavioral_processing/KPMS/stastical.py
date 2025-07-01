import keypoint_moseq as kpms
import os

project_dir = "/home/pedrov/kpms_project"
config = lambda: kpms.load_config(project_dir)

allmodels = set()
for entry in os.listdir(project_dir):
    if os.path.isdir(os.path.join(project_dir, entry)) and entry.startswith("2025_"):
        allmodels.add(entry)
model_name = max(allmodels)

kpms.interactive_group_setting(project_dir, model_name)

moseq_df = kpms.compute_moseq_df(project_dir, model_name, smooth_heading=True)
moseq_df

stats_df = kpms.compute_stats_df(
    project_dir,
    model_name,
    moseq_df,
    min_frequency=0.005,  # threshold frequency for including a syllable in the dataframe
    groupby=["group", "name"],  # column(s) to group the dataframe by
    fps=25,
)  # frame rate of the video from which keypoints were inferred
stats_df

kpms.label_syllables(project_dir, model_name, moseq_df)

kpms.plot_syll_stats_with_sem(
    stats_df,
    project_dir,
    model_name,
    plot_sig=True,  # whether to mark statistical significance with a star
    thresh=0.05,  # significance threshold
    stat="frequency",  # statistic to be plotted (e.g. 'duration' or 'velocity_px_s_mean')
    order="stat",  # order syllables by overall frequency ("stat") or degree of difference ("diff")
    ctrl_group="wt",  # name of the control group for statistical testing
    exp_group="HOM",  # name of the experimental group for statistical testing
    figsize=(8, 4),  # figure size
    groups=stats_df["group"].unique(),  # groups to be plotted
)

normalize = "bigram"  # normalization method ("bigram", "rows" or "columns")

trans_mats, usages, groups, syll_include = kpms.generate_transition_matrices(
    project_dir,
    model_name,
    normalize=normalize,
    min_frequency=0.005,  # minimum syllable frequency to include
)

kpms.visualize_transition_bigram(
    project_dir,
    model_name,
    groups,
    trans_mats,
    syll_include,
    normalize=normalize,
    show_syllable_names=True,  # label syllables by index (False) or index and name (True)
)

# Generate a transition graph for each single group
kpms.plot_transition_graph_group(
    project_dir,
    model_name,
    groups,
    trans_mats,
    usages,
    syll_include,
    layout="circular",  # transition graph layout ("circular" or "spring")
    show_syllable_names=False,  # label syllables by index (False) or index and name (True)
)

# Generate a difference-graph for each pair of groups.
kpms.plot_transition_graph_difference(
    project_dir, model_name, groups, trans_mats, usages, syll_include, layout="circular"
)  # transition graph layout ("circular" or "spring")