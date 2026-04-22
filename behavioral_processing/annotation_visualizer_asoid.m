clear all;
close all;
clc;

%% ==== Configuration ====
fps = 10;
min_frames = 10;
bin_min = 10;                          % Bin size in minutes for trend plot
binSize = bin_min * 60 * fps;         % Frames per bin
min_bout_frames = 5;                  % Minimum frames to count as a bout


%% ==== Select Single .mat File ====
[mat_file, file_path] = uigetfile('*.mat', 'Select Single .mat File');
if isequal(mat_file, 0)
    disp('No file selected. Exiting.');
    return;
end
mat_path = fullfile(file_path, mat_file);
custom_str_header = mat_file;

%% ==== Ask user for time range in minutes ====
dlg_title = 'Select Time Range for Overall Metrics (Leave both blank for Full Data)';
prompt_lines = {
    'Start time (minutes):', ...
    'End time (minutes):', ...
};
default_vals = {'', ''};

user_input = inputdlg(prompt_lines, dlg_title, [1 30], default_vals);

if isempty(user_input)
    disp('Dialog closed. Exiting.');
    return;
end

% Parse user input
start_min = str2double(user_input{1});
end_min = str2double(user_input{2});

% Validate and set data portion parameters
if isempty(start_min) && isempty(end_min)
    data_portion = 3;
    portion_str = custom_str_header;
    start_frame = 1;
    end_frame = Inf;
elseif isempty(start_min) || isempty(end_min) || isnan(start_min) || isnan(end_min)
    warning('Invalid time input. Using Full Data.');
    data_portion = 3;
    portion_str = custom_str_header;
    start_frame = 1;
    end_frame = Inf;
elseif start_min < 0
    warning('Start time cannot be negative. Using 0.');
    start_min = 0;
    data_portion = 4;
    portion_str = sprintf(" (%.1f-%.1f min)", start_min, end_min);
    start_frame = 1;
    end_frame = round(end_min * 60 * fps);
elseif end_min <= start_min
    warning('End time must be greater than start time. Using Full Data.');
    data_portion = 3;
    portion_str = custom_str_header;
    start_frame = 1;
    end_frame = Inf;
else
    data_portion = 4;
    portion_str = sprintf(" (%.1f-%.1f min)", start_min, end_min);
    start_frame = round(start_min * 60 * fps) + 1;
    end_frame = round(end_min * 60 * fps);
end

%% ==== Load Data ====
fprintf('Loading: %s\n', mat_file);
S = load(mat_path);

if ~isfield(S, 'annotation')
    error('MAT file missing ''annotation'' field.');
end

behaviors = S.annotation.behaviors;
annot = int32(S.annotation.annotation);

has_zone_data = false;
zone_sum = [];

if isfield(S, 'stat') && isfield(S.stat, 'sum')
    zone_sum = int32(S.stat.sum);
    has_zone_data = true;
    min_len = min(length(annot), length(zone_sum));
    annot = annot(1:min_len);
    zone_sum = zone_sum(1:min_len);
end

%% ==== Define and Reorder Behavior Types ====
behavior_types = {'cage', 'interact'};
beh_keys = fieldnames(behaviors); 
% --- Original Detection Loop (Keep this) ---
for i = 1:length(beh_keys)
    beh = string(beh_keys{i});
    if beh == "other"
        continue;
    end
    beh_no_prefix = strrep(beh, "dom_", "");
    beh_no_prefix = strrep(beh_no_prefix, "sub_", "");
    if any(cellfun(@(x) strcmp(x, char(beh_no_prefix)), behavior_types))
        continue;
    end
    behavior_types = [behavior_types, {char(beh_no_prefix)}];
end

% --- NEW: Reorder Logic (Excluding Cage/Interact) ---
fixed_behaviors = {'cage', 'interact'};
dynamic_behaviors = behavior_types(3:end);

