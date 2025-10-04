import argparse
import logging

from textual import events
from textual.app import App
from textual.binding import Binding
from textual.logging import TextualHandler
from typing import List

from ssh_manager.screens import EditSSHConfigScreen, SSHManageMainScreen, SSHConnScreen
from ssh_manager.utils.ssh_configs import (
    HostConfig, load_ssh_config_file, update_host_config, load_known_ssh_hosts, parse_ssh_command
)


class SSHManagerApp(App):
    BINDINGS = [
        Binding("escape", "quit", "Quit", show=True),
        Binding("c", "connect", "Connect", show=True),
    ]

    def __init__(self, host_configs: List[HostConfig], selected_config: HostConfig = None):

        super().__init__()

        self.main_screen = SSHManageMainScreen(host_configs, selected=selected_config)

    def on_mount(self):
        self.install_screen(self.main_screen, name="main_screen")
        self.push_screen("main_screen")

    def on_key(self, event: events.Key) -> None:
        """处理按键事件"""
        print(f"[DEBUG] Main App Detect Key pressed: {event.key}")
        if event.key == "enter" and self.screen_stack[-1] == self.main_screen:
            self.action_connect()

    def action_connect(self) -> None:
        if self.main_screen.create_connection():
            host_config = self.main_screen.get_selected_host_config()
            self.push_screen(SSHConnScreen(host_config))

    def action_quit(self) -> None:
        """退出应用，但仅在编辑器没有焦点时生效"""
        if self.screen_stack[-1] == self.main_screen:
            self.main_screen.quit()


class EditorSSHConfigApp(App):
    """A simple Textual app to display the two-editor screen."""

    BINDINGS = [Binding("escape", "quit", "Quit", show=True)]

    def on_mount(self) -> None:
        """Called when the app is first mounted."""
        # When the app starts, we immediately push the TwoEditorsScreen onto the display stack.
        self.push_screen(EditSSHConfigScreen())


def handle_init_command(args):
    """Handle the 'init' subcommand to initialize SSH config."""
    host_configs_map = load_ssh_config_file()
    if not host_configs_map:
        print("No SSH hosts found in ~/.ssh/config")
        return

    for host, config in host_configs_map.items():
        update_host_config(config)
        print(f"Initialized SSH config for {host}")

    print(f"\nTotal {len(host_configs_map)} hosts initialized successfully.")


def handle_config_command(args):
    """Handle the 'config' subcommand to open configuration editor."""
    app = EditorSSHConfigApp()
    app.run()


def handle_ssh_command(args):
    """Handle the 'ssh' subcommand for SSH connection management."""
    # Load known hosts
    host_configs_map = load_known_ssh_hosts()

    # Parse SSH command arguments if provided
    cmd_host_config = None
    if args.target:
        # Build SSH-style command arguments from parsed args
        ssh_args = []
        if args.target:
            ssh_args.append(args.target)
        if args.port:
            ssh_args.extend(['-p', str(args.port)])
        if args.proxy_jump:
            ssh_args.extend(['-J', args.proxy_jump])

        cmd_host_config = parse_ssh_command(['ssh'] + ssh_args)
        if cmd_host_config:
            update_host_config(cmd_host_config)
            host_configs_map[cmd_host_config.host] = cmd_host_config

    # Launch the TUI application
    host_configs = list(host_configs_map.values())
    app = SSHManagerApp(host_configs, selected_config=cmd_host_config)
    app.run()


def main():
    # Create main parser
    parser = argparse.ArgumentParser(
        description="SSH Manager - A TUI application for managing SSH connections",
        prog="mssh"
    )

    # Global options
    parser.add_argument(
        "--log-level",
        choices=['debug', 'info', 'warning', 'error'],
        default="warning",
        help="Set logging level"
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands'
    )

    # Init subcommand
    parser_init = subparsers.add_parser(
        'init',
        help='Initialize SSH config from ~/.ssh/config file'
    )
    parser_init.add_argument(
        '--force',
        action='store_true',
        help='Force overwrite existing configurations'
    )

    # Config subcommand
    parser_config = subparsers.add_parser(
        'config',
        help='Open SSH configuration editor'
    )

    # SSH subcommand
    parser_ssh = subparsers.add_parser(
        'ssh',
        help='Manage SSH connections (default action)'
    )
    parser_ssh.add_argument(
        'target',
        nargs='?',
        help='SSH target in format [user@]host or host alias'
    )
    parser_ssh.add_argument(
        '-p', '--port',
        type=int,
        help='Port number for SSH connection'
    )
    parser_ssh.add_argument(
        '-J', '--proxy-jump',
        help='ProxyJump host for connection'
    )

    # Parse arguments
    args, unknown_args = parser.parse_known_args()

    # Set up logging
    if args.log_level:
        logging.basicConfig(
            level=getattr(logging, args.log_level.upper()),
            handlers=[TextualHandler()]
        )

    # Handle commands
    if args.command == 'init':
        handle_init_command(args)
    elif args.command == 'config':
        handle_config_command(args)
    elif args.command == 'ssh':
        handle_ssh_command(args)
    else:
        # Default behavior: if no subcommand provided, launch SSH management interface
        # Try to parse any unknown args as SSH command
        ssh_args = argparse.Namespace(
            target=None,
            port=None,
            proxy_jump=None
        )

        if unknown_args:
            # Add 'ssh' prefix if not present for parse_ssh_command compatibility
            if unknown_args[0] != 'ssh':
                unknown_args = ['ssh'] + unknown_args

            cmd_host_config = parse_ssh_command(unknown_args)
            if cmd_host_config:
                ssh_args.target = f"{cmd_host_config.user}@{cmd_host_config.host}" if cmd_host_config.user else cmd_host_config.host
                ssh_args.port = cmd_host_config.port

        handle_ssh_command(ssh_args)


if __name__ == "__main__":
    main()
