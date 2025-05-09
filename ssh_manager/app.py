import argparse
from ssh_manager.ui.main_ui import SSHManagerMainUI
from ssh_manager.utils.ssh_configs import load_ssh_config_file, update_ssh_config, load_known_ssh_hosts

def main():
    parser = argparse.ArgumentParser(description="SSH Manager")
    parser.add_argument("--init", action="store_true", help="Initialize SSH config file")
    args = parser.parse_args()
    
    if args.init:
        host_configs_map = load_ssh_config_file()
        for host, config in host_configs_map.items():
            update_ssh_config(config)
            print(f"Initialized SSH config for {host}")
        return
    
    host_configs_map = load_known_ssh_hosts()
    host_configs = list(host_configs_map.values())
    ui = SSHManagerMainUI(host_configs)
    ui.run()

if __name__ == "__main__":
    main()