import subprocess
import time
import uuid
import threading
from typing import Dict, Optional
from ssh_manager.utils.ssh_configs import HostConfig


class SSHConnection(subprocess.Popen):
    def __init__(self, host_config: HostConfig, **kwargs):
        print(f"[INFO] Creating SSH connection using command: {host_config.get_ssh_command()}")
        super().__init__(
            args=host_config.get_ssh_command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **kwargs
        )
        self.available = False
        self._running = True
        self.daemon_thread = threading.Thread(target=self.keep_alive, daemon=True)
        self.daemon_thread.start()

        self.host_config = host_config
        

    def keep_alive(self):
        flag = str(uuid.uuid4())
        command = f'echo "{flag}"\n'
        self.stdin.write(command)
        self.stdin.flush()
        time.sleep(5)
        while self._running:
            try:
                content = self.stdout.readline()
                if not content:  # EOF reached
                    break
                if flag in content:
                    break
            except (IOError, ValueError):  # 管道已关闭
                break
        
        self.available = True
        while self._running:
            try:
                self.stdin.write(command)
                self.stdin.flush()
                output = self.stdout.readline()
                if not output:  # EOF reached
                    break
                time.sleep(3)
            except (IOError, ValueError):  # 管道已关闭
                break
        
        self.available = False
        self._running = False

    def terminate(self) -> None:
        """重写terminate方法以确保守护线程正确退出"""
        self._running = False
        super().terminate()

    def is_alive(self):
        return self.poll() is None and self.available
    
    def add_local_forward(self, local_port: int, forward_host: str, forward_port: int):
        self.host_config.local_forwards[local_port] = f"{forward_host}:{forward_port}"
        create_persistent_ssh_connection(self.host_config)
    

_PERSISTENT_SSH_CONNECTIONS: Dict[str, SSHConnection] = {}


def create_persistent_ssh_connection(host_config: HostConfig) -> SSHConnection:
    """创建持久化SSH连接
    
    Args:
        host_config: 主机配置
    """
    ssh_connection = SSHConnection(host_config)

    if _PERSISTENT_SSH_CONNECTIONS.get(host_config.host):
        _PERSISTENT_SSH_CONNECTIONS[host_config.host].terminate()
    
    _PERSISTENT_SSH_CONNECTIONS[host_config.host] = ssh_connection

    return ssh_connection


def close_persistent_ssh_connection(host_config: HostConfig):
    """关闭持久化SSH连接
    
    Args:
        host_config: 主机配置
    """
    if _PERSISTENT_SSH_CONNECTIONS.get(host_config.host):
        _PERSISTENT_SSH_CONNECTIONS.pop(host_config.host).terminate()


def get_ssh_connection(host: str) -> Optional[SSHConnection]:
    return _PERSISTENT_SSH_CONNECTIONS.get(host)


if __name__ == "__main__":
    # ssh_process = SSHConnection(["ssh", "jetson", "-L", "75:localhost:8000", "-t"])

    # while ssh_process.is_alive():
    #     # print("Alive")
    #     time.sleep(1)

    from paramiko.client import SSHClient
    client = SSHClient()
    client.load_system_host_keys()
    client.connect(hostname='192.168.31.100', username='zzzcb')
    print(client.invoke_shell())
    # stdin, stdout, stderr = client.exec_command('ls -l')
    # print(stdout.read().decode())
