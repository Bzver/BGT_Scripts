function GroupedBarGUI
    % Create main figure
    fig = figure('Name', 'Grouped Bar Plot with SEM', 'Position', [100 100 1000 700], ...
                'NumberTitle', 'off', 'MenuBar', 'none');
    
    % Data table with expandable rows
    uicontrol('Style', 'text', 'Position', [20 650 150 20], 'String', 'Enter Data (4 columns):');
    defaultData = num2cell([nan(10,4); rand(5,4)]); % 15 initial rows (5 with example data)
    dataTable = uitable(fig, 'Data', defaultData, 'Position', [20 350 300 300], ...
                       'ColumnEditable', true(1,4), 'ColumnName', {'Col1','Col2','Col3','Col4'}, ...
                       'RowName', [], 'CellEditCallback', @adjustTableSize);
    
    % Plot controls panel
    uipanel('Title', 'Plot Controls', 'Position', [0.35 0.7 0.3 0.25]);
    
    % Title and labels
    uicontrol('Style', 'text', 'Position', [400 650 100 20], 'String', 'Title:');
    titleBox = uicontrol('Style', 'edit', 'Position', [500 650 200 20], 'String', 'Grouped Bar Plot');
    
    uicontrol('Style', 'text', 'Position', [400 620 100 20], 'String', 'X Label:');
    xlabelBox = uicontrol('Style', 'edit', 'Position', [500 620 200 20], 'String', 'Groups');
    
    uicontrol('Style', 'text', 'Position', [400 590 100 20], 'String', 'Y Label:');
    ylabelBox = uicontrol('Style', 'edit', 'Position', [500 590 200 20], 'String', 'Values');
    
    % Column names
    uicontrol('Style', 'text', 'Position', [400 560 100 20], 'String', 'Legend Names:');
    colNameBoxes = gobjects(1,4);
    for i = 1:4
        uicontrol('Style', 'text', 'Position', [400 530-30*i 50 20], 'String', sprintf('Col %d:',i));
        colNameBoxes(i) = uicontrol('Style', 'edit', 'Position', [450 530-30*i 150 20], ...
                                   'String', sprintf('Column %d',i));
    end
    
    % Color selection
    uicontrol('Style', 'text', 'Position', [720 650 100 20], 'String', 'Bar Colors:');
    colorButtons = gobjects(1,4);
    defaultColors = [0.2 0.4 0.8; 0.8 0.4 0.2; 0.2 0.8 0.4; 0.8 0.2 0.8];
    for i = 1:4
        uicontrol('Style', 'text', 'Position', [720 620-30*i 50 20], 'String', sprintf('Col %d:',i));
        colorButtons(i) = uicontrol('Style', 'pushbutton', 'Position', [770 620-30*i 50 20], ...
                                  'BackgroundColor', defaultColors(i,:), ...
                                  'Callback', {@chooseColor, i});
    end
    
    % Symbol selection
    uicontrol('Style', 'text', 'Position', [850 650 120 20], 'String', 'Point Style:');
    symbolMenus = gobjects(1,4);
    symbols = {'o', '+', '*', 'x', 's', 'd', '^', 'v', '>', '<', 'p', 'h'};
    for i = 1:4
        uicontrol('Style', 'text', 'Position', [850 620-30*i 50 20], 'String', sprintf('Col %d:',i));
        symbolMenus(i) = uicontrol('Style', 'popupmenu', 'Position', [900 620-30*i 80 20], ...
                                 'String', symbols, 'Value', min(i,length(symbols)));
    end
    
    % Plot button
    uicontrol('Style', 'pushbutton', 'Position', [400 50 200 30], ...
             'String', 'Generate Plot', 'Callback', @generatePlot);
    
    % Store data for callbacks
    guiData = struct();
    guiData.dataTable = dataTable;
    guiData.titleBox = titleBox;
    guiData.xlabelBox = xlabelBox;
    guiData.ylabelBox = ylabelBox;
    guiData.colNameBoxes = colNameBoxes;
    guiData.colorButtons = colorButtons;
    guiData.symbolMenus = symbolMenus;
    guidata(fig, guiData);
    
    % Color selection callback
    function chooseColor(~, ~, colNum)
        c = uisetcolor(guiData.colorButtons(colNum).BackgroundColor);
        if length(c) == 3
            guiData.colorButtons(colNum).BackgroundColor = c;
        end
    end
    
    % Table size adjustment
    function adjustTableSize(~, ~)
        data = guiData.dataTable.Data;
        lastRow = find(~all(cellfun(@(x) any(isnan(x(:)) || isempty(x), data), 1, 'last')));
        if isempty(lastRow) || lastRow == size(data,1)
            newData = [data; num2cell(nan(1,4))];
            guiData.dataTable.Data = newData;
        end
    end
    
    % Main plot function
    function generatePlot(~, ~)
        guiData = guidata(gcf);
        data = cell2mat(guiData.dataTable.Data);
        validRows = ~any(isnan(data), 2);
        data = data(validRows,:);
        
        if isempty(data)
            errordlg('No valid data entered!', 'Input Error');
            return;
        end
        
        % Calculate means and SEM
        means = mean(data, 1);
        sems = std(data, 0, 1) / sqrt(size(data, 1));
        
        % Group positions
        groupCenters = [1, 2];
        barWidth = 0.35;
        groupOffset = 0.4;
        barPositions = [
            groupCenters(1) - groupOffset/2, ...
            groupCenters(1) + groupOffset/2, ...
            groupCenters(2) - groupOffset/2, ...
            groupCenters(2) + groupOffset/2
        ];
        
        % Create plot
        figure('Name', 'Grouped Bar Plot', 'Color', 'w');
        hold on;
        
        % Plot bars
        bars = gobjects(1,4);
        for i = 1:4
            bars(i) = bar(barPositions(i), means(i), barWidth, ...
                'FaceColor', guiData.colorButtons(i).BackgroundColor, ...
                'EdgeColor', 'k', 'LineWidth', 1);
        end
        
        % Error bars (hidden from legend)
        errorbar(barPositions, means, sems, 'k.', 'LineWidth', 1.5, 'CapSize', 10, ...
               'HandleVisibility', 'off');
        
        % Scatter points with connections
        jitter = 0.05 * barWidth;
        symbols = {'o', '+', '*', 'x', 's', 'd', '^', 'v', '>', '<', 'p', 'h'};
        symbolColors = lines(4); % Distinct colors for each column's points
        
        for row = 1:size(data,1)
            % Group 1 (Cols 1-2)
            x1 = barPositions(1) + jitter * (rand() - 0.5);
            x2 = barPositions(2) + jitter * (rand() - 0.5);
            scatter(x1, data(row,1), 60, symbolColors(1,:), ...
                   symbols{guiData.symbolMenus(1).Value}, 'LineWidth', 1.5);
            scatter(x2, data(row,2), 60, symbolColors(2,:), ...
                   symbols{guiData.symbolMenus(2).Value}, 'LineWidth', 1.5);
            plot([x1, x2], data(row,1:2), 'Color', [0.5 0.5 0.5 0.3], 'LineWidth', 1);
            
            % Group 2 (Cols 3-4)
            x3 = barPositions(3) + jitter * (rand() - 0.5);
            x4 = barPositions(4) + jitter * (rand() - 0.5);
            scatter(x3, data(row,3), 60, symbolColors(3,:), ...
                   symbols{guiData.symbolMenus(3).Value}, 'LineWidth', 1.5);
            scatter(x4, data(row,4), 60, symbolColors(4,:), ...
                   symbols{guiData.symbolMenus(4).Value}, 'LineWidth', 1.5);
            plot([x3, x4], data(row,3:4), 'Color', [0.5 0.5 0.5 0.3], 'LineWidth', 1);
        end
        
        % Customize plot
        xlim([0.5, 2.5]);
        set(gca, 'XTick', groupCenters, 'XTickLabel', {'Group 1', 'Group 2'}, ...
                'FontSize', 12, 'Box', 'on');
        
        % Apply user labels
        title(guiData.titleBox.String, 'FontSize', 14);
        xlabel(guiData.xlabelBox.String, 'FontSize', 12);
        ylabel(guiData.ylabelBox.String, 'FontSize', 12);
        
        % Legend with user names
        legendNames = arrayfun(@(i) guiData.colNameBoxes(i).String, 1:4, 'UniformOutput', false);
        legend(bars, legendNames, 'Location', 'best', 'FontSize', 10);
        
        grid on;
        hold off;
    end
end
