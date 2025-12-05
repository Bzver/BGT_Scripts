import os
import shutil
import re

def find_and_rename_mat(folder_path, dry_run=False):
    """
    Find .mat files, verify them, and rename based on folder/filename conventions.
    
    Args:
        folder_path (str): Root folder to search.
        dry_run (bool): If True, only print intended actions (no actual rename).
    """
    renamed_count = 0
    skipped_count = 0

    for root, _, files in os.walk(folder_path):
        for file in files:
            filepath = os.path.join(root, file)
            if not file.lower().endswith('.mat'):
                continue

            try:
                if not verify_file_id(filepath):
                    skipped_count += 1
                    continue

                folder_match = re.search(r'2025(\d{4,6})', root)
                if not folder_match:
                    print(f"Skipping {filepath}: Cannot parse date from folder path.")
                    skipped_count += 1
                    continue
                date_part = folder_match.group(1)  # e.g., "0415" or "041512"

                name_match = re.match(r'([A-Za-z0-9_]+?)T_aaa_', file)
                if not name_match:
                    print(f"Skipping {filepath}: Cannot parse location from filename.")
                    skipped_count += 1
                    continue
                location = name_match.group(1)

                try:
                    exp_day = determine_exp_day(filepath, date_part)
                except Exception as e:
                    print(f"Error determining exp_day for {filepath}: {e}")
                    skipped_count += 1
                    continue

                new_name = f"{location}_2025{date_part}_{exp_day}.mat"
                new_path = os.path.join(root, new_name)

                if dry_run:
                    print(f"[DRY-RUN] Would rename:\n  {filepath}\n  → {new_path}")
                else:
                    shutil.move(filepath, new_path)
                    print(f"Renamed:\n  {filepath}\n  → {new_path}")
                    renamed_count += 1

            except Exception as e:
                print(f"Unexpected error processing {filepath}: {e}")

    print(f"\nDone. Renamed: {renamed_count}, Skipped: {skipped_count}")
                    
def verify_file_id(filepath):
    return (" Marathon" in filepath and
            "2025" in filepath and
            "T_aaa_" in filepath
            )

def determine_exp_day(filepath, start_date):
    if str(int(start_date) + 2) in filepath:
        return "Day3"
    elif str(int(start_date) + 1) in filepath:
        return "Day2"
    elif str(int(start_date)) in filepath:
        return "Day1"
    
if __name__ == "__main__":
    find_and_rename_mat("D:/Data/Videos", dry_run=False)