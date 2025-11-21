clear all; close all; clc;

%% --- User Input ---
[filename, pathname] = uigetfile('*.mat', 'Select MAT file');
if isequal(filename, 0)
    error('No file selected. Execution aborted.');
end
annot_mat = fullfile(pathname, filename);

% --- CONFIGURABLE PARAMETERS ---
fps = 10;                     % ← adjust to your video FPS
bin_duration_seconds = 600;    % bin for pies/line
x_bins_per_pie = 5;           % pies aggregate this many bins

%% --- Load Data ---
data = load(annot_mat);
annotation = data.annotation;

% Support both single-stream (vector) and multi-stream (matrix) annotation
if isvector(annotation.annotation)
    a = annotation.annotation(:);     % ensure column
    nstream = 1;
else
    a = annotation.annotation;        % [frames × streams]
    nstream = size(a, 2);
end

num_frames_total = size(a, 1);

% Get behavior mapping
behaviors_struct = annotation.behaviors;
behavior_names = fieldnames(behaviors_struct);
behavior_ids = double(struct2array(behaviors_struct));
num_behaviors = numel(behavior_names);

% ✔️ FIXED COLOR MAP (same as pies/line plot)
fixed_colors = lines(num_behaviors);  % or lines(), tab10, etc.
% To use custom:
% fixed_colors = [0.85 0.325 0.098; 0.1 0.4 0.7; ...]; assert(size match)

% Map ID → index (for color lookup)
[~, id_to_idx] = ismember(behavior_ids, behavior_ids); % trivial, but safe
% Actually: behavior_ids(j) ↔ fixed_colors(j,:) ↔ behavior_names(j)

%% --- Raster Plot (NEW) ---
time_sec = (0:num_frames_total-1)' / fps;  % time vector [0, 1/fps, ..., T]

fig_raster = figure('Name', 'Behavior Raster Plot', ...
                    'Color', 'white', 'Position', [100, 100, 1200, 300 + 80*nstream]);

% For each stream (e.g., animal), compress annotation to segments
for stream = 1:nstream
    ann_vec = a(:, stream);
    
    % Detect transitions: where behavior changes
    diff_ann = [1; diff(ann_vec) ~= 0];  % mark starts
    start_idx = find(diff_ann);
    end_idx = [start_idx(2:end)-1; num_frames_total];
    beh_ids = ann_vec(start_idx);
    
    % Convert to time and duration
    t_start = time_sec(start_idx);
    t_end   = time_sec(end_idx);
    durations = t_end - t_start;
    
    % Plot rectangles
    for k = 1:numel(beh_ids)
        bid = beh_ids(k);
        [~, j] = ismember(bid, behavior_ids);  % behavior index
        if isempty(j) || j == 0
            color = [0.8 0.8 0.8];  % unknown → gray
        else
            color = fixed_colors(j, :);
        end
        
        rectangle('Position', [t_start(k), nstream - stream + 0.1, durations(k), 0.8], ...
                  'FaceColor', color, 'EdgeColor', 'none', 'Parent', gca);
    end
end

% Axis setup
total_time = time_sec(end);
xticks(linspace(0, total_time, 6));
xlabel('Time (seconds)');
ylabel('Stream');
title('Behavior Raster Plot');

% Y-ticks: label streams (customize if needed)
yticks(1:nstream);
if nstream == 1
    yticklabels({'Stream 1'});
elseif nstream == 3
    yticklabels({'Female', 'Subordinate', 'Dominant'});  % as in your example
else
    yticklabels(compose('Stream %d', 1:nstream));
end
ytickangle(0);
grid on;
box on;
xlim([0, total_time]);

%% --- Rest: Binning for Pies & Line Plot (unchanged core logic) ---
bin_duration_frames = bin_duration_seconds * fps;
num_base_bins = floor(num_frames_total / bin_duration_frames);
num_pies = ceil(num_base_bins / x_bins_per_pie);

% Flatten annotation for counting (ignore stream — aggregate all)
% If you want *per-stream* pies, modify accordingly
annot_flat = reshape(a, [], 1);
[~, idx_flat] = ismember(annot_flat, behavior_ids);
annot_named_flat = string(behavior_names(idx_flat));

