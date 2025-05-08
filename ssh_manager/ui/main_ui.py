from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import ListView, Footer
from textual.binding import Binding
from textual.message import Message
from typing import List

from ssh_manager.widgets.editor import HostConfigEditor
from ssh_manager.widgets.host_list import HostListItem
from ssh_manager.utils.ssh_configs import HostConfig

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
        
        # 隐藏其他快捷键提示
        Binding("ctrl+s", "focus_list", "Focus list", show=False),
        Binding("ctrl+c", "quit", "Quit", show=False),
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
        editor.focus()

    def action_focus_list(self) -> None:
        """将焦点移动回列表"""
        list_view = self.query_one(ListView)
        list_view.focus()

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
