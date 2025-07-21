import os
import shutil

def filename_replacer(folder, string_A, string_B):
    renamed_dir = os.path.join(folder, "renamed_files")
    os.makedirs(renamed_dir, exist_ok=True)
    files = os.listdir(folder)
    renamed_count = 0
    for file in files:
        if string_A in file:
            part_1, part_2 = file.split(string_A)
            new_file_name = f"{part_1}{string_B}{part_2}"
            filepath = os.path.join(folder, file)
            new_filepath = os.path.join(renamed_dir, new_file_name)
            shutil.copy(filepath, new_filepath)
            renamed_count += 1
    print(f"Process complete, renamed {renamed_count} files and saved in {renamed_dir}")

if __name__ == "__main__":
    folder = "D:/Project/A-SOID/Data/20250709/mis"
    string_A = "-D-"
    string_B = "-S-"
    filename_replacer(folder, string_A, string_B)