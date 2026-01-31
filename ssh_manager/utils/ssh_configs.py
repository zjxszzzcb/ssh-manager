import argparse
import json
import os
import uuid

from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Sequence, Union

# Environment variable for SSH config file path, defaults to ~/.ssh/config
SSH_CONFIG_FILE_PATH = os.getenv("SSH_HOME", os.path.expanduser("~/.ssh/config"))
# Path to mssh configuration directory
MSSH_HOME = os.path.expanduser("~/.mssh")
# Path to the JSON file that caches known SSH host configurations
HOST_CACHE_FILE_PATH = os.path.join(MSSH_HOME, "config.json")
# In-memory cache for storing host configurations to avoid repeated file I/O
HOST_CONFIG_CACHE: Dict[str, "HostConfig"] = {}


class HostConfig(BaseModel):
    """SSH host configuration model containing all connection parameters."""
    host: str                               # Host alias/name used in SSH config
    hostname: str                           # Actual hostname or IP address
    user: str                               # Username for SSH connection
    port: int = 22                          # SSH port number (default: 22)
    local_forwards: Dict[str, str] = {}     # Local port forwarding rules {local_port: remote_host:remote_port}
    remote_forwards: Dict[str, str] = {}    # Remote port forwarding rules {remote_port: local_host:local_port}
    proxy_command: Optional[str] = None     # ProxyCommand for SSH connection
    proxy_jump: Optional[str] = None        # ProxyJump host for SSH connection
    
    def get_ssh_command(self, extra_options: List[str] = None) -> List[str]:
        """Generate SSH command arguments list for this host configuration.

        Args:
            extra_options: Optional list of extra SSH options (e.g., ['-o', 'BatchMode=yes'])

        Returns:
            List[str]: Complete SSH command arguments including connection parameters and port forwarding
        """
        # Build basic SSH command with port, user, and hostname
        ssh_command_args = ['ssh', '-p', str(self.port), f'{self.user}@{self.hostname}']

        # Add extra options if provided (insert before port forwarding)
        if extra_options:
            ssh_command_args.extend(extra_options)

        port_forwarding_commands = []

        # Add local port forwarding arguments (-L flag)
        # Format: -L [bind_address:]port:host:hostport
        # Default bind_address is 127.0.0.1 if not specified
        for local_port, remote_host_port in self.local_forwards.items():
            # Replace localhost with 127.0.0.1 to avoid DNS resolution issues
            remote_host_port = remote_host_port.replace('localhost:', '127.0.0.1:')

            # Check if local_port includes bind address (e.g., "0.0.0.0:8080" or just "8080")
            if ':' in local_port:
                # Already includes bind address
                port_forwarding_commands.extend(["-L", f"{local_port}:{remote_host_port}"])
            else:
                # Add default 127.0.0.1 as bind address
                port_forwarding_commands.extend(["-L", f"127.0.0.1:{local_port}:{remote_host_port}"])

        # Add remote port forwarding arguments (-R flag)
        # Format: -R [bind_address:]port:host:hostport
        for remote_port, local_host_port in self.remote_forwards.items():
            # Replace localhost with 127.0.0.1 to avoid DNS resolution issues
            local_host_port = local_host_port.replace('localhost:', '127.0.0.1:')

            # Check if remote_port includes bind address
            if ':' in remote_port:
                # Already includes bind address
                port_forwarding_commands.extend(["-R", f"{remote_port}:{local_host_port}"])
            else:
                # Add default bind address (empty means all interfaces on remote)
                port_forwarding_commands.extend(["-R", f"{remote_port}:{local_host_port}"])

        # Add proxy command if specified
        if self.proxy_command:
            ssh_command_args.extend(["-o", f"ProxyCommand={self.proxy_command}"])

        # Add proxy jump if specified, resolve proxy jump host config if available
        if self.proxy_jump:
            proxy_jump = self.proxy_jump
            known_host_config = get_host_config(proxy_jump, None)
            if known_host_config:
                # Convert proxy jump host alias to full user@hostname:port format
                proxy_jump = f"{known_host_config.user}@{known_host_config.hostname}:{known_host_config.port}"
            ssh_command_args.extend(["-J", proxy_jump])

        # Combine base command with port forwarding arguments
        return ssh_command_args + port_forwarding_commands

    def update_config(self, config: "HostConfig"):
        """Update current configuration with values from another HostConfig.
        
        Args:
            config: HostConfig instance to merge with current configuration
            
        Returns:
            HostConfig: New HostConfig instance with merged configuration
        """
        # Convert current config to dictionary and merge with new config
        self_config = self.model_dump(mode='json')
        self_config.update(config.model_dump(mode='json'))
        return self.__class__(**self_config)

    def to_text(self) -> str:
        """Convert host configuration to SSH config file text format.

        Returns:
            str: SSH config file format text representation
        """
        indent = ' ' * 4

        # Build SSH config text with proper indentation
        texts = [
            f"Host {self.host}\n",
            f"{indent}HostName {self.hostname}\n",
            f"{indent}User {self.user}\n",
            f"{indent}Port {self.port}\n",
        ]

        # Add local port forwarding rules
        for local_port, remote_host_port in self.local_forwards.items():
            texts.append(f"{indent}# localhost:{local_port} -> remote's {remote_host_port}\n")
            texts.append(f"{indent}LocalForward {local_port} {remote_host_port}\n")

        # Add remote port forwarding rules
        for remote_port, local_host_port in self.remote_forwards.items():
            texts.append(f"{indent}# remote:{remote_port} -> localhost's {local_host_port}\n")
            texts.append(f"{indent}RemoteForward {remote_port} {local_host_port}\n")

        # Add proxy command if present
        if self.proxy_command:
            texts.append(f"{indent}# Command to connect through a proxy server\n")
            texts.append(f"{indent}ProxyCommand {self.proxy_command}\n")

        # Add proxy jump if present
        if self.proxy_jump:
            texts.append(f"{indent}# Through host to reach target\n")
            texts.append(f"{indent}ProxyJump {self.proxy_jump}\n")

        return "".join(texts)
    
    @classmethod
    def from_text(cls, text: str) -> Optional["HostConfig"]:
        """Parse SSH config text and return the first host configuration found.
        
        Args:
            text: SSH config file text content
            
        Returns:
            Optional[HostConfig]: First host configuration found, or None if no valid config
        """
        return next(iter(parse_text_to_configs(text).values()), None)


