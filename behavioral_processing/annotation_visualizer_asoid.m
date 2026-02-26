clear all;
close all;

%%
batch_mode = false;
fps = 10;
pin_duration_seconds = 600;

%%
if ~batch_mode
    [filename, pathname] = uigetfile('*.mat', 'Select MAT file');
    if isequal(filename, 0)
        disp('No file selected. Execution aborted.');
        return;
    end
    annot_mat = fullfile(pathname, filename);
    processSingleMatFile(annot_mat, fps, pin_duration_seconds, batch_mode);
else
    root_dir = uigetdir('', 'Select Root Folder to Search for .mat Files');
    if root_dir == 0
        disp('No folder selected. Exiting.');
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
    
    % Process each file
    for i = 1:n_files
        mat_path = mat_files{i};
        [~, name, ~] = fileparts(mat_path);
        fprintf('\n[%d/%d] Processing: %s\n', i, n_files, name);
        
        try
            processSingleMatFile(mat_path, fps, pin_duration_seconds, batch_mode);
            logMessage(log_file, sprintf('SUCCESS: %s', mat_path));
        catch ME
            warn_msg = sprintf('FAILED: %s | Error: %s', mat_path, ME.message);
            warning(warn_msg);
            logMessage(log_file, warn_msg);
        end
        
        % Update progress in command window
        fprintf('  → Done. Figures saved.\n');
    end
    
    fprintf('\nbatch_mode complete! Log saved to:\n%s\n', log_file);
end

%%
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
    % Get current time as a datetime object and format it
    currentTime = datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss');
    fprintf(fid, '[%s] %s\n', string(currentTime), msg);
    fclose(fid);
end

function safe_pie(counts, labels, colors, title_str)
    nonzero = counts > 0;
    if ~any(nonzero)
        text(0.5, 0.5, 'No data', 'HorizontalAlignment', 'center', ...
             'FontSize', 12, 'Interpreter', 'none');
        title(title_str, 'Interpreter', 'none');
        return;
    end
    
    % Extract non-zero data
    counts_nz = counts(nonzero);
    labels_nz = labels(nonzero);
    colors_nz = colors(nonzero, :);
    
    p = pie(counts_nz, zeros(size(counts_nz)));
    delete(findobj(p, 'Type', 'text'));
    
    % Color patches
    patches = p(1:2:end);
    n = min(length(patches), size(colors_nz, 1));
    for i = 1:n
        set(patches(i), 'FaceColor', colors_nz(i, :));
    end
    
    % Add LEGEND instead of inline labels (prevents overlap)
    lgd = legend(labels_nz, 'Location', 'bestoutside', 'Interpreter', 'none');
    lgd.FontSize = 8;
    
    % Title
    title(title_str, 'Interpreter', 'none');
end

function processSingleMatFile(annot_mat, fps, pin_duration_seconds, batch_mode)
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
    

    %% === 1. Behavior Duration & Subtype Analysis ===
    count_beh = @(beh_str) sum(contains(annot_named, string(beh_str)));
    
    total = length(annot_named);
    dom_genita  = count_beh('dom_anogenital') ;
    dom_hug = count_beh('dom_huddling');
    dom_mount = count_beh('dom_mounting');
    dom_pass = count_beh('dom_passive');
    dom_sniff = count_beh('dom_sniffing');
    dom_intro = count_beh('dom_intromission') + count_beh('dom_ejaculation');
    sub_genita  = count_beh('sub_anogenital');
    sub_hug = count_beh('sub_huddling');
    sub_mount = count_beh('sub_mounting');
    sub_pass = count_beh('sub_passive');
    sub_sniff = count_beh('sub_sniffing');
    sub_intro = count_beh('sub_intromission') + count_beh('sub_ejaculation');
    other = count_beh('other');

    behavior_labels_full = {
        sprintf('dom_anogenital (%.1f%%)',   100*dom_genita/total);
        sprintf('dom_huddling (%.1f%%)',     100*dom_hug/total);
        sprintf('dom_mounting (%.1f%%)',     100*dom_mount/total);
        sprintf('dom_passive (%.1f%%)',      100*dom_pass/total);
        sprintf('dom_sniffing (%.1f%%)',     100*dom_sniff/total);
        sprintf('dom_intromission (%.1f%%)',     100*dom_intro/total);
        sprintf('sub_anogenital (%.1f%%)',   100*sub_genita/total);
        sprintf('sub_huddling (%.1f%%)',     100*sub_hug/total);
        sprintf('sub_mounting (%.1f%%)',     100*sub_mount/total);
        sprintf('sub_passive (%.1f%%)',      100*sub_pass/total);
        sprintf('sub_sniffing (%.1f%%)',     100*sub_sniff/total);
        sprintf('sub_intromission (%.1f%%)',     100*sub_intro/total);
        sprintf('other (%.1f%%)',            100*other/total)
    };

    counts_full = [dom_genita, dom_hug, dom_mount, dom_pass, dom_sniff, dom_intro  ...
                   sub_genita, sub_hug, sub_mount, sub_pass, sub_sniff, sub_intro, other];

