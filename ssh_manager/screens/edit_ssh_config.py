from textual.app import ComposeResult
from textual.containers import Horizontal, Container
from textual.screen import Screen
from textual.widgets import Header, Footer, Static

from ssh_manager.widgets.editor import TextEditor
from ssh_manager.utils.ssh_configs import SSH_CONFIG_FILE_PATH, load_known_ssh_hosts


# Define the custom screen with two editors
class EditSSHConfigScreen(Screen):

    BINDINGS = [
        ("ctrl+s", "save", "Save"),
    ]

    def compose(self) -> ComposeResult:
        """Create the child widgets for the screen."""
        # The Header widget displays the app title.
        yield Header()

        with open(SSH_CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            user_ssh_config_text = f.read()

        known_ssh_configs = load_known_ssh_hosts()
        known_ssh_config_text = "\n".join(config.to_text() for config in known_ssh_configs.values())
        
        # A Horizontal container arranges its children from left to right.
        with Horizontal():
            # The first TextArea widget. We assign an ID for potential styling or querying.
            with Container(id="left-container"):
                yield Static("  ~/.ssh/config")
                yield TextEditor(text=user_ssh_config_text, id="left_editor")
            
            # Right editor with its own header, grouped in a Container.
            with Container(id="right-container"):
                yield Static("  mssh-configs")
                yield TextEditor(text=known_ssh_config_text, id="right_editor")
            
        # The Footer widget displays key bindings.
        yield Footer()

    def action_save(self) -> None:
        """An action to trigger a save request."""
        left_editor = self.query_one("#left_editor")
        assert isinstance(left_editor, TextEditor)
        with open(SSH_CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(left_editor.text)
