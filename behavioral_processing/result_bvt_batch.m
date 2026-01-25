clear; close all; clc;

%% ==== USER CONFIGURATION ====
folderPath = uigetdir;
if isequal(folderPath, 0)
    error("No folder is selected.")
end
dataFolder = folderPath;
matPattern = fullfile(dataFolder, "*.mat");

cutoff_pct = 50;
bin_min = 10;
fps = 10;
binSize = bin_min * 60 * fps;

% Auto-detect .mat files
matFiles = dir(matPattern);
matFiles = {matFiles.name};
matFiles = fullfile(dataFolder, matFiles);

numSessions = length(matFiles);

%% ==== TIME WINDOW SELECTION ====
timeMode = questdlg(...
    'Select time window for PI analysis:', ...
    'Time Window', ...
    'Full Session', 'Custom',...
    'Full Session');

switch timeMode
    case 'Custom'
        pctStr = inputdlg({'Start (%):','End (%):'}, 'Custom Time Window', 1, {'0','100'});
        if isempty(pctStr), error('Cancelled.'); end
        timeOpts.startPct = str2double(pctStr{1});
        timeOpts.endPct   = str2double(pctStr{2});
        if isnan(timeOpts.startPct) || isnan(timeOpts.endPct) || timeOpts.startPct >= timeOpts.endPct
            error('Invalid percent range.');
        end
        timeOpts.desc = sprintf('Custom (%.0f–%.0f%%)', timeOpts.startPct, timeOpts.endPct);
    case 'Full Session'
        timeOpts.startPct = 0;
        timeOpts.endPct   = 100;
        timeOpts.desc = 'Full Session';
end

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

% For time-course PI: store per-session binned
maxFrames = 0;
for i = 1:numSessions
    S = load(matFiles{i});
    totalFrames = length(S.annotation.annotation);
    maxFrames = max(maxFrames, totalFrames);
end
maxBins = ceil(maxFrames / binSize);
PI_time = cell(numSessions, 1); 

for i = 1:numSessions
    fprintf('Processing %s...\n', matFiles{i});
    
    [~, name, ~] = fileparts(matFiles{i});
    
    % ==== NEW: Parse {cage}_{segment_id}_Day{n}
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
    totalFrames = length(annot_named);

    % === SELECT TIME WINDOW ===
    startIdx = floor(totalFrames * timeOpts.startPct / 100) + 1;
    endIdx   = ceil(totalFrames * timeOpts.endPct / 100);
    startIdx = max(1, startIdx);
    endIdx   = min(totalFrames, endIdx);
    
    if startIdx > endIdx
        warning('Empty time window for %s. Skipping.', name);
        dom_int = 0; sub_int = 0; totalFrames_win = 1; % avoid div/0
    else
        annot_win = annot_named(startIdx:endIdx);
        totalFrames_win = length(annot_win);
        
        dom_int = sum(contains(annot_win, "dom_interaction"));
        sub_int = sum(contains(annot_win, "sub_interaction"));
    end

    dom_icg = sum(contains(annot_named, "dom_"));
    sub_icg = sum(contains(annot_named, "sub_"));
    inCage_dom(i) = 100 * dom_icg / totalFrames_win;
    inCage_sub(i) = 100 * sub_icg / totalFrames_win;
    inter_dom(i)  = 100 * dom_int / totalFrames_win;
    inter_sub(i)  = 100 * sub_int / totalFrames_win;


    % === Locomotion: ONLY load if Full Session ===
    if strcmp(timeMode, 'Full Session')
        dom_avg_sp(i)  = S.locomotion.dom_avg;
        sub_avg_sp(i)  = S.locomotion.sub_avg;
        dom_avgm_sp(i) = S.locomotion.dom_avgm;
        sub_avgm_sp(i) = S.locomotion.sub_avgm;
        dom_mperc(i)   = S.locomotion.dom_mperc;
        sub_mperc(i)   = S.locomotion.sub_mperc;
    else
        % Skip locomotion
        dom_avg_sp(i) = NaN; sub_avg_sp(i) = NaN;
        dom_avgm_sp(i) = NaN; sub_avgm_sp(i) = NaN;
        dom_mperc(i) = NaN; sub_mperc(i) = NaN;
    end

    % === Preference Index === (always computed)
    total_int = dom_int + sub_int;
    if total_int == 0
        PI(i) = NaN;
    else
        PI(i) = (dom_int - sub_int) / total_int;  % ← NEW symmetric PI
    end

    % --- TIME-COURSE PI: bin by hour (full session only) ---
    numBins = ceil(totalFrames / binSize);
    binDuration_sec = binSize / fps;
    time_sec = (0:numBins-1 + 0.5) * binDuration_sec;  % center of each bin
    time_hrs = time_sec / 3600;                        % convert to hours
    % OR, for minutes (often clearer for short bins):
    time_min = time_sec / 60;
    PI_binned = nan(1, numBins);
    for b = 1:numBins
        binStart = (b-1)*binSize + 1;
        binEnd = min(b*binSize, totalFrames);
        if binStart > totalFrames, break; end
        binAnnot = annot_named(binStart:binEnd);
        d = sum(contains(binAnnot, "dom_interaction"));
        s = sum(contains(binAnnot, "sub_interaction"));
        tot = d + s;
        if tot > 0
            PI_binned(b) = (d - s) / tot;
        else
            PI_binned(b) = NaN;  % no interaction → undefined
        end
    end
    PI_time{i} = PI_binned;
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

