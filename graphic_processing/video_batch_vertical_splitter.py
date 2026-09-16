import os
import subprocess
from tqdm import tqdm
import tkinter as tk
from tkinter import filedialog, messagebox

def run_ffmpeg(command, total_duration, desc):
    """Runs an FFmpeg command and updates a tqdm progress bar."""
    process = subprocess.Popen(
        command, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        universal_newlines=True, 
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    
    with tqdm(total=total_duration, unit="s", desc=desc) as pbar:
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
    
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, command)

def split_videos(input_folder, output_folder, upper_sub="upper", lower_sub="lower", recursive=False, progress_callback=None):
    """Splits videos into upper and lower halves using FFmpeg."""
    if not input_folder:
        messagebox.showerror("Error", "Input folder must be selected.")
        return (0, 0, 0)

    if not output_folder:
        output_folder = input_folder

    print(f"--- Starting Video Splitting ---")
    print(f"Input Folder: {input_folder}")
    print(f"Output Folder: {output_folder}")
    print(f"Upper Subfolder: {upper_sub}")
    print(f"Lower Subfolder: {lower_sub}")
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
                    video_files_to_process.append(os.path.join(root, f))
    else:
        try:
            for f in os.listdir(input_folder):
                if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    video_files_to_process.append(os.path.join(input_folder, f))
        except Exception as e:
            messagebox.showerror("Error", f"Could not read input folder:\n{input_folder}\n{e}")
            return (0, 0, 0)

    total_files = len(video_files_to_process)
    if total_files == 0:
        messagebox.showinfo("Info", "No video files found in the input folder(s).")
        if progress_callback: progress_callback(0, 0, "No video files found.")
        return (0, 0, 0)

    # Create output subfolders
    upper_dir = os.path.join(output_folder, upper_sub)
    lower_dir = os.path.join(output_folder, lower_sub)
    os.makedirs(upper_dir, exist_ok=True)
    os.makedirs(lower_dir, exist_ok=True)

    for i, input_path in enumerate(video_files_to_process):
        filename = os.path.basename(input_path)
        base, ext = os.path.splitext(filename)
        if not ext:
            ext = ".mp4"
        
        upper_output_path = os.path.join(upper_dir, f"{base}{ext}")
        lower_output_path = os.path.join(lower_dir, f"{base}{ext}")

        # Skip if both halves already exist
        if os.path.exists(upper_output_path) and os.path.exists(lower_output_path):
            print(f"Skipping (already exists): {filename}")
            skipped_count += 1
            continue

        if progress_callback:
            progress_callback(i, total_files, f"Processing: {filename}")

        try:
            # Get video duration for progress bar
            probe_command = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', input_path
            ]
            duration_result = subprocess.run(
                probe_command, capture_output=True, text=True, check=True, 
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            total_duration = float(duration_result.stdout.strip())

            # Process Upper Half
            if not os.path.exists(upper_output_path):
                # scale=iw:-2 ensures height is even to prevent h264_nvenc errors
                vf_upper = "hwdownload,format=nv12,crop=iw:ih/2:0:0,scale=iw:-2"
                cmd_upper = [
                    "ffmpeg", "-y", "-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
                    "-i", input_path, "-vf", vf_upper,
                    "-c:v", "h264_nvenc", "-preset", "p7", "-global_quality", "18", "-rc", "vbr_hq",
                    "-an", upper_output_path
                ]
                run_ffmpeg(cmd_upper, total_duration, f"Upper: {filename}")

            # Process Lower Half
            if not os.path.exists(lower_output_path):
                vf_lower = "hwdownload,format=nv12,crop=iw:ih/2:0:ih/2,scale=iw:-2"
                cmd_lower = [
                    "ffmpeg", "-y", "-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
                    "-i", input_path, "-vf", vf_lower,
                    "-c:v", "h264_nvenc", "-preset", "p7", "-global_quality", "18", "-rc", "vbr_hq",
                    "-an", lower_output_path
                ]
                run_ffmpeg(cmd_lower, total_duration, f"Lower: {filename}")

            print(f"Processed: {filename}")
            processed_count += 1

        except subprocess.CalledProcessError as e:
            print(f"Error processing {filename}: {e}")
            error_count += 1
        except FileNotFoundError as e:
            tool_name = 'ffprobe' if 'ffprobe' in str(e) else 'ffmpeg'
            messagebox.showerror("Error", f"{tool_name} not found. Make sure FFmpeg is installed and in your system's PATH.")
            remaining_files = total_files - i
            error_count += remaining_files
            if progress_callback: progress_callback(i, total_files, f"{tool_name} not found. Aborting.")
            return (processed_count, skipped_count, error_count)
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
        master.title("Batch Video Splitter (Upper/Lower)")
        master.geometry("500x300")

        self.input_folder = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.upper_sub = tk.StringVar(value="upper")
        self.lower_sub = tk.StringVar(value="lower")
        self.recursive_search = tk.BooleanVar(value=True)

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

        tk.Label(top_frame, text="Output Folder:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.output_entry = tk.Entry(top_frame, textvariable=self.output_folder, width=40)
        self.output_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(top_frame, text="Browse...", command=self.select_output).grid(row=1, column=2, padx=5, pady=5)

        top_frame.grid_columnconfigure(1, weight=1)

        # --- Parameter Frame Widgets ---
        param_frame.grid_columnconfigure(1, weight=1)

        tk.Label(param_frame, text="Upper Subfolder:").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        tk.Entry(param_frame, textvariable=self.upper_sub, width=15).grid(row=0, column=1, padx=5, pady=2, sticky="w")

        tk.Label(param_frame, text="Lower Subfolder:").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        tk.Entry(param_frame, textvariable=self.lower_sub, width=15).grid(row=1, column=1, padx=5, pady=2, sticky="w")

        tk.Checkbutton(param_frame, text="Include Subfolders (Recursive Search)", variable=self.recursive_search).grid(row=2, column=0, columnspan=2, padx=5, pady=(10,0), sticky="w")

        # --- Action Frame Widgets ---
        self.run_button = tk.Button(action_frame, text="Run Splitting", command=self.run_processing, width=45, height=2, bg="#4CAF50", fg="white", font=("Arial", 18, "bold"))
        self.run_button.pack(side=tk.RIGHT, padx=5)

        self.progress_label = tk.Label(action_frame, text="")
        self.progress_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    def select_input(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.input_folder.set(folder_selected)
            # Auto-fill output folder if it's empty
            if not self.output_folder.get():
                self.output_folder.set(folder_selected)

    def select_output(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.output_folder.set(folder_selected)

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
        output_f = self.output_folder.get()
        upper_s = self.upper_sub.get()
        lower_s = self.lower_sub.get()
        recursive_val = self.recursive_search.get()

        if not input_f:
            messagebox.showerror("Input Error", "Please select an input folder.")
            return
            
        if not output_f:
            output_f = input_f

        self.run_button.config(state=tk.DISABLED)
        self.update_progress(0, 0, "Starting...")

        try:
            processed, skipped, errors = split_videos(
                input_f, output_f, upper_s, lower_s, recursive_val,
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