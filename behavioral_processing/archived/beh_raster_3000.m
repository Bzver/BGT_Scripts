clear;close all;clc;
path = cd;
load Beh.mat;
nstream = length(annotation.stream_ID);
a = annotation.annotation;
%Adjust this if not filmed in 60 fps
fps = 60;
frame = reshape(1:size(a,1), [], 1);
time = frame/fps,2;
for i = 1:nstream
    tbl = [a(:,i), time];
    dif = diff(tbl(:,1), 1);
    ied = find(all(dif == 0, 2));
    tbl(ied, :) = [];
    disp(tbl);
    bh = reshape(tbl(:,1), [], 1);
    sp = reshape(tbl(:,2), [], 1);
    sp = [0 ; sp];
    wd = size(tbl,1);
    dura = round(sp(wd+1),-1);
    figure(1);
    for k = 1:wd
    w = sp(k);
    q = bh(k);
    p = sp(k+1) - sp(k);
    if q==1
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[1 0 0],LineStyle="none");
    end
    if q==2
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[1 1 0],LineStyle="none");
    end
    if q==3
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[1 0.667 1],LineStyle="none");
    end
    if q==4
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[1 0 1],LineStyle="none");
    end
    if q==5
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[0.667 0 1],LineStyle="none");
    end
    if q==6
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[0.608 0.608 0.675],LineStyle="none");
    end
    if q==7
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[0 1 0],LineStyle="none");
    end
    if q==8
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[0.635 0 0.443],LineStyle="none");
    end
    if q==9
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[1 0.608 0.616],LineStyle="none");
    end
    if q==10
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[1 0.667 0],LineStyle="none");
    end
    if q==11
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[0.808 0.635 0.29],LineStyle="none");
    end
    if q==12
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[0 1 0.498],LineStyle="none");
    end
    if q==13
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[0 1 1],LineStyle="none");
    end
    if q==14
         rectangle('Position',[w,nstream-i,p,1],'FaceColor',[0 0 1],LineStyle="none");
    end
    end
    xticks([0 dura/2 dura]);
    xlim([0 dura]);
    yticks([0.5 1.5 2.5]);
    yticklabels({'female','subordinate','dominant'});
    ytickangle(90)
end
