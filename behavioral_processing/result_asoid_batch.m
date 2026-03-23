clear all;
close all;
clc;

%% ==== Configuration ====
fps = 10;
min_frames = 10;
bin_min = 10;                          % Bin size in minutes for trend plot
binSize = bin_min * 60 * fps;         % Frames per bin

root_dir = uigetdir('', 'Select Root Folder to Search for .mat Files');
if root_dir == 0
    disp('No folder selected. Exiting.');
    return;
end

% Ask user which portion of data to analyze (for OVERALL metric only)
dlg_title = 'Select Data Portion';
prompt = 'Which part of the data should be analyzed for the overall preference index?';
btn1 = 'First Half';
btn2 = 'Second Half';
btn3 = 'Full Data';
default_btn = 'Full Data';

user_choice = questdlg(prompt, dlg_title, btn1, btn2, btn3, default_btn);

if strcmp(user_choice, btn1)
    data_portion = 1;
    portion_str = " (First Half)";
elseif strcmp(user_choice, btn2)
    data_portion = 2;
    portion_str = " (Second Half)";
elseif strcmp(user_choice, btn3)
    data_portion = 3;
    portion_str = " (Full Data)";
else
    disp('Dialog closed. Exiting.');
    return;
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

% Define behavior types
behavior_types = {'anogenital', 'huddling', 'mounting', 'passive', 'sniffing', 'intromission'};
n_beh = length(behavior_types);

% Store individual file metrics
individual_metrics = zeros(n_files, n_beh);
dom_colors = []; 
colors_initialized = false;

%% ==== Pre-allocate for trend data (RAW DURATIONS over time) ====
% Determine max frames across all files to set bin count
max_frames = 0;
for i = 1:n_files
    try
        S_test = load(mat_files{i});
        if isfield(S_test, 'annotation')
            max_frames = max(max_frames, length(S_test.annotation.annotation));
        end
    catch
        % Skip if file fails to load
    end
end
n_bins = ceil(max_frames / binSize);  % Based on longest file

% NEW: Store dom and sub counts separately (not PI)
trend_dom = NaN(n_files, n_beh, n_bins);   % [file, behavior, time_bin]
trend_sub = NaN(n_files, n_beh, n_bins);   % [file, behavior, time_bin]

