import cv2
cv2.imshow("test",1)
cv2.waitKey(1000)
cv2.destroyAllWindows()

import os
import deepof.data
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk # Pillow library for image handling

# --- Configuration ---
project_base_path = os.path.join("/mnt", "d", "Project", "DeepOF")
project_name = "deepof_project"
project_path = os.path.join(project_base_path, project_name)
arena_image_folder_name = "Arena_detection" # Name of the subfolder
arena_image_path = os.path.join(project_path, arena_image_folder_name)
tables_path = os.path.join(project_path, "Tables") # Path to the Tables directory

# --- DeepOF Project Loading ---
print(f"Loading DeepOF project from: {project_path}")
try:
    my_deepof_project = deepof.data.load_project(project_path)
    print("Project loaded successfully.")
except FileNotFoundError:
    print(f"ERROR: Project directory not found at {project_path}")
    exit()
except Exception as e:
    print(f"ERROR: Failed to load DeepOF project: {e}")
    exit()

# --- Get Project Keys from Table Folder Names ---
project_keys_from_folders = set() # Use a set for efficient lookup
print(f"Looking for project keys (folder names) in: {tables_path}")
if not os.path.isdir(tables_path):
    print(f"Warning: Tables directory not found at {tables_path}. Cannot verify keys against table folders.")
    # Decide how to proceed if Tables dir is missing. Currently, verification will fail for all keys.
else:
    try:
        for entry in os.listdir(tables_path):
            full_entry_path = os.path.join(tables_path, entry)
            if os.path.isdir(full_entry_path):
                project_keys_from_folders.add(entry) # Add folder name as a valid key
        print(f"Found {len(project_keys_from_folders)} keys (folders) in Tables directory.")
        if not project_keys_from_folders:
             print(f"Warning: No subdirectories found in {tables_path}. Key verification might fail.")
    except Exception as e:
        print(f"ERROR: Failed to read Tables directory {tables_path}: {e}")

# --- Find Arena Images and Extract Keys ---
video_key_to_image_map = {}
available_keys_from_images = []

print(f"Looking for arena images in: {arena_image_path}")
if not os.path.isdir(arena_image_path):
    print(f"ERROR: Arena image directory not found: {arena_image_path}")
    exit()
else:
    try:
        for filename in os.listdir(arena_image_path):
            # Basic assumption: filename starts with the video key
            potential_key = filename.split('_arena_detection.')[0] # Example split
            if not potential_key or potential_key == filename: # Basic check if split worked
                 potential_key = os.path.splitext(filename)[0] # Fallback: Just remove extension
                 print(f"Warning: Could not reliably extract key from '{filename}' using '_arena_detection.'. Using '{potential_key}'. Verify.")

            full_path = os.path.join(arena_image_path, filename)
            if os.path.isfile(full_path) and filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                 # Check if the extracted key exists as a folder name in the Tables directory
                 if potential_key in project_keys_from_folders:
                     video_key_to_image_map[potential_key] = full_path
                     available_keys_from_images.append(potential_key)
                 else:
                     # Provide a more specific warning if the Tables dir was missing/empty vs. key just not found
                     if not project_keys_from_folders and os.path.isdir(tables_path):
                          print(f"Warning: Image found for key '{potential_key}', but no folders were found in '{tables_path}' to verify against. Skipping image.")
                     elif not os.path.isdir(tables_path):
                          print(f"Warning: Image found for key '{potential_key}', but Tables directory '{tables_path}' was not found. Skipping image.")
                     else:
                          print(f"Warning: Image found for key '{potential_key}', but no corresponding folder found in '{tables_path}'. Skipping image.")

        available_keys_from_images = sorted(list(set(available_keys_from_images))) # Sort and ensure uniqueness
        print(f"Found {len(available_keys_from_images)} potential keys with images for review (verified against Tables folders).")

    except Exception as e:
        print(f"ERROR: Failed to read arena image directory or process files: {e}")
        available_keys_from_images = [] # Reset on error

# --- GUI for Image Review and Selection ---

accepted_keys_list = []
current_key_index = 0

