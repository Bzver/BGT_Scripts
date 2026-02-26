clear all;
close all;

%%
fps = 10;
pin_duration_seconds = 600;
min_frames = 10;

root_dir = uigetdir('', 'Select Root Folder to Search for .mat Files');
if root_dir == 0
    disp('No folder selected. Exiting.');
    return;
end

% NEW: Ask user which portion of data to analyze using buttons
dlg_title = 'Select Data Portion';
prompt = 'Which part of the data should be analyzed?';
btn1 = 'First Half';
btn2 = 'Second Half';
btn3 = 'Full Data';
default_btn = 'Full Data'; % This must match one of the button labels

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
    % User closed the dialog (clicked 'X')
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

% Process each file to collect individual metrics
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

        % NEW: Extract only the specified portion of data
        total_frames = length(annot);
        if data_portion == 1
            % First half
            half_point = floor(total_frames / 2);
            annot_subset = annot(1:half_point);
        elseif data_portion == 2
            % Second half
            half_point = floor(total_frames / 2) + 1;
            annot_subset = annot(half_point:end);
        else
            % Full data
            annot_subset = annot;
        end

        % Initialize colors from first valid file
        if ~colors_initialized
            dom_colors = [
                S.color.dom_anogenital;
                S.color.dom_huddling;
                S.color.dom_mounting;
                S.color.dom_passive;
                S.color.dom_sniffing;
                S.color.dom_intromission
            ];
            colors_initialized = true;
        end
        
        % Calculate individual file metrics
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
            
            % Calculate normalized metric for this file
            if (dom_count + sub_count) > min_frames
                individual_metrics(i, b) = (dom_count - sub_count) / (dom_count + sub_count);
            else
                individual_metrics(i, b) = NaN; % No data for this behavior in this file
            end
        end
        
        logMessage(log_file, sprintf('SUCCESS: %s', mat_path));
    catch ME
        warn_msg = sprintf('FAILED: %s | Error: %s', mat_path, ME.message);
        warning(warn_msg);
        logMessage(log_file, warn_msg);
        individual_metrics(i, :) = NaN; % Mark entire file as failed
    end
    
    fprintf('  → Done.\n');
end

if ~colors_initialized
    error('No valid files found to extract behavior colors.');
end

% Calculate mean metrics across files (ignoring NaN values)
mean_metrics = nanmean(individual_metrics, 1)';

% Perform one-sample t-tests (vs 0) for each behavior
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
        p_vals(b) = NaN; % Not testable
    else
        sem_metrics(b) = 0;
        p_vals(b) = NaN;
    end
end

% Create combined bar + scatter plot with significance
fprintf('\nCreating aggregated batch plot with significance...\n');

figure('Name', 'Batch Mode: Normalized Dom vs Sub Metric', 'Position', [300, 300, 950, 500]);
hold on; box on; grid on;

x = 1:n_beh;
width = 0.6;

% Plot bars with behavior-specific colors
for b = 1:n_beh
    bar(x(b), mean_metrics(b), width, ...
        'FaceColor', dom_colors(b,:), ...
        'EdgeColor', 'k', 'LineWidth', 0.5);
    % Add error bars
    errorbar(x(b), mean_metrics(b), sem_metrics(b), 'k.', 'HandleVisibility', 'off');
end

% Overlay individual data points as scatter (jittered)
rng(0); % For reproducible jitter
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
        y_top = mean_metrics(b) + sem_metrics(b) + 0.08; % Adjust offset as needed
        add_sig_bracket(x(b), x(b), y_top, p_vals(b), 'FontSize', 10);
    end
end

hold off;

% Labels and formatting
ylabel('(Dom - Sub) / (Dom + Sub)');
set(gca, 'XTick', x, 'XTickLabel', behavior_types);
xtickangle(45);
title('Preference Index Across All Files', 'Interpreter', 'none');
ylim([-1, 1]);

fprintf('\nbatch_mode complete! Log saved to:\n%s\n', log_file);

%% ==== Helper Functions ====
function label = pval2sig(p)
    if p < 0.001
        label = [string(p);"***"];
    elseif p < 0.01
        label = [string(p);"**"];
    elseif p < 0.05
        label = [string(p);"*"];
    else
        label = string(p);
    end
end

function add_sig_bracket(x1, x2, y_base, pval, varargin)
    ax = gca;
    ylims = ax.YLim;
    y_range = diff(ylims);
    y_margin = 0.03 * y_range;
    y_line = min(y_base, ylims(2) - y_margin);
    y_text = y_line + 0.6 * y_margin;
    
    if x1 == x2
        % Single bar: just a cap
        plot([x1-0.15, x1+0.15], [y_line, y_line], 'k-', 'LineWidth', 1);
        plot([x1-0.15, x1-0.15], [y_line, y_line + 0.2*y_margin], 'k-', 'LineWidth', 1);
        plot([x1+0.15, x1+0.15], [y_line, y_line + 0.2*y_margin], 'k-', 'LineWidth', 1);
    else
        % Bracket between two bars
        plot([x1 x2], [y_line y_line], 'k-', 'LineWidth', 1);
        plot([x1 x1], [y_line y_line + 0.2*y_margin], 'k-', 'LineWidth', 1);
        plot([x2 x2], [y_line y_line + 0.2*y_margin], 'k-', 'LineWidth', 1);
    end
    
    label = pval2sig(pval);
    if ~isempty(label)
        text((x1+x2)/2, y_text, label, 'HorizontalAlignment', 'center', 'FontWeight', 'bold', varargin{:});
    end
    
    if y_text > ylims(2)
        ax.YLim(2) = y_text + 0.1*y_margin;
    end
end

%% ==== Supporting Functions ====
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