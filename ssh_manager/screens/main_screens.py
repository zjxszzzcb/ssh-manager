import logging

from textual import on
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.containers import Horizontal, Vertical
from textual.widgets import ListView, Footer, Label
from textual.binding import Binding
from typing import Dict, List, Optional

from ssh_manager.widgets.editor import HostConfigEditor
from ssh_manager.widgets.host_list import HostListItem
from ssh_manager.utils.ssh_configs import (
    HostConfig, update_host_config, parse_text_to_configs,
    remove_host_config, get_ssh_config_example
)
from ssh_manager.utils.ssh_util import SSHConnection, create_persistent_ssh_connection, get_ssh_connection

logger = logging.getLogger("MainScreen")


class SSHManageMainScreen(Screen):
    """SSH Manager main interface
    
    Args:
        host_configs: host configurations list
        selected: initially selected host config, defaults to first item if None
    """

    BINDINGS = [
        # Hide up/down key hints as they are common operations
        Binding("up", "cursor_up", "Move cursor up", show=False),
        Binding("down", "cursor_down", "Move cursor down", show=False),
        
        # Show editor and exit shortcut hints
        Binding("e", "focus_editor", "Edit", show=True),
        Binding("c", "connect", "Connect", show=True),
        
        # Hide other shortcut hints
        Binding("ctrl+s", "save_config", "Save config", show=True),
        Binding("ctrl+d", "delete_config", "Delete config"),
        Binding("ctrl+n", "new_config", "New config"),
    ]

    CSS = """
    Screen {
        background: #161b22;
        color: #e6edf3;
    }

    Horizontal {
        height: 1fr;
        background: #161b22;
    }

    #host_list_area {
        width: 50%;
        background: #161b22;
    }

    #editor_area {
        width: 50%;
        background: #161b22;
    }

    #host_list_label, #editor_label {
        width: 100%;
        height: 1;
        text-align: center;
        background: #161b22;
        color: #ffb366;
        margin: 0 1 0 1;
        padding: 0;
        border: none;
        content-align: center middle;
        text-style: bold;
    }

    ListView {
        width: 100%;
        border: solid #21262d;
        scrollbar-gutter: stable;
        padding: 0 1;
        background: #161b22;
        margin: 0 1;
    }

    HostConfigEditor {
        width: 100%;
        height: 1fr;
        border: solid #238636;
        background: #161b22;
        margin: 0 1 0 0;
    }

    ListView:focus {
        border: solid #1f6feb;
    }

    HostConfigEditor:focus {
        border: solid #1f6feb;
    }

    Footer {
        background: #161b22;
        color: #e6edf3;
        height: 1;
    }
    """

    def __init__(self, host_configs: Optional[List[HostConfig]] = None, selected: Optional[HostConfig] = None):
        super().__init__()

        self.host_configs: List[HostConfig] = host_configs or []
        self._initial_selected_config: Optional[HostConfig] = selected
        # host_alias -> SSHConnection
        self.connections: Dict[str, SSHConnection] = dict()

    def compose(self) -> ComposeResult:
        # Create horizontal layout
        with Horizontal():
            # Left host list area
            with Vertical(id="host_list_area"):
                yield Label("🚀  SSH Hosts", id="host_list_label")
                list_view = ListView()
                list_view.can_focus = True
                yield list_view
            
            # Right configuration editor area
            with Vertical(id="editor_area"):
                yield Label("🔧  Configuration Editor", id="editor_label")
                editor = HostConfigEditor(self.host_configs[0] if self.host_configs else None)
                editor.can_focus = True  # Allow editor to get focus
                yield editor
        
        # Add bottom shortcut hints
        yield Footer()

    def on_mount(self) -> None:
        """Add list items when app is mounted"""
        list_view = self.query_one(ListView)
        
        # Add host list items
        if self.host_configs:
            for config in self.host_configs:
                list_view.append(HostListItem(config))

            # Set initial focus to list view
            list_view.focus()
            
            # Determine initial selected index position
            initial_index = 0
            if self._initial_selected_config:
                # Find specified config position in list
                for i, config in enumerate(self.host_configs):
                    if config.host == self._initial_selected_config.host:
                        initial_index = i
                        break
            
            # Set list selection position
            list_view.index = initial_index

            # Update editor to show corresponding config
            self.update_editor(self.host_configs[initial_index].to_text())

        # Set timer to update connection status every second
        self.set_interval(1.0, self.update_connection_status)

    def update_connection_status(self):
        list_view = self.query_one(ListView)
        for idx in range(len(list_view.children)):
            host_item = list_view.children[idx]
            assert isinstance(host_item, HostListItem)
            connection = self.connections.get(host_item.host_info.host)
            is_alive = connection.is_alive() if isinstance(connection, SSHConnection) else False
            host_item.host_info.is_alive = is_alive
            host_item.update_status()

    def update_editor(self, text: str):
        """Update editor content"""
        editor = self.query_one(HostConfigEditor)
        editor.load_text(text)

    def update_selected_item(self, config: HostConfig):
        list_view = self.query_one(ListView)

        selected_item = self.get_selected_item()
        if not selected_item:
            return

        selected_item.host_info = selected_item.host_info.update_config(config)
        selected_item.update_status()
        self.host_configs[list_view.index] = selected_item.host_info
    
    def get_selected_host_config(self) -> Optional[HostConfig]:
        selected_item = self.get_selected_item()
        if selected_item is None:
            return None
        return selected_item.host_info or None

    def get_selected_item(self) -> Optional[HostListItem]:
        list_view = self.query_one(ListView)
        items = list_view.children
        index = list_view.index
        if items and 0 <= index < len(items):
            item = list_view.children[list_view.index]
            assert isinstance(item, HostListItem)
            return item
        else:
            return None
    
    def create_connection(self, auto_mode: bool = False) -> bool:
        """Create SSH connection.

        Args:
            auto_mode: If True, test key auth and prompt for upload; if False, direct connection with timeout

        Returns:
            bool: True if connection successful, False otherwise
        """
        logger.info("action_connect triggered")
        host_config = self.get_selected_host_config()
        if not host_config:
            return False

        logger.info(f"Creating connection for host: {host_config.host}")

        exist_connection = get_ssh_connection(host_config.host)
        if exist_connection and exist_connection.is_alive():
            return True

        if auto_mode:
            # Auto mode: test key auth, prompt for upload if needed
            return self._create_connection_with_key_check(host_config)
        else:
            # Manual mode: direct connection with timeout
            return self._create_connection_direct(host_config)

    def _create_connection_direct(self, host_config: HostConfig) -> bool:
        """Manual mode: direct connection attempt with fast timeout.

        Args:
            host_config: Host configuration

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Direct connection attempt, 10 second timeout
            with self.app.suspend():
                connection = create_persistent_ssh_connection(
                    host_config,
                    key_check=False,  # Skip key check for fast connection
                    timeout=10
                )

            if connection:
                self.connections[host_config.host] = connection
                return True
            else:
                self.notify("Connection failed", severity="error")
                return False
        except TimeoutError:
            self.notify("Connection timeout (10s)", severity="error")
            return False
        except Exception as e:
            self.notify(f"Connection error: {e}", severity="error")
            return False

    def _create_connection_with_key_check(self, host_config: HostConfig) -> bool:
        """Auto mode: test key auth and prompt for upload if needed.

        Args:
            host_config: Host configuration

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Create connection with key check and upload prompt
            with self.app.suspend():
                connection = create_persistent_ssh_connection(
                    host_config,
                    key_check=True  # Enable key check and upload prompt
                )

            if connection:
                self.connections[host_config.host] = connection
                return True
            else:
                self.notify("Connection failed", severity="error")
                return False
        except Exception as e:
            self.notify(f"Connection error: {e}", severity="error")
            return False
        
    def cleanup_connections(self):
        for connection in self.connections.values():
            if isinstance(connection, SSHConnection):
                connection.terminate()
                connection.wait()
        self.connections.clear()

    @on(ListView.Highlighted)
    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update editor when list item is highlighted"""
        item = event.item
        assert isinstance(item, HostListItem)
        self.update_editor(item.host_info.to_text())

    def action_cursor_up(self) -> None:
        """Move cursor up"""
        list_view = self.query_one(ListView)
        if list_view.has_focus and list_view.index > 0:
            list_view.index -= 1

    def action_cursor_down(self) -> None:
        """Move cursor down"""
        list_view = self.query_one(ListView)
        if list_view.has_focus and list_view.index < len(list_view.children) - 1:
            list_view.index += 1

    def action_focus_editor(self) -> None:
        """Move focus to editor"""
        editor = self.query_one(HostConfigEditor)
        if not editor.has_focus:
            editor.focus()

    def action_focus_list(self) -> None:
        """Move focus back to list"""
        list_view = self.query_one(ListView)
        list_view.focus()

    def action_new_config(self) -> None:
        """Create a new config"""
        example_config = get_ssh_config_example()
        self.host_configs.append(example_config)
        update_host_config(example_config)

        new_item = HostListItem(example_config)
        list_view = self.query_one(ListView)
        list_view.append(new_item)
        list_view.focus()
        list_view.index = len(list_view.children) - 1
        self.update_editor(new_item.host_info.to_text())

    def action_save_config(self) -> None:
        """Save current config in editor"""
        editor = self.query_one(HostConfigEditor)
        if editor.has_cursor():
            # Parse config from editor text
            selected_config_old = self.get_selected_host_config()
            new_config = list(parse_text_to_configs(editor.text).values())[0]
            for known_host_config in self.host_configs:
                if selected_config_old.to_text() == known_host_config.to_text():
                    continue
                if known_host_config.host == new_config.host:
                    self.notify(f"Host {known_host_config.host} already exists.", severity="error")
                    self.update_editor(selected_config_old.to_text())
                    return
            self.update_selected_item(new_config)
            # Update config
            update_host_config(new_config)
            # Move focus back to list
            self.action_focus_list()

    def action_delete_config(self) -> None:
        """Delete currently selected config"""
        list_view = self.query_one(ListView)
        if list_view.has_focus and list_view.children:
            remove_host_config(self.host_configs[list_view.index].host)
            self.host_configs.pop(list_view.index)
            selected_item = list_view.children[list_view.index]
            selected_item.remove()
            self.action_focus_list()
            list_view.index = min(list_view.index, len(list_view.children) - 1)

    def quit(self) -> None:
        list_view = self.query_one(ListView)
        editor = self.query_one(HostConfigEditor)
        if editor.has_cursor():
            list_view.focus()
        else:
            self.cleanup_connections()
            self.app.exit()


def view_main_ui():
    # Example usage
    demo_configs = [
        HostConfig(
            host="demo-server-1",
            hostname="server1.example.com",
            user="admin",
            port=22,
        ),
        HostConfig(
            host="demo-server-2",
            hostname="server2.example.com",
            user="admin",
            port=22,
        ),
    ]

    class MainApp(App):
        def on_mount(self):
            self.install_screen(SSHManageMainScreen(demo_configs), name="main")
            self.push_screen("main")

    app = MainApp()
    app.run()


if __name__ == "__main__":
    view_main_ui()
