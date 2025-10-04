import os
from typing import Dict

from textual import on, events
from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Button, DataTable, Footer, Label
from textual.containers import Vertical, Center, Middle, VerticalScroll, Horizontal

from ssh_manager.widgets.proxy_table import ProxyManageTable
from ssh_manager.utils.ssh_configs import HostConfig
from ssh_manager.utils.ssh_util import create_persistent_ssh_connection
from ssh_manager.utils.terminal_util import open_new_terminal, CLEAR_COMMAND


def create_ascii_table(data: list[tuple[str, str, str]]) -> str:
    """
    Create an ASCII table from a list of (icon, label, value) tuples.
    Using fixed character positions to ensure perfect alignment.
    """
    lines = []

    # Fixed borders - these will always align
    border_top =    "┌──────────────────────────┬──────────────────────────┐"
    border_middle = "├──────────────────────────┼──────────────────────────┤"
    border_bottom = "└──────────────────────────┴──────────────────────────┘"

    lines.append(border_top)

    for i, (icon, label, value) in enumerate(data):
        # Build the row with exact spacing
        # Left side: icon + label (fixed positions)
        # Right side: value (right-aligned)

        # Format based on known labels for consistent spacing
        if "SSH Connection" in label:
            row = f"│ {icon} SSH Connection        │{value:>25} │"
        elif "Host" in label:
            row = f"│ {icon} Host                  │{value:>25} │"
        elif "Port" in label:
            row = f"│ {icon} Port                  │{value:>25} │"
        elif "User" in label:
            row = f"│ {icon} User                  │{value:>25} │"
        elif "Password" in label:
            row = f"│ {icon} Password              │{value:>25} │"
        else:
            # Generic formatting for unknown labels
            label_padded = label[:20].ljust(20)
            row = f"│ {icon} {label_padded} │{value:>25} │"

        lines.append(row)

        # Add separator between rows (except after the last row)
        if i < len(data) - 1:
            lines.append(border_middle)

    lines.append(border_bottom)

    return "\n".join(lines)


