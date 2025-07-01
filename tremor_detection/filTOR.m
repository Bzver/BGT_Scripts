clearvars;
[file,path] = uigetfile;
filepath = [path,'/',file];
load(filepath);

TF = 5;
while true
    close all;
    figure('Visible','on');
    plot(data);
    xlim([0 length(data)]);
    dataNew = data;
%Adjust the threshold factor accordingly
    indicesOut = find(isoutlier(data,'ThresholdFactor',TF));
    dataNew(indicesOut) = 0;
    figure('Visible','on');
    plot(dataNew);
    xlim([0 length(data)]);
    drawnow;
    contin = input('Press x if result is OK, or input the desired filter threshold: ','s');
    if strcmp(contin,'x') || strcmp(contin,'X')
        break;
    elseif isnan(str2double(contin)) == 1
        warning('Invalid input')
    else
        TF = str2double(contin);
    end
end

close all;
data(indicesOut) = [];
plot(data,'-m');
axis([1 length(data) min(data)-margin max(data)+margin]);
grid on;

save(['filtered','_',file,'.mat']);
saveas(gcf,['filtered','_',file,'.png']);