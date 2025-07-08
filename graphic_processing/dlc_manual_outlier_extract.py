import os
import pandas as pd
import h5py
import subprocess

#######################    W    #######################    I    #######################    P    #######################

def extract_frame_and_label(original_vid, prediction, frame_list, deeplabcut_dir = None):
    if not os.path.isfile(original_vid):
        print(f"Original video not found at {original_vid}")
        return False
    elif not os.path.isfile(prediction):
        print(f"Prediction file not found at {prediction}")
        return False
    else:
        video_name = os.path.basename(original_vid).split(".")[0]
        video_path = os.path.dirname(original_vid)
        if deeplabcut_dir is not None:
            project_dir = os.path.join(deeplabcut_dir,"labeled-data",video_name)
            existing_img = [ int(f.split("img")[1].split(".")[0]) for f in os.listdir(project_dir) if f.endswith(".png") and f.startswith("img") ]
            for frame in frame_list:
                if frame in existing_img:
                    frame_list.remove(frame)
                    print(f"Frame {frame} already in the {project_dir}, skipping...")
        else:
            project_dir = video_path
        frame_extraction = extract_frame(original_vid, frame_list, project_dir)
        label_extraction = extract_label(prediction, frame_list, deeplabcut_dir)
        if frame_extraction and label_extraction:
            print("Extraction successful.")
            return True
        else:
            fail_message = ""
            fail_message += " extract frame" if not frame_extraction else ""
            fail_message += " extract label" if not label_extraction else ""
            print(f"Extraction failed. Error:{fail_message}")
    
def extract_frame(original_vid, frame_list, project_dir):
    # Extract frame from original vid
    for frame in frame_list:
        image_path = [f"img{str(int(frame)).zfill(8)}.png"]
        image_output_path = os.path.join(project_dir,image_path)
        ffmpeg_command = f'ffmpeg -y -i "{original_vid}" -vf select="eq(n\,{int(frame-1)})" -vframes 1 "{image_output_path}"'
        try:
            subprocess.run(ffmpeg_command, shell=True, check=True, capture_output=True, text=True)
            print(f"Successfully extracted frame {frame}.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error extracting frame {frame}: {e}")
            print(f"Stderr: {e.stderr}")
            print(f"Stdout: {e.stdout}")

def extract_label(prediction, frame_list, deeplabcut_dir = None): ## Unimplemented
    # Extract label from prediction
    with h5py.File(prediction, 'r') as pred_file:
        if not "tracks" in pred_file.keys():
            print("Error: Prediction file not valid, no 'tracks' key found in prediction file.")
            return False
        else:
            if not "table" in pred_file["tracks"].keys():
                print("Errpr: Prediction file not valid, no prediction table found in 'tracks'.")
                return False
        data = []
        for frame in frame_list:
            data.append(pred_file["tracks"]["table"][frame-1][1])
        data_df = pd.DataFrame(data)

        print(data_df)

if __name__ == "__main__":
    video_name = ""
    frame_list = ""
    extract_frame(video_name, frame_list)