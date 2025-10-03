# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SSH Manager is a Textual-based TUI application for managing SSH connections with support for port forwarding, proxy jumping, and persistent connections. The application can initialize from `~/.ssh/config` and provides an interactive interface for managing SSH hosts.

## Commands

### Development & Running

```bash
# Install in development mode
pip install -e .

# Run the TUI application
mssh

# Initialize from ~/.ssh/config
mssh --init

# Run with a specific SSH command
mssh ssh user@hostname -p 2222

# Run configuration editor
mssh --configure

# Run with debug logging
mssh --log-level debug
```

### Testing

```bash
# Run the SSH config parser test
python tests/test_parse_ssh_config_text.py

# Run the app directly from module
python -m ssh_manager.app
```

## Architecture

### Core Components

The application follows a Model-View architecture using the Textual framework:

1. **Entry Point** (`ssh_manager/app.py`): Contains two main applications:
   - `SSHManagerApp`: Main TUI for SSH connection management
   - `EditorSSHConfigApp`: Configuration editor interface
   - Handles CLI argument parsing and routing to appropriate modes

2. **Configuration Management** (`ssh_manager/utils/ssh_configs.py`):
   - `HostConfig`: Pydantic model representing SSH host configurations
   - Manages reading/writing to `~/.ssh/config` and local JSON cache (`mssh_config.json`)
   - Supports SSH config parsing with extensions (Password, LocalForward, ProxyJump)
   - Configuration persistence through `HOST_CONFIG_CACHE` and file operations

3. **SSH Connection Handling** (`ssh_manager/utils/ssh_util.py`):
   - `SSHConnection`: Custom subprocess.Popen wrapper for persistent SSH connections
   - Implements automatic key-based authentication with password fallback
   - Connection pool management through global `SSH_CONNECTIONS` dictionary
   - Daemon thread monitoring for connection health checks

4. **Screen System** (`ssh_manager/screens/`):
   - `SSHManageMainScreen`: Host list view with inline configuration editor
   - `SSHConnScreen`: Active connection management with port forwarding controls
   - `EditSSHConfigScreen`: Dual-pane SSH config file editor
   - Screens communicate through Textual's screen stack and event system

5. **Widget Components** (`ssh_manager/widgets/`):
   - `HostListItem`: Visual representation of SSH hosts with status indicators
   - `HostConfigEditor`: Text editor for SSH configuration with syntax support
   - `ProxyManageTable`: DataTable for managing port forwarding rules

### Key Design Patterns

- **Configuration Flow**: SSH config file → HostConfig models → JSON cache → UI components
- **Connection Lifecycle**: Host selection → Authentication → Persistent subprocess → Terminal spawn
- **State Management**: Screen-level state with widget composition, no global state except connection pool
- **Port Forwarding**: Managed as dictionaries in HostConfig (`local_forwards`, `remote_forwards`)

### External Dependencies

- **textual**: TUI framework for building the interface
- **paramiko**: SSH client library for connection validation
- **pydantic**: Data validation for HostConfig models

### File Organization

```
ssh_manager/
├── app.py                  # Application entry points and CLI handling
├── screens/
│   ├── main_screens.py     # Main host list and editor screen
│   ├── ssh_conn_screens.py # Active SSH connection management
│   └── edit_ssh_config.py  # SSH config file editor
├── utils/
│   ├── ssh_configs.py      # Configuration models and parsing
│   ├── ssh_util.py         # SSH connection management
│   └── terminal_util.py    # Terminal spawning utilities
├── widgets/
│   ├── host_list.py        # Host list item widget
│   ├── editor.py           # Configuration text editor
│   └── proxy_table.py      # Port forwarding table
└── vendor/
    └── textual_textarea/   # Vendored text editor component
```

### Important Implementation Details

- SSH connections are managed as persistent subprocesses with automatic reconnection
- The app maintains a connection pool to avoid duplicate connections to the same host
- Configuration changes are immediately persisted to both JSON cache and optionally to SSH config
- Terminal spawning is platform-specific (uses different commands for Linux/Mac/Windows)
- ProxyJump hosts are resolved from the known hosts configuration automatically