clear; close all; clc;

%% ==== USER CONFIGURATION ====
folderPath = uigetdir;
if isequal(folderPath, 0)
    error("No folder is selected.")
end
dataFolder = folderPath;
matPattern = fullfile(dataFolder, "*.mat");

% Auto-detect .mat files
matFiles = dir(matPattern);
matFiles = {matFiles.name};
matFiles = fullfile(dataFolder, matFiles);

numSessions = length(matFiles);

%% ==== BOUT CONFIGURATION ====
fps = 10;                    % Frames per second
min_bout_frames = 5;         % Minimum 5 frames = 0.5 seconds to qualify as a bout

%% ==== FRAME RANGE SELECTION ====
fprintf('\n=== Frame Range Selection ===\n');
useFrameRange = questdlg('Do you want to process a specific frame range?', ...
    'Frame Range Selection', 'Yes', 'No', 'No');

if strcmp(useFrameRange, 'Yes')
    frameStart = input('Enter starting frame number: ');
    frameEnd = input('Enter ending frame number: ');
    
    if frameStart >= frameEnd || frameStart < 1
        error('Invalid frame range. Start must be less than end and >= 1.');
    end
    
    fprintf('Processing frames %d to %d\n', frameStart, frameEnd);
    processFrameRange = true;
else
    processFrameRange = false;
    frameStart = 1;
    frameEnd = Inf;
    fprintf('Processing all frames\n');
end

%% ==== PREALLOCATE ====
% DURATION METRICS (percentage of frames)
inCage_dom = zeros(numSessions, 1);
inCage_sub = zeros(numSessions, 1);
inter_dom  = zeros(numSessions, 1);
inter_sub  = zeros(numSessions, 1);

% BOUT COUNT METRICS
boutCount_icg_dom = zeros(numSessions, 1);
boutCount_icg_sub = zeros(numSessions, 1);
boutCount_int_dom = zeros(numSessions, 1);
boutCount_int_sub = zeros(numSessions, 1);

% MEAN BOUT LENGTH (frames)
meanBoutLen_icg_dom = zeros(numSessions, 1);
meanBoutLen_icg_sub = zeros(numSessions, 1);
meanBoutLen_int_dom = zeros(numSessions, 1);
meanBoutLen_int_sub = zeros(numSessions, 1);

% PREFERENCE INDICES
PI_duration = zeros(numSessions, 1);   % Based on frame counts
PI_bouts    = zeros(numSessions, 1);   % Based on bout counts

