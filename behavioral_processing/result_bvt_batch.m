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

% Preallocate
inCage_dom = zeros(numSessions, 1);
inCage_sub = zeros(numSessions, 1);
inter_dom  = zeros(numSessions, 1);
inter_sub  = zeros(numSessions, 1);

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
figure('Position', [100, 100, 950, 400]);

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

% Add significance annotation
allYVals = [meanInCage + semInCage, inCage_dom.', inCage_sub.'];
yMax = max(allYVals) + 5;
plot([1 2], [yMax yMax], 'k-', 'LineWidth', 1);
text(1.5, yMax + 1, labelInCage, 'HorizontalAlignment', 'center', 'FontSize', 12, 'FontWeight', 'bold');

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