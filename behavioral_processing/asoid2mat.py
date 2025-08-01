import os
import pandas as pd

###############################        W         ##################     I     ###################    P     ######################

def abcdefg(folder:str, dom_id:str, *csv_filename:str):
    list_df = []
    for csv in csv_filename:
        csv_filepath = os.path.join(folder, csv)
        df = csv_loader(csv_filepath)
        if dom_id in csv:
            df = prefix_adder(df, dom=True)
        else:
            df = prefix_adder(df)
        list_df.append(df)

    behavior_sorter(list_df)

def csv_loader(csv_filepath:str):
    try:
        df = pd.read_csv(csv_filepath)
        return df
    except Exception as e:
        print(f"Failed to load {csv_filepath}, Exception: {e}.")

def prefix_adder(df:pd.DataFrame, dom=False):
    if "time" in df.columns:
        df = df.drop("time", axis=1)
    if "other" in df.columns:
        df = df.drop("other", axis=1)
    prefix = "dom_" if dom else "sub_"
    for behavior in df.columns:
        behavior = prefix + behavior 
    df = df.add_prefix(prefix)
    return df

def behavior_sorter(list_df:list):
    try:
        df_combined = pd.DataFrame()
        for df in list_df:
            df_combined = pd.concat([df_combined,df], axis=1)
            print("yay")
        print(df_combined)

    except Exception as e:
        print(f"behavior_sorter exception: {e}")


    


if __name__ == "__main__":
    folder = "D:/Project/A-SOID/250720-Social/videos"
    csv_dom = "250626D.csv"
    csv_sub = "250626S.csv"
    dom_id = "D."
    abcdefg(folder, dom_id, csv_dom, csv_sub)

