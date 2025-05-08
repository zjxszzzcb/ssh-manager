from ssh_manager.ui.main_ui import SSHManagerMainUI
from ssh_manager.utils.ssh_configs import load_ssh_config_file

def main():
    host_configs_map = load_ssh_config_file()
    host_configs = list(host_configs_map.values())
    ui = SSHManagerMainUI(host_configs)
    ui.run()

if __name__ == "__main__":
    main()