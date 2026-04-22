clear all;
close all;
clc;

%% ==== Configuration ====
fps = 10;
min_frames = 10;
bin_min = 10;                          % Bin size in minutes for trend plot
binSize = bin_min * 60 * fps;         % Frames per bin
min_bout_frames = 5;                  % Minimum frames to count as a bout

custom_str_header = " (SE + Mating)";

root_dir = uigetdir('', 'Select Root Folder to Search for .mat Files');
if root_dir == 0
    disp('No folder selected. Exiting.');
    return;
end

% === Ask user for time range in minutes ===
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

% Find all .mat files recursively
mat_files = getAllMatFiles(root_dir);
n_files = length(mat_files);

if n_files == 0
    error('No .mat files found in "%s" or subfolders.', root_dir);
end

fprintf('Found %d .mat files. Starting batch_mode processing...\n', n_files);
log_file = fullfile(root_dir, 'batch_mode_processing_log.txt');
fid = fopen(log_file, 'w');
fclose(fid);

%% ==== Pre-allocate for trend data ====
% Determine max frames
max_frames = 0;
for i = 1:n_files
    try
        S_test = load(mat_files{i});
        if isfield(S_test, 'annotation')
            max_frames = max(max_frames, length(S_test.annotation.annotation));
            behaviors = S_test.annotation.behaviors;
        end
    catch
    end
end

% ==== Define and Reorder Behavior Types ====
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

% Store individual file metrics (Duration based)
individual_metrics = zeros(n_files, n_beh);
raw_counts_dom = zeros(n_files, n_beh);
raw_counts_sub = zeros(n_files, n_beh);

% Store BOUT COUNTS
bout_counts_dom = zeros(n_files, n_beh);
bout_counts_sub = zeros(n_files, n_beh);
individual_metrics_bouts = zeros(n_files, n_beh); 

dom_colors = []; 
colors_initialized = false;

n_bins = ceil(max_frames / binSize);

% Trend arrays for Duration (Frames)
trend_dom = NaN(n_files, n_beh, n_bins);
trend_sub = NaN(n_files, n_beh, n_bins);

% Trend arrays for BOUT COUNTS
trend_bouts_dom = NaN(n_files, n_beh, n_bins);
trend_bouts_sub = NaN(n_files, n_beh, n_bins);

% === NEW: Trend arrays for MEAN BOUT LENGTH (Frames) ===
trend_bout_len_dom = NaN(n_files, n_beh, n_bins);
trend_bout_len_sub = NaN(n_files, n_beh, n_bins);

