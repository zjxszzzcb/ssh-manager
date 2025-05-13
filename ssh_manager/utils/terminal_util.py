import subprocess

from typing import List


def open_new_terminal(commands: List[str]):
    """
    Opens a new terminal window and executes 'ssh ym-testenv' command
    """
    import platform
    
    if platform.system() == "Windows":
        commands = ['start', 'cmd', '/k'] + commands
    
    subprocess.Popen(commands, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)


if __name__ == "__main__":
    open_new_terminal(['ssh', 'ym-testenv'])
