from rich.console import RenderableType
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import DataTable, Input, TextArea
from textual.coordinate import Coordinate

from typing import Optional, Sequence
import re

from ssh_manager.utils.ssh_configs import HostConfig
from ssh_manager.vendor.textual_textarea import TextEditor


def ssh_config_completer(word: str, line_context: str = "") -> Sequence[tuple[RenderableType, str]]:
    """SSH 配置补全器

    Args:
        word: 当前正在输入的单词
        line_context: 当前行光标前的完整内容（可选）
    """

    # Check if typing a port number after LocalForward or RemoteForward
    if line_context:
        forward_pattern = r'^\s*(LocalForward|RemoteForward)\s+(\d+)\s*$'
        match = re.match(forward_pattern, line_context)

        if match and word == match.group(2):  # Current word is the port number
            port = match.group(2)
            # Provide completion suggestions for port forwarding format
            return [(f"{port} 127.0.0.1:{port}", f"{port} 127.0.0.1:{port}")]

    # Original completion logic
    suggests_map = {
        'HostN': ('HostName',),
        'H': ('Host', 'HostName'),

        'Pa': ('Password',),
        'Po': ('Port',),
        'Pr': ('ProxyJump', 'ProxyCommand ssh -W %h:%p',),
        'P': ('Port', 'Password'),

        'U': ('User',),
        'L': ('LocalForward',),
        'R': ('RemoteForward',),
        'l': ('localhost', ),
        '1': ('127.0.0.1', '192.168.'),
        '12': ('127.0.0.1', ),
        '19': ('192.168.', ),
    }

    for key, values in suggests_map.items():
        if word.startswith(key):
            return [(value, value) for value in values]
    return []


class HostConfigEditor(TextEditor, inherit_bindings=False):

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self, host_config: Optional[HostConfig] = None, text: str = "", **kwargs):

        if not text and isinstance(host_config, HostConfig):
            text = host_config.to_text()

        super().__init__(
            text=text,
            word_completer=self._wrapped_ssh_config_completer,
            **kwargs
        )

    def _wrapped_ssh_config_completer(self, word: str) -> Sequence[tuple[RenderableType, str]]:
        """Wrapper for ssh_config_completer that passes line context"""
        line_context = self._get_line_before_cursor() if hasattr(self, 'text_input') and self.text_input else ""
        return ssh_config_completer(word, line_context)

    def _get_line_before_cursor(self) -> str:
        """Get the content of the current line from the beginning to the cursor position"""
        if self.text_input:
            lno = self.text_input.cursor_location[0]
            return self.text_input.get_text_range(
                start=(lno, 0),
                end=self.text_input.cursor_location
            )
        return ""

    def load_text(self, text: str):
        self.text = text

    def has_cursor(self) -> bool:
        return self.text_input.has_focus


class TextEditor(TextArea):
    BINDINGS = [
        ("ctrl+a", "select_all", "Select All")

    ]


