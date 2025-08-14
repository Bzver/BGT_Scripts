import os
import re
import pandas as pd
import numpy as np

def annot_to_csv(input_file, fps, behavior_map=None, cutoff=None, output_path= None):
    file_name = input_file.split(".")[0]
    text_content = read_text_file(input_file)
    config, data = parse_annotation(text_content)
    # Determine all unique behaviors, considering both original and mapped names
    all_behaviors = set()
    for seg in data:
        original_type = seg["type"]
        if behavior_map and original_type in behavior_map:
            all_behaviors.add(behavior_map[original_type])
        else:
            all_behaviors.add(original_type)
            
    # Separate 'other' behavior if it exists, and sort the rest
    behaviors_list = sorted([b for b in all_behaviors if b != "other"])
    if "other" in all_behaviors:
        behaviors_list.append("other") # Ensure 'other' is always last
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
        if behavior_map and original_type in behavior_map:
            col = behavior_map[original_type]
        else:
            col = original_type
        
        start = seg["start"] - 1
        end = seg["end"] - 1
        
        df_annot.loc[start:end, col] = 1
    
    if not output_path:
        output_path = f"{file_name}.csv"
    df_annot.to_csv(output_path, index=False)
    print(f"Exported csv saved to {output_path}.")

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
    if text_content is None:
        print("Annotation is empty?!!")
        return
    
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

if __name__ == "__main__":
    fps = 10
    project_path = "D:/DGH/Data/Videos/2025-06-26 7day Marathon"
    annot_path = os.path.join(project_path, "20250626-directorsCut_annot.txt")

    output_name_L = "1-20250626_annot_L"
    output_name_R = "2-20250626_annot_R"

    output_path_L = os.path.join(project_path, f"{output_name_L}.csv")
    output_path_R = os.path.join(project_path, f"{output_name_R}.csv")

    behavior_mapping_L =  {
        "leftchamber": "idle",
        "rightchamber": "other",
        "leftinitiative": "initiative",
        "rightinitiative": "other",
        "leftpassive": "passive",
        "rightpassive": "other",
        "leftflee": "flee",
        "rightflee": "other",
        "middleChamber": "other"
    }

    behavior_mapping_R =  {
        "leftchamber": "other",
        "rightchamber": "idle",
        "leftinitiative": "other",
        "rightinitiative": "initiative",
        "leftpassive": "other",
        "rightpassive": "passive",
        "leftflee": "other",
        "rightflee": "flee",
        "middleChamber": "other"
    }
    cutoff_frame = 125800

    annot_to_csv(annot_path, fps, behavior_mapping_L, cutoff_frame, output_path_L)
    annot_to_csv(annot_path, fps, behavior_mapping_R, cutoff_frame, output_path_R)