%% ==== PROCESS EACH FILE ====
for i = 1:numSessions
    fprintf('Processing %s...\n', matFiles{i});
    
    S = load(matFiles{i});
    annotStruct = S.annotation;
    
    annot = int32(annotStruct.annotation);
    behaviors = annotStruct.behaviors;
    
    behavior_names = string(fieldnames(behaviors));
    beh_values = struct2array(behaviors);
    [~, idx] = ismember(annot, beh_values);
    annot_named = behavior_names(idx);
    
    % Apply frame range selection
    if processFrameRange
        totalFrames = frameEnd - frameStart + 1;
        if frameEnd > length(annot_named)
            frameEnd = length(annot_named);
            totalFrames = frameEnd - frameStart + 1;
        end
        annot_named = annot_named(frameStart:frameEnd);
        annot_subset = annot(frameStart:frameEnd);
    else
        totalFrames = length(annot_named);
        annot_subset = annot;
    end
    
    % === GET BEHAVIOR VALUES ===
    dom_icg_val = []; sub_icg_val = [];
    dom_int_val = []; sub_int_val = [];
    
    % In-cage: ALL dom_ or sub_ behaviors (union of all values)
    dom_icg_fields = behavior_names(contains(behavior_names, "dom_"));
    sub_icg_fields = behavior_names(contains(behavior_names, "sub_"));
    
    for f = 1:length(dom_icg_fields)
        dom_icg_val = [dom_icg_val; behaviors.(char(dom_icg_fields(f)))];
    end
    for f = 1:length(sub_icg_fields)
        sub_icg_val = [sub_icg_val; behaviors.(char(sub_icg_fields(f)))];
    end
    
    % Interaction: specific interaction behaviors (subset of in-cage)
    if any(contains(behavior_names, "dom_interaction"))
        dom_int_val = behaviors.dom_interaction;
    end
    if any(contains(behavior_names, "sub_interaction"))
        sub_int_val = behaviors.sub_interaction;
    end
    
    % === DURATION METRICS (frame counts) ===
    % In-cage: ANY dom_ or sub_ behavior (interaction does NOT break this up)
    is_dom_icg = ismember(annot_subset, dom_icg_val);
    is_sub_icg = ismember(annot_subset, sub_icg_val);
    
    dom_icg = sum(is_dom_icg);
    sub_icg = sum(is_sub_icg);
    
    % Interaction: subset of in-cage frames
    if ~isempty(dom_int_val)
        is_dom_int = ismember(annot_subset, dom_int_val);
        dom_int = sum(is_dom_int);
    else
        is_dom_int = false(size(annot_subset));
        dom_int = 0;
    end
    
    if ~isempty(sub_int_val)
        is_sub_int = ismember(annot_subset, sub_int_val);
        sub_int = sum(is_sub_int);
    else
        is_sub_int = false(size(annot_subset));
        sub_int = 0;
    end
    
    inCage_dom(i) = 100 * dom_icg / totalFrames;
    inCage_sub(i) = 100 * sub_icg / totalFrames;
    inter_dom(i)  = 100 * dom_int / totalFrames;
    inter_sub(i)  = 100 * sub_int / totalFrames;

    % === BOUT COUNT METRICS ===
    % Extract bouts for in-cage (interaction frames are INCLUDED, not excluded)
    dom_icg_bouts = extract_bout_durations(is_dom_icg, min_bout_frames);
    sub_icg_bouts = extract_bout_durations(is_sub_icg, min_bout_frames);
    
    % Extract bouts for interaction (subset, counted separately)
    dom_int_bouts = extract_bout_durations(is_dom_int, min_bout_frames);
    sub_int_bouts = extract_bout_durations(is_sub_int, min_bout_frames);
    
    boutCount_icg_dom(i) = numel(dom_icg_bouts);
    boutCount_icg_sub(i) = numel(sub_icg_bouts);
    boutCount_int_dom(i) = numel(dom_int_bouts);
    boutCount_int_sub(i) = numel(sub_int_bouts);
    
    % === MEAN BOUT LENGTH ===
    if ~isempty(dom_icg_bouts)
        meanBoutLen_icg_dom(i) = mean(dom_icg_bouts);
    else
        meanBoutLen_icg_dom(i) = NaN;
    end
    
    if ~isempty(sub_icg_bouts)
        meanBoutLen_icg_sub(i) = mean(sub_icg_bouts);
    else
        meanBoutLen_icg_sub(i) = NaN;
    end
    
    if ~isempty(dom_int_bouts)
        meanBoutLen_int_dom(i) = mean(dom_int_bouts);
    else
        meanBoutLen_int_dom(i) = NaN;
    end
    
    if ~isempty(sub_int_bouts)
        meanBoutLen_int_sub(i) = mean(sub_int_bouts);
    else
        meanBoutLen_int_sub(i) = NaN;
    end

    % === PREFERENCE INDICES ===
    % Duration-based PI
    total_int = dom_int + sub_int;
    if total_int == 0
        PI_duration(i) = NaN;
    else
        PI_duration(i) = dom_int / total_int;
    end
    
    % Bout-based PI
    total_int_bouts = boutCount_int_dom(i) + boutCount_int_sub(i);
    if total_int_bouts == 0
        PI_bouts(i) = NaN;
    else
        PI_bouts(i) = boutCount_int_dom(i) / total_int_bouts;
    end
end

%% ==== AGGREGATE FOR PLOTTING ====
% Duration metrics
inCageData = [inCage_dom, inCage_sub];
interData  = [inter_dom,  inter_sub];

meanInCage = mean(inCageData);
meanInter  = mean(interData);
semInCage = std(inCageData) / sqrt(numSessions);
semInter  = std(interData)  / sqrt(numSessions);

% Bout count metrics
boutCount_icg = [boutCount_icg_dom, boutCount_icg_sub];
boutCount_int = [boutCount_int_dom,  boutCount_int_sub];

