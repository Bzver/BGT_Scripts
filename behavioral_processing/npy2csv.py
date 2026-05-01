import os
import numpy as np
import pandas as pd
import configparser
import warnings
warnings.simplefilter("error", FutureWarning)

def parse_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)
    annotation_classes = [cls.strip() for cls in config['Project']['CLASSES'].split(',')]
    framerate = int(config['Project']['FRAMERATE'])
    print(annotation_classes)
    return annotation_classes, framerate

def save_predictions(predict_npy, source_file_name, annotation_classes, framerate):
    """From ASOID https://github.com/YttriLab/A-SOID/blob/main/asoid/apps/F_predict.py"""
    predict = np.load(predict_npy, allow_pickle=True)

    df = pd.DataFrame(predict, columns=["labels"])
    time_clm = np.round(np.arange(0, df.shape[0]) / framerate, 2)
    # convert numbers into behavior names
    class_dict = {i: x for i, x in enumerate(annotation_classes)}
    df["classes"] = df["labels"].copy()
    for cl_idx, cl_name in class_dict.items():
        df["classes"].iloc[df["labels"] == cl_idx] = cl_name

    dummy_df = pd.get_dummies(df["classes"]).astype(int)
    # add 0 columns for each class that wasn't predicted in the file
    not_predicted_classes = [x for x in annotation_classes if x not in np.unique(df["classes"].values)]
    for not_predicted_class in not_predicted_classes:
        dummy_df[not_predicted_class] = 0

    dummy_df["time"] = time_clm
    dummy_df = dummy_df.set_index("time")
    if not os.path.isfile(source_file_name):
        dummy_df.to_csv(source_file_name)
    return dummy_df


if __name__ == "__main__":
    rootdir = r"D:\Project\ASOID-Models\Apr-29-2026\videos"
    config = r"D:\Project\ASOID-Models\Apr-29-2026\config.ini"
    annotation_classes, framerate = parse_config(config)

    print(f"Finding npy files in {rootdir}")
    npy_list = []
    for f in os.listdir(rootdir):
        if not f.endswith(".npy"):
            continue
        npy_list.append(os.path.join(rootdir, f))

    print(f"Found {len(npy_list)} npy files.")

    success = 0
    for f_f in npy_list:
        d_f = f_f.replace(".npy",".csv")
        try:
            save_predictions(f_f, d_f, annotation_classes, framerate)
        except Exception as e:
            print(f"Failed: {f_f}, {e}")
        else:
            if os.path.isfile(d_f):
                success += 1
            else:
                print(f"Failed: {f_f}")

    print(f"{success}/{len(npy_list)} succeeded.")
