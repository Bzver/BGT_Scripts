import os
import sys
import glob
import subprocess

def concat_videos(input_dir, file_suffix=None, output_file=None, extensions=None):
    if extensions is None:
        extensions = ['mp4', 'mov', 'mkv', 'avi']
    
    files = []
    for ext in extensions:
        for pattern in [f'*.{ext}']:
            files.extend(glob.glob(os.path.join(input_dir, pattern)))
    
    if not files:
        raise FileNotFoundError(f"No video files found in {input_dir} with extensions {extensions}")
    
    files = [os.path.abspath(f) for f in files]
    files.sort()

    if file_suffix is not None:
        filtered_files = []
        for f in files:
            base = os.path.basename(f)
            name, ext = os.path.splitext(base)
            if name.endswith(file_suffix):
                filtered_files.append(f)
        files = filtered_files

    if not files:
        raise FileNotFoundError(f"No video files matched the suffix '{file_suffix}' in {input_dir}")

    print(f"Found {len(files)} files to concatenate:")
    for f in files:
        print(f"  - {os.path.basename(f)}")

    _, first_ext = os.path.splitext(files[0])
    output_ext = first_ext.lstrip('.').lower() or 'mp4'

    if output_file is None:
        folder_name = os.path.basename(os.path.normpath(input_dir))
        parent_dir = os.path.dirname(os.path.normpath(input_dir))
        output_file = os.path.join(parent_dir, f"{folder_name}_combined.{output_ext}")

    list_file = os.path.join(os.getcwd(), 'concat_list.txt')
    try:
        with open(list_file, 'w') as f:
            for video in files:
                path = video.replace('\\', '/')
                f.write(f"file '{path}'\n")

        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',
            '-y',
            output_file
        ]

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
    # # Single folder mode
    # input_folder = "D:\Data\Videos\\20250913 Marathon\c55-S-Top"
    # output_file = ""
    # concat_videos(input_folder, output_file)

    # Batch folder mode
    # prime_folder = "D:/Data\Videos\\20251013 Marathon\\N2"
    # for f in os.listdir(prime_folder):
    #     if not os.path.isdir(os.path.join(prime_folder, f)):
    #         continue

    #     input_folder = os.path.join(prime_folder, f)
    #     concat_videos(input_folder, file_suffix="-proc-resized")

    # Rescursive folder mode
    prime_folder = "D:\Data\Videos\\2B_Proc"
    for f in os.listdir(prime_folder):
        pf = os.path.join(prime_folder, f)
        if not os.path.isdir(pf):
            continue
        for sf in os.listdir(pf):
            psf = os.path.join(pf, sf)
            if not os.path.isdir(psf):
                continue
            input_folder = psf
            concat_videos(input_folder, file_suffix="-proc")