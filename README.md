# SSH Manager

A modern Terminal User Interface (TUI) application for managing SSH connections and configurations. Built with Textual, it provides an intuitive visual interface for managing `~/.ssh/config` entries, port forwarding rules, and establishing SSH connections.

## Features

- **Visual Host Management**: Browse and manage all SSH hosts in a split-pane interface
- **Port Forwarding**: Easy-to-use table for managing Local/Remote port forwarding rules
- **Quick Connect**: Fast connection to known hosts via command line
- **Config Editor**: Built-in editor for `~/.ssh/config` with SSH syntax highlighting
- **Connection Monitoring**: Real-time status tracking of active SSH connections

## Screenshots

### Host Management Interface
![main](sources/images/main_screen.png)

### Connection & Port Forwarding
![ssh_conn](sources/images/ssh_conn_screen.png)

## Installation

```bash
pip install git+https://github.com/zjxszzzcb/ssh-manager.git
```

## CLI Usage

### Commands Overview

| Command | Description |
|---------|-------------|
| `mssh` | Launch main TUI interface |
| `mssh init` | Import hosts from `~/.ssh/config` |
| `mssh config` | Open `~/.ssh/config` editor |
| `mssh ssh [user@]host [-p PORT]` | Connect with custom parameters |
| `mssh <host-alias>` | Quick connect to known host |

### Initialize from Existing Config

Import your existing SSH hosts:

```bash
mssh init
```

This reads `~/.ssh/config` and populates `~/.mssh/config.json`.

### Launch TUI Interface

```bash
# Open main management interface
mssh

# Open with a new connection preset
mssh ssh user@192.168.1.100 -p 2222
```

### Edit SSH Config File

```bash
mssh config
```

Opens a dual-pane editor for `~/.ssh/config`.

### Quick Connect

```bash
# Directly connect to a known host alias
mssh my-server

# Equivalent to: ssh my-server
```