%% ==== Process each file ====
for i = 1:n_files
    mat_path = mat_files{i};
    [~, name, ~] = fileparts(mat_path);
    fprintf('\n[%d/%d] Processing: %s\n', i, n_files, name);
    
    try
        S = load(mat_path);
        
        if isfield(S, 'annotation')
            behaviors = S.annotation.behaviors;
            annot = int32(S.annotation.annotation);
        else
            error('MAT file missing ''annotation'' field.');
        end

        % === OVERALL METRIC: Apply data portion selection ===
        total_frames = length(annot);
        if data_portion == 1
            half_point = floor(total_frames / 2);
            annot_subset = annot(1:half_point);
        elseif data_portion == 2
            half_point = floor(total_frames / 2) + 1;
            annot_subset = annot(half_point:end);
        else
            annot_subset = annot;  % Full data
        end

        % Initialize colors from first valid file
        if ~colors_initialized
            if isfield(S, 'color')
                dom_colors = [
                    S.color.dom_anogenital;
                    S.color.dom_huddling;
                    S.color.dom_mounting;
                    S.color.dom_passive;
                    S.color.dom_sniffing;
                    S.color.dom_intromission
                ];
            else
                dom_colors = lines(n_beh);
            end
            colors_initialized = true;
        end
        
        % Calculate individual file metrics (overall preference index)
        for b = 1:n_beh
            beh_name = behavior_types{b};
            dom_field = ['dom_' beh_name];
            sub_field = ['sub_' beh_name];
            
            dom_count = 0;
            sub_count = 0;
            
            if isfield(behaviors, dom_field)
                dom_count = sum(annot_subset == behaviors.(dom_field));
            end
            if isfield(behaviors, sub_field)
                sub_count = sum(annot_subset == behaviors.(sub_field));
            end
            
            if (dom_count + sub_count) > min_frames
                individual_metrics(i, b) = (dom_count - sub_count) / (dom_count + sub_count);
            else
                individual_metrics(i, b) = NaN;
            end
        end
        
        % === TREND METRIC: ALWAYS use FULL annot array (ignore data_portion) ===
        effective_frames = length(annot);  % ← Full data, not subset
        n_bins_actual = ceil(effective_frames / binSize);
        
        for b = 1:n_beh
            beh_name = behavior_types{b};
            dom_field = ['dom_' beh_name];
            sub_field = ['sub_' beh_name];
            
            dom_val = [];
            sub_val = [];
            if isfield(behaviors, dom_field), dom_val = behaviors.(dom_field); end
            if isfield(behaviors, sub_field), sub_val = behaviors.(sub_field); end
            
            for bin = 1:n_bins_actual
                start_idx = (bin-1)*binSize + 1;
                end_idx = min(bin*binSize, effective_frames);
                
                if start_idx > effective_frames, break; end
                
                bin_annot = annot(start_idx:end_idx);  % ← Full annot, not subset
                dom_count = sum(bin_annot == dom_val);
                sub_count = sum(bin_annot == sub_val);
                
                % === STORE RAW COUNTS (not PI) ===
                trend_dom(i, b, bin) = dom_count;
                trend_sub(i, b, bin) = sub_count;
            end
        end
        
        logMessage(log_file, sprintf('SUCCESS: %s', mat_path));
        
    catch ME
        warn_msg = sprintf('FAILED: %s | Error: %s', mat_path, ME.message);
        warning(warn_msg);
        logMessage(log_file, warn_msg);
        individual_metrics(i, :) = NaN;
        trend_data(i, :, :) = NaN;
    end
    
    fprintf('  → Done.\n');
end

if ~colors_initialized
    error('No valid files found to extract behavior colors.');
end

%% ==== Calculate mean metrics across files (overall) ====
mean_metrics = nanmean(individual_metrics, 1)';

% One-sample t-tests (vs 0) for each behavior (overall)
p_vals = nan(n_beh, 1);
sem_metrics = nan(n_beh, 1);
for b = 1:n_beh
    vals = individual_metrics(:, b);
    vals = vals(~isnan(vals));
    if numel(vals) >= 2
        [~, p_vals(b)] = ttest(vals, 0);
        sem_metrics(b) = std(vals) / sqrt(numel(vals));
    elseif numel(vals) == 1
        sem_metrics(b) = 0;
        p_vals(b) = NaN;
    end
end

%% ==== Vectorized Statistics Calculation (NaN → 0 first) ====
fprintf('Calculating trend statistics (%d behaviors x %d bins)...\n', n_beh, n_bins);

% === Step 1: Replace all NaN with 0 in one shot ===
trend_dom_clean = trend_dom;
trend_dom_clean(isnan(trend_dom_clean)) = 0;

trend_sub_clean = trend_sub;
trend_sub_clean(isnan(trend_sub_clean)) = 0;

% === Step 2: Compute mean and SEM across files (dimension 1) ===
% Input: [n_files, n_beh, n_bins] → Output: [1, n_beh, n_bins]
trend_dom_mean = mean(trend_dom_clean, 1);
trend_sub_mean = mean(trend_sub_clean, 1);

n_files_valid = size(trend_dom_clean, 1);
trend_dom_sem = std(trend_dom_clean, 0, 1) / sqrt(n_files_valid);
trend_sub_sem = std(trend_sub_clean, 0, 1) / sqrt(n_files_valid);

% === Step 3: Paired t-test per bin (still needs loop, but cleaner) ===
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

%% ==== Plot 1: Overall Preference Index (Original Script 1 plot) ====
fprintf('\nCreating overall preference index plot...\n');

