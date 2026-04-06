# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SSH Manager is a Terminal User Interface (TUI) application built with Textual for managing SSH connections and configurations. It provides a visual interface for managing `~/.ssh/config` entries, port forwarding rules, and establishing SSH connections.

## Development Commands

### Installation
```bash
pip install -e .              # Install in editable mode
```

### Run Application
```bash
mssh                                    # Launch main TUI interface
mssh init [--force]                     # Initialize from ~/.ssh/config
mssh config                             # Open SSH config editor
mssh add <host-alias> -c "ssh ..."      # Add host config from SSH command string
mssh <host-alias>                       # Quick connect to known host (opens in new terminal)
mssh ssh [user@]host [-p PORT] [-J proxy] [-t] [remote_command]  # Direct shell mode
mssh --log-level debug                  # With debug logging
mssh -v                                 # Show version
```

### Test Environment
Docker-based SSH test server in `tests/` (see `tests/README.md` for details):
```bash
cd tests && docker compose up -d    # Start test SSH server on localhost:2222
cd tests && docker compose down     # Stop test server
```

## Architecture

### Entry Point
- `ssh_manager/app.py` - `main()` with argparse-based command routing via `handle_init_command()`, `handle_config_command()`, `handle_add_command()`, `handle_ssh_command()`. Two Textual apps: `SSHManagerApp` (host management) and `EditorSSHConfigApp` (config editor)

### Core Modules

**Configuration Layer** (`ssh_manager/utils/ssh_configs.py`)
- `HostConfig` - Pydantic model: `host`, `hostname`, `user`, `port`, `local_forwards`, `remote_forwards`, `proxy_command`, `proxy_jump`, `remote_command`, `request_tty`
  - `get_ssh_command()` generates subprocess args, `to_text()` / `from_text()` for SSH config text format
- `parse_text_to_configs()` / `parse_ssh_command()` - Parsers for SSH config text and CLI arguments
- `load_known_ssh_hosts()` / `load_ssh_config_file()` - Load from JSON cache and SSH config file
- `update_host_config()` / `remove_host_config()` - Mutate cache + persist to JSON
- `HOST_CONFIG_CACHE` - In-memory dict for fast lookup
- Dual storage: `~/.ssh/config` (source of truth) ↔ `~/.mssh/config.json` (runtime cache)

**SSH Connection Layer** (`ssh_manager/utils/ssh_util.py`)
- Pure subprocess-based SSH (no paramiko/external libs), uses native `ssh` binary
- `SSHConnection` - Extends `subprocess.Popen` with daemon monitor thread for connection health tracking
- `SSHConnectionManager` - Thread-safe registry (`RLock`) via global singleton `_connection_manager`
- `test_ssh_key_auth()` / `upload_ssh_key_with_ssh()` - Key auth test and upload workflow
- `create_persistent_ssh_connection()` / `close_persistent_ssh_connection()` - High-level connection lifecycle with optional key check + upload prompt

**Terminal Utilities** (`ssh_manager/utils/terminal_util.py`)
- `open_new_terminal()` - Cross-platform new terminal window (Windows `cmd`, Linux gnome-terminal/xterm)
- `clear_terminal()` - Decorator for screen clearing

**UI Layer** (`ssh_manager/screens/`, `ssh_manager/widgets/`)
- `SSHManageMainScreen` - Split-pane: host list (left) + config editor (right)
- `EditSSHConfigScreen` - Dual-pane `~/.ssh/config` editor (left: raw config, right: mssh cache)
- `SSHConnScreen` - Active connection with port forwarding management, ASCII host info table
- `HostListItem` - List item with connection status indicator (green/red dot)
- `HostConfigEditor` - Vendored TextEditor with SSH config autocomplete (`ssh_config_completer`)
- `ProxyManageTable` - Editable DataTable for port forwarding rules (extends `EditableTableWidget`)
- `AddPortForwardModal` - Modal dialog for adding new port forwarding rules
- `EditableTableWidget` - Base widget: editable DataTable with inline cell editing via Input
- `TextEditor` - Simple TextArea wrapper used in config editor screen

**Vendored** (`ssh_manager/vendor/textual_textarea/`) - Bundled text editor component with autocomplete

### Key Bindings (TUI)

**Main Screen** (`SSHManageMainScreen`):
- `ESC` - Quit (only when list has focus) | `C` / `Enter` - Connect to selected host
- `E` - Focus editor | `Ctrl+S` - Save config | `Ctrl+D` - Delete config | `Ctrl+N` - New config

**Connection Screen** (`SSHConnScreen`):
- `ESC` - Back to main screen

**Port Forward Table** (`ProxyManageTable`):
- `Ctrl+L` - Add local forward | `Ctrl+R` - Add remote forward | `Ctrl+D` - Delete row

### Data Flow

1. **Init**: `mssh init` → `~/.ssh/config` → `parse_text_to_configs()` → `~/.mssh/config.json`
2. **Runtime**: `mssh` → `~/.mssh/config.json` → `HOST_CONFIG_CACHE` → TUI display
3. **Connection**: TUI action → `test_ssh_key_auth()` → prompt if failed → `upload_ssh_key_with_ssh()` → `SSHConnection` subprocess
4. **Persistence**: Editor changes → `parse_text_to_configs()` → `update_host_config()` → JSON cache

### Design Patterns
- **Pydantic models** for config validation and serialization
- **Thread-safe connection manager** with RLock
- **Dual parsing**: SSH config text format ↔ JSON cache
- **Pure subprocess SSH**: native `ssh` binary with daemon monitor threads
- **Key auth workflow**: test → prompt → upload → retry

## Important Paths

- `~/.ssh/config` - SSH config (source of truth)
- `~/.mssh/config.json` - App's host cache
- `SSH_CONFIG_FILE_PATH`, `MSSH_HOME`, `HOST_CACHE_FILE_PATH` in `ssh_configs.py`

## Dependencies

- `textual` - TUI framework
- `textual-dev` - Textual dev tools
- `pydantic` - Config validation
- `pyperclip` - Clipboard operations
- Build: `flit` (PEP 517)
