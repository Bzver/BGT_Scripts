import subprocess
import os
import sys
from pathlib import Path

def check_ffmpeg():
    """Check if ffmpeg is installed"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def get_video_info(video_path):
    """Get video duration and dimensions using ffprobe"""
    # Get Duration
    cmd_dur = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(video_path)
    ]
    result_dur = subprocess.run(cmd_dur, capture_output=True, text=True)
    if not result_dur.stdout.strip():
        raise Exception(f"Could not get duration for {video_path}")
    duration = float(result_dur.stdout.strip())
    
    # Get Dimensions
    cmd_dim = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=p=0',
        str(video_path)
    ]
    result_dim = subprocess.run(cmd_dim, capture_output=True, text=True)
    if not result_dim.stdout.strip():
        raise Exception(f"Could not get dimensions for {video_path}")
    
    width, height = map(int, result_dim.stdout.strip().split(','))
    return duration, width, height

def create_grid_video(input_folder, output_file='output_preview.mp4', max_duration=60):
    """
    Creates a 4x2 grid video.
    max_duration: Limits output to X seconds (default 60) for quick testing.
    """
    input_path = Path(input_folder)
    
    # 1. Check FFmpeg
    if not check_ffmpeg():
        print("❌ Error: ffmpeg is not installed.")
        sys.exit(1)
    
    # 2. Find Files
    all_videos = [f for f in os.listdir(input_path) if f.endswith(".mp4")]
    video_files = []
    
    # Sort them 1 to 8 based on filename start
    for i in range(1, 9):
        for vid in all_videos:
            if vid.startswith(str(i)):  
                video_files.append(vid)
                
    if len(video_files) != 8:
        print(f"❌ Error: Found {len(video_files)} videos. Need exactly 8.")
        sys.exit(1)

    print(f"✅ Found 8 videos. Analyzing (Limiting to first {max_duration}s)...")
    
    # 3. Get Info & Find Smallest Size
    widths = []
    heights = []
    
    for vid_name in video_files:
        full_path = input_path / vid_name
        d, w, h = get_video_info(full_path)
        widths.append(w)
        heights.append(h)
        print(f"   {vid_name}: {w}x{h}")

    target_w = min(widths)
    target_h = min(heights)
    
    print(f"\n📏 Grid Cell Size: {target_w}x{target_h}")
    print(f"🖼️  Final Output Size: {target_w * 2}x{target_h * 4}")

    # 4. Build Command
    inputs = []
    for vid_name in video_files:
        inputs.extend(['-i', str(input_path / vid_name)])

    # 5. The Magic Filter (xstack)
    scale_parts = []
    for i in range(8):
        # Scale and pad to ensure uniform blocks
        s = f"[{i}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2[v{i}]"
        scale_parts.append(s)
    
    # Layout for 4 rows, 2 cols
    layout = f"0_0|{target_w}_0|0_{target_h}|{target_w}_{target_h}|0_{target_h*2}|{target_w}_{target_h*2}|0_{target_h*3}|{target_w}_{target_h*3}"
    
    xstack_part = f"[v0][v1][v2][v3][v4][v5][v6][v7]xstack=inputs=8:layout={layout}[out]"
    
    filter_complex = ";".join(scale_parts + [xstack_part])

    # 6. Run FFmpeg
    cmd = ['ffmpeg'] + inputs + [
        '-filter_complex', filter_complex,
        '-map', '[out]',
        '-t', str(max_duration),  # <--- THIS LIMITS THE TIME
        '-c:v', 'libx264',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-y',
        str(output_file)
    ]
    
    print(f"\n🎬 Creating preview ({max_duration}s)...")
    process = subprocess.run(cmd, capture_output=True, text=True)
    
    if process.returncode == 0:
        print(f"\n🎉 SUCCESS! Preview saved as: {output_file}")
        print("Check this file. If it looks good, change max_duration to 0 (for full length) and run again.")
    else:
        print("\n❌ FAILED:")
        print(process.stderr)

if __name__ == "__main__":
    folder = r"D:\Data\Videos\20260623 ANR\pre\1 batch"
    # Change max_duration to 0 for full video, or keep 60 for test
    create_grid_video(folder, max_duration=3574)