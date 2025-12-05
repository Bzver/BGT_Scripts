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

%% ==== EXTRACT DAY NUMBERS (if filenames start with Day{n}) ====
dayNum = nan(numSessions, 1);
hasDayInfo = false;

for i = 1:numSessions
    [~, name, ~] = fileparts(matFiles{i});
    % Try matching 'Day' followed by digits at start of filename
    tk = regexp(name, '^Day(\d+)', 'tokens');
    if ~isempty(tk)
        dayNum(i) = str2double(tk{1}{1});
        hasDayInfo = true;
    end
end

if hasDayInfo
    % Sort files by day number (and original order within same day, for stability)
    [dayNum, idx] = sort(dayNum);
    matFiles = matFiles(idx);
    % Re-index dayNum to consecutive (e.g., Day3, Day5 → 1,2 for x-axis)
    uniqueDays = unique(dayNum);
    dayIdx = arrayfun(@(d) find(uniqueDays == d, 1), dayNum);
else
    % Fallback: assign sequential days 1:numSessions (but warn user)
    dayNum = 1:numSessions;
    dayIdx = dayNum;
    warning('No Day{n} prefix detected. Using file order as day order.');
end

%% ==== PREALLOCATE ====
inCage_dom = zeros(numSessions, 1);
inCage_sub = zeros(numSessions, 1);
inter_dom  = zeros(numSessions, 1);
inter_sub  = zeros(numSessions, 1);

% Locomotion stats
dom_avg_sp  = zeros(numSessions, 1);
sub_avg_sp  = zeros(numSessions, 1);
dom_avgm_sp = zeros(numSessions, 1);
sub_avgm_sp = zeros(numSessions, 1);
dom_mperc   = zeros(numSessions, 1);
sub_mperc   = zeros(numSessions, 1);

% Preference index
PI = zeros(numSessions, 1);

%% ==== PROCESS EACH FILE ====
cage_ids = cell(numSessions, 1);
segment_ids = cell(numSessions, 1);
cage_segment_keys = cell(numSessions, 1);  % 'cage_segment' unique key

for i = 1:numSessions
    fprintf('Processing %s...\n', matFiles{i});
    
    [~, name, ~] = fileparts(matFiles{i});
    
    % ==== NEW: Parse {cage}_{segment_id}_Day{n}
    % Example: "20_20251018_Day1" => cage='20', segment='20251018', day='1'
    tk = regexp(name, '^(\d+)_(\d+)_Day(\d+)', 'tokens');
    if ~isempty(tk)
        cage_ids{i} = tk{1}{1};
        segment_ids{i} = tk{1}{2};
        cage_segment_keys{i} = [tk{1}{1}, '_', tk{1}{2}];  % e.g., '20_20251018'
        dayNum(i) = str2double(tk{1}{3});
        hasDayInfo = true;
    else
        error('Filename format unsupported: %s. Expected {cage}_{segment}_Day{n}', name);
    end

    % Load and process as before
    S = load(matFiles{i});
    annotStruct = S.annotation;
    
    annot = int32(annotStruct.annotation);
    behaviors = annotStruct.behaviors;
    
    behavior_names = string(fieldnames(behaviors));
    beh_values = struct2array(behaviors);
    [~, idx_match] = ismember(annot, beh_values);
    annot_named = behavior_names(idx_match);
    
    totalFrames = length(annot_named);
    
    dom_icg = sum(contains(annot_named, "dom_"));
    sub_icg = sum(contains(annot_named, "sub_"));
    dom_int = sum(contains(annot_named, "dom_interaction"));
    sub_int = sum(contains(annot_named, "sub_interaction"));
    
    inCage_dom(i) = 100 * dom_icg / totalFrames;
    inCage_sub(i) = 100 * sub_icg / totalFrames;
    inter_dom(i)  = 100 * dom_int / totalFrames;
    inter_sub(i)  = 100 * sub_int / totalFrames;

    % Locomotion
    dom_avg_sp(i)  = S.locomotion.dom_avg;
    sub_avg_sp(i)  = S.locomotion.sub_avg;
    dom_avgm_sp(i) = S.locomotion.dom_avgm;
    sub_avgm_sp(i) = S.locomotion.sub_avgm;
    dom_mperc(i)   = S.locomotion.dom_mperc;
    sub_mperc(i)   = S.locomotion.sub_mperc;

    % Preference Index
    total_int = dom_int + sub_int;
    if total_int == 0
        PI(i) = NaN;
    else
        PI(i) = dom_int / total_int;
    end
