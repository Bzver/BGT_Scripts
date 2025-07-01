import shutil
import os

folderSrc = "D:/Project/SDANNCE-Models/555-5CAM/SD-20250605M"
folderDst = "D:/Project/DLC-Models/Label3D/videos/jobs"

numVids = 4

for i in range(numVids):
    folderName = os.path.basename(folderSrc).split("SD-")[1]
    pathIn = os.path.join(folderSrc,"Videos",f"Camera{i+1}","0.mp4")
    pathOut = os.path.join(folderDst,f"{folderName}_cam{i+1}.mp4")
    if os.path.exists(pathOut):
        print(f"{pathOut} already existed. Skipping...")
    else:
        shutil.copy(pathIn,pathOut)
        print(f"{pathIn} --→ {pathOut}")