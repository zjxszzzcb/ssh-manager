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
        # Column order optimized by edit frequency - Listen fields first
        columns = ["#", "Listen Port", "Listen Host", "Target Port", "Target Host", "Type"]
        super().__init__(columns=columns, data=data, **kwargs)
    
    async def on_key(self, event: events.Key) -> None:
        """Handle key events to prevent editing row number column."""
        assert self.data_table is not None
        assert self._edit_input is not None

        if event.key == "enter":
            if self.data_table.has_focus:
                cursor_coord = self.data_table.cursor_coordinate
                # Ensure cursor is on a valid data row
                if cursor_coord.row < 0 or cursor_coord.row >= self.data_table.row_count:
                    return

                # If cursor is in row number column (col 0) or Type column (col 5), editing is not allowed
                if cursor_coord.column == 0 or cursor_coord.column == 5:
                    self.app.bell()  # Play sound to indicate editing not allowed
                    return

                self._cell_to_edit_coords = cursor_coord
                
                # self.table_data[0] is the header, so actual data starts from self.table_data[1]
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
        """Custom column widths: proportional distribution based on content requirements"""
        # Based on actual content requirements:
        # #: Row number - minimum ratio
        # Listen Port: Port number needs 11 characters
        # Listen Host: Domain/IP needs more space
        # Target Port: Same as Listen Port
        # Target Host: Same as Listen Host
        # Type: Only needs to display Local/Remote

        total_width = 70  # Total width
        # Ratio distribution: Row#:Listen Port:Listen Host:Target Port:Target Host:Type
        width_ratios = [1, 4, 4, 4, 4, 2]  # Total ratio = 19
        total_ratio = sum(width_ratios)

        column_widths = []
        for ratio in width_ratios:
            width = (total_width * ratio) // total_ratio
            column_widths.append(width)

        # Ensure minimum widths
        min_widths = [2, 8, 10, 8, 10, 5]
        for i in range(len(column_widths)):
            column_widths[i] = max(column_widths[i], min_widths[i])

        print(f"[DEBUG] Column widths: {column_widths}, total: {sum(column_widths)}")
        return column_widths
    
    def _process_data_row(self, row_index: int, row_values: list) -> list[str]:
        """Process data row, automatically add row numbers"""
        # Ensure row data length is correct
        header_labels = self.table_data[0]
        while len(row_values) < len(header_labels):
            row_values.append("")
        
        # Automatically add row number for each row (starting from 1)
        row_with_number = [str(row_index + 1)] + [str(cell_value) if cell_value is not None else "" for cell_value in row_values[1:]]
        
        # Update row number in internal data
        self.table_data[row_index + 1][0] = str(row_index + 1)
        
        return row_with_number

    def action_add_local_forward(self) -> None:
        """Add a new LocalForward row (Ctrl+L)."""
        self._add_forward_row("Local")

    def action_add_remote_forward(self) -> None:
        """Add a new RemoteForward row (Ctrl+R)."""
        self._add_forward_row("Remote")

    def _add_forward_row(self, forward_type: str) -> None:
        """Add a new port forwarding row."""
        assert self.data_table is not None

        new_row_number = len(self.table_data)  # New row number

        # Create new row data: Row#, Listen Port, Listen Host, Target Port, Target Host, Type
        new_data_row_values = [
            str(new_row_number),  # Row number
            "",                   # Listen Port (to be filled)
            "127.0.0.1",         # Listen Host (default value)
            "",                   # Target Port (to be filled, usually same as Listen Port)
            "127.0.0.1",         # Target Host (default value)
            forward_type         # Type (Local or Remote)
        ]

        self.table_data.append(list(new_data_row_values))   # Add to internal data source
        self.data_table.add_row(*new_data_row_values)

        # Move cursor to Listen Port column (column 1) of the newly added row
        new_row_index = self.data_table.row_count - 1
        if new_row_index >= 0:
            self.data_table.cursor_coordinate = Coordinate(new_row_index, 1)
            # Moving cursor will automatically trigger scrolling to that row

        # If parent container is scrollable, also scroll to bottom
        from textual.containers import VerticalScroll
        parent = self.parent
        while parent:
            if isinstance(parent, VerticalScroll):
                parent.scroll_end(animate=False)
                break
            parent = parent.parent

        self.app.bell()     # Play sound

    # Keep old method for compatibility, but recommend using new shortcuts
    def action_add_new_row(self) -> None:
        """Add a new LocalForward row (kept for compatibility)."""
        self.action_add_local_forward()
    
    def action_delete_selected_row(self) -> None:
        """Delete the currently selected row and renumber all rows."""
        assert self.data_table is not None
        assert self._edit_input is not None

        cursor_row_idx = self.data_table.cursor_row    # Get visual row index in DataTable

        # Check if there is a valid row selected
        if cursor_row_idx < 0 or cursor_row_idx >= self.data_table.row_count:
            self.app.bell()     # No valid row selected, play sound
            return

        # If editing cell is in the row to be deleted, cancel editing
        if self._edit_input.has_class("visible") and self._cell_to_edit_coords:
            if self._cell_to_edit_coords.row == cursor_row_idx:
                self._edit_input.value = ""
                self._edit_input.remove_class("visible")
                self._cell_to_edit_coords = None

        if self.data_table.row_count > 0 and 0 <= cursor_row_idx < self.data_table.row_count:
            # Delete row from DataTable
            all_row_keys = list(self.data_table.rows.keys())
            key_to_delete = all_row_keys[cursor_row_idx]
            self.data_table.remove_row(key_to_delete)
        
            # Delete row from internal data
            del self.table_data[cursor_row_idx + 1]
            
            # Renumber all remaining rows
            self._renumber_all_rows()
        
            if self.data_table.row_count > 0:
                new_cursor_row = min(cursor_row_idx, self.data_table.row_count - 1)
                current_col_cursor = self.data_table.cursor_column
                # Ensure cursor is not in row number column (column 0)
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
        """Renumber all rows."""
        # Update row numbers in internal data
        for i in range(1, len(self.table_data)):  # Start from 1, skip header
            self.table_data[i][0] = str(i)

        # Update row numbers in all DataTable rows
        all_row_keys = list(self.data_table.rows.keys())
        for i, row_key in enumerate(all_row_keys):
            # Get current row data
            current_row = list(self.data_table.get_row(row_key))
            # Update row number
            current_row[0] = str(i + 1)
            # Update row in DataTable
            self.data_table.update_cell_at(Coordinate(i, 0), str(i + 1))

    async def on_input_submitted(self, event) -> None:
        """Handle submitted input and auto-fill Target Port when Listen Port changes."""

        # Save the current edit coordinates before parent clears them
        edit_coords = self._cell_to_edit_coords

        # Call parent's handler first
        await super().on_input_submitted(event)

        # Check if we just edited Listen Port (column 1)
        if edit_coords and edit_coords.column == 1:
            table_row_idx = edit_coords.row
            source_data_row_idx = table_row_idx + 1

            # Get the new Listen Port value
            if 0 <= source_data_row_idx < len(self.table_data):
                listen_port = self.table_data[source_data_row_idx][1]  # Listen Port column
                target_port = self.table_data[source_data_row_idx][3]  # Target Port column

                # If Target Port is empty, auto-fill with Listen Port value
                if listen_port and not target_port:
                    self.table_data[source_data_row_idx][3] = listen_port
                    # Update the visual display
                    self.data_table.update_cell_at(
                        Coordinate(table_row_idx, 3),
                        listen_port
                    )


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