meanBoutCount_icg = mean(boutCount_icg);
meanBoutCount_int = mean(boutCount_int);
semBoutCount_icg = std(boutCount_icg) / sqrt(numSessions);
semBoutCount_int = std(boutCount_int) / sqrt(numSessions);

% Mean bout length metrics
boutLen_icg = [meanBoutLen_icg_dom, meanBoutLen_icg_sub];
boutLen_int = [meanBoutLen_int_dom, meanBoutLen_int_sub];

meanBoutLen_icg = mean(boutLen_icg);
meanBoutLen_int = mean(boutLen_int);
semBoutLen_icg = std(boutLen_icg, 0) / sqrt(numSessions);
semBoutLen_int = std(boutLen_int, 0) / sqrt(numSessions);

%% ==== STATISTICAL TESTS ====
% Duration metrics
[~, p_inCage] = ttest(inCage_dom, inCage_sub);
[~, p_inter]  = ttest(inter_dom,  inter_sub);

% Bout count metrics
[~, p_boutCount_icg] = ttest(boutCount_icg_dom, boutCount_icg_sub);
[~, p_boutCount_int] = ttest(boutCount_int_dom,  boutCount_int_sub);

% Mean bout length metrics
[~, p_boutLen_icg] = ttest(meanBoutLen_icg_dom, meanBoutLen_icg_sub);
[~, p_boutLen_int] = ttest(meanBoutLen_int_dom,  meanBoutLen_int_sub);

% Preference Index vs 50%
validIdx_PI_dur = find(~isnan(PI_duration));
validIdx_PI_bout = find(~isnan(PI_bouts));

if length(validIdx_PI_dur) > 1
    [~, p_pi_duration] = ttest(PI_duration(validIdx_PI_dur), 0.5);
else
    p_pi_duration = NaN;
end

if length(validIdx_PI_bout) > 1
    [~, p_pi_bouts] = ttest(PI_bouts(validIdx_PI_bout), 0.5);
else
    p_pi_bouts = NaN;
end

labelInCage = pval2sig(p_inCage);
labelInter  = pval2sig(p_inter);
labelBoutCount_icg = pval2sig(p_boutCount_icg);
labelBoutCount_int = pval2sig(p_boutCount_int);
labelBoutLen_icg = pval2sig(p_boutLen_icg);
labelBoutLen_int = pval2sig(p_boutLen_int);
labelPI_duration = pval2sig(p_pi_duration);
labelPI_bouts = pval2sig(p_pi_bouts);

%% ==== PLOTTING: DURATION METRICS ====
figure('Name', 'Duration Metrics', 'Position', [100, 100, 950, 600]);

barX = [1, 2];
jitter = 0.12;

