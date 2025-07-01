import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk # Added ttk for progress later if needed
import tempfile # For temporary frame image
from PIL import Image, ImageTk # For image display

# --- Main Processing Function (Mostly unchanged, added progress reporting) ---

def crop_resize_and_convert_videos(input_folder, output_folder, crop_left, crop_top, crop_right, crop_bottom, target_width, target_height, output_suffix="-conv.mp4", progress_callback=None):
    """
    Crops, resizes, and converts videos using FFmpeg.

    Args:
        input_folder (str): Path to the folder containing input videos.
        output_folder (str): Path to the folder to save output videos.
        crop_left (int): Number of pixels to crop from the left.
        crop_top (int): Number of pixels to crop from the top.
        crop_right (int): Number of pixels to crop from the right.
        crop_bottom (int): Number of pixels to crop from the bottom.
        target_width (int): Target width of the output video.
        target_height (int): Target height of the output video.
        output_suffix (str): Suffix to add to the converted output filenames.
        progress_callback (function, optional): Function to call with progress updates (current, total).

    Returns:
        tuple: (processed_count, skipped_count, error_count)
    """
    if not input_folder or not output_folder:
        messagebox.showerror("Error", "Input and Output folders must be selected.")
        return (0, 0, 0)

    if not os.path.exists(output_folder):
        try:
            os.makedirs(output_folder)
        except OSError as e:
            messagebox.showerror("Error", f"Could not create output folder:\n{output_folder}\n{e}")
            return (0, 0, 0)

    ffmpeg_found = True
    ffprobe_found = True

    print(f"--- Starting Batch Crop, Resize, and Convert ---")
    print(f"Input Folder: {input_folder}")
    print(f"Output Folder: {output_folder}")
    print(f"Crop (L, T, R, B): ({crop_left}, {crop_top}, {crop_right}, {crop_bottom})")
    print(f"Target Size (W x H): {target_width} x {target_height}")
    print(f"Output Suffix: {output_suffix}") # Added suffix print
    print("-" * 20)

    processed_count = 0
    skipped_count = 0
    error_count = 0

    try: # Added try/except for listdir
        video_files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))]
    except FileNotFoundError:
        messagebox.showerror("Error", f"Input folder not found:\n{input_folder}")
        return (0,0,0)
    except Exception as e:
        messagebox.showerror("Error", f"Could not read input folder:\n{input_folder}\n{e}")
        return (0,0,0)

    total_files = len(video_files)
    if total_files == 0:
        messagebox.showinfo("Info", "No video files found in the input folder.")
        if progress_callback: progress_callback(0, 0, "No video files found.")
        return (0, 0, 0)


    for i, filename in enumerate(video_files):
        input_path = os.path.join(input_folder, filename)
        # Ensure suffix is added correctly, even if empty
        base, ext = os.path.splitext(filename)
        output_filename = base + output_suffix + (ext if not output_suffix.endswith(('.mp4', '.avi', '.mov', '.mkv')) else '') # Try to preserve original ext if suffix doesn't specify one
        if not os.path.splitext(output_filename)[1]: # If still no extension, default to .mp4
             output_filename += ".mp4"
        output_path = os.path.join(output_folder, output_filename)


        if progress_callback:
            progress_callback(i, total_files, f"Processing: {filename}")

        try:
            # Get video dimensions using ffprobe
            probe_command = [
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', input_path
            ]
            probe_result = subprocess.run(probe_command, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            width, height = map(int, probe_result.stdout.strip().split('x'))

            # Calculate crop parameters
            crop_width = width - crop_left - crop_right
            crop_height = height - crop_top - crop_bottom
            crop_x = crop_left
            crop_y = crop_top

            # Validate crop dimensions and area
            if crop_width <= 0 or crop_height <= 0:
                print(f"Warning: Invalid crop dimensions calculated for {filename} (W:{crop_width}, H:{crop_height}). Skipping.")
                skipped_count += 1
                continue
            if crop_x < 0 or crop_y < 0 or crop_x + crop_width > width or crop_y + crop_height > height:
                print(f"Warning: Crop area out of bounds for {filename}. Skipping.")
                skipped_count += 1
                continue

            ffmpeg_command = [
                'ffmpeg', '-y', '-i', input_path,
                '-vf', f'crop={crop_width}:{crop_height}:{crop_x}:{crop_y},scale={target_width}:{target_height}',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'superfast',
                '-crf', '23', '-c:a', 'copy', output_path
            ]
            subprocess.run(ffmpeg_command, check=True, creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            print(f"Processed: {filename} -> {output_filename}")
            processed_count += 1

        except subprocess.CalledProcessError as e:
            print(f"Error processing {filename}: {e}")
            if e.cmd and e.cmd[0] == 'ffprobe' and not ffprobe_found: pass # Already handled
            elif e.cmd and e.cmd[0] == 'ffmpeg' and not ffmpeg_found: pass # Already handled
            else:
                print(f"  Command failed: {' '.join(e.cmd)}")
                if e.stderr: print(f"  FFmpeg/FFprobe Error Output:\n{e.stderr.decode(errors='ignore')}") # Decode stderr
            error_count += 1
        except FileNotFoundError as e:
            tool_name = 'ffprobe' if 'ffprobe' in str(e) else 'ffmpeg'
            if (tool_name == 'ffprobe' and ffprobe_found) or (tool_name == 'ffmpeg' and ffmpeg_found):
                 messagebox.showerror("Error", f"{tool_name} not found. Make sure FFmpeg (which includes ffprobe) is installed and in your system's PATH.")
                 if tool_name == 'ffprobe': ffprobe_found = False
                 if tool_name == 'ffmpeg': ffmpeg_found = False
                 # Assume remaining files will also fail
                 remaining_files = total_files - i
                 error_count += remaining_files
                 if progress_callback: progress_callback(i, total_files, f"{tool_name} not found. Aborting.")
                 return (processed_count, skipped_count, error_count)
            elif ffprobe_found and ffmpeg_found: # Other file not found? Unlikely here.
                 print(f"Error: File not found during processing of {filename}: {e}")
                 error_count += 1
        except ValueError as e:
             print(f"Error parsing dimensions for {filename}. Probe output: '{probe_result.stdout.strip()}'. Error: {e}")
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
    # Summary messagebox shown by the GUI caller
    return (processed_count, skipped_count, error_count)


# --- GUI Setup ---
class App:
    def __init__(self, master):
        self.master = master
        master.title("Batch Video Processor")
        master.geometry("750x750") # Increased size slightly for new field

        # --- Variables ---
        self.output_folder = tk.StringVar()
        self.input_folder = tk.StringVar()
        self.preview_video_path = tk.StringVar()
        self.crop_left = tk.IntVar(value=10)
        self.crop_top = tk.IntVar(value=10)
        self.crop_right = tk.IntVar(value=10)
        self.crop_bottom = tk.IntVar(value=10)
        self.target_width = tk.IntVar(value=640)
        self.target_height = tk.IntVar(value=480)
        self.output_suffix = tk.StringVar(value="-conv.mp4") # <-- New Variable

        # Internal state for preview
        self.preview_image_path = None
        self.preview_photo_image = None # Keep reference for tkinter
        self.crop_rect_id = None
        self.preview_scale_factor = 1.0
        self.original_preview_dims = (0, 0)

        # --- Layout Frames ---
        top_frame = tk.Frame(master, padx=5, pady=5)
        top_frame.pack(fill=tk.X)

        param_frame = tk.LabelFrame(master, text="Processing Parameters", padx=10, pady=10)
        param_frame.pack(fill=tk.X, padx=5, pady=5)

        preview_frame = tk.LabelFrame(master, text="Crop Preview", padx=10, pady=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        action_frame = tk.Frame(master, padx=5, pady=10)
        action_frame.pack(fill=tk.X, side=tk.BOTTOM) # Place at bottom

        # --- Top Frame Widgets (Folders) ---
        tk.Label(top_frame, text="Input Folder:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.input_entry = tk.Entry(top_frame, textvariable=self.input_folder, width=60)
        self.input_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(top_frame, text="Browse...", command=self.select_input).grid(row=0, column=2, padx=5, pady=5)

        tk.Label(top_frame, text="Output Folder:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.output_entry = tk.Entry(top_frame, textvariable=self.output_folder, width=60)
        self.output_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(top_frame, text="Browse...", command=self.select_output).grid(row=1, column=2, padx=5, pady=5)

        top_frame.grid_columnconfigure(1, weight=1) # Allow entry to expand

        # --- Parameter Frame Widgets ---
        # Crop Parameters
        tk.Label(param_frame, text="Crop Pixels From:").grid(row=0, column=0, columnspan=4, pady=(0, 5), sticky="w")
        tk.Label(param_frame, text="Left:").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        tk.Entry(param_frame, textvariable=self.crop_left, width=7).grid(row=1, column=1, padx=5, pady=2, sticky="w")
        tk.Label(param_frame, text="Top:").grid(row=1, column=2, padx=5, pady=2, sticky="e")
        tk.Entry(param_frame, textvariable=self.crop_top, width=7).grid(row=1, column=3, padx=5, pady=2, sticky="w")
        tk.Label(param_frame, text="Right:").grid(row=2, column=0, padx=5, pady=2, sticky="e")
        tk.Entry(param_frame, textvariable=self.crop_right, width=7).grid(row=2, column=1, padx=5, pady=2, sticky="w")
        tk.Label(param_frame, text="Bottom:").grid(row=2, column=2, padx=5, pady=2, sticky="e")
        tk.Entry(param_frame, textvariable=self.crop_bottom, width=7).grid(row=2, column=3, padx=5, pady=2, sticky="w")

        # Target Size Parameters
        tk.Label(param_frame, text="Target Size (pixels):").grid(row=3, column=0, columnspan=4, pady=(10, 5), sticky="w")
        tk.Label(param_frame, text="Width:").grid(row=4, column=0, padx=5, pady=2, sticky="e")
        tk.Entry(param_frame, textvariable=self.target_width, width=7).grid(row=4, column=1, padx=5, pady=2, sticky="w")
        tk.Label(param_frame, text="Height:").grid(row=4, column=2, padx=5, pady=2, sticky="e")
        tk.Entry(param_frame, textvariable=self.target_height, width=7).grid(row=4, column=3, padx=5, pady=2, sticky="w")

        # --- Output Suffix Parameter --- <--- NEW WIDGETS
        tk.Label(param_frame, text="Output Suffix:").grid(row=5, column=0, padx=5, pady=(10,2), sticky="e")
        tk.Entry(param_frame, textvariable=self.output_suffix, width=15).grid(row=5, column=1, columnspan=3, padx=5, pady=(10,2), sticky="w")


        # --- Preview Frame Widgets ---
        preview_controls_frame = tk.Frame(preview_frame)
        preview_controls_frame.pack(fill=tk.X, pady=(0, 5))

        tk.Label(preview_controls_frame, text="Preview Video:").pack(side=tk.LEFT, padx=(0, 5))
        self.preview_entry = tk.Entry(preview_controls_frame, textvariable=self.preview_video_path, width=40)
        self.preview_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(preview_controls_frame, text="Browse...", command=self.select_preview_video).pack(side=tk.LEFT, padx=5)
        tk.Button(preview_controls_frame, text="Update Preview", command=self.update_preview).pack(side=tk.LEFT, padx=(5, 0))

        self.preview_canvas = tk.Canvas(preview_frame, bg="grey", relief=tk.SUNKEN, borderwidth=1)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        self.preview_canvas.bind("<Configure>", self.on_canvas_resize) # Handle resize

        # --- Action Frame Widgets ---
        self.run_button = tk.Button(action_frame, text="Run Processing", command=self.run_processing, width=20, height=2)
        self.run_button.pack(side=tk.RIGHT, padx=5) # Place run button to the right

        # Progress Bar (Optional but good for long tasks)
        self.progress_label = tk.Label(action_frame, text="")
        self.progress_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        # self.progress_bar = ttk.Progressbar(action_frame, orient=tk.HORIZONTAL, length=300, mode='determinate')
        # self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)


    def select_input(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.input_folder.set(folder_selected)

    def select_output(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.output_folder.set(folder_selected)

    def select_preview_video(self):
        file_selected = filedialog.askopenfilename(
            title="Select Video for Preview",
            filetypes=(("Video Files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*"))
        )
        if file_selected:
            self.preview_video_path.set(file_selected)
            self.update_preview() # Automatically update preview on new selection

    def _get_int_param(self, tk_var, name):
        """Helper to get integer parameter with validation."""
        try:
            val = tk_var.get()
            if val < 0:
                raise ValueError(f"{name} cannot be negative.")
            return val
        except tk.TclError:
            raise ValueError(f"Invalid integer value for {name}.")
        except ValueError as e:
             raise ValueError(f"Invalid value for {name}: {e}")


    def _extract_frame(self, video_path, output_image_path, time_offset="00:00:01"):
        """Extracts a single frame using FFmpeg."""
        try:
            ffmpeg_command = [
                'ffmpeg', '-y', '-i', video_path, '-ss', time_offset,
                '-vframes', '1', '-q:v', '2', # Good quality JPEG
                output_image_path
            ]
            result = subprocess.run(ffmpeg_command, check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return True
        except FileNotFoundError:
            messagebox.showerror("Error", "ffmpeg not found. Make sure FFmpeg is installed and in your system's PATH.")
            return False
        except subprocess.CalledProcessError as e:
            print(f"Error extracting frame from {os.path.basename(video_path)}: {e}")
            print(f"FFmpeg stderr: {e.stderr.decode(errors='ignore')}")
            messagebox.showerror("Preview Error", f"Could not extract frame from video.\nCheck console for details.\nIs the video file valid?")
            return False
        except Exception as e:
            print(f"Unexpected error extracting frame: {e}")
            messagebox.showerror("Preview Error", f"An unexpected error occurred during frame extraction:\n{e}")
            return False

    def _get_video_dimensions(self, video_path):
        """Gets video dimensions using ffprobe."""
        try:
            probe_command = [
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', video_path
            ]
            probe_result = subprocess.run(probe_command, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            width, height = map(int, probe_result.stdout.strip().split('x'))
            return width, height
        except FileNotFoundError:
            messagebox.showerror("Error", "ffprobe not found. Make sure FFmpeg (which includes ffprobe) is installed and in your system's PATH.")
            return None
        except (subprocess.CalledProcessError, ValueError, Exception) as e:
            print(f"Error getting dimensions for {os.path.basename(video_path)}: {e}")
            if isinstance(e, subprocess.CalledProcessError) and e.stderr:
                 print(f"FFprobe stderr: {e.stderr.decode(errors='ignore')}")
            messagebox.showerror("Preview Error", f"Could not get video dimensions for preview.\nCheck console for details.")
            return None

    def on_canvas_resize(self, event):
        """Redraw preview when canvas size changes."""
        # Simple redraw - could be optimized later if needed
        self.update_preview(force_extract=False) # Don't re-extract frame on resize

    def update_preview(self, force_extract=True):
        """Updates the preview canvas with the frame and crop rectangle."""
        video_path = self.preview_video_path.get()
        if not video_path or not os.path.exists(video_path):
            self.preview_canvas.delete("all") # Clear canvas if no valid video
            self.preview_canvas.create_text(self.preview_canvas.winfo_width()/2, self.preview_canvas.winfo_height()/2, text="Select a video file and click 'Update Preview'", fill="white")
            self.preview_image_path = None
            self.preview_photo_image = None
            self.crop_rect_id = None
            return

        # --- 1. Extract Frame (if needed) ---
        if force_extract or not self.preview_image_path or not os.path.exists(self.preview_image_path):
            # Clean up old temp file if it exists
            if self.preview_image_path and os.path.exists(self.preview_image_path):
                try:
                    os.remove(self.preview_image_path)
                except OSError: pass # Ignore if deletion fails

            # Create a temporary file for the frame
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_f:
                self.preview_image_path = temp_f.name

            if not self._extract_frame(video_path, self.preview_image_path):
                self.preview_canvas.delete("all")
                self.preview_canvas.create_text(self.preview_canvas.winfo_width()/2, self.preview_canvas.winfo_height()/2, text="Error extracting frame. Check console.", fill="red")
                self.preview_image_path = None # Invalidate path
                return

            # Get original dimensions right after extracting
            dims = self._get_video_dimensions(video_path)
            if not dims:
                self.preview_canvas.delete("all")
                self.preview_canvas.create_text(self.preview_canvas.winfo_width()/2, self.preview_canvas.winfo_height()/2, text="Error getting video dimensions. Check console.", fill="red")
                self.preview_image_path = None # Invalidate path
                return
            self.original_preview_dims = dims


        # --- 2. Load and Resize Image ---
        try:
            img = Image.open(self.preview_image_path)
            img.load() # Ensure image data is loaded

            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()

            if canvas_width <= 1 or canvas_height <= 1: # Canvas not ready yet
                self.master.after(50, lambda: self.update_preview(force_extract=False)) # Try again shortly, don't force extract
                return

            # Calculate scaling factor to fit image in canvas
            img_width, img_height = img.size
            width_scale = canvas_width / img_width
            height_scale = canvas_height / img_height
            self.preview_scale_factor = min(width_scale, height_scale)

            # Prevent upscaling beyond original size (optional, but often desired)
            # self.preview_scale_factor = min(self.preview_scale_factor, 1.0)

            new_width = int(img_width * self.preview_scale_factor)
            new_height = int(img_height * self.preview_scale_factor)

            # Check for zero dimensions after scaling
            if new_width <= 0 or new_height <= 0:
                print(f"Warning: Calculated preview dimensions are too small ({new_width}x{new_height}). Skipping display.")
                self.preview_canvas.delete("all")
                self.preview_canvas.create_text(canvas_width/2, canvas_height/2, text="Preview too small to display.", fill="orange")
                return

            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS) # Use LANCZOS for better quality resize
            self.preview_photo_image = ImageTk.PhotoImage(resized_img)

        except FileNotFoundError:
            messagebox.showerror("Preview Error", f"Preview image file not found:\n{self.preview_image_path}")
            self.preview_canvas.delete("all")
            self.preview_image_path = None
            return
        except Exception as e:
            messagebox.showerror("Preview Error", f"Error loading or resizing preview image:\n{e}")
            print(f"Error loading/resizing preview: {e}")
            self.preview_canvas.delete("all")
            return

        # --- 3. Display Image and Draw Rectangle ---
        self.preview_canvas.delete("all") # Clear previous content
        # Calculate position to center the image
        x_pos = (canvas_width - new_width) / 2
        y_pos = (canvas_height - new_height) / 2
        self.preview_canvas.create_image(x_pos, y_pos, anchor=tk.NW, image=self.preview_photo_image)

        # --- 4. Draw Crop Rectangle ---
        try:
            c_left = self._get_int_param(self.crop_left, "Crop Left")
            c_top = self._get_int_param(self.crop_top, "Crop Top")
            c_right = self._get_int_param(self.crop_right, "Crop Right")
            c_bottom = self._get_int_param(self.crop_bottom, "Crop Bottom")

            orig_w, orig_h = self.original_preview_dims
            if orig_w <= 0 or orig_h <=0: # Check if original dimensions are valid
                 print("Warning: Invalid original video dimensions for preview rectangle.")
                 return

            # Calculate crop box in *original* video coordinates
            crop_x1_orig = c_left
            crop_y1_orig = c_top
            crop_x2_orig = orig_w - c_right
            crop_y2_orig = orig_h - c_bottom

            # Validate original crop box
            if crop_x1_orig >= crop_x2_orig or crop_y1_orig >= crop_y2_orig:
                print("Warning: Invalid crop parameters (e.g., Left >= Width - Right). Not drawing rectangle.")
                self.preview_canvas.create_text(10, 10, anchor=tk.NW, text="Invalid Crop Parameters", fill="red", font=("Arial", 10, "bold"))
                return # Don't draw invalid rect

            # Scale coordinates to the *displayed* image size
            scale = self.preview_scale_factor
            crop_x1_scaled = crop_x1_orig * scale + x_pos # Add offset for centered image
            crop_y1_scaled = crop_y1_orig * scale + y_pos
            crop_x2_scaled = crop_x2_orig * scale + x_pos
            crop_y2_scaled = crop_y2_orig * scale + y_pos

            # Draw the rectangle
            self.crop_rect_id = self.preview_canvas.create_rectangle(
                crop_x1_scaled, crop_y1_scaled, crop_x2_scaled, crop_y2_scaled,
                outline='red', width=2, tags="crop_rect"
            )

        except ValueError as e:
             # Error getting parameters, message already shown by _get_int_param
             print(f"Value error getting crop params: {e}")
             self.preview_canvas.create_text(10, 10, anchor=tk.NW, text=f"Invalid Input: {e}", fill="red", font=("Arial", 10, "bold"))
        except Exception as e:
            print(f"Error drawing crop rectangle: {e}")
            self.preview_canvas.create_text(10, 10, anchor=tk.NW, text="Error drawing crop", fill="red", font=("Arial", 10, "bold"))


    def update_progress(self, current, total, message=""):
        """Callback function to update progress indicators."""
        if total > 0:
            percent = int((current / total) * 100)
            # self.progress_bar['value'] = percent
            self.progress_label['text'] = f"{message} ({current}/{total}) {percent}%"
        else:
            # self.progress_bar['value'] = 0
            self.progress_label['text'] = message
        self.master.update_idletasks() # Force GUI update


    def run_processing(self):
        in_folder = self.input_folder.get()
        out_folder = self.output_folder.get()

        if not in_folder or not out_folder:
            messagebox.showerror("Error", "Please select both Input and Output folders.")
            return

        try:
            # Get parameters from the GUI using helper
            c_left = self._get_int_param(self.crop_left, "Crop Left")
            c_top = self._get_int_param(self.crop_top, "Crop Top")
            c_right = self._get_int_param(self.crop_right, "Crop Right")
            c_bottom = self._get_int_param(self.crop_bottom, "Crop Bottom")
            t_width = self._get_int_param(self.target_width, "Target Width")
            t_height = self._get_int_param(self.target_height, "Target Height")
            out_suffix = self.output_suffix.get() # <-- Get suffix value

            # Basic validation
            if t_width <= 0 or t_height <= 0:
                 raise ValueError("Target Width and Height must be positive integers.")
            # Optional: Validate suffix? (e.g., not empty, starts with '-', etc.)
            # For now, allow any string including empty.

            # Disable button during processing
            self.run_button.config(state=tk.DISABLED, text="Processing...")
            self.update_progress(0, 0, "Starting...") # Initial progress update
            self.master.update_idletasks() # Ensure GUI updates

            # Run the main function with progress callback
            processed, skipped, errors = crop_resize_and_convert_videos(
                in_folder,
                out_folder,
                c_left,
                c_top,
                c_right,
                c_bottom,
                t_width,
                t_height,
                output_suffix=out_suffix, # <-- Pass the suffix
                progress_callback=self.update_progress # Pass the callback
            )

            # Show summary message
            messagebox.showinfo("Complete", f"Processing finished.\n\nProcessed: {processed}\nSkipped: {skipped}\nErrors: {errors}\n\nCheck console for details.")


        except ValueError as e:
             messagebox.showerror("Invalid Input", f"Error in parameters: {e}")
             self.update_progress(0, 0, "Error.") # Update progress on error
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
            print(f"Unexpected error during run_processing setup or execution: {e}") # Log details
            self.update_progress(0, 0, "Error.") # Update progress on error
        finally:
             # Re-enable button regardless of success or failure
            self.run_button.config(state=tk.NORMAL, text="Run Processing")
            # Optional: Clear progress label after a delay or keep the final message
            # self.master.after(3000, lambda: self.update_progress(0, 0, ""))


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
    # Clean up temporary preview file on exit (if it exists and wasn't cleaned)
    if hasattr(app, 'preview_image_path') and app.preview_image_path and os.path.exists(app.preview_image_path):
         try:
             os.remove(app.preview_image_path)
             print(f"Cleaned up temp file: {app.preview_image_path}")
         except OSError as e:
             print(f"Warning: Could not remove temp file {app.preview_image_path}: {e}")