if not available_keys_from_images:
    print("No arena images found or processed. Cannot proceed with review.")
else:
    # Create the main window
    root = tk.Tk()
    root.title("Review Arena Detection and Select Keys")

    # --- GUI Elements ---
    main_frame = ttk.Frame(root, padding="10")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    # Status Label
    status_var = tk.StringVar()
    status_label = ttk.Label(main_frame, textvariable=status_var, font=("Arial", 10))
    status_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))

    # Image Display Label
    image_label = ttk.Label(main_frame, text="Image will appear here", relief="solid", padding=5)
    image_label.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
    main_frame.rowconfigure(1, weight=1) # Allow image area to expand
    main_frame.columnconfigure(0, weight=1) # Allow image area to expand horizontally too

    # Buttons Frame
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=2, column=0, columnspan=3, pady=(10, 0))

    # --- Functions ---
    def display_image(index):
        """Loads and displays the image for the given key index."""
        global current_key_index
        current_key_index = index

        if index >= len(available_keys_from_images):
            status_var.set(f"Review Complete! {len(accepted_keys_list)} keys accepted.")
            image_label.config(image='', text="Review Complete") # Clear image
            image_label.image = None # Clear reference
            accept_button.config(state=tk.DISABLED)
            skip_button.config(state=tk.DISABLED)
            return

        key = available_keys_from_images[index]
        image_path = video_key_to_image_map.get(key)
        status_var.set(f"Reviewing: {key} ({index + 1} of {len(available_keys_from_images)})")

        if not image_path:
            image_label.config(image='', text=f"Error: Image path not found for key {key}")
            image_label.image = None
            return

        try:
            img = Image.open(image_path)
            # Resize image to fit reasonably in the GUI (e.g., max 600x600)
            img.thumbnail((600, 600))
            photo = ImageTk.PhotoImage(img)

            image_label.config(image=photo, text="") # Display image
            image_label.image = photo # IMPORTANT: Keep a reference!
        except Exception as e:
            image_label.config(image='', text=f"Error loading image:\n{image_path}\n{e}")
            image_label.image = None
            print(f"Error loading image {image_path}: {e}")

        # Enable buttons
        accept_button.config(state=tk.NORMAL)
        skip_button.config(state=tk.NORMAL)


    def accept_action():
        """Accept the current key and move to the next."""
        key = available_keys_from_images[current_key_index]
        if key not in accepted_keys_list:
            accepted_keys_list.append(key)
            print(f"Accepted: {key}")
        display_image(current_key_index + 1)

    def skip_action():
        """Skip the current key and move to the next."""
        key = available_keys_from_images[current_key_index]
        print(f"Skipped: {key}")
        display_image(current_key_index + 1)

    def finish_action():
        """Close the GUI."""
        print("Finishing review.")
        root.destroy()

    # --- Buttons ---
    accept_button = ttk.Button(button_frame, text="Accept & Next", command=accept_action, state=tk.DISABLED)
    accept_button.grid(row=0, column=0, padx=5)

    skip_button = ttk.Button(button_frame, text="Skip & Next", command=skip_action, state=tk.DISABLED)
    skip_button.grid(row=0, column=1, padx=5)

    finish_button = ttk.Button(button_frame, text="Finish Review", command=finish_action)
    finish_button.grid(row=0, column=2, padx=5)


    # --- Initial Display ---
    display_image(0) # Load the first image

    # --- Start GUI ---
    print("Starting image review GUI...")
    root.mainloop() # Blocks until window is closed
    print("GUI closed.")


# --- Proceed with Arena Editing using accepted keys ---

if accepted_keys_list:
    print(f"\nProceeding to edit arenas for {len(accepted_keys_list)} accepted keys:")
    # print(accepted_keys_list) # Uncomment to see the full list
    try:
        my_deepof_project.edit_arenas(
            video_keys=accepted_keys_list, # Use the list built from the GUI review
            arena_type="polygonal-manual",
        )
        print("Arena editing process initiated.")
    except Exception as e:
        print(f"ERROR during arena editing: {e}")
else:
    print("\nNo video keys were accepted during the review. Skipping arena editing.")

print("\nScript finished.")