class SSHConnScreen(Screen):
    """SSH 连接界面"""

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
        width: 70;  /* Same width as the ASCII table (70 chars) */
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

    #port_forwarding_label {
        width: 100%;
        height: 1;
        text-align: center;
        background: #161b22;
        color: #7fb069;
        margin: 0;  /* No margin to reduce space between label and table */
        padding: 0;
        border: none;
        content-align: center middle;
        text-style: bold;
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

        # 合并本地和远程转发到一个统一的列表
        # 列顺序: #, Listen Port, Listen Host, Target Port, Target Host, Type
        port_forwards = []

        # 处理本地转发
        for local_port, forward_address in self.host_config.local_forwards.items():
            target_host, target_port = forward_address.split(":")
            # LocalForward: 监听本地local_port，转发到远程target_host:target_port
            port_forwards.append(("", local_port, "127.0.0.1", target_port, target_host, "Local"))

        # 处理远程转发
        for remote_port, local_address in self.host_config.remote_forwards.items():
            local_host, local_port = local_address.split(":")
            # RemoteForward: 监听远程remote_port，转发到本地local_host:local_port
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

                    # 单一的端口转发表格
                    yield Label("🔗 Port Forwarding", id="port_forwarding_label")
                    port_table = ProxyManageTable(port_forwards, id="port_forwards_table")
                    port_table.can_focus = True
                    yield port_table

        yield Footer()

    def on_mount(self) -> None:
        """初始化界面"""
        print("[DEBUG] SSHConnUI on_mount")
        self.query_one("#connect_shell", Button).focus()
        # 确保表格可以获得焦点
        port_table = self.query_one("#port_forwards_table", ProxyManageTable)
        port_table.can_focus = True
        port_table.data_table.can_focus = True
    
    def on_key(self, event: events.Key) -> None:
        if event.key == "up":
            if self.cursor_up():
                # 如果我们处理了这个事件，阻止它继续传播
                event.stop()
        elif event.key == "down":
            if self.cursor_down():
                # 如果我们处理了这个事件，阻止它继续传播
                event.stop()
    
    def cursor_up(self) -> bool:
        """处理向上键：在表格内部导航，当在表格第一行时切换到按钮"""
        new_shell_button = self.query_one("#new_shell", Button)
        connect_shell_button = self.query_one("#connect_shell", Button)
        port_table = self.query_one("#port_forwards_table", ProxyManageTable).query_one(DataTable)

        if port_table.has_focus:
            # 如果表格有焦点且光标在第一行，切换到 new_shell 按钮
            if port_table.cursor_row == 0:
                new_shell_button.focus()
                return True
            return False
        elif new_shell_button.has_focus:
            # 如果 new_shell 按钮有焦点，切换到 connect_shell 按钮
            connect_shell_button.focus()
            return True
        else:
            print("no widget has focus for up navigation")
            return False

    def cursor_down(self) -> bool:
        """处理向下键：从按钮切换到表格"""
        new_shell_button = self.query_one("#new_shell", Button)
        connect_shell_button = self.query_one("#connect_shell", Button)
        port_table = self.query_one("#port_forwards_table", ProxyManageTable).query_one(DataTable)

        if connect_shell_button.has_focus:
            # 从 connect_shell 按钮切换到 new_shell 按钮
            new_shell_button.focus()
            return True
        elif new_shell_button.has_focus:
            # 从 new_shell 按钮切换到表格
            port_table.focus()
            # 确保表格光标在第一行第二列（跳过行号列）
            if port_table.row_count > 0:
                port_table.move_cursor(row=0, column=1, animate=False)
            return True
        return False

    def monitor_proxy_table(self) -> None:
        """监控代理表"""
        # print("[DEBUG] Monitoring proxy table")

        # 监控统一的端口转发表格
        port_table = self.query_one("#port_forwards_table", ProxyManageTable).query_one(DataTable)
        local_forwards: Dict[str, str] = {}
        remote_forwards: Dict[str, str] = {}

        for row_key in port_table.rows.keys():
            row_data = port_table.get_row(row_key)
            # 数据格式：(行号, Listen Port, Listen Host, Target Port, Target Host, Type)
            if len(row_data) < 6:
                continue

            _, listen_port, listen_host, target_port, target_host, forward_type = row_data[:6]

            # 验证端口号
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

            # 检查必要字段
            if not all([listen_port, target_port, target_host]):
                continue

            # 根据类型分配到不同的字典
            if forward_type == "Local":
                # LocalForward: 监听本地listen_port，转发到远程target_host:target_port
                local_forwards[listen_port] = f"{target_host}:{target_port}"
            elif forward_type == "Remote":
                # RemoteForward: 监听远程listen_port，转发到本地target_host:target_port
                remote_forwards[listen_port] = f"{target_host}:{target_port}"

        # 检查配置是否有变化
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

    @on(Button.Pressed, "#new_shell")
    def new_shell(self) -> None:
        """打开SSH终端"""
        print("[DEBUG] New shell button clicked")
        ssh_command = self.host_config.get_ssh_command()
        print(f"[DEBUG] Generated SSH command: {ssh_command}")
        open_new_terminal(ssh_command)

    @on(Button.Pressed, "#connect_shell")
    def connect_shell(self) -> None:
        """在当前终端中直接连接SSH"""
        with self.app.suspend():
            os.system(CLEAR_COMMAND)
            command = ' '.join(self.host_config.get_ssh_command())
            print(f"> {command}")
            os.system(command)
            os.system(CLEAR_COMMAND)


# 这个独立运行的部分需要修改为使用App来包装Screen
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
            # 安装完屏幕后，需要推送屏幕使其显示
            self.push_screen("ssh_conn")

    app = TestApp()
    app.run()


if __name__ == "__main__":
    view_ssh_conn_ui()
