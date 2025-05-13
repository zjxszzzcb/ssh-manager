from typing import Sequence, Optional
from ssh_manager.widgets.editor import EditableTableWidget

class ProxyManageTable(EditableTableWidget):

    def __init__(self, data: Optional[Sequence[Sequence[str]]] = None, **kwargs):
        super().__init__(columns=["Local Port", "Forwarded Host", "Forwarded Port"], data=data, **kwargs)

def view_proxy_manage_table():
    from textual.app import App, ComposeResult
    from textual.widgets import DataTable

    class DataEditTableApp(App):
        def compose(self) -> ComposeResult:
            yield ProxyManageTable(
                (
                    (443, "example.com", 80),
                    (80, "example2.com", 443),
                )
            )
        
        def on_mount(self) -> None:
            table = self.query_one(ProxyManageTable).query_one(DataTable)
            table.move_cursor(row=0, column=1, animate=False)

    app = DataEditTableApp()
    app.run()


if __name__ == "__main__":
    view_proxy_manage_table()
