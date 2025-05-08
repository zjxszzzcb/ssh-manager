import os
import json
from pydantic import BaseModel
from typing import Dict, List, Optional


class HostConfig(BaseModel):
    host: str
    hostname: str
    user: str
    password: Optional[str] = None
    port: int = 22
    local_forwards: List[Dict[str, str]] = []
    remote_forwards: List[Dict[str, str]] = []


_DEFAULT_SSH_CONFIG_FILE = os.path.expanduser("~/.ssh/config")
_KNOWN_SSH_HOSTS_FILE = os.path.join(os.path.dirname(__file__), "known_ssh_hosts.json")
_KNOWN_SSH_HOSTS: Dict[str, HostConfig] = {}


def get_ssh_config(host: str) -> Optional[HostConfig]:
    return _KNOWN_SSH_HOSTS.get(host)


def update_ssh_config(config: HostConfig):
    _KNOWN_SSH_HOSTS[config.host] = config
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

    configs: Dict[str, Dict[str, str]] = {}
    current_host = None
    current_config = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(None, 1)
            if len(parts) != 2:
                continue

            key, value = parts
            key = key.lower()

            if key == "host":
                # 保存前一个主机的配置
                if current_host and current_config:
                    configs[current_host] = current_config

                # 开始新的主机配置
                current_host = value
                current_config = {"host": value}
            elif current_host:
                # 添加配置项
                current_config[key] = value

        # 保存最后一个主机的配置
        if current_host and current_config:
            configs[current_host] = current_config

    # 转换为HostConfig对象
    host_configs: Dict[str, HostConfig] = {}
    for host, config in configs.items():
        try:
            # 确保必要的字段存在
            if "hostname" in config and "user" in config:
                # 转换端口为整数
                if "port" in config:
                    config["port"] = int(config["port"])
                
                host_configs[host] = HostConfig(**config)
        except Exception as e:
            print(f"Warning: Failed to parse config for host {host}: {e}")

    return host_configs


def load_known_ssh_hosts() -> Dict[str, HostConfig]:
    if not os.path.exists(_KNOWN_SSH_HOSTS_FILE):
        return {}

    with open(_KNOWN_SSH_HOSTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {config["host"]: HostConfig(**config) for config in data}

if __name__ == "__main__":
    print(load_ssh_config_file())
