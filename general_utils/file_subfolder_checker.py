import os

def check_file_any_subfolder(folder:str, filename:str) -> list:
    folder_without_filename = []
    for subfolder in [f for f in os.listdir(folder) if os.path.isdir(os.path.join(folder, f))]:
        if not filename in os.listdir(os.path.join(folder, subfolder)):
            folder_without_filename.append(subfolder)
    return folder_without_filename

if __name__ == "__main__":
    folder = "D:/Starsector/mods"
    filename = "mod_info.json"
    print(check_file_any_subfolder(folder, filename))