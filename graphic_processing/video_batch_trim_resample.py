import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd # Keep pandas import if you might re-integrate CSV later, otherwise optional

# --- Helper Functions ---

def get_video_metadata(input_path):
    """Gets frame rate and optionally total frames using ffprobe."""
    try:
        probe_command = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=r_frame_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1', input_path
        ]
        probe_result = subprocess.run(probe_command, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        probe_output_lines = probe_result.stdout.strip().split('\n')

        frame_rate_str = probe_output_lines[0]
        num, den = map(int, frame_rate_str.split('/'))
        frame_rate = num / den

        return frame_rate

    except subprocess.CalledProcessError as e:
        print(f"Error probing {os.path.basename(input_path)}: {e}")
        stderr_output = e.stderr.decode(errors='ignore') if e.stderr else "No stderr output."
        print(f"  FFprobe Error Output:\n{stderr_output}")
        return None, None
    except (ValueError, IndexError) as e:
        print(f"Error parsing metadata for {os.path.basename(input_path)}. Check if video is valid. Probe output: '{probe_result.stdout.strip()}'. Error: {e}")
        return None, None
    except FileNotFoundError:
        messagebox.showerror("Error", "ffprobe not found. Make sure FFmpeg (which includes ffprobe) is installed and in your system's PATH.")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred probing {os.path.basename(input_path)}: {e}")
        return None, None


def cut_video(input_path, output_path, start_frame, end_frame, frame_rate):
    """Cuts a single video to a specified frame range using stream copy."""
    try:
        start_time = start_frame / frame_rate
        duration = (end_frame - start_frame) / frame_rate

        if duration <= 0:
            print(f"Warning: Calculated duration is zero or negative for {os.path.basename(input_path)}. Skipping cut.")
            return False

        ffmpeg_command = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-i', input_path,
            '-t', str(duration),
            '-c', 'copy', # Stream copy for cutting
            output_path
        ]

        subprocess.run(ffmpeg_command, check=True, creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Cut: {os.path.basename(input_path)} (frames {start_frame}-{end_frame}) -> {os.path.basename(output_path)}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error cutting {os.path.basename(input_path)}: {e}")
        stderr_output = e.stderr.decode(errors='ignore') if e.stderr else "No stderr output."
        print(f"  FFmpeg Error Output:\n{stderr_output}")
        return False
    except FileNotFoundError:
        messagebox.showerror("Error", "ffmpeg not found. Make sure FFmpeg is installed and in your system's PATH.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred cutting {os.path.basename(input_path)}: {e}")
        return False


def resample_video(input_path, output_path, target_fps):
    """Resamples a single video to a target FPS."""
    try:
        ffmpeg_command = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-filter:v', f'fps={target_fps}', # Resample filter
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-preset', 'superfast',
            '-crf', '23',
            '-c:a', 'copy', # Copy audio stream without re-encoding
            output_path
        ]

        subprocess.run(ffmpeg_command, check=True, creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Resampled: {os.path.basename(input_path)} (to {target_fps} fps) -> {os.path.basename(output_path)}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error resampling {os.path.basename(input_path)}: {e}")
        stderr_output = e.stderr.decode(errors='ignore') if e.stderr else "No stderr output."
        print(f"  FFmpeg Error Output:\n{stderr_output}")
        return False
    except FileNotFoundError:
        messagebox.showerror("Error", "ffmpeg not found. Make sure FFmpeg is installed and in your system's PATH.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred resampling {os.path.basename(input_path)}: {e}")
        return False


# --- Main Processing Function (Orchestrator) ---

def process_videos_batch(input_folder, output_folder, output_suffix="-processed.mp4",
                         start_frame=1, end_frame=30000, target_fps=50,
                         resample_only=False, cut_only=False, progress_callback=None):
    """
    Processes videos in a batch, optionally cutting and/or resampling.

    Args:
        input_folder (str): Path to the folder containing input videos.
        output_folder (str): Path to the folder to save output videos.
        output_suffix (str): Suffix to add to the processed output filenames.
        start_frame (int): The starting frame number for the cut (1-based).
        end_frame (int): The ending frame number for the cut (1-based).
        target_fps (int): The target frames per second for resampling.
        resample_only (bool): If True, only resample the entire video.
        cut_only (bool): If True, only cut the video using stream copy.
        progress_callback (function, optional): Function to call with progress updates.

    Returns:
        tuple: (processed_count, skipped_count, error_count)
    """
    if not input_folder or not output_folder:
        print("Error: Input and Output folders must be specified.")
        return (0, 0, 0)

    if not os.path.exists(output_folder):
        try:
            os.makedirs(output_folder)
        except OSError as e:
            print(f"Error: Could not create output folder: {output_folder}\n{e}")
            raise

    print(f"--- Starting Batch Process ---")
    print(f"Input Folder: {input_folder}")
    print(f"Output Folder: {output_folder}")
    if resample_only and not cut_only:
        print(f"Mode: Resample Only")
        print(f"Target FPS: {target_fps}")
    elif cut_only and not resample_only:
        print(f"Mode: Cut Only")
        print(f"Cut Frames: {start_frame} to {end_frame}")
    elif not resample_only and not cut_only:
        print(f"Mode: Cut and Resample")
        print(f"Cut Frames: {start_frame} to {end_frame}")
        print(f"Target FPS: {target_fps}")
    else:
        print("Error: Invalid mode selection. Please select 'Resample Only', 'Cut Only', or neither.")
        return (0, 0, 0)

    print("-" * 20)

    processed_count = 0
    skipped_count = 0
    error_count = 0

    try:
        video_files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))]
    except FileNotFoundError:
        print(f"Error: Input folder not found: {input_folder}")
        raise
    except Exception as e:
        print(f"Error listing files in input folder: {e}")
        raise

    total_files = len(video_files)
    if total_files == 0:
        print("No video files found in the input folder.")
        if progress_callback: progress_callback(0, 0, "No video files found.")
        return (0, 0, 0)


    for i, filename in enumerate(video_files):
        input_path = os.path.join(input_folder, filename)
        output_filename = os.path.splitext(filename)[0] + output_suffix
        output_path = os.path.join(output_folder, output_filename)

        if progress_callback:
            progress_callback(i, total_files, f"Processing: {filename}")

        try:
            frame_rate, total_frames = get_video_metadata(input_path, get_frames=not resample_only)

            if frame_rate is None:
                 error_count += 1
                 continue # Skip if metadata could not be retrieved

            if frame_rate <= 0:
                 print(f"Warning: Invalid frame rate ({frame_rate}) detected for {filename}. Skipping.")
                 skipped_count += 1
                 continue

            # Determine intermediate and final output paths
            intermediate_path = None
            final_output_path = output_path

            if not resample_only and not cut_only:
                # Cut and Resample mode: Cut first, then resample the cut video
                intermediate_filename = "temp_" + filename
                intermediate_path = os.path.join(output_folder, intermediate_filename)
                if cut_video(input_path, intermediate_path, start_frame, end_frame, frame_rate):
                    # If cutting was successful, now resample the intermediate file
                    if resample_video(intermediate_path, final_output_path, target_fps):
                        processed_count += 1
                    else:
                        error_count += 1 # Resampling failed
                else:
                    error_count += 1 # Cutting failed

            elif cut_only:
                # Cut Only mode: Just cut the video
                if cut_video(input_path, final_output_path, start_frame, end_frame, frame_rate):
                    processed_count += 1
                else:
                    error_count += 1 # Cutting failed

            elif resample_only:
                # Resample Only mode: Just resample the video
                 if resample_video(input_path, final_output_path, target_fps):
                     processed_count += 1
                 else:
                     error_count += 1 # Resampling failed


        except Exception as e:
            print(f"An unexpected error occurred processing {filename}: {e}")
            error_count += 1
        finally:
            # Clean up intermediate file if it exists
            if intermediate_path and os.path.exists(intermediate_path):
                try:
                    os.remove(intermediate_path)
                except OSError as e:
                    print(f"Warning: Could not remove intermediate file {intermediate_path}: {e}")


    if progress_callback:
        progress_callback(total_files, total_files, "Finished.")

    print("-" * 20)
    print(f"--- Processing Summary ---")
    print(f"Successfully processed: {processed_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Errors: {error_count}")
    print("-" * 20)
    # Summary messagebox shown by the GUI caller

    return (processed_count, skipped_count, error_count)


