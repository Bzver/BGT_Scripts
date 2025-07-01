clearvars; cd;
folder = pwd;
filelist = dir(fullfile(folder, '*.mat'));
allfileNames = {filelist.name};

for k = 1:length(allfileNames)

    currentfile = allfileNames(k);
    fprintf('Now processing %s\n', string(currentfile));
    load(string(currentfile));
    if exist('Fs','var') == 0
    warning('No frequency of sample located, double-check your file and manually assign one right now.')
    prompt = 'Enter Fs value: ';
    Fs = input(prompt);
    end
    runtime = i/Fs;
    x = double(data)/100;
    x_demeaned = x - mean(x);

    Fc = Fs/5;
    [b, a] = butter(4, Fc/(Fs/2), 'high');
    force = filtfilt(b, a, x_demeaned);
    %force = x_demeaned;

    segmentDuration = 3; 
    segmentLength = floor(segmentDuration * Fs); 

    numSegments = floor(runtime / segmentDuration);
    
    for i = 1:numSegments
        segment = force((i-1)*segmentLength + 1:i*segmentLength);
    end

    NFFT = segmentLength; 
    overlap = 0; 

    avgPowerSpectrum = zeros(1, ceil(NFFT/2 + 1));

    for i = 1:numSegments
        segment = force((i-1)*segmentLength + 1:i*segmentLength);
        fftSegment = fft(segment, NFFT);
        powerSpectrum = (1/(NFFT * Fs)) * abs(fftSegment).^2;
        avgPowerSpectrum = avgPowerSpectrum + powerSpectrum(1:ceil(NFFT/2 + 1));
    end

    avgPowerSpectrum = avgPowerSpectrum / numSegments;
    avgavg = avgPowerSpectrum / mean(avgPowerSpectrum);
    frequencies = (0:ceil(NFFT/2)) * Fs / NFFT;

    plot(frequencies, avgavg, 'DisplayName', string(currentfile));
    hold on;
    xlabel('Frequency (Hz)');
    ylabel('Power (Au)');
    xlim([Fc/2 Fs/2]);
    %title(string(currentfile));
    grid on;
    legend('Location', 'eastoutside');
    legend show;
end

hold off;

disp('Done!')