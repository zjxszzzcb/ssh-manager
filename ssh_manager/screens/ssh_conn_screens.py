import os
from typing import Dict

from textual import on, events
from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Button, DataTable, Footer, Label
from textual.containers import Vertical, Center, VerticalScroll, Horizontal

from ssh_manager.widgets.proxy_table import ProxyManageTable
from ssh_manager.widgets.add_forward_modal import AddPortForwardModal
from ssh_manager.utils.ssh_configs import HostConfig
from ssh_manager.utils.ssh_util import create_persistent_ssh_connection
from ssh_manager.utils.terminal_util import open_new_terminal, CLEAR_COMMAND


def create_ascii_table(data: list[tuple[str, str, str]]) -> str:
    """
    Create an ASCII table from a list of (icon, label, value) tuples.
    Using fixed character positions to ensure perfect alignment.
    Total width: 70 characters (display width)
    """
    lines = []

    # Fixed borders - exactly 70 display chars
    border_top =    "┌──────────────────────────────────┬──────────────────────────────────┐"
    border_middle = "├──────────────────────────────────┼──────────────────────────────────┤"
    border_bottom = "└──────────────────────────────────┴──────────────────────────────────┘"

    lines.append(border_top)

    for i, (icon, label, value) in enumerate(data):
        # Build each row to be exactly 70 display chars
        # Left column: 35 chars (including border)
        # Middle border: 1 char
        # Right column: 34 chars (including border)

        # Create left content with icon and label
        left_content = f" {icon} {label}"

        # Calculate padding needed (emoji displays as 2 chars but len() counts as 1)
        # So we need to subtract 1 extra space for the emoji
        left_padding = 34 - len(left_content) - 1  # -1 for emoji display width
        left_side = "│" + left_content + " " * left_padding

        # Create right content
        right_padding = 33 - len(value)
        right_side = "│" + " " * right_padding + value + " │"

        row = left_side + right_side
        lines.append(row)

        # Add separator between rows (except after the last row)
        if i < len(data) - 1:
            lines.append(border_middle)

    lines.append(border_bottom)

    return "\n".join(lines)


