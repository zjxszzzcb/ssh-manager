from textual.app import App, ComposeResult
from textual.widgets import Label, ListItem, ListView

from ssh_manager.utils.ssh_configs import HostConfig


class HostListItem(ListItem):
    """List item representing an SSH host."""

    class HostStatusInfo(HostConfig):
        is_alive: bool = False
    
    def __init__(self, host_config: HostConfig):
        """Initialize the host list item.
        
        Args:
            host_config: The SSH host to represent.
        """
        super().__init__()
        self.host_info = self.HostStatusInfo(**host_config.model_dump())

    def compose(self) -> ComposeResult:
        """Compose the list item."""
        status_dot = "[green]●[/]" if self.host_info.is_alive else "[red]●[/]"
        status_text = "active" if self.host_info.is_alive else "offline"
        yield Label(f"{status_dot} {self.host_info.host} ({status_text})")
    
    def update_status(self) -> None:
        """Update the status display."""
        status_dot = "[green]●[/]" if self.host_info.is_alive else "[red]●[/]"
        status_text = "active" if self.host_info.is_alive else "offline"
        
        # Get the first Label widget and update its content
        label = self.query_one(Label)
        label.update(f"{status_dot} {self.host_info.host} ({status_text})")


def view_host_item():
    """Demo function to show how HostListItem works."""
    
    class HostListDemo(App):
        """A demo application showing HostListItem usage."""
        
        def compose(self) -> ComposeResult:
            """Create a demo view with sample hosts."""

            host_item_1 = HostListItem(HostConfig(
                host="demo-server-1",
                hostname="server1.example.com",
                user="admin",
                port=22,
                password=None,
            ))
            host_item_2 = HostListItem(HostConfig(
                host="demo-server-2",
                hostname="server2.example.com",
                user="admin",
                port=22,
                password=None,
            ))
            host_item_2.host_info.is_alive = True

            yield ListView(
                host_item_1,
                host_item_2,
            )
            
    app = HostListDemo()
    app.run()

if __name__ == "__main__":
    view_host_item()