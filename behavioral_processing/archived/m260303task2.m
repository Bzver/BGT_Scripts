clear all;
close all;

%% ==== Configuration ====
fps = 10;
pin_duration_seconds = 600;
min_frames = 5;  % Minimum bout length to include (frames)

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

% Count files per group (using filenames only)
file_names = cellfun(@(x) fileparts(x), mat_files, 'UniformOutput', false);
file_names = cellfun(@(x) x(2), file_names, 'UniformOutput', false);
n_group1 = sum(startsWith(file_names, group1_prefix));
n_group2 = sum(startsWith(file_names, group2_prefix));

if n_files == 0
    error('No .mat files found in "%s" or subfolders.', root_dir);
end

fprintf('Found %d .mat files (Group1: %d, Group2: %d).\n', n_files, n_group1, n_group2);

log_file = fullfile(root_dir, 'batch_mode_processing_log.txt');
fid = fopen(log_file, 'w'); fclose(fid);

%% ==== Discover Behavior Types ====
peek_mat = mat_files{1}; 
S = load(peek_mat);

if isfield(S, 'annotation') && isfield(S.annotation, 'behaviors')
    behavior_types = fieldnames(S.annotation.behaviors); 
else
    error('Could not find annotation.behaviors in the first file.');
end
n_beh = numel(behavior_types);

% Set colors
if isfield(S, 'color')
    colors = S.color;
else
    colors = lines(n_beh); 
end

% Initialize Metric Matrices: NOW TWO METRICS PER FILE
group1_counts = zeros(n_group1, n_beh);      % Bout COUNTS per file
group1_durations = zeros(n_group1, n_beh);   % Mean bout DURATION per file
group2_counts = zeros(n_group2, n_beh);
group2_durations = zeros(n_group2, n_beh);

idx1 = 0; idx2 = 0;

%% ==== Process Files ====
for i = 1:n_files
    mat_path = mat_files{i};
    [~, name, ~] = fileparts(mat_path);
    fprintf('\n[%d/%d] Processing: %s\n', i, n_files, name);

    if startsWith(name, group1_prefix)
        group = 1; idx1 = idx1 + 1;
    elseif startsWith(name, group2_prefix)
        group = 2; idx2 = idx2 + 1;
    else
        logMessage(log_file, sprintf('SKIPPED: %s', mat_path));
        continue;
    end

    try
        S = load(mat_path);
        if ~isfield(S, 'annotation') || ~isfield(S.annotation, 'annotation')
            error('Missing annotation field');
        end
        
        annot_raw = S.annotation.annotation(:);
        if min(annot_raw) == 0
            annot = int32(annot_raw) + 1;
        else
            annot = int32(annot_raw);
        end
        
        for b = 1:n_beh
            is_behavior = (annot == b);
            d = diff([0; is_behavior; 0]);
            bout_starts = find(d == 1);
            bout_ends = find(d == -1) - 1;
            bout_lengths_frames = bout_ends - bout_starts + 1;
            
            % Filter by minimum duration
            valid = bout_lengths_frames >= min_frames;
            valid_lengths = bout_lengths_frames(valid);
            n_valid_bouts = sum(valid);  % ← BOUT COUNT
            bout_lengths_sec = valid_lengths / fps;
            
            % Mean duration (0 if no valid bouts)
            
            if ~isempty(bout_lengths_sec)
                mean_dur = mean(bout_lengths_sec)
            else
                mean_dur = 0;
            end
                
            
            if group == 1
                group1_counts(idx1, b) = n_valid_bouts;
                group1_durations(idx1, b) = mean_dur;
            else
                group2_counts(idx2, b) = n_valid_bouts;
                group2_durations(idx2, b) = mean_dur;
            end
        end
        logMessage(log_file, sprintf('SUCCESS: %s', mat_path));
    catch ME
        logMessage(log_file, sprintf('FAILED: %s | %s', mat_path, ME.message));
        fprintf('  → Error: %s\n', ME.message);
        continue;
    end
    fprintf('  → Done.\n');
end

%% ==== Statistical Analysis (for both metrics) ====
fprintf('\nCalculating statistics...\n');
p_counts = zeros(1, n_beh);
p_durations = zeros(1, n_beh);

for b = 1:n_beh
    % --- Bout Counts ---
    g1c = group1_counts(:, b); g2c = group2_counts(:, b);
    % Optional: exclude files with zero bouts
    % g1c = g1c(g1c > 0); g2c = g2c(g2c > 0);
    if length(g1c) > 1 && length(g2c) > 1
        [~, p_counts(b)] = ttest2(g1c, g2c, 'Vartype', 'unequal');
    else
        p_counts(b) = NaN;
    end
    
    % --- Bout Durations ---
    g1d = group1_durations(:, b); g2d = group2_durations(:, b);
    % Only test files that had at least one valid bout
    g1d = g1d(g1d > 0); g2d = g2d(g2d > 0);
    if length(g1d) > 1 && length(g2d) > 1
        [~, p_durations(b)] = ttest2(g1d, g2d, 'Vartype', 'unequal');
    else
        p_durations(b) = NaN;
    end
end

