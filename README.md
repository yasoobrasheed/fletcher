# Agent Manager

Run Claude Code in isolated Docker containers while your code stays synced with your local IDE.

## Why?

Work in Cursor/VS Code with your AI assistant while Claude Code develops on the **same codebase** in parallel. The code is mounted from your filesystem—both see changes instantly, no conflicts.

## Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
echo "ANTHROPIC_API_KEY=paste_your_key_here" > .env
```

Requires: Docker, Python 3.8+, [Claude Code CLI](https://github.com/anthropics/claude-code)

## Usage

```bash
# Spawn agent (creates container + git clone)
am spawn https://github.com/user/repo

# Attach to Claude Code session
am attach <agent-id>

# List agents
am list

# Clean up
am clean
```

Press `Ctrl+B` then `D` to detach.

## Commands

| Command | Description |
| ------- | ----------- |
| `am spawn <repo-url>` | Create new agent in isolated container |
| `am list` | View all agents |
| `am attach <agent-id>` | Connect to agent's Claude session |
| `am stop <agent-id>` | Stop agent |
| `am clean` | Remove stopped agents + Docker cleanup |

## How it Works

1. Spawns Docker container with Claude Code
2. Clones repo to `~/.agent-manager/agents/<id>/`
3. Mounts directory into container (code syncs both ways)
4. Runs Claude in tmux session for easy attach/detach

## License

MIT
