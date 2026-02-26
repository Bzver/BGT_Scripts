clear all;
close all;

%% Setup
fps = 10; % Frame rate - adjust if your data uses different fps
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

fprintf('Found %d .mat files. Starting batch processing...\n', n_files);

% Initialize storage for metrics
n_metrics = 4;
dom_values = cell(n_metrics, 1);
sub_values = cell(n_metrics, 1);
for i = 1:n_metrics
    dom_values{i} = [];
    sub_values{i} = [];
end

% Process each file
for i = 1:n_files
    mat_path = mat_files{i};
    [~, name, ~] = fileparts(mat_path);
    fprintf('\n[%d/%d] Processing: %s\n', i, n_files, name);
    
    try
        S = load(mat_path);
        
        if ~isfield(S, 'annotation') || ~isfield(S.annotation, 'behaviors') || ~isfield(S.annotation, 'annotation')
            error('MAT file missing required annotation fields.');
        end
        
        behaviors = S.annotation.behaviors;
        annot = int32(S.annotation.annotation);
  
        %% Metric 1: Mounting bout COUNTS
        dom_mount_bouts = 0; sub_mount_bouts = 0;
        
        if isfield(behaviors, 'dom_mounting')
            dom_mount_mask = (annot == behaviors.dom_mounting);
            dom_mount_bouts = countBouts(dom_mount_mask);
        end
        if isfield(behaviors, 'sub_mounting')
            sub_mount_mask = (annot == behaviors.sub_mounting);
            sub_mount_bouts = countBouts(sub_mount_mask);
        end
        dom_values{1}(end+1) = dom_mount_bouts;
        sub_values{1}(end+1) = sub_mount_bouts;
        
        %% Metric 2: Average (mounting + intromission) bout duration (seconds)
        dom_durs = []; sub_durs = [];
        if isfield(behaviors, 'dom_mounting') && isfield(behaviors, 'dom_intromission')
            dom_mask = (annot == behaviors.dom_mounting) | (annot == behaviors.dom_intromission);
            dom_durs = extractBoutDurations(dom_mask, fps);
        end
        if isfield(behaviors, 'sub_mounting') && isfield(behaviors, 'sub_intromission')
            sub_mask = (annot == behaviors.sub_mounting) | (annot == behaviors.sub_intromission);
            sub_durs = extractBoutDurations(sub_mask, fps);
        end
        dom_values{2}(end+1) = ifelse(~isempty(dom_durs), mean(dom_durs), NaN);
        sub_values{2}(end+1) = ifelse(~isempty(sub_durs), mean(sub_durs), NaN);
        
        %% Metric 3: Transition probability: mounting → intromission
        dom_trans = NaN; sub_trans = NaN;
        dom_trans = calcTransitionProb(annot, behaviors.dom_mounting, behaviors.dom_intromission, fps);
        sub_trans = calcTransitionProb(annot, behaviors.sub_mounting, behaviors.sub_intromission, fps);
        dom_values{3}(end+1) = dom_trans;
        sub_values{3}(end+1) = sub_trans;
        
        %% Metric 4: First ejaculation latency (seconds)
        dom_lat = NaN; sub_lat = NaN;
        if isfield(behaviors, 'dom_ejaculation') && isfield(behaviors, 'dom_mounting')
            first_mount = find(annot == behaviors.dom_mounting, 1, 'first');
            first_ejac = find(annot == behaviors.dom_ejaculation, 1, 'first');
            if ~isempty(first_mount) && ~isempty(first_ejac) && first_ejac > first_mount
                dom_lat = (first_ejac - first_mount) / fps;
            end
        end
        if isfield(behaviors, 'sub_ejaculation') && isfield(behaviors, 'sub_mounting')
            first_mount = find(annot == behaviors.sub_mounting, 1, 'first');
            first_ejac = find(annot == behaviors.sub_ejaculation, 1, 'first');
            if ~isempty(first_mount) && ~isempty(first_ejac) && first_ejac > first_mount
                sub_lat = (first_ejac - first_mount) / fps;
            end
        end
        dom_values{4}(end+1) = dom_lat;
        sub_values{4}(end+1) = sub_lat;
        
        fprintf('  ✓ Completed\n');
        
    catch ME
        warning('⚠ FAILED: %s | %s', name, ME.message);
        for m = 1:n_metrics
            dom_values{m}(end+1) = NaN;
            sub_values{m}(end+1) = NaN;
        end
    end