end

%% ==== AGGREGATE FOR PLOTTING ====
inCageData = [inCage_dom, inCage_sub];
interData  = [inter_dom,  inter_sub];

meanInCage = mean(inCageData);
meanInter  = mean(interData);

semInCage = std(inCageData) / sqrt(numSessions);
semInter  = std(interData)  / sqrt(numSessions);

%% ==== AGGREGATE PI BY CAGE-SEGMENT (across days) ====
unique_keys = unique(cage_segment_keys);
num_groups = length(unique_keys);

meanPI_group = nan(num_groups, 1);
semPI_group  = nan(num_groups, 1);
n_group      = zeros(num_groups, 1);
group_labels = cell(num_groups, 1);

for k = 1:num_groups
    key = unique_keys{k};
    idx = strcmp(cage_segment_keys, key);
    vals = PI(idx);
    vals = vals(~isnan(vals));
    n_group(k) = numel(vals);
    group_labels{k} = key;  % e.g., '20_20251018'

    if n_group(k) > 0
        meanPI_group(k) = mean(vals) * 100;
        if n_group(k) > 1
            semPI_group(k) = std(vals) / sqrt(n_group(k)) * 100;
        else
            semPI_group(k) = 0;
        end
    end
end

%% ==== AGGREGATE PI BY SEGMENT (across cages & days) ====
unique_segments = unique(segment_ids);
num_seg_groups = length(unique_segments);

meanPI_seg = nan(num_seg_groups, 1);
semPI_seg  = nan(num_seg_groups, 1);
n_seg      = zeros(num_seg_groups, 1);

for k = 1:num_seg_groups
    seg = unique_segments{k};
    idx = strcmp(segment_ids, seg);
    vals = PI(idx);
    vals = vals(~isnan(vals));
    n_seg(k) = numel(vals);
    
    if n_seg(k) > 0
        meanPI_seg(k) = mean(vals);  % keep as fraction (0–1) for t-test
        if n_seg(k) > 1
            semPI_seg(k) = std(vals) / sqrt(n_seg(k));
        else
            semPI_seg(k) = 0;
        end
    end
end

% Overall mean ± SEM across segments (for the single bar)
meanPI_across_seg = mean(meanPI_seg) * 100;     % convert to %
semPI_across_seg  = std(meanPI_seg) / sqrt(num_seg_groups) * 100;

% One-sample t-test: are segment means ≠ 0.5 (chance)?
% Use meanPI_seg (fraction), not %, for correct stats
if num_seg_groups > 1
    [h_ttest, p_seg] = ttest(meanPI_seg, 0.5);
else
    p_seg = NaN;  % not testable
end

%% ==== STATISTICAL TESTS (overall) ====
[~, p_inCage] = ttest(inCage_dom, inCage_sub);
[~, p_inter]  = ttest(inter_dom,  inter_sub);

labelInCage = pval2sig(p_inCage);
labelInter  = pval2sig(p_inter);

%% ==== LOCOMOTION AGGREGATES ====
locoData.avg  = [dom_avg_sp,  sub_avg_sp];
locoData.avgm = [dom_avgm_sp, sub_avgm_sp];
locoData.mperc = [dom_mperc,  sub_mperc];

meanAvg  = mean(locoData.avg);
meanAvgm = mean(locoData.avgm);
meanMperc = mean(locoData.mperc);

semAvg   = std(locoData.avg)  / sqrt(numSessions);
semAvgm  = std(locoData.avgm) / sqrt(numSessions);
semMperc = std(locoData.mperc)/ sqrt(numSessions);

[~, p_avg]   = ttest(dom_avg_sp,  sub_avg_sp);
[~, p_avgm]  = ttest(dom_avgm_sp, sub_avgm_sp);
[~, p_mperc] = ttest(dom_mperc,   sub_mperc);

%% ==== PLOTTING: Behavior Summary ====
figure('Position', [100, 100, 950, 600]);

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
ylabel('In-Cage Time (%)'); title('Total In-Cage Time');
ylim([0, 65]); box on; grid on;

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
ylim([0 65]); title('Total Interaction Time');
box on; grid on;

