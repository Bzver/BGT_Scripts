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
inCage_dom = zeros(numSessions, 1);
inCage_sub = zeros(numSessions, 1);
inter_dom  = zeros(numSessions, 1);
inter_sub  = zeros(numSessions, 1);

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
    
    % Apply frame range selection
    if processFrameRange
        totalFrames = frameEnd - frameStart + 1;
        if frameEnd > length(annot_named)
            frameEnd = length(annot_named);
            totalFrames = frameEnd - frameStart + 1;
        end
        annot_named = annot_named(frameStart:frameEnd);
    else
        totalFrames = length(annot_named);
    end
    
    dom_icg = sum(contains(annot_named, "dom_"));
    sub_icg = sum(contains(annot_named, "sub_"));
    dom_int = sum(contains(annot_named, "dom_interaction"));
    sub_int = sum(contains(annot_named, "sub_interaction"));
    
    inCage_dom(i) = 100 * dom_icg / totalFrames;
    inCage_sub(i) = 100 * sub_icg / totalFrames;
    inter_dom(i)  = 100 * dom_int / totalFrames;
    inter_sub(i)  = 100 * sub_int / totalFrames;

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

if processFrameRange
    sgtitle(sprintf('Group-Level Behavior Summary (n = %d sessions, Frames %d-%d)', ...
        numSessions, frameStart, frameEnd), 'FontSize', 12);
else
    sgtitle(sprintf('Group-Level Behavior Summary (n = %d sessions)', numSessions), 'FontSize', 12);
end

%% ==== PLOT: PREFERENCE INDEX ====
figure('Position', [100, 550, 800, 600]);

% --- PI Bar Plot ---
subplot(1,1,1); hold on;

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

if processFrameRange
    sgtitle(sprintf('Social Preference (Frames %d-%d)', frameStart, frameEnd), 'FontSize', 12);
else
    sgtitle('Social Preference', 'FontSize', 12);
end

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
    
    % Add frame range info to filename if applicable
    if processFrameRange
        fig_name = [fig_name, '_frames_', num2str(frameStart), '_', num2str(frameEnd)];
    end
    
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
    y_line  = min(y_base, ylims(2) - y_margin);  % don't exceed top - margin
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