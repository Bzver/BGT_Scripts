clearvars; cd;
close all;

folder = pwd;
filelist = dir(fullfile(folder, '*.csv'));
afn = {filelist.name};

f1 = figure('Name','Head Angle');
hold on;
legend;
f2 = figure('Name','Trajectory');
hold on;

procana = table();

for k = 1:length(afn)

    currentfile = afn(k);
    data = readtable(string(currentfile));
    if height(data) > 36000
        data = data(1:36000, :);
    end

    data(:,2:end) = fillmissing(data(:,2:end), 'spline');

    procdata = table();
    procdata.frame = data.frame_idx + 1;

    x1 = data.spine1_x;
    y1 = data.spine1_y;
    x2 = data.spine2_x;
    y2 = data.spine2_y;
    x3 = data.spine4_x;
    y3 = data.spine4_y;
    %x4 = data.lEar_x;
    %y4 = data.lEar_y;
    %x5 = data.rEar_x;
    %y5 = data.rEar_y;
    x6 = data.front_x;
    y6 = data.front_y;

    procdata.micetwist = calAngle(x6,y6,x1,y1,x2,y2);
    procdata.micetwist(isnan(procdata.micetwist)) = 0;
    procdata.micetwist2 = calAngle2(x6,y6,x1,y1,x2,y2);
    procdata.micetwist2(isnan(procdata.micetwist2)) = 0;
    procdata.miceangle = rad2deg(atan2((y3-y6),(x3-x6)));

    procdata.micespeed = calSpeed(x2,y2,240);
    procdata.micespeedNS = procdata.micespeed;
    procdata.micespeedNS(procdata.micespeedNS < 200) = NaN;

    procana.filename(k) = string(currentfile);
    procana.micetwistmean(k) = mean(procdata.micetwist,'omitnan');
    procana.micetwistmedian(k) = median(procdata.micetwist,'omitnan');
    procana.micespeedmean(k) = mean(procdata.micespeed);
    procana.micespeedmedian(k) = median(procdata.micespeed);
    procana.micespeedNSmean(k) = mean(procdata.micespeedNS,'omitnan');
    procana.micespeedNSmedian(k) = median(procdata.micespeedNS,'omitnan');
    procana.miceactive(k) = length(rmmissing(procdata.micespeedNS)) / length(procdata.micespeed);
    
    diffs = diff(procdata.miceangle);
    procana.micedrct(k) = sum(diffs > 0) / (sum(diffs < 0) + sum(diffs > 0));
    
    figure(f1);
    fg1 = histogram(procdata.micetwist);
    if contains(string(currentfile),'exp') == 1
        fg2.Color = [0.5 0 0.5];
    end
    if contains(string(currentfile),'HOM') == 1
        fg1.FaceColor = [0.4940 0.1840 0.5560];
    elseif contains(string(currentfile),'het') == 1
        fg1.FaceColor = [0.8500, 0.3250, 0.0980];
    else
        fg1.FaceColor = [0 0.4470 0.7410];
    end
    figure(f2);
    subplot(ceil(length(afn)/3),3,k);
    fg2 = plot(data.spine2_x, data.spine2_y);
    %if contains(string(currentfile),'exp') == 1
    %    fg2.Color = [0.5 0 0.5];
    %end
    if contains(string(currentfile),'HOM') == 1
        fg2.Color = [0.4940 0.1840 0.5560];
    elseif contains(string(currentfile),'het') == 1
        fg2.Color = [0.8500, 0.3250, 0.0980];
    else
        fg2.Color = [0 0.4470 0.7410];
    end
end

hold off;
%exp_indices = find(contains(procana.filename, 'exp'));
%m = length(exp_indices);
HOM_indices = find(contains(procana.filename, 'HOM'));
m = length(HOM_indices);
het_indices = find(contains(procana.filename, 'het'));
n = length(het_indices);


figure('Name','Analysis');
subplot(2, 3, 1);
tf1 = bar(procana.micetwistmean,'FaceColor','flat');
%for i=1:m
%    tf1.CData(exp_indices(i),:)=[0.5 0 0.5];
%end
for i=1:m
    tf1.CData(HOM_indices(i),:)=[0.4940 0.1840 0.5560];
end
for i=1:n
    tf1.CData(het_indices(i),:)=[0.8500, 0.3250, 0.0980];
end
title("Mean of Head Angle");
subplot(2, 3, 2);
tf2 = bar(procana.micespeedNSmean,'FaceColor','flat');
%for i=1:m
%    tf2.CData(exp_indices(i),:)=[0.5 0 0.5];
%end
for i=1:m
    tf2.CData(HOM_indices(i),:)=[0.4940 0.1840 0.5560];
end
for i=1:n
    tf2.CData(het_indices(i),:)=[0.8500, 0.3250, 0.0980];
end
title("Mean of Moving Speed");
subplot(2, 3, 3);
tf3 = bar(procana.micespeedmean,'FaceColor','flat');
%for i=1:m
%    tf3.CData(exp_indices(i),:)=[0.5 0 0.5];
%end
for i=1:m
    tf3.CData(HOM_indices(i),:)=[0.4940 0.1840 0.5560];
