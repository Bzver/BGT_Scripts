clear all;
close all;
clc;

%% ==== Configuration ====
fps = 10;
fixed_frames = 18000;
bin_min = 1;                          % Bin size in minutes
binSize = bin_min * 60 * fps;          % Frames per bin

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
n_group1_max = sum(startsWith(cellfun(@(x) fileparts(x), mat_files, 'UniformOutput', false), group1_prefix));
n_group2_max = sum(startsWith(cellfun(@(x) fileparts(x), mat_files, 'UniformOutput', false), group2_prefix));

fprintf('Found %d files (Max G1: %d, Max G2: %d).\n', n_files, n_group1_max, n_group2_max);

%% ==== Discover Behavior Types ====
S = load(mat_files{1}); 

if isfield(S, 'annotation') && isfield(S.annotation, 'behaviors')
    behavior_types = fieldnames(S.annotation.behaviors); 
else
    error('Could not find annotation.behaviors in the first file.');
end
n_beh = numel(behavior_types);

if isfield(S, 'color')
    colors = S.color;
else
    colors = lines(n_beh); 
end

%% ==== Process Files & Bin Data ====
fprintf('Processing files and binning data (%d-min bins)...\n', bin_min);

n_bins = ceil(fixed_frames / binSize);

data_g1 = zeros(n_group1_max, n_beh, n_bins);
data_g2 = zeros(n_group2_max, n_beh, n_bins);

idx1 = 0;
idx2 = 0;

log_file = fullfile(root_dir, 'behavior_trend_log.txt');
fid = fopen(log_file, 'w'); fclose(fid);

for i = 1:n_files
    mat_path = mat_files{i};
    [~, name, ~] = fileparts(mat_path);
    
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
        annot = int32(S.annotation.annotation(:)) + 1;
        total_frames = length(annot);
        
        if total_frames < fixed_frames
            logMessage(log_file, sprintf('SKIPPED (Length %d < %d): %s', total_frames, fixed_frames, name));
            continue;
        end
        
        annot = annot(1:fixed_frames);
        total_frames = fixed_frames;
        
        if group_id == 1
            idx1 = idx1 + 1;
            curr_idx = idx1;
        elseif group_id == 2
            idx2 = idx2 + 1;
            curr_idx = idx2;
        end
        
        for b = 1:n_bins
            start_idx = (b-1)*binSize + 1;
            end_idx = min(b*binSize, total_frames);
            
            if start_idx > total_frames
                break;
            end
            
            bin_data = annot(start_idx:end_idx);
            
            for beh = 1:n_beh
                count = sum(bin_data == beh);
                if group_id == 1
                    data_g1(curr_idx, beh, b) = count;
                else
                    data_g2(curr_idx, beh, b) = count;
                end
            end
        end
        
        logMessage(log_file, sprintf('SUCCESS: %s (Frames: %d)', name, total_frames));
        
    catch ME
        fprintf('Error processing %s: %s\n', name, ME.message);
        logMessage(log_file, sprintf('FAILED: %s | Error: %s', name, ME.message));
    end
end

n_group1 = idx1;
n_group2 = idx2;

data_g1 = data_g1(1:n_group1, :, :);
data_g2 = data_g2(1:n_group2, :, :);

if n_group1 == 0 || n_group2 == 0
    error('No valid files processed for one or both groups. Check log file.');
end

fprintf('Valid files processed: G1 = %d, G2 = %d\n', n_group1, n_group2);

%% ==== Statistical Analysis (Per Bin) ====
fprintf('Running statistics (%d behaviors x %d bins)...\n', n_beh, n_bins);

p_values_matrix = zeros(n_beh, n_bins);

for b = 1:n_bins
    for beh = 1:n_beh
        g1_vec = squeeze(data_g1(:, beh, b));
        g2_vec = squeeze(data_g2(:, beh, b));

        [~, p_val] = ttest2(g1_vec, g2_vec, 'Vartype', 'unequal');
        p_values_matrix(beh, b) = p_val;
    end
end

%% ==== Statistical Analysis (Aggregated Totals for Summary) ====
fprintf('Running summary statistics (aggregated totals)...\n');

p_summary = zeros(1, n_beh);

