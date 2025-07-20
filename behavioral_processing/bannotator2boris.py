import os
import re
import pandas as pd
import numpy as np

#################   W   ##################   I   ##################   P   ##################   

def read_text_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        print(f"Error: The file at {file_path} was not found.")
        return None
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return None

def parse_annotation(text_content):
    config = {}
    s1_data = []
    lines = text_content.strip().split('\n')
    
    # Find the start of the configuration section
    config_start_index = -1
    for i, line in enumerate(lines):
        if "Configuration file:" in line:
            config_start_index = i + 1
            break
    
    # Parse configuration
    if config_start_index != -1:
        for i in range(config_start_index, len(lines)):
            line = lines[i].strip()
            if not line: # Empty line
                continue
            if "S1:" in line: # End of config, start of S1
                break
            
            parts = re.split(r'\s+', line)
            if len(parts) == 2:
                config[parts[0]] = parts[1]

    # Find the start of the S1 section
    s1_start_index = -1
    for i, line in enumerate(lines):
        if "S1:" in line:
            s1_start_index = i + 2 # Skip "S1:" and "-----------------------------"
            break

    # Parse S1 data
    if s1_start_index != -1:
        for i in range(s1_start_index, len(lines)):
            line = lines[i].strip()
            if not line:
                continue
            
            # Use regex to handle multiple spaces/tabs as delimiters
            parts = re.split(r'\s+', line)
            
            # Filter out empty strings from parts
            parts = [part for part in parts if part]

            if len(parts) == 3: # Expecting start, end, type
                try:
                    start = int(parts[0])
                    end = int(parts[1])
                    type_ = parts[2]
                    s1_data.append({"start": start, "end": end, "type": type_})
                except ValueError:
                    # Handle cases where conversion to int fails
                    continue
    
    return config, s1_data

def annot_to_csv(input_file, fps, behavior_map=None, cutoff=None):
    file_name = input_file.split(".")[0]
    text_content = read_text_file(input_file)
    config, data = parse_annotation(text_content)
    # Determine all unique behaviors, considering both original and mapped names
    all_behaviors = set()
    for seg in data:
        original_type = seg["type"]
        if behavior_mapping and original_type in behavior_mapping:
            all_behaviors.add(behavior_mapping[original_type])
        else:
            all_behaviors.add(original_type)
            
    behaviors_list = sorted(list(all_behaviors)) # Sort for consistent column order
    max_frame = data[-1]["end"]
    if cutoff and cutoff < max_frame:
        max_frame = cutoff

    # Initialize empty df for storing annotations
    columns = ["time"] + behaviors_list
    df_annot = pd.DataFrame(np.zeros((max_frame, len(behaviors_list) + 1)), columns=columns)
    df_annot["time"] = np.array(range(max_frame)) / fps
    
    for seg in data:
        original_type = seg["type"]
        # Apply behavior mapping if provided
        if behavior_mapping and original_type in behavior_mapping:
            col = behavior_mapping[original_type]
        else:
            col = original_type
        
        start = seg["start"] - 1
        end = seg["end"] - 1
        
        df_annot.loc[start:end, col] = 1
    
    output_csv = f"{file_name}.csv"
    df_annot.to_csv(output_csv, index=False)

if __name__ == "__main__":
    project_path = "D:/Project/DLC-Models/NTD/videos/jobs/assdfa/"
    annot_path = os.path.join(project_path,"20250626-directorsCut_annot.txt")
    behavior_mapping =  {
        "leftchamber": "other",
        "rightchamber": "other",
        "leftinitiative": "other",
        "rightinitiative": "initiative",
        "leftpassive": "other",
        "rightpassive": "passive",
        "leftflee": "other",
        "rightflee": "flee",
        "middleChamber": "other"
    }
    cutoff_frame = 12000
    fps = 10
    annot_to_csv(annot_path, fps, behavior_mapping, cutoff_frame)