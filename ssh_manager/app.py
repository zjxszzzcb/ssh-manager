import argparse

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding

from typing import List

from ssh_manager.utils.ssh_configs import HostConfig

from ssh_manager.screens.main_screens import SSHManageMainScreen
from ssh_manager.screens.ssh_conn_screens import SSHConnScreen
from ssh_manager.utils.ssh_util import SSHConnection
from ssh_manager.utils.ssh_configs import load_ssh_config_file, update_ssh_config, load_known_ssh_hosts

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
        print(f"[DEBUG] Key pressed: {event.key}")
        if event.key == "enter":
            self.action_connect()
    
        
    def action_connect(self) -> None:
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
    app = SSHManagerApp(host_configs)
    app.run()

if __name__ == "__main__":
    main()