class SSHConnScreen(Screen):
    """SSH connection interface"""

    CSS = """
    Screen {
        background: #161b22;
        color: #e6edf3;
    }

    Center {
        background: #161b22;
    }

    Middle {
        background: #161b22;
    }

    VerticalScroll {
        height: 100%;
    }

    #content_container {
        background: #161b22;
        width: 80;
        height: auto;
        margin: 1 2 2 2;  /* top: 1, right: 2, bottom: 2, left: 2 */
    }

    #host_info_table {
        width: 100%;
        height: auto;
        background: #161b22;
        color: #e6edf3;
        margin: 0 0 1 0;  /* Small bottom margin */
        padding: 0;
        border: none;
        text-align: center;
    }

    .table-width-button {
        width: 73;  /* Same width as the ASCII table (73 chars) */
        margin: 0 0 1 0;  /* Small bottom margin for spacing between buttons */
        background: #1f6feb;
        color: #ffffff;
        border: tall transparent;
        align: center middle;
    }

    Button {
        background: #1f6feb;
        color: #ffffff;
        border: tall transparent;
        align: center middle;
    }

    Button:focus {
        background: #238636;
    }

    ProxyManageTable {
        height: auto;
        min-height: 10;
        max-height: 20;
        margin: 0;
        background: #161b22;
        overflow-x: hidden;
        scrollbar-size-horizontal: 0;
    }

    #port_forwards_table {
        height: auto;
        min-height: 10;
        max-height: 20;
        margin-bottom: 2;
    }

    DataTable {
        border: tall #21262d;
        background: #161b22;
        overflow-x: hidden;
        scrollbar-size-horizontal: 0;
    }

    DataTable:focus {
        border: tall #1f6feb;
    }

    Input {
        background: #161b22;
        color: #e6edf3;
        border: round #21262d;
    }

    Input:focus {
        border: round #1f6feb;
    }

    #port_forwarding_header {
        width: 100%;
        height: auto;
        align: center middle;
        margin: 0;
    }

    #port_forwarding_label {
        width: auto;
        height: 1;
        text-align: center;
        background: #161b22;
        color: #7fb069;
        margin: 0;
        padding: 0;
        border: none;
        content-align: center middle;
        text-style: bold;
    }

    #add_forward_btn {
        width: 3;
        height: 1;
        min-width: 3;
        background: #238636;
        color: #ffffff;
        border: none;
        margin-left: 1;
        padding: 0;
    }

    #add_forward_btn:hover {
        background: #2ea043;
    }
    """

    BINDINGS = [
        # Binding("up", "cursor_up", "Up", show=False),
        # Binding("down", "cursor_down", "Down", show=False),
        Binding("escape", "app.pop_screen", "Quit", show=True),
    ]

    def __init__(self, host_config: HostConfig):
        print("[DEBUG] Initializing SSHConnScreen")
        super().__init__()
        self.host_config = host_config
        print(f"[DEBUG] SSHConnScreen initialized with host: {host_config.host}")
        self.set_interval(1/5, self.monitor_proxy_table, name="monitor_proxy_table")

    def compose(self) -> ComposeResult:
        print("[DEBUG] SSHConnScreen compose called")

        # Merge local and remote forwards into a unified list
        # Column order: #, Listen Port, Listen Host, Target Port, Target Host, Type
        port_forwards = []

        # Process local forwards
        for local_port, forward_address in self.host_config.local_forwards.items():
            target_host, target_port = forward_address.split(":")
            # LocalForward: listen on local local_port, forward to remote target_host:target_port
            # Check if local_port includes bind address (e.g., "0.0.0.0:3000")
            if ':' in local_port and not local_port.isdigit():
                bind_address, listen_port = local_port.rsplit(':', 1)
                port_forwards.append(("", listen_port, bind_address, target_port, target_host, "Local"))
            else:
                # Simple port number without bind address
                port_forwards.append(("", local_port, "127.0.0.1", target_port, target_host, "Local"))

        # Process remote forwards
        for remote_port, local_address in self.host_config.remote_forwards.items():
            local_host, local_port = local_address.split(":")
            # RemoteForward: listen on remote remote_port, forward to local local_host:local_port
            port_forwards.append(("", remote_port, "127.0.0.1", local_port, local_host, "Remote"))

        print(f"[DEBUG] Port forwards: {port_forwards}")

        with VerticalScroll():
            with Center():
                with Vertical(id="content_container"):
                    # Prepare data for the ASCII table
                    table_data = [
                        ("⚡", "SSH Connection", self.host_config.host),
                        ("🌐", "Host", self.host_config.hostname),
                        ("📍", "Port", str(self.host_config.port)),
                    ]

                    if self.host_config.user:
                        table_data.append(("👤", "User", self.host_config.user))

                    if self.host_config.password:
                        # Show the actual password
                        table_data.append(("🔑", "Password", self.host_config.password))

                    # Create and display the ASCII table
                    table_text = create_ascii_table(table_data)
                    yield Label(table_text, id="host_info_table")

                    # Buttons with same width as table, centered and stacked vertically
                    with Center():
                        yield Button("🔌 Connect Shell", id="connect_shell", classes="table-width-button")
                    with Center():
                        yield Button("🚀 New Shell", id="new_shell", classes="table-width-button")

                    # Unified port forwarding table with add button
                    with Horizontal(id="port_forwarding_header"):
                        yield Label("🔗 Port Forwarding", id="port_forwarding_label")
                        yield Button("+", id="add_forward_btn")
                    port_table = ProxyManageTable(port_forwards, id="port_forwards_table")
                    port_table.can_focus = True
                    yield port_table

        yield Footer()

    def on_mount(self) -> None:
        """Initialize interface"""
        print("[DEBUG] SSHConnUI on_mount")
        self.query_one("#connect_shell", Button).focus()
        # Ensure table can get focus
        port_table = self.query_one("#port_forwards_table", ProxyManageTable)
        port_table.can_focus = True
        port_table.data_table.can_focus = True
    
    def on_key(self, event: events.Key) -> None:
        if event.key == "up":
            if self.cursor_up():
                # If we handled this event, prevent it from propagating
                event.stop()
        elif event.key == "down":
            if self.cursor_down():
                # If we handled this event, prevent it from propagating
                event.stop()
    
    def cursor_up(self) -> bool:
        """Handle up key: navigate between buttons, add button, and table"""
        new_shell_button = self.query_one("#new_shell", Button)
        connect_shell_button = self.query_one("#connect_shell", Button)
        add_forward_btn = self.query_one("#add_forward_btn", Button)
        port_table = self.query_one("#port_forwards_table", ProxyManageTable).query_one(DataTable)

        if port_table.has_focus:
            # If table has focus and cursor is on first row, switch to add button
            if port_table.cursor_row == 0:
                add_forward_btn.focus()
                return True
            return False
        elif add_forward_btn.has_focus:
            # From add button switch to new_shell button
            new_shell_button.focus()
            return True
        elif new_shell_button.has_focus:
            # From new_shell button switch to connect_shell button
            connect_shell_button.focus()
            return True
        else:
            return False

    def cursor_down(self) -> bool:
        """Handle down key: navigate between buttons, add button, and table"""
        new_shell_button = self.query_one("#new_shell", Button)
        connect_shell_button = self.query_one("#connect_shell", Button)
        add_forward_btn = self.query_one("#add_forward_btn", Button)
        port_table = self.query_one("#port_forwards_table", ProxyManageTable).query_one(DataTable)

        if connect_shell_button.has_focus:
            # From connect_shell button switch to new_shell button
            new_shell_button.focus()
            return True
        elif new_shell_button.has_focus:
            # From new_shell button switch to add button
            add_forward_btn.focus()
            return True
        elif add_forward_btn.has_focus:
            # From add button switch to table
            port_table.focus()
            if port_table.row_count > 0:
                port_table.move_cursor(row=0, column=1, animate=False)
            return True
        return False

    def monitor_proxy_table(self) -> None:
        """Monitor proxy table"""
        # print("[DEBUG] Monitoring proxy table")

        # Monitor unified port forwarding table
        port_table = self.query_one("#port_forwards_table", ProxyManageTable).query_one(DataTable)
        local_forwards: Dict[str, str] = {}
        remote_forwards: Dict[str, str] = {}

        for row_key in port_table.rows.keys():
            row_data = port_table.get_row(row_key)
            # Data format: (Row#, Listen Port, Listen Host, Target Port, Target Host, Type)
            if len(row_data) < 6:
                continue

            _, listen_port, listen_host, target_port, target_host, forward_type = row_data[:6]

            # Validate port numbers
            if not listen_port:
                continue
            try:
                int(listen_port)
            except ValueError:
                self.notify("Invalid listen port", severity="error", timeout=0.2)
                continue

            if not target_port:
                continue
            try:
                int(target_port)
            except ValueError:
                self.notify("Invalid target port", severity="error", timeout=0.2)
                continue

            # Check required fields
            if not all([listen_port, target_port, target_host]):
                continue

            # Distribute to different dictionaries based on type
            if forward_type == "Local":
                # LocalForward: listen on local listen_port, forward to remote target_host:target_port
                # Check if listen_host is not the default (127.0.0.1) and construct full binding address
                if listen_host != "127.0.0.1":
                    local_forwards[f"{listen_host}:{listen_port}"] = f"{target_host}:{target_port}"
                else:
                    local_forwards[listen_port] = f"{target_host}:{target_port}"
            elif forward_type == "Remote":
                # RemoteForward: listen on remote listen_port, forward to local target_host:target_port
                # For remote forwards, we don't need to handle bind addresses specially
                remote_forwards[listen_port] = f"{target_host}:{target_port}"

        # Check if configuration has changed
        config_changed = False
        if local_forwards != self.host_config.local_forwards:
            print(f"[INFO] Old local forwards: {self.host_config.local_forwards}")
            print(f"[INFO] New local forwards: {local_forwards}")
            self.host_config.local_forwards = local_forwards
            config_changed = True

        if remote_forwards != self.host_config.remote_forwards:
            print(f"[INFO] Old remote forwards: {self.host_config.remote_forwards}")
            print(f"[INFO] New remote forwards: {remote_forwards}")
            self.host_config.remote_forwards = remote_forwards
            config_changed = True

        if config_changed:
            print("[INFO] Host configs have changed, updating SSH connection")
            with self.app.suspend():
                connection = create_persistent_ssh_connection(self.host_config)
            if connection is None:
                self.notify("Failed to create new SSH connection", severity="error", timeout=1)
            else:
                self.notify(f"SSH connection updated successfully", timeout=1)

    @on(Button.Pressed, "#add_forward_btn")
    def show_add_forward_modal(self) -> None:
        """Show modal dialog to add a new port forward rule."""
        self.app.push_screen(AddPortForwardModal(), callback=self._on_modal_dismiss)

    def _on_modal_dismiss(self, result) -> None:
        """Handle modal dismiss with result."""
        if result:
            self._add_forward_from_modal(result)
        
        # Focus on table after modal closes
        self._focus_table_last_row()

    def _focus_table_last_row(self) -> None:
        """Focus on the table and highlight the last row."""
        port_table = self.query_one("#port_forwards_table", ProxyManageTable)
        data_table = port_table.query_one(DataTable)
        data_table.focus()
        if data_table.row_count > 0:
            # Move cursor to last row, second column (skip row number)
            data_table.move_cursor(row=data_table.row_count - 1, column=1, animate=False)

    def _add_forward_from_modal(self, data: dict) -> None:
        """Add a port forward rule from modal dialog result."""
        port_table = self.query_one("#port_forwards_table", ProxyManageTable)

        # Create new row data: Row#, Listen Port, Listen Host, Target Port, Target Host, Type
        new_row_number = len(port_table.table_data)
        new_row = [
            str(new_row_number),
            data["listen_port"],
            data["listen_host"],
            data["target_port"],
            data["target_host"],
            data["type"],
        ]

        # Add to table
        port_table.table_data.append(list(new_row))
        port_table.data_table.add_row(*new_row)

        # Notify user
        self.notify(f"Added {data['type']} forward: {data['listen_port']} → {data['target_host']}:{data['target_port']}", timeout=2)

    @on(Button.Pressed, "#new_shell")
    def new_shell(self) -> None:
        """Open SSH terminal"""
        print("[DEBUG] New shell button clicked")
        ssh_command = self.host_config.get_ssh_command()
        print(f"[DEBUG] Generated SSH command: {ssh_command}")
        open_new_terminal(ssh_command)

    @on(Button.Pressed, "#connect_shell")
    def connect_shell(self) -> None:
        """Connect SSH directly in current terminal"""
        with self.app.suspend():
            os.system(CLEAR_COMMAND)
            command = ' '.join(self.host_config.get_ssh_command())
            print(f"> {command}")
            os.system(command)
            os.system(CLEAR_COMMAND)


# This standalone section needs to be modified to use App to wrap Screen
def view_ssh_conn_ui():
    from textual.app import App
    
    class TestApp(App):
        
        def on_mount(self):
            host_config = HostConfig(
                host="demo-server-1",
                hostname="server1.example.com",
                user="user1",
                password="password1",
                local_forwards={
                    "8080": "localhost:80",
                    "3306": "db.internal:3306",
                },
                remote_forwards={
                    "9000": "localhost:9000",
                    "5432": "localhost:5432",
                }
            )
            self.install_screen(SSHConnScreen(host_config), name="ssh_conn")
            # After installing screen, need to push screen to make it visible
            self.push_screen("ssh_conn")

    app = TestApp()
    app.run()


if __name__ == "__main__":
    view_ssh_conn_ui()
