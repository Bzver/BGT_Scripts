clear all;
close all;

%%
[filename, pathname] = uigetfile('*.mat', 'Select MAT file');
if isequal(filename, 0)
    error('No file selected. Execution aborted.');
end
annot_mat = fullfile(pathname, filename);

fps = 10;
pin_duration_seconds = 600;

%% Load data
S = load(annot_mat);

if isfield(S, 'annotation')
    behaviors = S.annotation.behaviors;
    annot = int32(S.annotation.annotation);
else
    error('MAT file missing ''annotation'' field.');
end

behavior_names = string(fieldnames(behaviors));
[~, idx] = ismember(annot, struct2array(behaviors));
annot_named = behavior_names(idx);
num_frames_total = length(annot_named);

dom_loco = S.locomotion.dom_loco;
sub_loco = S.locomotion.sub_loco;
dom_td = S.locomotion.dom_td;
sub_td = S.locomotion.sub_td;

dom_bg = S.heatmap.dom_bg;
sub_bg = S.heatmap.sub_bg;
dom_heatmap = S.heatmap.dom_h;
sub_heatmap = S.heatmap.sub_h;

%% Color ref
color_map_active = [
    0.1    0.2    0.5;    % dom_int
    0.55   0.80   0.95;   % dom_icg
    0.65   0.10   0.15;   % sub_int
    0.95   0.55   0.55;   % sub_icg
    0.7    0.7    0.7;    % other
];

%% === 1. Heatmaps with Shared Color Scale ===
dom_hm = im2double(dom_heatmap);
sub_hm = im2double(sub_heatmap);

figure('Name', 'Heatmap & Locomotion Summary', 'Position', [100, 100, 1400, 600]);

subplot(2,2,1);
imshow(dom_bg);
hold on;
h = imagesc(dom_hm); axis image; colormap(jet); 
h.AlphaData = 0.5;
title('Dominant');
xlabel('Arena X'); ylabel('Arena Y');
hold off;

subplot(2,2,2);
imshow(sub_bg);
hold on;
h = imagesc(sub_hm); axis image; colormap(jet);
h.AlphaData = 0.5;
title('Subordinate');
xlabel('Arena X'); ylabel('Arena Y');
hold off;
colorbar;

subplot(2,2,3);
hold on; box on; grid on;

bar(1, dom_td, 0.8, 'FaceColor', [0.1 0.2 0.5], ...
    'EdgeColor', 'k', 'LineWidth', 0.5);
bar(2, sub_td, 0.8, 'FaceColor', [0.65 0.1 0.15], ...
    'EdgeColor', 'k', 'LineWidth', 0.5);

hold off;

ylabel('Total Distance (px)');
set(gca, 'XTick', [1 2], 'XTickLabel', {'Dominant', 'Subordinate'});

distances = [dom_td, sub_td];
max_dist = max(distances);
for i = 1:2
    yval = distances(i);
    text(i, yval + 0.02*max_dist, ...
        sprintf('%.0f', yval), ...
        'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'bottom', ...
        'FontSize', 10, 'FontWeight', 'bold');
end

subplot(2,2,4);
hold on; box on; grid on;

h_dom = histogram(dom_loco, 50, 'FaceColor', [0.1 0.2 0.5], 'FaceAlpha', 0.7);
med_dom = median(dom_loco, 'omitnan');
xline(med_dom, '-.', 'D', 'Color', [0.1 0.2 0.5], 'LineWidth', 1.5);

h_sub = histogram(sub_loco, 50, 'FaceColor', [0.65 0.1 0.15], 'FaceAlpha', 0.7);
med_sub = median(sub_loco, 'omitnan');
xline(med_sub, '--', 'S', 'Color', [0.65 0.1 0.15], 'LineWidth', 1.5);

xlabel('Locomotion (px/frame)');
ylabel('Frame Count');
title('Locomotion Distribution');
legend([h_dom, h_sub], {'Dominant', 'Subordinate'}, 'Location', 'northeast');
hold off;

%% === 2. Behavior Duration & Subtype Analysis ===
count_beh = @(beh_str) sum(contains(annot_named, string(beh_str)));

total = length(annot_named);
dom_int  = count_beh('dom_interaction');
dom_icg  = count_beh('dom_in_cage');
sub_init = count_beh('sub_interaction');
sub_icg  = count_beh('sub_in_cage');
other    = count_beh('other');

%% === 3. Pie Chart ===
figure('Name', 'Behavior Distribution with Contact Type');
colormap(color_map_active);
set(gcf, 'Color', 'white');


role_labels = {
    sprintf('Interact With Dom (%.1f%%)', dom_int/total*100), ...
    sprintf('In Dom Cage (%.1f%%)',      dom_icg/total*100), ...
    sprintf('Interact With Sub (%.1f%%)', sub_init/total*100), ...
    sprintf('In Sub Cage (%.1f%%)',      sub_icg/total*100), ...
    sprintf('In Neither Cage (%.1f%%)',  other/total*100)
};

counts = [dom_int, dom_icg, sub_init, sub_icg, other];
pie(counts, role_labels);
title('Total Interaction Time');

%% === 4. Line Plot: Behavior Trends Over Time ===
pin_duration_frames = pin_duration_seconds * fps;
num_bins = floor(num_frames_total / pin_duration_frames);
if num_bins < 1
    warning('Not enough frames for trend analysis.');
    return;
end

time_minutes = (0.5:num_bins-0.5) * (pin_duration_frames / fps / 60);
behaviors_active = {'dom_interaction', 'dom_in_cage', 'sub_interaction', 'sub_in_cage'};

% Preallocate
trends_active = zeros(num_bins, length(behaviors_active));
for p = 1:num_bins
    start_idx = (p-1)*pin_duration_frames + 1;
    end_idx = min(p*pin_duration_frames, num_frames_total);
    segment = annot_named(start_idx:end_idx);
    
    for b = 1:length(behaviors_active)
        trends_active(p, b) = sum(contains(segment, behaviors_active{b})) / (end_idx - start_idx + 1);
    end
end


smoothed_active = movmean(trends_active, 3, 1);

figure('Name', 'Behavior Trends', 'Position', [100, 100, 1600, 500]);
hold on;

for b = 1:length(behaviors_active)
    h = plot(time_minutes, smoothed_active(:,b), 'LineWidth', 2, ...
        'Color', color_map_active(b,:), ...
        'DisplayName', behaviors_active{b});
end

hold off;
xlabel('Time (minutes)');
ylabel('Probability');
title('Active Behavior Dynamics', 'FontSize', 12);
grid on; box on;
xlim([min(time_minutes), max(time_minutes)]);
legend('Location', 'eastoutside', 'Interpreter', 'none');
set(gca, 'XColor', 'black', 'YColor', 'black');
set(gcf, 'Color', 'white');