%% ==== Plot 1: Bout Counts ====
fprintf('Generating Bout Count plot...\n');
fig1 = figure('Name', 'Bout Count Comparison', 'Color', 'w', 'Position', [100, 100, 800, 600]);
plot_bout_metric(group1_counts, group2_counts, p_counts, ...
    behavior_types, group1_prefix, group2_prefix, ...
    'Mean Bout Count', 'k.', [0.2 0.4 0.6], [0.8 0.4 0.2]);

%% ==== Plot 2: Bout Durations ====
fprintf('Generating Bout Duration plot...\n');
fig2 = figure('Name', 'Bout Duration Comparison', 'Color', 'w', 'Position', [100, 100, 800, 600]);
plot_bout_metric(group1_durations, group2_durations, p_durations, ...
    behavior_types, group1_prefix, group2_prefix, ...
    'Mean Bout Duration (s)', 'k.', [0.2 0.4 0.6], [0.8 0.4 0.2]);

fprintf('Done. Both plots generated.\n');

%% ==== Helper: Generic Plotting Function ====

function plot_bout_metric(g1_data, g2_data, p_values, beh_types, g1_name, g2_name, ylabel_txt, err_style, col1, col2)
    % Calculate stats
    mean1 = mean(g1_data); mean2 = mean(g2_data);
    sem1 = std(g1_data) / sqrt(max(1, size(g1_data,1)));
    sem2 = std(g2_data) / sqrt(max(1, size(g2_data,1)));
    
    n_beh = numel(mean1);
    bar_width = 0.4;
    x = 1:n_beh;
    x1 = x - bar_width/2;
    x2 = x + bar_width/2;
    
    hold on;
    
    % Bars
    h1 = bar(x1, mean1, bar_width, 'FaceAlpha', 0.8, 'FaceColor', col1);
    errorbar(x1, mean1, sem1, err_style, 'LineWidth', 1, 'CapSize', 10, 'HandleVisibility', 'off');
    h2 = bar(x2, mean2, bar_width, 'FaceAlpha', 0.8, 'FaceColor', col2);
    errorbar(x2, mean2, sem2, err_style, 'LineWidth', 1, 'CapSize', 10, 'HandleVisibility', 'off');
    
    % Scatter points
    jitter = 0.06; ms = 50;
    all_y = [g1_data(:); g2_data(:)];
    all_y = all_y(all_y > 0);  % For scaling
    max_val = max(all_y);
    if isempty(max_val), max_val = 1; end
    y_range = max(1, max_val);
    ylim([0, max_val + 0.25*y_range]);
    
    for b = 1:n_beh
        % Group 1 scatter
        y1 = g1_data(:,b); y1 = y1(y1>0);
        if ~isempty(y1)
            xj = x1(b) + (rand(numel(y1),1)-0.5)*jitter;
            scatter(xj, y1, ms, col1, 'filled', ...
                'MarkerEdgeColor','k','MarkerEdgeAlpha',0.4,'MarkerFaceAlpha',0.9,...
                'HandleVisibility','off');
        end
        % Group 2 scatter
        y2 = g2_data(:,b); y2 = y2(y2>0);
        if ~isempty(y2)
            xj = x2(b) + (rand(numel(y2),1)-0.5)*jitter;
            scatter(xj, y2, ms, col2, 'filled', ...
                'MarkerEdgeColor','k','MarkerEdgeAlpha',0.4,'MarkerFaceAlpha',0.9,...
                'HandleVisibility','off');
        end
    end
    
    % Significance brackets
    for b = 1:n_beh
        y_line = max_val + 0.10*y_range;
        y_text = y_line + 0.03*y_range;
        if ~isnan(p_values(b))
            add_sig_bracket(x1(b), x2(b), y_line, y_text, p_values(b));
        end
    end
    
    % Formatting
    set(gca, 'XTick', x, 'XTickLabel', beh_types, 'XTickLabelRotation', 45);
    ylabel(ylabel_txt);
    xlabel('Behavior Type');
    title(sprintf('%s: %s vs %s', ylabel_txt, g1_name, g2_name));
    legend([h1,h2], {g1_name, g2_name}, 'Location', 'northwest');
    grid on;
    hold off;
end

%% ==== Significance & P-value Helpers ====
function label = pval2sig(p)
    if isnan(p)
        label = 'N/A';
    elseif p < 0.001
        label = sprintf('%.1e\n***', p);
    elseif p < 0.01
        label = sprintf('%.3f\n**', p);
    elseif p < 0.05
        label = sprintf('%.3f\n*', p);
    else
        label = sprintf('%.3f\nns', p);
    end
end

function add_sig_bracket(x1, x2, y_line, y_text, pval)
    plot([x1,x2], [y_line,y_line], 'k-', 'LineWidth', 1.5);
    plot([x1,x1], [y_line, y_line+0.02], 'k-', 'LineWidth', 1.5);
    plot([x2,x2], [y_line, y_line+0.02], 'k-', 'LineWidth', 1.5);
    label = pval2sig(pval);
    text((x1+x2)/2, y_text, label, ...
        'HorizontalAlignment','center','VerticalAlignment','bottom',...
        'FontWeight','bold','FontSize',10,'Color','k');
end

%% ==== File Utilities ====
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
    if fid == -1, disp(msg); return; end
    fprintf(fid, '[%s] %s\n', string(datetime('now','Format','yyyy-MM-dd HH:mm:ss')), msg);
    fclose(fid);
end
