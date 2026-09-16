import os
import shutil

# ============================================================
# User settings
# ============================================================

# Root directory containing all the animal experiment folders
ROOT = r"D:\MQQ\260803"

# Directory where the copied and renamed .mat files will be saved
DEST_DIR = r"D:\MQQ\260803\extracted_mats"

# Filename pattern for the renamed files.
# Available variables: {sex}, {geno}, {folder}
# Example: "{sex}_{geno}_{folder}.mat" -> "male_homo_Rat123.mat"
RENAME_PATTERN = "{sex}_{geno}_{folder}.mat"


# ============================================================
# Folder parsing (extracting metadata)
# ============================================================

def parse_folder(folder):
    """
    Extracts sex and genotype metadata from the folder name.
    """
    folder_lower = folder.lower()

    sex = "unknown"
    if "female" in folder_lower:
        sex = "female"
    elif "male" in folder_lower:
        sex = "male"

    geno = "unknown"
    if "homo" in folder_lower:
        geno = "homo"
    elif "fet" in folder_lower:
        geno = "fet"
    elif "wt" in folder_lower:
        geno = "wt"

    return sex, geno


# ============================================================
# Main execution
# ============================================================

if __name__ == "__main__":
    # Create destination directory if it doesn't exist
    os.makedirs(DEST_DIR, exist_ok=True)
    
    print(f"Starting file extraction and copying process...")
    print(f"Source root: {ROOT}")
    print(f"Destination: {DEST_DIR}\n")

    processed_count = 0
    skipped_count = 0

    for folder in os.listdir(ROOT):
        folder_path = os.path.join(ROOT, folder)
        
        # Skip if not a directory
        if not os.path.isdir(folder_path):
            continue

        # Parse metadata from folder name
        sex, geno = parse_folder(folder)
        
        # Skip folders that don't contain recognized metadata
        if sex == "unknown" or geno == "unknown":
            print(f"[SKIP] Unknown category: {folder}")
            skipped_count += 1
            continue

        # Locate the specific .mat file based on original script's logic
        mat_file = os.path.join(
            folder_path,
            "DANNCE",
            "predict00",
            "save_data_AVG.mat"
        )

        # Skip if the file doesn't exist
        if not os.path.exists(mat_file):
            print(f"[SKIP] save_data_AVG.mat not found in {folder_path}")
            skipped_count += 1
            continue

        # Construct new filename using the defined pattern
        new_filename = RENAME_PATTERN.format(sex=sex, geno=geno, folder=folder)
        dest_path = os.path.join(DEST_DIR, new_filename)

        # Copy the file to the destination with the new name
        # Note: copy2 preserves original file metadata like creation/modification times
        try:
            shutil.copy2(mat_file, dest_path)
            print(f"[COPY] {folder} -> {new_filename}")
            processed_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to copy {folder}: {e}")

    print("\n" + "="*40)
    print("SUMMARY")
    print("="*40)
    print(f"Total processed and copied: {processed_count}")
    print(f"Total skipped/ignored:     {skipped_count}")
    print("Done!")