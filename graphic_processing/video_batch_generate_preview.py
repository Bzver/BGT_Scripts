import os
import subprocess
import re

def generate_video_preview(input_path, output_path, start_time, duration):
    """
    Generates a video preview using ffmpeg.

    Args:
        input_path (str): Path to the input video file.
        output_path (str): Path for the output preview file.
        start_time (str): Start time for the preview in HH:MM:SS or seconds.
        duration (str): Duration of the preview in HH:MM:SS or seconds.
    """
    command = [
        'ffmpeg',
        '-ss', str(start_time),
        '-i', input_path,
        '-t', str(duration),
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-y', # Overwrite output files without asking
        output_path
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Generated preview: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error generating preview for {input_path}:")
        print(f"STDOUT: {e.stdout.decode()}")
        print(f"STDERR: {e.stderr.decode()}")
    except FileNotFoundError:
        print("Error: ffmpeg not found. Please ensure ffmpeg is installed and in your system's PATH.")

def get_video_files(folder_path):
    """
    Lists all common video files in a given folder.
    """
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm')
    video_files = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(video_extensions):
            video_files.append(os.path.join(folder_path, filename))
    return video_files

def is_valid_time_format(time_str):
    """Checks if a string is a valid time format (HH:MM:SS or seconds)."""
    # Regex for HH:MM:SS
    if re.fullmatch(r'(\d{1,2}:){0,2}\d{1,2}', time_str):
        return True
    # Check if it's a number (seconds)
    try:
        float(time_str)
        return True
    except ValueError:
        return False

def parse_timestamps(file_path):
    """
    Parses a text file with timestamp entries in format "HH:MM:SS - description"
    and returns a list of dictionaries with start_time and save_name.
    """
    entries = []
    
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if not line:  # Skip empty lines
                continue
                
            # Split on the first occurrence of " - "
            if " - " in line:
                start_time, save_name = line.split(" - ", 1)
                entries.append({
                    "start_time": start_time.strip(),
                    "save_name": save_name.strip()
                })
            else:
                print(f"Skipping malformed line: {line}")
    
    return entries

if __name__ == "__main__":
    
    MODE = input("Press 1 to load existing timestamp.txt and preview a single video, or else preview the whole folder:")

    if MODE == '1':
        timestamp = input("Enter the path of timestamp files: ")
        video_file = input("Enter the path of the video file: ")
        length = input("Enter the duration of the preview (e.g., 00:00:05 or 5 for 5 seconds): ")
        folder_path = os.path.dirname(video_file)
        if os.path.isfile(video_file) and os.path.isfile(timestamp):
            entries = parse_timestamps(timestamp)
            for entry in entries:
                start_time = entry["start_time"]
                save_name = entry["save_name"]
                output_folder = os.path.join(folder_path, "video_previews")
                os.makedirs(output_folder, exist_ok=True)
                output_file = os.path.join(output_folder, f"{save_name}.mp4")
                generate_video_preview(video_file, output_file, start_time, length)
        else:
            print(f"Error: Video file '{video_file}' or timestamp file '{timestamp}' not found.")
    else:
        folder_path = input("Enter the folder path containing video files: ")
        if not os.path.isdir(folder_path):
            print(f"Error: Folder '{folder_path}' not found.")
        else:
                start_time = input("Enter the start time for the preview (e.g., 00:00:10 or 10 for 10 seconds): ")
                while not is_valid_time_format(start_time):
                    print("Invalid start time format. Please use HH:MM:SS or seconds (e.g., 00:00:10 or 10).")
                    start_time = input("Enter the start time for the preview: ")

                duration = input("Enter the duration of the preview (e.g., 00:00:05 or 5 for 5 seconds): ")
                while not is_valid_time_format(duration):
                    print("Invalid duration format. Please use HH:MM:SS or seconds (e.g., 00:00:05 or 5).")
                    duration = input("Enter the duration of the preview: ")

                output_folder = os.path.join(folder_path, "video_previews")
                os.makedirs(output_folder, exist_ok=True)

                video_files = get_video_files(folder_path)

                if not video_files:
                    print(f"No video files found in '{folder_path}'.")
                else:
                    print(f"Found {len(video_files)} video files. Generating previews...")
                    for video_file in video_files:
                        base_name = os.path.basename(video_file)
                        name, ext = os.path.splitext(base_name)
                        output_file = os.path.join(output_folder, f"{name}_preview.mp4")
                        generate_video_preview(video_file, output_file, start_time, duration)
                    print("\nPreview generation complete. Previews are saved in the 'video_previews' subfolder.")