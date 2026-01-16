# Cleanup Guide for Agent Manager

This guide explains how to properly clean up agents, containers, and Docker resources.

## Understanding Cleanup Levels

### 1. Agent Cleanup (Workspace + Database)
Removes agent records from database and deletes working directories.

### 2. Container Cleanup
Removes Docker containers (already done automatically when containers stop).

### 3. Image Cleanup
Removes Docker images to free up disk space.

## Automatic Cleanup

### Containers Auto-Remove
Containers are created with `--rm` flag, so they automatically clean up when stopped:
- ✅ Container removed when agent exits
- ✅ No orphaned containers left behind
- ❌ Image remains (needs manual cleanup)

## Manual Cleanup Commands

### Clean Stopped Agents
```bash
# Remove stopped agents (default)
am clean

# Confirm with 'y' when prompted
```

This removes:
- ✅ Agent database records
- ✅ Working directories (`.agents/<id>/`)
- ✅ Containers (if still running)

### Clean All Agents
```bash
# Remove ALL agents (including running ones)
am clean --all
```

⚠️ **Warning**: This stops and removes ALL agents!

### Clean Specific Status
```bash
# Clean only agents with errors
am clean --status error

# Clean running agents
am clean --status running
```

### Stop Individual Agent
```bash
# Stop agent and keep workspace
am stop <agent-id> --keep-workdir

# Stop agent and remove workspace
am stop <agent-id>
```

This handles both tmux and container modes automatically.

### Delete Individual Agent
```bash
am delete <agent-id>
```

This removes:
- ✅ Container (if exists)
- ✅ Working directory
- ✅ Database record

## Docker Resource Cleanup

### Clean Orphaned Containers
```bash
# Remove any leftover agent containers
am docker-clean --containers
```

This finds all containers named `agent-*` and removes them.

### Clean Docker Images
```bash
# Remove agent Docker images
am docker-clean --images
```

This removes:
- ✅ `claude-agent:latest` image
- ✅ Dangling images (layers with no tags)

### Clean Everything
```bash
# Remove all Docker resources (containers + images)
am docker-clean --all
```

Use this for a complete cleanup.

## Manual Docker Commands

If you need to clean up manually:

### List Agent Containers
```bash
docker ps -a --filter "name=agent-"
```

### Remove All Agent Containers
```bash
docker rm -f $(docker ps -a --filter "name=agent-" -q)
```

### Remove Agent Image
```bash
docker rmi claude-agent:latest
```

### Remove All Unused Images
```bash
docker image prune -a
```

### Check Docker Disk Usage
```bash
docker system df
```

## Cleanup Workflows

### Daily Cleanup (After Testing)
```bash
# 1. Clean stopped agents
am clean

# 2. Check remaining agents
am list
```

### Weekly Cleanup (Maintenance)
```bash
# 1. Clean all stopped agents
am clean

# 2. Clean Docker images if not needed
am docker-clean --images

# 3. Verify cleanup
docker ps -a --filter "name=agent-"
docker images | grep claude-agent
```

### Complete Reset
```bash
# 1. Remove all agents (will prompt for confirmation)
am clean --all

# 2. Clean all Docker resources
am docker-clean --all

# 3. Verify everything is clean
am list
docker ps -a --filter "name=agent-"
docker images | grep claude-agent
```

## What Gets Cleaned Where

### `am stop <id>`
- Stops tmux session OR Docker container
- Optionally removes working directory
- Updates database status

### `am delete <id>`
- Stops container (if exists)
- Removes working directory
- Removes database record

### `am clean`
- Calls delete for each matching agent
- Handles both tmux and container modes
- Batch operation with error handling

### `am docker-clean --containers`
- Finds containers by name pattern
- Force removes all agent containers
- Independent of database state

### `am docker-clean --images`
- Removes `claude-agent:latest` image
- Prunes dangling images
- Frees up disk space

## Troubleshooting

### Containers Won't Stop
```bash
# Force kill and remove
docker rm -f agent-<id>

# Or clean all
am docker-clean --containers --all
```

### Image Won't Delete (containers using it)
```bash
# Remove all containers first
am docker-clean --containers --all

# Then remove images
am docker-clean --images --all
```

### Working Directory Permission Denied
```bash
# Change ownership if needed
sudo chown -R $USER .agents/<id>

# Then delete
am delete <id>
```

### Database Out of Sync
If database has agents but containers/directories are gone:
```bash
# Clean will remove database records even if dirs don't exist
am clean --all
```

## Disk Space Management

### Check Space Usage
```bash
# Agent workspaces
du -sh .agents/*

# Docker resources
docker system df -v
```

### Free Up Space Quickly
```bash
# Remove everything
am clean --all
am docker-clean --all

# Prune Docker system
docker system prune -a
```

## Best Practices

1. **Regular Cleanup**: Run `am clean` after testing sessions
2. **Monitor Space**: Check `docker system df` weekly
3. **Remove Images**: Clean images when not actively developing
4. **Use Flags**: Use `--keep-workdir` if you need to inspect code
5. **Batch Operations**: Use `am clean --all` for full resets

## Safety Features

- ✅ Confirmation prompts for destructive operations
- ✅ Error handling continues cleaning other agents
- ✅ Auto-remove flag prevents container accumulation
- ✅ Database tracks container mode for proper cleanup
- ✅ Force flags for stuck containers

## Summary

| Command | Agents | Workspaces | Containers | Images |
|---------|--------|------------|------------|--------|
| `am stop <id>` | Updates | Optional | ✓ | - |
| `am delete <id>` | ✓ | ✓ | ✓ | - |
| `am clean` | ✓ | ✓ | ✓ | - |
| `docker-clean --containers` | - | - | ✓ | - |
| `docker-clean --images` | - | - | - | ✓ |
| `docker-clean --all` | - | - | ✓ | ✓ |

✓ = Removed
\- = Not affected
Optional = Depends on flags
