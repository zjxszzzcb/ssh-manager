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
    """SSH configuration completer

    Args:
        word: currently typing word
        line_context: complete content before cursor in current line (optional)
    """

    # Check if typing after LocalForward or RemoteForward
    if line_context:
        # Pattern to match: LocalForward {host}:{port} or LocalForward {port}
        # Captures the forward type (LocalForward/RemoteForward) and the port part
        forward_pattern = r'^\s*(LocalForward|RemoteForward)\s+(.+?)\s*$'
        match = re.match(forward_pattern, line_context)

        if match:
            forward_type = match.group(1)  # LocalForward or RemoteForward
            port_part = match.group(2)     # Everything after the forward type

            # Check if port_part is in the format {host}:{port}
            if ':' in port_part and not port_part.endswith(':'):
                # Extract port from {host}:{port} format
                port = port_part.split(':')[-1]
                # Provide completion suggestion for {host}:{port} 127.0.0.1:{port}
                suggestion = f"{port_part} 127.0.0.1:{port}"
                return [(suggestion, suggestion)]
            elif port_part.isdigit():  # Simple port number
                port = port_part
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

    def has_cursor(self):
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
        Binding("ctrl+n", "add_new_row", "Add new row"),
        Binding("ctrl+d", "delete_selected_row", "Delete selected row"),
    ]

    def __init__(self, columns: list[str], data: Optional[list[list[str]]] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        if not columns:
            raise ValueError("Column definition (columns) cannot be empty.")
        
        # Internal data storage, first row is header
        self.table_data: list[list[str]] = [list(columns)]          # Header
        if data:
            self.table_data.extend([list(row) for row in data])     # Data rows

        self._cell_to_edit_coords: Optional[Coordinate] = None
        self.data_table: Optional[DataTable] = None                # Initialized in compose
        self._edit_input: Optional[Input] = None                    # Initialized in compose

    def compose(self) -> ComposeResult:
        """Create UI layout for the widget."""
        # DataTable initialized with fixed_columns=0 (or not set) allows column expansion or adjustment
        self.data_table = DataTable(id="data_table_widget", fixed_columns=0)
        self._edit_input = Input(placeholder="Cell content will be edited here...", id="edit_input_widget")
        yield self.data_table
        yield self._edit_input

    def on_mount(self) -> None:
        """Set up DataTable when widget is first mounted."""
        assert self.data_table is not None, "DataTable not initialized in compose"
        
        header_labels = self.table_data[0]

        # Get column width configuration
        column_widths = self._get_column_widths()
        
        # Iterate through header and set calculated width for each column
        for i, label_text in enumerate(header_labels):
            width = column_widths[i] if i < len(column_widths) else 10
            self.data_table.add_column(label_text, width=width)

        # Process data rows
        data_rows = self.table_data[1:]
        for row_index, row_values in enumerate(data_rows):
            processed_row = self._process_data_row(row_index, row_values)
            self.data_table.add_row(*processed_row)

        self.data_table.focus()
    
    def _get_column_widths(self) -> list[int]:
        """Get column width configuration, subclasses can override to customize"""
        header_labels = self.table_data[0]
        # Default evenly distribute width
        column_width = max(10, 80 // len(header_labels) if len(header_labels) > 0 else 10)
        return [column_width] * len(header_labels)
    
    def _process_data_row(self, row_index: int, row_values: list) -> list[str]:
        """Process data row, subclasses can override to customize row data processing"""
        return [str(cell_value) for cell_value in row_values]

    async def on_key(self, event: events.Key) -> None:
        """Handle key events to start or cancel editing."""
        assert self.data_table is not None
        assert self._edit_input is not None

        if event.key == "enter":
            if self.data_table.has_focus:
                cursor_coord = self.data_table.cursor_coordinate
                # Ensure cursor is on a valid data row
                if cursor_coord.row < 0 or cursor_coord.row >= self.data_table.row_count:
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

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle new cell value submitted from Input widget."""
        assert self.data_table is not None
        assert self._edit_input is not None
        
        if event.input is not self._edit_input:
            return

        if self._cell_to_edit_coords:
            new_value = self._edit_input.value
            
            table_row_idx = self._cell_to_edit_coords.row   # Visual row index in DataTable
            table_col_idx = self._cell_to_edit_coords.column

            source_data_row_idx = table_row_idx + 1     # Corresponding row index in self.table_data

            if 0 <= source_data_row_idx < len(self.table_data) and \
               0 <= table_col_idx < len(self.table_data[source_data_row_idx]):
                self.table_data[source_data_row_idx][table_col_idx] = new_value
                self.data_table.update_cell_at(self._cell_to_edit_coords, new_value)
            
            self._edit_input.value = ""
            self._edit_input.remove_class("visible")
            self.data_table.focus()
            self._cell_to_edit_coords = None
        else:
            self._edit_input.remove_class("visible")    # Preventively hide
            self.data_table.focus()

    def action_add_new_row(self) -> None:
        """Add a new row to the table."""
        assert self.data_table is not None
        
        num_columns = len(self.table_data[0])   # Get column count based on header
        new_data_row_values = [""] * num_columns    # Create empty string list as new row data
        
        self.table_data.append(list(new_data_row_values))   # Add to internal data source
        
        # DataTable will automatically generate unique keys for rows without provided keys
        self.data_table.add_row(*new_data_row_values) 
        
        # Move cursor to first cell of newly added row
        # Textual should automatically scroll new cursor position into view
        new_row_index = self.data_table.row_count - 1
        if new_row_index >= 0:
            self.data_table.cursor_coordinate = Coordinate(new_row_index, 0)
            # Removed explicit scroll_to_coordinate call
        self.app.bell()     # Play sound

    def action_delete_selected_row(self) -> None:
        """Delete the currently selected row."""
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
            all_row_keys = list(self.data_table.rows.keys())
            key_to_delete = all_row_keys[cursor_row_idx]
            self.data_table.remove_row(key_to_delete)
        
            del self.table_data[cursor_row_idx + 1]
        
            if self.data_table.row_count > 0:
                new_cursor_row = min(cursor_row_idx, self.data_table.row_count - 1)
                current_col_cursor = self.data_table.cursor_column
                # Use len(self.data_table.columns) instead of self.data_table.column_count
                if not (0 <= current_col_cursor < len(self.data_table.columns)):
                    current_col_cursor = 0
                
                if len(self.data_table.columns) > 0:
                    self.data_table.cursor_coordinate = Coordinate(new_cursor_row, current_col_cursor)
                else:
                    self.data_table.cursor_coordinate = Coordinate(new_cursor_row, 0)
                # Removed explicit scroll_to_coordinate call
            else:   # If table becomes empty
                pass    # No need to set cursor

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
