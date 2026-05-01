clear all
close all

%%

numAnimal = 2;
isAnnotated = 1;

predFile = "D:\Project\Sleap-Models\QUAD\labels.v001.000_13-b-20-1toe1.analysis.csv";
annotFile = "D:\Project\Sleap-Models\QUAD\13-b-20-1toe1_annot.mat";

%%
function point_val = interpolate_predctions()
% Interpolate the missing predictions

end

function speed = calSpeed(x, y, frameRate)
  if length(x) ~= length(y)
    error('x and y vectors must have the same length.');
  end
  dx = diff(x);
  dy = diff(y);
  distances = sqrt(dx.^2 + dy.^2);
  timeDiff = 1 / frameRate;
  speed = distances / timeDiff;
  speed = [0; speed]; % Pad the first frame speed with 0
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
    angles(i) = abs(acos(cosAngle));
  end
end

%%

data = readtable(predFile);

if isAnnotated == 1
    load(annotFile);
end




procdata = table();

procdata.category = annotation.annotation(1:15000,:);

procdata.nose_vis = data.nose_x;
procdata.nose_vis(~isnan(procdata.nose_vis)) = 1;
procdata.nose_vis(isnan(procdata.nose_vis)) = 0;

procdata.tail_vis = data.tail_x;
procdata.tail_vis(~isnan(procdata.tail_vis)) = 1;
procdata.tail_vis(isnan(procdata.tail_vis)) = 0;

data.Hpaw_x = ( data.HpawL_x + data.HpawR_x )/ 2;
data.Hpaw_y = ( data.HpawL_y + data.HpawR_y )/ 2;
data.Fpaw_x = ( data.FpawL_x + data.FpawR_x )/ 2;
data.Fpaw_y = ( data.FpawL_y + data.FpawR_y )/ 2;

x1 = data.nose_x;
backupx1 = [data.head_x, data.neck_x, data.bodyU_x, data.Fpaw_x, data.bodyL_x];
x1 = fillNaNFromBackups(x1,backupx1);
y1 = data.nose_y;
backupy1 = [data.head_y, data.neck_y, data.bodyU_y, data.Fpaw_y, data.bodyL_y];
y1 = fillNaNFromBackups(y1,backupy1);
x2 = data.tail_x;
backupx2 = [data.bodyL_x, data.Hpaw_x, data.HpawL_x, data.HpawR_x, data.bodyU_x, data.neck_x];
x2 = fillNaNFromBackups(x2,backupx2);
y2 = data.tail_y;
backupy2 = [data.bodyL_y, data.Hpaw_y, data.HpawL_y, data.HpawR_y, data.bodyU_y, data.neck_y];
y2 = fillNaNFromBackups(y2,backupy2);
x3 = data.Fpaw_x;
backupx3 = [data.FpawL_x, data.FpawR_x, data.bodyU_x, data.bodyL_x];
x3 = fillNaNFromBackups(x3,backupx3);
y3 = data.Fpaw_y;
backupy3 = [data.FpawL_y, data.FpawR_y, data.bodyU_y, data.bodyL_y];
y3 = fillNaNFromBackups(y3,backupy2);
x4 = data.bodyU_x;
backupx4 = [data.Fpaw_x, data.FpawL_x, data.FpawR_x, data.neck_x, data.bodyL_x];
x4 = fillNaNFromBackups(x4,backupx4);
y4 = data.bodyU_x;
backupy4 = [data.Fpaw_x, data.FpawL_x, data.FpawR_x, data.neck_x, data.bodyL_x];
y4 = fillNaNFromBackups(y4,backupy4);

procdata.miceangle = abs(atan2((y2-y1),(x2-x1)));
procdata.micetwist = calAngle(x1,y1,x4,y4,x2,y2);
procdata.micelength = sqrt((x2 - x1).^2 + (y2 - y1).^2);
procdata.nosepaw_dis = sqrt((x3 - x1).^2 + (y3 - y1).^2);
procdata.micespeed = calSpeed(x4,y4,25);
procdata.miceheadspeed = calSpeed(x1,y1,25);

procdata.micespeed(isoutlier(procdata.micespeed)) = 0;
procdata.miceheadspeed(isoutlier(procdata.micespeed)) = 0;

procdatamat = table2array(procdata);
procdatamat(:,4:9) = zscore(procdatamat(:,4:9));

save('data2.mat');
