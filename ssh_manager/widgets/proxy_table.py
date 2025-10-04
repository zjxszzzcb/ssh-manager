from typing import Sequence, Optional
from textual import events
from textual.binding import Binding
from textual.coordinate import Coordinate
from ssh_manager.widgets.editor import EditableTableWidget


class ProxyManageTable(EditableTableWidget):

    BINDINGS = [
        Binding("ctrl+l", "add_local_forward", "Add Local Forward"),
        Binding("ctrl+r", "add_remote_forward", "Add Remote Forward"),
        Binding("ctrl+d", "delete_selected_row", "Delete Row"),
    ]

    def __init__(self, data: Optional[Sequence[Sequence[str]]] = None, **kwargs):
        """Initialize ProxyManageTable as a unified port forwarding table.

        Args:
            data: Initial table data
            **kwargs: Additional arguments passed to parent class
        """
        # Column order optimized by edit frequency
        columns = ["#", "Target Port", "Target Host", "Listen Port", "Listen Host", "Type"]
        super().__init__(columns=columns, data=data, **kwargs)
    
    async def on_key(self, event: events.Key) -> None:
        """处理按键事件，防止编辑行号列。"""
        assert self.data_table is not None
        assert self._edit_input is not None

        if event.key == "enter":
            if self.data_table.has_focus:
                cursor_coord = self.data_table.cursor_coordinate
                # 确保光标在有效的数据行上
                if cursor_coord.row < 0 or cursor_coord.row >= self.data_table.row_count:
                    return

                # 如果光标在行号列（第0列）或Type列（第5列），不允许编辑
                if cursor_coord.column == 0 or cursor_coord.column == 5:
                    self.app.bell()  # 发出提示音表示不可编辑
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
    
    def _get_column_widths(self) -> list[int]:
        """自定义列宽：基于内容需求的比例分配"""
        # 基于实际内容需求的比例：
        # #: 行号 - 最小比例
        # Target Port: 端口号需要11字符
        # Target Host: 域名/IP需要更多空间
        # Listen Port: 同Target Port
        # Listen Host: 同Target Host
        # Type: 只需要显示Local/Remote

        total_width = 70  # 总宽度
        # 比例分配: 行号:目标端口:目标主机:监听端口:监听主机:类型
        width_ratios = [1, 4, 4, 4, 4, 2]  # 总比例 = 19
        total_ratio = sum(width_ratios)

        column_widths = []
        for ratio in width_ratios:
            width = (total_width * ratio) // total_ratio
            column_widths.append(width)

        # 确保最小宽度
        min_widths = [2, 8, 10, 8, 10, 5]
        for i in range(len(column_widths)):
            column_widths[i] = max(column_widths[i], min_widths[i])

        print(f"[DEBUG] Column widths: {column_widths}, total: {sum(column_widths)}")
        return column_widths
    
    def _process_data_row(self, row_index: int, row_values: list) -> list[str]:
        """处理数据行，自动添加行号"""
        # 确保行数据长度正确
        header_labels = self.table_data[0]
        while len(row_values) < len(header_labels):
            row_values.append("")
        
        # 为每行自动添加行号（从1开始）
        row_with_number = [str(row_index + 1)] + [str(cell_value) if cell_value is not None else "" for cell_value in row_values[1:]]
        
        # 更新内部数据的行号
        self.table_data[row_index + 1][0] = str(row_index + 1)
        
        return row_with_number

    def action_add_local_forward(self) -> None:
        """添加一个新的LocalForward行（Ctrl+L）。"""
        self._add_forward_row("Local")

    def action_add_remote_forward(self) -> None:
        """添加一个新的RemoteForward行（Ctrl+R）。"""
        self._add_forward_row("Remote")

    def _add_forward_row(self, forward_type: str) -> None:
        """添加一个新的端口转发行。"""
        assert self.data_table is not None

        new_row_number = len(self.table_data)  # 新行号

        # 创建新行数据：行号, Target Port, Target Host, Listen Port, Listen Host, Type
        new_data_row_values = [
            str(new_row_number),  # 行号
            "",                   # Target Port (待填写)
            "127.0.0.1",         # Target Host (默认值)
            "",                   # Listen Port (待填写，通常与Target Port相同)
            "127.0.0.1",         # Listen Host (默认值)
            forward_type         # Type (Local或Remote)
        ]

        self.table_data.append(list(new_data_row_values))   # 添加到内部数据源
        self.data_table.add_row(*new_data_row_values)

        # 移动光标到新添加行的Target Port列（第1列）
        new_row_index = self.data_table.row_count - 1
        if new_row_index >= 0:
            self.data_table.cursor_coordinate = Coordinate(new_row_index, 1)
        self.app.bell()     # 发出提示音

    # 保留旧的方法以兼容，但建议使用新的快捷键
    def action_add_new_row(self) -> None:
        """添加一个新的LocalForward行（保留以兼容）。"""
        self.action_add_local_forward()
    
    def action_delete_selected_row(self) -> None:
        """删除当前选中的行，并重新编号所有行。"""
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
            # 删除DataTable中的行
            all_row_keys = list(self.data_table.rows.keys())
            key_to_delete = all_row_keys[cursor_row_idx]
            self.data_table.remove_row(key_to_delete)
        
            # 删除内部数据中的行
            del self.table_data[cursor_row_idx + 1]
            
            # 重新编号所有剩余的行
            self._renumber_all_rows()
        
            if self.data_table.row_count > 0:
                new_cursor_row = min(cursor_row_idx, self.data_table.row_count - 1)
                current_col_cursor = self.data_table.cursor_column
                # 确保光标不在行号列（第0列）
                if current_col_cursor == 0:
                    current_col_cursor = 1
                
                if not (1 <= current_col_cursor < len(self.data_table.columns)):
                    current_col_cursor = 1
                
                if len(self.data_table.columns) > 1:
                    self.data_table.cursor_coordinate = Coordinate(new_cursor_row, current_col_cursor)
                else:
                    self.data_table.cursor_coordinate = Coordinate(new_cursor_row, 0)

            self.data_table.focus() 
            self.app.bell()
        else:
            self.app.bell()
    
    def _renumber_all_rows(self) -> None:
        """重新编号所有行。"""
        # 更新内部数据的行号
        for i in range(1, len(self.table_data)):  # 从1开始，跳过表头
            self.table_data[i][0] = str(i)
        
        # 更新DataTable中所有行的行号
        all_row_keys = list(self.data_table.rows.keys())
        for i, row_key in enumerate(all_row_keys):
            # 获取当前行数据
            current_row = list(self.data_table.get_row(row_key))
            # 更新行号
            current_row[0] = str(i + 1)
            # 更新DataTable中的行
            self.data_table.update_cell_at(Coordinate(i, 0), str(i + 1))


def view_proxy_manage_table():
    from textual.app import App, ComposeResult
    from textual.widgets import DataTable

    class DataEditTableApp(App):
        def compose(self) -> ComposeResult:
            yield ProxyManageTable(
                (
                    ("", "443", "example.com", "80"),
                    ("", "80", "example2.com", "443"),
                )
            )
        
        def on_mount(self) -> None:
            table = self.query_one(ProxyManageTable).query_one(DataTable)
            table.move_cursor(row=0, column=1, animate=False)

    app = DataEditTableApp()
    app.run()


if __name__ == "__main__":
    view_proxy_manage_table()