if num_seg_groups > 1
    [h_ttest, p_seg] = ttest(meanPI_seg, 0);
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

%% ==== PLOTTING: Behavior Summary (Interaction Only) ====

figure('Position', [100, 100, 1350, 1050]);

% ------------------------------------------------------------------
% (1) Session-level interaction: dom vs sub (all sessions)
% ------------------------------------------------------------------
subplot(2, 2, 1);
hold on;

% Plot dominant bar (left, orange)
bar(1, meanInter(1), 0.6, ...
    'FaceColor', [0.8 0.5 0.3], ...  % orange (dom)
    'EdgeColor', 'k', ...
    'FaceAlpha', 0.8);

% Plot subordinate bar (right, blue)
bar(2, meanInter(2), 0.6, ...
    'FaceColor', [0.3 0.6 0.8], ...  % blue (sub)
    'EdgeColor', 'k', ...
    'FaceAlpha', 0.8);

% Error bars
errorbar(1, meanInter(1), semInter(1), 'k.', 'LineWidth', 1.2, 'HandleVisibility', 'off');
errorbar(2, meanInter(2), semInter(2), 'k.', 'LineWidth', 1.2, 'HandleVisibility', 'off');

% Raw paired data
jitter = 0.12;
for i = 1:numSessions
    x_dom = 1 + (rand - 0.5) * jitter;
    x_sub = 2 + (rand - 0.5) * jitter;
    plot([x_dom, x_sub], [inter_dom(i), inter_sub(i)], 'k-', 'LineWidth', 0.8);
    scatter(x_dom, inter_dom(i), 60, 'ko', 'MarkerFaceColor', [0.6 0.2 0.1]);   % dark orange
    scatter(x_sub, inter_sub(i), 60, 'ko', 'MarkerFaceColor', [0.1 0.4 0.7]);   % dark blue
end

set(gca, 'XTick', [1, 2], 'XTickLabel', {'Dominant', 'Subordinate'});
ylabel('Interaction Time (%)');
ylim([0 50]); 
title(sprintf('All Sessions (n = %d)', numSessions));
box on; grid on;

% Significance
yMax = max([meanInter + semInter, [max(inter_dom), max(inter_sub)]]) + 3;;
add_sig_bracket(1, 2, yMax, p_inter, 'FontSize', 11);

% ------------------------------------------------------------------
% (2) Group-level grand mean: dom vs sub (one bar per condition)
% ------------------------------------------------------------------
subplot(2, 2, 2);