def get_ssh_config_example() -> HostConfig:
    """Generate an example SSH host configuration for demonstration purposes.

    Returns:
        HostConfig: Example configuration with random host name and sample settings
    """
    return HostConfig(
        host=f"machine-{str(uuid.uuid4())[:8]}",
        hostname="127.0.0.1",
        user="root",
        port=22,
        local_forwards={"8000": "localhost:80"},
        remote_forwards={"9090": "localhost:9090"},
        proxy_jump='jump-machine-host'
    )


def get_host_config(host: str, default: Any = None) -> Optional[HostConfig]:
    """Retrieve host configuration from cache by host alias.
    
    Args:
        host: Host alias to look up
        default: Default value to return if host not found
        
    Returns:
        Optional[HostConfig]: Host configuration if found, otherwise default value
    """
    return HOST_CONFIG_CACHE.get(host, default)


def update_host_config(config: Optional[HostConfig] = None):
    """Update host configuration in cache and persist to JSON file.
    
    Args:
        config: HostConfig instance to add/update in cache. If None, only saves current cache to file.
    """
    if isinstance(config, HostConfig):
        HOST_CONFIG_CACHE[config.host] = config
    
    # Ensure mssh config directory exists
    os.makedirs(MSSH_HOME, exist_ok=True)
    
    # Persist all cached configurations to JSON file
    with open(HOST_CACHE_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps([config.model_dump() for config in HOST_CONFIG_CACHE.values()], indent=4))


def remove_host_config(host_alias_or_config: Union[str, HostConfig]):
    """Remove host configuration from cache and update persistent storage.
    
    Args:
        host_alias_or_config: Either host alias string or HostConfig instance to remove
    """
    if isinstance(host_alias_or_config, HostConfig):
        # TODO: Implement removal by HostConfig instance
        raise NotImplementedError()
    else:
        # Remove by host alias
        HOST_CONFIG_CACHE.pop(host_alias_or_config)
    
    # Update persistent storage after removal
    update_host_config()


def load_ssh_config_file(file_path: str = SSH_CONFIG_FILE_PATH) -> Dict[str, HostConfig]:
    """Load host configurations from SSH config file.

    Args:
        file_path: Path to SSH config file, defaults to ~/.ssh/config

    Returns:
        Dict[str, HostConfig]: Dictionary mapping host names to their configurations
    """
    # Return empty dict if config file doesn't exist
    if not os.path.exists(file_path):
        return {}

    # Read and parse SSH config file content
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    host_configs = parse_text_to_configs(text)

    return host_configs


