import os

import subprocess

#######################    W    #######################    I    #######################    P    #######################

frame_list = [1,3,56,78]

def extract_frame_and_label(original_vid, prediction, frame_list, deeplabcut_dir = None):
    if not os.path.isfile(original_vid):
        print(f"Original video not found at {original_vid}")
        return
    if not os.path.isfile(prediction):
        print(f"Prediction file not found at {prediction}")
        return
    
    # Extract frame
    video_name = os.path.basename(original_vid).split(".")[0]
    video_path = os.path.dirname(original_vid)
    for frame in frame_list:
        image_path = [f"img{str(int(frame)).zfill(8)}.png"]
        if deeplabcut_dir is not None:
            image_output_path = os.path.join(deeplabcut_dir,"labeled-data",video_name,image_path)
        else:
            image_output_path = os.path.join(video_path,image_path)
        if os.path.isfile(image_output_path):
            print(f"Frame {frame} already in the {deeplabcut_dir}, skipping...")
            continue
        else:
            ffmpeg_command = f'ffmpeg -y -i "{original_vid}" -vf select="eq(n\,{int(frame)})" -vframes 1 "{image_output_path}"'
            try:
                subprocess.run(ffmpeg_command, shell=True, check=True, capture_output=True, text=True)
                print(f"Successfully extracted frame {frame}.")
            except subprocess.CalledProcessError as e:
                print(f"Error extracting frame {frame}: {e}")
                print(f"Stderr: {e.stderr}")
                print(f"Stdout: {e.stdout}")

    # Extract label
