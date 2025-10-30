import os
import subprocess

from tqdm import tqdm

import tkinter as tk
from tkinter import filedialog, messagebox

def preprocess_videos(input_folder, target_width, target_height, fps, output_suffix="-proc.mp4", recursive=False, use_original_dims=False, progress_callback=None):
    """Preprocesses videos (resizes and converts) using FFmpeg."""
    if not input_folder:
        messagebox.showerror("Error", "Input folder must be selected.")
        return (0, 0, 0)

    ffmpeg_found = True
    ffprobe_found = True

    print(f"--- Starting Batch Preprocessing ---")
    print(f"Input Folder: {input_folder}")
    print(f"Target Size (W x H): {target_width} x {target_height} (Using original dimensions: {use_original_dims})")
    print(f"Output Suffix: {output_suffix}")
    print(f"Recursive Search: {recursive}")
    print("-" * 20)

    processed_count = 0
    skipped_count = 0
    error_count = 0

    video_files_to_process = []
    if recursive:
        for root, _, files in os.walk(input_folder):
            for f in files:
                if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    if output_suffix in f:
                        continue
                    video_files_to_process.append(os.path.join(root, f))
    else:
        try:
            for f in os.listdir(input_folder):
                if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    if output_suffix in f:
                        continue
                    video_files_to_process.append(os.path.join(input_folder, f))
        except FileNotFoundError:
            messagebox.showerror("Error", f"Input folder not found:\n{input_folder}")
            return (0,0,0)
        except Exception as e:
            messagebox.showerror("Error", f"Could not read input folder:\n{input_folder}\n{e}")
            return (0,0,0)

    total_files = len(video_files_to_process)
    if total_files == 0:
        messagebox.showinfo("Info", "No video files found in the input folder(s).")
        if progress_callback: progress_callback(0, 0, "No video files found.")
        return (0, 0, 0)

    for i, input_path in enumerate(video_files_to_process):
        input_dir = os.path.dirname(input_path)
        filename = os.path.basename(input_path)
        base, ext = os.path.splitext(filename)
        output_filename = base + output_suffix + (ext if not output_suffix.endswith(('.mp4', '.avi', '.mov', '.mkv')) else '')
        if not os.path.splitext(output_filename)[1]:
             output_filename += ".mp4"
        output_path = os.path.join(input_dir, output_filename)

        if progress_callback:
            progress_callback(i, total_files, f"Processing, check terminal for detail: {filename}")

        try:
            probe_command = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', input_path
            ]
            duration_result = subprocess.run(probe_command, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            total_duration = float(duration_result.stdout.strip())

            # Build video filter chain
            if use_original_dims:
                vf_filter = "hwdownload,format=nv12,fps={fps},hwupload_cuda"
            else:
                vf_filter = f"hwdownload,format=nv12,scale={target_width}:{target_height},fps={fps},hwupload_cuda"

            ffmpeg_command = [
                "ffmpeg", "-y",
                "-hwaccel", "cuda",
                "-hwaccel_output_format", "cuda",
                "-i", input_path,
                "-vf", vf_filter,
                "-c:v", "h264_nvenc",
                "-preset", "p7",
                "-global_quality", "18",
                "-rc", "vbr_hq",
                "-an",
                output_path
            ]
            process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, creationflags=subprocess.CREATE_NO_WINDOW)

            with tqdm(total=total_duration, unit="s", desc=f"Processing: {filename}") as pbar:
                for line in process.stdout:
                    if "time=" in line:
                        try:
                            time_str = line.split("time=")[1].split(" ")[0]
                            h, m, s = map(float, time_str.split(':'))
                            current_time_seconds = h * 3600 + m * 60 + s
                            pbar.update(current_time_seconds - pbar.n)
                        except (IndexError, ValueError):
                            pass
            process.wait()

            print(f"Processed: {filename} -> {output_filename}")
            processed_count += 1

        except subprocess.CalledProcessError as e:
            print(f"Error processing {filename}: {e}")
            if e.cmd and e.cmd[0] == 'ffprobe' and not ffprobe_found: pass
            elif e.cmd and e.cmd[0] == 'ffmpeg' and not ffmpeg_found: pass
            else:
                print(f"  Command failed: {' '.join(e.cmd)}")
                if e.stderr: print(f"  FFmpeg/FFprobe Error Output:\n{e.stderr.decode(errors='ignore')}")
            error_count += 1
        except FileNotFoundError as e:
            tool_name = 'ffprobe' if 'ffprobe' in str(e) else 'ffmpeg'
            if (tool_name == 'ffprobe' and ffprobe_found) or (tool_name == 'ffmpeg' and ffmpeg_found):
                 messagebox.showerror("Error", f"{tool_name} not found. Make sure FFmpeg (which includes ffprobe) is installed and in your system's PATH.")
                 if tool_name == 'ffprobe': ffprobe_found = False
                 if tool_name == 'ffmpeg': ffmpeg_found = False
                 remaining_files = total_files - i
                 error_count += remaining_files
                 if progress_callback: progress_callback(i, total_files, f"{tool_name} not found. Aborting.")
                 return (processed_count, skipped_count, error_count)
            elif ffprobe_found and ffmpeg_found:
                 print(f"Error: File not found during processing of {filename}: {e}")
                 error_count += 1
        except ValueError as e:
             print(f"Error parsing dimensions for {filename}. Error: {e}")
             error_count += 1
        except Exception as e:
            print(f"An unexpected error occurred processing {filename}: {e}")
            error_count += 1

    if progress_callback:
        progress_callback(total_files, total_files, "Finished.")

    print("-" * 20)
    print(f"--- Processing Summary ---")
    print(f"Successfully processed: {processed_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Errors: {error_count}")
    print("-" * 20)
    return (processed_count, skipped_count, error_count)