for beh = 1:n_beh
    % FIX: Sum across bins (dimension 3)
    total_g1_beh = squeeze(sum(data_g1(:, beh, :), 3));
    total_g2_beh = squeeze(sum(data_g2(:, beh, :), 3));
    
    % Ensure column vectors
    total_g1_beh = total_g1_beh(:);
    total_g2_beh = total_g2_beh(:);
    
    [~, p_summary(beh)] = ttest2(total_g1_beh, total_g2_beh, 'Vartype', 'unequal');
end

%% ==== Plotting: Behavior Trends Over Time ====
fprintf('Generating trend plots...\n');

binDuration_sec = binSize / fps;
time_min = (0:n_bins-1 + 0.5) * (binDuration_sec / 60);

n_rows = ceil(sqrt(n_beh));
n_cols = ceil(n_beh / n_rows);

figure('Name', 'Behavior Trends Over Time', 'Color', 'w', ...
    'Position', [50, 50, 400*n_cols, 300*n_rows]);

c1 = [0.2 0.4 0.6];
c2 = [0.8 0.4 0.2];

for beh = 1:n_beh
    subplot(n_rows, n_cols, beh);
    hold on;
    
    mean1 = squeeze(mean(data_g1(:, beh, :)));
    mean2 = squeeze(mean(data_g2(:, beh, :)));
    sem1 = squeeze(std(data_g1(:, beh, :)) / sqrt(n_group1));
    sem2 = squeeze(std(data_g2(:, beh, :)) / sqrt(n_group2));
    
    % Force row vectors for fill()
    time_min_row = time_min(:)';
    mean1 = mean1(:)';
    mean2 = mean2(:)';
    sem1 = sem1(:)';
    sem2 = sem2(:)';
    
    plot(time_min_row, mean1, '-', 'Color', c1, 'LineWidth', 2, 'DisplayName', group1_prefix);
    fill([time_min_row, fliplr(time_min_row)], ...
         [mean1 + sem1, fliplr(mean1 - sem1)], ...
         c1, 'FaceAlpha', 0.2, 'EdgeColor', 'none', 'HandleVisibility', 'off');
    
    plot(time_min_row, mean2, '-', 'Color', c2, 'LineWidth', 2, 'DisplayName', group2_prefix);
    fill([time_min_row, fliplr(time_min_row)], ...
         [mean2 + sem2, fliplr(mean2 - sem2)], ...
         c2, 'FaceAlpha', 0.2, 'EdgeColor', 'none', 'HandleVisibility', 'off');
    
    % FDR Correction
    p_raw = p_values_matrix(beh, :);
    valid_bins = ~isnan(p_raw);
    
    if sum(valid_bins) > 1
        [~, ~, p_adj] = fdr_bh(p_raw(valid_bins));
        p_corrected = nan(size(p_raw));
        p_corrected(valid_bins) = p_adj;
    else
        p_corrected = p_raw;
    end
    
    sig_bins = find(p_corrected < 0.05 & ~isnan(p_corrected));
    if ~isempty(sig_bins)
        for sb = sig_bins
            x_pos = time_min_row(sb);
            y_max = max([mean1(sb) + sem1(sb), mean2(sb) + sem2(sb)]);
            plot(x_pos, y_max, '*', 'Color', 'k', 'MarkerSize', 12, ...
                'MarkerFaceColor', 'k', 'HandleVisibility', 'off');
        end
        legend_text = {group1_prefix, group2_prefix, sprintf('★ FDR q<0.05 (n=%d)', numel(sig_bins))};
        legend(legend_text, 'Location', 'best');
    else
        legend('Location', 'best');
    end
    
    xlabel('Time (minutes)');
    ylabel('Count');
    title(behavior_types{beh});
    grid on;
    box on;
    
    hold off;
end

sgtitle(sprintf('Behavior Trends: %s vs %s (n1=%d, n2=%d) | ★ = FDR-corrected per behavior', ...
    group1_prefix, group2_prefix, n_group1, n_group2), 'FontSize', 14);

%% ==== Plotting: Summary Bar Chart ====
fprintf('Generating summary plot...\n');

figure('Name', 'Behavior Summary', 'Color', 'w', 'Position', [100, 100, 900, 600]);

total_g1 = squeeze(sum(data_g1, 3));
total_g2 = squeeze(sum(data_g2, 3));

mean1 = mean(total_g1);
mean2 = mean(total_g2);
sem1 = std(total_g1) / sqrt(n_group1);
sem2 = std(total_g2) / sqrt(n_group2);