allYVals = [meanInter + semInter, inter_dom.', inter_sub.'];
yMax = max(allYVals) + 5;
plot([1 2], [yMax yMax], 'k-', 'LineWidth', 1);
text(1.5, yMax + 1, labelInter, 'HorizontalAlignment', 'center', 'FontSize', 12, 'FontWeight', 'bold');

sgtitle(sprintf('Group-Level Behavior Summary (n = %d sessions)', numSessions), 'FontSize', 12);

%% ==== PLOT: LOCOMOTION STATS ====
figure('Position', [200, 100, 1400, 600]);

barX = [1, 2]; jitter = 0.12;

subplot(1,3,1); hold on;
bar(barX, meanAvg, 'FaceColor', [0.2 0.4 0.7], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
errorbar(barX, meanAvg, semAvg, 'k.', 'LineWidth', 1.2, 'HandleVisibility', 'off');

for i = 1:numSessions
    x1 = barX(1) + (rand - 0.5)*jitter;
    x2 = barX(2) + (rand - 0.5)*jitter;
    plot([x1,x2], [dom_avg_sp(i), sub_avg_sp(i)], 'k-', 'LineWidth', 0.8, 'HandleVisibility','off');
    scatter(x1, dom_avg_sp(i), 50, 'ko', 'MarkerFaceColor', [0.1 0.2 0.5]);
    scatter(x2, sub_avg_sp(i), 50, 'ko', 'MarkerFaceColor', [0.5 0.7 1.0]);
end
set(gca, 'XTick', barX, 'XTickLabel', {'Dom', 'Sub'});
ylabel('Avg Speed (px/s)'); title('Overall Avg Speed'); box on; grid on;
allVals = [ reshape(meanAvg + 3*semAvg, [], 1) ; dom_avg_sp(:) ; sub_avg_sp(:) ];
ylim([0, max(allVals) * 1.1]);
y_data_top = max([ (meanAvg + semAvg).' ; dom_avg_sp(:) ; sub_avg_sp(:) ]);
add_sig_bracket(1, 2, y_data_top, p_avg);

subplot(1,3,2); hold on;
bar(barX, meanAvgm, 'FaceColor', [0.2 0.6 0.5], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
errorbar(barX, meanAvgm, semAvgm, 'k.', 'LineWidth', 1.2, 'HandleVisibility', 'off');

for i = 1:numSessions
    x1 = barX(1) + (rand - 0.5)*jitter;
    x2 = barX(2) + (rand - 0.5)*jitter;
    plot([x1,x2], [dom_avgm_sp(i), sub_avgm_sp(i)], 'k-', 'LineWidth', 0.8, 'HandleVisibility','off');
    scatter(x1, dom_avgm_sp(i), 50, 'ko', 'MarkerFaceColor', [0.1 0.4 0.3]);
    scatter(x2, sub_avgm_sp(i), 50, 'ko', 'MarkerFaceColor', [0.5 0.9 0.7]);
end
set(gca, 'XTick', barX, 'XTickLabel', {'Dom', 'Sub'});
ylabel('Avg Moving Speed (px/s)'); title('When Moving'); box on; grid on;
y_data_top = max([ (meanAvgm + semAvgm).' ; dom_avgm_sp(:) ; sub_avgm_sp(:) ]);
add_sig_bracket(1, 2, y_data_top, p_avgm);

subplot(1,3,3); hold on;
bar(barX, meanMperc, 'FaceColor', [0.7 0.3 0.5], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
errorbar(barX, meanMperc, semMperc, 'k.', 'LineWidth', 1.2, 'HandleVisibility', 'off');

for i = 1:numSessions
    x1 = barX(1) + (rand - 0.5)*jitter;
    x2 = barX(2) + (rand - 0.5)*jitter;
    plot([x1,x2], [dom_mperc(i), sub_mperc(i)], 'k-', 'LineWidth', 0.8, 'HandleVisibility','off');
    scatter(x1, dom_mperc(i), 50, 'ko', 'MarkerFaceColor', [0.5 0.1 0.3]);
    scatter(x2, sub_mperc(i), 50, 'ko', 'MarkerFaceColor', [0.9 0.5 0.7]);
end
set(gca, 'XTick', barX, 'XTickLabel', {'Dom', 'Sub'});
ylabel('Moving Time (%)'); title('Locomotor Activity'); box on; grid on;
y_data_top = max([ (meanMperc + semMperc).' ; dom_mperc(:) ; sub_mperc(:) ]);
add_sig_bracket(1, 2, y_data_top, p_mperc);

sgtitle(sprintf('Locomotion Comparison (n = %d)', numSessions), 'FontSize', 12);

%% ==== PLOT: PREFERENCE INDEX + CORRELATION ====
figure('Position', [100, 550, 1200, 600]);

subplot(1,2,1); hold on;
validIdx = find(~isnan(PI));

if ~isempty(validIdx)
    meanPI_pct = mean(PI(validIdx)) * 100;
    semPI_pct  = std(PI(validIdx)) / sqrt(length(validIdx)) * 100;

    bar(1, meanPI_pct, 'FaceColor', [0.3 0.6 0.8], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
    errorbar(1, meanPI_pct, semPI_pct, 'k.', 'LineWidth', 1.5, 'HandleVisibility', 'off');

    for i = validIdx.'
        xi = 1 + (rand - 0.5) * 0.2;
        scatter(xi, PI(i) * 100, 60, 'ko', 'MarkerFaceColor', [0.1 0.4 0.7], 'MarkerFaceAlpha', 0.8);
    end

    yline(50, '--', 'k', 'LineWidth', 1);
    set(gca, 'XTick', 1, 'XTickLabel', {'Pref for Dom (%)'});
    ylabel('Preference Index (%)');
    title(sprintf('Social Preference (n = %d)', numSessions));
    ylim([0, 100]); xlim([0.5, 1.5]); box on; grid on;

    if length(validIdx) > 1
        [~, p_pi] = ttest(PI(validIdx), 0.5);
        yTop = meanPI_pct + semPI_pct + 5;
        plot([1 1], [yTop yTop+3], 'k-', 'LineWidth', 1);
        text(1, yTop+4, pval2sig(p_pi), 'HorizontalAlignment', 'center', 'FontWeight', 'bold');
    end
else
    text(0.5, 50, 'No valid PI data', 'FontSize', 12, 'HorizontalAlignment', 'center');
end

subplot(1,2,2); hold on;
dom_PI = []; dom_speed = []; sub_PI = []; sub_speed = [];
for i = validIdx.'
    dom_PI(end+1)    = PI(i) * 100;
    dom_speed(end+1) = dom_avg_sp(i);
    sub_PI(end+1)    = (1 - PI(i)) * 100;
    sub_speed(end+1) = sub_avg_sp(i);
end

if ~isempty(dom_PI)
    hDom = scatter(dom_PI, dom_speed, 80, [0.1 0.3 0.6], 'filled', 'MarkerFaceAlpha', 0.7, 'MarkerEdgeColor', 'k');
    hSub = scatter(sub_PI, sub_speed, 80, [0.6 0.1 0.2], 'filled', 'MarkerFaceAlpha', 0.7, 'MarkerEdgeColor', 'k');

    all_PI_pct = [dom_PI, sub_PI];
    all_speed  = [dom_speed, sub_speed];
    mdl = fitlm(all_PI_pct.', all_speed.');
    xFit = linspace(min(all_PI_pct), max(all_PI_pct), 100);
    yFit = mdl.Coefficients.Estimate(1) + mdl.Coefficients.Estimate(2)*xFit;
    hFit = plot(xFit, yFit, 'k--', 'LineWidth', 1.5);

    xlabel('Preference for Animal (%)');
    ylabel('Avg Speed (px/s)');
    title(sprintf('Preference Index vs Speed (R=%.2f, p=%.3f)', mdl.Rsquared.Ordinary, mdl.Coefficients.pValue(2)));
    grid on; box on;
    legend([hDom, hSub, hFit], {'Dom', 'Sub', 'Fit'}, 'Location', 'best');
else
    text(50, 0, 'No valid PI data', 'FontSize', 12, 'HorizontalAlignment', 'center');
end

sgtitle('Social Preference and Locomotion');

%% ==== PI OVER DAYS (if Day{n} detected) ====
if hasDayInfo
    figure('Position', [100, 300, 1000, 500]); hold on;

    % Group PI by day
    uniqueDaysSorted = unique(dayNum);
    PI_by_day = cell(size(uniqueDaysSorted));
    for k = 1:length(uniqueDaysSorted)
        idx = dayNum == uniqueDaysSorted(k);
        PI_by_day{k} = PI(idx);
    end

    % Compute mean ± SEM per day (in %)
    meanPI_day = nan(size(uniqueDaysSorted));
    semPI_day  = nan(size(uniqueDaysSorted));
    n_day      = zeros(size(uniqueDaysSorted));
    for k = 1:length(uniqueDaysSorted)
        vals = PI_by_day{k};
        vals = vals(~isnan(vals));
        n_day(k) = length(vals);
        if n_day(k) > 0
            meanPI_day(k) = mean(vals) * 100;
            if n_day(k) > 1
                semPI_day(k) = std(vals) / sqrt(n_day(k)) * 100;
            else
                semPI_day(k) = 0;  % no SEM for n=1, but we'll still plot
            end
        end
    end

    % === BAR PLOT ===
    barX_days = 1:length(uniqueDaysSorted);
    b = bar(barX_days, meanPI_day, 'FaceColor', [0.3 0.6 0.8], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
    errorbar(barX_days, meanPI_day, semPI_day, 'k.', 'LineWidth', 1.5, 'HandleVisibility', 'off');

    % Scatter raw PI (jittered)
    for k = 1:length(uniqueDaysSorted)
        vals = PI_by_day{k};
        vals = vals(~isnan(vals));
        if ~isempty(vals)
            xj = barX_days(k) + (rand(size(vals)) - 0.5) * 0.2;
            scatter(xj, vals * 100, 60, 'ko', ...
                'MarkerFaceColor', [0.1 0.4 0.7], 'MarkerFaceAlpha', 0.8);
        end
    end

    % Reference line at 50%
    yline(50, '--', 'k', 'LineWidth', 1);

    % Axes
    set(gca, 'XTick', barX_days, 'XTickLabel', compose('Day%d', uniqueDaysSorted));
    ylabel('Preference Index (%)');
    xlabel('Day');
    title('Preference Index Across Days');
    ylim([0, 100]); xlim([barX_days(1)-0.5, barX_days(end)+0.5]);
    box on; grid on;

    % === SIGNIFICANCE ===
    for k = 1:length(uniqueDaysSorted)
        vals = PI_by_day{k};
        vals = vals(~isnan(vals));
        if length(vals) > 1  % only test if ≥2 sessions
            [~, p_val] = ttest(vals, 0.5);
            yTop = meanPI_day(k) + semPI_day(k) + 5;
            plot([k, k], [yTop, yTop + 3], 'k-', 'LineWidth', 1);
            text(k, yTop + 4, pval2sig(p_val), ...
                'HorizontalAlignment', 'center', 'FontWeight', 'bold', 'FontSize', 10);
        end
    end
end

%% ==== NEW PLOT: PI AVERAGED BY CAGE-SEGMENT (1 point per cage-segment) ====
figure('Position', [100, 200, 1000, 500]); hold on;

barX_group = 1:num_groups;
b = bar(barX_group, meanPI_group, 'FaceColor', [0.4 0.7 0.4], ...
    'EdgeColor', 'k', 'FaceAlpha', 0.8);
errorbar(barX_group, meanPI_group, semPI_group, 'k.', 'LineWidth', 1.5, ...
    'HandleVisibility', 'off');

% Scatter raw (per-day) PI points jittered per group
for k = 1:num_groups
    key = unique_keys{k};
    idx = strcmp(cage_segment_keys, key);
    vals = PI(idx);
    vals = vals(~isnan(vals));
    if ~isempty(vals)
        xj = barX_group(k) + (rand(size(vals)) - 0.5) * 0.2;
        scatter(xj, vals * 100, 60, 'ko', ...
            'MarkerFaceColor', [0.2 0.5 0.2], 'MarkerFaceAlpha', 0.8);
    end
end

% Reference line at chance (50%)
yline(50, '--', 'k', 'LineWidth', 1);

% Labels
set(gca, 'XTick', barX_group, 'XTickLabel', group_labels, 'TickLabelInterpreter', 'none');
xtickangle(45);
ylabel('Preference Index (%)');
xlabel('Cage_Segment ID');
title('Preference Index: Mean per Cage-Segment (Across Days)');
ylim([0 100]); xlim([0.5, num_groups + 0.5]);
box on; grid on;

% ==== NEW PLOT: ONE-BAR SUMMARY OF CAGE-SEGMENT MEAN PIs ====
% Only proceed if we have at least one valid group mean
valid_group_means = meanPI_group / 100;  % Convert back to proportion for stats
valid_group_means = valid_group_means(~isnan(valid_group_means));

if ~isempty(valid_group_means)
    % Grand mean and SEM across groups (N = num_groups)
    grand_mean_pct = mean(valid_group_means) * 100;
    if numel(valid_group_means) > 1
        grand_sem_pct = std(valid_group_means) / sqrt(numel(valid_group_means)) * 100;
        [t_val, p_grand] = ttest(valid_group_means, 0.5);  % vs chance (0.5)
    else
        grand_sem_pct = 0;
        p_grand = NaN;
    end

    figure('Position', [200, 200, 600, 500]); hold on;

    % --- Bar + error bar ---
    bar(1, grand_mean_pct, 'FaceColor', [0.5 0.7 0.5], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
    errorbar(1, grand_mean_pct, grand_sem_pct, 'k.', 'LineWidth', 1.5, 'HandleVisibility', 'off');

    % --- Scatter group means (one per cage-segment) ---
    xj = 1 + (rand(size(valid_group_means)) - 0.5) * 0.3;
    scatter(xj, valid_group_means * 100, 80, 'ko', ...
        'MarkerFaceColor', [0.2 0.5 0.2], 'MarkerFaceAlpha', 0.8, 'LineWidth', 1);

    % Reference line at 50%
    yline(50, '--', 'k', 'LineWidth', 1.2);

    % Axes & labels
    set(gca, 'XTick', 1, 'XTickLabel', {'Cage-Segment Mean'});
    ylabel('Preference Index (%)');
    title(sprintf('Grand Mean PI Across Cage-Segment Groups (n = %d groups)', numel(valid_group_means)));
    ylim([0, 100]); xlim([0.5, 1.5]);
    box on; grid on;

    % --- Significance bracket vs 50% ---
    if numel(valid_group_means) > 1
        yTop = grand_mean_pct + grand_sem_pct + 5;
        add_sig_bracket(1, 1, yTop, p_grand, 'FontSize', 12);
    elseif numel(valid_group_means) == 1
        text(1, grand_mean_pct + 4, sprintf('%.1f%%', grand_mean_pct), ...
            'HorizontalAlignment', 'center', 'FontWeight', 'bold', 'FontSize', 12);
    end

else
    warning('No valid cage-segment group means for grand summary plot.');
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
    if isempty(fig_name) || startsWith(fig_name, 'Figure ')
        fig_name = sprintf('figure_%d', fIdx);
    end
    fig_name = regexprep(fig_name, '[\\/:*?"<>|\s]', '_');
    png_path = fullfile(figures_dir, [fig_name, '.png']);
    try
        exportgraphics(fig, png_path, 'Resolution', 600);
    catch
        print(fig, png_path, '-dpng', '-r600');
    end
    fprintf('Saved: %s\n', png_path);
end

fprintf('\nAll figures saved to:\n%s\n', figures_dir);
  
%% ==== Helper Functions ====
function label = pval2sig(p)
    if p < 0.001
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
    y_line = min(y_base, ylims(2) - y_margin);
    y_text = y_line + 0.6 * y_margin;
    plot([x1 x2], [y_line y_line], 'k-', 'LineWidth', 1);
    plot([x1 x1], [y_line y_line + 0.2*y_margin], 'k-', 'LineWidth', 1);
    plot([x2 x2], [y_line y_line + 0.2*y_margin], 'k-', 'LineWidth', 1);
    label = pval2sig(pval);
    text((x1+x2)/2, y_text, label, 'HorizontalAlignment', 'center', 'FontWeight', 'bold', varargin{:});
    if y_text > ylims(2)
        ax.YLim(2) = y_text + 0.1*y_margin;
    end
end