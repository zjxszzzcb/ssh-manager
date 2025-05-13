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

```bash
mssh
```

### Run TUI With Command

```bash
mssh ssh {user}@{hostname} 

mssh ssh {host}

# Optional args
-p, --port {port}
--passowrd {password}
-L {local_forward}  # Format: local_port:forward_host:forward_port
```

![main](sources/images/main_screen.png)


### Connect To Target

![ssh_conn](sources/images/ssh_conn_screen.png)


##  TODO LIST

### SSH Manager

* Confiuguration Backup

* Configuration Sync
  * Export configurations back to ~/.ssh/config
  * Edit ~/.ssh directory

* Connection Management TUI
  * manager terminal supports the following commands:
    * basic systemctl commands
    * Open remote terminal on existing terminal
    * Open remote directory, edit remote files with TUI editor
    * File upload / download.
    * command completition
    * add port forward
  * Proxy/Jump host configuration

### Docker Manager