end
for i=1:n
    tf3.CData(het_indices(i),:)=[0.8500, 0.3250, 0.0980];
end
title("Mean of Speed");
subplot(2, 3, 4);
tf4 = bar(procana.miceactive,'FaceColor','flat');
%for i=1:m
%    tf4.CData(exp_indices(i),:)=[0.5 0 0.5];
%end
for i=1:m
    tf4.CData(HOM_indices(i),:)=[0.4940 0.1840 0.5560];
end
for i=1:n
    tf4.CData(het_indices(i),:)=[0.8500, 0.3250, 0.0980];
end
title("Time Moving Percentage");
subplot(2, 3, 5);
tf5 = bar(procana.micespeedmean,'FaceColor','flat');
%for i=1:m
%    tf5.CData(exp_indices(i),:)=[0.5 0 0.5];
%end
for i=1:m
    tf5.CData(HOM_indices(i),:)=[0.4940 0.1840 0.5560];
end
for i=1:n
    tf5.CData(het_indices(i),:)=[0.8500, 0.3250, 0.0980];
end
title("Median of Speed");
subplot(2, 3, 6);
tf6 = bar(procana.micedrct,'FaceColor','flat');
%for i=1:m
%    tf6.CData(exp_indices(i),:)=[0.5 0 0.5];
%end
for i=1:m
    tf6.CData(HOM_indices(i),:)=[0.4940 0.1840 0.5560];
end
for i=1:n
    tf6.CData(het_indices(i),:)=[0.8500, 0.3250, 0.0980];
end
title("Right / Left Index");



%exp = procana(exp_indices,:);
%ctrl = procana;
%ctrl(exp_indices,:) = [];
%h1 = mean(exp.micetwistmean)/mean(ctrl.micetwistmean);
%h2 = mean(exp.micespeedNSmean)/mean(ctrl.micespeedNSmean);
%h3 = mean(exp.miceactive)/mean(ctrl.miceactive);
%h = bar([h1 1;h2 1;h3 1]);
%h(1).FaceColor= [0.9290 0.6940 0.1250];
%h(2).FaceColor= [0 0.4470 0.7410];
%xticklabels(["Average Head Angle" "Average Moving Speed" "Time Moving Percentage"]);

%%
function speed = calSpeed(x, y, frameRate)
% Check if input vectors have the same length
if length(x) ~= length(y)
    error('x and y vectors must have the same length.');
end

% Calculate the distance between consecutive points
dx = diff(x);
dy = diff(y);
distances = sqrt(dx.^2 + dy.^2);

% Calculate the time difference between frames
timeDiff = 1 / frameRate;

% Calculate the speed
speed = distances / timeDiff;

% If you want to include the speed at the first frame, you can pad with NaN.
speed = [0; speed]; % or speed = [0; speed] if you want to assume speed 0 at the first frame.
end

function angles = calAngle(x1, y1, x2, y2, x3, y3)
if ~isequal(length(x1), length(y1), length(x2), length(y2), length(x3), length(y3))
    error('All input columns must have the same length.');
end
numPoints = length(x1); % Number of sets of three points
% Preallocate the angles vector
angles = zeros(numPoints, 1);
% Calculate the angle for each set of three points
for i = 1:numPoints
    p1 = [x1(i), y1(i)];
    p2 = [x2(i), y2(i)];
    p3 = [x3(i), y3(i)];
    v1 = p1 - p2;
    v2 = p3 - p2;
    dotProduct = dot(v1, v2);
    magnitudeV1 = norm(v1);
    magnitudeV2 = norm(v2);
    cosAngle = dotProduct / (magnitudeV1 * magnitudeV2);
    angleRad = acos(cosAngle);
    angleDeg = rad2deg(angleRad);

    % Determine the orientation using the cross product
    crossProduct = cross([v1, 0], [v2, 0]); % Add a zero z-component for 2D cross product
    if crossProduct(3) < 0 % Check the z-component of the cross product
        angles(i) = 360 - angleDeg; % Reflex angle
    else
        angles(i) = angleDeg; % Acute or obtuse angle
    end
end
end

function angles = calAngle2(x1, y1, x2, y2, x3, y3)
if ~isequal(length(x1), length(y1), length(x2), length(y2), length(x3), length(y3))
    error('All input columns must have the same length.');
end

numPoints = length(x1); % Number of sets of three points

% Preallocate the angles vector
angles = zeros(numPoints, 1);

% Calculate the angle for each set of three points
for i = 1:numPoints
    p1 = [x1(i), y1(i)];
    p2 = [x2(i), y2(i)];
    p3 = [x3(i), y3(i)];

    v1 = p1 - p2;
    v2 = p3 - p2;

    dotProduct = dot(v1, v2);
    magnitudeV1 = norm(v1);
    magnitudeV2 = norm(v2);

    cosAngle = dotProduct / (magnitudeV1 * magnitudeV2);
    %angles(i) = rad2deg(abs(acos(cosAngle)));
    angles(i) = rad2deg(acos(cosAngle));
end
end