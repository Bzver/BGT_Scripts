import os
import sys
import glob
import subprocess

def concat_videos(input_dir, output_file=None, extensions=None):
    if extensions is None:
        extensions = ['mp4', 'mov', 'mkv', 'avi']
    
    files = []
    detected_ext = None
    for ext in extensions:
        pattern = os.path.join(input_dir, '*.' + ext)
        files.extend(glob.glob(pattern))
        if detected_ext is None:
            detected_ext = ext
        pattern_upper = os.path.join(input_dir, '*.' + ext.upper())
        files.extend(glob.glob(pattern_upper))
        if detected_ext is None:
            detected_ext = ext
    
    if not files:
        raise FileNotFoundError(f"No video files found in {input_dir}")
    
    if not output_file:
        folder_name = os.path.basename(os.path.normpath(input_dir))
        parent_dir = os.path.dirname(os.path.normpath(input_dir))
        output_file = os.path.join(parent_dir, f"{folder_name}_combined.{detected_ext}")

    files.sort()
    
    print(f"Found {len(files)} files:")
    for f in files:
        print(f"  - {os.path.basename(f)}")
    
    list_file = os.path.join(os.getcwd(), 'concat_list.txt')
    with open(list_file, 'w') as f:
        for video in files:
            escaped_path = video.replace('\\', '/').replace("'", "'\"'\"'")
            f.write(f"file '{escaped_path}'\n")
    
    cmd = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', list_file,
        '-c', 'copy',
        '-y', 
        output_file
    ]
    
    try:
        print("\nRunning FFmpeg...")
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("Success! Output saved to:", output_file)
    except subprocess.CalledProcessError as e:
        print("FFmpeg failed:", file=sys.stderr)
        print(e.stderr.decode('utf-8', errors='replace'), file=sys.stderr)
        sys.exit(1)
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)

if __name__ == "__main__":
    input_folder = "D:\Data\Videos\\20250913 Marathon\c55-S-Top"
    output_file = ""
    concat_videos(input_folder, output_file)