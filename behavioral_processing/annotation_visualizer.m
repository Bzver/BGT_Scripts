clear all
close all

%%

annot_mat = "20250709-first3h.mat";

isCutOff = 0;
fps = 10;
cutOffTime = "03:00:00"; %hh:mm:ss

%%
load(annot_mat)

behaviors = annotation.behaviors;
annot = annotation.annotation;

if isCutOff == 1
    cutOffTime_split = str2double(split(cutOffTime,":"));
    cutOffTime_second = cutOffTime_split(1)*3600 + cutOffTime_split(2)*60 + cutOffTime_split(3);
    cutOff_frame = cutOffTime_second * fps;
    annot = annot(1:cutOff_frame);
end

% Convert numeric annotations to behavior names
behavior_names = fieldnames(behaviors);
[~, idx] = ismember(annot, struct2array(behaviors));
annot_named = behavior_names(idx);

%% Durations Plot
transitions = find(diff(annot) ~= 0)+1;
durations = diff([1; transitions; length(annot)]);
transitions = [1;transitions];
behavior_labels = annot_named(transitions);

colors_inverse_mask = ones(6,3);
colors = [0.8715    0.9028    0.9028;
          0.7431    0.8056    0.8056;
          0.6146    0.7083    0.7083;
          0.4861    0.6111    0.6111;
          0.3889    0.4722    0.5139;
          0.2917    0.3333    0.4167];
colors_inverse = colors_inverse_mask-colors;

%% Transition matrix
unique_behaviors = numel(behavior_names);
trans_counts = zeros(unique_behaviors);

for i = 1:length(annot)-1
    current = annot(i) + 1;
    next = annot(i+1) + 1;
    if current ~= next
        trans_counts(current, next) = trans_counts(current, next) + 1;
    end
end

% Convert to probabilities
trans_prob = trans_counts ./ sum(trans_counts, 2);
trans_prob(isnan(trans_prob)) = 0; % Handle divide-by-zero (rows with no transitions)

% Plot
figure('Name','Behavior Transition Probabilities');
imagesc(trans_prob);
colormap(flipud(bone));
colorbar;

% Label axes
xticks(1:unique_behaviors);
yticks(1:unique_behaviors);
xticklabels(behavior_names(1:unique_behaviors));
yticklabels(behavior_names(1:unique_behaviors));
set(gca, 'TickLabelInterpreter', 'none');
xlabel('Next Behavior');
ylabel('Current Behavior');

% Overlay the numbers (using counts or probabilities)
% Choose which to display: trans_counts or trans_prob
display_matrix = trans_counts;  % or trans_prob, your choice

% Add text annotations
for i = 1:unique_behaviors
    for j = 1:unique_behaviors
        val = display_matrix(i, j);
        if val > 9
            text(j, i, num2str(val, '%d'), ...
                 'HorizontalAlignment', 'center', ...
                 'VerticalAlignment', 'middle', ...
                 'FontSize', 10, 'Color', 'yellow');
        else
            text(j, i, num2str(val, '%d'), ...
                 'HorizontalAlignment', 'center', ...
                 'VerticalAlignment', 'middle', ...
                 'FontSize', 8, 'Color', [0.5, 0.5, 0.5]);  % Optional: show zero values dimly
        end
    end
end

% Ensure text is visible (axes not clipped)
axis image;  % Equal scaling

%% Categorial pie charts

duration_total_dom = sum(count(annot_named,"dom"));
duration_total_sub = sum(count(annot_named,"sub"));

other_idx = annotation.behaviors.other;
bout_total_dom = trans_counts(other_idx + 1, annotation.behaviors.dom_idle + 1) +...
                 trans_counts(other_idx + 1, annotation.behaviors.dom_initiative + 1) +...
                 trans_counts(other_idx + 1, annotation.behaviors.dom_passive + 1) +...
                 trans_counts(other_idx + 1, annotation.behaviors.dom_flee + 1);
bout_total_sub = trans_counts(other_idx + 1, annotation.behaviors.sub_idle + 1);
                 trans_counts(other_idx + 1, annotation.behaviors.sub_initiative + 1) +...
                 trans_counts(other_idx + 1, annotation.behaviors.sub_passive + 1) +...
                 trans_counts(other_idx + 1, annotation.behaviors.sub_flee + 1);

duration_initiative_dom = sum(count(annot_named,"dom_initiative"));
duration_passive_dom = sum(count(annot_named,"dom_passive"));
duration_flee_dom = sum(count(annot_named,"dom_flee"));

duration_initiative_sub = sum(count(annot_named,"sub_initiative"));
duration_passive_sub = sum(count(annot_named,"sub_passive"));
duration_flee_sub = sum(count(annot_named,"sub_flee"));

figure('Name','Behavior Distribution Pie');
colormap(colors)
set(gcf, 'color', 'white');
label_l_v_r= ["Dom", "Sub"];
label_comp = ["Initiative", "Passive", "Flee"];
label_comp_b = ["Initiative", "Passive", " "];

subplot(2, 2, 1);
duration_total_l_v_r = [duration_total_dom, duration_total_sub];
pie(duration_total_l_v_r, label_l_v_r)
title("Total Time");

subplot(2, 2, 2);
bout_total_l_v_r = [bout_total_dom, bout_total_sub];
pie(bout_total_l_v_r, label_l_v_r)
title("Total Entries");

