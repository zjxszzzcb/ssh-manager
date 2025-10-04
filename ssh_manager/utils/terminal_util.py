import os
import platform
import shutil
import subprocess

from typing import List


def open_new_terminal(commands: List[str]):
    """Opens a new terminal window and executes the given commands"""
    system = platform.system()

    if system == "Windows":
        cmd = ['start', 'cmd', '/k'] + commands
        subprocess.Popen(cmd, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)

    elif system == "Linux":
        terminals = [
            ('x-terminal-emulator', ['-e']),
            ('gnome-terminal', ['--']),
            ('konsole', ['-e']),
            ('xterm', ['-e']),
        ]

        for terminal_cmd, terminal_args in terminals:
            if not shutil.which(terminal_cmd):
                continue

            if terminal_cmd == 'gnome-terminal':
                cmd = [terminal_cmd] + terminal_args + commands
            else:
                cmd = [terminal_cmd] + terminal_args + [' '.join(commands)]

            subprocess.Popen(cmd)

        raise OSError("No suitable terminal emulator found")
    else:
        # Future platform support
        raise NotImplementedError(f"Platform '{system}' is not supported")


CLEAR_COMMAND = 'cls' if platform.system().lower() == 'windows' else 'clear'
def clear_terminal(func):
    """Decorator to clear the terminal before executing the function"""
    def wrapper(*args, **kwargs):
        try:
            os.system(CLEAR_COMMAND)
            return func(*args, **kwargs)
        finally:
            os.system(CLEAR_COMMAND)
    return wrapper
