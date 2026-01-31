import logging
import os
import re
import subprocess
import threading
import time
from typing import Dict, List, Optional, Tuple

from ssh_manager.utils.ssh_configs import HostConfig

logger = logging.getLogger(__name__)


def test_ssh_key_auth(host_config: HostConfig) -> Tuple[bool, str]:
    """Test if SSH key authentication works.

    Uses BatchMode to disable password prompts, so if key auth fails
    the command will return non-zero immediately.

    Args:
        host_config: Host configuration

    Returns:
        (success: bool, message: str)
    """
    # Build test options for key authentication
    test_options = [
        '-o', 'BatchMode=yes',                      # Disable password prompts
        '-o', 'ConnectTimeout=10',                  # 10 second timeout
        '-o', 'StrictHostKeyChecking=accept-new',   # Auto accept new host keys
        '-o', 'PreferredAuthentications=publickey', # Only try publickey auth
    ]

    # Use get_ssh_command as base, add test options
    cmd = host_config.get_ssh_command(extra_options=test_options)
    cmd.append('echo SUCCESS')  # Simple test command that outputs and exits

    cmd_str = ' '.join(cmd)
    logger.debug(f"Testing key auth for {host_config.host}")
    print(f"[DEBUG] Running command: {cmd_str}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            logger.info(f"Key auth successful for {host_config.host}")
            return True, "SSH key authentication successful"

        # Parse error message
        stderr = result.stderr.strip()
        print(f"[DEBUG] SSH test failed with stderr: {stderr}")
        print(f"[DEBUG] SSH test failed with stdout: {result.stdout.strip()}")
        print(f"[DEBUG] SSH test exit code: {result.returncode}")

        if "Permission denied" in stderr or "publickey" in stderr:
            return False, "SSH key authentication failed - key not authorized on remote host"
        elif "Could not resolve hostname" in stderr:
            return False, f"DNS resolution failed for {host_config.hostname}"
        elif "Connection refused" in stderr:
            return False, f"Connection refused - check if SSH server is running on port {host_config.port}"
        elif "Connection timed out" in stderr or "timed out" in stderr.lower():
            return False, "Connection timed out - network may be unreachable"
        else:
            return False, f"SSH error: {stderr}"

    except subprocess.TimeoutExpired:
        return False, "Connection timeout"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def upload_ssh_key_with_ssh(host_config: HostConfig) -> Tuple[bool, str]:
    """Upload SSH public key using SSH command.

    Args:
        host_config: Host configuration

    Returns:
        (success: bool, message: str)
    """
    public_key_file = os.path.expanduser("~/.ssh/id_rsa.pub")

    # Check if public key exists
    if not os.path.exists(public_key_file):
        return False, "SSH public key not found at ~/.ssh/id_rsa.pub. Run 'ssh-keygen' to generate one."

    # Read public key
    try:
        with open(public_key_file, 'r') as f:
            public_key = f.read().strip()
        if not _validate_ssh_public_key(public_key):
            return False, "Invalid SSH public key format"
    except Exception as e:
        return False, f"Error reading public key: {e}"

    # Build SSH command to upload key
    # This will create .ssh directory and authorized_keys if they don't exist,
    # then append the public key
    ssh_command = (
        f"mkdir -p ~/.ssh && "
        f"chmod 700 ~/.ssh && "
        f"touch ~/.ssh/authorized_keys && "
        f"chmod 600 ~/.ssh/authorized_keys && "
        f"grep -q '{public_key}' ~/.ssh/authorized_keys || "
        f"echo '{public_key}' >> ~/.ssh/authorized_keys"
    )

    cmd = [
        'ssh',
        '-o', 'StrictHostKeyChecking=accept-new',
        '-o', 'ConnectTimeout=10',
        '-p', str(host_config.port),
        f'{host_config.user}@{host_config.hostname}',
        ssh_command
    ]

    logger.info(f"Uploading SSH key to {host_config.host} using SSH")
    print(f"[DEBUG] Running command: {' '.join(cmd[:6])} '<remote-command>'")

    try:
        # Run SSH command without capturing output so user can enter password
        result = subprocess.run(cmd, timeout=60)

        if result.returncode == 0:
            logger.info(f"Successfully uploaded SSH key to {host_config.host}")
            return True, "SSH key uploaded successfully"
        else:
            return False, f"SSH command failed with exit code {result.returncode}"

    except subprocess.TimeoutExpired:
        return False, "SSH connection timed out"
    except Exception as e:
        return False, f"Error running SSH command: {e}"


def _validate_ssh_public_key(key: str) -> bool:
    """Validate SSH public key format."""
    key = key.strip()
    # SSH public key format: type base64-encoded-data [comment]
    # Supported types: ssh-rsa, ssh-ed25519, ecdsa-sha2-nistp256, ecdsa-sha2-nistp384, ecdsa-sha2-nistp521
    ssh_key_pattern = r'^(ssh-(rsa|ed25519)|ecdsa-sha2-nistp\d+)\s+\S+'
    return bool(re.match(ssh_key_pattern, key))


class SSHConnectionManager:
    """Thread-safe manager for SSH connections."""

    def __init__(self):
        self._connections: Dict[str, 'SSHConnection'] = {}
        self._lock = threading.RLock()
        self._logger = logging.getLogger("SSHConnectionManager")

    def get(self, host: str) -> Optional['SSHConnection']:
        """Get connection by host alias (thread-safe)."""
        with self._lock:
            return self._connections.get(host)

    def add(self, host: str, conn: 'SSHConnection'):
        """Add connection (thread-safe). Closes existing connection if present."""
        with self._lock:
            if host in self._connections:
                self._connections[host].terminate()
            self._connections[host] = conn
            self._logger.debug(f"Added connection for {host}")

    def remove(self, host: str):
        """Remove and close connection (thread-safe)."""
        with self._lock:
            if host in self._connections:
                conn = self._connections.pop(host)
                conn.terminate()
                self._logger.debug(f"Removed connection for {host}")

    def cleanup_all(self):
        """Close all connections (thread-safe)."""
        with self._lock:
            for host, conn in list(self._connections.items()):
                try:
                    conn.terminate()
                except Exception as e:
                    self._logger.error(f"Error closing connection to {host}: {e}")
            self._connections.clear()

    def list_hosts(self) -> List[str]:
        """List all connected hosts (thread-safe)."""
        with self._lock:
            return list(self._connections.keys())


# Global singleton instance
_connection_manager = SSHConnectionManager()


class SSHConnection(subprocess.Popen):
    """SSH connection using pure subprocess (no paramiko)."""

    def __init__(self, host_config: HostConfig, **kwargs):
        """Initialize SSH connection.

        Args:
            host_config: Host configuration
            **kwargs: Additional arguments for subprocess.Popen

        Raises:
            TimeoutError: If connection fails to establish
        """
        self.host_config = host_config
        self.logger = logging.getLogger(f"SSHConnection.{host_config.host}")

        # Thread-safe state
        self._state_lock = threading.Lock()
        self._available = False
        self._running = False

        # Build SSH command
        ssh_cmd = self._build_ssh_command()
        ssh_cmd_str = ' '.join(ssh_cmd)
        self.logger.info(f"Starting SSH: {ssh_cmd_str}")
        print(f"[DEBUG] Creating SSH connection: {ssh_cmd_str}")

        # Initialize subprocess
        # Use DEVNULL for stdin/stdout to avoid pipe deadlocks
        # Keep stderr for error logging
        super().__init__(
            args=ssh_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            **kwargs
        )

        # Start monitoring thread
        with self._state_lock:
            self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_connection,
            daemon=True,
            name=f"SSH-Monitor-{host_config.host}"
        )
        self._monitor_thread.start()

        # Wait for connection to be ready
        if not self._wait_for_ready(timeout=10):
            self.terminate()
            raise TimeoutError(f"Failed to establish SSH connection to {host_config.host}")

    def _build_ssh_command(self) -> List[str]:
        """Build SSH command with keepalive options using get_ssh_command as base."""
        # Build keepalive and connection options
        connection_options = [
            '-o', 'ConnectTimeout=10',
            '-o', 'ServerAliveInterval=30',
            '-o', 'ServerAliveCountMax=3',
            '-o', 'TCPKeepAlive=yes',
            '-o', 'StrictHostKeyChecking=accept-new',
        ]

        # Use get_ssh_command as base (includes port, user, hostname, proxy, port forwarding)
        cmd = self.host_config.get_ssh_command(extra_options=connection_options)

        return cmd

    def _resolve_proxy_jump(self) -> str:
        """Resolve proxy jump alias to connection string."""
        proxy_jump = self.host_config.proxy_jump
        from ssh_manager.utils.ssh_configs import get_host_config
        known_config = get_host_config(proxy_jump, None)
        if known_config:
            return f"{known_config.user}@{known_config.hostname}:{known_config.port}"
        return proxy_jump

    def _monitor_connection(self):
        """Monitor connection health (runs in daemon thread)."""
        self.logger.debug("Monitor thread started")

        # Wait for connection to establish
        time.sleep(0.5)

        while True:
            with self._state_lock:
                if not self._running:
                    break

            # Check if process is still alive
            poll_result = self.poll()
            if poll_result is not None:
                self.logger.info(f"SSH process exited with code {poll_result}")
                break

            # Mark as available
            with self._state_lock:
                if self._running:
                    self._available = True

            time.sleep(2)

        # Mark as unavailable
        with self._state_lock:
            self._available = False
            self._running = False

        self.logger.debug("Monitor thread exited")

    def _wait_for_ready(self, timeout: int = 10) -> bool:
        """Wait for connection to be ready."""
        start = time.time()
        while time.time() - start < timeout:
            with self._state_lock:
                if self._available:
                    return True
            time.sleep(0.1)
        return False

    def terminate(self) -> None:
        """Terminate connection and clean up resources."""
        self.logger.info("Terminating connection")

        # Stop monitor thread
        with self._state_lock:
            self._running = False

        # Terminate subprocess
        try:
            super().terminate()
            super().wait(timeout=5)
        except Exception as e:
            self.logger.error(f"Error terminating subprocess: {e}")

        # Wait for monitor thread
        if hasattr(self, '_monitor_thread') and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)

        # Close pipes
        for pipe in [self.stdin, self.stdout, self.stderr]:
            if pipe:
                try:
                    pipe.close()
                except:
                    pass

        self.logger.info("Connection terminated")

    def is_alive(self) -> bool:
        """Check if connection is alive."""
        with self._state_lock:
            return self._available and self.poll() is None

    @property
    def host(self) -> str:
        """Get host identifier."""
        return self.host_config.host

    def add_local_forward(self, local_port: str, forward_host: str, forward_port: int):
        """Add a local port forwarding rule to the SSH connection.

        Args:
            local_port: Local port to forward from
            forward_host: Target host to forward to
            forward_port: Target port to forward to
        """
        self.host_config.local_forwards[local_port] = f"{forward_host}:{forward_port}"
        create_persistent_ssh_connection(self.host_config)

    def add_remote_forward(self, remote_port: str, local_host: str, local_port: int):
        """Add a remote port forwarding rule to the SSH connection.

        Args:
            remote_port: Remote port to forward from
            local_host: Local host to forward to
            local_port: Local port to forward to
        """
        self.host_config.remote_forwards[remote_port] = f"{local_host}:{local_port}"
        create_persistent_ssh_connection(self.host_config)