# --- GUI Setup ---
class App:
    def __init__(self, master):
        self.master = master
        master.title("Batch Video Preprocessor")
        master.geometry("500x500")

        self.input_folder = tk.StringVar()
        self.target_width = tk.IntVar(value=640)
        self.target_height = tk.IntVar(value=480)
        self.output_suffix = tk.StringVar(value="-proc.mp4")
        self.fps = tk.DoubleVar(value=20.0)
        self.recursive_search = tk.BooleanVar(value=True)
        self.use_original_dims = tk.BooleanVar(value=False)

        # --- Layout Frames ---
        top_frame = tk.Frame(master, padx=5, pady=5)
        top_frame.pack(fill=tk.X)

        param_frame = tk.LabelFrame(master, text="Processing Parameters", padx=10, pady=10)
        param_frame.pack(fill=tk.X, padx=5, pady=5)

        action_frame = tk.Frame(master, padx=5, pady=10)
        action_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # --- Top Frame Widgets (Folders) ---
        tk.Label(top_frame, text="Input Folder:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.input_entry = tk.Entry(top_frame, textvariable=self.input_folder, width=40)
        self.input_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(top_frame, text="Browse...", command=self.select_input).grid(row=0, column=2, padx=5, pady=5)

        top_frame.grid_columnconfigure(1, weight=1)

        # --- Parameter Frame Widgets ---
        param_frame.grid_columnconfigure(1, weight=1)

        tk.Label(param_frame, text="Target Width:").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        tk.Entry(param_frame, textvariable=self.target_width, width=7).grid(row=0, column=1, padx=5, pady=2, sticky="w")

        tk.Label(param_frame, text="Target Height:").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        tk.Entry(param_frame, textvariable=self.target_height, width=7).grid(row=1, column=1, padx=5, pady=2, sticky="w")

        tk.Label(param_frame, text="Output Suffix:").grid(row=2, column=0, padx=5, pady=2, sticky="e")
        tk.Entry(param_frame, textvariable=self.output_suffix, width=15).grid(row=2, column=1, padx=5, pady=2, sticky="w")

        tk.Label(param_frame, text="Output FPS:").grid(row=3, column=0, padx=5, pady=2, sticky="e")
        tk.Entry(param_frame, textvariable=self.fps, width=10).grid(row=3, column=1, padx=5, pady=2, sticky="w")

        tk.Checkbutton(param_frame, text="Include Subfolders (Recursive Search)", variable=self.recursive_search).grid(row=4, column=0, columnspan=2, padx=5, pady=(10,0), sticky="w")
        tk.Checkbutton(param_frame, text="Use Original Dimensions (No Resizing)", variable=self.use_original_dims).grid(row=5, column=0, columnspan=2, padx=5, pady=(5,0), sticky="w")

        # --- Action Frame Widgets ---
        self.run_button = tk.Button(action_frame, text="Run Preprocessing", command=self.run_processing, width=20, height=2)
        self.run_button.pack(side=tk.RIGHT, padx=5)

        self.progress_label = tk.Label(action_frame, text="")
        self.progress_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    def select_input(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.input_folder.set(folder_selected)

    def _get_int_param(self, tk_var, name):
        """Helper to get integer parameter with validation."""
        try:
            val = tk_var.get()
            if val < 0:
                raise ValueError(f"{name} cannot be negative.")
            return val
        except tk.TclError:
            pass
        except ValueError as e:
            raise ValueError(f"Invalid value for {name}: {e}")

    def update_progress(self, current, total, message=""):
        """Updates the progress label in the GUI."""
        if total > 0:
            progress_percent = (current / total) * 100
            self.progress_label.config(text=f"Progress: {current}/{total} ({progress_percent:.1f}%) - {message}")
        else:
            self.progress_label.config(text=f"Progress: {message}")
        self.master.update_idletasks()

    def run_processing(self):
        input_f = self.input_folder.get()
        
        try:
            t_width = self._get_int_param(self.target_width, "Target Width")
            t_height = self._get_int_param(self.target_height, "Target Height")
            fps_val = self.fps.get()
            output_s = self.output_suffix.get()
            recursive_val = self.recursive_search.get()
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            return

        self.run_button.config(state=tk.DISABLED)
        self.update_progress(0, 0, "Starting...")

        try:
            processed, skipped, errors = preprocess_videos(
                input_f, t_width, t_height, fps_val, output_s, recursive_val,
                use_original_dims=self.use_original_dims.get(),
                progress_callback=self.update_progress
            )
            messagebox.showinfo("Processing Complete",
                                f"Successfully processed: {processed}\nSkipped: {skipped}\nErrors: {errors}")
        except Exception as e:
            messagebox.showerror("Processing Error", f"An unexpected error occurred during processing:\n{e}")
            print(f"Unexpected error in run_processing: {e}")
        finally:
            self.run_button.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()