clf; clearvars;
delete(instrfindall);

s6=serial('COM6','BaudRate',57600); 
s6.BytesAvailableFcnMode = 'byte';
s6.InputBufferSize = 9;        
s6.BytesAvailableFcnCount= 8;   
runtime = 300;    

try
  fopen(s6);                       
catch err
  fclose(instrfind);               
  error('Specified serial port unopened or occupied.');   
end

num = ['01';'03';'00';'52';'00';'02';'65';'DA'];    
send = hex2dec(num);                                

data = zeros(1,runtime*50);

hold on;
grid on;
InputBufferSize = 200;
margin = 50;
t = 1:InputBufferSize;
InputBuffer = zeros(1,InputBufferSize);

tic
for i = 1:InputBufferSize
    fwrite(s6, send);
    recv = fread(s6);     
    res = typecast(uint8(flip(recv(4:7))),'uint32'); 
    if res > 1e8
        res = 0;
    end
    InputBuffer(i) = res;
    plot((1:i),InputBuffer(1,1:i),'-b');
    axis([t(1) t(InputBufferSize) min(InputBuffer(1:i))-margin max(InputBuffer)+margin]);
    data(i) = res;
    pause(0.001);
end

while toc < runtime
    i = i + 1;
    grid on;
    t = t + 1;
    for j = 2:InputBufferSize
        InputBuffer(j-1) = InputBuffer(j);
    end
    fwrite(s6, send);
    recv = fread(s6);     
    res = typecast(uint8(flip(recv(4:7))),'uint32'); 
    if res > 1e8
        res = 0;
    end
    InputBuffer(InputBufferSize) = res;
    plot(t,InputBuffer(1,:),'-b');
    axis([t(1) t(InputBufferSize) min(InputBuffer)-margin max(InputBuffer)+margin]);
    data(i) = res;
    drawnow limitrate;
    pause(0.001);
    hold on;
    if mod(min(t)-1, InputBufferSize) == 0
        hold off
    end
end
Fs = i/runtime;

data = data(1:i);
hold off;
plot(data,'-b');
axis([1 i min(data)-margin max(data)+margin]);
grid on;

prompt = 'Experiment finished. Name this experiment: ';
nameExp = input(prompt,'s');
save([nameExp,'.mat']);
saveas(gcf,[nameExp,'.png']);
fclose(s6);
