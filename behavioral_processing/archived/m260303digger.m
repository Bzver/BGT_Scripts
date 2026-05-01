clear all;
close all;
clc;

%% ==== Configuration ====
% Analysis Settings
n_segments = 5;          % Try 5 or 10. Splits total time into this many bins.
use_fdr_correction = true;% True = Correct for multiple comparisons (Recommended)
alpha_threshold = 0.05;   % Significance threshold

% File Settings
fps = 10; 
fixed_frames = 12000;     % ==== ADDED: Frame constraint ====

root_dir = uigetdir('', 'Select Root Folder to Search for .mat Files');
if root_dir == 0
    disp('No folder selected. Exiting.');
    return;
end

group1_prefix = "NEX";
group2_prefix = "ctrl";

fprintf('Searching for files...\n');
mat_files = getAllMatFiles(root_dir);
n_files = length(mat_files);

if n_files == 0
    error('No .mat files found.');
end

% Count groups (based on filenames for pre-allocation)
n_group1_max = sum(startsWith({mat_files.name}, group1_prefix));
n_group2_max = sum(startsWith({mat_files.name}, group2_prefix));

fprintf('Found %d files (Max G1: %d, Max G2: %d).\n', n_files, n_group1_max, n_group2_max);

%% ==== Discover Behavior Types ====
% Peek first file to get structure
S = load(mat_files(1).fullpath); 

if isfield(S, 'annotation') && isfield(S.annotation, 'behaviors')
    behavior_types = fieldnames(S.annotation.behaviors); 
else
    error('Could not find annotation.behaviors in the first file.');
end
n_beh = numel(behavior_types);

% Colors
if isfield(S, 'color')
    colors = S.color;
else
    colors = lines(n_beh); 
end

%% ==== Process Files & Segment Data ====
fprintf('Processing files and segmenting data (%d segments)...\n', n_segments);

% Preallocate 3D Matrix: [Group x Behaviors x Segments]
% We store the COUNT of frames per behavior per segment
data_g1 = zeros(n_group1_max, n_beh, n_segments);
data_g2 = zeros(n_group2_max, n_beh, n_segments);

idx1 = 0;
idx2 = 0;

log_file = fullfile(root_dir, 'segmented_analysis_log.txt');
fid = fopen(log_file, 'w'); fclose(fid);

for i = 1:n_files
    f_info = mat_files(i);
    mat_path = f_info.fullpath;
    [~, name, ~] = fileparts(mat_path);
    
    % Determine Group (Do NOT increment index yet)
    group_id = 0;
    if startsWith(name, group1_prefix)
        group_id = 1;
    elseif startsWith(name, group2_prefix)
        group_id = 2;
    else
        continue; 
    end

    try
        S = load(mat_path);
        annot = int32(S.annotation.annotation(:)) + 1; % 1-based index
        total_frames = length(annot);
        
        % ==== CONSTRAINT 1: Exclude files shorter than fixed_frames ====
        if total_frames < fixed_frames
            logMessage(log_file, sprintf('SKIPPED (Length %d < %d): %s', total_frames, fixed_frames, name));
            continue; % Skip to next file, do NOT increment idx
        end
        
        % ==== CONSTRAINT 2: Truncate files longer than fixed_frames ====
        annot = annot(1:fixed_frames);
        total_frames = fixed_frames; % Update to reflect truncated length
        
        % Now that data is valid, increment the specific group counter
        if group_id == 1
            idx1 = idx1 + 1;
            curr_idx = idx1;
        elseif group_id == 2
            idx2 = idx2 + 1;
            curr_idx = idx2;
        end
        
        % Calculate segment length (now based on fixed_frames)
        seg_len = floor(total_frames / n_segments);
        
        % Loop through segments
        for s = 1:n_segments
            start_idx = (s-1)*seg_len + 1;
            if s == n_segments
                end_idx = total_frames; % Ensure last frame is included
            else
                end_idx = s*seg_len;
            end
            
            segment_data = annot(start_idx:end_idx);
            
            % Count occurrences per behavior in this segment
            for b = 1:n_beh
                count = sum(segment_data == b);
                if group_id == 1
                    data_g1(curr_idx, b, s) = count;
                else
                    data_g2(curr_idx, b, s) = count;
                end
            end
        end
        
        logMessage(log_file, sprintf('SUCCESS: %s (Frames: %d)', name, total_frames));
        
    catch ME
        fprintf('Error processing %s: %s\n', name, ME.message);
        logMessage(log_file, sprintf('FAILED: %s | Error: %s', name, ME.message));
    end
end

% ==== Update Counts and Trim Matrices ====
% Ensure statistics only use the actually processed files, not pre-allocated zeros
n_group1 = idx1;
n_group2 = idx2;

data_g1 = data_g1(1:n_group1, :, :);
data_g2 = data_g2(1:n_group2, :, :);

if n_group1 == 0 || n_group2 == 0
    error('No valid files processed for one or both groups. Check log file.');
