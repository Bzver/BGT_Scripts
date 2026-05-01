clear all;
close all;

%% ==== Configuration ====
fps = 10;
pin_duration_seconds = 600;
fixed_frames = 18000;

root_dir = uigetdir('', 'Select Root Folder to Search for .mat Files');
if root_dir == 0
    disp('No folder selected. Exiting.');
    return;
end

group1_prefix = "NEX";
group2_prefix = "ctrl";

% Find all .mat files recursively
mat_files = getAllMatFiles(root_dir);
n_files = length(mat_files);

% Count files per group (Based on filenames for pre-allocation)
% Note: We use fileparts to ensure we check the filename, not the full path
n_group1_max = sum(startsWith(cellfun(@(x) fileparts(x), mat_files, 'UniformOutput', false), group1_prefix));
n_group2_max = sum(startsWith(cellfun(@(x) fileparts(x), mat_files, 'UniformOutput', false), group2_prefix));

if n_files == 0
    error('No .mat files found in "%s" or subfolders.', root_dir);
end

fprintf('Found %d .mat files (Max Group1: %d, Max Group2: %d). Starting batch_mode processing...\n', ...
    n_files, n_group1_max, n_group2_max);

log_file = fullfile(root_dir, 'batch_mode_processing_log.txt');
% Initialize log file
fid = fopen(log_file, 'w');
fclose(fid);

%% ==== Discover Behavior Types ====
% Load one file to determine behavior types and colors
% Find a valid file to peek
peek_idx = 1;
S = [];
while isempty(S) && peek_idx <= n_files
    try
        S = load(mat_files{peek_idx});
    catch
        peek_idx = peek_idx + 1;
    end
end

if isempty(S) || ~(isfield(S, 'annotation') && isfield(S.annotation, 'behaviors'))
    error('Could not find annotation.behaviors in any available file.');
end

behavior_types = fieldnames(S.annotation.behaviors); 
n_beh = numel(behavior_types);

% Set colors (use file colors if available, otherwise default)
if isfield(S, 'color')
    colors = S.color;
else
    colors = lines(n_beh); 
end

% Initialize Metric Matrices (Pre-allocate based on max possible files)
group1_metrics = zeros(n_group1_max, n_beh);
group2_metrics = zeros(n_group2_max, n_beh);

% Counters for filling the matrices (Actual valid files)
idx1 = 0;
idx2 = 0;

%% ==== Process Files ====
for i = 1:n_files
    mat_path = mat_files{i};
    [~, name, ~] = fileparts(mat_path);
    fprintf('\n[%d/%d] Processing: %s\n', i, n_files, name);

    % Determine Group (Do NOT increment index yet)
    group = 0;
    if startsWith(name, group1_prefix)
        group = 1;
    elseif startsWith(name, group2_prefix)
        group = 2;
    else
        logMessage(log_file, sprintf('SKIPPED (No Group Match): %s', mat_path));
        continue;
    end

    try
        S = load(mat_path);
        
        if isfield(S, 'annotation')
            behaviors = S.annotation.behaviors;
            annot = int32(S.annotation.annotation(:)) + 1; 
        else
            error('MAT file missing ''annotation'' field.');
        end

        % ==== CONSTRAINT 1: Exclude files shorter than fixed_frames ====
        if length(annot) < fixed_frames
            logMessage(log_file, sprintf('SKIPPED (Length %d < %d): %s', length(annot), fixed_frames, mat_path));
            continue; % Skip to next file, do NOT increment idx
        end

        % ==== CONSTRAINT 2: Truncate files longer than fixed_frames ====
        annot = annot(1:fixed_frames);

        % Now that data is valid, increment the specific group counter
        if group == 1
            idx1 = idx1 + 1;
        elseif group == 2
            idx2 = idx2 + 1;
        end

        % Calculate Metrics on the truncated data
        for b = 1:n_beh
            if group == 1
                group1_metrics(idx1, b) = sum(annot == b);
            elseif group == 2
                group2_metrics(idx2, b) = sum(annot == b);
            end
        end
        
        logMessage(log_file, sprintf('SUCCESS: %s (Frames: %d)', mat_path, length(annot)));
    catch ME
        warn_msg = sprintf('FAILED: %s | Error: %s', mat_path, ME.message);
        logMessage(log_file, warn_msg);
        fprintf('  → Error: %s\n', ME.message);
        continue;
    end
    
    fprintf('  → Done.\n');
end

% ==== Update Counts and Trim Matrices ====
% Ensure statistics only use the actually processed files, not pre-allocated zeros
n_group1 = idx1;
n_group2 = idx2;

group1_metrics = group1_metrics(1:n_group1, :);
group2_metrics = group2_metrics(1:n_group2, :);

if n_group1 == 0 || n_group2 == 0
    error('No valid files processed for one or both groups. Check log file.');
end

%% ==== Statistical Analysis ====
fprintf('\nCalculating statistics...\n');
p_values = zeros(1, n_beh);

for b = 1:n_beh
    g1_data = group1_metrics(:, b);
    g2_data = group2_metrics(:, b);

    [~, p_values(b)] = ttest2(g1_data, g2_data, 'Vartype', 'unequal');
end

%% ==== Plotting ====
fprintf('Generating plot...\n');
figure('Name', 'Behavior Comparison', 'Color', 'w', 'Position', [100, 100, 800, 600]);

% Calculate Means and Standard Error of Mean (SEM)
% Uses the updated n_group1/n_group2
mean1 = mean(group1_metrics);
mean2 = mean(group2_metrics);
sem1 = std(group1_metrics) / sqrt(n_group1);
sem2 = std(group2_metrics) / sqrt(n_group2);

