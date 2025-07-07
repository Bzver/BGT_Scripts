import os
import subprocess
import math
import json

def get_video_duration(video_path):
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration_data = json.loads(result.stdout)
        return float(duration_data['format']['duration'])
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error getting duration for {video_path}: {e}")
        return 0

def find_optimal_grid(num_videos):
    """Find x, y for grid with smallest x+y where x*y >= num_videos."""
    best_x, best_y = 1, num_videos
    min_sum = best_x + best_y

    for x in range(1, int(math.sqrt(num_videos)) + 2):
        y = math.ceil(num_videos / x)
        if x * y >= num_videos and x + y < min_sum:
            min_sum = x + y
            best_x, best_y = x, y
    return best_x, best_y

def merge_videos_to_grid(input_folder, output_folder):
    video_files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))]
    if not video_files:
        print(f"No video files found in {input_folder}")
        return

    video_paths = [os.path.join(input_folder, f) for f in video_files]

    # Get durations and find the longest video
    video_durations = {}
    longest_video_duration = 0
    for vp in video_paths:
        duration = get_video_duration(vp)
        video_durations[vp] = duration
        if duration > longest_video_duration:
            longest_video_duration = duration

    target_merged_duration = longest_video_duration * 3
    print(f"Longest video duration: {longest_video_duration:.2f} seconds")
    print(f"Target merged video duration: {target_merged_duration:.2f} seconds")

    num_videos = len(video_paths)
    grid_x, grid_y = find_optimal_grid(num_videos)
    print(f"Optimal grid dimensions: {grid_x} rows, {grid_y} columns (total cells: {grid_x * grid_y})")

    # FFmpeg command construction
    input_streams = []
    filter_complex_parts = []
    xstack_inputs_video = []

    target_width, target_height = 1280, 740

    for i, video_path in enumerate(video_paths):
        current_duration = video_durations[video_path]
        if current_duration == 0:
            print(f"Skipping {video_path} due to zero duration.")
            continue

        # Use -stream_loop input option for efficiency
        if current_duration > 0 and current_duration < target_merged_duration:
            num_loops = math.ceil(target_merged_duration / current_duration)
            loop_count = int(num_loops - 1)
            input_streams.extend(['-stream_loop', str(loop_count), '-i', video_path])
        else:
            # No looping needed if the video is already long enough
            input_streams.extend(['-i', video_path])

        # Video processing filter chain - no loop filter needed here
        video_filter = (
            f"[{i}:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1[v{i}];"
        )
        filter_complex_parts.append(video_filter)
        xstack_inputs_video.append(f"[v{i}]")

    # Create empty video streams for padding if num_videos < grid_x * grid_y
    empty_video_count = (grid_x * grid_y) - num_videos
    for i in range(empty_video_count):
        # Create a black video stream for padding
        filter_complex_parts.append(f"color=c=black:s={target_width}x{target_height}:d={target_merged_duration}[v_empty{i}];")
        xstack_inputs_video.append(f"[v_empty{i}]")

    # Video xstack
    filter_complex_parts.append(
        f"{''.join(xstack_inputs_video)}xstack=inputs={grid_x * grid_y}:grid={grid_x}x{grid_y}:fill=black[v_out]"
    )

    output_filename = os.path.join(output_folder,f"{os.path.basename(input_folder)}.mp4")

    # Final FFmpeg command
    ffmpeg_cmd = [
        'ffmpeg',
        *input_streams,
        '-filter_complex',
        ''.join(filter_complex_parts),
        '-map', '[v_out]',
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-t', str(target_merged_duration), # Trim output to target duration
        output_filename
    ]

    print("\nExecuting FFmpeg command:")
    print(" ".join(ffmpeg_cmd))

    try:
        subprocess.run(ffmpeg_cmd, check=True)
        print(f"\nSuccessfully merged videos to {output_filename}")
    except subprocess.CalledProcessError as e:
        print(f"\nError during FFmpeg execution: {e}")
        print(f"FFmpeg stderr: {e.stderr}")
    except FileNotFoundError:
        print("\nError: ffmpeg or ffprobe not found. Please ensure FFmpeg is installed and added to your system's PATH.")

def processing_behatlas_project(project_folder):
    if not os.path.isdir(project_folder):
        print(f"BehaviorAtlas segmentation video folder not found at {project_folder}!")
        return False
    else:
        project_videos = [os.path.join(project_folder,f) for f in os.listdir(project_folder) if os.path.isdir(os.path.join(project_folder,f))]
        for video_folder in project_videos:
            merge_videos_to_grid(video_folder, project_folder)
        return True

if __name__ == "__main__":
    project_folder = "D:/Project/BehaviorAtlas-Analysis/Video_seg/cam3/"
    processing_behatlas_project(project_folder)