n_beh_plot = numel(mean1);
bar_width = 0.4;
x = 1:n_beh_plot;
x1 = x - bar_width/2;
x2 = x + bar_width/2;

hold on;

h1 = bar(x1, mean1, bar_width, 'FaceAlpha', 0.8, 'FaceColor', c1);
errorbar(x1, mean1, sem1, 'k.', 'LineWidth', 1, 'CapSize', 10, 'HandleVisibility', 'off');

h2 = bar(x2, mean2, bar_width, 'FaceAlpha', 0.8, 'FaceColor', c2);
errorbar(x2, mean2, sem2, 'k.', 'LineWidth', 1, 'CapSize', 10, 'HandleVisibility', 'off');

jitter_range = 0.06;
marker_size = 50;

for b = 1:n_beh_plot
    y_values = total_g1(:, b);
    n_points = length(y_values);
    if n_points > 0
        x_jitter = x1(b) + (rand(n_points, 1) - 0.5) * jitter_range;
        scatter(x_jitter, y_values, marker_size, c1, 'filled', ...
            'MarkerEdgeColor', 'k', 'MarkerEdgeAlpha', 0.4, 'HandleVisibility', 'off');
    end
end

for b = 1:n_beh_plot
    y_values = total_g2(:, b);
    n_points = length(y_values);
    if n_points > 0
        x_jitter = x2(b) + (rand(n_points, 1) - 0.5) * jitter_range;
        scatter(x_jitter, y_values, marker_size, c2, 'filled', ...
            'MarkerEdgeColor', 'k', 'MarkerEdgeAlpha', 0.4, 'HandleVisibility', 'off');
    end
end

max_data_val = max([total_g1(:); total_g2(:)]);
y_range = max(1, max_data_val);
y_line = max_data_val + (0.10 * y_range);
y_text = y_line + (0.03 * y_range);

for b = 1:n_beh_plot
    p_total = p_summary(b);
    
    if ~isnan(p_total)
        add_sig_bracket(x1(b), x2(b), y_line, y_text, p_total);
    end
end

set(gca, 'XTick', x, 'XTickLabel', behavior_types, 'XTickLabelRotation', 45);
ylabel('Total Count');
xlabel('Behavior Type');
title(sprintf('Behavior Comparison: %s vs %s (Aggregated Totals)', group1_prefix, group2_prefix));
legend([h1, h2], {group1_prefix, group2_prefix}, 'Location', 'northwest');
grid on;
ylim([0, max_data_val + (0.25 * y_range)]);

hold off;

fprintf('Done. Plots generated and log saved.\n');

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
        label = sprintf('%.3f\nns', p);
    end
end

function add_sig_bracket(x1, x2, y_line, y_text, pval)
    plot([x1, x2], [y_line, y_line], 'k-', 'LineWidth', 1.5);
    plot([x1, x1], [y_line, y_line + 0.02], 'k-', 'LineWidth', 1.5);
    plot([x2, x2], [y_line, y_line + 0.02], 'k-', 'LineWidth', 1.5);
    
    label = pval2sig(pval);
    text((x1+x2)/2, y_text, label, ...
        'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'bottom', ...
        'FontWeight', 'bold', ...
        'FontSize', 10, ...
        'Color', 'k');
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
    if fid == -1
        disp(msg); 
        return;
    end
    currentTime = datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss');
    fprintf(fid, '[%s] %s\n', string(currentTime), msg);
    fclose(fid);
end

function [h, s, adj_p] = fdr_bh(p_vals)
    p_vals = p_vals(:);
    m = length(p_vals);
    [sorted_p, sort_idx] = sort(p_vals);
    
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
    
    adj_p_sorted = zeros(m_valid, 1);
    adj_p_sorted(m_valid) = s_p(m_valid);
    for i = (m_valid-1):-1:1
        adj_p_sorted(i) = min(s_p(i) * m_valid / i, adj_p_sorted(i+1));
    end
    adj_p_sorted = min(adj_p_sorted, 1);
    
    adj_p = ones(m, 1);
    adj_p(sort_idx(valid_idx)) = adj_p_sorted;
    adj_p(isnan(p_vals)) = NaN;
    
    h = adj_p < 0.05;
    s = double(h);
end
