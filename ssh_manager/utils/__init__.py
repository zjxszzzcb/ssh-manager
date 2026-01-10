"""SSH Manager utilities module.

This module provides utility functions and classes for SSH configuration and connection management.
"""

from ssh_manager.utils.ssh_configs import (
    HostConfig,
    load_ssh_config_file,
    load_known_ssh_hosts,
    parse_ssh_command,
    update_host_config,
    remove_host_config,
    get_host_config,
    parse_text_to_configs,
    get_ssh_config_example,
)

from ssh_manager.utils.ssh_util import (
    SSHConnection,
    create_persistent_ssh_connection,
    get_ssh_connection,
    close_persistent_ssh_connection,
)

from ssh_manager.utils.terminal_util import (
    open_new_terminal,
)

__all__ = [
    # ssh_configs
    "HostConfig",
    "load_ssh_config_file",
    "load_known_ssh_hosts",
    "parse_ssh_command",
    "update_host_config",
    "remove_host_config",
    "get_host_config",
    "parse_text_to_configs",
    "get_ssh_config_example",
    # ssh_util
    "SSHConnection",
    "create_persistent_ssh_connection",
    "get_ssh_connection",
    "close_persistent_ssh_connection",
    # terminal_util
    "open_new_terminal",
]
