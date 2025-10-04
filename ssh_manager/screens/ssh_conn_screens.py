import os
from typing import Dict

from textual import on, events
from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Button, DataTable, Footer, Label
from textual.containers import Vertical, Center, Middle

from ssh_manager.widgets.proxy_table import ProxyManageTable
from ssh_manager.utils.ssh_configs import HostConfig
from ssh_manager.utils.ssh_util import create_persistent_ssh_connection
from ssh_manager.utils.terminal_util import open_new_terminal, CLEAR_COMMAND


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

    #content_container {
        background: #161b22;
        width: 80;
        height: auto;
        margin: 2;
    }

    #host_label {
        width: 100%;
        height: auto;
        text-align: center;
        background: #161b22;
        color: #7fb069;
        margin: 1 0;
        padding: 1;
        border: solid #21262d;
        content-align: center middle;
        text-style: bold;
    }

    Button {
        width: 100%;
        margin: 1 0;
        background: #1f6feb;
        color: #ffffff;
        border: tall transparent;
    }

    Button:focus {
        background: #238636;
    }

    ProxyManageTable {
        height: 1fr;
        margin: 0;
        background: #161b22;
        overflow-x: hidden;
        scrollbar-size-horizontal: 0;
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

    #local_table_label, #remote_table_label {
        width: 100%;
        height: 1;
        text-align: center;
        background: #161b22;
        color: #7fb069;
        margin: 1 0 0 0;
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
        print("[DEBUG] Initializing SSHConnUI")
        super().__init__()
        self.host_config = host_config
        print(f"[DEBUG] SSHConnUI initialized with host: {host_config.host}")
        self.set_interval(1/5, self.monitor_proxy_table, name="monitor_proxy_table")

    def compose(self) -> ComposeResult:
        print("[DEBUG] SSHConnUI compose called")
        local_forwards = []
        for local_port, forward_address in self.host_config.local_forwards.items():
            # 为ProxyManageTable添加空的行号列（第一列将被自动填充）
            local_forwards.append(("", local_port, *forward_address.split(":")))
        print(f"[DEBUG] Local forwards: {local_forwards}")

        remote_forwards = []
        for remote_port, local_address in self.host_config.remote_forwards.items():
            # 为ProxyManageTable添加空的行号列（第一列将被自动填充）
            remote_forwards.append(("", remote_port, *local_address.split(":")))
        print(f"[DEBUG] Remote forwards: {remote_forwards}")

        # 创建多行标签文本
        label_lines = [
            f"⚡ SSH Connection: {self.host_config.host}",
            f"🌐 Hostname: {self.host_config.hostname} | Port: {self.host_config.port}",
        ]
        if self.host_config.user:
            label_lines.append(f"🙋‍♂️ User: {self.host_config.user}")
        if self.host_config.password:
            label_lines.append(f"🔑 Password: {self.host_config.password}")

        label_text = "\n".join(label_lines)
        print(f"[DEBUG] Creating label with text: {label_text}")

        with Center():
            with Middle():
                with Vertical(id="content_container"):
                    yield Label(label_text, id="host_label")
                    yield Button("🔌 Connect Shell", id="connect_shell")
                    yield Button("🚀 New Shell", id="new_shell")

                    # Local Port Forwarding table
                    yield Label("🔗 Local Port Forwarding", id="local_table_label")
                    local_table = ProxyManageTable(local_forwards, mode="local", id="local_forwards_table")
                    local_table.can_focus = True
                    yield local_table

                    # Remote Port Forwarding table
                    yield Label("🔄 Remote Port Forwarding", id="remote_table_label")
                    remote_table = ProxyManageTable(remote_forwards, mode="remote", id="remote_forwards_table")
                    remote_table.can_focus = True
                    yield remote_table

        yield Footer()

    def on_mount(self) -> None:
        """初始化界面"""
        print("[DEBUG] SSHConnUI on_mount")
        self.query_one("#connect_shell", Button).focus()
        # 确保表格可以获得焦点
        local_table = self.query_one("#local_forwards_table", ProxyManageTable)
        local_table.can_focus = True
        local_table.data_table.can_focus = True
        remote_table = self.query_one("#remote_forwards_table", ProxyManageTable)
        remote_table.can_focus = True
        remote_table.data_table.can_focus = True
    
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
        local_table = self.query_one("#local_forwards_table", ProxyManageTable).query_one(DataTable)
        remote_table = self.query_one("#remote_forwards_table", ProxyManageTable).query_one(DataTable)

        if remote_table.has_focus:
            # 如果远程表格有焦点且光标在第一行，切换到本地表格
            if remote_table.cursor_row == 0:
                if local_table.row_count > 0:
                    local_table.focus()
                    local_table.move_cursor(row=local_table.row_count - 1, column=1, animate=False)
                else:
                    new_shell_button.focus()
                return True
            return False
        elif local_table.has_focus:
            # 如果本地表格有焦点且光标在第一行，切换到 new_shell 按钮
            if local_table.cursor_row == 0:
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
        local_table = self.query_one("#local_forwards_table", ProxyManageTable).query_one(DataTable)
        remote_table = self.query_one("#remote_forwards_table", ProxyManageTable).query_one(DataTable)

        if connect_shell_button.has_focus:
            # 从 connect_shell 按钮切换到 new_shell 按钮
            new_shell_button.focus()
            return True
        elif new_shell_button.has_focus:
            # 从 new_shell 按钮切换到本地表格
            local_table.focus()
            # 确保表格光标在第一行第二列（跳过行号列）
            if local_table.row_count > 0:
                local_table.move_cursor(row=0, column=1, animate=False)
            return True
        elif local_table.has_focus:
            # 从本地表格最后一行切换到远程表格
            if local_table.cursor_row == local_table.row_count - 1:
                remote_table.focus()
                if remote_table.row_count > 0:
                    remote_table.move_cursor(row=0, column=1, animate=False)
                return True
            return False
        return False

    def monitor_proxy_table(self) -> None:
        """监控代理表"""
        # print("[DEBUG] Monitoring proxy table")

        # 监控本地端口转发表格
        local_table = self.query_one("#local_forwards_table", ProxyManageTable).query_one(DataTable)
        local_forwards: Dict[str, str] = {}
        for row_key in local_table.rows.keys():
            row_data = local_table.get_row(row_key)
            # 现在数据格式是：(行号, local_port, forward_host, forward_port)
            if len(row_data) >= 4:
                _, local_port, forward_host, forward_port = row_data[:4]
            else:
                continue  # 如果数据不完整，跳过这一行

            if not local_port:
                continue
            try:
                int(local_port)
            except ValueError:
                self.notify("Invalid local port", severity="error", timeout=0.2)
                continue

            if not forward_port:
                continue
            try:
                int(forward_port)
            except ValueError:
                self.notify("Invalid forward port", severity="error", timeout=0.2)
                continue

            # 检查除行号外的其他数据是否完整
            if not all([local_port, forward_host, forward_port]):
                continue

            local_forwards[local_port] = f"{forward_host}:{forward_port}"

        # 监控远程端口转发表格
        remote_table = self.query_one("#remote_forwards_table", ProxyManageTable).query_one(DataTable)
        remote_forwards: Dict[str, str] = {}
        for row_key in remote_table.rows.keys():
            row_data = remote_table.get_row(row_key)
            # 现在数据格式是：(行号, remote_port, local_host, local_port)
            if len(row_data) >= 4:
                _, remote_port, local_host, local_port = row_data[:4]
            else:
                continue  # 如果数据不完整，跳过这一行

            if not remote_port:
                continue
            try:
                int(remote_port)
            except ValueError:
                self.notify("Invalid remote port", severity="error", timeout=0.2)
                continue

            if not local_port:
                continue
            try:
                int(local_port)
            except ValueError:
                self.notify("Invalid local port", severity="error", timeout=0.2)
                continue

            # 检查除行号外的其他数据是否完整
            if not all([remote_port, local_host, local_port]):
                continue

            remote_forwards[remote_port] = f"{local_host}:{local_port}"

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
