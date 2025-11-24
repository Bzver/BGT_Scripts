clear; close all; clc;

%% ==== USER CONFIGURATION ====
folderPath = uigetdir;
if isequal(folderPath, 0)
    error("No folder is selected.")
end
dataFolder = folderPath;  % Adjust as needed
matPattern = fullfile(dataFolder, "*.mat");

% Auto-detect .mat files
matFiles = dir(matPattern);
matFiles = {matFiles.name};
matFiles = fullfile(dataFolder, matFiles);

numSessions = length(matFiles);

%% ==== PREALLOCATE ====
inCage_dom = zeros(numSessions, 1);
inCage_sub = zeros(numSessions, 1);
inter_dom  = zeros(numSessions, 1);
inter_sub  = zeros(numSessions, 1);

% Locomotion stats (scalar per session, per animal)
dom_avg_sp  = zeros(numSessions, 1);
sub_avg_sp  = zeros(numSessions, 1);
dom_avgm_sp = zeros(numSessions, 1);
sub_avgm_sp = zeros(numSessions, 1);
dom_mperc   = zeros(numSessions, 1);
sub_mperc   = zeros(numSessions, 1);

% Preference index
PI = zeros(numSessions, 1);

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
    
    totalFrames = length(annot_named);
    
    dom_icg = sum(contains(annot_named, "dom_"));
    sub_icg = sum(contains(annot_named, "sub_"));
    dom_int = sum(contains(annot_named, "dom_interaction"));
    sub_int = sum(contains(annot_named, "sub_interaction"));
    
    inCage_dom(i) = 100 * dom_icg / totalFrames;
    inCage_sub(i) = 100 * sub_icg / totalFrames;
    inter_dom(i)  = 100 * dom_int / totalFrames;
    inter_sub(i)  = 100 * sub_int / totalFrames;

    % --- Locomotion stats ---
    dom_avg_sp(i)  = S.locomotion.dom_avg;
    sub_avg_sp(i)  = S.locomotion.sub_avg;
    dom_avgm_sp(i) = S.locomotion.dom_avgm;
    sub_avgm_sp(i) = S.locomotion.sub_avgm;
    dom_mperc(i)   = S.locomotion.dom_mperc;
    sub_mperc(i)   = S.locomotion.sub_mperc;

    % --- Preference Index for third mouse ---
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

% Standard Error of the Mean (SEM)
semInCage = std(inCageData) / sqrt(numSessions);
semInter  = std(interData)  / sqrt(numSessions);

%% ==== STATISTICAL TESTS ====
% Paired t-tests
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

% Paired t-tests
[~, p_avg]   = ttest(dom_avg_sp,  sub_avg_sp);
[~, p_avgm]  = ttest(dom_avgm_sp, sub_avgm_sp);
[~, p_mperc] = ttest(dom_mperc,   sub_mperc);

%% ==== PLOTTING ====
figure('Position', [100, 100, 950, 600]);

barX = [1, 2];
jitter = 0.12;

