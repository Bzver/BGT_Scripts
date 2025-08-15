clear all
close all

%%

annot_mat = "2025-07-16-first3h.mat";

isCutOff = 0;
fps = 10;
cutOffTime = "03:00:00"; %hh:mm:ss

%%
load(annot_mat)

behaviors = annotation.behaviors;
annot = annotation.annotation;

if isCutOff == 1
    cutOffTime_split = str2double(split(cutOffTime,":"));
    cutOffTime_second = cutOffTime_split(1)*3600 + cutOffTime_split(2)*60 + cutOffTime_split(3);
    cutOff_frame = cutOffTime_second * fps;
    annot = annot(1:cutOff_frame);
end

% Convert numeric annotations to behavior names
behavior_names = fieldnames(behaviors);
[~, idx] = ismember(annot, struct2array(behaviors));
annot_named = behavior_names(idx);

%% Durations Plot
transitions = find(diff(annot) ~= 0)+1;
durations = diff([1; transitions; length(annot)]);
transitions = [1;transitions];
behavior_labels = annot_named(transitions);

colors_inverse_mask = ones(6,3);
colors = [0.8715    0.9028    0.9028;
          0.7431    0.8056    0.8056;
          0.6146    0.7083    0.7083;
          0.4861    0.6111    0.6111;
          0.3889    0.4722    0.5139;
          0.2917    0.3333    0.4167];
colors_inverse = colors_inverse_mask-colors;

%figure('Name','Behavior Duration Distribution');
%grpstats(durations, behavior_labels, {'mean'});
%boxplot(durations, behavior_labels, 'Orientation', 'horizontal', 'Colors', colors_inverse);
%ylabel('Duration (frames)');

%% Transition matrix
unique_behaviors = numel(behavior_names);
trans_counts = zeros(unique_behaviors);

for i = 1:length(annot)-1
    current = annot(i)+1;
    next = annot(i+1)+1;
    if current ~= next
        trans_counts(current, next) = trans_counts(current, next)+1;
    end
end

% Convert to probabilities
trans_prob = trans_counts ./ sum(trans_counts, 2);

% Plot
figure('Name','Behavior Transition Probabilities');
imagesc(trans_prob);
colormap(flipud(bone));
colorbar;

% Label axes
xticks(1:unique_behaviors);
yticks(1:unique_behaviors);
xticklabels(behavior_names(1:unique_behaviors));
yticklabels(behavior_names(1:unique_behaviors));
xlabel('Next Behavior');
ylabel('Current Behavior');

%% Categorial pie charts

duration_total_dom = sum(count(annot_named,"dom"));
duration_total_sub = sum(count(annot_named,"sub"));

other_idx = annotation.behaviors.other;
dom_idle_idx = annotation.behaviors.dom_idle;
sub_idle_idx = annotation.behaviors.sub_idle;
bout_total_dom = trans_counts(other_idx + 1, dom_idle_idx + 1);
bout_total_sub = trans_counts(other_idx + 1, sub_idle_idx + 1);

duration_initiative_dom = sum(count(annot_named,"dom_initiative"));
duration_passive_dom = sum(count(annot_named,"dom_passive"));
duration_flee_dom = sum(count(annot_named,"dom_flee"));

duration_initiative_sub = sum(count(annot_named,"sub_initiative"));
duration_passive_sub = sum(count(annot_named,"sub_passive"));
duration_flee_sub = sum(count(annot_named,"sub_flee"));

figure('Name','Behavior Distribution Pie');
colormap(colors)
set(gcf, 'color', 'white');
label_l_v_r= ["Dom", "Sub"];
label_comp = ["Initiative", "Passive", "Flee"];
label_comp_b = ["Initiative", "Passive", " "];

subplot(2, 2, 1);
duration_total_l_v_r = [duration_total_dom, duration_total_sub];
pie(duration_total_l_v_r, label_l_v_r)
title("Total Time");

subplot(2, 2, 2);
bout_total_l_v_r = [bout_total_dom, bout_total_sub];
pie(bout_total_l_v_r, label_l_v_r)
title("Total Entries");

subplot(2, 2, 3);
duration_comp_dom = [duration_initiative_dom, duration_passive_dom, duration_flee_dom];
pie(duration_comp_dom, label_comp_b)
title("Dom Interacting Time");

subplot(2, 2, 4);
duration_comp_sub = [duration_initiative_sub, duration_passive_sub, duration_flee_sub];
pie(duration_comp_sub, label_comp)
title("Sub Interacting Time");

%% Categorial Bar Plots
figure('Name','Behavior Distribution Bar');

subplot(1, 2, 1);
duration_init_l_vs_r = [duration_initiative_dom/fps duration_initiative_sub/fps];
dura_init_x = categorical(label_l_v_r);
B1 = bar(dura_init_x, duration_init_l_vs_r, 'FaceColor', 'flat');
B1.CData(1,:) = colors(1,:);
B1.CData(2,:) = colors(6,:);
title("Female-led Interaction Time(s)");

subplot(1, 2, 2);
perc_active_dom = ( duration_passive_dom + duration_flee_dom ) / duration_total_dom;
perc_active_sub = ( duration_passive_sub + duration_flee_sub ) / duration_total_sub;
perc_active_l_vs_r = [perc_active_dom perc_active_sub];
perc_act_x = categorical(label_l_v_r);
B2 = bar(perc_act_x, perc_active_l_vs_r, 'FaceColor', 'flat');
B2.CData(1,:) = colors(1,:);
B2.CData(2,:) = colors(6,:);
title("Male Active Index");