%% ==== Process each file ====
for i = 1:n_files
    mat_path = mat_files{i};
    [~, name, ~] = fileparts(mat_path);
    fprintf('\n[%d/%d] Processing: %s\n', i, n_files, name);
    
    % try
        S = load(mat_path);
        
        if isfield(S, 'annotation')
            behaviors = S.annotation.behaviors;
            annot = int32(S.annotation.annotation);
        else
            error('MAT file missing ''annotation'' field.');
        end

        has_zone_data = false;
        zone_sum = [];
        
        if isfield(S, 'stat') && isfield(S.stat, 'sum')
            zone_sum = int32(S.stat.sum);
            has_zone_data = true;
            min_len = min(length(annot), length(zone_sum));
            annot = annot(1:min_len);
            zone_sum = zone_sum(1:min_len);
        end
     
        % === Apply time range selection (for overall metrics only) ===
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
                
        % Initialize colors
        if ~colors_initialized
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
            colors_initialized = true;
        end
        
        % Calculate Overall Metrics
        for b = 1:n_beh
            beh_name = behavior_types{b};
            
            % --- HANDLE ZONE BEHAVIORS ---
            if b == 1  % 'cage'
                if has_zone_data && ~isempty(zone_subset)
                    dom_count = sum(zone_subset == 1 | zone_subset == 2);
                    sub_count = sum(zone_subset == 3 | zone_subset == 4);
                    dom_bouts = extract_zone_bout_durations(zone_subset', 1, 2, min_bout_frames);
                    sub_bouts = extract_zone_bout_durations(zone_subset', 3, 4, min_bout_frames);
                else
                    dom_count = 0; sub_count = 0;
                    dom_bouts = []; sub_bouts = [];
                end
                
            elseif b == 2  % 'interact'
                if has_zone_data && ~isempty(zone_subset)
                    dom_count = sum(zone_subset == 2);
                    sub_count = sum(zone_subset == 4);
                    dom_bouts = extract_zone_bout_durations(zone_subset', 2, -1, min_bout_frames);
                    sub_bouts = extract_zone_bout_durations(zone_subset', 4, -1, min_bout_frames);
                else
                    dom_count = 0; sub_count = 0;
                    dom_bouts = []; sub_bouts = [];
                end
                
            else
                % --- REGULAR BEHAVIORS ---
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

                dom_bouts = extract_bout_durations(annot_subset, dom_val, min_bout_frames);
                sub_bouts = extract_bout_durations(annot_subset, sub_val, min_bout_frames);
            end
            
            % STORE DURATION COUNTS
            raw_counts_dom(i, b) = dom_count;
            raw_counts_sub(i, b) = sub_count;
            
            % STORE BOUT COUNTS
            n_dom_bouts = numel(dom_bouts);
            n_sub_bouts = numel(sub_bouts);
            bout_counts_dom(i, b) = n_dom_bouts;
            bout_counts_sub(i, b) = n_sub_bouts;
            
            % Calculate Preference Indices
            if (dom_count + sub_count) > min_frames
                individual_metrics(i, b) = (dom_count - sub_count) / (dom_count + sub_count);
            else
                individual_metrics(i, b) = NaN;
            end
            
            if (n_dom_bouts + n_sub_bouts) > 0
                individual_metrics_bouts(i, b) = (n_dom_bouts - n_sub_bouts) / (n_dom_bouts + n_sub_bouts);
            else
                individual_metrics_bouts(i, b) = NaN;
            end
        end
        
        % === TREND METRIC: ALWAYS use FULL annot array ===
        effective_frames = length(annot);
        n_bins_actual = ceil(effective_frames / binSize);
        
        for b = 1:n_beh
            beh_name = behavior_types{b};
            
            % --- ZONE: Cage ---
            if b == 1 
                for bin = 1:n_bins_actual
                    start_idx = (bin-1)*binSize + 1;
                    end_idx = min(bin*binSize, effective_frames);
                    if start_idx > effective_frames, break; end
                    
                    if has_zone_data
                        bin_zone = zone_sum(start_idx:end_idx);
                        % Duration
                        trend_dom(i, b, bin) = sum(bin_zone == 1 | bin_zone == 2);
                        trend_sub(i, b, bin) = sum(bin_zone == 3 | bin_zone == 4);
                        % Bout Count
                        trend_bouts_dom(i, b, bin) = count_zone_bouts_in_bin(bin_zone', 1, 2, min_bout_frames);
                        trend_bouts_sub(i, b, bin) = count_zone_bouts_in_bin(bin_zone', 3, 4, min_bout_frames);
                        % Mean Bout Length
                        lens_dom = get_zone_bout_lengths_in_bin(bin_zone', 1, 2, min_bout_frames);
                        lens_sub = get_zone_bout_lengths_in_bin(bin_zone', 3, 4, min_bout_frames);
                        trend_bout_len_dom(i, b, bin) = mean(lens_dom);
                        trend_bout_len_sub(i, b, bin) = mean(lens_sub);
                    end
                end
                
            % --- ZONE: Interact ---
            elseif b == 2 
                for bin = 1:n_bins_actual
                    start_idx = (bin-1)*binSize + 1;
                    end_idx = min(bin*binSize, effective_frames);
                    if start_idx > effective_frames, break; end
                    
                    if has_zone_data
                        bin_zone = zone_sum(start_idx:end_idx);
                        % Duration
                        trend_dom(i, b, bin) = sum(bin_zone == 2);
                        trend_sub(i, b, bin) = sum(bin_zone == 4);
                        % Bout Count
                        trend_bouts_dom(i, b, bin) = count_zone_bouts_in_bin(bin_zone', 2, -1, min_bout_frames);
                        trend_bouts_sub(i, b, bin) = count_zone_bouts_in_bin(bin_zone', 4, -1, min_bout_frames);
                        % Mean Bout Length
                        lens_dom = get_zone_bout_lengths_in_bin(bin_zone', 2, -1, min_bout_frames);
                        lens_sub = get_zone_bout_lengths_in_bin(bin_zone', 4, -1, min_bout_frames);
                        trend_bout_len_dom(i, b, bin) = mean(lens_dom);
                        trend_bout_len_sub(i, b, bin) = mean(lens_sub);
                    end
                end
            
            % --- REGULAR BEHAVIORS ---
            else
                dom_field = 'dom_'+beh_name;
                sub_field = 'sub_'+beh_name;
                dom_val = []; sub_val = [];
                if isfield(behaviors, dom_field), dom_val = behaviors.(dom_field); end
                if isfield(behaviors, sub_field), sub_val = behaviors.(sub_field); end
                
                for bin = 1:n_bins_actual
                    start_idx = (bin-1)*binSize + 1;
                    end_idx = min(bin*binSize, effective_frames);
                    if start_idx > effective_frames, break; end
                    
                    bin_annot = annot(start_idx:end_idx);
                    
                    % Duration
                    trend_dom(i, b, bin) = sum(bin_annot == dom_val);
                    trend_sub(i, b, bin) = sum(bin_annot == sub_val);
                    
                    % Bout Count
                    trend_bouts_dom(i, b, bin) = count_bouts_in_bin(bin_annot, dom_val, min_bout_frames);
                    trend_bouts_sub(i, b, bin) = count_bouts_in_bin(bin_annot, sub_val, min_bout_frames);
                    
                    % Mean Bout Length
                    lens_dom = get_bout_lengths_in_bin(bin_annot, dom_val, min_bout_frames);
                    lens_sub = get_bout_lengths_in_bin(bin_annot, sub_val, min_bout_frames);
                    
                    trend_bout_len_dom(i, b, bin) = mean(lens_dom);
                    trend_bout_len_sub(i, b, bin) = mean(lens_sub);
                end
            end
        end
        
        logMessage(log_file, sprintf('SUCCESS: %s', mat_path));
        
    % catch ME
    %     warn_msg = sprintf('FAILED: %s | Error: %s', mat_path, ME.message);
    %     warning(warn_msg);
    %     logMessage(log_file, warn_msg);
    %     % Fill NaNs on error
    %     individual_metrics(i, :) = NaN;
    %     individual_metrics_bouts(i, :) = NaN;
    %     trend_dom(i, :, :) = NaN; trend_bouts_dom(i, :, :) = NaN; trend_bout_len_dom(i, :, :) = NaN;
    %     trend_sub(i, :, :) = NaN; trend_bouts_sub(i, :, :) = NaN; trend_bout_len_sub(i, :, :) = NaN;
    % end
    
    fprintf('  → Done.\n');
end

if ~colors_initialized
    error('No valid files found to extract behavior colors.');
end

%% ==== Calculate Statistics: DURATION ====
mean_metrics = nanmean(individual_metrics, 1)';
mean_counts_dom = nanmean(raw_counts_dom, 1)';
mean_counts_sub = nanmean(raw_counts_sub, 1)';
sem_counts_dom = nanstd(raw_counts_dom, 0, 1)'/sqrt(n_files);
sem_counts_sub = nanstd(raw_counts_sub, 0, 1)'/sqrt(n_files);

p_vals = nan(n_beh, 1);
sem_metrics = nan(n_beh, 1);
for b = 1:n_beh
    vals = individual_metrics(:, b);
    vals = vals(~isnan(vals));
    if numel(vals) >= 2
        [~, p_vals(b)] = ttest(vals, 0);
        sem_metrics(b) = std(vals) / sqrt(numel(vals));
    elseif numel(vals) == 1
        sem_metrics(b) = 0; p_vals(b) = NaN;
    end
end

%% ==== Calculate Statistics: BOUT COUNTS ====
mean_metrics_bouts = nanmean(individual_metrics_bouts, 1)';
mean_bouts_dom = nanmean(bout_counts_dom, 1)';
mean_bouts_sub = nanmean(bout_counts_sub, 1)';
sem_bouts_dom = nanstd(bout_counts_dom, 0, 1)'/sqrt(n_files);
sem_bouts_sub = nanstd(bout_counts_sub, 0, 1)'/sqrt(n_files);

p_vals_bouts = nan(n_beh, 1);
sem_metrics_bouts = nan(n_beh, 1);
for b = 1:n_beh
    vals = individual_metrics_bouts(:, b);
    vals = vals(~isnan(vals));
    if numel(vals) >= 2
        [~, p_vals_bouts(b)] = ttest(vals, 0);
        sem_metrics_bouts(b) = std(vals) / sqrt(numel(vals));
    elseif numel(vals) == 1
        sem_metrics_bouts(b) = 0; p_vals_bouts(b) = NaN;
    end
end

%% ==== Vectorized Statistics: TRENDS (Duration) ====
trend_dom_clean = trend_dom; trend_dom_clean(isnan(trend_dom_clean)) = 0;
trend_sub_clean = trend_sub; trend_sub_clean(isnan(trend_sub_clean)) = 0;
trend_dom_mean = mean(trend_dom_clean, 1);
trend_sub_mean = mean(trend_sub_clean, 1);
n_files_valid = size(trend_dom_clean, 1);
trend_dom_sem = std(trend_dom_clean, 0, 1) / sqrt(n_files_valid);
trend_sub_sem = std(trend_sub_clean, 0, 1) / sqrt(n_files_valid);

trend_p = nan(1, n_beh, n_bins);
for b = 1:n_beh
    for bin = 1:n_bins
        dom_vals = squeeze(trend_dom_clean(:, b, bin));
        sub_vals = squeeze(trend_sub_clean(:, b, bin));
        if numel(dom_vals) >= 2
            [~, trend_p(1, b, bin)] = ttest(dom_vals, sub_vals);
        end
    end
end

%% ==== Vectorized Statistics: TRENDS (Bout Counts) ====
trend_bouts_dom_clean = trend_bouts_dom; trend_bouts_dom_clean(isnan(trend_bouts_dom_clean)) = 0;
trend_bouts_sub_clean = trend_bouts_sub; trend_bouts_sub_clean(isnan(trend_bouts_sub_clean)) = 0;
trend_bouts_dom_mean = mean(trend_bouts_dom_clean, 1);
trend_bouts_sub_mean = mean(trend_bouts_sub_clean, 1);
trend_bouts_dom_sem = std(trend_bouts_dom_clean, 0, 1) / sqrt(n_files_valid);
trend_bouts_sub_sem = std(trend_bouts_sub_clean, 0, 1) / sqrt(n_files_valid);

trend_bouts_p = nan(1, n_beh, n_bins);
for b = 1:n_beh
    for bin = 1:n_bins
        dom_vals = squeeze(trend_bouts_dom_clean(:, b, bin));
        sub_vals = squeeze(trend_bouts_sub_clean(:, b, bin));
        if numel(dom_vals) >= 2
            [~, trend_bouts_p(1, b, bin)] = ttest(dom_vals, sub_vals);
        end
    end
end

%% ==== Vectorized Statistics: TRENDS (Mean Bout Length) ====
% Note: We do NOT replace NaN with 0 here, because 0 length is impossible. 
% NaN means no bouts occurred. We use 'omitnan' in mean calculation.
trend_len_dom_mean = nanmean(trend_bout_len_dom, 1);
trend_len_sub_mean = nanmean(trend_bout_len_sub, 1);
trend_len_dom_sem = nanstd(trend_bout_len_dom, 0, 1) / sqrt(n_files_valid);
trend_len_sub_sem = nanstd(trend_bout_len_sub, 0, 1) / sqrt(n_files_valid);

trend_len_p = nan(1, n_beh, n_bins);
for b = 1:n_beh
    for bin = 1:n_bins
        dom_vals = squeeze(trend_bout_len_dom(:, b, bin));
        sub_vals = squeeze(trend_bout_len_sub(:, b, bin));
        % Remove NaNs for t-test
        valid = ~isnan(dom_vals) & ~isnan(sub_vals);
        if sum(valid) >= 2
            [~, trend_len_p(1, b, bin)] = ttest(dom_vals(valid), sub_vals(valid));
        end
    end
end


x = 1:n_beh;               
lighten_factor = 0.4;      
time_min = (0:n_bins-1 + 0.5) * ((binSize / fps) / 60); 

%% ==== Plot 0A: Raw Frame Counts (Duration) ====
fprintf('\nCreating raw frame counts plot (Duration)...\n');

% --- Subplot 1: Cage behavior (log scale) ---
ax1 = subplot(1, 2, 1);
plot_grouped_bar(1, mean_counts_dom(1), mean_counts_sub(1), ...
    sem_counts_dom(1), sem_counts_sub(1), raw_counts_dom(:,1), raw_counts_sub(:,1), ...
    dom_colors(1,:), lighten_factor, behavior_types(1), ...
    '', '', false, true);
set(gca);
current_ylim = ylim;
ylim([max([current_ylim(1), 0.1]), current_ylim(2) * 1.2]);
ylabel('Frame Count');

% --- Subplot 2: Other behaviors (linear scale) ---
ax2 = subplot(1, 2, 2);
plot_grouped_bar(1:(n_beh-1), mean_counts_dom(2:end), mean_counts_sub(2:end), ...
    sem_counts_dom(2:end), sem_counts_sub(2:end), ...
    raw_counts_dom(:,2:end), raw_counts_sub(:,2:end), ...
    dom_colors(2:end,:), lighten_factor, behavior_types(2:end), ...
    '', '', false, false);
xtickangle(45);

% === ADJUST SUBPLOT WIDTHS ===
% Get figure normalized units for positioning
fig_pos = get(gcf, 'Position');
fig_width = fig_pos(3);

% Define margins and spacing (in pixels)
left_margin = 40;      % left edge of fig
right_margin = 40;     % right edge of fig
gap = 0;              % space between subplots
cage_width = 90;      % narrow width for cage subplot (pixels)

% Convert to normalized units [left bottom width height]
ax1_pos = [left_margin/fig_width, 0.15, cage_width/fig_width, 0.75];
ax2_pos = [(left_margin + cage_width + gap)/fig_width, 0.15, ...
           (fig_width - left_margin - cage_width - gap - right_margin)/fig_width, 0.75];

set(ax1, 'Position', ax1_pos);
set(ax2, 'Position', ax2_pos);

sgtitle(['Raw Frame Counts (Duration)' portion_str], 'FontSize', 14, 'FontWeight', 'bold');
sgtitle(['Raw Frame Counts (Duration)' portion_str], 'FontSize', 14, 'FontWeight', 'bold');

%% ==== Plot 0B: Raw Bout Counts ====
fprintf('\nCreating raw bout counts plot...\n');
figure('Name', 'Batch Mode: Raw Bout Counts', 'Position', [300, 300, 950, 500]);
plot_grouped_bar(x, mean_bouts_dom, mean_bouts_sub, sem_bouts_dom, sem_bouts_sub, ...
    bout_counts_dom, bout_counts_sub, dom_colors, lighten_factor, behavior_types, ...
    ['Raw Bout Counts' portion_str], 'Number of Bouts', true, false);

%% ==== Plot 1A: Preference Index (Duration) ====
fprintf('\nCreating overall preference index plot (Duration)...\n');
figure('Name', 'Batch Mode: PI (Duration)', 'Position', [300, 300, 950, 500]);
plot_pi_chart(x, mean_metrics, sem_metrics, individual_metrics, p_vals, ...
    dom_colors, behavior_types, ['Preference Index (Duration)' portion_str], true);

%% ==== Plot 1B: Preference Index (Bout Counts) ====
fprintf('\nCreating overall preference index plot (Bout Counts)...\n');
figure('Name', 'Batch Mode: PI (Bout Counts)', 'Position', [300, 300, 950, 500]);
plot_pi_chart(x, mean_metrics_bouts, sem_metrics_bouts, individual_metrics_bouts, p_vals_bouts, ...
    dom_colors, behavior_types, ['Preference Index (Bout Counts)' portion_str], true);

%% ==== Plot 2A: Raw Duration Trend ====
fprintf('Generating raw duration trend plot...\n');
plot_trend_figure(trend_dom_mean, trend_sub_mean, trend_dom_sem, trend_sub_sem, trend_p, ...
    time_min, behavior_types, 'Raw Duration Trend: Dom vs Sub', 'Duration (frames)', false);

%% ==== Plot 2B: Raw Bout Count Trend ====
fprintf('Generating raw bout count trend plot...\n');
plot_trend_figure(trend_bouts_dom_mean, trend_bouts_sub_mean, trend_bouts_dom_sem, trend_bouts_sub_sem, trend_bouts_p, ...
    time_min, behavior_types, 'Raw Bout Count Trend: Dom vs Sub', 'Number of Bouts', false);

%% ==== Plot 3A: Cumulative Duration Trend ====
fprintf('Generating cumulative duration trend plot...\n');
plot_cumulative_figure(trend_dom_mean, trend_sub_mean, trend_dom_sem, trend_sub_sem, trend_p, ...
    time_min, behavior_types, 'Cumulative Duration Trend', 'Cumulative Duration (frames)', false);

%% ==== Plot 3B: Cumulative Bout Count Trend ====
fprintf('Generating cumulative bout count trend plot...\n');
plot_cumulative_figure(trend_bouts_dom_mean, trend_bouts_sub_mean, trend_bouts_dom_sem, trend_bouts_sub_sem, trend_bouts_p, ...
    time_min, behavior_types, 'Cumulative Bout Count Trend', 'Cumulative Bout Count', false);

%% ==== Plot 4: Mean Bout Length Trend (NEW) ====
fprintf('Generating mean bout length trend plot...\n');
plot_trend_figure(trend_len_dom_mean, trend_len_sub_mean, trend_len_dom_sem, trend_len_sub_sem, trend_len_p, ...
    time_min, behavior_types, 'Mean Bout Duration Over Time', 'Avg Bout Length (frames)', false);

fprintf('\nBatch mode complete!\n');

%% ==== Helper Plotting Functions ====

function plot_grouped_bar(x, m_dom, m_sub, s_dom, s_sub, raw_dom, raw_sub, colors, light_fac, labels, title_str, ylabel_str, add_sep, no_legend)
    hold on; box on; grid on;
    width = 0.35;
    x_dom = x - width/2;
    x_sub = x + width/2;
    n_beh = length(x);
    n_files = size(raw_dom, 1);
    
    for b = 1:n_beh
        sub_color = colors(b,:) + (1 - colors(b,:)) * light_fac;
        bar(x_dom(b), m_dom(b), width, 'FaceColor', colors(b,:), 'EdgeColor', 'k', 'LineWidth', 0.5);
        errorbar(x_dom(b), m_dom(b), s_dom(b), 'k.', 'HandleVisibility', 'off');
        bar(x_sub(b), m_sub(b), width, 'FaceColor', sub_color, 'EdgeColor', 'k', 'LineWidth', 0.5);
        errorbar(x_sub(b), m_sub(b), s_sub(b), 'k.', 'HandleVisibility', 'off');
    end
    
    if add_sep, xline(2.5, '-', 'Color', 'black', 'LineWidth', 1, 'HandleVisibility', 'off'); end
    
    rng(0); jitter_amount = 0.15;
    x_dom_jit = NaN(n_files, n_beh); x_sub_jit = NaN(n_files, n_beh);
    for b = 1:n_beh
        d_val = ~isnan(raw_dom(:, b)); s_val = ~isnan(raw_sub(:, b));
        if any(d_val), x_dom_jit(d_val, b) = x_dom(b) + (rand(sum(d_val), 1) - 0.5) * jitter_amount * 2; end
        if any(s_val), x_sub_jit(s_val, b) = x_sub(b) + (rand(sum(s_val), 1) - 0.5) * jitter_amount * 2; end
    end
    
    for b = 1:n_beh
        for i = 1:n_files
            if ~isnan(raw_dom(i,b)) && ~isnan(raw_sub(i,b)) && ~isnan(x_dom_jit(i,b)) && ~isnan(x_sub_jit(i,b))
                plot([x_dom_jit(i,b), x_sub_jit(i,b)], [raw_dom(i,b), raw_sub(i,b)], ...
                    '-', 'Color', [0.7 0.7 0.7], 'LineWidth', 0.8, 'HandleVisibility', 'off');
            end
        end
    end
    
    for b = 1:n_beh
        sub_color = colors(b,:) + (1 - colors(b,:)) * light_fac;
        d_val = raw_dom(:, b); v = ~isnan(d_val);
        if any(v), scatter(x_dom_jit(v,b), d_val(v), 40, colors(b,:), 'filled', 'MarkerEdgeColor', 'k'); end
        s_val = raw_sub(:, b); v = ~isnan(s_val);
        if any(v), scatter(x_sub_jit(v,b), s_val(v), 40, sub_color, 'filled', 'MarkerEdgeColor', 'k'); end
    end
    
    for b = 1:n_beh
        d_v = raw_dom(:, b); s_v = raw_sub(:, b); v = ~isnan(d_v) & ~isnan(s_v);
        if sum(v) >= 2
            [~, p_val] = ttest(d_v(v), s_v(v));
            if ~isnan(p_val)
                y_top = max([m_dom(b)+s_dom(b), m_sub(b)+s_sub(b)]) + 0.08 * max([m_dom(b), m_sub(b)]);
                add_sig_bracket(x_dom(b), x_sub(b), y_top, p_val);
            end
        end
    end
    hold off;
    ylabel(ylabel_str);
    set(gca, 'XTick', x, 'XTickLabel', labels, 'TickLabelInterpreter', 'none'); xtickangle(45);
    title(title_str, 'Interpreter', 'none');
    if ~no_legend
        legend({'Dominant', 'Subordinate'}, 'Location', 'best', 'Interpreter', 'none');
    end
end

function plot_pi_chart(x, m, s, individual, p_vals, colors, labels, title_str, add_sep)
    hold on; box on; grid on;
    width = 0.6;
    for b = 1:length(x)
        bar(x(b), m(b), width, 'FaceColor', colors(b,:), 'EdgeColor', 'k', 'LineWidth', 0.5);
        errorbar(x(b), m(b), s(b), 'k.', 'HandleVisibility', 'off');
    end
    if add_sep, xline(2.5, '-', 'Color', 'black', 'LineWidth', 1, 'HandleVisibility', 'off'); end
    
    rng(0); jitter_amount = 0.15;
    for b = 1:length(x)
        fv = individual(:, b); v = ~isnan(fv);
        if any(v)
            x_j = x(b) + (rand(sum(v), 1) - 0.5) * jitter_amount * 2;
            scatter(x_j, fv(v), 40, colors(b,:), 'filled', 'MarkerEdgeColor', 'k');
        end
    end
    
    for b = 1:length(x)
        if ~isnan(p_vals(b)) && ~isnan(m(b))
            y_top = m(b) + s(b) + 0.08;
            add_sig_bracket(x(b), x(b), y_top, p_vals(b));
        end
    end
    hold off;
    ylabel('(Dom - Sub) / (Dom + Sub)');
    set(gca, 'XTick', x, 'XTickLabel', labels, 'TickLabelInterpreter', 'none'); xtickangle(45);
    title(title_str, 'Interpreter', 'none');
    ylim([-1, 1]);
end

function plot_trend_figure(m_dom, m_sub, s_dom, s_sub, p_raw, time_min, labels, sgtitle_str, ylabel_str, ~)
    color_dom = [0.2 0.4 0.6]; color_sub = [0.9 0.6 0.1];
    n_beh = length(labels);
    n_rows = ceil(sqrt(n_beh)); n_cols = ceil(n_beh / n_rows);
    
    figure('Name', sgtitle_str, 'Color', 'w', 'Position', [50, 50, 500*n_cols, 400*n_rows]);
    for beh = 1:n_beh
        subplot(n_rows, n_cols, beh); hold on; box on; grid on;
        md = squeeze(m_dom(1, beh, :))'; ms = squeeze(m_sub(1, beh, :))';
        sd = squeeze(s_dom(1, beh, :))'; ss = squeeze(s_sub(1, beh, :))';
        pb = squeeze(p_raw(1, beh, :))';
        
        plot(time_min, md, '-', 'Color', color_dom, 'LineWidth', 2, 'DisplayName', 'Dom');
        fill([time_min, fliplr(time_min)], [md+sd, fliplr(md-sd)], color_dom, 'FaceAlpha', 0.12, 'EdgeColor', 'none', 'HandleVisibility', 'off');
        plot(time_min, ms, '-', 'Color', color_sub, 'LineWidth', 2, 'DisplayName', 'Sub');
        fill([time_min, fliplr(time_min)], [ms+ss, fliplr(ms-ss)], color_sub, 'FaceAlpha', 0.12, 'EdgeColor', 'none', 'HandleVisibility', 'off');
        
        % Significance
        vp = ~isnan(pb);
        if sum(vp) > 1
            [~, ~, p_adj] = fdr_bh(pb(vp));
            pc = nan(size(pb)); pc(vp) = p_adj;
        else
            pc = pb;
        end
        sig_idx = find(pc < 0.05 & ~isnan(pc));
        if ~isempty(sig_idx)
            for si = sig_idx
                y_max = max([md(si)+sd(si), ms(si)+ss(si)]);
                plot(time_min(si), y_max, '*', 'Color', 'k', 'MarkerSize', 14, 'MarkerFaceColor', 'k');
            end
        end
        
        xlabel('Time (min)'); ylabel(ylabel_str);
        title(labels{beh}, 'Interpreter', 'none');
        xlim([0, 720]);
        max_val = max([md+sd; ms+ss]);
        ylim([0, max(max(max_val * 1.15),1)]);
        
        if ~isempty(sig_idx)
            legend({'Dom', 'Sub', '★ p<0.05'}, 'Location', 'best', 'FontSize', 8, 'Interpreter', 'none');
        else
            legend({'Dom', 'Sub'}, 'Location', 'best', 'FontSize', 8, 'Interpreter', 'none');
        end
        hold off;
    end
    sgtitle(sgtitle_str, 'FontSize', 14, 'FontWeight', 'bold');
end

function plot_cumulative_figure(m_dom, m_sub, s_dom, s_sub, p_raw, time_min, labels, sgtitle_str, ylabel_str, ~)
    color_dom = [0.2 0.4 0.6]; color_sub = [0.9 0.6 0.1];
    n_beh = length(labels);
    n_rows = ceil(sqrt(n_beh)); n_cols = ceil(n_beh / n_rows);
    
    figure('Name', sgtitle_str, 'Color', 'w', 'Position', [50, 50, 500*n_cols, 400*n_rows]);
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
        
        vp = ~isnan(pb);
        if sum(vp) > 1
            [~, ~, p_adj] = fdr_bh(pb(vp));
            pc = nan(size(pb)); pc(vp) = p_adj;
        else
            pc = pb;
        end
        sig_idx = find(pc < 0.05 & ~isnan(pc));
        if ~isempty(sig_idx)
            for si = sig_idx
                y_max = max([md_cum(si)+sd_cum(si), ms_cum(si)+ss_cum(si)]);
                plot(time_min(si), y_max, '*', 'Color', 'k', 'MarkerSize', 14, 'MarkerFaceColor', 'k');
            end
        end
        
        xlabel('Time (min)'); ylabel(ylabel_str);
        title(labels{beh}, 'Interpreter', 'none');
        xlim([0, 720]);
        max_val = max([md_cum+sd_cum; ms_cum+ss_cum]);
        ylim([0, max(max(max_val * 1.05), 1)]);
        
        if ~isempty(sig_idx)
            legend({'Dom', 'Sub', '★ p<0.05'}, 'Location', 'best', 'FontSize', 8, 'Interpreter', 'none');
        else
            legend({'Dom', 'Sub'}, 'Location', 'best', 'FontSize', 8, 'Interpreter', 'none');
        end
        hold off;
    end
    sgtitle(sgtitle_str, 'FontSize', 14, 'FontWeight', 'bold');
end

%% ==== Existing Helper Functions ====
function label = pval2sig(p)
    if isnan(p), label = 'N/A';
    elseif p < 0.001, label = sprintf('%.3f\n***', p);
    elseif p < 0.01, label = sprintf('%.3f\n**', p);
    elseif p < 0.05, label = sprintf('%.3f\n*', p);
    else, label = sprintf('%.3f\nns', p);
    end
end

function add_sig_bracket(x1, x2, y_line, pval, varargin)
    plot([x1, x2], [y_line, y_line], 'k-', 'LineWidth', 1.5);
    plot([x1, x1], [y_line, y_line + 0.02], 'k-', 'LineWidth', 1.5);
    plot([x2, x2], [y_line, y_line + 0.02], 'k-', 'LineWidth', 1.5);
    ax = gca; ylims = ax.YLim; y_range = diff(ylims);
    y_margin = 0.03 * y_range; y_text = y_line + 0.6 * y_margin;
    label = pval2sig(pval);
    text((x1+x2)/2, y_text, label, 'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'bottom', 'FontWeight', 'bold', 'FontSize', 10, 'Color', 'k', varargin{:});
end

function files = getAllMatFiles(root)
    files = {};
    dirs = dir(fullfile(root, '**', '*.mat'));
    for k = 1:length(dirs)
        if ~dirs(k).isdir
            files{end+1} = fullfile(dirs(k).folder, dirs(k).name);
        end
    end
end

function logMessage(logFile, msg)
    fid = fopen(logFile, 'a');
    if fid == -1, error('Could not open log file: %s', logFile); end
    currentTime = datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss');
    fprintf(fid, '[%s] %s\n', string(currentTime), msg);
    fclose(fid);
end

function [h, s, adj_p] = fdr_bh(p_vals)
    p_vals = p_vals(:); m = length(p_vals);
    [sorted_p, sort_idx] = sort(p_vals);
    valid_idx = ~isnan(sorted_p);
    s_p = sorted_p(valid_idx); m_valid = sum(valid_idx);
    if m_valid == 0
        h = false(m, 1); s = zeros(m, 1); adj_p = ones(m, 1); adj_p(isnan(p_vals)) = NaN; return;
    end
    adj_p_sorted = zeros(m_valid, 1); adj_p_sorted(m_valid) = s_p(m_valid);
    for i = (m_valid-1):-1:1
        adj_p_sorted(i) = min(s_p(i) * m_valid / i, adj_p_sorted(i+1));
    end
    adj_p_sorted = min(adj_p_sorted, 1);
    adj_p = ones(m, 1); adj_p(sort_idx(valid_idx)) = adj_p_sorted; adj_p(isnan(p_vals)) = NaN;
    h = adj_p < 0.05; s = double(h);
end

function bouts = extract_bout_durations(annot_array, behavior_value, min_frames)
    if isempty(behavior_value) || behavior_value == 0, bouts = []; return; end
    is_behavior = (annot_array == behavior_value);
    d = diff([0; is_behavior; 0]);
    bout_starts = find(d == 1); bout_ends = find(d == -1) - 1;
    durations = bout_ends - bout_starts + 1;
    bouts = durations(durations >= min_frames);
end

function bouts = extract_zone_bout_durations(zone_array, behavior_value, secondary_value, min_frames)
    if isempty(behavior_value) || behavior_value == 0, bouts = []; return; end
    if secondary_value == -1
        is_behavior = (zone_array == behavior_value);
    else
        is_behavior = ismember(zone_array, [behavior_value, secondary_value]);
    end
    d = diff([0; is_behavior; 0]);
    bout_starts = find(d == 1); bout_ends = find(d == -1) - 1;
    durations = bout_ends - bout_starts + 1;
    bouts = durations(durations >= min_frames);
end

function count = count_bouts_in_bin(annot_array, behavior_value, min_frames)
    if isempty(behavior_value) || behavior_value == 0, count = 0; return; end
    is_behavior = (annot_array == behavior_value);
    d = diff([0; is_behavior; 0]);
    bout_starts = find(d == 1); bout_ends = find(d == -1) - 1;
    durations = bout_ends - bout_starts + 1;
    count = sum(durations >= min_frames);
end

function count = count_zone_bouts_in_bin(zone_array, behavior_value, secondary_value, min_frames)
    if isempty(behavior_value) || behavior_value == 0, count = 0; return; end
    if secondary_value == -1
        is_behavior = (zone_array == behavior_value);
    else
        is_behavior = ismember(zone_array, [behavior_value, secondary_value]);
    end
    d = diff([0; is_behavior; 0]);
    bout_starts = find(d == 1); bout_ends = find(d == -1) - 1;
    durations = bout_ends - bout_starts + 1;
    count = sum(durations >= min_frames);
end

% === NEW: Helper to return vector of bout lengths for averaging ===
function lengths = get_bout_lengths_in_bin(annot_array, behavior_value, min_frames)
    if isempty(behavior_value) || behavior_value == 0
        lengths = []; 
        return; 
    end
    is_behavior = (annot_array == behavior_value);
    d = diff([0; is_behavior(:); 0]);
    bout_starts = find(d == 1); 
    bout_ends = find(d == -1) - 1;
    
    if isempty(bout_starts)
        lengths = [];
        return;
    end
    
    durations = bout_ends - bout_starts + 1;
    % Filter by min_frames
    lengths = durations(durations >= min_frames);
end

function lengths = get_zone_bout_lengths_in_bin(zone_array, behavior_value, secondary_value, min_frames)
    if isempty(behavior_value) || behavior_value == 0
        lengths = []; 
        return; 
    end
    if secondary_value == -1
        is_behavior = (zone_array == behavior_value);
    else
        is_behavior = ismember(zone_array, [behavior_value, secondary_value]);
    end
    d = diff([0; is_behavior(:); 0]);
    bout_starts = find(d == 1); 
    bout_ends = find(d == -1) - 1;
    
    if isempty(bout_starts)
        lengths = [];
        return;
    end
    
    durations = bout_ends - bout_starts + 1;
    lengths = durations(durations >= min_frames);
end