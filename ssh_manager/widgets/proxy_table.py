from ssh_manager.widgets.editor import EditableTableWidget

class ProxyManageTable(EditableTableWidget):

    def __init__(self, data: list[list[str]] | None = None, **kwargs):
        super().__init__(columns=["Local Port", "Forwarded Host", "Forwarded Port"], data=data, **kwargs)

def view_proxy_manage_table():
    from textual.app import App, ComposeResult

    class DataEditTableApp(App):
        def compose(self) -> ComposeResult:
            yield ProxyManageTable(
                (
                    (443, "example.com", 80),
                    (80, "example2.com", 443),
                )
            )
        
        def on_mount(self) -> None:
            table = self.query_one(ProxyManageTable)
            # table._data_table.move_cursor(row=0, column=1, animate=False)
    app = DataEditTableApp()
    app.run()



if __name__ == "__main__":
    view_proxy_manage_table()
