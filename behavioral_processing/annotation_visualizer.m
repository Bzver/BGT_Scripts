clear all;
close all;

%%
annot_mat = "2025-07-16-first3h.mat";

isCutOff = 1;
fps = 10;
cutOffTime = "03:00:00"; % hh:mm:ss

%%
load(annot_mat);

behaviors = annotation.behaviors;
annot = annotation.annotation;  % Numeric behavior IDs

% Convert to behavior names
behavior_names = string(fieldnames(behaviors));
[~, idx] = ismember(annot, struct2array(behaviors));
annot_named = behavior_names(idx);

%% Apply time cutoff
if isCutOff
    cutOffTime_split = str2double(split(cutOffTime, ':'));
    cutOffTime_seconds = cutOffTime_split(1)*3600 + cutOffTime_split(2)*60 + cutOffTime_split(3);
    cutOff_frame = round(cutOffTime_seconds * fps);
    if cutOff_frame < length(annot)
        annot = annot(1:cutOff_frame);
        annot_named = annot_named(1:cutOff_frame);
    end
end

%% Color ref
colors = [0.8715    0.9028    0.9028;
          0.7431    0.8056    0.8056;
          0.6146    0.7083    0.7083;
          0.4861    0.6111    0.6111;
          0.3889    0.4722    0.5139;
          0.2917    0.3333    0.4167];

%% === 1. Transition Matrix (All Behaviors) ===
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
row_sums = sum(trans_counts, 2);
trans_prob = trans_counts ./ (row_sums + eps);  % Avoid division by zero
trans_prob(isnan(trans_prob)) = 0;

% Plot
figure('Name','Behavior Transition Probabilities');
imagesc(trans_prob);
colormap(flipud(bone));
colorbar;
hold on;

% Labels
ax = gca;
ax.XTick = 1:unique_behaviors;
ax.YTick = 1:unique_behaviors;
ax.XTickLabel = behavior_names;
ax.YTickLabel = behavior_names;
ax.TickLabelInterpreter = 'none';
xlabel('Next Behavior');
ylabel('Current Behavior');

% Overlay counts
for i = 1:unique_behaviors
    for j = 1:unique_behaviors
        val = trans_counts(i,j);
        fontSize = 10;
        if val > 9
            color = 'yellow';
        else
            color = [0.5, 0.5, 0.5];  % gray
        end
        text(j, i, num2str(val, '%d'), ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
            'FontSize', fontSize, 'Color', color);
    end
end

axis image;
title('Transition Counts');
hold off;

%% === 2. Behavior Duration & Subtype Analysis ===
% Helper: count behavior by name
count_beh = @(beh) sum(contains(annot_named, beh));

% --- Total Interaction Time by Role ---
duration_total_dom = sum(contains(annot_named, "dom_"));
duration_total_sub = sum(contains(annot_named, "sub_"));

% --- Initiative Subtypes ---
dom_initiative = sum(contains(annot_named, "dom_init_"));
dom_sniff = count_beh("dom_init_sniff");
dom_anogenital = count_beh("dom_init_anogenital");

sub_initiative = sum(contains(annot_named, "sub_init_"));
sub_sniff = count_beh("sub_init_sniff");
sub_anogenital = count_beh("sub_init_anogenital");

% --- Passive/Flee ---
dom_passive = count_beh("dom_passive");
dom_flee = count_beh("dom_flee");
sub_passive = count_beh("sub_passive");
sub_flee = count_beh("sub_flee");

% --- Idle ---
dom_idle = count_beh("dom_idle");
sub_idle = count_beh("sub_idle");

%% === 3. Pie Charts===
figure('Name', 'Behavior Distribution with Contact Type');
colormap(colors);
set(gcf, 'Color', 'white');

% Labels
role_labels = ["Dom", "Sub"];
contact_labels = ["Sniff", "Anogenital"];

subplot(2,3,1);
pie([duration_total_dom, duration_total_sub], role_labels);
title("Total Interaction Time");

subplot(2,3,2);
dom_init_breakdown = [dom_sniff, dom_anogenital];
if sum(dom_init_breakdown) > 0
    pie(dom_init_breakdown, contact_labels);
    title("Dom Initiative: Contact Type");
else
    text(0, 0, 'No dom initiative', 'HorizontalAlignment', 'center');
    title("Dom Initiative");
end

subplot(2,3,3);
sub_init_breakdown = [sub_sniff, sub_anogenital];
if sum(sub_init_breakdown) > 0
    pie(sub_init_breakdown, contact_labels);
    title("Sub Initiative: Contact Type");
