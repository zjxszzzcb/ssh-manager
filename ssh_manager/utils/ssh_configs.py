import os
import json
import uuid
from pydantic import BaseModel
from typing import Dict, List, Optional


class HostConfig(BaseModel):
    host: str
    hostname: str
    user: str
    password: Optional[str] = None
    port: int = 22
    local_forwards: Dict[str, str] = {}
    remote_forwards: Dict[str, str] = {}
    
    def get_ssh_command(self) -> List[str]:
        connect_commands = ['ssh', '-p', str(self.port), f'{self.user}@{self.hostname}']
        local_forwards_commands = []
        for local_port, remote_host_port in self.local_forwards.items():
            local_forwards_commands.extend(["-L", f"{local_port}:{remote_host_port}"])
        return connect_commands + local_forwards_commands

    def update_config(self, config: "HostConfig"):
        self_config = self.model_dump(mode='json')
        self_config.update(config.model_dump(mode='json'))
        return self.__class__(**self_config)


_DEFAULT_SSH_CONFIG_FILE = os.path.expanduser("~/.ssh/config")
_KNOWN_SSH_HOSTS_FILE = os.path.join(os.path.dirname(__file__), "known_ssh_hosts.json")
_KNOWN_SSH_HOSTS: Dict[str, HostConfig] = {}

def get_ssh_config_example() -> HostConfig:
    return HostConfig(
        host=f"ubuntu-{str(uuid.uuid4())[:8]}",
        hostname="127.0.0.1",
        user="root",
        port=22,
        local_forwards={"8888": "localhost:80"},
    )


def get_ssh_config(host: str) -> Optional[HostConfig]:
    return _KNOWN_SSH_HOSTS.get(host)


def update_ssh_config(config: HostConfig):
    _KNOWN_SSH_HOSTS[config.host] = config
    with open(_KNOWN_SSH_HOSTS_FILE, "w", encoding="utf-8") as f:
        f.write(json.dumps([config.model_dump() for config in _KNOWN_SSH_HOSTS.values()]))


def delete_ssh_config(host: str):
    _KNOWN_SSH_HOSTS.pop(host)
    with open(_KNOWN_SSH_HOSTS_FILE, "w", encoding="utf-8") as f:
        f.write(json.dumps([config.model_dump() for config in _KNOWN_SSH_HOSTS.values()]))


def load_ssh_config_file(file_path: str = _DEFAULT_SSH_CONFIG_FILE) -> Dict[str, HostConfig]:
    """从SSH配置文件加载主机配置

    Args:
        file_path: SSH配置文件路径，默认为~/.ssh/config

    Returns:
        Dict[str, HostConfig]: 主机名到配置的映射
    """
    if not os.path.exists(file_path):
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    host_configs = parse_text_to_configs(text)

    return host_configs

def parse_text_to_configs(text: str) -> Dict[str, HostConfig]:
    text_lines = text.splitlines()

    all_configs: Dict[str, Dict[str, str]] = {}
    current_host = None
    current_config = {}

    for line in text_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()

        if len(parts) < 2:
            continue

        key, values = parts[0], parts[1:]
        key = key.lower()

        if key == "host":
            # 保存前一个主机的配置
            if current_host and current_config:
                all_configs[current_host] = current_config

            # 开始新的主机配置
            current_host = values[0]
            current_config = {"host": values[0]}

        elif current_host and key == 'port':
            current_config[key] = int(values[0])

        elif current_host and key == 'localforward':
            current_config.setdefault('local_forwards', dict())
            current_config['local_forwards'][values[0]] = values[1]

        elif current_host and key == 'remoteforward':
            current_config.setdefault('remote_forwards', dict())
            current_config['remote_forwards'][values[0]] = values[1]

        elif current_host:
            # 添加配置项
            current_config[key] = values[0]

    # 保存最后一个主机的配置
    if current_host and current_config:
        all_configs[current_host] = current_config

    # 转换为HostConfig对象
    host_configs: Dict[str, HostConfig] = {}
    for host, config in all_configs.items():
        try:
            host_configs[host] = HostConfig(**config)
        except Exception:
            print(f"Warning: Failed to parse config for host {host}")
    return host_configs


def load_known_ssh_hosts() -> Dict[str, HostConfig]:
    if not os.path.exists(_KNOWN_SSH_HOSTS_FILE):
        return {}
    
    with open(_KNOWN_SSH_HOSTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    _KNOWN_SSH_HOSTS.update({config["host"]: HostConfig(**config) for config in data})
    
    return _KNOWN_SSH_HOSTS

if __name__ == "__main__":
    print(load_ssh_config_file()['zzzcb-ubuntu'].get_ssh_command())