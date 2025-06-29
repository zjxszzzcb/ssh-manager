import argparse
import json
import os
import uuid

from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Sequence


class HostConfig(BaseModel):
    host: str
    hostname: str
    user: str
    password: Optional[str] = None
    port: int = 22
    local_forwards: Dict[str, str] = {}
    remote_forwards: Dict[str, str] = {}
    proxy_command: Optional[str] = None
    proxy_jump: Optional[str] = None
    
    def get_ssh_command(self) -> List[str]:
        connect_commands = ['ssh', '-p', str(self.port), f'{self.user}@{self.hostname}']
        local_forwards_commands = []
        for local_port, remote_host_port in self.local_forwards.items():
            local_forwards_commands.extend(["-L", f"{local_port}:{remote_host_port}"])
        if self.proxy_command:
            connect_commands.extend(["-o", f"ProxyCommand={self.proxy_command}"])
        if self.proxy_jump:
            proxy_jump = self.proxy_jump
            known_host_config = get_ssh_config(proxy_jump, None)
            if known_host_config:
                proxy_jump = f"{known_host_config.user}@{known_host_config.hostname}:{known_host_config.port}"
            connect_commands.extend(["-J", proxy_jump])
        return connect_commands + local_forwards_commands

    def update_config(self, config: "HostConfig"):
        self_config = self.model_dump(mode='json')
        self_config.update(config.model_dump(mode='json'))
        return self.__class__(**self_config)

    def to_text(self, add_password: bool = False) -> str:
        indent = ' ' * 4

        texts = [
            f"Host {self.host}\n",
            f"{indent}HostName {self.hostname}\n",
            f"{indent}User {self.user}\n",
            f"{indent}Port {self.port}\n",
        ]

        if add_password:
            texts.append(f"{indent}Password {self.password}\n")

        for local_port, remote_host_port in self.local_forwards.items():
            texts.append(f"{indent}LocalForward {local_port}:{remote_host_port}\n")

        if self.proxy_command:
            texts.append(f"{indent}ProxyCommand {self.proxy_command}")

        return "".join(texts)
    
    @classmethod
    def from_text(cls, text: str) -> Optional["HostConfig"]:
        return next(iter(parse_text_to_configs(text).values()), None)


DEFAULT_SSH_CONFIG_FILE = os.path.expanduser("~/.ssh/config")
KNOWN_SSH_HOSTS_FILE = os.path.join(os.path.dirname(__file__), "known_ssh_hosts.json")
KNOWN_SSH_HOSTS: Dict[str, HostConfig] = {}


def get_ssh_config_example() -> HostConfig:
    return HostConfig(
        host=f"ubuntu-{str(uuid.uuid4())[:8]}",
        hostname="127.0.0.1",
        user="root",
        port=22,
        local_forwards={"8888": "localhost:80"},
    )


def get_ssh_config(host: str, default: Any = None) -> Optional[HostConfig]:
    return KNOWN_SSH_HOSTS.get(host, default)


def update_ssh_config(config: HostConfig):
    KNOWN_SSH_HOSTS[config.host] = config
    with open(KNOWN_SSH_HOSTS_FILE, "w", encoding="utf-8") as f:
        f.write(json.dumps([config.model_dump() for config in KNOWN_SSH_HOSTS.values()]))


def delete_ssh_config(host: str):
    KNOWN_SSH_HOSTS.pop(host)
    with open(KNOWN_SSH_HOSTS_FILE, "w", encoding="utf-8") as f:
        f.write(json.dumps([config.model_dump() for config in KNOWN_SSH_HOSTS.values()]))


def load_ssh_config_file(file_path: str = DEFAULT_SSH_CONFIG_FILE) -> Dict[str, HostConfig]:
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
    current_config: Dict[str, Any] = dict()

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

        elif current_host and key == 'proxycommand':
            current_config['proxy_command'] = " ".join(values)

        elif current_host and key == 'proxyjump':
            current_config['proxy_jump'] = values[0]

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
    if not os.path.exists(KNOWN_SSH_HOSTS_FILE):
        return {}
    
    with open(KNOWN_SSH_HOSTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    KNOWN_SSH_HOSTS.update({config["host"]: HostConfig(**config) for config in data})
    
    return KNOWN_SSH_HOSTS


class SilentArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise SystemExit(message)


def parse_ssh_command(args: Sequence[str]) -> Optional[HostConfig]:
    if not args:
        return None

    parser = SilentArgumentParser(
        description="SSH Command Parser",
        exit_on_error=False
    )
    parser.add_argument("command", choices=['ssh'])
    parser.add_argument("host")
    parser.add_argument("-L", nargs="*", default=[], dest='local_forwards')

    parser.add_argument("-p", "--port", type=int, required=False, default=22)
    parser.add_argument("--password", type=str, required=False, default=None)
    parser.add_argument("-n", "--name", type=str, required=False, default="")

    try:
        args, unkargs = parser.parse_known_args(args)
    except SystemExit:
        return None

    host_configs_map = load_known_ssh_hosts()

    if '@' in args.host:
        user, hostname = args.host.split("@")
        host = args.name or hostname
    else:
        user = ""
        host = hostname = args.host

    known_host_config = host_configs_map.get(host)

    if not user:
        if known_host_config:
            return known_host_config

        host_configs_map.update(load_ssh_config_file())
        return host_configs_map.get(host)

    local_forwards = {}
    for local_forward in args.local_forwards:
        local_port, forward_host, forward_port = local_forward.split(":")

        if not all([local_port, forward_host, forward_port]):
            print(f'Error LocalForward: {local_forward}')
            continue

        local_forwards[local_port] = f"{forward_host}:{forward_port}"

    host_config = HostConfig(
        host=host,
        hostname=hostname,
        user=user,
        port=args.port,
        password=args.password,
        local_forwards=local_forwards
    )

    if known_host_config:
        new_config = known_host_config.model_dump()
        new_config.update(host_config.model_dump())
        return HostConfig(**new_config)
    else:
        return host_config


if __name__ == "__main__":
    # print(parse_text_to_configs(
    #     "Host jetson\n"
    #     "HostName 192.168.31.100\n"
    #     "User zzzcb\n"
    #     "Port 22\n"
    #     "Password None\n"
    #     "ProxyCommand ssh -W %h:%p zzzcb-ubuntu\n"
    # )['jetson'].get_ssh_command())

    from ssh_manager.utils.ssh_util import create_persistent_ssh_connection

    create_persistent_ssh_connection(parse_text_to_configs(
        "Host jetson\n"
        "HostName 192.168.31.42\n"
        "User zzzcb\n"
        "Port 22\n"
        "Password None\n"
        "ProxyCommand ssh -W 192.168.31.42:22 zzzcb-ubuntu\n"
    )['jetson'])
