import os
import sys

import numpy as np
import cv2

def get_video_preview(video_path, frames_to_sample=100, output_folder=None):
    if not os.path.isfile(video_path):
        print(f"Error: Video file not found at {video_path}", file=sys.stderr)
        return []
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file {video_path}", file=sys.stderr)
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames == 0:
        print(f"Error: Video file {video_path} has no frames.", file=sys.stderr)
        cap.release()
        return []
    
    if total_frames < frames_to_sample:
        print(f"Warning: Video has less than {frames_to_sample} frames. Returning all available frames.", file=sys.stderr)
        frames_to_sample = total_frames

    sampled_frames = []
    if total_frames > 1:
        indices = np.linspace(0, total_frames - 1, frames_to_sample, dtype=int)
    else:
        indices = [0] # Handle single frame video

    for i in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret:
            sampled_frames.append(frame)
        else:
            print(f"Warning: Could not read frame {i} from {video_path}", file=sys.stderr)

    if output_folder:
        os.makedirs(output_folder, exist_ok=True)
        for idx, frame in enumerate(sampled_frames):
            frame_filename = os.path.join(output_folder, f"frame_{idx:03d}.png")
            cv2.imwrite(frame_filename, frame)
        print(f"Sampled frames saved to {output_folder}")

    cap.release()
    print("\nPreview generation complete.")
    return sampled_frames