end

fprintf('Valid files processed: G1 = %d, G2 = %d\n', n_group1, n_group2);

%% ==== Statistical Analysis (Per Segment) ====
fprintf('Running statistics (%d behaviors x %d segments)...\n', n_beh, n_segments);

p_values_matrix = zeros(n_beh, n_segments); % Store raw p-values
t_stats_matrix = zeros(n_beh, n_segments);

for s = 1:n_segments
    for b = 1:n_beh
        g1_vec = squeeze(data_g1(:, b, s));
        g2_vec = squeeze(data_g2(:, b, s));

        [~, p_val] = ttest2(g1_vec, g2_vec, 'Vartype', 'unequal');
        p_values_matrix(b, s) = p_val;
    end
end

%% ==== Multiple Comparison Correction ====
% Flatten matrix to apply correction across ALL tests simultaneously
raw_p_flat = p_values_matrix(:);
valid_mask = ~isnan(raw_p_flat);
corrected_p_flat = ones(size(raw_p_flat));

if use_fdr_correction && any(valid_mask)
    % Benjamini-Hochberg FDR
    [~, ~, adj_p] = fdr_bh(raw_p_flat(valid_mask));
    corrected_p_flat(valid_mask) = adj_p;
else
    % No correction (Raw p-values) - NOT RECOMMENDED for publication
    corrected_p_flat = raw_p_flat;
end

% Reshape back
p_corrected_matrix = reshape(corrected_p_flat, size(p_values_matrix));

%% ==== Auto-Dig: Find the "Most Significant" Segment ====
% Strategy: Find the segment with the lowest MINIMUM p-value across all behaviors.
% Alternatively, you could look for the segment with the most behaviors < 0.05.

min_p_per_seg = min(p_corrected_matrix, [], 1, 'omitnan'); % Best p-value in each segment
[best_min_p, best_segment_idx] = min(min_p_per_seg, [], 'omitnan');

if isempty(best_segment_idx) || isnan(best_min_p)
    error('No valid statistical results found. Check data inputs.');
end

fprintf('=== AUTO-DIG RESULT ===\n');
fprintf('Most significant segment detected: Segment %d / %d\n', best_segment_idx, n_segments);
fprintf('Lowest corrected p-value in this segment: %.4f\n', best_min_p);

% Extract data for plotting ONLY this segment
s_plot = best_segment_idx;
mean1 = squeeze(mean(data_g1(:, :, s_plot)));
mean2 = squeeze(mean(data_g2(:, :, s_plot)));
sem1 = squeeze(std(data_g1(:, :, s_plot)) / sqrt(n_group1));
sem2 = squeeze(std(data_g2(:, :, s_plot)) / sqrt(n_group2));
p_vals_plot = p_corrected_matrix(:, s_plot);

%% ==== Plotting The Winning Segment ====
figure('Name', sprintf('Significant Segment Detected: #%d', s_plot), ...
    'Color', 'w', 'Position', [100, 100, 900, 600]);

n_beh_plot = numel(mean1);
bar_width = 0.4;
x = 1:n_beh_plot;
x1 = x - bar_width/2;
x2 = x + bar_width/2;

hold on;

% Colors
c1 = [0.2 0.4 0.6];
c2 = [0.8 0.4 0.2];

% Bars
h1 = bar(x1, mean1, bar_width, 'FaceAlpha', 0.7, 'FaceColor', c1);
errorbar(x1, mean1, sem1, 'k.', 'LineWidth', 1, 'CapSize', 8, 'HandleVisibility', 'off');

h2 = bar(x2, mean2, bar_width, 'FaceAlpha', 0.7, 'FaceColor', c2);
errorbar(x2, mean2, sem2, 'k.', 'LineWidth', 1, 'CapSize', 8, 'HandleVisibility', 'off');

% Scatter Individual Points (Jittered)
jitter_range = 0.08;
marker_size = 40;

% Group 1 Points
for b = 1:n_beh_plot
    y_vals = squeeze(data_g1(:, b, s_plot));
    n_pts = length(y_vals);
    if n_pts > 0
        x_jit = x1(b) + (rand(n_pts, 1) - 0.5) * jitter_range;
        scatter(x_jit, y_vals, marker_size, c1, 'filled', ...
            'MarkerEdgeColor', 'k', 'MarkerEdgeAlpha', 0.3, 'HandleVisibility', 'off');
    end
end

% Group 2 Points
for b = 1:n_beh_plot
    y_vals = squeeze(data_g2(:, b, s_plot));
    n_pts = length(y_vals);
    if n_pts > 0
        x_jit = x2(b) + (rand(n_pts, 1) - 0.5) * jitter_range;
        scatter(x_jit, y_vals, marker_size, c2, 'filled', ...
            'MarkerEdgeColor', 'k', 'MarkerEdgeAlpha', 0.3, 'HandleVisibility', 'off');
    end
