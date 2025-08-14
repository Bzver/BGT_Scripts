import os
import shutil

def change_filename(filepath, identifier, ext):
    if identifier in filepath and filepath.endswith(ext):
        new_filepath = filepath.split(identifier)[0] + identifier + ext
        try:
            shutil.move(filepath, new_filepath)
        except Exception as e:
            print(f"Failed processing {filepath}. Exception; {e}")

if __name__ == "__main__":
    folder = "D:/Project/A-SOID/250720-Social/videos"
    for file in os.listdir(folder):
        filepath = os.path.join(folder, file)
        change_filename(filepath, identifier="-first3h-D", ext=".csv")
        change_filename(filepath, identifier="-first3h-S", ext=".csv")