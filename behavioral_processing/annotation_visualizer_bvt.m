clear all;
close all;

%%
[filename, pathname] = uigetfile('*.mat', 'Select MAT file');
if isequal(filename, 0)
    error('No file selected. Execution aborted.');
end
annot_mat = fullfile(pathname, filename);

fps = 10;
pin_duration_seconds = 600;

%%

load(annot_mat)

behaviors = annotation.behaviors;
annot = int32(annotation.annotation);  % Numeric behavior IDs

% Convert to behavior names
behavior_names = string(fieldnames(behaviors));
[~, idx] = ismember(annot, struct2array(behaviors));
annot_named = behavior_names(idx);
num_frames_total = length(annot_named);

%% Color ref
colors = [0.8715    0.9028    0.9028;
          0.7431    0.8056    0.8056;
          0.6146    0.7083    0.7083;
          0.4861    0.6111    0.6111;
          0.3889    0.4722    0.5139;
          0.2917    0.3333    0.4167];

%% === 2. Behavior Duration & Subtype Analysis ===
% Helper: count behavior by name
count_beh = @(beh) sum(contains(annot_named, beh));

% --- Total Interaction Time by Role ---
duration_total_dom = sum(contains(annot_named, "dom_"));
duration_total_sub = sum(contains(annot_named, "sub_"));

other = count_beh("other");
dom_int = count_beh("dom_interaction");
dom_icg = count_beh("dom_in_cage");
sub_init = count_beh("sub_interaction");
sub_icg = count_beh("sub_in_cage");

%% === 3. Pie Charts===
figure('Name', 'Behavior Distribution with Contact Type');
colormap(colors);
set(gcf, 'Color', 'white');

% Labels
role_labels = ["Dom", "Sub"];

subplot(2,1,1);
pie([duration_total_dom, duration_total_sub], role_labels);
title("Total Time In Cage");

subplot(2,1,2);
pie([dom_int, sub_init], role_labels);
title("Total Interaction Time");


%% === 5. Line Plot: Behavior Trends Over Time (Active Behaviors Only) ===

pin_duration_frames = pin_duration_seconds * fps;
num_bins = floor(num_frames_total / pin_duration_frames);
time_minutes = (0.5:num_bins-0.5) * (pin_duration_frames / fps / 60);

behaviors_active = ["dom_interaction", "dom_in_cage", "sub_interaction", "sub_in_cage"];

% Preallocate
num_bins = floor(num_frames_total / pin_duration_frames);
trends_active = zeros(num_bins, length(behaviors_active));

for p = 1:num_bins
    start_idx = (p-1)*pin_duration_frames + 1;
    end_idx = p*pin_duration_frames;
    segment = annot_named(start_idx:end_idx);
    
    % Fill trends
    for b = 1:length(behaviors_active)
        beh = behaviors_active(b);
        trends_active(p, b) = sum(contains(segment, beh)) / pin_duration_frames;
    end
end

% Smooth
smoothed_active = movmean(trends_active, [1 1], 1);

figure('Name', 'Behavior Trends', 'Position', [100, 100, 1600, 500]);
hold on;

% Colors
color_map_active = [
    0.2    0.4    0.8;      % dom_int
    0.9290 0.6940 0.1250;   % dom_icg
    0.1    0.2    0.5;      % sub_int
    0.8500 0.3250 0.0980;   % sub_icg
];

hLines1 = gobjects(size(trends_active,2),1);
for b = 1:length(behaviors_active)
    hLines1(b) = plot(time_minutes, smoothed_active(:,b), 'LineWidth', 2, ...
        'Color', color_map_active(b,:), 'DisplayName', behaviors_active(b));
    % Dashed for sub
    if startsWith(behaviors_active(b), 'sub')
        hLines1(b).LineStyle = '--';
    end
end

hold off;
xlabel('Time (minutes)');
ylabel('Probability');
title('Active Behavior Dynamics Over Time');
grid on;
box on;
xlim([min(time_minutes), max(time_minutes)]);
xticks(0:pin_duration_seconds/20:length(annot)/600);
legend('Location', 'eastoutside', 'Interpreter', 'none');
set(gca, 'XColor', 'black', 'YColor', 'black');
set(gcf, 'Color', 'white');