def _create_and_register_connection(host_config: HostConfig, timeout: int = 10) -> Optional[SSHConnection]:
    """Create SSH connection and register with manager.

    Args:
        host_config: Host configuration
        timeout: Connection timeout in seconds

    Returns:
        SSHConnection if successful, None otherwise
    """
    try:
        ssh_connection = SSHConnection(host_config)
        _connection_manager.add(host_config.host, ssh_connection)
        return ssh_connection
    except (TimeoutError, Exception) as e:
        logger.error(f"Failed to create SSH connection: {e}")
        return None


def create_persistent_ssh_connection(
    host_config: HostConfig,
    debug: bool = False,
    key_check: bool = True,
    timeout: int = 10
) -> Optional[SSHConnection]:
    """Create SSH connection with optional key upload prompt.

    Workflow:
    1. Test key authentication (if key_check=True)
    2. If failed, ask user in terminal if they want to upload key
    3. If user says yes, run ssh-copy-id
    4. Retry connection

    Args:
        host_config: Host configuration
        debug: Enable debug mode
        key_check: If True, test key auth and prompt for upload; if False, create connection directly
        timeout: Connection timeout in seconds

    Returns:
        SSHConnection if successful, None otherwise
    """
    # Step 1: Test if key auth already works (if key_check is enabled)
    if key_check:
        success, message = test_ssh_key_auth(host_config)

        if success:
            logger.info(f"Key auth works for {host_config.host}, creating connection")
            return _create_and_register_connection(host_config, timeout=timeout)

        # Step 2: Key auth failed - ask user in terminal
        logger.warning(f"Key auth failed for {host_config.host}: {message}")
        print(f"\n[INFO] SSH Key Authentication Failed")
        print(f"[INFO] Host: {host_config.host} ({host_config.user}@{host_config.hostname}:{host_config.port})")
        print(f"[ERROR] {message}")
        print(f"\n[INFO] Would you like to upload your SSH public key?")
        print(f"[INFO] This will require password authentication for one-time setup.")

        choice = input("Upload key now? [y/N]: ").strip().lower()

        if choice != 'y':
            # User said no, try to create connection anyway
            print("[INFO] Skipping key upload, attempting connection...")
            return _create_and_register_connection(host_config, timeout=timeout)

        # Step 3: User said yes, run ssh command to upload key
        print(f"\n[INFO] Uploading SSH key to {host_config.host}...")
        upload_success, upload_message = upload_ssh_key_with_ssh(host_config)

        if not upload_success:
            logger.error(f"Key upload failed: {upload_message}")
            print(f"[ERROR] Key upload failed: {upload_message}")
            return None

        print(f"[INFO] Key uploaded successfully!")

        # Step 4: Wait a moment for server to process the new key
        print(f"[INFO] Waiting for server to process the new key...")
        time.sleep(2)

        # Step 5: Retry key auth test
        logger.info("Retrying key auth test after upload")
        success, message = test_ssh_key_auth(host_config)

        if not success:
            logger.error(f"Key auth still fails after upload: {message}")
            print(f"[ERROR] Key authentication still fails after upload: {message}")
            return None

        # Step 6: Success! Create connection
        print(f"[INFO] Key authentication successful, creating connection...")
        return _create_and_register_connection(host_config, timeout=timeout)
    else:
        # Direct connection mode - skip key check
        return _create_and_register_connection(host_config, timeout=timeout)


def close_persistent_ssh_connection(host_config: HostConfig):
    """Close SSH connection."""
    _connection_manager.remove(host_config.host)


def get_ssh_connection(host: str) -> Optional[SSHConnection]:
    """Get existing SSH connection."""
    return _connection_manager.get(host)


def cleanup_all_connections():
    """Close all SSH connections."""
    _connection_manager.cleanup_all()
