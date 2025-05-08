from textual.app import App, ComposeResult
from textual.widgets import TextArea

from ssh_manager.utils.ssh_configs import HostConfig

class HostConfigEditor(TextArea):
    def __init__(self, host_config: HostConfig, **kwargs):
        text = self.config_to_text(host_config)
        super().__init__(text, tab_behavior="indent", **kwargs)


    @staticmethod
    def config_to_text(host_config: HostConfig) -> str:
        indent = " " * 4

        text_items = [
            f"Host {host_config.host}\n",
            f"{indent}Hostname {host_config.hostname}\n",
            f"{indent}User {host_config.user}\n",
            f"{indent}Password {host_config.password}\n" if host_config.password else "",
            f"{indent}Port {host_config.port}\n",
        ]
        return "".join(text_items)


def view_host_config_editor():
    from textual.containers import Container

    host_config_1 = HostConfig(
        host="demo-server-1",
        hostname="server1.example.com",
        user="admin",
        port=22,
        password="123456",
    )
    host_config_2 = HostConfig(
        host="demo-server-2",
        hostname="server2.example.com",
        user="admin",
        port=22,
        password=None,
    )
    # print(HostConfigEditor.config_to_text(host_config_1))

    class TextAreaExample(App):

        CSS = """
        #container {
            layout: horizontal;
        }
        """

        def compose(self) -> ComposeResult:
            yield Container(
                HostConfigEditor(host_config_1, id='editor-1'),
                HostConfigEditor(host_config_2, id='editor-2'),
                id='container',
            )

    app = TextAreaExample()
    app.run()

if __name__ == "__main__":
    view_host_config_editor()
