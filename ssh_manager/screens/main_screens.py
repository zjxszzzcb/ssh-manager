import logging

from textual import on
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.containers import Horizontal
from textual.widgets import ListView, Footer
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
    """SSH Manager 主界面
    
    Args:
        host_configs: 主机配置列表
        selected: 初始选中的主机配置，如果为None则默认选中第一项
    """

    BINDINGS = [
        # 隐藏上下键的提示，因为这是常见操作
        Binding("up", "cursor_up", "Move cursor up", show=False),
        Binding("down", "cursor_down", "Move cursor down", show=False),
        
        # 显示编辑器和退出的快捷键提示
        Binding("e", "focus_editor", "Edit", show=True),
        Binding("c", "connect", "Connect", show=True),
        
        # 隐藏其他快捷键提示
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

    ListView {
        width: 50%;
        border: solid #21262d;
        scrollbar-gutter: stable;
        padding: 0 1;
        background: #161b22;
    }

    HostConfigEditor {
        width: 50%;
        border: solid #238636;
        background: #161b22;
        margin: 0 1;
    }

    ListView:focus {
        border: solid #1f6feb;
    }

    HostConfigEditor:focus {
        border: solid #1f6feb !important;
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
        
        # 添加主机列表项
        if self.host_configs:
            for config in self.host_configs:
                list_view.append(HostListItem(config))

            # 设置初始焦点到列表视图
            list_view.focus()
            
            # 确定初始选中的索引位置
            initial_index = 0
            if self._initial_selected_config:
                # 查找指定的配置在列表中的位置
                for i, config in enumerate(self.host_configs):
                    if config.host == self._initial_selected_config.host:
                        initial_index = i
                        break
            
            # 设置列表选中位置
            list_view.index = initial_index
            
            # 更新编辑器显示对应配置
            self.update_editor(self.host_configs[initial_index].to_text(add_password=True))

        # 设置定时器每秒更新一次连接状态
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
        """更新编辑器内容"""
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
    
    def create_connection(self) -> bool:
        logger.info("action_connect triggered")
        host_config = self.get_selected_host_config()
        if not host_config:
            return False

        logger.info(f"Creating connection for host: {host_config.host}")

        exist_connection = get_ssh_connection(host_config.host)
        if exist_connection and exist_connection.is_alive():
            return True

        with self.app.suspend():
            connection = create_persistent_ssh_connection(host_config)
            success = connection is not None

        list_view = self.query_one(ListView)
        if connection:
            self.host_configs[list_view.index] = host_config
            self.connections[host_config.host] = connection

        return success
        
    def cleanup_connections(self):
        for connection in self.connections.values():
            if isinstance(connection, SSHConnection):
                connection.terminate()
                connection.wait()
        self.connections.clear()

    @on(ListView.Highlighted)
    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """当列表项高亮时更新编辑器"""
        item = event.item
        assert isinstance(item, HostListItem)
        self.update_editor(item.host_info.to_text(add_password=True))

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
        update_host_config(example_config)

        new_item = HostListItem(example_config)
        list_view = self.query_one(ListView)
        list_view.append(new_item)
        list_view.focus()
        list_view.index = len(list_view.children) - 1
        self.update_editor(new_item.host_info.to_text(add_password=False))

    def action_save_config(self) -> None:
        """保存当前编辑器中的配置"""
        editor = self.query_one(HostConfigEditor)
        if editor.has_cursor():
            # 从编辑器文本解析配置
            selected_config_old = self.get_selected_host_config()
            new_config = list(parse_text_to_configs(editor.text).values())[0]
            for known_host_config in self.host_configs:
                if selected_config_old.to_text(True) == known_host_config.to_text(True):
                    continue
                if known_host_config.host == new_config.host:
                    self.notify(f"Host {known_host_config.host} already exists.", severity="error")
                    self.update_editor(selected_config_old.to_text(add_password=True))
                    return
            self.update_selected_item(new_config)
            # 更新配置
            update_host_config(new_config)
            # 将焦点移回列表
            self.action_focus_list()

    def action_delete_config(self) -> None:
        """删除当前选中的配置"""
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

    class MainApp(App):
        def on_mount(self):
            self.install_screen(SSHManageMainScreen(demo_configs), name="main")
            self.push_screen("main")

    app = MainApp()
    app.run()


if __name__ == "__main__":
    view_main_ui()
