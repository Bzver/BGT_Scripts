clear all;
close all;

%%
annot_mat = "20250626-first3h.mat";

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
num_frames_total = length(annot_named);

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

% %% === 1. Transition Matrix (All Behaviors) ===
% unique_behaviors = numel(behavior_names);
% trans_counts = zeros(unique_behaviors);
% 
% for i = 1:length(annot)-1
%     current = annot(i) + 1;
%     next = annot(i+1) + 1;
%     if current ~= next
%         trans_counts(current, next) = trans_counts(current, next) + 1;
%     end
% end
% 
% % Convert to probabilities
% row_sums = sum(trans_counts, 2);
% trans_prob = trans_counts ./ (row_sums + eps);  % Avoid division by zero
% trans_prob(isnan(trans_prob)) = 0;
% 
% % Plot
% figure('Name','Behavior Transition Probabilities');
% imagesc(trans_prob);
% colormap(flipud(bone));
% colorbar;
% hold on;
% 
% % Labels
% ax = gca;
% ax.XTick = 1:unique_behaviors;
% ax.YTick = 1:unique_behaviors;
% ax.XTickLabel = behavior_names;
% ax.YTickLabel = behavior_names;
% ax.TickLabelInterpreter = 'none';
% xlabel('Next Behavior');
% ylabel('Current Behavior');
% 
% % Overlay counts
% for i = 1:unique_behaviors
%     for j = 1:unique_behaviors
%         val = trans_counts(i,j);
%         fontSize = 10;
%         if val > 9
%             color = 'yellow';
%         else
%             color = [0.5, 0.5, 0.5];  % gray
%         end
%         text(j, i, num2str(val, '%d'), ...
%             'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
%             'FontSize', fontSize, 'Color', color);
%     end
% end
% 
% axis image;
% title('Transition Counts');
% hold off;

%% === 2. Behavior Duration & Subtype Analysis ===
% Helper: count behavior by name
count_beh = @(beh) sum(contains(annot_named, beh));

% --- Total Interaction Time by Role ---
duration_total_dom = sum(contains(annot_named, "dom_"));
duration_total_sub = sum(contains(annot_named, "sub_"));

% --- Initiative Subtypes ---
dom_init = count_beh("dom_init");
%dom_sniff = count_beh("dom_sniff");
%dom_anogenital = count_beh("dom_anogenital");

sub_init = count_beh("sub_init");
%sub_sniff = count_beh("sub_init_sniff");
%sub_anogenital = count_beh("sub_init_anogenital");

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

subplot(2,2,1);
pie([duration_total_dom, duration_total_sub], role_labels);
title("Total Interaction Time");

subplot(2,2,2);
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

subplot(2,2,3);
dom_style = [dom_init, dom_passive, dom_flee];
style_labels = ["Initiative", "Passive", "Flee"];
pie(dom_style, style_labels);
title("Dom Interaction Comp");

subplot(2,2,4);
sub_style = [sub_init, sub_passive, sub_flee];
pie(sub_style, style_labels);
title("Sub Interaction Comp");

%% === 4. Categorial Bar Plots===
figure('Name','Behavior Distribution Bar');

subplot(1, 2, 1);
duration_init_data = [dom_init/fps sub_init/fps];
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

%% === 5. Line Plot: Behavior Trends Over Time (Active Behaviors Only) ===

pin_duration_seconds = 60;
pin_duration_frames = pin_duration_seconds * fps;
num_bins = floor(num_frames_total / pin_duration_frames);
time_minutes = (0.5:num_bins-0.5) * (pin_duration_frames / fps / 60);

behaviors_all = ["dom_idle", "dom_init", "dom_passive", "dom_flee", ...
                 "sub_idle", "sub_init", "sub_passive", "sub_flee", "other"];
behaviors_active = ["dom_init", "dom_passive", "dom_flee", ...
                    "sub_init", "sub_passive", "sub_flee"];

% Preallocate
num_bins = floor(num_frames_total / pin_duration_frames);
trends_active = zeros(num_bins, length(behaviors_active));

