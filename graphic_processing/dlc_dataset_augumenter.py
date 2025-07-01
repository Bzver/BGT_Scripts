import os
import sys

import cv2

import numpy as np
from scipy.interpolate import interp1d

################  W  ####  I  ####  P  ###############

dlcDatasetFolder = "D:/Project/DLC-Models/NTD/labeled-data"
videoFile = "D:/Data/DGH/Videos/2025-06-26 7D Marathon/video_previews/2025-06-24 22-29-29_preview-cam4.mp4"

def get_eligible_dataset(base_folder):
    if not os.path.isdir(base_folder):
        print(f"Error: DLC dataset folder not found at {base_folder}", file=sys.stderr)
        return False
    dataset_folder = []
    for root, dirs, files in os.walk(base_folder):
        dirs[:] = [d for d in dirs if not d.endswith("_labeled") and not d.endswith("_augmented")] 
        if 'CollectedData_bezver.h5' in files:
            dataset_folder.append(root)
    return dataset_folder

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

def compare_tones(img_1, img_2, hist_bins=16, hist_range=[0, 256]):
    if not os.path.isfile(img_1) or not os.path.isfile(img_2):
        not_found_path = img_1 if not os.path.isfile(img_1) else img_2
        print(f"Error: Images to be compared not found at {not_found_path}", file=sys.stderr)
        return False

    ref_img_1 = cv2.imread(img_1)
    ref_lab_1 = cv2.cvtColor(ref_img_1, cv2.COLOR_BGR2LAB)
    
    ref_img_2 = cv2.imread(img_2)
    ref_lab_2 = cv2.cvtColor(ref_img_2, cv2.COLOR_BGR2LAB)

    # Calculate histograms for each LAB channel
    hist_1_L = cv2.calcHist([ref_lab_1], [0], None, [hist_bins], hist_range)
    hist_1_A = cv2.calcHist([ref_lab_1], [1], None, [hist_bins], hist_range)
    hist_1_B = cv2.calcHist([ref_lab_1], [2], None, [hist_bins], hist_range)

    hist_2_L = cv2.calcHist([ref_lab_2], [0], None, [hist_bins], hist_range)
    hist_2_A = cv2.calcHist([ref_lab_2], [1], None, [hist_bins], hist_range)
    hist_2_B = cv2.calcHist([ref_lab_2], [2], None, [hist_bins], hist_range)

    # Normalize histograms
    cv2.normalize(hist_1_L, hist_1_L, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist_1_A, hist_1_A, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist_1_B, hist_1_B, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist_2_L, hist_2_L, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist_2_A, hist_2_A, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist_2_B, hist_2_B, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

    # Compare histograms using Bhattacharyya distance
    dist_L = cv2.compareHist(hist_1_L, hist_2_L, cv2.HISTCMP_BHATTACHARYYA)
    dist_A = cv2.compareHist(hist_1_A, hist_2_A, cv2.HISTCMP_BHATTACHARYYA)
    dist_B = cv2.compareHist(hist_1_B, hist_2_B, cv2.HISTCMP_BHATTACHARYYA)

    # Return the average distance or individual distances
    return (dist_L, dist_A, dist_B)

def match_tones(reference_img, target_paths, output_dir, hist_bins=16, hist_range=[0, 256], threshold=0.1):
    if not os.path.isfile(reference_img):
        print(f"Error: Reference image not found at {reference_img}", file=sys.stderr)
        return False

    ref_img = cv2.imread(reference_img)
    ref_lab = cv2.cvtColor(ref_img, cv2.COLOR_BGR2LAB)

    # Calculate CDFs for reference image
    ref_hist_L = cv2.calcHist([ref_lab], [0], None, [hist_bins], hist_range)
    ref_hist_A = cv2.calcHist([ref_lab], [1], None, [hist_bins], hist_range)
    ref_hist_B = cv2.calcHist([ref_lab], [2], None, [hist_bins], hist_range)

    ref_cdf_L = ref_hist_L.cumsum()
    ref_cdf_A = ref_hist_A.cumsum()
    ref_cdf_B = ref_hist_B.cumsum()

    # Normalize CDFs, handling potential division by zero
    ref_cdf_L = ref_cdf_L / (ref_cdf_L.max() if ref_cdf_L.max() > 0 else 1)
    ref_cdf_A = ref_cdf_A / (ref_cdf_A.max() if ref_cdf_A.max() > 0 else 1)
    ref_cdf_B = ref_cdf_B / (ref_cdf_B.max() if ref_cdf_B.max() > 0 else 1)
    
    skipped_img = []

    for target_path in target_paths:
        if not os.path.isfile(target_path):
            print(f"Error: Target image not found at {target_path}", file=sys.stderr)
            skipped_img.append(target_path)
        else:
            # Use compare_tones to check tone similarity
            dist_L, dist_A, dist_B = compare_tones(reference_img, target_path, hist_bins, hist_range)
            avg_dist = (dist_L + dist_A + dist_B) / 3

            if avg_dist < threshold:
                print(f"Skipping {target_path} as tones are already similar (average distance: {avg_dist:.4f})", file=sys.stderr)
                skipped_img.append(target_path)
            else:
                # Apply histogram matching logic if tones are dissimilar
                target_img = cv2.imread(target_path)
                target_lab = cv2.cvtColor(target_img, cv2.COLOR_BGR2LAB)

                # Calculate CDFs for target image
                target_hist_L = cv2.calcHist([target_lab], [0], None, [hist_bins], hist_range)
                target_hist_A = cv2.calcHist([target_lab], [1], None, [hist_bins], hist_range)
                target_hist_B = cv2.calcHist([target_lab], [2], None, [hist_bins], hist_range)

                target_cdf_L = target_hist_L.cumsum()
                target_cdf_A = target_hist_A.cumsum()
                target_cdf_B = target_hist_B.cumsum()

                # Normalize CDFs, handling potential division by zero
                target_cdf_L = target_cdf_L / (target_cdf_L.max() if target_cdf_L.max() > 0 else 1)
                target_cdf_A = target_cdf_A / (target_cdf_A.max() if target_cdf_A.max() > 0 else 1)
                target_cdf_B = target_cdf_B / (target_cdf_B.max() if target_cdf_B.max() > 0 else 1)

                # Create inverse CDFs for the reference image (mapping from CDF value to intensity)
                # Ensure unique and monotonically increasing values for interp1d
                unique_ref_cdf_L, unique_indices_L = np.unique(ref_cdf_L, return_index=True)
                unique_ref_cdf_A, unique_indices_A = np.unique(ref_cdf_A, return_index=True)
                unique_ref_cdf_B, unique_indices_B = np.unique(ref_cdf_B, return_index=True)

                interp_ref_L = interp1d(unique_ref_cdf_L, np.arange(hist_bins)[unique_indices_L], bounds_error=False, fill_value=(0, hist_bins - 1))
                interp_ref_A = interp1d(unique_ref_cdf_A, np.arange(hist_bins)[unique_indices_A], bounds_error=False, fill_value=(0, hist_bins - 1))
                interp_ref_B = interp1d(unique_ref_cdf_B, np.arange(hist_bins)[unique_indices_B], bounds_error=False, fill_value=(0, hist_bins - 1))

                # Apply the transformation: new_pixel_value = inverse_ref_cdf(target_cdf(original_pixel_value))
                # Map target image pixel values to their CDF values
                target_pixels_L_cdf = target_cdf_L[target_lab[:,:,0].flatten()]
                target_pixels_A_cdf = target_cdf_A[target_lab[:,:,1].flatten()]
                target_pixels_B_cdf = target_cdf_B[target_lab[:,:,2].flatten()]

                # Apply the inverse reference CDF to these target CDF values
                matched_L = interp_ref_L(np.clip(target_pixels_L_cdf, 0, 1)).reshape(target_lab[:,:,0].shape)
                matched_A = interp_ref_A(np.clip(target_pixels_A_cdf, 0, 1)).reshape(target_lab[:,:,1].shape)
                matched_B = interp_ref_B(np.clip(target_pixels_B_cdf, 0, 1)).reshape(target_lab[:,:,2].shape)

                # Handle potential NaN values and clip to valid range before casting to uint8
                matched_L = np.nan_to_num(matched_L, nan=0.0).clip(0, 255)
                matched_A = np.nan_to_num(matched_A, nan=0.0).clip(0, 255)
                matched_B = np.nan_to_num(matched_B, nan=0.0).clip(0, 255)

                matched_lab = np.stack([matched_L, matched_A, matched_B], axis=-1).astype(np.uint8)
                adjusted_img = cv2.cvtColor(matched_lab, cv2.COLOR_LAB2BGR)
                
                output_path = f"{output_dir}/{os.path.basename(target_path)}"
                os.makedirs(output_dir, exist_ok=True) # Ensure output directory exists
                cv2.imwrite(output_path, adjusted_img)
                print(f"Processed and saved {target_path} to {output_path}")
                dist_L, dist_A, dist_B = compare_tones(reference_img,output_path)
                avg_dist = (dist_L + dist_A + dist_B) / 3
                if avg_dist < threshold:
                    print(f"Processed and saved {target_path} to {output_path}")
                else:
                    print(f"Processed image still not similar:\n dist_L:{dist_L}, dist_A:{dist_A}, dist_B:{dist_B}")

    print("Processing complete.")
    if skipped_img:
        print(f"Skipped target images:\n{skipped_img}")



reference_image = "D:/Data/DGH/Videos/2025-06-26 7D Marathon/video_previews/sampled_frames/frame_000.png"
dataset_folder = get_eligible_dataset(dlcDatasetFolder)[0]
target_images = [os.path.join(dataset_folder,"img00000040.png")]
output_directory = os.path.join(dataset_folder,"adjusted_images")

os.makedirs(output_directory, exist_ok=True)

match_tones(reference_image, target_images, output_directory)


# a1 = "D:/Data/DGH/Videos/2025-06-26 7D Marathon/video_previews/sampled_frames/frame_000.png"
# b1 = "D:/Data/DGH/Videos/2025-06-26 7D Marathon/video_previews/sampled_frames2/frame_000.png"
# # dataset_folder = get_eligible_dataset(dlcDatasetFolder)[0]
# # b1 = os.path.join(dataset_folder,"adjusted_images","img00000040.png")
# print(compare_tones(a1,b1))