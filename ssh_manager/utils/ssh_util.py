import logging
import os
import subprocess
import threading
import time
import traceback
import uuid

from paramiko.client import SSHClient
from paramiko.ssh_exception import AuthenticationException, SSHException
from typing import Dict, Optional

from ssh_manager.utils.ssh_configs import HostConfig
from ssh_manager.utils.terminal_util import clear_terminal


def load_public_key():
    """Load SSH public key from the default location (~/.ssh/id_rsa.pub).
    
    Returns:
        str: Content of the public key file
    """
    public_key_file = os.path.expanduser("~/.ssh/id_rsa.pub")
    if not os.path.exists(public_key_file):
        pass
    with open(public_key_file, "r") as f:
        return f.read()


def load_private_key():
    """Load SSH private key from the default location (~/.ssh/id_rsa).
    
    Returns:
        str: Content of the private key file
    """
    private_key_file = os.path.expanduser("~/.ssh/id_rsa")
    if not os.path.exists(private_key_file):
        pass
    with open(private_key_file, "r") as f:
        return f.read()


class SSHConnection(subprocess.Popen):
    """SSH connection class that extends subprocess.Popen to manage SSH connections.

    This class provides a wrapper around SSH connections with automatic key-based
    authentication, password fallback, and connection monitoring through a daemon thread.
    """

    def __init__(self, host_config: HostConfig, **kwargs):
        """Initialize SSH connection with the given host configuration.

        Args:
            host_config (HostConfig): Configuration object containing SSH connection details
            **kwargs: Additional arguments passed to subprocess.Popen

        Raises:
            TimeoutError: If connection cannot be established within 10 seconds
        """
        self.client = SSHClient()
        self.host_config = host_config
        self.logger = logging.getLogger(self.host_config.host)

        # Initialize the SSH client connection
        self._initialize_client()

        print(f"[INFO] Establishing an SSH connection, this requires key-based authentication.")

        # Connection state management
        self._available = False
        self._running = True
        # Initialize subprocess with SSH command
        print(f"Executing command >> `{' '.join(self.host_config.get_ssh_command())}`")
        super().__init__(
            args=host_config.get_ssh_command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **kwargs
        )
        # Start daemon thread to monitor connection
        self.daemon_thread = threading.Thread(target=self._connection_daemon, daemon=True)
        self.daemon_thread.start()

        # Wait for connection to be ready (maximum 10 seconds)
        for _ in range(100):
            if self._available:
                break
            time.sleep(0.1)
        else:
            raise TimeoutError("Failed to create ssh connection")

    def _initialize_client(self):
        """Initialize the SSH client with authentication and proxy settings.

        This method attempts key-based authentication first, then falls back to
        password authentication if needed. It also handles SSH public key upload
        for future key-based authentication.
        """
        # TODO: Implement paramiko SSHClient support for proxy connections
        if self.host_config.proxy_command or self.host_config.proxy_jump:
            print(f"[WARNING] paramiko SSHClient is disabled in proxy mode")
            return
        elif not self.host_config.password:
            print(f"[WARNING] paramiko SSHClient is disabled without password")
            return
        try:
            print(
                f"[INFO] Trying to connect "
                f"`{self.host_config.user}@{self.host_config.hostname} -p {self.host_config.port}` "
            )
            # Load system host keys and attempt connection
            self.client.load_system_host_keys()
            self.client.connect(
                hostname=self.host_config.hostname,
                username=self.host_config.user,
                port=self.host_config.port,
                auth_timeout=3,
            )
        except SSHException:
            # Fallback to password authentication if key-based auth fails
            for _ in range(3):
                success, password = self.connect_by_password(self.host_config)
                if success:
                    break
                self.host_config.password = ""
            else:
                print(
                    f"[ERROR] Fail to connect "
                    f"`{self.host_config.user}@{self.host_config.hostname} -p {self.host_config.port}` "
                )
                return

            # Ask user if they want to upload SSH public key for future key-based authentication
            choice = input(
                "SSH key-based authentication failed but password authentication succeeded. "
                "mssh requires key-based authentication. Do you want to upload your public key? [y/N]:"
            )

            if choice.lower() == 'y':
                # Upload SSH public key for future key-based authentication
                print("[INFO] Uploading SSH public key (~/.ssh/id_rsa.pub)")
                stdin, stdout, stderr = self.client.exec_command(
                    f"echo \"\n{load_public_key()}\" >> ~/.ssh/authorized_keys"
                )
                stdout = stdout.read().decode('utf-8')
                stderr = stderr.read().decode('utf-8')
                print(stdout + stderr)
                if stdout and not stderr:
                    print("[INFO] Successfully uploaded SSH public key")

    @property
    def host(self):
        """Get the host identifier from the configuration.
        
        Returns:
            str: The host identifier
        """
        return self.host_config.host

    def add_local_forward(self, local_port: str, forward_host: str, forward_port: int):
        """Add a local port forwarding rule to the SSH connection.
        
        Args:
            local_port (str): Local port to forward from
            forward_host (str): Target host to forward to
            forward_port (int): Target port to forward to
        """
        self.host_config.local_forwards[local_port] = f"{forward_host}:{forward_port}"
        create_persistent_ssh_connection(self.host_config)

    def exec_command(self, command: str) -> str:
        """Execute a command on the remote SSH server.
        
        Args:
            command (str): Command to execute on the remote server
            
        Returns:
            str: Combined stdout and stderr output from the command
        """
        if isinstance(self.client, SSHClient):
            stdin, stdout, stderr = self.client.exec_command(command)
            return stdout.read().decode(encoding="utf-8") + stderr.read().decode(encoding="utf-8")
        else:
            print("[WARNING] No paramiko SSHClient available")
            return ""

    def _connection_daemon(self):
        """Daemon thread that monitors the SSH connection health.
        
        This method runs in a separate thread to continuously monitor the SSH
        connection by sending periodic echo commands and checking responses.
        It marks the connection as available once initial setup is complete.
        """
        # Generate unique flag for connection testing
        flag = str(uuid.uuid4())
        command = f'echo "{flag}"\n'
        
        # Send initial test command
        self.stdin.write(command)
        self.stdin.flush()
        
        # Wait for initial response to confirm connection is ready
        while self._running:
            try:
                content = self.stdout.readline()
                print(content)
                if not content:
                    break
                if flag in content:
                    break
            except (IOError, ValueError):  # Pipe closed
                break
        
        # Mark connection as available
        self._available = True
        
        # Continue monitoring connection with periodic heartbeatINFO:jetson:stop
        while self._running:
            try:
                self.stdin.write(command)
                self.stdin.flush()
                output = self.stdout.readline()
                if not output:  # EOF reached
                    break
                self.logger.debug(f"pause.")
                time.sleep(3)  # Wait 3 seconds between heartbeats
            except (IOError, ValueError):  # Pipe closed
                print(traceback.print_exc())
                break

        # Connection lost or terminated
        self.logger.info(f"Running state: {self._running}, stop {self.host_config.host}")
        self._available = False

    def terminate(self) -> None:
        """Override terminate method to ensure daemon thread exits properly.
        
        This method stops the daemon thread and closes the persistent SSH connection
        before calling the parent terminate method.
        """
        self.logger.info(f"Terminate {self.host_config.host}")
        self._running = False
        super().terminate()
        close_persistent_ssh_connection(self.host_config)

    def is_alive(self):
        """Check if the SSH connection is alive and available.
        
        Returns:
            bool: True if connection is alive and available, False otherwise
        """
        return self.poll() is None and self._available

    def connect_by_password(self, host_config: HostConfig):
        """Attempt to connect using password authentication.
        
        Args:
            host_config (HostConfig): Host configuration containing connection details
            
        Returns:
            tuple: (success: bool, password: str) - Success status and password used
        """
        password = host_config.password
        success = False
        try:
            # Prompt for password if not provided
            if not password:
                password = input("Password:")
                
            # Attempt password-based connection
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