%% === Pies: x_bins_per_pie, fixed colors, shared legend ===
nRows = floor(sqrt(num_pies));
while nRows > 1 && mod(num_pies, nRows) ~= 0
    nRows = nRows - 1;
end
nRows = max(1, nRows);
nCols = ceil(num_pies / nRows);

fig_pies = figure('Name', sprintf('Behavior Distribution: %d × %d-sec Bins per Pie', ...
                                  x_bins_per_pie, bin_duration_seconds), ...
                  'Color', 'white', 'Position', [100, 100, 1600, 800]);

for p = 1:num_pies
    start_bin = (p-1) * x_bins_per_pie + 1;
    end_bin   = min(p * x_bins_per_pie, num_base_bins);
    if start_bin > num_base_bins; continue; end
    
    % Gather frames in window
    frames_list = [];
    for b = start_bin:end_bin
        s = (b-1)*bin_duration_frames + 1;
        e = min(b*bin_duration_frames, num_frames_total);
        frames_list = [frames_list, s:e];
    end
    window_data = annot_named_flat(frames_list);
    
    % Count per behavior (full list, for color alignment)
    counts = zeros(1, num_behaviors);
    for j = 1:num_behaviors
        counts(j) = sum(window_data == behavior_names{j});
    end
    
    nonzero_mask = counts > 0;
    pie_values = counts(nonzero_mask);
    pie_colors = fixed_colors(nonzero_mask, :);
    
    subplot(nRows, nCols, p);
    if ~isempty(pie_values)
        h = pie(pie_values, zeros(size(pie_values)));
        patches = h(arrayfun(@(x) isa(x,'patch'), h));
        for k = 1:numel(patches)
            set(patches(k), 'FaceColor', pie_colors(k,:), ...
                'EdgeColor', 'white', 'LineWidth', 0.5);
        end
    else
        text(0.5, 0.5, 'No data', 'HorizontalAlignment','center',...
             'FontSize',11,'Color',[0.5 0.5 0.5]);
    end
    
    t0 = (start_bin-1)*bin_duration_seconds;
    t1 = end_bin*bin_duration_seconds;
    title(sprintf('[%d–%d sec]', t0, t1), 'FontSize', 9);
end

% Shared legend (right)
legend_ax = axes('Parent', fig_pies, 'Position', [0.91 0.1 0.08 0.8]);
axis(legend_ax, 'off');
legend_patches = gobjects(num_behaviors,1);
for j = 1:num_behaviors
    legend_patches(j) = patch('Faces',[1 2 3],'Vertices',[0 0;1 0;0.2 0.8],...
                              'FaceColor',fixed_colors(j,:),'EdgeColor','none',...
                              'Parent',legend_ax);
end
legend(legend_ax, legend_patches, string(behavior_names),...
       'Location','west','NumColumns',max(1,floor(num_behaviors/15)),'FontSize',8.5);

%% === Line Plot ===
trends = zeros(num_base_bins, num_behaviors);
for b = 1:num_base_bins
    s = (b-1)*bin_duration_frames + 1;
    e = min(b*bin_duration_frames, num_frames_total);
    seg = annot_named_flat(s:e);
    for j = 1:num_behaviors
        trends(b,j) = sum(seg == behavior_names{j}) / (e-s+1);
    end
end

smoothed = movmean(trends, [1 1], 1);
time_min = (0.5:num_base_bins-0.5) * (bin_duration_seconds/60);

fig_line = figure('Name','Behavior Trends Over Time','Color','white',...
                  'Position',[100,100,1000,600]);
hold on;
for j = 1:num_behaviors
    plot(time_min, smoothed(:,j), 'LineWidth',1.6,'Color',fixed_colors(j,:),...
         'DisplayName',behavior_names{j});
end
xlabel('Time (minutes)'); ylabel('Behavior Probability');
title(sprintf('Behavior Dynamics (Bin = %d sec)', bin_duration_seconds));
grid on; box on; xlim([min(time_min),max(time_min)]);
legend('Location','eastoutside','FontSize',9);
set(gca,'FontSize',10); hold off;