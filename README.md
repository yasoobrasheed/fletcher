# Agent Manager

A CLI tool for managing multiple Claude Code agents, each running in isolated git repository clones. Spawn agents to work on different repositories simultaneously and interact with them in real-time.

## Features

- **Isolated Environments**: Each agent gets a fresh git clone with complete isolation
- **Interactive Sessions**: Attach to agents for real-time collaboration
- **Multi-Agent Management**: Run multiple agents in parallel on different repositories
- **Persistent State**: Agent state is persisted across sessions in SQLite