# Global dictionary to store persistent SSH connections
_PERSISTENT_SSH_CONNECTIONS: Dict[str, SSHConnection] = {}


@clear_terminal
def create_persistent_ssh_connection(host_config: HostConfig, debug: bool=False) -> Optional[SSHConnection]:
    """Create a persistent SSH connection that can be reused.
    
    This function creates a new SSH connection and stores it in the global
    connections dictionary. If a connection already exists for the host,
    it terminates the old one before creating a new one.
    
    Args:
        host_config (HostConfig): Configuration object containing SSH connection details
        debug (bool): Whether to enable debug mode
        
    Returns:
        Optional[SSHConnection]: The created SSH connection, or None if creation failed
    """
    try:
        # Terminate existing connection if present
        close_persistent_ssh_connection(host_config)
            
        # Create new SSH connection
        ssh_connection = SSHConnection(host_config)
    
        # Store the new connection
        _PERSISTENT_SSH_CONNECTIONS[host_config.host] = ssh_connection

        while True:
            if debug:
                time.sleep(0.1)
            else:
                break

        return ssh_connection

    except (RuntimeError, TimeoutError, KeyboardInterrupt):
        print(traceback.format_exc())
        return None


def close_persistent_ssh_connection(host_config: HostConfig):
    """Close and remove a persistent SSH connection.
    
    Args:
        host_config (HostConfig): Configuration object containing the host to disconnect
    """
    if _PERSISTENT_SSH_CONNECTIONS.get(host_config.host):
        _PERSISTENT_SSH_CONNECTIONS.pop(host_config.host).terminate()


def get_ssh_connection(host: str) -> Optional[SSHConnection]:
    """Retrieve an existing persistent SSH connection by host identifier.
    
    Args:
        host (str): Host identifier to look up
        
    Returns:
        Optional[SSHConnection]: The SSH connection if found, None otherwise
    """
    return _PERSISTENT_SSH_CONNECTIONS.get(host)
