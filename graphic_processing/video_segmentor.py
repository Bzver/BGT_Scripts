import subprocess
import os

def format_time_ffmpeg(seconds_total):
    """Converts total seconds to HH:MM:SS format for ffmpeg."""
    hours = int(seconds_total // 3600)
    minutes = int((seconds_total % 3600) // 60)
    seconds = int(seconds_total % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def cut_video_into_segments(input_video_path, output_directory,
                            num_segments=4, segment_duration_minutes=10):
    """
    Cuts a video into a specified number of segments, each of a given duration.

    Args:
        input_video_path (str): Path to the input video file.
        output_directory (str): Directory where segmented videos will be saved.
        num_segments (int): The number of segments to create.
        segment_duration_minutes (int): Duration of each segment in minutes.
    """
    if not os.path.isfile(input_video_path):
        print(f"Error: Input video file not found at {input_video_path}")
        return

    if not os.path.exists(output_directory):
        try:
            os.makedirs(output_directory)
            print(f"Created output directory: {output_directory}")
        except OSError as e:
            print(f"Error creating output directory {output_directory}: {e}")
            return

    # Check if ffmpeg is installed and accessible
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True, shell=True)
    except FileNotFoundError:
        print("Error: ffmpeg command not found. Please ensure FFmpeg is installed and in your system's PATH.")
        return
    except subprocess.CalledProcessError as e:
        # This might happen if ffmpeg -version itself errors for some reason
        print(f"Error while checking ffmpeg version. FFmpeg might not be configured correctly.\nStderr: {e.stderr}")
        return

    base_name, ext = os.path.splitext(os.path.basename(input_video_path))
    segment_duration_seconds = segment_duration_minutes * 60
    duration_ffmpeg_format = format_time_ffmpeg(segment_duration_seconds)

    for i in range(num_segments):
        start_time_seconds = i * segment_duration_seconds
        start_time_ffmpeg_format = format_time_ffmpeg(start_time_seconds)

        output_filename = f"{base_name}_segment_{i+1}{ext}"
        output_segment_path = os.path.join(output_directory, output_filename)

        # Using -c copy for fast, lossless cutting (stream copy)
        # Using -y to overwrite output files without asking
        command = [
            "ffmpeg",
            "-i", input_video_path,
            "-ss", start_time_ffmpeg_format,
            "-t", duration_ffmpeg_format,
            "-c", "copy",
            "-y", # Overwrite output files without asking
            output_segment_path
        ]

        print(f"\nProcessing segment {i+1}/{num_segments}: {output_segment_path}")

        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True, shell=True)
            print(f"Successfully created segment: {output_segment_path}")
            # ffmpeg often prints informational messages to stderr
            if result.stderr:
                print(f"FFmpeg output:\n{result.stderr.strip()}")
        except subprocess.CalledProcessError as e:
            print(f"Error cutting segment {i+1} to {output_segment_path}")
            print(f"Return code: {e.returncode}")
            if e.stdout:
                print(f"FFmpeg stdout:\n{e.stdout.strip()}")
            if e.stderr:
                print(f"FFmpeg stderr:\n{e.stderr.strip()}")
            print("Continuing to next segment if any...")

if __name__ == "__main__":
    input_video = 'D:/Stockpile/2025-05-17 20-47-47/2025-05-17 20-47-47.mp4'  # Replace with your input video file
    segments_output_folder = 'D:/Stockpile/video_segments_output' # Replace with your desired output directory

    print(f"Starting video segmentation for: {input_video}")
    print(f"Output will be saved to: {segments_output_folder}")

    cut_video_into_segments(input_video, segments_output_folder, num_segments=4, segment_duration_minutes=10)

    print("\nVideo cutting process finished.")