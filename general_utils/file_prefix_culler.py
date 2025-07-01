import os

def remove_prefix_before_underscore(folder_path):
    """
    Removes the prefix (everything up to and including the first underscore)
    from all files in the given folder. Mimics the logic of purge_underscore.

    Args:
        folder_path (str): The path to the folder containing the files.
    """
    print(f"Scanning folder: {folder_path}")
    files_processed = 0
    files_renamed = 0
    files_skipped = 0

    try:
        for filename in os.listdir(folder_path):
            old_filepath = os.path.join(folder_path, filename)

            # Check if it's a file
            if os.path.isfile(old_filepath):
                files_processed += 1
                underscore_index = filename.find('_')

                # Check if an underscore exists and it's not the very first character
                if underscore_index > 0:
                    # Get the part of the filename *after* the first underscore
                    new_filename = filename[underscore_index + 1:]

                    # Ensure the new filename is not empty and actually different
                    if new_filename and new_filename != filename:
                        new_filepath = os.path.join(folder_path, new_filename)

                        # Avoid overwriting existing files with the new name
                        if os.path.exists(new_filepath):
                            print(f"Skipping rename of '{filename}' to '{new_filename}': Target file already exists.")
                            files_skipped += 1
                            continue

                        try:
                            os.rename(old_filepath, new_filepath)
                            print(f"Renamed '{filename}' to '{new_filename}'")
                            files_renamed += 1
                        except OSError as e:
                            print(f"Error renaming '{filename}' to '{new_filename}': {e}")
                            files_skipped += 1
                    else:
                        print(f"Skipping '{filename}': No change needed or result is empty.")
                        files_skipped += 1
                else:
                    # No underscore found, or it's the first character (nothing to remove before it)
                    print(f"Skipping '{filename}': No underscore found or underscore is at the beginning.")
                    files_skipped += 1
            else:
                # print(f"Skipping '{filename}': Not a file.") # Optional: uncomment to see skipped directories
                pass # Silently ignore directories/other non-files

        print("\n--- Processing Summary ---")
        print(f"Total items scanned: {files_processed + files_skipped}") # Rough count
        print(f"Files processed: {files_processed}")
        print(f"Files renamed: {files_renamed}")
        print(f"Files skipped: {files_skipped}")
        print("--------------------------")

    except FileNotFoundError:
        print(f"Error: Folder not found at '{folder_path}'")
    except OSError as e:
        print(f"An OS error occurred accessing the folder: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    folder_to_process = input("Enter the path to the folder: ")
    if os.path.isdir(folder_to_process):
        remove_prefix_before_underscore(folder_to_process)
    else:
        print(f"Error: '{folder_to_process}' is not a valid directory.")

