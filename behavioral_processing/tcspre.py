import os
import re
import csv
import pandas as pd
import glob

def convert_to_seconds(time_str):
    if not time_str or time_str == "":
        return 0.0
    try:
        return float(time_str)
    except ValueError:
        pass
    
    parts = time_str.split(':')
    try:
        if len(parts) == 3: # HH:MM:SS
            h, m, s = map(float, parts)
            return h * 3600 + m * 60 + s
        elif len(parts) == 2: # MM:SS
            m, s = map(float, parts)
            return m * 60 + s
    except:
        return 0.0
    return 0.0

def parse_single_file(file_path):
    results = {}
    current_id = None
    zone_map = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return {}

    header_row_1 = None # The row with "Zone: ..."
    header_row_2 = None # The row with "No.", "Date", "Duration (s)"
    is_reading_data = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        reader = csv.reader([line])
        cols = next(reader)
        cols = [c.strip() for c in cols]

        id_match = re.search(r'(?:\(ID\s+(\d+)\)|ID\s+(\d+)\s*\()', stripped)
        if id_match:
            id_val = id_match.group(1) if id_match.group(1) else id_match.group(2)
            if id_val:
                current_id = int(id_val)
                results[current_id] = {}
                zone_map = {}
                header_row_1 = None
                header_row_2 = None
                is_reading_data = False
                continue

        if current_id is None:
            continue

        if header_row_1 is None and any("Zone:" in c for c in cols):
            header_row_1 = cols
            continue

        if header_row_1 is not None and header_row_2 is None:
            if "No." in cols[0] and any("Duration (s)" in c for c in cols):
                header_row_2 = cols

                for i, metric in enumerate(header_row_2):
                    if "Duration (s)" in metric:
                        if i < len(header_row_1):
                            zone_header = header_row_1[i]
                        
                            if zone_header and zone_header.startswith("Zone:"):
                                zone_name = zone_header.replace("Zone:", "").strip().lower()
                                
                                zone_key = ""
                                if 'd' in zone_name:
                                    base = 'D'
                                elif 's' in zone_name:
                                    base = 'S'
                                else:
                                    continue # Unknown zone type
                                    
                                if 'in' in zone_name:
                                    suffix = 'i'
                                else:
                                    suffix = 'o'
                                    
                                zone_key = f"{base}{suffix}"
                                zone_map[i] = zone_key
                
                is_reading_data = True
                continue

        if is_reading_data and current_id is not None:
            if not cols or (len(cols) == 1 and cols[0] == ''):
                continue

            interval_str = cols[0]
            try:
                interval = int(interval_str)
            except ValueError:
                continue

            if interval not in results[current_id]:
                results[current_id][interval] = {}
            
            for col_idx, zone_key in zone_map.items():
                if col_idx < len(cols):
                    dur = convert_to_seconds(cols[col_idx])
                    results[current_id][interval][zone_key] = dur

    return results


def process_folder(folder_path):
    if not os.path.exists(folder_path):
        print(f"Error: Folder path does not exist: {folder_path}")
        return pd.DataFrame()

    all_files = glob.glob(os.path.join(folder_path, "*.csv"))
    
    pre_files = {}
    main_files = {}
    
    for f in all_files:
        basename = os.path.basename(f)
        if basename.lower().endswith('p.csv'):
            key = basename[:-5] # remove 'p.csv'
            pre_files[key] = f
        else:
            key = basename[:-4] # remove '.csv'
            main_files[key] = f
            
    combined_data = []
    
    for key, main_path in main_files.items():
        pre_path = pre_files.get(key)
        
        if not pre_path:
            continue
            
        print(f"Processing pair: {key}")
        
        try:
            main_data = parse_single_file(main_path)
            pre_data = parse_single_file(pre_path)
        except Exception as e:
            print(f"Error parsing files for {key}: {e}")
            import traceback
            traceback.print_exc()
            continue
            
        if not main_data:
            print(f"Warning: No data extracted from Main file {key}")
            continue

        ids = sorted(main_data.keys())
        
        for animal_id in ids:
            row = {}
            source_id = f"{key}-{animal_id}"
            row['Data_Source'] = source_id
            
            zones = ['Di', 'Do', 'Si', 'So']
            
            for zone in zones:
                pre_val = 0.0
                if animal_id in pre_data:
                    if 1 in pre_data[animal_id]:
                        pre_val = pre_data[animal_id][1].get(zone, 0.0)
                row[f'{zone}_pre'] = pre_val

                intervals = list(range(1,31))
                sum_val = 0.0
                
                for i, interval_num in enumerate(intervals):
                    val = 0.0
                    if animal_id in main_data and interval_num in main_data[animal_id]:
                        val = main_data[animal_id][interval_num].get(zone, 0.0)
                    
                    col_name = f"{zone}_{(interval_num)}min"
                    row[col_name] = val
                    sum_val += val
                    
                row[f'{zone}_Sum'] = sum_val
                
            combined_data.append(row)
            
    if not combined_data:
        return pd.DataFrame()
        
    df_final = pd.DataFrame(combined_data)
    
    desired_order = []
    for zone in ['Di', 'Do', 'Si', 'So']:
        desired_order.append(f'{zone}_pre')
        for i in list(range(1, 31)):
            desired_order.append(f'{zone}_{i}min')
        desired_order.append(f'{zone}_Sum')
    
    final_cols = ['Data_Source'] + desired_order
    
    for col in final_cols:
        if col not in df_final.columns:
            df_final[col] = 0.0
            
    df_final = df_final[final_cols]
    
    return df_final

if __name__ == "__main__":
    folder_path = r'D:\Data\TCS'
    
    print("Starting batch processing...")
    df_result = process_folder(folder_path)
    
    if not df_result.empty:
        output_filename = "Unified_Zone_Durations.csv"
        output_path = os.path.join(folder_path, output_filename)
        df_result.to_csv(output_path, index=False)
        print(f"\nSuccess! Data saved to {output_path}")
        print(df_result.head())
    else:
        print("No data processed. Check file naming conventions.")