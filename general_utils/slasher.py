import pandas as pd

inputString = input("Enter the slash you wish to be slashed: ")
if "\\" in inputString:
    print("Slash found, prepare to slash.")
    ouputString = inputString.replace("\\" ,"/")
    df = pd.DataFrame([ouputString])
    df.to_clipboard(index=False, header=False)
    print("Slashed string copied to clipboard.")
else:
    print("No slash found in input. Slash operation aborted.")