end

% Add Significance Brackets only for significant behaviors in THIS segment
max_y = max([mean1+sem1; mean2+sem2], [], 'omitnan');
y_base = max_y * 1.15; 
y_step = max_y * 0.05;

sig_count = 0;
for b = 1:n_beh_plot
    p_val = p_vals_plot(b);
    if ~isnan(p_val) && p_val < alpha_threshold
        sig_count = sig_count + 1;
        % Stack brackets if multiple significant items exist close together? 
        % For simplicity, we put them at a uniform height or slightly staggered
        y_line = y_base + (sig_count-1)*y_step; 
        y_text = y_line + y_step*0.6;
        
        add_sig_bracket(x1(b), x2(b), y_line, y_text, p_val);
    end
end

% Formatting
set(gca, 'XTick', x, 'XTickLabel', behavior_types, 'XTickLabelRotation', 45);
ylabel(sprintf('Frequency (Segment %d)', s_plot));
xlabel('Behavior Type');
title(sprintf('Auto-Detected Significant Phase: Segment %d/%d\n(Corrected P < %.3f)', ...
    s_plot, n_segments, best_min_p));
legend([h1, h2], {group1_prefix, group2_prefix}, 'Location', 'northwest');
grid on;
ylim([0, max(max_y * 1.4)]); % Reserve space for brackets

hold off;

fprintf('Plot generated for Segment %d.\n', s_plot);

%% ==== Helper Functions ====


function label = pval2sig(p)
    if isnan(p)
        label = 'N/A';
    elseif p < 0.001
        label = sprintf('%.3g\n***', p);
    elseif p < 0.01
        label = sprintf('%.3g\n**', p);
    elseif p < 0.05
        label = sprintf('%.3g\n*', p);
    else
        label = sprintf('%.3g\nns', p);
    end
end

function add_sig_bracket(x1, x2, y_line, y_text, pval)
    plot([x1, x2], [y_line, y_line], 'k-', 'LineWidth', 1.5);
    plot([x1, x1], [y_line, y_line + 0.015], 'k-', 'LineWidth', 1.5);
    plot([x2, x2], [y_line, y_line + 0.015], 'k-', 'LineWidth', 1.5);
    
    label = pval2sig(pval);
    text((x1+x2)/2, y_text, label, ...
        'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'bottom', ...
        'FontWeight', 'bold', 'FontSize', 11, 'Color', 'k');
end

function files = getAllMatFiles(root)
    dirs = dir(fullfile(root, '**', '*.mat'));
    files = struct('name', {}, 'folder', {}, 'fullpath', {});
    count = 0;
    for k = 1:length(dirs)
        if ~dirs(k).isdir
            count = count + 1;
            files(count).name = dirs(k).name;
            files(count).folder = dirs(k).folder;
            files(count).fullpath = fullfile(dirs(k).folder, dirs(k).name);
        end
    end
end

function logMessage(logFile, msg)
    fid = fopen(logFile, 'a');
    if fid ~= -1
        fprintf(fid, '[%s] %s\n', char(datetime('now')), msg);
        fclose(fid);
    end
end

% Simple FDR implementation (Benjamini-Hochberg) if Statistics Toolbox is missing
% If you have the toolbox, MATLAB's built-in fdr_bh is not standard, usually people use mafdr or custom.
% Here is a robust standalone implementation:
function [h, s, adj_p] = fdr_bh(p_vals)
    p_vals = p_vals(:);
    m = length(p_vals);
    [sorted_p, sort_idx] = sort(p_vals);
    
    % Remove NaNs for calculation
    valid_idx = ~isnan(sorted_p);
    s_p = sorted_p(valid_idx);
    m_valid = sum(valid_idx);
    
    if m_valid == 0
        h = false(m, 1);
        s = zeros(m, 1);
        adj_p = ones(m, 1);
        adj_p(isnan(p_vals)) = NaN;
        return;
    end
    
    % BH Step-up
    ranks = (1:m_valid)';
    thresholds = (ranks / m_valid) * 0.05; % Default alpha 0.05 inside logic, but we return adj_p
    
    % Calculate Adjusted P-values
    adj_p_sorted = zeros(m_valid, 1);
    adj_p_sorted(m_valid) = s_p(m_valid);
    for i = (m_valid-1):-1:1
        adj_p_sorted(i) = min(s_p(i) * m_valid / i, adj_p_sorted(i+1));
    end
    adj_p_sorted = min(adj_p_sorted, 1);
    
    % Reorder to original
    adj_p_full = ones(m, 1);
    adj_p_full(valid_idx) = adj_p_sorted;
    
    % Map back to original order
    adj_p = ones(m, 1);
    adj_p(sort_idx(valid_idx)) = adj_p_sorted;
    adj_p(isnan(p_vals)) = NaN;
    
    % Significance mask (at 0.05)
    h = adj_p < 0.05;
    s = double(h);
end