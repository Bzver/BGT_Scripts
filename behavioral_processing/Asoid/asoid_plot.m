clearvars; cd;
close all;

folder = pwd;
filelist = dir(fullfile(folder, '*.csv'));
afn = {filelist.name};
subfolderName = 'exported_figs'; % Name of your subfolder
if ~exist(subfolderName, 'dir')
    mkdir(subfolderName);
end

dataAna = table();

for k = 1:length(afn)

    currentfile = char(afn(k));
    data = readtable(string(currentfile));
    currentfile = extractgroomConv(currentfile);
    fig1name = strcat(string(currentfile),'_raster');
    fig2name = strcat(string(currentfile),'_pie');
    time = data.time + 0.1;
    fig1 = figure('Name',fig1name,'Position', [50, 800-(20*(k-1)), 1500, 100]);
    hold on;
    bar(time,data.grooming,'Facecolor',[0.4660 0.6740 0.1880]);
    bar(time,data.bodylicking,'Facecolor',[0.9290 0.6940 0.1250]);
    legend('Grooming','Body licking', 'Location', 'westoutside');
    yticks([]);
    xlabel('Time(sec)');
    hold off;
    %saveas(fig1, strcat(folder,'\exported_figs\',fig1name,'.emf'))
    fig2 = figure('Name',fig2name,'Position', [1300, 500-(20*(k-1)), 500, 500]);
    pieLabels = {'Grooming', 'Body licking', 'Other'};
    groomingTime = sum(data.grooming == 1);
    bodylickingTime = sum(data.bodylicking == 1);
    totalTime = length(time);
    pieDatum = [groomingTime, bodylickingTime, totalTime - groomingTime - bodylickingTime];
    colors = [
    0.4660 0.6740 0.1880;
    0.9290 0.6940 0.1250;
    1 1 1 
    ];
    pie(pieDatum, pieLabels);
    colormap(colors);
    %saveas(fig2, strcat(folder,'\exported_figs\',fig2name,'.emf'))
    
    dataAna.filename(k) = string(currentfile);
    dataAna.groomingPerc(k) = groomingTime/totalTime;
    dataAna.bodylickingPerc(k) = bodylickingTime/totalTime;
    dataAna.gNbPerc(k) = (groomingTime+bodylickingTime)/totalTime;

end

ckoIndices = find(contains(dataAna.filename, 'cko'));
conIndices = setdiff(reshape(1:k,[k,1]),ckoIndices);

ckoGMean = mean(dataAna.groomingPerc(ckoIndices));
ckoGError = std(dataAna.groomingPerc(ckoIndices));
conGMena = mean(dataAna.groomingPerc(conIndices));
conGError = std(dataAna.groomingPerc(conIndices));
[h1, p1] = ttest2(dataAna.groomingPerc(ckoIndices), dataAna.groomingPerc(conIndices));

ckoBMean = mean(dataAna.bodylickingPerc(ckoIndices));
ckoBError = std(dataAna.bodylickingPerc(ckoIndices));
conBMena = mean(dataAna.bodylickingPerc(conIndices));
conBError = std(dataAna.bodylickingPerc(conIndices));
[h2, p2] = ttest2(dataAna.bodylickingPerc(ckoIndices), dataAna.bodylickingPerc(conIndices));

ckoGnBMean = mean(dataAna.gNbPerc(ckoIndices));
ckoGnBError = std(dataAna.gNbPerc(ckoIndices));
conGnBMean = mean(dataAna.gNbPerc(conIndices));
conGnBError = std(dataAna.gNbPerc(conIndices));
[h3, p3] = ttest2(dataAna.gNbPerc(ckoIndices), dataAna.gNbPerc(conIndices));

figure('Name','Analysis');
data_error=[ckoGError conGError;ckoBError conBError;ckoGnBError conGnBError];
data_mean=[ckoGMean conGMena; ckoBMean conBMena; ckoGnBMean conGnBMean];
neg = data_error; 
pos = data_error; 
y=data_mean;
m = size(y,1);
n = size(y,2);
x = 1 : m;
fig3 = bar(x,y);
colors = [
 0.8500 0.3250 0.0980;
 0 0.4470 0.7410
];
for i = 1:length(fig3)
    fig3(i).FaceColor = colors(i, :);
end

hold on;
xCnt =  fig3(1).XData.' + [fig3.XOffset]; 
errorbar(xCnt(:),y(:),data_error(:),'*k');

xx = zeros(m, n);
for i = 1 : n
    xx(:, i) = fig3(1, i).XEndPoints';
end

t1 = 1; 
n1 = 1; 
n2 = 2; 
x1 = xx(t1,n1); x2 = xx(t1,n2);
ySig = max(y(t1,n1)+pos(t1,n1),y(t1,n2)+pos(t1,n2));
sigline([x1,x2],ySig,p1)

t1 = 2; 
n1 = 1; 
n2 = 2; 
x1 = xx(t1,n1); x2 = xx(t1,n2);
ySig = max(y(t1,n1)+pos(t1,n1),y(t1,n2)+pos(t1,n2));
sigline([x1,x2],ySig,p2)

t1 = 3; 
n1 = 1; 
n2 = 2; 
x1 = xx(t1,n1); x2 = xx(t1,n2);
ySig = max(y(t1,n1)+pos(t1,n1),y(t1,n2)+pos(t1,n2));
sigline([x1,x2],ySig,p3)

hold off;
legend('cko','con','Location','northwest');
saveas(gcf, strcat(folder,'\exported_figs\data_analysis','.png'))

%%
function extractedString = extractgroomConv(inputString)
  % Extracts the part of a string that begins with 'groom' and ends with '-conv'.
  % Returns an empty string if no such part is found.

  extractedString = ''; % Initialize to empty string

  startIndex = strfind(inputString, 'groom');
  endIndex = strfind(inputString, '-conv');

  if ~isempty(startIndex) && ~isempty(endIndex)
    % Found both 'groom' and '-conv'
    if startIndex(1) < endIndex(end)
      % 'groom' comes before '-conv'
      extractedString = inputString(startIndex(1):endIndex(end) + length('-conv') - 1);
    end
  end
end

function sigline(x, y, p)
hold on
x = x';
p_value = string(p);

if p<0.001
    plot(mean(x),       y*1.15, '*k')          % the sig star sign
    plot(mean(x)- 0.02, y*1.15, '*k')          % the sig star sign
    plot(mean(x)+ 0.02, y*1.15, '*k')          % the sig star sign

elseif (0.001<=p)&&(p<0.01)
    plot(mean(x)- 0.01, y*1.15, '*k')         % the sig star sign
    plot(mean(x)+ 0.01, y*1.15, '*k')         % the sig star sign

elseif (0.01<=p)&&(p<0.05)
    plot(mean(x), y*1.15, '*k')               % the sig star sign
else
    text(mean(x)-0.1, y*1.1+0.01, strcat('p=',p_value)) 
end

plot(x, [1;1]*y*1.1, '-k', 'LineWidth',1); 
plot([1;1]*x(1), [y*1.05, y*1.1], '-k', 'LineWidth', 1); 
plot([1;1]*x(2), [y*1.05, y*1.1], '-k', 'LineWidth', 1); 

hold off
end