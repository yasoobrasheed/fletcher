# Container Isolation for Agent Manager

## Overview

Agent Manager now supports running Claude Code agents in completely isolated Docker containers. This provides maximum security by isolating each agent's execution environment.

## Features

### Complete Isolation
- **Filesystem Isolation**: Each agent runs in its own container with no access to host files except the mounted workspace
- **Network Isolation**: Containers run with `--network none` by default (no internet access)
- **Resource Limits**:
  - 2GB memory limit per container
  - 2 CPU core limit
  - 100 process limit
- **Auto-cleanup**: Containers are automatically removed when agents stop

### Git Repository Handling
- The git repository is cloned on the **host filesystem** (in `.agents/<id>/`)
- The repository directory is **mounted as a volume** into the container at `/workspace`
- Changes made in the container are immediately visible on the host
- **Git worktrees are fully supported** - you can use worktrees on the host and mount different worktrees into different containers

## Usage

### Basic Container Spawning

```bash
# Spawn agent in isolated container
am spawn https://github.com/user/repo --container

# Spawn with skip permissions flag
am spawn https://github.com/user/repo --container --skip-permissions
```

### Prerequisites

1. **Docker Installation**
   - macOS: [Install Docker Desktop](https://docs.docker.com/desktop/install/mac-install/)
   - Linux: [Install Docker Engine](https://docs.docker.com/engine/install/)

2. **Docker Running**
   - Ensure Docker daemon is running before spawning agents
   - macOS: Start Docker Desktop application
   - Linux: `sudo systemctl start docker`

### First Time Setup

On first use, the agent image will be built automatically:
```bash
am spawn https://github.com/user/repo --container
# Output: Building agent Docker image (this may take a few minutes)...
```

## Architecture

### Container Image

The base image ([Dockerfile](Dockerfile)) includes:
- Ubuntu 22.04 base
- Git, curl, Python3, Node.js
- Claude Code CLI (placeholder - needs actual installation method)
- Non-root user (`agent`) for security
- Working directory: `/workspace`

### Volume Mounting

```
Host:      ~/.agents/<agent-id>/
            ↓ mounted as volume
Container: /workspace/
```

All git operations can be performed on either side and changes are synchronized instantly.

### Network Security

By default, containers run with `--network none`:
- ✅ Complete isolation from the internet
- ✅ No outbound connections possible
- ✅ No inbound connections possible
- ❌ Cannot access external APIs or download packages

If you need network access, you can modify the `network_mode` parameter in [container_process.py](agent_manager/container_process.py).

## Comparison: tmux vs Container Mode

| Feature | tmux Mode | Container Mode |
|---------|-----------|----------------|
| **Isolation** | Process-level | Container-level |
| **Network Access** | Full | None (isolated) |
| **Filesystem Access** | Full host access | Only workspace |
| **Resource Limits** | None | 2GB RAM, 2 CPU |
| **Cleanup** | Manual | Automatic |
| **Security** | Lower | Higher |
| **Performance** | Faster | Slight overhead |
| **Setup Required** | tmux only | Docker required |

## Git Worktree Support

### Single Repo, Multiple Agents with Worktrees

```bash
# On host: Create main repo clone
git clone https://github.com/user/repo main-repo
cd main-repo

# Create worktrees for different features
git worktree add ../worktree-feature-a
git worktree add ../worktree-feature-b

# Spawn agents pointing to different worktrees
# (Requires modification to support custom working directory)
# This is a future enhancement
```

### Current Behavior
- Each agent gets its own full clone
- Worktrees can be created on the host after cloning
- Multiple containers can mount the same worktree (read-only or shared)

## Security Considerations

### What Containers CAN'T Do
- ✅ Access the internet (network disabled)
- ✅ Access host files outside workspace
- ✅ Exceed 2GB memory
- ✅ Spawn unlimited processes
- ✅ Persist after agent stops (auto-removed)

### What Containers CAN Do
- Read/write to workspace (mounted host directory)
- Execute code within workspace
- Modify git repository
- Use full CPU (up to 2 cores)

### When to Use Container Mode
- **Use containers when:**
  - Working with untrusted code
  - Testing potentially dangerous operations
  - Need strict resource limits
  - Want automatic cleanup
  - Security is paramount

- **Use tmux mode when:**
  - Need full network access
  - Want faster performance
  - Working with trusted code
  - Need access to host tools/files

## Advanced Configuration

### Customize Container Settings

Edit [container_process.py](agent_manager/container_process.py) to modify:

```python
# Change network mode
network_mode="bridge"  # Allow network access

# Adjust resource limits
'--memory', '4g',     # Increase memory to 4GB
'--cpus', '4',        # Allow 4 CPUs

# Add custom mounts
'-v', '/host/path:/container/path'
```

### Build Custom Agent Image

Modify [Dockerfile](Dockerfile) to:
- Add additional tools
- Install specific Python/Node versions
- Pre-install dependencies
- Configure environment

Then rebuild:
```bash
docker build -t claude-agent:latest .
```

## Troubleshooting

### Docker Not Found
```
Error: Docker not found in PATH.
```
**Solution**: Install Docker from links above

### Docker Not Running
```
Error: Docker daemon is not running.
```
**Solution**: Start Docker Desktop (macOS) or `sudo systemctl start docker` (Linux)

### Permission Denied
```
Error: permission denied while trying to connect to the Docker daemon
```
**Solution**: Add user to docker group: `sudo usermod -aG docker $USER` (then log out/in)

### Image Build Fails
```
Failed to build Docker image
```
**Solution**:
1. Check Docker has internet access to download packages
2. Review Dockerfile for syntax errors
3. Manually build: `docker build -t claude-agent:latest .`

## Future Enhancements

- [ ] Support for custom network policies (allowlist specific domains)
- [ ] Multiple network modes (none/limited/full)
- [ ] Configurable resource limits per agent
- [ ] Support for GPU access in containers
- [ ] Container health monitoring
- [ ] Direct worktree support in spawn command
- [ ] Container logs collection
- [ ] Volume snapshot/backup functionality