else
    text(0, 0, 'No sub initiative', 'HorizontalAlignment', 'center');
    title("Sub Initiative");
end

subplot(2,3,4);
is_other = strcmp(annot_named, 'other');
transition_from_other_idx = find(is_other(1:end-1) & ~is_other(2:end));
bout_total_dom = 0;
bout_total_sub = 0;
for i = 1:length(transition_from_other_idx)
    next_idx = transition_from_other_idx(i) + 1;  % Next frame after 'other'
    next_behavior = annot_named(next_idx);
    
    if startsWith(next_behavior, 'dom_')
        bout_total_dom = bout_total_dom + 1;
    elseif startsWith(next_behavior, 'sub_')
        bout_total_sub = bout_total_sub + 1;
    end
end
bout_data = [bout_total_dom, bout_total_sub];
pie(bout_data, role_labels)
title("Total Entries");

subplot(2,3,5);
dom_style = [dom_sniff + dom_anogenital, dom_passive, dom_flee];
style_labels = ["Initiative", "Passive", " "];
pie(dom_style, style_labels);
title("Dom Interaction Comp");

subplot(2,3,6);
sub_style = [sub_sniff + sub_anogenital, sub_passive, sub_flee];
pie(sub_style, style_labels);
title("Sub Interaction Comp");

%% === 4. Categorial Bar Plots===
figure('Name','Behavior Distribution Bar');

subplot(1, 2, 1);
duration_init_data = [dom_initiative/fps sub_initiative/fps];
dura_init_x = categorical(role_labels);
B1 = bar(dura_init_x, duration_init_data, 'FaceColor', 'flat');
B1.CData(1,:) = colors(1,:);
B1.CData(2,:) = colors(6,:);
title("Female-led Interaction Time(s)");

subplot(1, 2, 2);
perc_active_dom = ( dom_flee + dom_passive ) / duration_total_dom;
perc_active_sub = ( sub_flee + sub_passive ) / duration_total_sub;
perc_active_l_vs_r = [perc_active_dom perc_active_sub];
perc_act_x = categorical(role_labels);
B2 = bar(perc_act_x, perc_active_l_vs_r, 'FaceColor', 'flat');
B2.CData(1,:) = colors(1,:);
B2.CData(2,:) = colors(6,:);
title("Male Active Index");

%% === 5. Line Plot: Behavior Trends Over Time ===

pin_duration_seconds = 300;  % 5 minutes per bin
pin_duration_frames = pin_duration_seconds * fps;
num_frames_total = length(annot);
num_bins = floor(num_frames_total / pin_duration_frames);
time_minutes = (0.5:num_bins-0.5) * (pin_duration_seconds / 60);  % Center of each bin

% Define behavior groups
behaviors_all = ["dom_idle", "dom_initiative", "dom_passive", "dom_flee", ...
                 "sub_idle", "sub_initiative", "sub_passive", "sub_flee", "other"];

% Preallocate
trends_all = zeros(num_bins, length(behaviors_all));

for p = 1:num_bins
    start_idx = (p-1)*pin_duration_frames + 1;
    end_idx = p*pin_duration_frames;
    segment = annot_named(start_idx:end_idx);
    
    % Reconstruct dom_initiative = sniff + anogenital
    dom_init_total = sum(contains(segment, "dom_init_sniff") | contains(segment, "dom_init_anogenital"));
    sub_init_total = sum(contains(segment, "sub_init_sniff") | contains(segment, "sub_init_anogenital"));
    
    % Fill main trends
    for b = 1:length(behaviors_all)
        beh = behaviors_all(b);
        switch beh
            case "dom_initiative"
                trends_all(p, b) = dom_init_total / pin_duration_frames;
            case "sub_initiative"
                trends_all(p, b) = sub_init_total / pin_duration_frames;
            otherwise
                trends_all(p, b) = sum(contains(segment, beh)) / pin_duration_frames;
        end
    end
end

% Smooth
smoothed_all = movmean(trends_all, [1 1], 1);

% === Plot 1: Full Behavior Dynamics ===
figure('Name', 'Behavior Trends - Full Set', 'Position', [100, 100, 900, 500]);
hold on;