figure('Name', 'Batch Mode: Normalized Dom vs Sub Metric', 'Position', [300, 300, 950, 500]);
hold on; box on; grid on;

x = 1:n_beh;
width = 0.6;

for b = 1:n_beh
    bar(x(b), mean_metrics(b), width, ...
        'FaceColor', dom_colors(b,:), ...
        'EdgeColor', 'k', 'LineWidth', 0.5);
    errorbar(x(b), mean_metrics(b), sem_metrics(b), 'k.', 'HandleVisibility', 'off');
end

% Overlay individual data points
rng(0);
jitter_amount = 0.15;
for b = 1:n_beh
    file_values = individual_metrics(:, b);
    valid_idx = ~isnan(file_values);
    if any(valid_idx)
        x_jitter = x(b) + (rand(sum(valid_idx), 1) - 0.5) * jitter_amount * 2;
        y_values = file_values(valid_idx);
        scatter(x_jitter, y_values, 40, dom_colors(b,:), 'filled', ...
            'MarkerEdgeColor', 'k', 'LineWidth', 0.5);
    end
end

% Add significance brackets
for b = 1:n_beh
    if ~isnan(p_vals(b)) && ~isnan(mean_metrics(b))
        y_top = mean_metrics(b) + sem_metrics(b) + 0.08;
        add_sig_bracket(x(b), x(b), y_top, p_vals(b));
    end
end

hold off;
ylabel('(Dom - Sub) / (Dom + Sub)');
set(gca, 'XTick', x, 'XTickLabel', behavior_types);
xtickangle(45);
title(['Preference Index Across All Files' portion_str], 'Interpreter', 'none');
ylim([-1, 1]);

%% ==== Plot 2: Raw Duration Trend Over Time (FULL DATA ONLY) ====
fprintf('Generating raw duration trend plot (full data)...\n');

% Time axis (in minutes)
binDuration_sec = binSize / fps;
time_min = (0:n_bins-1 + 0.5) * (binDuration_sec / 60);  % [1, n_bins]

% Colors
color_dom = [0.2 0.4 0.6];   % Dark blue
color_sub = [0.9 0.6 0.1];   % Orange

% Subplot grid
n_rows = ceil(sqrt(n_beh));
n_cols = ceil(n_beh / n_rows);

figure('Name', 'Raw Duration Trend: Dom vs Sub (Full Data)', 'Color', 'w', ...
    'Position', [50, 50, 500*n_cols, 400*n_rows]);
