# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SSH Manager is a Terminal User Interface (TUI) application built with Textual for managing SSH connections and configurations. It provides a visual interface for managing `~/.ssh/config` entries, port forwarding rules, and establishing SSH connections.

## Development Commands

### Installation
```bash
pip install -e .              # Install in editable mode
pip install -e ".[dev]"       # Install with dev dependencies (pytest, etc.)
```

### Run Tests
```bash
pytest                                    # Run all tests
pytest tests/unit/                        # Run only unit tests
pytest tests/unit/test_ssh_configs.py     # Run a single test file
pytest -m unit                            # Run tests by marker
pytest -m "not slow and not docker"       # Exclude slow/docker tests (default behavior)
pytest -m docker                          # Run Docker-dependent tests
pytest --no-cov                           # Skip coverage for faster runs
```

Test markers: `unit`, `integration`, `ui`, `e2e`, `slow`, `ssh`, `docker`, `snapshot`

Slow and docker tests are skipped by default. Use `-m docker` or `-m slow` to include them.

### Run Application
```bash
mssh                           # Launch main TUI interface
mssh init                      # Initialize from ~/.ssh/config
mssh config                    # Open SSH config editor
mssh <host-alias>              # Quick connect to known host (opens in new terminal)
mssh ssh [user@]host [-p PORT] # Connect with custom parameters (direct shell mode)
mssh --log-level debug         # With debug logging
```

### Test Environment
Docker-based SSH test server in `tests/`:
```bash
cd tests && docker compose up -d    # Start test SSH server on localhost:2222
cd tests && docker compose down     # Stop test server
```

## Architecture

### Entry Point
- `ssh_manager/app.py` - `main()` with argparse-based command routing. Two Textual apps: `SSHManagerApp` (host management) and `EditorSSHConfigApp` (config editor)

### Core Modules

**Configuration Layer** (`ssh_manager/utils/ssh_configs.py`)
- `HostConfig` - Pydantic model with SSH params + port forwarding rules, `get_ssh_command()` generates subprocess args
- `parse_text_to_configs()` / `parse_ssh_command()` - Parsers for SSH config text and CLI arguments
- Dual storage: `~/.ssh/config` (source of truth) ↔ `~/.mssh/config.json` (runtime cache)
- `HOST_CONFIG_CACHE` - In-memory dict for fast lookup

**SSH Connection Layer** (`ssh_manager/utils/ssh_util.py`)
- Pure subprocess-based SSH (no paramiko/external libs), uses native `ssh` binary
- `SSHConnection` - Wraps `subprocess.Popen` with daemon monitor thread
- `SSHConnectionManager` - Thread-safe registry (`RLock`) via global `_connection_manager`
- `test_ssh_key_auth()` / `upload_ssh_key_with_ssh()` - Key auth test and upload workflow

**Terminal Utilities** (`ssh_manager/utils/terminal_util.py`)
- `open_new_terminal()` - Cross-platform new terminal window (Windows `cmd`, Linux gnome-terminal/xterm)
- `clear_terminal()` - Decorator for screen clearing

**UI Layer** (`ssh_manager/screens/`, `ssh_manager/widgets/`)
- `SSHManageMainScreen` - Split-pane: host list (left) + config editor (right)
- `EditSSHConfigScreen` - Dual-pane `~/.ssh/config` editor
- `SSHConnScreen` - Active connection with port forwarding management
- `HostListItem` / `HostConfigEditor` / `ProxyTableWidget` / `AddForwardModal` - Reusable widgets

**Vendored** (`ssh_manager/vendor/textual_textarea/`) - Bundled text editor component with autocomplete

### Key Bindings (TUI)
- `ESC` - Quit | `C` / `Enter` - Connect to selected host

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
