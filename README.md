# SSH Manager

SSH Manager is an easy-to-use SSH connection management tool that helps you efficiently manage and use multiple SSH connections.

## Install

```bash
pip install git+https://github.com/zjxszzzcb/ssh-manager.git@dev
```

## Features

### Initialize from ~/.ssh/config

```bash
mssh --init
```

### Run TUI

```
mssh
```

![main](sources/images/main_screen.png)


### Connect To Target

![ssh_conn](sources/images/ssh_conn_screen.png)


##  TODO LIST

### SSH Manager
* Configuration Sync
    * Export configurations back to ~/.ssh/config

* CLI Features
    * Full SSH command compatibility
    * Drop-in replacement for OpenSSH client

* Connection Management TUI
    * Upload SSH key to remote host
    * Open remote folder in SFTP
    * Edit remote files with TUI editor
    * Proxy/Jump host configuration

### Docker Manager