for beh = 1:n_beh
    subplot(n_rows, n_cols, beh);
    hold on; box on; grid on;
    
    % === Extract and force row vectors (exactly like Script 2) ===
    mean_dom = squeeze(trend_dom_mean(1, beh, :))';   % [1, n_bins]
    mean_sub = squeeze(trend_sub_mean(1, beh, :))';   % [1, n_bins]
    sem_dom = squeeze(trend_dom_sem(1, beh, :))';     % [1, n_bins]
    sem_sub = squeeze(trend_sub_sem(1, beh, :))';     % [1, n_bins]
    p_vals_bin = squeeze(trend_p(1, beh, :))';        % [1, n_bins]
    
    % === Plot with fill (no masking, no conditions) ===
    plot(time_min, mean_dom, '-', 'Color', color_dom, 'LineWidth', 2, 'DisplayName', 'Dom');
    fill([time_min, fliplr(time_min)], ...
         [mean_dom + sem_dom, fliplr(mean_dom - sem_dom)], ...
         color_dom, 'FaceAlpha', 0.12, 'EdgeColor', 'none', 'HandleVisibility', 'off');
    
    plot(time_min, mean_sub, '-', 'Color', color_sub, 'LineWidth', 2, 'DisplayName', 'Sub');
    fill([time_min, fliplr(time_min)], ...
         [mean_sub + sem_sub, fliplr(mean_sub - sem_sub)], ...
         color_sub, 'FaceAlpha', 0.12, 'EdgeColor', 'none', 'HandleVisibility', 'off');
    
    % Significance markers (FDR corrected)
    p_raw = p_vals_bin;
    valid_p = ~isnan(p_raw);
    if sum(valid_p) > 1
        [~, ~, p_adj] = fdr_bh(p_raw(valid_p));
        p_corr = nan(size(p_raw));
        p_corr(valid_p) = p_adj;
    else
        p_corr = p_raw;
    end
    
    sig_idx = find(p_corr < 0.05 & ~isnan(p_corr));
    if ~isempty(sig_idx)
        for si = sig_idx
            y_max = max([mean_dom(si) + sem_dom(si), mean_sub(si) + sem_sub(si)]);
            plot(time_min(si), y_max, '*', 'Color', 'k', ...
                'MarkerSize', 14, 'MarkerFaceColor', 'k', 'HandleVisibility', 'off');
        end
    end
    
    % Formatting
    xlabel('Time (min)');
    ylabel('Duration (frames)');
    title(behavior_types{beh}, 'Interpreter', 'none');
    
    % Y-axis: auto-scale with small padding
    max_val = max([mean_dom + sem_dom; mean_sub + sem_sub]);
    xlim([0, 720])
    max_y = max(max_val * 1.15);
    if max_y < 1
        max_y = 1;
    end

    ylim([0, max_y]);
    
    % Legend
    if ~isempty(sig_idx)
        legend({'Dom', 'Sub', sprintf('★ p<0.05 FDR (n=%d)', numel(sig_idx))}, ...
               'Location', 'best', 'FontSize', 8);
    else
        legend({'Dom', 'Sub'}, 'Location', 'best', 'FontSize', 8);
    end
    
    hold off;
end

sgtitle('Raw Duration Over Time: Dom vs Sub', ...
    'FontSize', 14, 'FontWeight', 'bold');

%% ==== Plot 3: CUMULATIVE Duration Trend Over Time (FULL DATA ONLY) ====
fprintf('Generating CUMULATIVE duration trend plot (full data)...\n');

% Time axis (in minutes)
binDuration_sec = binSize / fps;
time_min = (0:n_bins-1 + 0.5) * (binDuration_sec / 60);  % [1, n_bins]

% Colors
color_dom = [0.2 0.4 0.6];   % Dark blue
color_sub = [0.9 0.6 0.1];   % Orange

% Subplot grid
n_rows = ceil(sqrt(n_beh));
n_cols = ceil(n_beh / n_rows);

figure('Name', 'Cumulative Duration Trend: Dom vs Sub (Full Data)', 'Color', 'w', ...
    'Position', [50, 50, 500*n_cols, 400*n_rows]);

