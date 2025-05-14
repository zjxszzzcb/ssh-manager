import os
import subprocess
import threading
import time
import traceback
import uuid

from paramiko.client import SSHClient
from paramiko.ssh_exception import AuthenticationException
from typing import Dict, Optional

from ssh_manager.utils.ssh_configs import HostConfig


def load_public_key():
    public_key_file = os.path.expanduser("~/.ssh/id_rsa.pub")
    if not os.path.exists(public_key_file):
        pass
    with open(public_key_file, "r") as f:
        return f.read()


def load_private_key():
    private_key_file = os.path.expanduser("~/.ssh/id_rsa")
    if not os.path.exists(private_key_file):
        pass
    with open(private_key_file, "r") as f:
        return f.read()


class SSHConnection(subprocess.Popen):
    def __init__(self, host_config: HostConfig, **kwargs):
        self.initialize = False
        self.client = SSHClient()
        print(f"Executing command >> `{' '.join(host_config.get_ssh_command())}`")
        try:
            self.client.load_system_host_keys()
            self.client.connect(
                hostname=host_config.hostname,
                username=host_config.user,
                port=host_config.port,
                auth_timeout=3,
            )
        except AuthenticationException:
            for _ in range(3):
                success, password = self.connect_by_password(host_config)
                if success:
                    break
                host_config.password = ""
            else:
                print(f"Faild to connect `{host_config.user}@{host_config.hostname}` on port `{host_config.port}`")
                return

            print("[INFO] Uploading SSH public key (~/.ssh/id_rsa.pub)")
            stdin, stdout, stderr = self.client.exec_command(
                f"echo \"\n{load_public_key()}\" >> ~/.ssh/authorized_keys"
            )
            stdout = stdout.read().decode('utf-8')
            stderr = stderr.read().decode('utf-8')
            print(stdout+stderr)
            if stdout and not stderr:
                print("[INFO] Successfully to upload ssh public key")

        self.initialize = True

        print(f"[INFO] Establishing an SSH connection, this requires key-based authentication.")
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

        # 等待加载完成，最大10秒
        for _ in range(100):
            if self.available:
                break
            time.sleep(0.1)
        else:
            raise TimeoutError("Failed to create ssh connection")

        self.host_config = host_config

    def add_local_forward(self, local_port: str, forward_host: str, forward_port: int):
        self.host_config.local_forwards[local_port] = f"{forward_host}:{forward_port}"
        create_persistent_ssh_connection(self.host_config)

    def exec_command(self, command: str) -> str:
        stdin, stdout, stderr = self.client.exec_command(command)
        return stdout.read().decode(encoding="utf-8") + stderr.read().decode(encoding="utf-8")

    def keep_alive(self):
        flag = str(uuid.uuid4())
        command = f'echo "{flag}"\n'
        self.stdin.write(command)
        self.stdin.flush()
        while self._running:
            try:
                content = self.stdout.readline()
                print(content)
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

    def connect_by_password(self, host_config: HostConfig):
        password = host_config.password
        success = False
        try:
            if not password:
                password = input("Password:")
            self.client.connect(
                hostname=host_config.hostname,
                username=host_config.user,
                password=password,
                port=host_config.port,
                auth_timeout=3
            )
            success = True
        except Exception as e:
            if isinstance(e, AuthenticationException):
                print("Authentication failed.")
            else:
                print(traceback.format_exc())
            password = ""
        return success, password


_PERSISTENT_SSH_CONNECTIONS: Dict[str, SSHConnection] = {}


def create_persistent_ssh_connection(host_config: HostConfig) -> Optional[SSHConnection]:
    """创建持久化SSH连接
    
    Args:
        host_config: 主机配置
    """
    try:
        ssh_connection = SSHConnection(host_config)

        if _PERSISTENT_SSH_CONNECTIONS.get(host_config.host):
            _PERSISTENT_SSH_CONNECTIONS[host_config.host].terminate()
    
        _PERSISTENT_SSH_CONNECTIONS[host_config.host] = ssh_connection

        return ssh_connection

    except (RuntimeError, TimeoutError, KeyboardInterrupt):
        print(traceback.format_exc())
        return None


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
    ssh_process = SSHConnection(HostConfig(host='ucloud', hostname='118.194.255.34', user='ubuntu', password='731008'))

    time.sleep(10)

    while ssh_process.is_alive():
        print("Alive")
        time.sleep(1)

    # client = SSHClient()
    # client.load_system_host_keys()
    # print(client.get_host_keys()['192.168.31.100'])
    # client.connect(hostname='192.168.31.100', username='zzzcb')
    # stdin, stdout, stderr = client.exec_command('ls -l')
    # print(stdout.read().decode())
    