%% === Dual Raster Plot: Dom vs Sub ===

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
    color_map_dom(k, :) = S.color.(dom_labels{k});
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
    color_map_sub(k, :) = S.color.(sub_labels{k});
end
if isfield(S.color, 'other')
    color_map_sub(end, :) = S.color.other;
else
    color_map_sub(end, :) = [0.5 0.5 0.5];
end
labels_sub = [sub_labels, "other"];

% --- Plot ---
figure('Name', 'Dual Behavior Raster (Dom vs Sub)', 'Position', [100, 100, 1400, 600]);

% Top: Dom
ax1 = subplot(2,1,1);
imagesc(ax1, plot_dom');
colormap(ax1, color_map_dom);
clim(ax1, [1, size(color_map_dom,1)]);
set(ax1, 'YTick', [], 'XTick', [], 'Box', 'on');
title(ax1, 'Dominant Mouse Behaviors', 'FontWeight', 'bold');

cb1 = colorbar(ax1, 'Ticks', 1:length(labels_dom), 'TickLabels', labels_dom);
cb1.Position = [0.92, 0.53, 0.02, 0.35];
cb1.Label.String = 'Behavior';

% Bottom: Sub
ax2 = subplot(2,1,2);
imagesc(ax2, plot_sub');
colormap(ax2, color_map_sub);
clim(ax2, [1, size(color_map_sub,1)]);
set(ax2, 'YTick', [], 'Box', 'on');
xlabel(ax2, 'Frame Index');
title(ax2, 'Subordinate Mouse Behaviors', 'FontWeight', 'bold');

cb2 = colorbar(ax2, 'Ticks', 1:length(labels_sub), 'TickLabels', labels_sub);
cb2.Position = [0.92, 0.13, 0.02, 0.35];
cb2.Label.String = 'Behavior';

ax1.XAxis.Exponent = 0;
ax1.XTick = 0:36000:length(annot);
ax2.XAxis.Exponent = 0;
ax2.XTick = 0:36000:length(annot);

cb1.TickLabelInterpreter = 'none';
cb2.TickLabelInterpreter = 'none';

set(gcf, 'Color', 'white');

other_count = sum(annot == 0);

% --- Colors ---
color_full = [
    S.color.dom_anogenital;
    S.color.dom_huddling;
    S.color.dom_mounting;
    S.color.dom_passive;
    S.color.dom_sniffing;
    S.color.dom_intromission;
    S.color.sub_anogenital;
    S.color.sub_huddling;
    S.color.sub_mounting;
    S.color.sub_passive;
    S.color.sub_sniffing;
    S.color.sub_intromission;
    S.color.other
];

% --- Create figure ---
figure('Name', 'Behavior Pie Charts', 'Position', [200, 200, 1200, 450]);

% Pie 1: All behaviors
labels_full = {'dom_anogenital','dom_huddling','dom_mounting','dom_passive','dom_sniffing', 'dom_intromission',...
               'sub_anogenital','sub_huddling','sub_mounting','sub_passive','sub_sniffing', 'sub_intromission', 'other'};
safe_pie(counts_full, labels_full, color_full, 'All Behaviors');

%% === Grouped Bar Plot: Dom vs Sub (True Per-Behavior Colors) ===

% Define behavior types (shared between dom/sub)
behavior_types = {'anogenital', 'huddling', 'mounting', 'passive', 'sniffing', 'intromission'};

% Preallocate counts and colors
n_beh = length(behavior_types);
dom_counts = zeros(n_beh, 1);
sub_counts = zeros(n_beh, 1);
dom_colors = zeros(n_beh, 3);
sub_colors = zeros(n_beh, 3);

% Extract counts and colors for each behavior type
for i = 1:n_beh
    beh_name = behavior_types{i};
    
    % Dom
    dom_field = ['dom_' beh_name];
    dom_counts(i) = sum(annot == behaviors.(dom_field));
    dom_colors(i, :) = S.color.(dom_field);
    
    % Sub
    sub_field = ['sub_' beh_name];
    sub_counts(i) = sum(annot == behaviors.(sub_field));
    sub_colors(i, :) = S.color.(sub_field);
end

% Create grouped bar plot manually (for full color control)
figure('Name', 'Dom vs Sub Behavior Comparison', 'Position', [300, 300, 950, 500]);
hold on;

x = 1:n_beh;           % x positions
width = 0.35;          % bar width

% Plot dom bars (left)
b1 = bar(x - width/2, dom_counts, width);
set(b1, 'FaceColor', 'flat', 'CData', dom_colors);

% Plot sub bars (right)
b2 = bar(x + width/2, sub_counts, width);
set(b2, 'FaceColor', 'flat', 'CData', sub_colors);

hold off;

% Labels
xticks(x);
xticklabels(behavior_types);
xtickangle(45);  % prevent overlap
xlabel('Behavior Type');
ylabel('Frame Count');
title('Dominant vs Subordinate Behavior Frequency', 'Interpreter', 'none');

% Legend
legend([b1(1), b2(1)], 'Dominant', 'Subordinate', ...
       'Location', 'northwest', 'Interpreter', 'none');

% Clean up
grid on;
box on;
set(gca, 'TickLabelInterpreter', 'none');  % prevent _ → subscript
set(gcf, 'Color', 'white');

%% === Dual Trend Plots: Dom vs Sub ===

% Parameters (reuse from earlier)
pin_duration_frames = pin_duration_seconds * fps;
num_bins = floor(num_frames_total / pin_duration_frames);
if num_bins < 1
    warning('Not enough frames for trend analysis.');
else
    time_minutes = (0.5:num_bins-0.5) * (pin_duration_frames / fps / 60);
    
    % Behavior types (same as bar plot)
    behavior_types = {'anogenital', 'huddling', 'mounting', 'passive', 'sniffing', 'intromission'};
    n_beh = length(behavior_types);
    
    % --- Prepare data matrices ---
    % Each row = time bin, each column = behavior type (NO "other")
    dom_trends = zeros(num_bins, n_beh);
    sub_trends = zeros(num_bins, n_beh);
    
    dom_ids = zeros(size(behavior_types));
    sub_ids = zeros(size(behavior_types));
    
    for lkj = 1:length(behavior_types)
        beh_name = behavior_types{lkj};
        dom_ids(lkj) = behaviors.(['dom_' beh_name]);
        sub_ids(lkj) = behaviors.(['sub_' beh_name]);
    end
        
    % --- Process each time bin ---
    for kp = 1:num_bins
        start_idx = (kp-1)*pin_duration_frames + 1;
        end_idx = min(kp*pin_duration_frames, num_frames_total);
        segment = annot(start_idx:end_idx);
        seg_len = end_idx - start_idx + 1;
        
        % Top: Dom trends (sub → ignore, only count dom behaviors)
        seg_dom = segment;
        % Only keep dom behaviors, ignore everything else (sub + other)
        valid_dom = ismember(seg_dom, dom_ids);
        for b = 1:n_beh
            dom_trends(kp, b) = sum(seg_dom(valid_dom) == dom_ids(b));
        end
        dom_trends(kp, :) = dom_trends(kp, :) / seg_len;  % normalize by total segment length
        
        % Bottom: Sub trends (dom → ignore, only count sub behaviors)
        seg_sub = segment;
        valid_sub = ismember(seg_sub, sub_ids);
        for b = 1:n_beh
            sub_trends(kp, b) = sum(seg_sub(valid_sub) == sub_ids(b));
        end
        sub_trends(kp, :) = sub_trends(kp, :) / seg_len;  % normalize by total segment length
    end
    
    % Smooth trends
    window = min(3, num_bins);
    dom_trends_smooth = movmean(dom_trends, window, 1);
    sub_trends_smooth = movmean(sub_trends, window, 1);
    
    % Get colors (only 6 behaviors, no "other")
    dom_colors = [
        S.color.dom_anogenital;
        S.color.dom_huddling;
        S.color.dom_mounting;
        S.color.dom_passive;
        S.color.dom_sniffing;
        S.color.dom_intromission
    ];
    sub_colors = [
        S.color.sub_anogenital;
        S.color.sub_huddling;
        S.color.sub_mounting;
        S.color.sub_passive;
        S.color.sub_sniffing;
        S.color.sub_intromission
    ];
    
    % Labels (no "other")
    dom_labels = strcat("dom_", behavior_types);
    sub_labels = strcat("sub_", behavior_types);
    
    % Find global y-limit for both plots
    global_ymax = max([max(dom_trends_smooth(:)), max(sub_trends_smooth(:))]);
    global_ylim = [0, global_ymax];
    
    % --- Plot ---
    figure('Name', 'Behavior Trends Over Time', 'Position', [400, 200, 1000, 600]);
    
    % Top: Dom
    subplot(2,1,1);
    hold on;
    for b = 1:size(dom_trends_smooth, 2)
        plot(time_minutes, dom_trends_smooth(:, b), 'LineWidth', 2, ...
             'Color', dom_colors(b, :), 'DisplayName', dom_labels{b});
    end
    hold off;
    ylabel('Probability');
    title('Dominant Mouse Behavior Trends', 'Interpreter', 'none');
    grid on; box on;
    legend('Location', 'eastoutside', 'Interpreter', 'none');
    set(gca, 'TickLabelInterpreter', 'none', 'XLim', [min(time_minutes) max(time_minutes)], ...
        'YLim', global_ylim);
    
    % Bottom: Sub
    subplot(2,1,2);
    hold on;
    for b = 1:size(sub_trends_smooth, 2)
        plot(time_minutes, sub_trends_smooth(:, b), 'LineWidth', 2, ...
             'Color', sub_colors(b, :), 'DisplayName', sub_labels{b});
    end
    hold off;
    xlabel('Time (minutes)');
    ylabel('Probability');
    title('Subordinate Mouse Behavior Trends', 'Interpreter', 'none');
    grid on; box on;
    legend('Location', 'eastoutside', 'Interpreter', 'none');
    set(gca, 'TickLabelInterpreter', 'none', 'XLim', [min(time_minutes) max(time_minutes)], ...
        'YLim', global_ylim);
    
    set(gcf, 'Color', 'white');
end

end