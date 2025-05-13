import argparse

from textual import events
from textual.app import App
from textual.binding import Binding
from typing import List, Sequence

from ssh_manager.screens.main_screens import SSHManageMainScreen
from ssh_manager.screens.ssh_conn_screens import SSHConnScreen
from ssh_manager.utils.ssh_configs import HostConfig, load_ssh_config_file, update_ssh_config, load_known_ssh_hosts

class SSHManagerApp(App):

    BINDINGS = [
        Binding("escape", "quit", "Quit", show=True),
        Binding("c", "connect", "Connect", show=True),
    ]

    def __init__(self, host_configs: List[HostConfig]):

        super().__init__()

        self.main_screen = SSHManageMainScreen(host_configs)
    

    def on_mount(self):
        self.install_screen(self.main_screen, name="main_screen")
        self.push_screen("main_screen")

    def on_key(self, event: events.Key) -> None:
        """处理按键事件"""
        print(f"[DEBUG] Main App Detect Key pressed: {event.key}")
        if event.key == "enter" and self.screen_stack[-1] == self.main_screen:
            self.action_connect()
    
        
    def action_connect(self) -> None:
        with self.suspend():
            if self.main_screen.create_connection():
                host_config = self.main_screen.get_selected_host_config()
                self.push_screen(SSHConnScreen(host_config))


    def action_quit(self) -> None:
        """退出应用，但仅在编辑器没有焦点时生效"""
        if self.screen_stack[-1] == self.main_screen:
            editor = self.main_screen.query_one("HostConfigEditor")
            if not editor.has_focus:
                self.main_screen.cleanup_connections()
                self.exit()

def parse_ssh_config(args: Sequence[str]):
    parser = argparse.ArgumentParser(description="SSH Command Parser")
    parser.add_argument("command", choices=['ssh'])
    parser.add_argument("host")
    parser.add_argument("-L", nargs="*", default=[], dest='local_forwards')

    parser.add_argument("-p", "--port", type=int, required=False, default=22)
    parser.add_argument("--password", type=str, required=False, default=None)
    parser.add_argument("-n", "--name", type=str, required=False, default="")

    args, unkargs = parser.parse_known_args(args)

    host_configs_map = load_known_ssh_hosts()

    if '@' in args.host:
        user, hostname = args.host.split("@")
        host = args.name or hostname
    else:
        user = ""
        host = hostname = args.host

    known_host_config = host_configs_map.get(host)

    if not user:
        if known_host_config:
            return known_host_config
        
        host_configs_map.update(load_ssh_config_file())
        return host_configs_map.get(host)
    
    local_forwards = {}
    for local_forward in args.local_forwards:
        local_port, forward_host, forward_port = local_forward.split(":")
        
        if not all([local_port, forward_host, forward_port]):
            print(f'Error LocalForward: {local_forward}')
            continue
            
        local_forwards[local_port] = f"{forward_host}:{forward_port}"
    
    host_config = HostConfig(
        host=host,
        hostname=hostname,
        user=user,
        port=args.port,
        password=args.password,
        local_forwards=local_forwards
    )

    if known_host_config:
        new_config = known_host_config.model_dump()
        new_config.update(host_config.model_dump())
        return new_config
    else:
        return host_config

def main():
    parser = argparse.ArgumentParser(description="SSH Manager")
    parser.add_argument("--init", action="store_true", help="Initialize SSH config file")
    args, unkargs = parser.parse_known_args()
    
    if args.init:
        host_configs_map = load_ssh_config_file()
        for host, config in host_configs_map.items():
            update_ssh_config(config)
            print(f"Initialized SSH config for {host}")
        return
    
    host_configs_map = load_known_ssh_hosts()
    cmd_host_config = parse_ssh_config(unkargs)
    if cmd_host_config:
        update_ssh_config(cmd_host_config)
        host_configs_map[cmd_host_config.host] = cmd_host_config

    host_configs = list(host_configs_map.values())
    app = SSHManagerApp(host_configs)

    app.run()

if __name__ == "__main__":
    main()