for beh = 1:n_beh
    subplot(n_rows, n_cols, beh);
    hold on; box on; grid on;
    
    % === Extract and force row vectors ===
    mean_dom = squeeze(trend_dom_mean(1, beh, :))';   % [1, n_bins]
    mean_sub = squeeze(trend_sub_mean(1, beh, :))';   % [1, n_bins]
    sem_dom = squeeze(trend_dom_sem(1, beh, :))';     % [1, n_bins]
    sem_sub = squeeze(trend_sub_sem(1, beh, :))';     % [1, n_bins]
    p_vals_bin = squeeze(trend_p(1, beh, :))';        % [1, n_bins]
    
    % === CONVERT TO CUMULATIVE ===
    mean_dom_cum = cumsum(mean_dom);
    mean_sub_cum = cumsum(mean_sub);
    % Cumulative SEM: sqrt of cumulative variance (assuming independence)
    sem_dom_cum = sqrt(cumsum(sem_dom.^2));
    sem_sub_cum = sqrt(cumsum(sem_sub.^2));
    
    % === Plot cumulative lines with fill ===
    plot(time_min, mean_dom_cum, '-', 'Color', color_dom, 'LineWidth', 2, 'DisplayName', 'Dom');
    fill([time_min, fliplr(time_min)], ...
         [mean_dom_cum + sem_dom_cum, fliplr(mean_dom_cum - sem_dom_cum)], ...
         color_dom, 'FaceAlpha', 0.12, 'EdgeColor', 'none', 'HandleVisibility', 'off');
    
    plot(time_min, mean_sub_cum, '-', 'Color', color_sub, 'LineWidth', 2, 'DisplayName', 'Sub');
    fill([time_min, fliplr(time_min)], ...
         [mean_sub_cum + sem_sub_cum, fliplr(mean_sub_cum - sem_sub_cum)], ...
         color_sub, 'FaceAlpha', 0.12, 'EdgeColor', 'none', 'HandleVisibility', 'off');
    
    % Significance markers (FDR corrected) - NOTE: interpret cautiously for cumulative
    p_raw = p_vals_bin;
    valid_p = ~isnan(p_raw);
    if sum(valid_p) > 1
        [~, ~, p_adj] = fdr_bh(p_raw(valid_p));
        p_corr = nan(size(p_raw));
        p_corr(valid_p) = p_adj;
    else
        p_corr = p_raw;
    end
    
    sig_idx = find(p_corr < 0.05 & ~isnan(p_corr));
    if ~isempty(sig_idx)
        for si = sig_idx
            y_max = max([mean_dom_cum(si) + sem_dom_cum(si), mean_sub_cum(si) + sem_sub_cum(si)]);
            plot(time_min(si), y_max, '*', 'Color', 'k', ...
                'MarkerSize', 14, 'MarkerFaceColor', 'k', 'HandleVisibility', 'off');
        end
    end
    
    % Formatting
    xlabel('Time (min)');
    ylabel('Cumulative Duration (frames)');  % ← Updated label
    title(behavior_types{beh}, 'Interpreter', 'none');  % ← Updated title
    
    % Y-axis: auto-scale with padding
    max_val = max([mean_dom_cum + sem_dom_cum; mean_sub_cum + sem_sub_cum]);
    xlim([0, 720])
    max_y = max(max_val * 1.05);  % Slightly less padding for cumulative
    if max_y < 1
        max_y = 1;
    end
    ylim([0, max_y]);
    
    % Legend
    if ~isempty(sig_idx)
        legend({'Dom', 'Sub', sprintf('★ p<0.05 FDR (n=%d)', numel(sig_idx))}, ...
               'Location', 'best', 'FontSize', 8);
    else
        legend({'Dom', 'Sub'}, 'Location', 'best', 'FontSize', 8);
    end
    
    hold off;
end

sgtitle('Cumulative Duration Over Time: Dom vs Sub', ...
    'FontSize', 14, 'FontWeight', 'bold');  % ← Updated figure title



fprintf('\nBatch mode complete! Log saved to:\n%s\n', log_file);

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

function add_sig_bracket(x1, x2, y_line, pval, varargin)
    plot([x1, x2], [y_line, y_line], 'k-', 'LineWidth', 1.5);
    plot([x1, x1], [y_line, y_line + 0.02], 'k-', 'LineWidth', 1.5);
    plot([x2, x2], [y_line, y_line + 0.02], 'k-', 'LineWidth', 1.5);
    
    ax = gca;
    ylims = ax.YLim;
    y_range = diff(ylims);
    y_margin = 0.03 * y_range;
    y_text = y_line + 0.6 * y_margin;

    label = pval2sig(pval);
    text((x1+x2)/2, y_text, label, ...
        'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'bottom', ...
        'FontWeight', 'bold', ...
        'FontSize', 10, ...
        'Color', 'k', varargin{:});
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
        error('Could not open log file: %s', logFile);
    end
    currentTime = datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss');
    fprintf(fid, '[%s] %s\n', string(currentTime), msg);
    fclose(fid);
end

function [h, s, adj_p] = fdr_bh(p_vals)
    % Benjamini-Hochberg FDR correction
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