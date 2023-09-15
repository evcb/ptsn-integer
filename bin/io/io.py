import os
from bin.constants import OUTPUT_FOLDER_NAME


def exists(f_name: str):
    return os.path.exists(f_name)

def create_folder(f_name: str):
    if not exists(f_name):
        os.mkdir(f_name)

def write_solution(f_name: str, output: str, append=False):
    """Write solution file

    Args:
        f_name (str): File name
        output (str): Output
        append (bool, optional): Append output if file exist. Defaults to False.
    """
    _o_f = OUTPUT_FOLDER_NAME
    mode = "w" if not append else "a"

    create_folder(_o_f)

    with open(f"{_o_f}/{f_name}", mode) as f:
        f.write(output)
        f.close()