subplot(2, 2, 3);
duration_comp_dom = [duration_initiative_dom, duration_passive_dom, duration_flee_dom];
pie(duration_comp_dom, label_comp_b)
title("Dom Interacting Time");

subplot(2, 2, 4);
duration_comp_sub = [duration_initiative_sub, duration_passive_sub, duration_flee_sub];
pie(duration_comp_sub, label_comp)
title("Sub Interacting Time");

%% Categorial Bar Plots
figure('Name','Behavior Distribution Bar');

subplot(1, 2, 1);
duration_init_l_vs_r = [duration_initiative_dom/fps duration_initiative_sub/fps];
dura_init_x = categorical(label_l_v_r);
B1 = bar(dura_init_x, duration_init_l_vs_r, 'FaceColor', 'flat');
B1.CData(1,:) = colors(1,:);
B1.CData(2,:) = colors(6,:);
title("Female-led Interaction Time(s)");

subplot(1, 2, 2);
perc_active_dom = ( duration_passive_dom + duration_flee_dom ) / duration_total_dom;
perc_active_sub = ( duration_passive_sub + duration_flee_sub ) / duration_total_sub;
perc_active_l_vs_r = [perc_active_dom perc_active_sub];
perc_act_x = categorical(label_l_v_r);
B2 = bar(perc_act_x, perc_active_l_vs_r, 'FaceColor', 'flat');
B2.CData(1,:) = colors(1,:);
B2.CData(2,:) = colors(6,:);
title("Male Active Index");

%% === LINE PLOT: Behavior Probability Over Time ===

% Parameters
pin_duration_seconds = 300;  % 5 minutes per bin
pin_duration_frames = pin_duration_seconds * fps;
num_frames_total = length(annot);
num_bins = floor(num_frames_total / pin_duration_frames);

% Ensure we have consistent behavior names
num_behaviors = length(behavior_names);

% Preallocate probability matrix
behavior_probabilities = zeros(num_bins, num_behaviors);

% Loop over bins
for p = 1:num_bins
    start_frame = (p - 1) * pin_duration_frames + 1;
    end_frame = p * pin_duration_frames;
    annot_named_pin = annot_named(start_frame:end_frame);
    
    for b = 1:num_behaviors
        count_b = sum(strcmp(annot_named_pin, behavior_names{b}));
        behavior_probabilities(p, b) = count_b / pin_duration_frames;
    end
end

% Time vector (center of each bin, in minutes)
time_minutes = ((0.5:num_bins-0.5) * pin_duration_seconds) / 60;

% === Smoothing: Moving average (window size = 3 bins) ===
window_size = 3;
smoothed_probs = movmean(behavior_probabilities, [floor(window_size/2), floor(window_size/2)], 1);

% === Define Custom Colors for Each Behavior ===
% Format: { 'BehaviorName', [R G B] }
behavior_colors = {
    'other',           [0.5, 0.5, 0.5];           % Gray
    'dom_idle',        [0.6, 0.6, 0.6];           % Light Gray
    'dom_initiative',  [0.2, 0.4, 0.8];           % Blue
    'dom_passive',     [0.9290 0.6940 0.1250];    % Yellow
    'dom_flee',        [0.8, 0.3, 0.3];           % Red
    'sub_idle',        [0.7, 0.7, 0.7];           % Very Light Gray
    'sub_initiative',  [0.1, 0.2, 0.5];           % Dark Blue
    'sub_passive',     [0.8500 0.3250 0.0980];    % Orange
    'sub_flee',        [0.9, 0.1, 0.1];           % Bright Red
};

% Map colors to behaviors
color_map = zeros(num_behaviors, 3);
for b = 1:num_behaviors
    found = false;
    for c = 1:size(behavior_colors, 1)
        if strcmp(behavior_names{b}, behavior_colors{c, 1})
            color_map(b, :) = behavior_colors{c, 2};
            found = true;
            break;
        end
    end
    if ~found
        color_map(b, :) = [0.5, 0.5, 0.5]; % Default gray
    end
end

% === Plot ===
figure('Name', 'Behavior Trends', 'Position', [100, 100, 900, 500]);
hold on;

% Plot each behavior with custom color
hLines = gobjects(num_behaviors, 1);
for b = 1:num_behaviors
    hLines(b) = plot(time_minutes, smoothed_probs(:, b), 'LineWidth', 2.0, ...
        'Color', color_map(b,:), 'DisplayName', behavior_names{b});
end

hold off;

% === Axes & Labels ===
xlim([min(time_minutes), 180]);                    % Cap at 180 min
xticks(0:30:180);                                  % Every 30 minutes
xlabel('Time (minutes)');
ylabel('Probability (Fraction of Time)');
title(['Behavior Dynamics Over Time' annot_mat]);
grid on;
box on;

% === Legend: Single Column, Outside Right ===
lgd = legend('Location', 'EastOutside', 'NumColumns', 1);
set(lgd, 'Interpreter', 'none');
lgd.Box = 'on';

% Ensure axes colors are black
set(gcf, 'Color', 'white');
set(gca, 'XColor', 'black', 'YColor', 'black', 'Layer', 'bottom');

% Optional: Add line style customization (e.g., dashed for sub)
for b = 1:num_behaviors
    if contains(behavior_names{b}, 'sub')
        hLines(b).LineStyle = '--';
    else
        hLines(b).LineStyle = '-';
    end
end