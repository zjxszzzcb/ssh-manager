# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SSH Manager is a Terminal User Interface (TUI) application built with Textual for managing SSH connections and configurations. It provides a visual interface for managing `~/.ssh/config` entries, port forwarding rules, and establishing SSH connections.

## Development Commands

### Installation
```bash
pip install -e .
```

### Run Tests
```bash
pytest
```

### Run Application
```bash
# Launch main TUI interface
mssh

# Initialize from ~/.ssh/config
mssh init

# Open SSH config editor
mssh config

# Quick connect to known host (opens in new terminal)
mssh <host-alias>

# Connect with custom parameters (direct shell mode)
mssh ssh [user@]host [-p PORT]

# With optional log level
mssh --log-level debug
```

### Test Environment
A Docker-based test environment is available in the `tests/` directory:
```bash
cd tests
docker compose up -d      # Start test SSH server on localhost:2222
docker compose down       # Stop test server
```

## Architecture

### Entry Point
- `ssh_manager/app.py` - Main CLI entry point with argparse-based command routing

### Core Components

**Configuration Layer** (`ssh_manager/utils/ssh_configs.py`)
- `HostConfig` - Pydantic model for SSH host configuration
- `parse_text_to_configs()` - Parser for SSH config file format
- `load_ssh_config_file()` - Load from `~/.ssh/config`
- `load_known_ssh_hosts()` - Load from `~/.mssh/config.json` cache
- `update_host_config()` - Persist configuration to JSON cache
- `HOST_CONFIG_CACHE` - In-memory cache for host configurations

**SSH Connection Layer** (`ssh_manager/utils/ssh_util.py`)
- `SSHConnection` - Pure subprocess-based SSH connection with monitoring thread
- `create_persistent_ssh_connection()` - Create and cache persistent connections
- `SSHConnectionManager` - Thread-safe global connection registry (`_connection_manager`)
- `test_ssh_key_auth()` - Test SSH key authentication using BatchMode
- `upload_ssh_key_with_ssh()` - Upload public key to remote host

**UI Layer** (Textual-based)
- `screens/main_screens.py` - `SSHManageMainScreen` - Split-pane interface (host list + config editor)
- `screens/edit_ssh_config.py` - Dual-pane editor for `~/.ssh/config`
- `screens/ssh_conn_screens.py` - Connection management screen
- `widgets/host_list.py` - `HostListItem` for host list display
- `widgets/editor.py` - `HostConfigEditor` with SSH syntax auto-completion
- `widgets/proxy_table.py` - `ProxyTableWidget` for port forwarding rules
- `widgets/add_forward_modal.py` - Modal for adding port forwarding

**TUI Key Bindings**
- `ESC` - Quit application
- `C` - Connect to selected host
- `Enter` - Connect to selected host (from main screen)

### Data Flow

1. **Initialization**: `mssh init` reads `~/.ssh/config` → `parse_text_to_configs()` → `~/.mssh/config.json`
2. **Runtime**: `mssh` loads `~/.mssh/config.json` → `HOST_CONFIG_CACHE` → TUI display
3. **Connection**: TUI action → `test_ssh_key_auth()` → prompt if failed → `upload_ssh_key_with_ssh()` → `SSHConnection` subprocess
4. **Persistence**: Editor changes → `parse_text_to_configs()` → `update_host_config()` → JSON cache

### Key Design Patterns

- **Pydantic models** for configuration validation and serialization
- **Thread-safe connection manager** (`SSHConnectionManager`) with RLock for concurrent access
- **Dual parsing**: SSH config file format (text) ↔ JSON cache (internal)
- **Pure subprocess SSH**: No external SSH libraries, uses native ssh binary with daemon monitor threads
- **Key authentication workflow**: Test key auth → Prompt user → Upload via ssh command → Retry

## Important Paths

- `~/.ssh/config` - Standard SSH configuration file
- `~/.mssh/config.json` - Application's host configuration cache
- `SSH_CONFIG_FILE_PATH` and `HOST_CACHE_FILE_PATH` in `ssh_configs.py`

## Dependencies

- `textual` - TUI framework
- `textual-dev` - Textual development tools
- `pydantic` - Configuration validation
- `pyperclip` - Clipboard operations