for p = 1:num_bins
    start_idx = (p-1)*pin_duration_frames + 1;
    end_idx = p*pin_duration_frames;
    segment = annot_named(start_idx:end_idx);
    
    % Fill trends
    for b = 1:length(behaviors_active)
        beh = behaviors_active(b);
        trends_active(p, b) = sum(contains(segment, beh)) / pin_duration_frames;
    end
end

% Smooth
smoothed_active = movmean(trends_active, [1 1], 1);

% === Plot 1: Active Behavior Dynamics ===
figure('Name', 'Behavior Trends - Active Only', 'Position', [100, 100, 900, 500]);
hold on;

% Colors
color_map_active = [
    0.2    0.4    0.8;      % dom_init
    0.9290 0.6940 0.1250;   % dom_passive
    0.8    0.3    0.3;      % dom_flee
    0.1    0.2    0.5;      % sub_init
    0.8500 0.3250 0.0980;   % sub_passive
    0.9    0.1    0.1       % sub_flee
];

hLines1 = gobjects(size(trends_active,2),1);
for b = 1:length(behaviors_active)
    hLines1(b) = plot(time_minutes, smoothed_active(:,b), 'LineWidth', 2, ...
        'Color', color_map_active(b,:), 'DisplayName', behaviors_active(b));
    % Dashed for sub
    if startsWith(behaviors_active(b), 'sub')
        hLines1(b).LineStyle = '--';
    end
end

hold off;
xlabel('Time (minutes)');
ylabel('Probability');
title('Active Behavior Dynamics Over Time');
grid on;
box on;
xlim([min(time_minutes), max(time_minutes)]);
xticks(0:30:180);
legend('Location', 'eastoutside', 'Interpreter', 'none');
set(gca, 'XColor', 'black', 'YColor', 'black');
set(gcf, 'Color', 'white');

%% === 6. Line Plot: dom_sum, sub_sum, and other Over Time ===

% Indices for active dom/sub behaviors
dom_active_indices = startsWith(behaviors_all, "dom_");
sub_active_indices = startsWith(behaviors_all, "sub_");

% Compute sums per bin (before smoothing, or use smoothed_all if consistent)
trends_dom_sum = zeros(num_bins, 1);
trends_sub_sum = zeros(num_bins, 1);
trends_other = zeros(num_bins, 1);

for p = 1:num_bins
    start_idx = (p-1)*pin_duration_frames + 1;
    end_idx = p*pin_duration_frames;
    segment = annot_named(start_idx:end_idx);
    
    trends_dom_sum(p) = sum(contains(segment, behaviors_all(dom_active_indices)));
    trends_sub_sum(p) = sum(contains(segment, behaviors_all(sub_active_indices)));
    trends_other(p) = sum(contains(segment, "other"));
end

% Convert to proportions
trends_dom_sum = trends_dom_sum / pin_duration_frames;
trends_sub_sum = trends_sub_sum / pin_duration_frames;
trends_other  = trends_other  / pin_duration_frames;

% Smooth (optional, for consistency)
trends_dom_sum = movmean(trends_dom_sum, [1 1]);
trends_sub_sum = movmean(trends_sub_sum, [1 1]);
trends_other   = movmean(trends_other,   [1 1]);

% Plot
figure('Name', 'Chamber Preference Over Time', 'Position', [100, 100, 900, 500]);
hold on;

h1 = plot(time_minutes, trends_dom_sum, 'LineWidth', 2.5, 'Color', [0.2, 0.4, 0.8],  'DisplayName', 'dom_sum');
h2 = plot(time_minutes, trends_sub_sum, 'LineWidth', 2.5, 'Color', [0.1, 0.2, 0.5],  'LineStyle', '--', 'DisplayName', 'sub_sum');
h3 = plot(time_minutes, trends_other,   'LineWidth', 2,   'Color', [0.5, 0.5, 0.5],  'LineStyle', ':', 'DisplayName', 'other');

hold off;

xlabel('Time (minutes)');
ylabel('Probability');
title('Dom Chamber, Sub Chamber and Middle Chamber Over Time');
grid on;
box on;
xlim([min(time_minutes), max(time_minutes)]);
xticks(round(min(time_minutes)):30:round(max(time_minutes)));
legend('Location', 'best', 'Interpreter', 'none');
set(gca, 'XColor', 'black', 'YColor', 'black');
set(gcf, 'Color', 'white');