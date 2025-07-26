from typing import Dict

from textual import on, events
from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Button, DataTable, Footer, Label
from textual.containers import Vertical

from ssh_manager.widgets.proxy_table import ProxyManageTable
from ssh_manager.utils.ssh_configs import HostConfig
from ssh_manager.utils.ssh_util import create_persistent_ssh_connection
from ssh_manager.utils.terminal_util import open_new_terminal


class SSHConnScreen(Screen):
    """SSH 连接界面"""

    CSS = """
    Screen {
        background: $surface;
    }

    #host_label {
        width: 100%;
        height: auto;
        text-align: center;
        background: $surface-lighten-1;
        color: $accent;
        margin: 1;
        padding: 1;
        border: solid $accent;
        content-align: center middle;
        text-style: bold;
    }

    Button {
        width: 100%;
        margin: 1;
        background: $accent;
        color: $text;
        border: tall transparent;
    }

    Button:hover {
        background: $accent-darken-2;
    }

    Button:focus {
        border: tall $accent-lighten-2;
        background: $accent-darken-1;
    }

    ProxyManageTable {
        height: 1fr;
        margin: 1;
    }

    DataTable {
        border: tall transparent;
    }

    DataTable:focus {
        border: tall $accent-lighten-2;
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
            local_forwards.append((local_port, *forward_address.split(":")))
        print(f"[DEBUG] Local forwards: {local_forwards}")
        
        label_text = f"SSH Connection: {self.host_config.host}"
        print(f"[DEBUG] Creating label with text: {label_text}")
        
        with Vertical():
            yield Label(label_text, id="host_label")
            yield Button("New Shell", id="new_shell")
            table = ProxyManageTable(local_forwards)
            table.can_focus = True
            yield table

        yield Footer()

    def on_mount(self) -> None:
        """初始化界面"""
        print("[DEBUG] SSHConnUI on_mount")
        self.query_one("#new_shell", Button).focus()
        # 确保表格可以获得焦点
        table = self.query_one(ProxyManageTable)
        table.can_focus = True
        table._data_table.can_focus = True
    
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
        button = self.query_one("#new_shell", Button)
        table = self.query_one(ProxyManageTable).query_one(DataTable)
        print(f"[DEBUG] Cursor up - Table has focus: {table.has_focus}")
        
        if table.has_focus:
            # 如果表格有焦点且光标在第一行，切换到按钮
            print(f"table.cursor_row: {table.cursor_row}")
            if table.cursor_row == 0:
                button.focus()
                return True
            # 否则让表格处理向上导航
            return False
        else:
            print("table has no focus")
            return False

    def cursor_down(self) -> bool:
        """处理向下键：从按钮切换到表格"""
        button = self.query_one("#new_shell", Button)
        table = self.query_one(ProxyManageTable).query_one(DataTable)
        print(f"[DEBUG] Cursor down - Button has focus: {button.has_focus}")
        
        if button.has_focus:
            # 先聚焦到表格的DataTable
            table.focus()
            print("table.row_count: ", table.row_count)
            # 确保表格光标在第一行
            if table.row_count > 0:
                table.move_cursor(row=0, column=0, animate=False)
            return True
        return False

    def monitor_proxy_table(self) -> None:
        """监控代理表"""
        # print("[DEBUG] Monitoring proxy table")
        
        table = self.query_one(ProxyManageTable).query_one(DataTable)
        
        # 打印表格中的每行数据
        local_forwards: Dict[str, str] = {}
        for row_key in table.rows.keys():
            row_data = table.get_row(row_key)
            local_port, forward_host, forward_port = row_data

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

            if not all(row_data):
                continue

            local_forwards[local_port] = f"{forward_host}:{forward_port}"

        if local_forwards != self.host_config.local_forwards:
            print(f"[INFO] Old host configs: {self.host_config.local_forwards}")
            print(f"[INFO] New host configs: {local_forwards}")
            print("[INFO] Host configs have changed, updating host config")
            self.host_config.local_forwards = local_forwards
            connection = create_persistent_ssh_connection(self.host_config)

    @on(Button.Pressed, "#new_shell")
    def new_shell(self) -> None:
        """打开SSH终端"""
        print("[DEBUG] New shell button clicked")
        ssh_command = self.host_config.get_ssh_command()
        print(f"[DEBUG] Generated SSH command: {ssh_command}")
        open_new_terminal(ssh_command)


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
                    "443": "example.com:80",
                    "80": "example2.com:443",
                }
            )
            self.install_screen(SSHConnScreen(host_config), name="ssh_conn")
            # 安装完屏幕后，需要推送屏幕使其显示
            self.push_screen("ssh_conn")

    app = TestApp()
    app.run()


if __name__ == "__main__":
    view_ssh_conn_ui()
