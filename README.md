# Agent Manager

A CLI tool for managing multiple Claude Code agents, each running in isolated git repository clones. Spawn agents to work on different repositories simultaneously and interact with them in real-time.

## Features

- **Isolated Environments**: Each agent gets a fresh git clone with complete isolation
- **Interactive Sessions**: Attach to agents for real-time collaboration
- **Multi-Agent Management**: Run multiple agents in parallel on different repositories
- **Persistent State**: Agent state is persisted across sessions in SQLite

## Prerequisites

- Python 3.8 or higher
- [Claude Code CLI](https://github.com/anthropics/claude-code) installed and available in PATH
- Git

## Installation

```bash
# Clone this repository
git clone https://github.com/yourusername/agent-manager.git
cd agent-manager

# Install in development mode
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt
```

## Quick Start

### 1. Spawn an Agent

Create a new agent with a fresh repository clone:

```bash
# Spawn an agent in interactive mode
agent-manager spawn https://github.com/user/repo
```

### 2. List Agents

View all active agents:

```bash
agent-manager list

# Filter by status
agent-manager list --status running
```

### 3. Attach to an Agent

Connect to an agent's interactive session:

```bash
agent-manager attach <agent-id>
```

Press `Ctrl+D` to detach without stopping the agent.

### 4. Stop an Agent

Gracefully stop a running agent:

```bash
agent-manager stop <agent-id>
```

### 5. Clean Up

Remove stopped agents and their working directories:

```bash
# Remove stopped agents only
agent-manager clean

# Remove all agents (including running)
agent-manager clean --all
```

## Commands

### `spawn`

```bash
agent-manager spawn <repo-url>
```

Spawn a new agent with a fresh repository clone in interactive mode.

### `list`
```bash
agent-manager list [--status STATUS]
```
List all agents.

**Options:**
- `--status, -s`: Filter by status (spawning, running, stopped, error)

### `attach`
```bash
agent-manager attach <agent-id>
```
Attach to an agent's interactive session. Press Ctrl+D to detach.

### `stop`
```bash
agent-manager stop <agent-id>
```
Stop a running agent.

### `info`
```bash
agent-manager info <agent-id>
```
Show detailed information about an agent.

### `clean`
```bash
agent-manager clean [--all]
```
Remove stopped agents and their working directories.

**Options:**
- `--all, -a`: Remove all agents including running ones

## Architecture

### Components

1. **CLI Interface** (`cli.py`): User-facing command-line interface
2. **Agent Manager** (`manager.py`): Core orchestration and lifecycle management
3. **Database Store** (`store.py`): SQLite persistence for agent state and outputs
4. **Process Manager** (`process.py`): Subprocess management for Claude Code CLI
5. **Utilities** (`utils.py`): Helper functions for git, paths, and process management

### Data Storage

- Database: `~/.agent-manager/agents.db`
- Working directories: `~/.agent-manager/agents/<agent-id>/`

### Agent States

- `spawning`: Agent is being created and repository is being cloned
- `running`: Agent is active and processing
- `stopped`: Agent has been stopped
- `error`: Agent encountered an error during spawn

## Use Cases

### Parallel Development

Work on multiple features simultaneously:

```bash
# Spawn agents for different features
agent-manager spawn https://github.com/myorg/app
agent-manager spawn https://github.com/myorg/app
agent-manager spawn https://github.com/myorg/app

# Check progress
agent-manager list

# Attach to agents to work on different features
agent-manager attach <agent-id-1>  # work on feature 1
agent-manager attach <agent-id-2>  # work on feature 2
```

### Code Review

Review multiple pull requests across different agents:

```bash
# Spawn agents for each PR
agent-manager spawn https://github.com/myorg/app
agent-manager spawn https://github.com/myorg/app

# Attach to each agent and review different PRs
agent-manager attach <agent-id-1>  # review PR #123
agent-manager attach <agent-id-2>  # review PR #124
```

### Interactive Exploration

Explore unfamiliar codebases:

```bash
# Spawn agent for exploration
agent-manager spawn https://github.com/someone/interesting-project

# Attach and interact with the agent
agent-manager attach <agent-id>
```

## Limitations

- Cannot reconnect to agents spawned in different sessions (yet)
- Each agent uses disk space for a full repository clone
- Interactive sessions require terminal support (PTY)

## Future Enhancements

- Git worktree mode for disk efficiency
- Agent-to-agent communication
- Web UI for visualization
- Docker containerization for stronger isolation
- Resume agents from previous sessions

## Troubleshooting

### "Claude Code CLI not found"

Make sure the `claude` command is in your PATH:

```bash
which claude
```

If not found, install Claude Code: https://github.com/anthropics/claude-code

### "Permission denied" errors

Ensure you have write permissions to `~/.agent-manager/` directory.

### Agent won't stop

Force kill the process:

```bash
# Get the PID
agent-manager info <agent-id>

# Kill manually
kill -9 <pid>

# Update status
agent-manager clean
```

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT License - see LICENSE file for details.