% Custom colors
color_map = [
    0.6    0.6    0.6;      % dom_idle
    0.2    0.4    0.8;      % dom_initiative (blue)
    0.9290 0.6940 0.1250;   % dom_passive (orange)
    0.8    0.3    0.3;      % dom_flee (red)
    0.7    0.7    0.7;      % sub_idle
    0.1    0.2    0.5;      % sub_initiative (dark blue)
    0.8500 0.3250 0.0980;   % sub_passive (darker orange)
    0.9    0.1    0.1;      % sub_flee (bright red)
    0.5    0.5    0.5       % other (gray)
];

hLines1 = gobjects(size(trends_all,2),1);
for b = 1:length(behaviors_all)
    hLines1(b) = plot(time_minutes, smoothed_all(:,b), 'LineWidth', 2, ...
        'Color', color_map(b,:), 'DisplayName', behaviors_all(b));
    % Dashed for sub
    if startsWith(behaviors_all(b), 'sub')
        hLines1(b).LineStyle = '--';
    end
end

hold off;
xlabel('Time (minutes)');
ylabel('Probability');
title('Behavior Dynamics Over Time');
grid on;
box on;
xlim([min(time_minutes), max(time_minutes)]);
xticks(0:30:180);
legend('Location', 'eastoutside', 'Interpreter', 'none');
set(gca, 'XColor', 'black', 'YColor', 'black');
set(gcf, 'Color', 'white');

% === Plot 2: Initiative Breakdown ===
% Preallocate: [dom_init_total, dom_sniff, dom_anogenital, sub_init_total, sub_sniff, sub_anogenital]
trends_init = zeros(num_bins, 6);

for p = 1:num_bins
    start_idx = (p-1)*pin_duration_frames + 1;
    end_idx = p*pin_duration_frames;
    segment = annot_named(start_idx:end_idx);
    
    % Compute all components
    dom_sniff = sum(contains(segment, "dom_init_sniff"));
    dom_anogenital = sum(contains(segment, "dom_init_anogenital"));
    dom_init_total = dom_sniff + dom_anogenital;
    
    sub_sniff = sum(contains(segment, "sub_init_sniff"));
    sub_anogenital = sum(contains(segment, "sub_init_anogenital"));
    sub_init_total = sub_sniff + sub_anogenital;
    
    % Store in trends_init
    trends_init(p, 1) = dom_init_total / pin_duration_frames;
    trends_init(p, 2) = dom_sniff / pin_duration_frames;
    trends_init(p, 3) = dom_anogenital / pin_duration_frames;
    trends_init(p, 4) = sub_init_total / pin_duration_frames;
    trends_init(p, 5) = sub_sniff / pin_duration_frames;
    trends_init(p, 6) = sub_anogenital / pin_duration_frames;
end

% Smooth
smoothed_init = movmean(trends_init, [1 1], 1);

% === Plot: Initiative Subtypes with Totals ===
figure('Name', 'Initiative Breakdown: Dom vs Sub', 'Position', [100, 100, 900, 500]);
hold on;

% Define colors and labels
colors = [
    0.2000    0.4000    0.8000;  % Dom: Total Initiative (dark blue)
    0.4000    0.6000    0.9000;  % Dom: Sniff (light blue)
    0.6000    0.8000    1.0000;  % Dom: Anogenital (very light blue)
    0.8000    0.3000    0.3000;  % Sub: Total Initiative (red)
    0.9000    0.5000    0.5000;  % Sub: Sniff (light red)
    1.0000    0.7000    0.7000  % Sub: Anogenital (very light red)
];

linestyles = {'-', '-', '-', '--', '--', '--'};
labels = {
    'Dom: Total Initiative';
    'Dom: Sniff';
    'Dom: Anogenital';
    'Sub: Total Initiative';
    'Sub: Sniff';
    'Sub: Anogenital'
};

hLines = gobjects(6,1);
for i = 1:6
    % Determine line width
    if i <= 3
        lw = 2.5;
    else
        lw = 2.0;
    end
    
    hLines(i) = plot(time_minutes, smoothed_init(:,i), 'LineWidth', lw, ...
        'Color', colors(i,:), 'LineStyle', linestyles{i}, 'DisplayName', labels{i});
end

hold off;

xlabel('Time (minutes)');
ylabel('Probability (Fraction of Time)');
title('Initiative Contact Type Over Time: Dom vs Sub');
grid on;
box on;
xlim([min(time_minutes), max(time_minutes)]);
xticks(0:30:180);
legend(hLines, labels, 'Location', 'northeastoutside', 'Interpreter', 'none');
set(gca, 'XColor', 'black', 'YColor', 'black', 'Layer', 'bottom');
set(gcf, 'Color', 'white');