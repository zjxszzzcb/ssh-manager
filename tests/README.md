# SSH Manager Test Environment

This directory contains a Docker-based test environment for SSH Manager.

## Quick Start

### 1. Start Test Server

```bash
cd tests
docker compose up -d
```

This will start a Linux SSH test server listening on `localhost:2222`.

### 2. Test Connection

There are multiple ways to test the connection:

**Using mssh CLI (Recommended)**:
```bash
# Quick connect (opens terminal directly)
mssh 127.0.0.1

# Or use full command
mssh ssh user@127.0.0.1 -p 2222

# Use mssh TUI interface
mssh
```

**Using standard ssh command**:
```bash
ssh user@127.0.0.1 -p 2222
```

**Login Credentials**:
- Username: `user`
- Password: `user`

### 3. Test Port Forwarding

The test container runs an HTTP server on port 8080, useful for testing port forwarding:

```bash
# Add local port forwarding in mssh TUI
# Listen Port: 8080
# Listen Host: 127.0.0.1  
# Target Port: 8080
# Target Host: 127.0.0.1
# Type: Local

# Then visit http://localhost:8080 in your browser
# You should see the file listing from inside the container
```

### 4. Stop Test Server

```bash
docker compose down
```

## Environment Details

### Server Configuration
- **Image**: Python 3.11 slim
- **SSH Port**: 2222 (mapped to container's 22)
- **HTTP Port**: 8080 (for port forwarding tests)
- **User**: user/user
- **Container Name**: ssh-test-server
- **Hostname**: test-server

### Available Test Scenarios

1. **Basic SSH Connection**
   - Password authentication
   - Quick connect (`mssh 127.0.0.1`)
   
2. **Configuration Management**
   - Edit configuration in TUI
   - Test password field persistence
   - Test configuration saved to `~/.mssh/config.json`

3. **Port Forwarding**
   - Local port forwarding (access container services)
   - Remote port forwarding
   - Dynamic add/remove forwarding rules

4. **TUI Features**
   - Keyboard navigation
   - Configuration editor
   - Connection status monitoring

## Troubleshooting

### Container Won't Start
```bash
# View logs
docker compose logs

# Restart container
docker compose restart
```

### Port Conflict
If port 2222 is already in use, modify the port mapping in `docker-compose.yml`:
```yaml
ports:
  - "2223:22"  # Use 2223 instead
```

### Clean Up
```bash
# Stop and remove container
docker compose down

# Rebuild and restart
docker compose up -d --build
```