def parse_text_to_configs(text: str) -> Dict[str, HostConfig]:
    """Parse SSH config file text content into HostConfig objects.
    
    Args:
        text: SSH config file text content
        
    Returns:
        Dict[str, HostConfig]: Dictionary mapping host aliases to their configurations
    """
    text_lines = text.splitlines()

    # Dictionary to store raw config data before converting to HostConfig objects
    all_configs: Dict[str, Dict[str, str]] = {}
    current_host = None
    current_config: Dict[str, Any] = dict()

    # Parse each line of the SSH config file
    for line in text_lines:
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        parts = line.split()

        # Skip malformed lines
        if len(parts) < 2:
            continue

        key, values = parts[0], parts[1:]
        key = key.lower()  # SSH config keys are case-insensitive

        if key == "host":
            # Save previous host configuration if exists
            if current_host and current_config:
                all_configs[current_host] = current_config

            # Start new host configuration
            current_host = values[0]
            current_config = {"host": values[0]}

        elif current_host and key == 'port':
            # Convert port to integer
            current_config[key] = int(values[0])

        elif current_host and key == 'localforward':
            # Parse local port forwarding: LocalForward local_port remote_host:remote_port
            current_config.setdefault('local_forwards', dict())
            current_config['local_forwards'][values[0]] = values[1]

        elif current_host and key == 'remoteforward':
            # Parse remote port forwarding: RemoteForward remote_port local_host:local_port
            current_config.setdefault('remote_forwards', dict())
            current_config['remote_forwards'][values[0]] = values[1]

        elif current_host and key == 'proxycommand':
            # Join all values for proxy command (may contain spaces)
            current_config['proxy_command'] = " ".join(values)

        elif current_host and key == 'proxyjump':
            # ProxyJump host alias
            current_config['proxy_jump'] = values[0]

        elif current_host:
            # Handle other SSH config options (hostname, user, etc.)
            current_config[key] = values[0]

    # Save the last host configuration
    if current_host and current_config:
        all_configs[current_host] = current_config

    # Convert raw config data to HostConfig objects
    host_configs: Dict[str, HostConfig] = {}
    for host, config in all_configs.items():
        try:
            host_configs[host] = HostConfig(**config)
        except Exception:
            print(f"Warning: Failed to parse config for host {host}")
    return host_configs


def load_known_ssh_hosts() -> Dict[str, HostConfig]:
    """Load known SSH hosts from the JSON cache file.
    
    Returns:
        Dict[str, HostConfig]: Dictionary of known host configurations
    """
    # Return empty dict if cache file doesn't exist
    if not os.path.exists(HOST_CACHE_FILE_PATH):
        return {}
    
    # Load configurations from JSON file
    with open(HOST_CACHE_FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Update in-memory cache with loaded configurations
    HOST_CONFIG_CACHE.update({config["host"]: HostConfig(**config) for config in data})
    
    return HOST_CONFIG_CACHE


def parse_ssh_command(cmd_args: Sequence[str]) -> Optional[HostConfig]:
    """Parse SSH command line arguments and return corresponding HostConfig.
    
    Args:
        cmd_args: Sequence of command line arguments (e.g., ['ssh', 'user@host', '-p', '2222'])
        
    Returns:
        Optional[HostConfig]: Parsed host configuration, or None if parsing fails
    """
    class SilentArgumentParser(argparse.ArgumentParser):
        """Custom ArgumentParser that raises SystemExit instead of printing errors."""
        def error(self, message):
            raise SystemExit(message)

    if not cmd_args:
        return None

    # Set up argument parser for SSH command syntax
    parser = SilentArgumentParser(
        description="SSH Command Parser",
        exit_on_error=False
    )
    parser.add_argument("command", choices=['ssh'])
    parser.add_argument("host")
    parser.add_argument("-L", nargs="*", default=[], dest='local_forwards')
    parser.add_argument("-R", nargs="*", default=[], dest='remote_forwards')

    parser.add_argument("-p", "--port", type=int, required=False, default=22)
    parser.add_argument("-n", "--name", type=str, required=False, default="")

    try:
        args, _ = parser.parse_known_args(cmd_args)
    except SystemExit:
        return None

    # Load known host configurations from cache
    host_configs_map = load_known_ssh_hosts()

    # Parse user@hostname format
    if '@' in args.host:
        user, hostname = args.host.split("@")
        host = args.name or hostname  # Use provided name or default to hostname
    else:
        user = ""
        host = hostname = args.host

    known_host_config = host_configs_map.get(host)

    # If no user specified, try to find existing configuration
    if not user:
        if known_host_config:
            return known_host_config

        # Also check SSH config file for host configuration
        host_configs_map.update(load_ssh_config_file())
        return host_configs_map.get(host)

    # Parse local port forwarding arguments (-L local_port:target_host:target_port)
    local_forwards = {}
    for local_forward in args.local_forwards:
        parts = local_forward.split(":")
        if len(parts) != 3:
            print(f'Error LocalForward: {local_forward}')
            continue
        local_port, target_host, target_port = parts

        if not all([local_port, target_host, target_port]):
            print(f'Error LocalForward: {local_forward}')
            continue

        local_forwards[local_port] = f"{target_host}:{target_port}"

    # Parse remote port forwarding arguments (-R remote_port:target_host:target_port)
    remote_forwards = {}
    for remote_forward in args.remote_forwards:
        parts = remote_forward.split(":")
        if len(parts) != 3:
            print(f'Error RemoteForward: {remote_forward}')
            continue
        remote_port, target_host, target_port = parts

        if not all([remote_port, target_host, target_port]):
            print(f'Error RemoteForward: {remote_forward}')
            continue

        remote_forwards[remote_port] = f"{target_host}:{target_port}"

    # Create new host configuration from parsed arguments
    host_config = HostConfig(
        host=host,
        hostname=hostname,
        user=user,
        port=args.port,
        local_forwards=local_forwards,
        remote_forwards=remote_forwards
    )

    # Merge with known configuration if exists (prioritize command line arguments)
    if known_host_config:
        new_config = known_host_config.model_dump()
        new_config.update(host_config.model_dump())
        return HostConfig(**new_config)
    else:
        return host_config