n_beh = numel(mean1);
bar_width = 0.4;

% Create X positions for grouped bars
x = 1:n_beh;
x1 = x - bar_width/2;
x2 = x + bar_width/2;

hold on;

% Plot Group 1 bars
h1 = bar(x1, mean1, bar_width, 'FaceAlpha', 0.8, 'FaceColor', [0.2 0.4 0.6]);
errorbar(x1, mean1, sem1, 'k.', 'LineWidth', 1, 'CapSize', 10, 'HandleVisibility', 'off');

% Plot Group 2 bars
h2 = bar(x2, mean2, bar_width, 'FaceAlpha', 0.8, 'FaceColor', [0.8 0.4 0.2]);
errorbar(x2, mean2, sem2, 'k.', 'LineWidth', 1, 'CapSize', 10, 'HandleVisibility', 'off');

% ==== Overlay Individual Data Points as Scatter ====
jitter_range = 0.06;
marker_size = 50;
all_y_data = []; % Track all data points to set YLim later

% Group 1 scatter points
for b = 1:n_beh
    y_values = group1_metrics(:, b);
    all_y_data = [all_y_data; y_values(:)];
    n_points = length(y_values);
    if n_points > 0
        x_jitter = x1(b) + (rand(n_points, 1) - 0.5) * jitter_range;
        scatter(x_jitter, y_values, marker_size, ...
            [0.2 0.4 0.6], 'filled', ...
            'MarkerEdgeColor', 'k', ...
            'MarkerEdgeAlpha', 0.4, ...
            'MarkerFaceAlpha', 0.9, ...
            'HandleVisibility', 'off');
    end
end

% Group 2 scatter points
for b = 1:n_beh
    y_values = group2_metrics(:, b);
    all_y_data = [all_y_data; y_values(:)];
    n_points = length(y_values);
    if n_points > 0
        x_jitter = x2(b) + (rand(n_points, 1) - 0.5) * jitter_range;
        scatter(x_jitter, y_values, marker_size, ...
            [0.8 0.4 0.2], 'filled', ...
            'MarkerEdgeColor', 'k', ...
            'MarkerEdgeAlpha', 0.4, ...
            'MarkerFaceAlpha', 0.9, ...
            'HandleVisibility', 'off');
    end
end

% ==== Set Y-Limits BEFORE adding brackets ====
% Find the absolute maximum data point (including error bars)

max_data_val = max(all_y_data);
y_range = max(1, max_data_val); % Avoid issues if data is 0
ylim_top = max_data_val + (0.25 * y_range); % Reserve top 25% for brackets
ylim([0, ylim_top]);

% Add Significance Brackets
% We calculate height dynamically so they don't overlap if you extend this later
bracket_height_start = max_data_val + (0.05 * y_range);
bracket_step = 0.05 * y_range;

for b = 1:n_beh
    % Calculate specific height for this behavior
    y_max_local = max(mean1(b) + sem1(b), mean2(b) + sem2(b));
    y_line = max_data_val + (0.10 * y_range); % Fixed offset above all data
    y_text = y_line + (0.03 * y_range);
    
    pos1 = x1(b);
    pos2 = x2(b);
    
    % Only draw if p-value exists
    if ~isnan(p_values(b))
        add_sig_bracket(pos1, pos2, y_line, y_text, p_values(b));
    end
end

% Formatting
set(gca, 'XTick', x, 'XTickLabel', behavior_types, 'XTickLabelRotation', 45);
ylabel('Frequency (Counts)');
xlabel('Behavior Type');
title(sprintf('Behavior Comparison: %s vs %s', group1_prefix, group2_prefix));
legend([h1, h2], {group1_prefix, group2_prefix}, 'Location', 'northwest');
grid on;

hold off;

fprintf('Done. Plot generated and log saved.\n');

%% ==== Helper Functions ====

function label = pval2sig(p)
    if isnan(p)
        label = 'N/A';
    elseif p < 0.001
        label = sprintf('%.3f\n***', p);
    elseif p < 0.01
        label = sprintf('%.3f\n**', p);
    elseif p < 0.05
        label = sprintf('%.3f\n*', p);
    else
        label = sprintf('%.3f\nns', p); % 'ns' indicates not significant
    end
end

function add_sig_bracket(x1, x2, y_line, y_text, pval)
    % Draw Bracket Line
    plot([x1, x2], [y_line, y_line], 'k-', 'LineWidth', 1.5);
    % Draw Left Leg
    plot([x1, x1], [y_line, y_line + 0.02], 'k-', 'LineWidth', 1.5);
    % Draw Right Leg
    plot([x2, x2], [y_line, y_line + 0.02], 'k-', 'LineWidth', 1.5);
    
    % Add Text
    label = pval2sig(pval);
    text((x1+x2)/2, y_text, label, ...
        'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'bottom', ...
        'FontWeight', 'bold', ...
        'FontSize', 10, ...
        'Color', 'k');
end

%% ==== Supporting Functions ====
function files = getAllMatFiles(root)
    files = {};
    % Recursively search for .mat files
    dirs = dir(fullfile(root, '**', '*.mat'));
    for k = 1:length(dirs)
        if ~dirs(k).isdir
            files{end+1} = fullfile(dirs(k).folder, dirs(k).name);
        end
    end
end

function logMessage(logFile, msg)
    fid = fopen(logFile, 'a');
    if fid == -1
        % Fallback to command window if log file fails
        disp(msg); 
        return;
    end
    currentTime = datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss');
    fprintf(fid, '[%s] %s\n', string(currentTime), msg);
    fclose(fid);
end