% Compute group means (once, efficiently)
unique_keys = unique(cage_segment_keys);
num_groups = length(unique_keys);
group_mean_dom = nan(num_groups, 1);
group_mean_sub = nan(num_groups, 1);

for k = 1:num_groups
    idx = strcmp(cage_segment_keys, unique_keys{k});
    dom_vals = inter_dom(idx);
    sub_vals = inter_sub(idx);
    valid = ~isnan(dom_vals) & ~isnan(sub_vals);
    if any(valid)
        group_mean_dom(k) = mean(dom_vals(valid));
        group_mean_sub(k) = mean(sub_vals(valid));
    end
end

% Grand stats across groups
valid_groups = ~isnan(group_mean_dom) & ~isnan(group_mean_sub);
dom_vals_g = group_mean_dom(valid_groups);
sub_vals_g = group_mean_sub(valid_groups);
n_eff = numel(dom_vals_g);

if n_eff == 0
    text(0.5, 50, 'No valid groups', 'HorizontalAlignment', 'center');
else
    grand_mean_dom = mean(dom_vals_g);
    grand_mean_sub = mean(sub_vals_g);
    
    if n_eff > 1
        sem_dom = std(dom_vals_g) / sqrt(n_eff);
        sem_sub = std(sub_vals_g) / sqrt(n_eff);
        [~, p_paired] = ttest(dom_vals_g, sub_vals_g);  % paired by group
    else
        sem_dom = 0; sem_sub = 0; p_paired = NaN;
    end
    
    % Plot two bars (R2022a safe)
    width = 0.6;
    bar(1, grand_mean_dom, width, 'FaceColor', [0.8 0.5 0.3], 'EdgeColor', 'k');
    hold on;
    bar(2, grand_mean_sub, width, 'FaceColor', [0.3 0.6 0.8], 'EdgeColor', 'k');
    errorbar(1, grand_mean_dom, sem_dom, 'k.', 'LineWidth', 1.5, 'HandleVisibility', 'off');
    errorbar(2, grand_mean_sub, sem_sub, 'k.', 'LineWidth', 1.5, 'HandleVisibility', 'off');
    
    % Raw group points (paired)
    for k = 1:n_eff
        j = (rand - 0.5) * 0.15;
        plot([1+j, 2+j], [dom_vals_g(k), sub_vals_g(k)], 'k:', 'LineWidth', 1);
        scatter(1+j, dom_vals_g(k), 60, 'ko', 'MarkerFaceColor', [0.6 0.2 0.1]);
        scatter(2+j, sub_vals_g(k), 60, 'ko', 'MarkerFaceColor', [0.1 0.4 0.7]);
    end
    
    set(gca, 'XTick', 1:2, 'XTickLabel', {'Dominant', 'Subordinate'});
    ylabel('Interaction Time (%)');
    title(sprintf('Group-Level (N = %d)', n_eff));
    ylim([0, 50]); grid on; box on;
    
    if n_eff > 1
        add_sig_bracket(1, 2, yMax, p_paired, 'FontSize', 11);
    end
end

% ------------------------------------------------------------------
% (3) Cage-segment detail: dom vs sub per group (paired bars)
% ------------------------------------------------------------------
subplot(2, 2, [3, 4]);  % ← spans bottom row (cols 3–4)
hold on;

% Reuse dom_vals_g/sub_vals_g computation above, but now need per-session raw data
% Recompute group-level means & SEM for bars (same as earlier)
meanDom = nan(num_groups, 1);
meanSub = nan(num_groups, 1);
semDom  = nan(num_groups, 1);
semSub  = nan(num_groups, 1);

for k = 1:num_groups
    idx = strcmp(cage_segment_keys, unique_keys{k});
    domV = inter_dom(idx);
    subV = inter_sub(idx);
    v = ~isnan(domV) & ~isnan(subV);
    domV = domV(v); subV = subV(v);
    if ~isempty(domV)
        meanDom(k) = mean(domV);
        meanSub(k) = mean(subV);
        if numel(domV) > 1
            semDom(k) = std(domV) / sqrt(numel(domV));
            semSub(k) = std(subV) / sqrt(numel(subV));
        else
            semDom(k) = 0; semSub(k) = 0;
        end
    end