class EditableTableWidget(Widget):

    DEFAULT_CSS = """
    EditableTableWidget {
        layout: vertical;
        width: 100%;
        height: 100%;
    }

    DataTable {
        width: 100%;
        min-height: 4;
        height: 6;
        max-height: 10;
        border: round $primary-lighten-1;
        margin-bottom: 1;
    }

    DataTable:focus {
        border: round $accent;
    }

    Input {
        width: 100%;
        border: round $primary-lighten-1;
        padding: 0 1;
        display: none; 
        margin-top: 1; 
    }

    Input.visible {
        display: block; 
    }

    Input:focus {
        border: round $accent;
    }
    """

    BINDINGS = [
        Binding("ctrl+n", "add_new_row", "添加新行"),
        Binding("ctrl+d", "delete_selected_row", "删除选中行"),
    ]

    def __init__(self, columns: list[str], data: Optional[list[list[str]]] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        if not columns:
            raise ValueError("列定义 (columns) 不能为空。")
        
        # 内部数据存储，第一行为表头
        self.table_data: list[list[str]] = [list(columns)]          # 表头
        if data:
            self.table_data.extend([list(row) for row in data])     # 数据行

        self._cell_to_edit_coords: Optional[Coordinate] = None
        self.data_table: Optional[DataTable] = None                # 在 compose 中初始化
        self._edit_input: Optional[Input] = None                    # 在 compose 中初始化

    def compose(self) -> ComposeResult:
        """创建控件的 UI 布局。"""
        # DataTable 初始化时 fixed_columns=0 (或不设置) 允许列扩展或调整
        self.data_table = DataTable(id="data_table_widget", fixed_columns=0)
        self._edit_input = Input(placeholder="单元格内容将在此处编辑...", id="edit_input_widget")
        yield self.data_table
        yield self._edit_input

    def on_mount(self) -> None:
        """控件首次挂载时设置 DataTable。"""
        assert self.data_table is not None, "DataTable 未在 compose 中初始化"
        
        header_labels = self.table_data[0]

        # 获取列宽配置
        column_widths = self._get_column_widths()
        
        # 遍历表头，并为每列设置计算出的宽度
        for i, label_text in enumerate(header_labels):
            width = column_widths[i] if i < len(column_widths) else 10
            self.data_table.add_column(label_text, width=width)

        # 处理数据行
        data_rows = self.table_data[1:]
        for row_index, row_values in enumerate(data_rows):
            processed_row = self._process_data_row(row_index, row_values)
            self.data_table.add_row(*processed_row)

        self.data_table.focus()
    
    def _get_column_widths(self) -> list[int]:
        """获取列宽配置，子类可以重写此方法自定义列宽"""
        header_labels = self.table_data[0]
        # 默认平均分配宽度
        column_width = max(10, 80 // len(header_labels) if len(header_labels) > 0 else 10)
        return [column_width] * len(header_labels)
    
    def _process_data_row(self, row_index: int, row_values: list) -> list[str]:
        """处理数据行，子类可以重写此方法自定义行数据处理"""
        return [str(cell_value) for cell_value in row_values]

    async def on_key(self, event: events.Key) -> None:
        """处理按键事件以启动或取消编辑。"""
        assert self.data_table is not None
        assert self._edit_input is not None

        if event.key == "enter":
            if self.data_table.has_focus:
                cursor_coord = self.data_table.cursor_coordinate
                # 确保光标在有效的数据行上
                if cursor_coord.row < 0 or cursor_coord.row >= self.data_table.row_count:
                    return

                self._cell_to_edit_coords = cursor_coord
                
                # self.table_data[0] 是表头, 所以实际数据从 self.table_data[1] 开始
                data_row_in_source = cursor_coord.row + 1
                data_col_in_source = cursor_coord.column

                if 0 <= data_row_in_source < len(self.table_data) and \
                   0 <= data_col_in_source < len(self.table_data[data_row_in_source]):
                    current_value = str(self.table_data[data_row_in_source][data_col_in_source])
                    
                    self._edit_input.value = current_value
                    self._edit_input.add_class("visible")
                    self._edit_input.focus()
                    event.stop() 
                else:
                    self._cell_to_edit_coords = None
                return

        elif event.key == "escape":
            if self._edit_input.has_class("visible") and self._cell_to_edit_coords is not None:
                self._edit_input.value = ""
                self._edit_input.remove_class("visible")
                self.data_table.focus()
                self._cell_to_edit_coords = None
                event.stop()
                return

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理从 Input 小部件提交的新单元格值。"""
        assert self.data_table is not None
        assert self._edit_input is not None
        
        if event.input is not self._edit_input:
            return

        if self._cell_to_edit_coords:
            new_value = self._edit_input.value
            
            table_row_idx = self._cell_to_edit_coords.row   # DataTable 中的视觉行索引
            table_col_idx = self._cell_to_edit_coords.column

            source_data_row_idx = table_row_idx + 1     # 对应 self.table_data 的行索引

            if 0 <= source_data_row_idx < len(self.table_data) and \
               0 <= table_col_idx < len(self.table_data[source_data_row_idx]):
                self.table_data[source_data_row_idx][table_col_idx] = new_value
                self.data_table.update_cell_at(self._cell_to_edit_coords, new_value)
            
            self._edit_input.value = ""
            self._edit_input.remove_class("visible")
            self.data_table.focus()
            self._cell_to_edit_coords = None
        else:
            self._edit_input.remove_class("visible")    # 预防性隐藏
            self.data_table.focus()

    def action_add_new_row(self) -> None:
        """添加一个新行到表格中。"""
        assert self.data_table is not None
        
        num_columns = len(self.table_data[0])   # 基于表头获取列数
        new_data_row_values = [""] * num_columns    # 创建空字符串列表作为新行数据
        
        self.table_data.append(list(new_data_row_values))   # 添加到内部数据源
        
        # DataTable 会自动为没有提供 key 的行生成唯一的键
        self.data_table.add_row(*new_data_row_values) 
        
        # 移动光标到新添加行的第一个单元格
        # Textual 应该会自动将新的光标位置滚动到视图中
        new_row_index = self.data_table.row_count - 1
        if new_row_index >= 0:
            self.data_table.cursor_coordinate = Coordinate(new_row_index, 0)
            # 移除了显式的 scroll_to_coordinate 调用
        self.app.bell()     # 发出提示音

    def action_delete_selected_row(self) -> None:
        """删除当前选中的行。"""
        assert self.data_table is not None
        assert self._edit_input is not None

        cursor_row_idx = self.data_table.cursor_row    # 获取 DataTable 中的视觉行索引

        # 检查是否有有效的行被选中
        if cursor_row_idx < 0 or cursor_row_idx >= self.data_table.row_count:
            self.app.bell()     # 无有效行选中，发出提示音
            return

        # 如果正在编辑的单元格位于要删除的行中，则取消编辑
        if self._edit_input.has_class("visible") and self._cell_to_edit_coords:
            if self._cell_to_edit_coords.row == cursor_row_idx:
                self._edit_input.value = ""
                self._edit_input.remove_class("visible")
                self._cell_to_edit_coords = None

        if self.data_table.row_count > 0 and 0 <= cursor_row_idx < self.data_table.row_count:
            all_row_keys = list(self.data_table.rows.keys())
            key_to_delete = all_row_keys[cursor_row_idx]
            self.data_table.remove_row(key_to_delete)
        
            del self.table_data[cursor_row_idx + 1]
        
            if self.data_table.row_count > 0:
                new_cursor_row = min(cursor_row_idx, self.data_table.row_count - 1)
                current_col_cursor = self.data_table.cursor_column
                # 使用 len(self.data_table.columns) 替换 self.data_table.column_count
                if not (0 <= current_col_cursor < len(self.data_table.columns)):
                    current_col_cursor = 0
                
                if len(self.data_table.columns) > 0:
                    self.data_table.cursor_coordinate = Coordinate(new_cursor_row, current_col_cursor)
                else:
                    self.data_table.cursor_coordinate = Coordinate(new_cursor_row, 0)
                # 移除了显式的 scroll_to_coordinate 调用
            else:   # 如果表格变空了
                pass    # 不需要设置光标

            self.data_table.focus() 
            self.app.bell()
        else:
            self.app.bell()

    def add_rows(self, rows: list[list[str]]):
        for row in rows:
            self.table_data.append(row)
            self.data_table.add_row(*row)


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