end

%% Create visualization figure
metric_labels = {
    'Mounting Occurrences'
    'Avg (Mount+Intro) Bout Duration (s)'
    'Transition Probability: Mount→Intro'
    'First Ejaculation Latency (s)'
};
y_labels = {
    'Event Count'
    'Duration (seconds)'
    'Proportion'
    'Latency (seconds)'
};

figure('Name', 'Dom vs Sub: Sex Behavioral Metrics', 'Position', [50, 50, 1400, 900], 'Color', 'w');
set(gcf, 'DefaultAxesFontSize', 11);

for m = 1:n_metrics
    subplot(2, 2, m);
    
    % === KEY CHANGE: Exclude zeros AND NaNs ===
    dom_data = dom_values{m};
    sub_data = sub_values{m};
    
    % Remove NaN AND zero values
    dom_data = dom_data(~isnan(dom_data) & (dom_data ~= 0));
    sub_data = sub_data(~isnan(sub_data) & (sub_data ~= 0));
    
    % Skip plotting if insufficient data after filtering
    if numel(dom_data) < 2 || numel(sub_data) < 2
        text(1.5, 0.5, sprintf('Insufficient non-zero data\n(Dom: %d, Sub: %d files)', ...
            numel(dom_values{m}(~isnan(dom_values{m}) & dom_values{m}~=0)), ...
            numel(sub_values{m}(~isnan(sub_values{m}) & sub_values{m}~=0))), ...
            'HorizontalAlignment', 'center', 'Color', 'r', 'FontWeight', 'bold', 'FontSize', 9);
        set(gca, 'XTick', [1,2], 'XTickLabel', {'Dominant','Subordinate'});
        ylabel(y_labels{m});
        title(metric_labels{m});
        grid on; box on;
        continue;
    end
    
    % Calculate statistics on filtered data
    dom_mean = mean(dom_data); sub_mean = mean(sub_data);
    dom_sem = std(dom_data)/sqrt(numel(dom_data));
    sub_sem = std(sub_data)/sqrt(numel(sub_data));
    
    % Independent t-test (Welch's correction for unequal variance)
    [~, p_val] = ttest2(dom_data, sub_data, 'Vartype', 'unequal');
    
    % Create bar plot - R2022a compatible
    hold on; box on; grid on;
    
    % Plot each bar separately for different colors
    bar(1, dom_mean, 0.4, 'FaceColor', [0.2 0.4 0.8], 'EdgeColor', 'k', 'LineWidth', 1);
    bar(2, sub_mean, 0.4, 'FaceColor', [0.8 0.3 0.3], 'EdgeColor', 'k', 'LineWidth', 1);
    
    % Error bars (SEM)
    errorbar(1, dom_mean, dom_sem, 'k.', 'LineWidth', 1.5, 'CapSize', 12);
    errorbar(2, sub_mean, sub_sem, 'k.', 'LineWidth', 1.5, 'CapSize', 12);
    
    % Overlay individual non-zero data points with jitter
    rng(42);
    jitter_width = 0.12;
    if ~isempty(dom_data)
        x_jit = 1 + (rand(size(dom_data)) - 0.5) * jitter_width * 2;
        scatter(x_jit, dom_data, 35, [0.2 0.4 0.8], 'filled', ...
            'MarkerEdgeColor', 'k', 'LineWidth', 0.3);
    end
    if ~isempty(sub_data)
        x_jit = 2 + (rand(size(sub_data)) - 0.5) * jitter_width * 2;
        scatter(x_jit, sub_data, 35, [0.8 0.3 0.3], 'filled', ...
            'MarkerEdgeColor', 'k', 'LineWidth', 0.3);
    end
    
    % Add significance annotation
    if ~isnan(p_val)
        y_max = max([dom_mean + dom_sem, sub_mean + sub_sem]);
        y_min = min([dom_mean - dom_sem, sub_mean - sub_sem]);
        y_range = max(0.1, y_max - y_min); % Prevent division issues
        bracket_height = y_max + 0.08 * y_range;
        text_height = bracket_height + 0.05 * y_range;
        
        % Draw bracket
        plot([1, 1, 2, 2], [bracket_height, bracket_height+0.015*y_range, ...
                           bracket_height+0.015*y_range, bracket_height], ...
            'k-', 'LineWidth', 1.2);
        
        % Significance stars
        if p_val < 0.001
            sig_txt = [string(p_val);"***"];
        elseif p_val < 0.01
            sig_txt = [string(p_val);"**"];
        elseif p_val < 0.05
            sig_txt = [string(p_val);"*"];
        else
            sig_txt = string(p_val);
        end
        text(1.5, text_height, sig_txt, ...
            'HorizontalAlignment', 'center', 'FontWeight', 'bold', 'FontSize', 13);
    end
    
    % Axis formatting
    set(gca, 'XTick', [1, 2], 'XTickLabel', {'Dominant', 'Subordinate'}, 'FontSize', 10);
    ylabel(y_labels{m}, 'FontWeight', 'bold');
    title(metric_labels{m}, 'FontWeight', 'bold');
    ylim auto;
    % Force 0 baseline for counts and proportions (but not if all values > 0)
    if m == 1 || m == 3
        yl = ylim; 
        if yl(1) > 0, ylim([0 yl(2)]); end
    end
    
    hold off;
end

sgtitle('Dominant vs Subordinate Sexual Behaviors Comparisons', ...
    'FontSize', 16, 'FontWeight', 'bold');

%% Helper Functions

function out = ifelse(cond, a, b)
    if cond
        out = a;
    else
        out = b;
    end
end

function durations = extractBoutDurations(mask, fps)
    durations = [];
    if ~any(mask(:)), return; end
    
    mask = mask(:);
    d = diff([false; mask; false]);
    starts = find(d == 1);
    ends = find(d == -1) - 1;
    
    for k = 1:numel(starts)
        dur_frames = ends(k) - starts(k) + 1;
        durations(end+1) = dur_frames / fps;
    end
end

function n_bouts = countBouts(mask)
    % Count number of contiguous TRUE segments (bouts) in a logical mask
    if ~any(mask(:))
        n_bouts = 0;
        return;
    end
    mask = mask(:);
    d = diff([false; mask; false]);
    starts = find(d == 1);  % rising edges = bout starts
    n_bouts = numel(starts);
end
function prob = calcTransitionProb(annot, mount_code, intro_code, fps)
    % Calculate: % of mounting bouts followed by an intromission bout
    % A "transition" = intromission bout starts within window_seconds after mounting bout ends
    
    prob = NaN;
    window_seconds = 5; % Max gap (seconds) between mount-end and intro-start to count as transition
    
    % Extract bout boundaries for both behaviors
    mount_bouts = extractBoutEdges(annot == mount_code);  % Nx2: [start, end] frames
    intro_bouts = extractBoutEdges(annot == intro_code);
    
    if isempty(mount_bouts)
        return; % No mounting bouts → undefined probability
    end
    
    n_bouts = size(mount_bouts, 1);
    n_transitions = 0;
    window_frames = window_seconds * fps;
    
    for b = 1:n_bouts
        mount_end = mount_bouts(b, 2); % End frame of this mounting bout
        
        % Check each intromission bout: does it start shortly after this mount ends?
        for i = 1:size(intro_bouts, 1)
            intro_start = intro_bouts(i, 1);
            
            % Valid transition: intro starts AFTER mount ends, but within time window
            if intro_start > mount_end && intro_start <= mount_end + window_frames
                n_transitions = n_transitions + 1;
                break; % Count each mount only once (avoid double-counting)
            end
        end
    end
    
    prob = n_transitions / n_bouts;
end

function bouts = extractBoutEdges(mask)
    % Helper: return Nx2 array [start_frame, end_frame] for each contiguous TRUE segment
    if ~any(mask(:))
        bouts = zeros(0, 2);
        return;
    end
    mask = mask(:);
    d = diff([false; mask; false]);  % Add padding to catch edges
    starts = find(d == 1);            % Rising edge = bout start
    ends = find(d == -1) - 1;         % Falling edge = bout end
    bouts = [starts, ends];
end

function files = getAllMatFiles(root)
    files = {};
    d = dir(fullfile(root, '**', '*.mat'));
    for k = 1:numel(d)
        if ~d(k).isdir
            files{end+1} = fullfile(d(k).folder, d(k).name);
        end
    end
end