end

% Plot grouped bars
barWidth = 0.35;
x = 1:num_groups;
bar(x - barWidth/2, meanDom, barWidth, 'FaceColor', [0.8 0.5 0.3], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
bar(x + barWidth/2, meanSub, barWidth, 'FaceColor', [0.3 0.6 0.8], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
errorbar(x - barWidth/2, meanDom, semDom, 'k.', 'HandleVisibility', 'off');
errorbar(x + barWidth/2, meanSub, semSub, 'k.', 'HandleVisibility', 'off');

% Paired dots & lines
jitter_range = 0.12;
for k = 1:num_groups
    idx = strcmp(cage_segment_keys, unique_keys{k});
    domV = inter_dom(idx);
    subV = inter_sub(idx);
    v = ~isnan(domV) & ~isnan(subV);
    domV = domV(v); subV = subV(v);
    if ~isempty(domV)
        jit = (rand(size(domV)) - 0.5) * jitter_range;
        xd = x(k) - barWidth/2 + jit;
        xs = x(k) + barWidth/2 + jit;
        for s = 1:numel(domV)
            plot([xd(s), xs(s)], [domV(s), subV(s)], 'k-', 'LineWidth', 0.8);
        end
        scatter(xd, domV, 60, 'ko', 'MarkerFaceColor', [0.6 0.2 0.1]);
        scatter(xs, subV, 60, 'ko', 'MarkerFaceColor', [0.1 0.4 0.7]);
    end
end

set(gca, 'XTick', x, 'XTickLabel', unique_keys, 'TickLabelInterpreter', 'none');
xtickangle(45);
ylabel('Interaction Time (%)');
title('Per Cage-Segment Group (with paired sessions)');
grid on; box on;
legend({'Dominant', 'Subordinate'}, 'Location', 'northeast');

sgtitle(sprintf('Interaction Time Summary — %s (n = %d sessions, %d groups)', ...
    timeOpts.desc, numSessions, num_groups), 'FontSize', 13);

%% ==== COMBINED PREFERENCE INDEX SUMMARY FIGURE ====
if ~isempty(PI) && any(~isnan(PI))
    figure('Position', [100, 200, 1200, 900]);
    
    % ------------------------------------------------------------------
    % (1) All Sessions PI (subplot 1,2,1)
    % ------------------------------------------------------------------
    subplot(1, 2, 1);
    hold on;
    validIdx = find(~isnan(PI));
    
    if ~isempty(validIdx)
        meanPI_pct = mean(PI(validIdx)) * 100;
        semPI_pct  = std(PI(validIdx)) / sqrt(length(validIdx)) * 100;
        
        bar(1, meanPI_pct, 0.6, 'FaceColor', [0.3 0.6 0.8], 'EdgeColor', 'k');
        errorbar(1, meanPI_pct, semPI_pct, 'k.', 'LineWidth', 1.5, 'HandleVisibility', 'off');
        
        for i = validIdx.'
            xi = 1 + (rand - 0.5) * 0.2;
            scatter(xi, PI(i) * 100, 60, 'ko', 'MarkerFaceColor', [0.1 0.4 0.7]);
        end
        
        yline(0, '--k', 'LineWidth', 1);
        set(gca, 'XTick', 1, 'XTickLabel', {'All Sessions'});
        ylabel('PI (%)');
        title(sprintf('All Sessions (n = %d)', numSessions), timeOpts.desc);
        ylim([-80, 80]); xlim([0.5, 1.5]); grid on; box on;
        
        if length(validIdx) > 1
            [~, p_pi] = ttest(PI(validIdx), 0);
            add_sig_bracket(1, 1, meanPI_pct + semPI_pct + 5, p_pi, 'FontSize', 10);
        end
    else
        text(0.5, 0, 'No data', 'HorizontalAlignment', 'center');
        set(gca, 'XTick', [], 'YTick', []);
    end
    
    % ------------------------------------------------------------------
    % (2) Group Grand Mean PI (subplot 1,2,2)
    % ------------------------------------------------------------------
    subplot(1, 2, 2);
    hold on;
    
    % Compute group-level PI means (1 per cage-segment)
    unique_keys = unique(cage_segment_keys);
    num_groups = length(unique_keys);
    group_PI = nan(num_groups, 1);
    
    for k = 1:num_groups
        idx = strcmp(cage_segment_keys, unique_keys{k});
        vals = PI(idx);
        vals = vals(~isnan(vals));
        if ~isempty(vals)
            group_PI(k) = mean(vals);
        end
    end
    
    valid_grp = ~isnan(group_PI);
    grp_vals = group_PI(valid_grp) * 100;  % convert to %
    n_grp = sum(valid_grp);
    
    if n_grp == 0
        text(0.5, 0, 'No groups', 'HorizontalAlignment', 'center');
        set(gca, 'XTick', [], 'YTick', []);
    else
        mean_grp = mean(grp_vals);
        if n_grp > 1
            sem_grp = std(grp_vals) / sqrt(n_grp);
            [~, p_grp] = ttest(grp_vals, 0);
        else
            sem_grp = 0; p_grp = NaN;
        end
        
        bar(1, mean_grp, 0.6, 'FaceColor', [0.4 0.7 0.4], 'EdgeColor', 'k');
        errorbar(1, mean_grp, sem_grp, 'k.', 'LineWidth', 1.5, 'HandleVisibility', 'off');
        
        % Raw group points
        for k = 1:n_grp
            xj = 1 + (rand - 0.5) * 0.15;
            scatter(xj, grp_vals(k), 60, 'ko', 'MarkerFaceColor', [0.2 0.5 0.2]);
        end
        
        yline(0, '--k');
        set(gca, 'XTick', 1, 'XTickLabel', {'Group Mean'});
        ylabel('PI (%)');
        title(sprintf('Cage-Segment Groups (N = %d)', n_grp), timeOpts.desc);
        ylim([-80, 80]); xlim([0.5, 1.5]); grid on; box on;
        
        if n_grp > 1
            add_sig_bracket(1, 1, mean_grp + sem_grp + 5, p_grp, 'FontSize', 10);
        end
    end
    
end

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

    % Reference line at 0%
    yline(0, '--', 'k', 'LineWidth', 1);

    % Axes
    set(gca, 'XTick', barX_days, 'XTickLabel', compose('Day%d', uniqueDaysSorted));
    ylabel('Preference Index (%)');
    xlabel('Day');
    title('Preference Index Across Days', timeOpts.desc);
    ylim([-80, 80]); xlim([barX_days(1)-0.5, barX_days(end)+0.5]);
    box on; grid on;

    % === SIGNIFICANCE ===
    for k = 1:length(uniqueDaysSorted)
        vals = PI_by_day{k};
        vals = vals(~isnan(vals));
        if length(vals) > 1  % only test if ≥2 sessions
            [~, p_val] = ttest(vals, 0);
            yTop = meanPI_day(k) + semPI_day(k) + 5;
            plot([k, k], [yTop, yTop + 3], 'k-', 'LineWidth', 1);
            text(k, yTop + 4, pval2sig(p_val), ...
                'HorizontalAlignment', 'center', 'FontWeight', 'bold', 'FontSize', 10);
        end
    end
end

%% ==== NEW: PREFERENCE INDEX OVER TIME — MEAN ± SEM SILHOUETTE ====

fprintf('\n→ Running cluster-based permutation test...\n');

% --- Build matrix of PI (rows = sessions, cols = time bins) ---
maxLen = max(cellfun(@length, PI_time));
PI_matrix = nan(numSessions, maxLen);
for i = 1:numSessions
    PI_matrix(i, 1:length(PI_time{i})) = PI_time{i};  % fill with NaN-padded rows
end

% Compute mean and SEM per bin (ignore NaNs)
meanPI_bins = nanmean(PI_matrix, 1) * 100;   % → %
semPI_bins  = nanstd(PI_matrix, 0, 1) ./ sqrt(sum(~isnan(PI_matrix), 1)) * 100;
semPI_bins(isnan(semPI_bins)) = 0;  % avoid NaN in SEM (e.g., only 1 session with data)

% --- Time axis (robust) ---
binDuration_sec = binSize / fps;
time_sec = (0:length(meanPI_bins)-1 + 0.5) * binDuration_sec;
time_min = time_sec / 60;
time_hrs = time_sec / 3600;

% Choose axis unit based on bin size
if bin_min <= 15
    time_axis = time_min;
    xlabel_str = 'Time (minutes)';
    tick_interval = 30;
else
    time_axis = time_hrs;
    xlabel_str = 'Time (hours)';
    tick_interval = 1;
end

p_vals = nan(size(meanPI_bins));
n_vals = zeros(size(meanPI_bins));
for b = 1:length(time_axis)
    vals = PI_matrix(:,b);
    vals = vals(~isnan(vals));
    n_vals(b) = numel(vals);
    if n_vals(b) > 1
        [~, p] = ttest(vals, 0);
        p_vals(b) = p;
    end
end

% ==== TEST: Earlyvs. Late Preference ====
fprintf('\n→ Testing Early vs. Late PI...\n');

PI_early = nan(numSessions, 1);
PI_late  = nan(numSessions, 1);

for i = 1:numSessions
    bins = PI_time{i};
    nBins = length(bins);
    cutoff_bin = floor(cutoff_pct / 100 * nBins);
    
    early_bins = bins(1:cutoff_bin);
    late_bins  = bins(cutoff_bin+1:end);
    
    % Use mean PI in each phase (robust to missing bins)
    early_bins = early_bins(~isnan(early_bins));
    late_bins  = late_bins(~isnan(late_bins));
    
    if ~isempty(early_bins)
        PI_early(i) = mean(early_bins);
    end
    if ~isempty(late_bins)
        PI_late(i) = mean(late_bins);
    end
end

% Keep only sessions with data in both phases
valid = ~isnan(PI_early) & ~isnan(PI_late);
PI_early = PI_early(valid);
PI_late  = PI_late(valid);
n_pair = sum(valid);
if n_pair < 2
    warning('Not enough paired data for early/late test.');
else
    % Paired t-test
    [h, p_earlyLate] = ttest(PI_early, PI_late);
    mean_early = mean(PI_early) * 100;
    mean_late  = mean(PI_late)  * 100;
    sem_early = std(PI_early) / sqrt(n_pair) * 100;
    sem_late  = std(PI_late)  / sqrt(n_pair) * 100;
    
    % Cohen's d (paired)
    diff = PI_early - PI_late;
    cohens_d = mean(diff) / std(diff);
    
    fprintf('Early PI: %.1f%% ± %.1f%%\n', mean_early, sem_early);
    fprintf('Late  PI: %.1f%% ± %.1f%%\n', mean_late,  sem_late);
    fprintf('Early vs Late: p = %.4f, d = %.2f (n = %d paired)\n', ...
            p_earlyLate, cohens_d, n_pair);
    
    % --- Plot early vs late ---
    figure('Position', [120, 250, 800, 500]);
    hold on;
    
    % === BARS ===
    bar(1, mean_early, 0.6, ...
        'FaceColor', [0.251 0.675 0.804], 'EdgeColor', 'k', 'FaceAlpha', 0, 'EdgeAlpha', 0);
    bar(2, mean_late, 0.6, ...
        'FaceColor', [0.941 0.769 0.212], 'EdgeColor', 'k', 'FaceAlpha', 0, 'EdgeAlpha', 0);
 
    % Error bars (must be after bars, and use 'HandleVisibility','off')
    errorbar(1, mean_early, sem_early, 'k.', 'LineWidth', 1.5, 'HandleVisibility', 'off');
    errorbar(2, mean_late,  sem_late,  'k.', 'LineWidth', 1.5, 'HandleVisibility', 'off');
    
    % Paired lines & scatter points
    jitter = 0.12;
    for i = 1:n_pair
        xj = (rand - 0.5) * jitter;
        plot([1+xj, 2+xj], [PI_early(i)*100, PI_late(i)*100], 'Color', [0.8 0.8 0.8], 'LineWidth', 1);
        scatter(1+xj, PI_early(i)*100, 50, [0.251, 0.675, 0.804], 'filled', 'MarkerEdgeColor', 'k',...
            'MarkerFaceAlpha', '0.3', 'MarkerEdgeAlpha', '0.3');
        scatter(2+xj, PI_late(i)*100,  50, [0.941, 0.769, 0.212], 'filled', 'MarkerEdgeColor', 'k',...
            'MarkerFaceAlpha', '0.3', 'MarkerEdgeAlpha', '0.3');
    end
    
    % === THICK MEAN-CONNECTING LINE (key request!) ===
    plot([1, 2], [mean_early, mean_late], ...
    'k-', 'LineWidth', 3, 'HandleVisibility', 'off');

    % Labels & limits
    grid on; box on;
    set(gca, ...
        'XTick', [1, 2], ...
        'XTickLabel', {sprintf('Early (≤%d)', cutoff_pct), sprintf('Late (≤%d)', cutoff_pct)}, ...
        'YLim', [-80, 80]);
    ylabel('Preference Index (%)');
    title(sprintf('Early vs Late Preference (n = %d)', n_pair), 'FontSize', 12);
    
    % Significance bracket
    yTop = max([mean_early + sem_early, mean_late + sem_late]) + 15;
    add_sig_bracket(1, 2, yTop, p_earlyLate, 'FontSize', 12);
    
    hold off;
end

%% ==== ENHANCED: PREFERENCE INDEX OVER TIME — WITH PER-DAY MEANS ====
if hasDayInfo
    figure('Position', [100, 200, 1000, 500]); hold on;

    % --- Build full matrix (sessions × bins) ---
    maxLen = max(cellfun(@length, PI_time));
    PI_matrix = nan(numSessions, maxLen);
    for i = 1:numSessions
        PI_matrix(i, 1:length(PI_time{i})) = PI_time{i};
    end

    % --- Compute grand mean and SEM (as before) ---
    meanPI_bins = nanmean(PI_matrix, 1) * 100;
    semPI_bins  = nanstd(PI_matrix, 0, 1) ./ sqrt(sum(~isnan(PI_matrix), 1)) * 100;
    semPI_bins(isnan(semPI_bins)) = 0;

    % Time axis (hours, robust)
    binDuration_sec = binSize / fps;
    time_sec = (0:length(meanPI_bins)-1 + 0.5) * binDuration_sec;
    time_hrs = time_sec / 3600;
    time_axis = time_hrs;
    xlabel_str = 'Time (hours)';
    tick_interval = 1;

    % --- Plot GRAND MEAN (black thick) + SEM shading (light blue) ---
    plot(time_axis, meanPI_bins, 'k-', 'LineWidth', 3, 'DisplayName', 'All Sessions Mean');
    
    upper = meanPI_bins + semPI_bins;
    lower = meanPI_bins - semPI_bins;
    patch([time_axis, fliplr(time_axis)], ...
          [upper, fliplr(lower)], ...
          [0.3 0.6 0.8], 'FaceAlpha', 0.3, 'EdgeColor', 'none', ...
          'DisplayName', '±SEM (All)');

    % --- Compute & plot MEAN PER DAY ---
    uniqueDaysSorted = unique(dayNum);
    colors = lines(length(uniqueDaysSorted));  % distinct colors per day
    leg_entries = {'All Sessions Mean', '±SEM (All)'};

    for dIdx = 1:length(uniqueDaysSorted)
        day = uniqueDaysSorted(dIdx);
        idx = (dayNum == day);
        day_PI_matrix = PI_matrix(idx, :);  % sessions on this day × bins
        
        % Mean per bin on this day (ignore NaNs)
        day_mean = nanmean(day_PI_matrix, 1) * 100;
        
        % Only plot if at least one session has data in that bin
        valid_bins = sum(~isnan(day_PI_matrix), 1) > 0;
        if any(valid_bins)
            % Interpolate or hold last value? Better: omit bins with no data
            % But for continuity, we plot only where ≥1 session has data
            plot(time_axis(valid_bins), day_mean(valid_bins), '-', ...
                 'Color', [colors(dIdx,:), 0.5], 'LineWidth', 2, ...
                 'DisplayName', sprintf('Day%d Mean', day));
            leg_entries{end+1} = sprintf('Day%d Mean', day);
        end
    end

    % Reference line at 0%
    yline(0, '--k', 'LineWidth', 1.2, 'HandleVisibility', 'off');

    % Axes formatting
    xlabel(xlabel_str, 'FontSize', 12);
    ylabel('Preference Index (%)', 'FontSize', 12);
    title(sprintf('Preference Index Over Time (%d-min bins; Day-wise Means)', bin_min), 'FontSize', 13);
    ylim([-100, 100]); xlim([0, max(time_axis)]);
    grid on; box on;
    xticks(0:tick_interval:max(time_axis));

    % === Early/Late shading & annotations (reuse your cutoff_pct) ===
    early_end = floor(cutoff_pct / 100 * length(time_axis));
    early_x = time_axis(early_end);
    
    area([0, early_x], [100, 100], ...
         'FaceColor', [0.9 0.95 1], 'EdgeColor','none', ...
         'BaseValue', -100, 'FaceAlpha', 0.3);
    area([early_x, max(time_axis)], [100, 100], ...
         'FaceColor', [1 0.95 0.9], 'EdgeColor','none', ...
         'BaseValue', -100, 'FaceAlpha', 0.3);
    xline(early_x, '--', [0.3 0.3 0.3], 'LineWidth', 1.5, ...
          'Label', sprintf('Early/Late (%d%%)', cutoff_pct), ...
          'LabelVerticalAlignment', 'bottom');

    % Annotate early/late means (if computed)
    if exist('mean_early', 'var') && exist('mean_late', 'var')
        early_mid = mean([time_axis(1), early_x]);
        late_mid  = mean([early_x, max(time_axis)]);
        text(early_mid, 30, sprintf('Early\n%.0f%%', mean_early), ...
             'BackgroundColor','w','HorizontalAlignment','center','FontSize',10);
        text(late_mid, 30, sprintf('Late\n%.0f%%', mean_late), ...
             'BackgroundColor','w','HorizontalAlignment','center','FontSize',10);
    end
    legend(leg_entries, 'Location', 'northeastoutside');
else
    % Fallback: no day info → just plot grand mean (your original)
    figure('Position', [100, 200, 1000, 500]); hold on;
    plot(time_axis, meanPI_bins, 'k-', 'LineWidth', 3, 'DisplayName', 'Mean PI');
    patch([time_axis, fliplr(time_axis)], ...
          [upper, fliplr(lower)], ...
          [0.3 0.6 0.8], 'FaceAlpha', 0.3, 'EdgeColor', 'none');
    yline(0, '--k');
    xlabel(xlabel_str); ylabel('Preference Index (%)');
    title(sprintf('Preference Index Over Time (%d-min bins)', bin_min));
    ylim([-100,100]); grid on; box on;
    xticks(0:tick_interval:max(time_axis));
end

%% ==== PLOT: LOCOMOTION STATS ====
if strcmp(timeMode, 'Full Session')
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
    if ~strcmp(timeMode, 'Full Session')
        fig_name = [fig_name, '_', regexprep(timeOpts.desc, '\s', '_')];
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

%% ==== Helper Functions ====
function label = pval2sig(p)
    if p < 0.001
        label = ["(p="+string(p)+")","***"];
    elseif p < 0.01
        label = ["(p="+string(p)+")","**"];
    elseif p < 0.05
        label = ["(p="+string(p)+")","*"];
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