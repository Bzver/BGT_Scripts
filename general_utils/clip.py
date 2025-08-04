import pandas as pd

def varname_to_print_statement() -> str:
    varname = input("Enter the variable name you wish to process: ").strip()
    output_string = f"print(f'{varname}: {{{varname}}}')"
    return output_string

def format_path() -> str:
    input_string = input("Enter the path string you wish to process: ")
    output_string = input_string.replace("\\", "/").strip()
    return output_string

def string_to_clipboard(output_string:str):
    df = pd.DataFrame([output_string])
    df.to_clipboard(excel=False, index=False, header=False)
    print("Processed string copied to clipboard.")

if __name__ == "__main__":
    MODE = "path"  
    func = format_path if MODE == "path" else varname_to_print_statement
    opstr = func()
    string_to_clipboard(opstr)