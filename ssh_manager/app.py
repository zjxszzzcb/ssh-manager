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

    def __init__(self, host_configs: List[HostConfig], selected_config: HostConfig = None, auto_connect: bool = False):

        super().__init__()

        self.main_screen = SSHManageMainScreen(host_configs, selected=selected_config)
        self.auto_connect = auto_connect  # Whether to auto-connect on mount

    def on_mount(self):
        self.install_screen(self.main_screen, name="main_screen")
        self.push_screen("main_screen")

        # Trigger auto-connect if enabled
        # Use call_later to ensure ListView is fully mounted first
        if self.auto_connect:
            self.call_later(self._check_and_auto_connect)

    def _check_and_auto_connect(self) -> None:
        """Check if host is selected and trigger auto-connect."""
        if self.main_screen.get_selected_host_config():
            self._auto_connect()

    def _auto_connect(self) -> None:
        """Auto-connect to the selected host."""
        if self.main_screen.create_connection(auto_mode=True):
            host_config = self.main_screen.get_selected_host_config()
            self.push_screen(SSHConnScreen(host_config))

    def on_key(self, event: events.Key) -> None:
        """Handle key events"""
        print(f"[DEBUG] Main App Detect Key pressed: {event.key}")
        if event.key == "enter" and self.screen_stack[-1] == self.main_screen:
            self.action_connect()

    def action_connect(self) -> None:
        if self.main_screen.create_connection():
            host_config = self.main_screen.get_selected_host_config()
            self.push_screen(SSHConnScreen(host_config))

    def action_quit(self) -> None:
        """Exit the application, but only when the editor doesn't have focus"""
        if self.screen_stack[-1] == self.main_screen:
            self.main_screen.quit()


class EditorSSHConfigApp(App):
    """A simple Textual app to display the two-editor screen."""

    BINDINGS = [Binding("escape", "quit", "Quit", show=True)]

    def on_mount(self) -> None:
        """Called when the app is first mounted."""
        # When the app starts, we immediately push the TwoEditorsScreen onto the display stack.
        self.push_screen(EditSSHConfigScreen())


def handle_init_command():
    """Handle the 'init' subcommand to initialize SSH config."""
    host_configs_map = load_ssh_config_file()
    if not host_configs_map:
        print("No SSH hosts found in ~/.ssh/config")
        return

    for host, config in host_configs_map.items():
        update_host_config(config)
        print(f"Initialized SSH config for {host}")

    print(f"\nTotal {len(host_configs_map)} hosts initialized successfully.")


def handle_config_command():
    """Handle the 'config' subcommand to open configuration editor."""
    app = EditorSSHConfigApp()
    app.run()


