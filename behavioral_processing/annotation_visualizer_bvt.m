clear all;
close all;

%%
batch_mode = true;
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
    
    dom_avg_sp = S.locomotion.dom_avg;
    sub_avg_sp = S.locomotion.sub_avg;
    dom_avgm_sp = S.locomotion.dom_avgm;
    sub_avgm_sp = S.locomotion.sub_avgm;
    dom_mov_perc = S.locomotion.dom_mperc;
    sub_mov_perc = S.locomotion.sub_mperc;
    
    dom_bg = S.heatmap.dom_bg;
    sub_bg = S.heatmap.sub_bg;
    dom_heatmap = S.heatmap.dom_h;
    sub_heatmap = S.heatmap.sub_h;
    
    dom_bg = dom_bg * (1 - 0.9) + repmat(rgb2gray(dom_bg), [1, 1, 3]) * 0.9;
    sub_bg = sub_bg * (1 - 0.9) + repmat(rgb2gray(sub_bg), [1, 1, 3]) * 0.9;
    
    %% Color ref
    color_map_active = [
        0.1    0.2    0.5;    % dom_int
        0.55   0.80   0.95;   % dom_icg
        0.65   0.10   0.15;   % sub_int
        0.95   0.55   0.55;   % sub_icg
        0.7    0.7    0.7;    % other
    ];
    
    %% === 0. Heatmaps ===
    dom_hm = im2double(dom_heatmap);
    sub_hm = im2double(sub_heatmap);
    [bg_h, bg_w, ~] = size(dom_bg);
    
    dom_hm = imresize(dom_hm, [bg_h, bg_w], 'bilinear');
    sub_hm = imresize(sub_hm, [bg_h, bg_w], 'bilinear');
    dom_hm = max(0, min(1, dom_hm));
    sub_hm = max(0, min(1, sub_hm));
    
    figure('Name', 'Heatmap', 'Position', [100, 100, 1100, 450]); % wider for colorbar
    
    subplot(1,2,1);
    imshow(dom_bg, 'Border', 'tight');
    hold on;
    h1 = imagesc(1:bg_w, 1:bg_h, dom_hm);
    colormap(jet);
    h1.AlphaData = 0.5;
    title('Dominant');
    axis equal tight;
    xlim([1, bg_w]);
    ylim([1, bg_h]);
    set(gca, 'YDir', 'normal');
    hold off;
    
    subplot(1,2,2);
    imshow(sub_bg, 'Border', 'tight');
    hold on;
    h2 = imagesc(1:bg_w, 1:bg_h, sub_hm);
    colormap(jet);
    h2.AlphaData = 0.5;
    title('Subordinate');
    axis equal tight;
    xlim([1, bg_w]);
    ylim([1, bg_h]);
    set(gca, 'YDir', 'normal');
    hold off;
    
    cb_ax = axes('Position', [0.92, 0.2, 0.02, 0.6], 'Visible', 'off');
    colorbar(cb_ax, 'Limits', [min(dom_hm(:)), max(dom_hm(:))]);
    
    %% === 1. Locomotion ===
    figure('Name', 'Locomotion Analysis', 'Position', [100, 100, 1600, 400]);
    subplot(1,3,1);
    hold on; box on; grid on;

    bar(1, dom_avg_sp, 0.8, 'FaceColor', [0.1 0.2 0.5], ...
        'EdgeColor', 'k', 'LineWidth', 0.5);
    bar(2, sub_avg_sp, 0.8, 'FaceColor', [0.65 0.1 0.15], ...
        'EdgeColor', 'k', 'LineWidth', 0.5);
    
    hold off;
    
    ylabel('Average Speed (px/s)');
    set(gca, 'XTick', [1 2], 'XTickLabel', {'Dominant', 'Subordinate'});
    
    subplot(1,3,2);
    hold on; box on; grid on;

    bar(1, dom_avgm_sp, 0.8, 'FaceColor', [0.1 0.2 0.5], ...
        'EdgeColor', 'k', 'LineWidth', 0.5);
    bar(2, sub_avgm_sp, 0.8, 'FaceColor', [0.65 0.1 0.15], ...
        'EdgeColor', 'k', 'LineWidth', 0.5);
    
    hold off;
    
    ylabel('Average Moving Speed (px/s)');
    set(gca, 'XTick', [1 2], 'XTickLabel', {'Dominant', 'Subordinate'});

    subplot(1,3,3);
    hold on; box on; grid on;

    bar(1, dom_mov_perc, 0.8, 'FaceColor', [0.1 0.2 0.5], ...
        'EdgeColor', 'k', 'LineWidth', 0.5);
    bar(2, sub_mov_perc, 0.8, 'FaceColor', [0.65 0.1 0.15], ...
        'EdgeColor', 'k', 'LineWidth', 0.5);
    
    hold off;
    
    ylabel('Moving Percentage (%)');
    set(gca, 'XTick', [1 2], 'XTickLabel', {'Dominant', 'Subordinate'});

    %% === 2. Behavior Duration & Subtype Analysis ===
    count_beh = @(beh_str) sum(contains(annot_named, string(beh_str)));
    
    total = length(annot_named);
    dom_init  = count_beh('dom_interaction');
    dom_icg  = count_beh('dom_in_cage');
    sub_init = count_beh('sub_interaction');
    sub_icg  = count_beh('sub_in_cage');
    other    = count_beh('other');

    %% === 3. Pie Chart ===
    figure('Name', 'Behavior Distribution', 'Position', [100, 100, 800, 600]);
    colormap(color_map_active);
    set(gcf, 'Color', 'white');
    
    role_labels = {
        sprintf('Interact With Dom (%.1f%%)', dom_init/total*100), ...
        sprintf('In Dom Cage (%.1f%%)',      dom_icg/total*100), ...
        sprintf('Interact With Sub (%.1f%%)', sub_init/total*100), ...
        sprintf('In Sub Cage (%.1f%%)',      sub_icg/total*100), ...
        sprintf('In Neither Cage (%.1f%%)',  other/total*100)
    };
    
    counts = [dom_init, dom_icg, sub_init, sub_icg, other];
    pie(counts, role_labels);
    title('Total Interaction Time');
    
    %% === 4. Line Plot: Behavior Trends Over Time ===
    pin_duration_frames = pin_duration_seconds * fps;
    num_bins = floor(num_frames_total / pin_duration_frames);
    if num_bins < 1
        warning('Not enough frames for trend analysis.');
        return;
    end
    
    time_minutes = (0.5:num_bins-0.5) * (pin_duration_frames / fps / 60);
    behaviors_active = {'dom_interaction', 'dom_in_cage', 'sub_interaction', 'sub_in_cage'};
    
    % Preallocate
    trends_active = zeros(num_bins, length(behaviors_active));
    for p = 1:num_bins
        start_idx = (p-1)*pin_duration_frames + 1;
        end_idx = min(p*pin_duration_frames, num_frames_total);
        segment = annot_named(start_idx:end_idx);
        
        for b = 1:length(behaviors_active)
            trends_active(p, b) = sum(contains(segment, behaviors_active{b})) / (end_idx - start_idx + 1);
        end
    end
    
    smoothed_active = movmean(trends_active, 3, 1);
    
    figure('Name', 'Behavior Trends', 'Position', [100, 100, 1600, 500]);
    hold on;
    
    for b = 1:length(behaviors_active)
        h = plot(time_minutes, smoothed_active(:,b), 'LineWidth', 2, ...
            'Color', color_map_active(b,:), ...
            'DisplayName', behaviors_active{b});
    end
    
    hold off;
    xlabel('Time (minutes)');
    ylabel('Probability');
    title('Active Behavior Dynamics', 'FontSize', 12);
    grid on; box on;
    xlim([min(time_minutes), max(time_minutes)]);
    legend('Location', 'eastoutside', 'Interpreter', 'none');
    set(gca, 'XColor', 'black', 'YColor', 'black');
    set(gcf, 'Color', 'white');
    
    %% === Save All Figures to <mat_dir>/figures/ ===
    % Create output folder
    [pathname, name, ext] = fileparts(annot_mat);
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
        
        fig_name = regexprep(fig_name, '[\\/:*?"<>|]', '_');
        
        png_path = fullfile(figures_dir, [fig_name, '.png']);
        exportgraphics(fig, png_path, 'Resolution', 600, 'ContentType', 'auto');
        
        fprintf('Saved: %s.png\n', fig_name);
    end
    
    fprintf('\nAll figures saved to:\n%s\n', figures_dir);
    if batch_mode
    close(fig_handles);
    end
end