import subprocess
import time
import uuid
import threading
from typing import List
from ssh_manager.utils.ssh_configs import HostConfig


_PERSISTENT_SSH_CONNECTIONS = {}


class SSHConnection(subprocess.Popen):
    def __init__(self, commands: List[str], **kwargs):
        super().__init__(
            args=commands,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **kwargs
        )
        self.available = False
        self.daemon_thread = threading.Thread(target=self.keep_alive, daemon=True)
        self.daemon_thread.start()
        

    def keep_alive(self):
        flag = str(uuid.uuid4())
        command = f'echo "{flag}"\n'
        self.stdin.write(command)
        self.stdin.flush()
        time.sleep(5)
        while True:
            content = self.stdout.readline()
            if flag in content:
                break
            print(content)
        self.available = True
        while True:
            self.stdin.write(command)
            self.stdin.flush()
            output = self.stdout.readline()
            print(output)
            time.sleep(3)

    def is_alive(self):
        return self.poll() is None and self.available

def create_persistent_ssh_connection(host_config: HostConfig):
    """创建持久化SSH连接
    
    Args:
        host_config: 主机配置
    """
    ssh_command = host_config.get_ssh_command()
    ssh_process = SSHConnection(ssh_command)

    if _PERSISTENT_SSH_CONNECTIONS.get(host_config.host):
        _PERSISTENT_SSH_CONNECTIONS[host_config.host].terminate()
    
    _PERSISTENT_SSH_CONNECTIONS[host_config.host] = ssh_process

    return ssh_process


def close_persistent_ssh_connection(host_config: HostConfig):
    """关闭持久化SSH连接
    
    Args:
        host_config: 主机配置
    """
    if _PERSISTENT_SSH_CONNECTIONS.get(host_config.host):
        _PERSISTENT_SSH_CONNECTIONS.pop(host_config.host).terminate()


def get_connection(host: str):
    return _PERSISTENT_SSH_CONNECTIONS.get(host)


if __name__ == "__main__":
    ssh_process = SSHConnection(["ssh", "jetson", "-L", "75:localhost:8000", "-t"])

    while ssh_process.is_alive():
        # print("Alive")
        time.sleep(1)
