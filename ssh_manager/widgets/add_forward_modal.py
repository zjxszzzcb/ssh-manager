"""Port forwarding modal dialog for adding new port forwarding rules."""

from typing import Optional
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class TypeSelector(Horizontal):
    """A selector widget with Local and Remote options, using green dot for selection."""

    DEFAULT_CSS = """
    TypeSelector {
        width: 1fr;
        height: 1;
        align: left middle;
    }

    .type_option {
        width: auto;
        height: 1;
        padding: 0 1;
        color: #8b949e;
    }

    .type_option.selected {
        color: #238636;
    }

    TypeSelector:focus .type_option.selected {
        color: #2ea043;
        text-style: bold;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._selected = "Local"
        self.can_focus = True

    def compose(self) -> ComposeResult:
        yield Label("● Local", id="opt_local", classes="type_option selected")
        yield Label("○ Remote", id="opt_remote", classes="type_option")

    @property
    def type_value(self) -> str:
        return self._selected

    def toggle(self) -> None:
        """Toggle between Local and Remote."""
        local_label = self.query_one("#opt_local", Label)
        remote_label = self.query_one("#opt_remote", Label)

        if self._selected == "Local":
            self._selected = "Remote"
            local_label.update("○ Local")
            local_label.remove_class("selected")
            remote_label.update("● Remote")
            remote_label.add_class("selected")
        else:
            self._selected = "Local"
            local_label.update("● Local")
            local_label.add_class("selected")
            remote_label.update("○ Remote")
            remote_label.remove_class("selected")

    def select_local(self) -> None:
        """Select Local option."""
        if self._selected != "Local":
            self.toggle()

    def select_remote(self) -> None:
        """Select Remote option."""
        if self._selected != "Remote":
            self.toggle()


class AddPortForwardModal(ModalScreen[Optional[dict]]):
    """Modal dialog for adding a new port forwarding rule."""

    DEFAULT_CSS = """
    AddPortForwardModal {
        align: center middle;
    }

    #modal_container {
        width: 50;
        height: auto;
        background: #161b22;
        border: round #238636;
        padding: 1 2;
    }

    #modal_title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: #238636;
        margin-bottom: 1;
    }

    .form_row {
        width: 100%;
        height: 3;
        margin-bottom: 0;
        align: left middle;
    }

    .form_label {
        width: 14;
        height: 3;
        padding: 0;
        color: #e6edf3;
        content-align: left middle;
    }

    .form_input {
        width: 1fr;
        height: 3;
    }

    .form_input:focus {
        border: round #238636;
    }

    #type_row {
        width: 100%;
        height: 1;
        margin-bottom: 0;
        margin-top: 1;
        align: left middle;
    }

    #type_label {
        width: 14;
        height: 1;
        padding: 0;
        color: #e6edf3;
        content-align: left middle;
    }

    #type_selector {
        width: 1fr;
        height: 1;
    }

    #type_selector:focus {
        background: #21262d;
    }

    #button_row {
        width: 100%;
        height: 3;
        margin-top: 1;
        align: center middle;
    }

    #cancel_btn {
        width: 12;
        margin-right: 2;
        background: #6e7681;
        color: #ffffff;
        border: none;
    }

    #cancel_btn:hover {
        background: #8b949e;
    }

    #confirm_btn {
        width: 12;
        background: #6e7681;
        color: #ffffff;
        border: none;
    }

    #confirm_btn.valid {
        background: #238636;
    }

    #confirm_btn.valid:hover {
        background: #2ea043;
    }
    """

    # Define focusable widgets order for navigation
    FOCUSABLE_IDS = ["listen_port", "listen_host", "target_port", "target_host", "type_selector"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._is_valid = False

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Label("🔗 Add Port Forward", id="modal_title")

            # Listen Port
            with Horizontal(classes="form_row"):
                yield Label("Listen Port:", classes="form_label")
                yield Input(placeholder="e.g. 8000", id="listen_port", classes="form_input")

            # Listen Host
            with Horizontal(classes="form_row"):
                yield Label("Listen Host:", classes="form_label")
                yield Input(value="127.0.0.1", id="listen_host", classes="form_input")

            # Target Port
            with Horizontal(classes="form_row"):
                yield Label("Target Port:", classes="form_label")
                yield Input(placeholder="e.g. 8000", id="target_port", classes="form_input")

            # Target Host
            with Horizontal(classes="form_row"):
                yield Label("Target Host:", classes="form_label")
                yield Input(value="127.0.0.1", id="target_host", classes="form_input")

            # Type (Selector with Local/Remote options)
            with Horizontal(id="type_row"):
                yield Label("Type:", id="type_label")
                yield TypeSelector(id="type_selector")

            # Buttons
            with Horizontal(id="button_row"):
                yield Button("Cancel", id="cancel_btn", variant="default")
                yield Button("Confirm", id="confirm_btn", variant="default")

    def on_mount(self) -> None:
        """Focus on the first input field."""
        self.query_one("#listen_port", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Validate form on any input change and update placeholders."""
        listen_port_input = self.query_one("#listen_port", Input)
        target_port_input = self.query_one("#target_port", Input)
        
        listen_port = listen_port_input.value.strip()
        target_port = target_port_input.value.strip()
        
        # Update placeholders dynamically
        if listen_port and not target_port:
            target_port_input.placeholder = f"default: {listen_port}"
        elif not listen_port:
            target_port_input.placeholder = "e.g. 8000"
        
        if target_port and not listen_port:
            listen_port_input.placeholder = f"default: {target_port}"
        elif not target_port:
            listen_port_input.placeholder = "e.g. 8000"
        
        self._validate_form()

    def _validate_form(self) -> None:
        """Validate all form fields and update confirm button state."""
        listen_port = self.query_one("#listen_port", Input).value.strip()
        listen_host = self.query_one("#listen_host", Input).value.strip()
        target_port = self.query_one("#target_port", Input).value.strip()
        target_host = self.query_one("#target_host", Input).value.strip()

        # Validate: at least one port must be valid, hosts must not be empty
        is_valid = True

        # At least one port must be valid
        has_valid_listen_port = self._is_valid_port(listen_port)
        has_valid_target_port = self._is_valid_port(target_port)
        
        if not (has_valid_listen_port or has_valid_target_port):
            is_valid = False
        if not listen_host:
            is_valid = False
        if not target_host:
            is_valid = False

        self._is_valid = is_valid
        confirm_btn = self.query_one("#confirm_btn", Button)

        if is_valid:
            confirm_btn.add_class("valid")
        else:
            confirm_btn.remove_class("valid")

    def _is_valid_port(self, port_str: str) -> bool:
        """Check if port string is a valid port number (1-65535)."""
        if not port_str:
            return False
        try:
            port = int(port_str)
            return 1 <= port <= 65535
        except ValueError:
            return False

    def _get_validation_error(self) -> str:
        """Get validation error message."""
        listen_port = self.query_one("#listen_port", Input).value.strip()
        listen_host = self.query_one("#listen_host", Input).value.strip()
        target_port = self.query_one("#target_port", Input).value.strip()
        target_host = self.query_one("#target_host", Input).value.strip()

        errors = []
        
        has_valid_listen_port = self._is_valid_port(listen_port)
        has_valid_target_port = self._is_valid_port(target_port)
        
        if not (has_valid_listen_port or has_valid_target_port):
            if listen_port and not has_valid_listen_port:
                errors.append(f"Invalid Listen Port: {listen_port}")
            if target_port and not has_valid_target_port:
                errors.append(f"Invalid Target Port: {target_port}")
            if not listen_port and not target_port:
                errors.append("At least one port is required")
        
        if not listen_host:
            errors.append("Listen Host is required")
        if not target_host:
            errors.append("Target Host is required")
        
        return "; ".join(errors) if errors else ""

    def _try_confirm(self) -> None:
        """Try to confirm the form, showing error if invalid."""
        if self._is_valid:
            result = self._get_form_data()
            self.dismiss(result)
        else:
            error_msg = self._get_validation_error()
            self.notify(error_msg, severity="error", timeout=3)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "confirm_btn":
            self._try_confirm()

    def _get_current_focus_index(self) -> int:
        """Get the index of the currently focused widget in FOCUSABLE_IDS."""
        for i, widget_id in enumerate(self.FOCUSABLE_IDS):
            widget = self.query_one(f"#{widget_id}")
            if widget.has_focus:
                return i
        return -1

    def _focus_by_index(self, index: int) -> None:
        """Focus on the widget at the given index."""
        if 0 <= index < len(self.FOCUSABLE_IDS):
            widget_id = self.FOCUSABLE_IDS[index]
            self.query_one(f"#{widget_id}").focus()

    def on_key(self, event) -> None:
        """Handle key events for navigation."""
        type_selector = self.query_one("#type_selector", TypeSelector)
        
        if event.key == "escape":
            self.dismiss(None)
            event.stop()
        elif event.key == "enter":
            # If on type selector, toggle it; otherwise try to confirm
            if type_selector.has_focus:
                type_selector.toggle()
            else:
                self._try_confirm()
            event.stop()
        elif event.key == "left":
            # Left key selects Local when type selector is focused
            if type_selector.has_focus:
                type_selector.select_local()
                event.stop()
        elif event.key == "right":
            # Right key selects Remote when type selector is focused
            if type_selector.has_focus:
                type_selector.select_remote()
                event.stop()
        elif event.key == "down":
            current_idx = self._get_current_focus_index()
            if current_idx >= 0 and current_idx < len(self.FOCUSABLE_IDS) - 1:
                self._focus_by_index(current_idx + 1)
                event.stop()
        elif event.key == "up":
            current_idx = self._get_current_focus_index()
            if current_idx > 0:
                self._focus_by_index(current_idx - 1)
                event.stop()

    def _get_form_data(self) -> dict:
        """Get form data as a dictionary."""
        type_selector = self.query_one("#type_selector", TypeSelector)
        forward_type = type_selector.type_value

        listen_port = self.query_one("#listen_port", Input).value.strip()
        target_port = self.query_one("#target_port", Input).value.strip()
        
        # Use the other port value if one is empty
        if not listen_port and target_port:
            listen_port = target_port
        elif not target_port and listen_port:
            target_port = listen_port

        return {
            "listen_port": listen_port,
            "listen_host": self.query_one("#listen_host", Input).value.strip(),
            "target_port": target_port,
            "target_host": self.query_one("#target_host", Input).value.strip(),
            "type": forward_type,
        }


def view_add_forward_modal():
    """Preview the modal dialog."""
    from textual.app import App

    class PreviewApp(App):
        CSS = """
        Screen {
            background: #161b22;
        }
        """

        def on_mount(self):
            self.push_screen(AddPortForwardModal(), callback=self._on_modal_result)

        def _on_modal_result(self, result):
            print(f"Modal result: {result}")
            self.exit()

    app = PreviewApp()
    app.run()


if __name__ == "__main__":
    view_add_forward_modal()