% --- Plot 1: In-Cage Percentage ---
subplot(1,2,1);
b1 = bar(barX, meanInCage, 'FaceColor', [0.4 0.6 0.8], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
hold on;

errorbar(barX, meanInCage, semInCage, 'k.', 'LineWidth', 1.2, 'HandleVisibility', 'off');

for i = 1:numSessions
    x_dom = barX(1) + (rand - 0.5) * jitter;
    x_sub = barX(2) + (rand - 0.5) * jitter;
    plot([x_dom, x_sub], [inCage_dom(i), inCage_sub(i)], 'k-', 'LineWidth', 0.8, 'HandleVisibility', 'off');
    scatter(x_dom, inCage_dom(i), 60, 'ko', 'MarkerFaceColor', [0.2 0.4 0.6]);
    scatter(x_sub, inCage_sub(i), 60, 'ko', 'MarkerFaceColor', [0.6 0.8 1.0]);
end

set(gca, 'XTick', barX, 'XTickLabel', {'Dom', 'Sub'});
ylabel('In-Cage Time (%)');
title('Total In-Cage Time (Duration)');
ylim([0, 65]);
box on; grid on;

y_data_top = max([meanInCage + semInCage, inCage_dom.', inCage_sub.']);
add_sig_bracket(1, 2, y_data_top, p_inCage, 'FontSize', 12);

% --- Plot 2: Interaction Percentage ---
subplot(1,2,2);
b2 = bar(barX, meanInter, 'FaceColor', [0.8 0.5 0.3], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
hold on;

errorbar(barX, meanInter, semInter, 'k.', 'LineWidth', 1.2, 'HandleVisibility', 'off');

for i = 1:numSessions
    x_dom = barX(1) + (rand - 0.5) * jitter;
    x_sub = barX(2) + (rand - 0.5) * jitter;
    plot([x_dom, x_sub], [inter_dom(i), inter_sub(i)], 'k-', 'LineWidth', 0.8, 'HandleVisibility', 'off');
    scatter(x_dom, inter_dom(i), 60, 'ko', 'MarkerFaceColor', [0.6 0.2 0.1]);
    scatter(x_sub, inter_sub(i), 60, 'ko', 'MarkerFaceColor', [1.0 0.7 0.5]);
end

set(gca, 'XTick', barX, 'XTickLabel', {'Dom', 'Sub'});
ylabel('Interaction Time (%)');
ylim([0 65]);
title('Total Interaction Time (Duration)');
box on; grid on;

allYVals = [meanInter + semInter, inter_dom.', inter_sub.'];
yMax = max(allYVals) + 5;
plot([1 2], [yMax yMax], 'k-', 'LineWidth', 1);
text(1.5, yMax + 1, labelInter, 'HorizontalAlignment', 'center', 'FontSize', 12, 'FontWeight', 'bold');

if processFrameRange
    sgtitle(sprintf('Duration Metrics (n = %d sessions, Frames %d-%d)', ...
        numSessions, frameStart, frameEnd), 'FontSize', 12);
else
    sgtitle(sprintf('Duration Metrics (n = %d sessions)', numSessions), 'FontSize', 12);
end

%% ==== PLOTTING: BOUT COUNT METRICS ====
figure('Name', 'Bout Count Metrics', 'Position', [100, 100, 950, 600]);

% --- Plot 1: In-Cage Bout Counts ---
subplot(1,2,1);
b1 = bar(barX, meanBoutCount_icg, 'FaceColor', [0.4 0.6 0.8], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
hold on;

errorbar(barX, meanBoutCount_icg, semBoutCount_icg, 'k.', 'LineWidth', 1.2, 'HandleVisibility', 'off');

for i = 1:numSessions
    x_dom = barX(1) + (rand - 0.5) * jitter;
    x_sub = barX(2) + (rand - 0.5) * jitter;
    plot([x_dom, x_sub], [boutCount_icg_dom(i), boutCount_icg_sub(i)], 'k-', 'LineWidth', 0.8, 'HandleVisibility', 'off');
    scatter(x_dom, boutCount_icg_dom(i), 60, 'ko', 'MarkerFaceColor', [0.2 0.4 0.6]);
    scatter(x_sub, boutCount_icg_sub(i), 60, 'ko', 'MarkerFaceColor', [0.6 0.8 1.0]);
end

set(gca, 'XTick', barX, 'XTickLabel', {'Dom', 'Sub'});
ylabel('Number of Bouts');
title('In-Cage Bout Count');
ylim([0, max([meanBoutCount_icg + semBoutCount_icg, boutCount_icg_dom.', boutCount_icg_sub.']) * 1.2]);
box on; grid on;

y_data_top = max([meanBoutCount_icg + semBoutCount_icg, boutCount_icg_dom.', boutCount_icg_sub.']);
add_sig_bracket(1, 2, y_data_top, p_boutCount_icg, 'FontSize', 12);

% --- Plot 2: Interaction Bout Counts ---
subplot(1,2,2);
b2 = bar(barX, meanBoutCount_int, 'FaceColor', [0.8 0.5 0.3], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
hold on;

errorbar(barX, meanBoutCount_int, semBoutCount_int, 'k.', 'LineWidth', 1.2, 'HandleVisibility', 'off');

for i = 1:numSessions
    x_dom = barX(1) + (rand - 0.5) * jitter;
    x_sub = barX(2) + (rand - 0.5) * jitter;
    plot([x_dom, x_sub], [boutCount_int_dom(i), boutCount_int_sub(i)], 'k-', 'LineWidth', 0.8, 'HandleVisibility', 'off');
    scatter(x_dom, boutCount_int_dom(i), 60, 'ko', 'MarkerFaceColor', [0.6 0.2 0.1]);
    scatter(x_sub, boutCount_int_sub(i), 60, 'ko', 'MarkerFaceColor', [1.0 0.7 0.5]);
end

set(gca, 'XTick', barX, 'XTickLabel', {'Dom', 'Sub'});
ylabel('Number of Bouts');
ylim([0, max([meanBoutCount_int + semBoutCount_int, boutCount_int_dom.', boutCount_int_sub.']) * 1.2]);
title('Interaction Bout Count');
box on; grid on;

allYVals = [meanBoutCount_int + semBoutCount_int, boutCount_int_dom.', boutCount_int_sub.'];
yMax = max(allYVals) + 2;
plot([1 2], [yMax yMax], 'k-', 'LineWidth', 1);
text(1.5, yMax + 1, labelBoutCount_int, 'HorizontalAlignment', 'center', 'FontSize', 12, 'FontWeight', 'bold');

if processFrameRange
    sgtitle(sprintf('Bout Count Metrics (n = %d sessions, Frames %d-%d)', ...
        numSessions, frameStart, frameEnd), 'FontSize', 12);
else
    sgtitle(sprintf('Bout Count Metrics (n = %d sessions)', numSessions), 'FontSize', 12);
end

%% ==== PLOTTING: MEAN BOUT LENGTH METRICS ====
figure('Name', 'Mean Bout Length Metrics', 'Position', [100, 100, 950, 600]);

% --- Plot 1: In-Cage Mean Bout Length ---
subplot(1,2,1);
b1 = bar(barX, meanBoutLen_icg, 'FaceColor', [0.4 0.6 0.8], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
hold on;

errorbar(barX, meanBoutLen_icg, semBoutLen_icg, 'k.', 'LineWidth', 1.2, 'HandleVisibility', 'off');

for i = 1:numSessions
    x_dom = barX(1) + (rand - 0.5) * jitter;
    x_sub = barX(2) + (rand - 0.5) * jitter;
    if ~isnan(meanBoutLen_icg_dom(i)) && ~isnan(meanBoutLen_icg_sub(i))
        plot([x_dom, x_sub], [meanBoutLen_icg_dom(i), meanBoutLen_icg_sub(i)], 'k-', 'LineWidth', 0.8, 'HandleVisibility', 'off');
    end
    if ~isnan(meanBoutLen_icg_dom(i))
        scatter(x_dom, meanBoutLen_icg_dom(i), 60, 'ko', 'MarkerFaceColor', [0.2 0.4 0.6]);
    end
    if ~isnan(meanBoutLen_icg_sub(i))
        scatter(x_sub, meanBoutLen_icg_sub(i), 60, 'ko', 'MarkerFaceColor', [0.6 0.8 1.0]);
    end
end

set(gca, 'XTick', barX, 'XTickLabel', {'Dom', 'Sub'});
ylabel('Mean Bout Length (frames)');
title('In-Cage Mean Bout Duration');
ylim([0, max([meanBoutLen_icg + semBoutLen_icg, meanBoutLen_icg_dom.', meanBoutLen_icg_sub.']) * 1.2]);
box on; grid on;

y_data_top = max([meanBoutLen_icg + semBoutLen_icg, meanBoutLen_icg_dom.', meanBoutLen_icg_sub.']);
add_sig_bracket(1, 2, y_data_top, p_boutLen_icg, 'FontSize', 12);

% --- Plot 2: Interaction Mean Bout Length ---
subplot(1,2,2);
b2 = bar(barX, meanBoutLen_int, 'FaceColor', [0.8 0.5 0.3], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
hold on;

errorbar(barX, meanBoutLen_int, semBoutLen_int, 'k.', 'LineWidth', 1.2, 'HandleVisibility', 'off');

for i = 1:numSessions
    x_dom = barX(1) + (rand - 0.5) * jitter;
    x_sub = barX(2) + (rand - 0.5) * jitter;
    if ~isnan(meanBoutLen_int_dom(i)) && ~isnan(meanBoutLen_int_sub(i))
        plot([x_dom, x_sub], [meanBoutLen_int_dom(i), meanBoutLen_int_sub(i)], 'k-', 'LineWidth', 0.8, 'HandleVisibility', 'off');
    end
    if ~isnan(meanBoutLen_int_dom(i))
        scatter(x_dom, meanBoutLen_int_dom(i), 60, 'ko', 'MarkerFaceColor', [0.6 0.2 0.1]);
    end
    if ~isnan(meanBoutLen_int_sub(i))
        scatter(x_sub, meanBoutLen_int_sub(i), 60, 'ko', 'MarkerFaceColor', [1.0 0.7 0.5]);
    end
end

set(gca, 'XTick', barX, 'XTickLabel', {'Dom', 'Sub'});
ylabel('Mean Bout Length (frames)');
ylim([0, max([meanBoutLen_int + semBoutLen_int, meanBoutLen_int_dom.', meanBoutLen_int_sub.']) * 1.2]);
title('Interaction Mean Bout Duration');
box on; grid on;

allYVals = [meanBoutLen_int + semBoutLen_int, meanBoutLen_int_dom.', meanBoutLen_int_sub.'];
yMax = max(allYVals) + 2;
plot([1 2], [yMax yMax], 'k-', 'LineWidth', 1);
text(1.5, yMax + 1, labelBoutLen_int, 'HorizontalAlignment', 'center', 'FontSize', 12, 'FontWeight', 'bold');

if processFrameRange
    sgtitle(sprintf('Mean Bout Length Metrics (n = %d sessions, Frames %d-%d)', ...
        numSessions, frameStart, frameEnd), 'FontSize', 12);
else
    sgtitle(sprintf('Mean Bout Length Metrics (n = %d sessions)', numSessions), 'FontSize', 12);
end

%% ==== PLOT: PREFERENCE INDICES ====
figure('Name', 'Preference Indices', 'Position', [100, 100, 800, 600]);

% --- PI Duration ---
subplot(1,2,1); hold on;

meanPI_dur_pct = mean(PI_duration) * 100;
semPI_dur_pct  = std(PI_duration) / sqrt(sum(~isnan(PI_duration))) * 100;

b = bar(1, meanPI_dur_pct, 'FaceColor', [0.4 0.6 0.8], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
errorbar(1, meanPI_dur_pct, semPI_dur_pct, 'k.', 'LineWidth', 1.5, 'HandleVisibility', 'off');

for i = 1:length(validIdx_PI_dur)
    xi = 1 + (rand - 0.5) * 0.2;
    scatter(xi, PI_duration(validIdx_PI_dur(i)) * 100, 60, 'ko', ...
        'MarkerFaceColor', [0.1 0.4 0.7], 'MarkerFaceAlpha', 0.8);
end

yline(50, '--', 'k', 'LineWidth', 1);

set(gca, 'XTick', 1, 'XTickLabel', {'Pref for Dom (%)'});
ylabel('Preference Index (%)');
title('Social Preference (Duration-Based)');
ylim([0, 100]); xlim([0.5, 1.5]); box on; grid on;

yTop = meanPI_dur_pct + semPI_dur_pct + 5;
plot([1 1], [yTop yTop+3], 'k-', 'LineWidth', 1);
text(1, yTop+4, labelPI_duration, 'HorizontalAlignment', 'center', 'FontWeight', 'bold');

% --- PI Bouts ---
subplot(1,2,2); hold on;

meanPI_bout_pct = mean(PI_bouts) * 100;
semPI_bout_pct  = std(PI_bouts) / sqrt(sum(~isnan(PI_bouts))) * 100;

b = bar(1, meanPI_bout_pct, 'FaceColor', [0.8 0.5 0.3], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
errorbar(1, meanPI_bout_pct, semPI_bout_pct, 'k.', 'LineWidth', 1.5, 'HandleVisibility', 'off');

for i = 1:length(validIdx_PI_bout)
    xi = 1 + (rand - 0.5) * 0.2;
    scatter(xi, PI_bouts(validIdx_PI_bout(i)) * 100, 60, 'ko', ...
        'MarkerFaceColor', [0.6 0.2 0.1], 'MarkerFaceAlpha', 0.8);
end

yline(50, '--', 'k', 'LineWidth', 1);

set(gca, 'XTick', 1, 'XTickLabel', {'Pref for Dom (%)'});
ylabel('Preference Index (%)');
title('Social Preference (Bout Count-Based)');
ylim([0, 100]); xlim([0.5, 1.5]); box on; grid on;

yTop = meanPI_bout_pct + semPI_bout_pct + 5;
plot([1 1], [yTop yTop+3], 'k-', 'LineWidth', 1);
text(1, yTop+4, labelPI_bouts, 'HorizontalAlignment', 'center', 'FontWeight', 'bold');

if processFrameRange
    sgtitle(sprintf('Preference Indices (Frames %d-%d)', frameStart, frameEnd), 'FontSize', 12);
else
    sgtitle('Preference Indices', 'FontSize', 12);
end

%% ==== SAVE ALL FIGURES ====
figures_dir = fullfile(dataFolder, 'figures');
if ~exist(figures_dir, 'dir')
    mkdir(figures_dir);
end

fig_handles = findobj('Type', 'figure');

for fIdx = 1:length(fig_handles)
    fig = fig_handles(fIdx);
    
    fig_name = fig.Name;
    if isempty(fig_name) || strcmp(fig_name, sprintf('Figure %d', fIdx))
        fig_name = sprintf('figure_%d', fIdx);
    end
    
    fig_name = regexprep(fig_name, '[\\/:*?"<>|\s]', '_');
    
    if processFrameRange
        fig_name = [fig_name, '_frames_', num2str(frameStart), '_', num2str(frameEnd)];
    end
    
    png_path = fullfile(figures_dir, [fig_name, '.png']);
    
    try
        exportgraphics(fig, png_path, 'Resolution', 600);
    catch
        print(fig, png_path, '-dpng', '-r600');
    end
    
    fprintf('Saved: %s\n', png_path);
end

fprintf('\nAll figures saved to:\n%s\n', figures_dir);

%% ==== HELPER FUNCTIONS ====

function bouts = extract_bout_durations(is_behavior, min_frames)
    % Extract bout durations from binary behavior vector
    % Uses diff() with padding to find bout boundaries
    
    if isempty(is_behavior) || ~any(is_behavior)
        bouts = [];
        return;
    end
    
    % Pad with zeros and find transitions
    d = diff([0; is_behavior(:); 0]);
    
    % Identify bout boundaries
    bout_starts = find(d == 1);       % Rising edge: 0→1
    bout_ends   = find(d == -1) - 1;  % Falling edge: 1→0 (adjust for padding)
    
    % Calculate durations
    durations = bout_ends - bout_starts + 1;
    
    % Filter by minimum threshold
    bouts = durations(durations >= min_frames);
end

function label = pval2sig(p)
    if isnan(p)
        label = "N/A";
    elseif p < 0.001
        label = ["***","(p="+string(p)+")"];
    elseif p < 0.01
        label = ["**","(p="+string(p)+")"];
    elseif p < 0.05
        label = ["*","(p="+string(p)+")"];
    else
        label = "p="+string(p);
    end
end

function add_sig_bracket(x1, x2, y_base, pval, varargin)
    ax = gca;
    
    ylims = ax.YLim;
    y_range = diff(ylims);
    y_margin = 0.05 * y_range;
    y_line  = min(y_base, ylims(2) - y_margin);
    y_text  = y_line + 0.6 * y_margin;
    
    plot([x1 x2], [y_line y_line], 'k-', 'LineWidth', 1.0);
    plot([x1 x1], [y_line y_line + 0.2*y_margin], 'k-', 'LineWidth', 1.0);
    plot([x2 x2], [y_line y_line + 0.2*y_margin], 'k-', 'LineWidth', 1.0);
    
    label = pval2sig(pval);
    
    if iscell(label)
        y_text = y_line + 0.8*y_margin;
    end
    
    text((x1+x2)/2, y_text, label, ...
        'HorizontalAlignment', 'center', ...
        'FontWeight', 'bold', ...
        varargin{:});
    
    if y_text > ylims(2)
        ax.YLim(2) = y_text + 0.1*y_margin;
    end
end