if ~isempty(dynamic_behaviors)
    disp('Detected Dynamic Behaviors (Cage/Interact are fixed):');
    disp(dynamic_behaviors');

    prompt = {'Enter order for dynamic behaviors (comma-separated). Leave blank for default:'};
    dlg_title = 'Reorder Dynamic Behaviors';
    default_order = strjoin(dynamic_behaviors, ', ');
    user_order = inputdlg(prompt, dlg_title, [1 80], {default_order});

    if ~isempty(user_order) && ~isempty(user_order{1})
        candidate_list = strsplit(user_order{1}, ',');
        candidate_list = strtrim(candidate_list); 
        
        % Validate
        valid_reorder = true;
        for k = 1:length(candidate_list)
            if ~any(strcmp(candidate_list{k}, dynamic_behaviors))
                valid_reorder = false;
                warndlg(sprintf('Behavior "%s" not found in dynamic list.', candidate_list{k}), 'Invalid Behavior Name');
                break;
            end
        end
        if valid_reorder && length(unique(candidate_list)) ~= length(candidate_list)
            valid_reorder = false;
            warndlg('Duplicate behaviors in order list.', 'Invalid Order');
        end
        
        if valid_reorder
            new_dynamic_behaviors = cell(1, length(candidate_list));
            for k = 1:length(candidate_list)
                idx = find(strcmp(candidate_list{k}, dynamic_behaviors), 1);
                new_dynamic_behaviors{k} = dynamic_behaviors{idx};
            end
            behavior_types = [fixed_behaviors, new_dynamic_behaviors];
            disp('Behaviors reordered successfully.');
        else
            disp('Keeping default behavior order.');
        end
    end
else
    disp('No additional behaviors found to reorder.');
end

% --- Finalize Count ---
n_beh = length(behavior_types);
n_zone_beh = 2;

%% ==== Apply Time Range Selection ====
total_frames = length(annot);
actual_start = min(start_frame, total_frames);
if isinf(end_frame)
    actual_end = total_frames;
else
    actual_end = min(end_frame, total_frames);
end
if actual_start > actual_end
    actual_start = 1;
    actual_end = total_frames;
end

annot_subset = annot(actual_start:actual_end);
if has_zone_data && ~isempty(zone_sum)
    zone_subset = zone_sum(actual_start:actual_end);
else
    zone_subset = [];
end

%% ==== Extract Colors ====
dom_colors = [];
if isfield(S, 'color') && isfield(S, 'stat') && isfield(S.stat, 'sum_color')
    dom_colors = [
        S.stat.sum_color.dom_cage;
        S.stat.sum_color.dom_interact;
    ];
    for mmi = 1:length(behavior_types)
        beh = ['dom_', behavior_types{mmi}];
        if strcmp(beh, 'other') || strcmp(beh, 'dom_cage') || strcmp(beh, 'dom_interact')
            continue;
        end
        dom_colors = [dom_colors; S.color.(beh)];
    end
else
    dom_colors = lines(n_beh);
end

%% ==== Calculate Overall Metrics (Duration) ====
raw_counts_dom = zeros(1, n_beh);
raw_counts_sub = zeros(1, n_beh);
individual_metrics = zeros(1, n_beh);

for b = 1:n_beh
    beh_name = behavior_types{b};
    
    if b == 1  % 'cage'
        if has_zone_data && ~isempty(zone_subset)
            dom_count = sum(zone_subset == 1 | zone_subset == 2);
            sub_count = sum(zone_subset == 3 | zone_subset == 4);
        else
            dom_count = 0; sub_count = 0;
        end
        
    elseif b == 2  % 'interact'
        if has_zone_data && ~isempty(zone_subset)
            dom_count = sum(zone_subset == 2);
            sub_count = sum(zone_subset == 4);
        else
            dom_count = 0; sub_count = 0;
        end
        
    else
        dom_field = ['dom_' beh_name];
        sub_field = ['sub_' beh_name];
        
        dom_count = 0; sub_count = 0;
        dom_val = []; sub_val = [];
        
        if isfield(behaviors, dom_field)
            dom_val = behaviors.(dom_field);
            dom_count = sum(annot_subset == dom_val);
        end
        if isfield(behaviors, sub_field)
            sub_val = behaviors.(sub_field);
            sub_count = sum(annot_subset == sub_val);
        end
    end
    
    raw_counts_dom(b) = dom_count;
    raw_counts_sub(b) = sub_count;
    
    if (dom_count + sub_count) > min_frames
        individual_metrics(b) = (dom_count - sub_count) / (dom_count + sub_count);
    else
        individual_metrics(b) = NaN;
    end
end

%% ==== Calculate Trend Metrics (Duration) ====
effective_frames = length(annot);
n_bins_actual = ceil(effective_frames / binSize);

trend_dom = NaN(1, n_beh, n_bins_actual);
trend_sub = NaN(1, n_beh, n_bins_actual);

for b = 1:n_beh
    beh_name = behavior_types{b};
    
    if b == 1  % 'cage'
        for bin = 1:n_bins_actual
            start_idx = (bin-1)*binSize + 1;
            end_idx = min(bin*binSize, effective_frames);
            if start_idx > effective_frames, break; end
            
            if has_zone_data
                bin_zone = zone_sum(start_idx:end_idx);
                trend_dom(1, b, bin) = sum(bin_zone == 1 | bin_zone == 2);
                trend_sub(1, b, bin) = sum(bin_zone == 3 | bin_zone == 4);
            end
        end
        
    elseif b == 2  % 'interact'
        for bin = 1:n_bins_actual
            start_idx = (bin-1)*binSize + 1;
            end_idx = min(bin*binSize, effective_frames);
            if start_idx > effective_frames, break; end
            
            if has_zone_data
                bin_zone = zone_sum(start_idx:end_idx);
                trend_dom(1, b, bin) = sum(bin_zone == 2);
                trend_sub(1, b, bin) = sum(bin_zone == 4);
            end
        end
    
    else
        dom_field = ['dom_' beh_name];
        sub_field = ['sub_' beh_name];
        dom_val = []; sub_val = [];
        if isfield(behaviors, dom_field), dom_val = behaviors.(dom_field); end
        if isfield(behaviors, sub_field), sub_val = behaviors.(sub_field); end
        
        for bin = 1:n_bins_actual
            start_idx = (bin-1)*binSize + 1;
            end_idx = min(bin*binSize, effective_frames);
            if start_idx > effective_frames, break; end
            
            bin_annot = annot(start_idx:end_idx);
            trend_dom(1, b, bin) = sum(bin_annot == dom_val);
            trend_sub(1, b, bin) = sum(bin_annot == sub_val);
        end
    end
end

%% ==== Statistics ====
mean_metrics = individual_metrics';
sem_metrics = zeros(n_beh, 1);  % Single file, SEM = 0

p_vals = nan(n_beh, 1);
for b = 1:n_beh
    if ~isnan(individual_metrics(b))
        p_vals(b) = 0;  % Single file, no statistical test
    end
end

% Trend statistics (single file)
trend_dom_mean = trend_dom;
trend_sub_mean = trend_sub;
trend_dom_sem = zeros(size(trend_dom));
trend_sub_sem = zeros(size(trend_sub));
trend_p = nan(1, n_beh, n_bins_actual);

time_min = (0:n_bins_actual-1 + 0.5) * ((binSize / fps) / 60);

%% ==== Plot 1: Raw Frame Counts (Duration) ====
fprintf('Creating raw frame counts plot (Duration)...\n');
figure('Name', 'Raw Frame Counts (Duration)', 'Position', [300, 300, 950, 500], 'Color', 'w');

x = 1:n_beh;
width = 0.35;
lighten_factor = 0.4;

hold on; box on; grid on;
for b = 1:n_beh
    sub_color = dom_colors(b,:) + (1 - dom_colors(b,:)) * lighten_factor;
    bar(x(b) - width/2, raw_counts_dom(b), width, 'FaceColor', dom_colors(b,:), 'EdgeColor', 'k', 'LineWidth', 0.5);
    bar(x(b) + width/2, raw_counts_sub(b), width, 'FaceColor', sub_color, 'EdgeColor', 'k', 'LineWidth', 0.5);
end

ylabel('Frame Count');
set(gca, 'XTick', x, 'XTickLabel', behavior_types, 'TickLabelInterpreter', 'none');
xtickangle(45);
title(['Raw Frame Counts (Duration)' portion_str], 'Interpreter', 'none', 'FontSize', 14, 'FontWeight', 'bold');
legend({'Dominant', 'Submissive'}, 'Location', 'best', 'Interpreter', 'none');
hold off;

%% ==== Plot 2: Preference Index (Duration) ====
fprintf('Creating preference index plot (Duration)...\n');
figure('Name', 'Preference Index (Duration)', 'Position', [300, 300, 950, 500], 'Color', 'w');

hold on; box on; grid on;
for b = 1:n_beh
    bar(x(b), mean_metrics(b), 0.6, 'FaceColor', dom_colors(b,:), 'EdgeColor', 'k', 'LineWidth', 0.5);
end

% Add individual point (single file)
for b = 1:n_beh
    if ~isnan(mean_metrics(b))
        scatter(x(b), mean_metrics(b), 80, dom_colors(b,:), 'filled', 'MarkerEdgeColor', 'k');
    end
end

ylabel('(Dom - Sub) / (Dom + Sub)');
set(gca, 'XTick', x, 'XTickLabel', behavior_types, 'TickLabelInterpreter', 'none');
xtickangle(45);
title(['Preference Index (Duration)' portion_str], 'Interpreter', 'none', 'FontSize', 14, 'FontWeight', 'bold');
ylim([-1, 1]);
hold off;

%% ==== Plot 3: Raw Duration Trend ====
fprintf('Generating raw duration trend plot...\n');
plot_trend_figure(trend_dom_mean, trend_sub_mean, trend_dom_sem, trend_sub_sem, trend_p, ...
    time_min, behavior_types, 'Raw Duration Trend: Dom vs Sub', 'Duration (frames)', false);

%% ==== Plot 4: Cumulative Duration Trend ====
fprintf('Generating cumulative duration trend plot...\n');
plot_cumulative_figure(trend_dom_mean, trend_sub_mean, trend_dom_sem, trend_sub_sem, trend_p, ...
    time_min, behavior_types, 'Cumulative Duration Trend', 'Cumulative Duration (frames)', false);

%% ==== Plot 5: Dual Behavior Raster (Dom vs Sub) ====
fprintf('Generating dual behavior raster plot...\n');

behavior_fields = fieldnames(behaviors);
dom_ids = [];
sub_ids = [];
dom_labels = {};
sub_labels = {};

% Extract dom/sub IDs from struct (these are positive integers)
for i = 1:length(behavior_fields)
    name = behavior_fields{i};
    id_val = behaviors.(name);
    if startsWith(name, 'dom_')
        dom_labels{end+1} = name;
        dom_ids(end+1) = id_val;
    elseif startsWith(name, 'sub_')
        sub_labels{end+1} = name;
        sub_ids(end+1) = id_val;
    end
end

% --- Top raster: DOM behaviors + OTHER (0) ---
annot_dom = annot;  % includes 0 for "other"
% Recode all SUB behaviors as "other" (0)
for id = sub_ids
    annot_dom(annot_dom == id) = 0;
end

% Remap for display: [dom1, dom2, ..., other] → [1, 2, ..., N]
plot_dom = zeros(size(annot_dom));
for k = 1:length(dom_ids)
    plot_dom(annot_dom == dom_ids(k)) = k;  % dom behavior → index k
end
plot_dom(annot_dom == 0) = length(dom_ids) + 1;  % other → last index

% Colormap: dom colors + other color
color_map_dom = zeros(length(dom_labels) + 1, 3);
for k = 1:length(dom_labels)
    if isfield(S.color, dom_labels{k})
        color_map_dom(k, :) = S.color.(dom_labels{k});
    else
        color_map_dom(k, :) = dom_colors(min(k, size(dom_colors,1)), :);
    end
end
if isfield(S.color, 'other')
    color_map_dom(end, :) = S.color.other;
else
    color_map_dom(end, :) = [0.5 0.5 0.5];  % fallback gray
end
labels_dom = [dom_labels, "other"];

% --- Bottom raster: SUB behaviors + OTHER (0) ---
annot_sub = annot;
for id = dom_ids
    annot_sub(annot_sub == id) = 0;
end

plot_sub = zeros(size(annot_sub));
for k = 1:length(sub_ids)
    plot_sub(annot_sub == sub_ids(k)) = k;
end
plot_sub(annot_sub == 0) = length(sub_ids) + 1;

color_map_sub = zeros(length(sub_labels) + 1, 3);
for k = 1:length(sub_labels)
    if isfield(S.color, sub_labels{k})
        color_map_sub(k, :) = S.color.(sub_labels{k});
    else
        color_map_sub(k, :) = dom_colors(min(k, size(dom_colors,1)), :);
    end
end
if isfield(S.color, 'other')
    color_map_sub(end, :) = S.color.other;
else
    color_map_sub(end, :) = [0.5 0.5 0.5];
end
labels_sub = [sub_labels, "other"];

% --- Plot ---
figure('Name', 'Dual Behavior Raster (Dom vs Sub)', 'Position', [100, 100, 1400, 600], 'Color', 'white');

% Top: Dom
ax1 = subplot(2,1,1);
imagesc(ax1, plot_dom');
colormap(ax1, color_map_dom);
clim(ax1, [1, size(color_map_dom,1)]);
set(ax1, 'YTick', [], 'XTick', [], 'Box', 'on');
title(ax1, 'Dominant Mouse Behaviors', 'FontWeight', 'bold', 'FontSize', 12);

cb1 = colorbar(ax1, 'Ticks', 1:length(labels_dom), 'TickLabels', labels_dom);
cb1.Position = [0.92, 0.53, 0.02, 0.35];
cb1.Label.String = 'Behavior';
cb1.Label.FontSize = 10;
cb1.TickLabelInterpreter = 'none';

% Bottom: Sub
ax2 = subplot(2,1,2);
imagesc(ax2, plot_sub');
colormap(ax2, color_map_sub);
clim(ax2, [1, size(color_map_sub,1)]);
set(ax2, 'YTick', [], 'Box', 'on');
xlabel(ax2, 'Frame Index', 'FontSize', 11);
title(ax2, 'Subordinate Mouse Behaviors', 'FontWeight', 'bold', 'FontSize', 12);

cb2 = colorbar(ax2, 'Ticks', 1:length(labels_sub), 'TickLabels', labels_sub);
cb2.Position = [0.92, 0.13, 0.02, 0.35];
cb2.Label.String = 'Behavior';
cb2.Label.FontSize = 10;
cb2.TickLabelInterpreter = 'none';

ax1.XAxis.Exponent = 0;
ax1.XTick = 0:36000:length(annot);
ax2.XAxis.Exponent = 0;
ax2.XTick = 0:36000:length(annot);

sgtitle(['Dual Behavior Raster Plot' portion_str], 'FontSize', 14, 'FontWeight', 'bold');

fprintf('\nSingle-file processing complete!\n');
fprintf('Total frames: %d\n', length(annot));
fprintf('Duration: %.1f minutes\n', length(annot) / (60 * fps));
other_count = sum(annot == 0);
fprintf('"Other" frames: %d (%.1f%%)\n', other_count, 100*other_count/length(annot));

%% ==== Save All Figures to <mat_dir>/figures/ ====
fprintf('\nSaving figures...\n');

% Create output folder
[pathname, name, ext] = fileparts(mat_path);
filename = [name, ext];  % e.g., 'data.mat'
figures_dirname = strrep(filename, '.mat', '_figures');
figures_dir = fullfile(pathname, figures_dirname);
if ~exist(figures_dir, 'dir')
    mkdir(figures_dir);
end

% Get all open figure handles
fig_handles = findobj('Type', 'figure');

% Save each figure as PNG (600 dpi)
for i = 1:length(fig_handles)
    fig = fig_handles(i);
    fig_name = fig.Name;
    if isempty(fig_name) || strcmp(fig_name, 'Figure 1')  % fallback
        fig_name = sprintf('figure_%d', i);
    end
    
    % Remove invalid filename characters
    fig_name = regexprep(fig_name, '[\\/:*?"<>|]', '_');
    
    png_path = fullfile(figures_dir, [fig_name, '.png']);
    exportgraphics(fig, png_path, 'Resolution', 600, 'ContentType', 'auto');
    
    fprintf('Saved: %s.png\n', fig_name);
end

fprintf('\nAll figures saved to:\n%s\n', figures_dir);

%% ==== Helper Plotting Functions ====

function plot_trend_figure(m_dom, m_sub, s_dom, s_sub, p_raw, time_min, labels, sgtitle_str, ylabel_str, ~)
    color_dom = [0.2 0.4 0.6]; color_sub = [0.9 0.6 0.1];
    n_beh = length(labels);
    n_rows = ceil(sqrt(n_beh)); n_cols = ceil(n_beh / n_rows);
    
    figure('Name', 'Raw Duration Trend', 'Color', 'w', 'Position', [50, 50, 500*n_cols, 400*n_rows]);
    for beh = 1:n_beh
        subplot(n_rows, n_cols, beh); hold on; box on; grid on;
        md = squeeze(m_dom(1, beh, :))'; ms = squeeze(m_sub(1, beh, :))';
        sd = squeeze(s_dom(1, beh, :))'; ss = squeeze(s_sub(1, beh, :))';
        pb = squeeze(p_raw(1, beh, :))';
        
        plot(time_min, md, '-', 'Color', color_dom, 'LineWidth', 2, 'DisplayName', 'Dom');
        fill([time_min, fliplr(time_min)], [md+sd, fliplr(md-sd)], color_dom, 'FaceAlpha', 0.12, 'EdgeColor', 'none', 'HandleVisibility', 'off');
        plot(time_min, ms, '-', 'Color', color_sub, 'LineWidth', 2, 'DisplayName', 'Sub');
        fill([time_min, fliplr(time_min)], [ms+ss, fliplr(ms-ss)], color_sub, 'FaceAlpha', 0.12, 'EdgeColor', 'none', 'HandleVisibility', 'off');
        
        % Significance (single file - no stars)
        xlabel('Time (min)'); ylabel(ylabel_str);
        title(labels{beh}, 'Interpreter', 'none');
        xlim([0, max(time_min) + 5]);
        max_val = max([md+sd; ms+ss]);
        ylim([0, max(max(max_val * 1.15),1)]);
        
        legend({'Dom', 'Sub'}, 'Location', 'best', 'FontSize', 8, 'Interpreter', 'none');
        hold off;
    end
    sgtitle(sgtitle_str, 'FontSize', 14, 'FontWeight', 'bold');
end

function plot_cumulative_figure(m_dom, m_sub, s_dom, s_sub, p_raw, time_min, labels, sgtitle_str, ylabel_str, ~)
    color_dom = [0.2 0.4 0.6]; color_sub = [0.9 0.6 0.1];
    n_beh = length(labels);
    n_rows = ceil(sqrt(n_beh)); n_cols = ceil(n_beh / n_rows);
    
    figure('Name', 'Cumulative Duration Trend', 'Color', 'w', 'Position', [50, 50, 500*n_cols, 400*n_rows]);
    for beh = 1:n_beh
        subplot(n_rows, n_cols, beh); hold on; box on; grid on;
        md = squeeze(m_dom(1, beh, :))'; ms = squeeze(m_sub(1, beh, :))';
        sd = squeeze(s_dom(1, beh, :))'; ss = squeeze(s_sub(1, beh, :))';
        pb = squeeze(p_raw(1, beh, :))';
        
        md_cum = cumsum(md); ms_cum = cumsum(ms);
        sd_cum = sqrt(cumsum(sd.^2)); ss_cum = sqrt(cumsum(ss.^2));
        
        plot(time_min, md_cum, '-', 'Color', color_dom, 'LineWidth', 2, 'DisplayName', 'Dom');
        fill([time_min, fliplr(time_min)], [md_cum+sd_cum, fliplr(md_cum-sd_cum)], color_dom, 'FaceAlpha', 0.12, 'HandleVisibility', 'off');
        plot(time_min, ms_cum, '-', 'Color', color_sub, 'LineWidth', 2, 'DisplayName', 'Sub');
        fill([time_min, fliplr(time_min)], [ms_cum+ss_cum, fliplr(ms_cum-ss_cum)], color_sub, 'FaceAlpha', 0.12, 'HandleVisibility', 'off');
        
        xlabel('Time (min)'); ylabel(ylabel_str);
        title(labels{beh}, 'Interpreter', 'none');
        xlim([0, max(time_min) + 5]);
        max_val = max([md_cum+sd_cum; ms_cum+ss_cum]);
        ylim([0, max(max(max_val * 1.05), 1)]);
        
        legend({'Dom', 'Sub'}, 'Location', 'best', 'FontSize', 8, 'Interpreter', 'none');
        hold off;
    end
    sgtitle(sgtitle_str, 'FontSize', 14, 'FontWeight', 'bold');
end