def handle_ssh_command(args):
    """Handle the 'ssh' subcommand for SSH connection management."""
    from ssh_manager.utils.ssh_util import test_ssh_key_auth, upload_ssh_key_with_ssh
    import time

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

            # Direct SSH mode: test key auth and connect directly to shell
            print(f"[INFO] Connecting to {cmd_host_config.host} ({cmd_host_config.user}@{cmd_host_config.hostname}:{cmd_host_config.port})...")

            # Test key authentication
            success, message = test_ssh_key_auth(cmd_host_config)

            if not success:
                # Key auth failed - ask user if they want to upload key
                print(f"[ERROR] {message}")
                print(f"\n[INFO] Would you like to upload your SSH public key?")
                print(f"[INFO] This will require password authentication for one-time setup.")

                choice = input("Upload key now? [y/N]: ").strip().lower()

                if choice == 'y':
                    # Upload key
                    print(f"\n[INFO] Uploading SSH key to {cmd_host_config.host}...")
                    upload_success, upload_message = upload_ssh_key_with_ssh(cmd_host_config)

                    if not upload_success:
                        print(f"[ERROR] Key upload failed: {upload_message}")
                        return

                    print(f"[INFO] Key uploaded successfully!")
                    print(f"[INFO] Waiting for server to process the new key...")
                    time.sleep(2)

                    # Retry key auth test
                    success, message = test_ssh_key_auth(cmd_host_config)

                    if not success:
                        print(f"[ERROR] Key authentication still fails after upload: {message}")
                        return

            # Key auth successful, connect directly to shell
            print(f"[INFO] Starting SSH session...")
            ssh_cmd = cmd_host_config.get_ssh_command()
            import subprocess
            result = subprocess.run(ssh_cmd)
            print(f"\n[INFO] SSH session ended (exit code: {result.returncode})")
            return

    # No target specified - launch TUI application
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

    # Create subparsers for commands (not required - allows unknown args)
    subparsers = parser.add_subparsers(
        dest='command',
        required=False,
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
    subparsers.add_parser(
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

    # Parse arguments with known args to capture potential host argument
    # Try normal parsing first
    try:
        args, unknown_args = parser.parse_known_args()
    except SystemExit as e:
        # Parsing failed - check if this is a quick connect attempt
        import sys
        from ssh_manager.utils.terminal_util import open_new_terminal
        
        argv = sys.argv[1:]
        
        # Filter out log-level arguments
        filtered_args = [arg for arg in argv if not arg.startswith('--log-level') 
                         and arg not in ['debug', 'info', 'warning', 'error']]
        
        # Check if it's a single non-option argument (potential host alias)
        if filtered_args and len(filtered_args) == 1 and not filtered_args[0].startswith('-'):
            host_alias = filtered_args[0]
            
            # Try to load and connect to the host
            host_configs_map = load_known_ssh_hosts()
            if host_alias in host_configs_map:
                # Found matching host - execute SSH connection directly
                host_config = host_configs_map[host_alias]
                ssh_command = host_config.get_ssh_command()
                print(f"Connecting to {host_alias}...")
                open_new_terminal(ssh_command)
                return
            else:
                # Host not found - show error
                print(f"Error: Unknown host '{host_alias}'")
                print(f"Use 'mssh init' to load hosts from ~/.ssh/config")
                print(f"Or use 'mssh ssh user@host' to connect to a new host")
                return
        
        # Not a quick connect - re-raise the original error
        raise e

    # Set up logging
    if args.log_level:
        logging.basicConfig(
            level=getattr(logging, args.log_level.upper()),
            handlers=[TextualHandler()]
        )

    # Handle known subcommands
    if args.command == 'init':
        handle_init_command()
        return
    elif args.command == 'config':
        handle_config_command()
        return
    elif args.command == 'ssh':
        handle_ssh_command(args)
        return

    # No subcommand provided - check for quick connect (single unknown arg = host alias)
    if unknown_args and len(unknown_args) == 1 and not unknown_args[0].startswith('-'):
        from ssh_manager.utils.terminal_util import open_new_terminal
        host_alias = unknown_args[0]
        
        # Try to load and connect to the host
        host_configs_map = load_known_ssh_hosts()
        if host_alias in host_configs_map:
            # Found matching host - execute SSH connection directly
            host_config = host_configs_map[host_alias]
            ssh_command = host_config.get_ssh_command()
            print(f"Connecting to {host_alias}...")
            open_new_terminal(ssh_command)
            return
        else:
            # Host not found in known hosts
            print(f"Error: Unknown host '{host_alias}'")
            print(f"Use 'mssh init' to load hosts from ~/.ssh/config")
            print(f"Or use 'mssh ssh {host_alias}' to connect to a new host")
            return

    # Default behavior: launch SSH management interface
    ssh_args = argparse.Namespace(
        target=None,
        port=None,
        proxy_jump=None
    )

    if unknown_args:
        # Try to parse unknown args as SSH command
        if unknown_args[0] != 'ssh':
            unknown_args = ['ssh'] + unknown_args

        cmd_host_config = parse_ssh_command(unknown_args)
        if cmd_host_config:
            ssh_args.target = f"{cmd_host_config.user}@{cmd_host_config.host}" if cmd_host_config.user else cmd_host_config.host
            ssh_args.port = cmd_host_config.port

    handle_ssh_command(ssh_args)


if __name__ == "__main__":
    main()
