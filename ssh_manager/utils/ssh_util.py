import subprocess

from ssh_manager.utils.ssh_configs import HostConfig


_PERSISTENT_SSH_CONNECTIONS = {}

def create_persistent_ssh_connection(host_config: HostConfig):
    """创建持久化SSH连接
    
    Args:
        host_config: 主机配置
    """
    ssh_command = host_config.get_ssh_command()
    ssh_process = subprocess.Popen(ssh_command)

    new_ssh_process = subprocess.Popen(ssh_command)

    if _PERSISTENT_SSH_CONNECTIONS.get(host_config.host):
        _PERSISTENT_SSH_CONNECTIONS[host_config.host].terminate()
    
    _PERSISTENT_SSH_CONNECTIONS[host_config.host] = new_ssh_process

    return ssh_process


def close_persistent_ssh_connection(host_config: HostConfig):
    """关闭持久化SSH连接
    
    Args:
        host_config: 主机配置
    """
    if _PERSISTENT_SSH_CONNECTIONS.get(host_config.host):
        _PERSISTENT_SSH_CONNECTIONS.pop(host_config.host).terminate()