# --- GUI Setup ---
class App:
    def __init__(self, master):
        self.master = master
        master.title("Batch Video Cut and Resample")
        master.geometry("600x400") # Adjusted size

        # --- Variables ---
        self.input_folder = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.start_frame = tk.IntVar(value=1)
        self.end_frame = tk.IntVar(value=30000)
        self.target_fps = tk.IntVar(value=50)
        self.resample_only = tk.BooleanVar(value=False)
        self.cut_only = tk.BooleanVar(value=False)

        # --- Layout Frames ---
        top_frame = tk.Frame(master, padx=10, pady=10)
        top_frame.pack(fill=tk.X)

        param_frame = tk.LabelFrame(master, text="Processing Parameters", padx=10, pady=10)
        param_frame.pack(fill=tk.X, padx=10, pady=5)

        action_frame = tk.Frame(master, padx=10, pady=10)
        action_frame.pack(fill=tk.X, side=tk.BOTTOM) # Place at bottom

        # --- Top Frame Widgets (Folders) ---
        tk.Label(top_frame, text="Input Folder:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.input_entry = tk.Entry(top_frame, textvariable=self.input_folder, width=50)
        self.input_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(top_frame, text="Browse...", command=self.select_input).grid(row=0, column=2, padx=5, pady=5)

        tk.Label(top_frame, text="Output Folder:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.output_entry = tk.Entry(top_frame, textvariable=self.output_folder, width=50)
        self.output_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(top_frame, text="Browse...", command=self.select_output).grid(row=1, column=2, padx=5, pady=5)

        top_frame.grid_columnconfigure(1, weight=1) # Allow entry to expand

        # --- Parameter Frame Widgets ---
        # Mode Selection Checkboxes
        self.resample_only_check = tk.Checkbutton(param_frame, text="Resample Only (Ignore Cut Frames)",
                                                  variable=self.resample_only, command=self.update_mode_fields)
        self.resample_only_check.grid(row=0, column=0, columnspan=2, pady=(0, 5), sticky="w")

        self.cut_only_check = tk.Checkbutton(param_frame, text="Cut Only (Ignore Resample & Re-encode)",
                                             variable=self.cut_only, command=self.update_mode_fields)
        self.cut_only_check.grid(row=0, column=2, columnspan=2, pady=(0, 5), sticky="w")


        # Cut Frame Parameters (conditionally enabled)
        self.start_frame_label = tk.Label(param_frame, text="Start Frame:")
        self.start_frame_label.grid(row=1, column=0, padx=5, pady=2, sticky="e")
        self.start_frame_entry = tk.Entry(param_frame, textvariable=self.start_frame, width=10)
        self.start_frame_entry.grid(row=1, column=1, padx=5, pady=2, sticky="w")

        self.end_frame_label = tk.Label(param_frame, text="End Frame:")
        self.end_frame_label.grid(row=1, column=2, padx=5, pady=2, sticky="e")
        self.end_frame_entry = tk.Entry(param_frame, textvariable=self.end_frame, width=10)
        self.end_frame_entry.grid(row=1, column=3, padx=5, pady=2, sticky="w")

        # Target FPS
        self.fps_label = tk.Label(param_frame, text="Target FPS:")
        self.fps_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.fps_entry = tk.Entry(param_frame, textvariable=self.target_fps, width=10)
        self.fps_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        # --- Action Frame Widgets ---
        self.run_button = tk.Button(action_frame, text="Run Processing", command=self.run_processing, width=15, height=2)
        self.run_button.pack(side=tk.RIGHT, padx=5)

        # Progress Bar and Label
        self.progress_label = tk.Label(action_frame, text="")
        self.progress_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.progress_bar = ttk.Progressbar(action_frame, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Initial state for mode fields
        self.update_mode_fields()

    def update_mode_fields(self):
        """Enable/disable input fields based on selected mode."""
        resample_only = self.resample_only.get()
        cut_only = self.cut_only.get()

        # Disable frame inputs if Resample Only is selected
        frame_state = tk.DISABLED if resample_only else tk.NORMAL
        self.start_frame_entry.config(state=frame_state)
        self.end_frame_entry.config(state=frame_state)
        self.start_frame_label.config(state=frame_state)
        self.end_frame_label.config(state=frame_state)

        # Disable FPS input if Cut Only is selected
        fps_state = tk.DISABLED if cut_only else tk.NORMAL
        self.fps_entry.config(state=fps_state)
        self.fps_label.config(state=fps_state)


    def select_input(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.input_folder.set(folder_selected)

    def select_output(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.output_folder.set(folder_selected)

    def _get_int_param(self, tk_var, name, allow_negative=False):
        """Helper to get integer parameter with validation."""
        try:
            val = tk_var.get()
            if not allow_negative and val < 0:
                raise ValueError(f"{name} cannot be negative.")
            return val
        except tk.TclError:
            raise ValueError(f"Invalid integer value for {name}.")
        except ValueError as e:
             raise ValueError(f"Invalid value for {name}: {e}")

    def update_progress(self, current, total, message=""):
        """Callback function to update progress indicators."""
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar['value'] = percent # Use the progress bar
            self.progress_label['text'] = f"{message} ({current}/{total}) {percent}%"
        else:
            self.progress_bar['value'] = 0 # Reset progress bar
            self.progress_label['text'] = message
        self.master.update_idletasks() # Force GUI update

    def run_processing(self):
        in_folder = self.input_folder.get()
        out_folder = self.output_folder.get()
        res_only = self.resample_only.get()
        cut_only = self.cut_only.get()

        if not in_folder or not out_folder:
            messagebox.showerror("Error", "Please select both Input and Output folders.")
            return

        if res_only and cut_only:
             messagebox.showerror("Error", "Please select either 'Resample Only' or 'Cut Only', not both.")
             return

        try:
            # Get parameters from the GUI using helper
            s_frame = 0
            e_frame = 0
            if not res_only: # Only get frame numbers if cutting
                s_frame = self._get_int_param(self.start_frame, "Start Frame", allow_negative=True) # Allow negative initially, checked in function
                e_frame = self._get_int_param(self.end_frame, "End Frame")
                if e_frame <= s_frame:
                    raise ValueError("End Frame must be greater than Start Frame.")

            t_fps = self._get_int_param(self.target_fps, "Target FPS")
            if t_fps <= 0:
                 raise ValueError("Target FPS must be a positive integer.")

            # Disable button during processing
            self.run_button.config(state=tk.DISABLED, text="Processing...")
            self.update_progress(0, 0, "Starting...") # Initial progress update
            self.master.update_idletasks() # Ensure GUI updates

            # Run the main function with progress callback
            processed, skipped, errors = process_videos_batch( # Changed function name
                in_folder,
                out_folder,
                start_frame=s_frame,
                end_frame=e_frame,
                target_fps=t_fps,
                resample_only=res_only,
                cut_only=cut_only,
                progress_callback=self.update_progress
            )

            # Show summary message
            messagebox.showinfo("Complete", f"Processing finished.\n\nProcessed: {processed}\nSkipped: {skipped}\nErrors: {errors}\n\nCheck console for details.")

        except ValueError as e:
             messagebox.showerror("Invalid Input", f"Error in parameters: {e}")
             self.update_progress(0, 0, "Error.") # Update progress on error
        except FileNotFoundError as e: # Catch folder not found errors from core function
             messagebox.showerror("Error", f"Folder not found: {e}")
             self.update_progress(0, 0, "Error.")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
            print(f"Unexpected error during run_processing setup or execution: {e}") # Log details
            self.update_progress(0, 0, "Error.") # Update progress on error
        finally:
             # Re-enable button regardless of success or failure
            self.run_button.config(state=tk.NORMAL, text="Run Processing")
            self.master.after(3000, lambda: self.update_progress(0, 0, ""))


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()