% --- Plot 1: In-Cage Percentage ---
subplot(1,2,1);
b1 = bar(barX, meanInCage, 'FaceColor', [0.4 0.6 0.8], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
hold on;

% Add error bars
errorbar(barX, meanInCage, semInCage, 'k.', 'LineWidth', 1.2, 'HandleVisibility', 'off');

% Scatter and paired lines
for i = 1:numSessions
    x_dom = barX(1) + (rand - 0.5) * jitter;
    x_sub = barX(2) + (rand - 0.5) * jitter;
    plot([x_dom, x_sub], [inCage_dom(i), inCage_sub(i)], 'k-', 'LineWidth', 0.8, 'HandleVisibility', 'off');
    scatter(x_dom, inCage_dom(i), 60, 'ko', 'MarkerFaceColor', [0.2 0.4 0.6]);
    scatter(x_sub, inCage_sub(i), 60, 'ko', 'MarkerFaceColor', [0.6 0.8 1.0]);
end

set(gca, 'XTick', barX, 'XTickLabel', {'Dom', 'Sub'});
ylabel('In-Cage Time (%)');
title('Total In-Cage Time');
ylim([0, 65]);
box on; grid on;

% Compute data top (max of means+sem and raw data)
y_data_top = max([meanInCage + semInCage, inCage_dom.', inCage_sub.']);
add_sig_bracket(1, 2, y_data_top, p_inCage, 'FontSize', 12);

% --- Plot 2: Interaction Percentage ---
subplot(1,2,2);
b2 = bar(barX, meanInter, 'FaceColor', [0.8 0.5 0.3], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
hold on;

% Add error bars
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
title('Total Interaction Time');
box on; grid on;

% Add significance annotation
allYVals = [meanInter + semInter, inter_dom.', inter_sub.'];
yMax = max(allYVals) + 5;
plot([1 2], [yMax yMax], 'k-', 'LineWidth', 1);
text(1.5, yMax + 1, labelInter, 'HorizontalAlignment', 'center', 'FontSize', 12, 'FontWeight', 'bold');

sgtitle(sprintf('Group-Level Behavior Summary (n = %d sessions)', numSessions), 'FontSize', 12);

%% ==== PLOT: LOCOMOTION STATS ====
figure('Position', [200, 100, 1400, 600]);

barX = [1, 2];
jitter = 0.12;

% --- Avg Speed ---
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
ylabel('Avg Speed (px/s)'); title('Overall Avg Speed');
box on; grid on;
allVals = [ reshape(meanAvg + 3*semAvg, [], 1) ; dom_avg_sp(:) ; sub_avg_sp(:) ];
ylim([0, max(allVals) * 1.1]);

% Sig
y_data_top = max([ (meanAvg + semAvg).' ; dom_avg_sp(:) ; sub_avg_sp(:) ]);
add_sig_bracket(1, 2, y_data_top, p_avg);

% --- Avg Moving Speed ---
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
ylabel('Avg Moving Speed (px/s)'); title('When Moving');
box on; grid on;

y_data_top = max([ (meanAvgm + semAvgm).' ; dom_avgm_sp(:) ; sub_avgm_sp(:) ]);
add_sig_bracket(1, 2, y_data_top, p_avgm);

% --- Moving Percentage ---
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
ylabel('Moving Time (%)'); title('Locomotor Activity');
box on; grid on;

y_data_top = max([ (meanMperc + semMperc).' ; dom_mperc(:) ; sub_mperc(:) ]);
add_sig_bracket(1, 2, y_data_top, p_mperc);

sgtitle(sprintf('Locomotion Comparison (n = %d)', numSessions), 'FontSize', 12);

%% ==== PLOT: PREFERENCE INDEX + CORRELATION ====
figure('Position', [100, 550, 1200, 600]);

% --- Subplot 1: PI Bar Plot ---
subplot(1,2,1); hold on;

% Compute mean PI (%) and SEM
meanPI_pct = mean(PI, 'omitnan') * 100;
semPI_pct  = std(PI, 'omitnan') / sqrt(sum(~isnan(PI))) * 100;

% Bar at x=1
b = bar(1, meanPI_pct, 'FaceColor', [0.3 0.6 0.8], 'EdgeColor', 'k', 'FaceAlpha', 0.8);
errorbar(1, meanPI_pct, semPI_pct, 'k.', 'LineWidth', 1.5, 'HandleVisibility', 'off');

% Scatter raw PI values (jittered)
validIdx = find(~isnan(PI));
for i = 1:length(validIdx)
    xi = 1 + (rand - 0.5) * 0.2;  % jitter around x=1
    scatter(xi, PI(validIdx(i)) * 100, 60, 'ko', ...
        'MarkerFaceColor', [0.1 0.4 0.7], 'MarkerFaceAlpha', 0.8);
end

% Reference line at 50% (no preference)
yline(50, '--', 'k', 'LineWidth', 1);

% Axes
set(gca, 'XTick', 1, 'XTickLabel', {'Pref for Dom (%)'});
ylabel('Preference Index (%)');
title(sprintf('Social Preference (n = %d)', numSessions));
ylim([0, 100]); xlim([0.5, 1.5]); box on; grid on;

% Significance vs 50%
if length(validIdx) > 1
    [~, p_pi] = ttest(PI(validIdx), 0.5);
    % Annotate above bar
    yTop = meanPI_pct + semPI_pct + 5;
    plot([1 1], [yTop yTop+3], 'k-', 'LineWidth', 1);
    text(1, yTop+4, pval2sig(p_pi), 'HorizontalAlignment', 'center', 'FontWeight', 'bold');
end

% --- Subplot 2: Scatter: PI vs Avg Speed ---
subplot(1,2,2); hold on;

% Pre-allocate
dom_PI = []; dom_speed = [];
sub_PI = []; sub_speed = [];

for i = 1:numSessions
    if ~isnan(PI(i))
        dom_PI(end+1)    = PI(i) * 100;      % Dom preference %
        dom_speed(end+1) = dom_avg_sp(i);
        sub_PI(end+1)    = (1 - PI(i)) * 100; % Sub preference %
        sub_speed(end+1) = sub_avg_sp(i);
    end
end

% Plot Dom points
hDom = scatter(dom_PI, dom_speed, 80, [0.1 0.3 0.6], 'filled', ...
    'MarkerFaceAlpha', 0.7, 'MarkerEdgeColor', 'k');

% Plot Sub points
hSub = scatter(sub_PI, sub_speed, 80, [0.6 0.1 0.2], 'filled', ...
    'MarkerFaceAlpha', 0.7, 'MarkerEdgeColor', 'k');

% Linear regression on *all* points
all_PI_pct = [dom_PI, sub_PI];
all_speed  = [dom_speed, sub_speed];
mdl = fitlm(all_PI_pct.', all_speed.');  % fitlm expects column vectors
xFit = linspace(min(all_PI_pct), max(all_PI_pct), 100);
yFit = mdl.Coefficients.Estimate(1) + mdl.Coefficients.Estimate(2)*xFit;
hFit = plot(xFit, yFit, 'k--', 'LineWidth', 1.5);

xlabel('Preference for Animal (%)');
ylabel('Avg Speed (px/s)');
title(sprintf('Preference Index vs Speed (R=%.2f, p=%.3f)', mdl.Rsquared.Ordinary, mdl.Coefficients.pValue(2)));
grid on; box on;

legend([hDom, hSub, hFit], {'Dom', 'Sub', 'Fit'}, 'Location', 'best');

sgtitle('Social Preference and Locomotion');

%% ==== SAVE ALL FIGURES ====
% Create figures directory inside the selected data folder
figures_dir = fullfile(dataFolder, 'figures');
if ~exist(figures_dir, 'dir')
    mkdir(figures_dir);
end

% Get all open figure handles
fig_handles = findobj('Type', 'figure');

% Save each figure
for fIdx = 1:length(fig_handles)
    fig = fig_handles(fIdx);
    
    % Use figure Name, or fallback
    fig_name = fig.Name;
    if isempty(fig_name) || strcmp(fig_name, sprintf('Figure %d', fIdx))
        fig_name = sprintf('figure_%d', fIdx);
    end
    
    % Sanitize filename: remove \ / : * ? " < > | and spaces → underscores
    fig_name = regexprep(fig_name, '[\\/:*?"<>|\s]', '_');
    
    % Full output path
    png_path = fullfile(figures_dir, [fig_name, '.png']);
    
    % Save (R2019a: use print instead of exportgraphics if needed)
    try
        % R2020a+: exportgraphics is preferred
        exportgraphics(fig, png_path, 'Resolution', 600);
    catch
        % Fallback for R2019a and earlier
        print(fig, png_path, '-dpng', '-r600');
    end
    
    fprintf('Saved: %s\n', png_path);
end

fprintf('\nAll figures saved to:\n%s\n', figures_dir);

%% Helper function to convert p-value to significance label
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
    % Get current axes
    ax = gca;
    
    % Ensure y_base is within view — but leave room for bracket + text
    ylims = ax.YLim;
    y_range = diff(ylims);
    y_margin = 0.05 * y_range;      % 5% of y-axis height
    y_line  = min(y_base, ylims(2) - y_margin);  % don’t exceed top - margin
    y_text  = y_line + 0.6 * y_margin;            % text just above line
    
    % Draw horizontal line
    plot([x1 x2], [y_line y_line], 'k-', 'LineWidth', 1.0);
    
    % Draw caps
    plot([x1 x1], [y_line y_line + 0.2*y_margin], 'k-', 'LineWidth', 1.0);
    plot([x2 x2], [y_line y_line + 0.2*y_margin], 'k-', 'LineWidth', 1.0);
    
    % Get label
    label = pval2sig(pval);
    
    % Place text — use cellstr for multiline
    if iscell(label)
        y_text = y_line + 0.8*y_margin;  % a bit higher for 2 lines
    end
    
    text( (x1+x2)/2, y_text, label, ...
        'HorizontalAlignment', 'center', ...
        'FontWeight', 'bold', ...
        varargin{:} );
    
    if y_text > ylims(2)
        ax.YLim(2) = y_text + 0.1*y_margin;
    end
end