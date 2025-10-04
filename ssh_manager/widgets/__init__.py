"""SSH Manager widgets module.

This module provides custom widget components for the SSH Manager TUI application.
"""

from ssh_manager.widgets.host_list import HostListItem
from ssh_manager.widgets.editor import HostConfigEditor
from ssh_manager.widgets.proxy_table import ProxyManageTable

__all__ = [
    "HostListItem",
    "HostConfigEditor",
    "ProxyManageTable",
]