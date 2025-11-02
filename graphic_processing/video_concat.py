import os
import sys
import glob
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

def concat_videos_in_folder(input_dir, file_suffix=None, extensions=None):
    if extensions is None:
        extensions = ['mp4', 'mov', 'mkv', 'avi']
    
    files = []
    for ext in extensions:
        pattern = os.path.join(input_dir, f"*.{ext}")
        files.extend(glob.glob(pattern))
    
    if not files:
        return None  # No files to process

    files = [os.path.abspath(f) for f in files]
    files.sort()

    if file_suffix is not None:
        filtered_files = []
        for f in files:
            base = os.path.basename(f)
            name, _ = os.path.splitext(base)
            if name.endswith(file_suffix):
                filtered_files.append(f)
        files = filtered_files

    if not files:
        return None  # No files matched suffix

    # Determine output extension
    _, first_ext = os.path.splitext(files[0])
    output_ext = first_ext.lstrip('.').lower() or 'mp4'
    
    folder_name = os.path.basename(os.path.normpath(input_dir))
    parent_dir = os.path.dirname(os.path.normpath(input_dir))
    output_file = os.path.join(parent_dir, f"{folder_name}_combined.{output_ext}")

    list_file = os.path.join(os.getcwd(), 'concat_list.txt')
    try:
        with open(list_file, 'w', encoding='utf-8') as f:
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

        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return output_file

    except subprocess.CalledProcessError as e:
        stderr_msg = e.stderr.decode('utf-8', errors='replace') if e.stderr else "Unknown FFmpeg error"
        raise RuntimeError(f"FFmpeg failed in {input_dir}:\n{stderr_msg}")
    finally:
        if os.path.exists(list_file):
            try:
                os.remove(list_file)
            except Exception:
                pass


def get_folders_to_process(root_folder, recursive):
    if not recursive:
        return [root_folder]
    else:
        folders = []
        for root, _, _ in os.walk(root_folder):
            folders.append(root)
        return folders


def process_all_folders(prime_folder, file_suffix, recursive, progress_callback):
    if not os.path.isdir(prime_folder):
        raise ValueError("Input folder does not exist.")

    folders = get_folders_to_process(prime_folder, recursive)
    total = len(folders)
    success = 0
    error = 0

    for i, folder in enumerate(folders):
        try:
            msg = f"Processing: {os.path.relpath(folder, prime_folder) or '.'}"
            if progress_callback:
                progress_callback(i, total, msg)
            
            result = concat_videos_in_folder(folder, file_suffix=file_suffix)
            if result:
                success += 1
            # If no videos, silently skip (not an error)
        except Exception as e:
            print(f"Error in {folder}: {e}", file=sys.stderr)
            error += 1

    return success, error


class ConcatApp:
    def __init__(self, master):
        self.master = master
        master.title("Batch Video Concatenator")
        master.geometry("500x350")

        self.input_folder = tk.StringVar()
        self.file_suffix = tk.StringVar(value="-proc")
        self.recursive = tk.BooleanVar(value=False)

        # Layout
        main = tk.Frame(master, padx=15, pady=15)
        main.pack(fill=tk.BOTH, expand=True)

        # Input Folder
        tk.Label(main, text="Select Folder to Process:").grid(row=0, column=0, sticky="w", pady=(0,5))
        entry_frame = tk.Frame(main)
        entry_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0,10))
        tk.Entry(entry_frame, textvariable=self.input_folder, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(entry_frame, text="Browse...", command=self.browse).pack(side=tk.RIGHT, padx=(10,0))
        main.columnconfigure(0, weight=1)

        # Options
        opts = tk.LabelFrame(main, text="Processing Options", padx=10, pady=10)
        opts.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0,15))
        opts.columnconfigure(1, weight=1)

        tk.Label(opts, text="Filename Suffix Filter (e.g., -proc):").grid(row=0, column=0, sticky="e", padx=(0,10), pady=3)
        tk.Entry(opts, textvariable=self.file_suffix, width=20).grid(row=0, column=1, sticky="w", pady=3)

        tk.Checkbutton(opts, text="Include all subfolders (recursive)", variable=self.recursive).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8,0)
        )

        # Progress & Run
        self.status = tk.Label(main, text="Ready", anchor="w", fg="gray")
        self.status.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0,15))

        self.run_btn = tk.Button(main, text="Run Concatenation", command=self.run, width=45, height=2, bg="#4CAF50", fg="white", font=("Arial", 20, "bold"))
        self.run_btn.grid(row=4, column=0, columnspan=2)

    def browse(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_folder.set(folder)

    def update_status(self, current, total, msg):
        if total > 0:
            pct = (current / total) * 100
            self.status.config(text=f"[{current}/{total}] {msg} ({pct:.1f}%)", fg="black")
        else:
            self.status.config(text=msg, fg="black")
        self.master.update_idletasks()

    def run(self):
        folder = self.input_folder.get().strip()
        suffix = self.file_suffix.get().strip() or None
        recursive = self.recursive.get()

        if not folder:
            messagebox.showerror("Error", "Please select a folder.")
            return

        if not os.path.isdir(folder):
            messagebox.showerror("Error", "Selected folder does not exist.")
            return

        # Check FFmpeg
        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except FileNotFoundError:
            messagebox.showerror("Error", "FFmpeg not found! Install FFmpeg and add to PATH.")
            return

        self.run_btn.config(state=tk.DISABLED)
        self.update_status(0, 0, "Starting...")

        try:
            success, error = process_all_folders(folder, suffix, recursive, self.update_status)
            messagebox.showinfo(
                "Done",
                f"Processing finished!\n\nSuccess: {success} folders\nErrors: {error} folders"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error:\n{str(e)}")
            print(f"Unexpected error: {e}", file=sys.stderr)
        finally:
            self.run_btn.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    app = ConcatApp(root)
    root.mainloop()