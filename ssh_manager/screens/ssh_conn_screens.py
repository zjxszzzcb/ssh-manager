from textual.app import ComposeResult
from textual.screen import Screen

from ssh_manager.widgets.proxy_table import ProxyManageTable
from ssh_manager.utils.ssh_configs import HostConfig

class SSHConnUI(Screen):
    """SSH 连接界面"""

    def __init__(self, host_config: HostConfig):
        print("[DEBUG] Initializing SSHConnUI")
        super().__init__()
        self.host_config = host_config
        print(f"[DEBUG] SSHConnUI initialized with host: {host_config.host}")

    def compose(self) -> ComposeResult:
        print("[DEBUG] SSHConnUI compose called")
        local_forwards = []
        for local_port, forward_address in self.host_config.local_forwards.items():
            local_forwards.append((local_port, *forward_address.split(":")))
        print(f"[DEBUG] Local forwards: {local_forwards}")
        yield ProxyManageTable(local_forwards)
        
    def on_mount(self) -> None:
        print("[DEBUG] SSHConnUI mounted")
        table = self.query_one(ProxyManageTable)

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
            self.install_screen(SSHConnUI(host_config), name="ssh_conn")
            # 安装完屏幕后，需要推送屏幕使其显示
            self.push_screen("ssh_conn")

    app = TestApp()
    app.run()

if __name__ == "__main__":
    view_ssh_conn_ui()
