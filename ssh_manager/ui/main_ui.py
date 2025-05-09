from textual.app import App, ComposeResult
from textual.events import Key
from textual.containers import Horizontal
from textual.widgets import ListView, Footer
from textual.binding import Binding
from typing import Dict, List

from ssh_manager.widgets.editor import HostConfigEditor
from ssh_manager.widgets.host_list import HostListItem
from ssh_manager.utils.ssh_configs import (
    HostConfig, update_ssh_config, parse_text_to_configs, 
    delete_ssh_config, get_ssh_config_example
)
from ssh_manager.utils.ssh_util import SSHConnection, create_persistent_ssh_connection
from ssh_manager.utils.terminal_util import open_new_terminal


class SSHManagerMainUI(App):
    """SSH Manager 主界面
    
    Args:
        host_configs: 主机配置列表
    """

    BINDINGS = [
        # 隐藏上下键的提示，因为这是常见操作
        Binding("up", "cursor_up", "Move cursor up", show=False),
        Binding("down", "cursor_down", "Move cursor down", show=False),
        
        # 显示编辑器和退出的快捷键提示
        Binding("e", "focus_editor", "Edit", show=True),
        Binding("escape", "quit", "Quit", show=True),
        Binding("c", "connect", "Connect", show=False),
        
        # 隐藏其他快捷键提示
        Binding("ctrl+s", "save_config", "Save config", show=False),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+d", "delete_config", "Delete config"),
        Binding("ctrl+n", "new_config", "New config"),
    ]

    CSS = """
    Screen {
        background: $surface;
    }

    Horizontal {
        height: 90%;
        background: $surface;
        margin: 0 0 1 0;
    }

    ListView {
        width: 50%;
        border: solid green;
        scrollbar-gutter: stable;
        padding: 0 1;
        background: $surface;
    }

    HostConfigEditor {
        width: 50%;
        border: solid blue;
        background: $surface;
        margin: 0 1;
    }

    ListView:focus {
        border: solid yellow;
    }

    HostConfigEditor:focus {
        border: solid yellow !important;
    }

    Footer {
        background: $surface;
        color: $text;
        height: 1;
    }
    """

    def __init__(self, host_configs: List[HostConfig]):
        self.host_configs = host_configs
        self.connections: Dict[str, SSHConnection] = dict()
        super().__init__()

    def compose(self) -> ComposeResult:
        # 创建水平布局
        with Horizontal():
            # 左侧主机列表
            list_view = ListView()
            list_view.can_focus = True
            yield list_view
            
            # 右侧配置编辑器（默认显示第一个主机的配置）
            editor = HostConfigEditor(self.host_configs[0] if self.host_configs else None)
            editor.can_focus = True  # 允许编辑器获得焦点
            yield editor
        
        # 添加底部快捷键提示
        yield Footer()

    def on_mount(self) -> None:
        """当应用挂载完成后添加列表项"""
        list_view = self.query_one(ListView)
        for config in self.host_configs:
            list_view.append(HostListItem(config))
        
        # 设置初始焦点到列表视图并选中第一项
        list_view.focus()
        if len(list_view.children) > 0:
            list_view.index = 0
            self._update_editor(list_view.children[0])
        
        # 设置定时器每秒更新一次连接状态
        self.set_interval(1.0, self._update_connection_status)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """当列表项高亮时更新编辑器"""
        self._update_editor(event.item)

    def action_cursor_up(self) -> None:
        """向上移动光标"""
        list_view = self.query_one(ListView)
        if list_view.has_focus and list_view.index > 0:
            list_view.index -= 1

    def action_cursor_down(self) -> None:
        """向下移动光标"""
        list_view = self.query_one(ListView)
        if list_view.has_focus and list_view.index < len(list_view.children) - 1:
            list_view.index += 1

    def action_focus_editor(self) -> None:
        """将焦点移动到编辑器"""
        editor = self.query_one(HostConfigEditor)
        if not editor.has_focus:
            editor.focus()

    def action_focus_list(self) -> None:
        """将焦点移动回列表"""
        list_view = self.query_one(ListView)
        list_view.focus()

    def action_new_config(self) -> None:
        """新建一个配置"""
        example_config = get_ssh_config_example()
        self.host_configs.append(example_config)
        update_ssh_config(example_config)
        
        new_item = HostListItem(example_config)
        list_view = self.query_one(ListView)
        list_view.append(new_item)
        list_view.focus()
        list_view.index = len(list_view.children) - 1
        self._update_editor(new_item)

    def action_save_config(self) -> None:
        """保存当前编辑器中的配置"""
        editor = self.query_one(HostConfigEditor)
        list_view = self.query_one(ListView)
        if editor.has_focus:
            # 从编辑器文本解析配置
            config = list(parse_text_to_configs(editor.text).values())[0]
            print(config)
            
            selected_item = list_view.children[list_view.index]
            selected_item.host_info = selected_item.host_info.update_config(config)
            selected_item.update_status()
            self.host_configs[list_view.index] = selected_item.host_info
            
            print(selected_item.host_info)
            # 更新配置
            update_ssh_config(config)
            # 将焦点移回列表
            self.action_focus_list()
    
    def action_delete_config(self) -> None:
        """删除当前选中的配置"""
        list_view = self.query_one(ListView)
        if list_view.has_focus:
            delete_ssh_config(self.host_configs[list_view.index].host)
            self.host_configs.pop(list_view.index)
            selected_item = list_view.children[list_view.index]
            selected_item.remove()
            self.action_focus_list()
            list_view.index = 0
    
    def action_connect(self) -> None:
        list_view = self.query_one(ListView)
        host_config = self.host_configs[list_view.index]
        self.connections[host_config.host] = create_persistent_ssh_connection(host_config)

    def action_open_ssh_terminal(self) -> None:
        """打开SSH终端"""
        print("open ssh terminal")
        list_view = self.query_one(ListView)
        if list_view.has_focus:
            config = self.host_configs[list_view.index]
            print(config.get_ssh_command())
            open_new_terminal(config.get_ssh_command())

    def action_quit(self) -> None:
        """退出应用，但仅在编辑器没有焦点时生效"""
        editor = self.query_one(HostConfigEditor)
        if not editor.has_focus:
            self.exit()

    def _update_editor(self, host_item: HostListItem) -> None:
        """更新编辑器内容"""
        if isinstance(host_item, HostListItem):
            editor = self.query_one(HostConfigEditor)
            editor.load_text(HostConfigEditor.config_to_text(host_item.host_info))

    def _update_connection_status(self):
        print("update_status")
        list_view = self.query_one(ListView)
        for idx in range(len(list_view.children)):
            host_item: HostListItem = list_view.children[idx]
            connection = self.connections.get(host_item.host_info.host)
            is_alive = connection.is_alive() if isinstance(connection, SSHConnection) else False
            host_item.host_info.is_alive = is_alive
            host_item.update_status()
            
    def on_key(self, event: Key) -> None:
        """处理按键事件"""
        if event.key == "enter":
            self.action_open_ssh_terminal()


def view_main_ui():
    # 示例用法
    demo_configs = [
        HostConfig(
            host="demo-server-1",
            hostname="server1.example.com",
            user="admin",
            port=22,
            password="123456",
        ),
        HostConfig(
            host="demo-server-2",
            hostname="server2.example.com",
            user="admin",
            port=22,
            password=None,
        ),
    ]
    ui = SSHManagerMainUI(demo_configs)
    ui.run()


if __name__ == "__main__":
    view_main_ui()
