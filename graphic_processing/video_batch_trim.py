import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

def get_video_metadata(input_path):
    """Gets frame rate using ffprobe."""
    try:
        probe_command = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=r_frame_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1', input_path
        ]
        probe_result = subprocess.run(probe_command, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        frame_rate_str = probe_result.stdout.strip()
        num, den = map(int, frame_rate_str.split('/'))
        frame_rate = num / den
        return frame_rate
    except (subprocess.CalledProcessError, ValueError, IndexError, FileNotFoundError, Exception) as e:
        print(f"Error probing {os.path.basename(input_path)}: {e}")
        if isinstance(e, FileNotFoundError):
            messagebox.showerror("Error", "ffprobe not found. Make sure FFmpeg is installed and in your system's PATH.")
        return None

def cut_video(input_path, output_path, start_frame, end_frame, frame_rate):
    """Cuts a single video to a specified 0-based frame range using stream copy."""
    try:
        start_time = start_frame / frame_rate
        duration = (end_frame - start_frame + 1) / frame_rate  # +1 because end_frame is inclusive

        if duration <= 0:
            print(f"Warning: Invalid frame range ({start_frame} to {end_frame}) for {os.path.basename(input_path)}. Skipping.")
            return False

        ffmpeg_command = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-i', input_path,
            '-t', str(duration),
            '-c', 'copy',
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

def process_videos_batch(input_folder, output_folder, output_suffix="_cut.mp4", start_frame=0, end_frame=29999, progress_callback=None):
    if not input_folder or not output_folder:
        print("Error: Input and Output folders must be specified.")
        return (0, 0, 0)

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    print(f"--- Starting Batch Cut ---")
    print(f"Input Folder: {input_folder}")
    print(f"Output Folder: {output_folder}")
    print(f"Cut Frames: {start_frame} to {end_frame}")
    print("-" * 30)

    processed_count = 0
    skipped_count = 0
    error_count = 0

    try:
        video_files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))]
    except Exception as e:
        print(f"Error listing files: {e}")
        raise

    total_files = len(video_files)
    if total_files == 0:
        print("No video files found.")
        if progress_callback:
            progress_callback(0, 0, "No video files found.")
        return (0, 0, 0)

    for i, filename in enumerate(video_files):
        input_path = os.path.join(input_folder, filename)
        output_filename = os.path.splitext(filename)[0] + output_suffix
        output_path = os.path.join(output_folder, output_filename)

        if progress_callback:
            progress_callback(i, total_files, f"Processing: {filename}")

        frame_rate = get_video_metadata(input_path)
        if frame_rate is None or frame_rate <= 0:
            error_count += 1
            continue

        if cut_video(input_path, output_path, start_frame, end_frame, frame_rate):
            processed_count += 1
        else:
            error_count += 1

    if progress_callback:
        progress_callback(total_files, total_files, "Finished.")

    print("-" * 30)
    print(f"--- Summary ---")
    print(f"Processed: {processed_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Errors: {error_count}")
    print("-" * 30)

    return (processed_count, skipped_count, error_count)

class App:
    def __init__(self, master):
        self.master = master
        master.title("Batch Video Cutter")
        master.geometry("600x300")

        # Variables
        self.input_folder = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.start_frame = tk.IntVar(value=0)
        self.end_frame = tk.IntVar(value=29999)

        # Layout
        top_frame = tk.Frame(master, padx=10, pady=10)
        top_frame.pack(fill=tk.X)

        param_frame = tk.LabelFrame(master, text="Cut Parameters", padx=10, pady=10)
        param_frame.pack(fill=tk.X, padx=10, pady=5)

        action_frame = tk.Frame(master, padx=10, pady=10)
        action_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Folder Selection
        tk.Label(top_frame, text="Input Folder:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        tk.Entry(top_frame, textvariable=self.input_folder, width=50).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(top_frame, text="Browse...", command=self.select_input).grid(row=0, column=2, padx=5, pady=5)

        tk.Label(top_frame, text="Output Folder:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        tk.Entry(top_frame, textvariable=self.output_folder, width=50).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(top_frame, text="Browse...", command=self.select_output).grid(row=1, column=2, padx=5, pady=5)

        top_frame.grid_columnconfigure(1, weight=1)

        # Frame Parameters
        tk.Label(param_frame, text="Start Frame:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(param_frame, textvariable=self.start_frame, width=10).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        tk.Label(param_frame, text="End Frame:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(param_frame, textvariable=self.end_frame, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # Action Button & Progress
        self.run_button = tk.Button(action_frame, text="Cut Videos", command=self.run_processing, width=15, height=2)
        self.run_button.pack(side=tk.RIGHT, padx=5)

        self.progress_label = tk.Label(action_frame, text="")
        self.progress_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.progress_bar = ttk.Progressbar(action_frame, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    def select_input(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_folder.set(folder)

    def select_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder.set(folder)

    def _get_int_param(self, var, name):
        try:
            val = var.get()
            if val < 0:
                raise ValueError(f"{name} must be >= 0.")
            return val
        except tk.TclError:
            raise ValueError(f"Invalid integer for {name}.")

    def update_progress(self, current, total, message=""):
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar['value'] = percent
            self.progress_label['text'] = f"{message} ({current}/{total}) {percent}%"
        else:
            self.progress_bar['value'] = 0
            self.progress_label['text'] = message
        self.master.update_idletasks()

    def run_processing(self):
        in_folder = self.input_folder.get()
        out_folder = self.output_folder.get()

        if not in_folder or not out_folder:
            messagebox.showerror("Error", "Please select both Input and Output folders.")
            return

        try:
            s_frame = self._get_int_param(self.start_frame, "Start Frame")
            e_frame = self._get_int_param(self.end_frame, "End Frame")
            if e_frame < s_frame:
                raise ValueError("End Frame must be >= Start Frame.")

            self.run_button.config(state=tk.DISABLED, text="Cutting...")
            self.update_progress(0, 0, "Starting...")

            processed, skipped, errors = process_videos_batch(
                in_folder, out_folder,
                start_frame=s_frame,
                end_frame=e_frame,
                progress_callback=self.update_progress
            )

            messagebox.showinfo("Complete", f"Processing finished.\n\nProcessed: {processed}\nSkipped: {skipped}\nErrors: {errors}")

        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")
            self.update_progress(0, 0, "Error.")
        finally:
            self.run_button.config(state=tk.NORMAL, text="Cut Videos")
            self.master.after(3000, lambda: self.update_progress(0, 0, ""))


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()