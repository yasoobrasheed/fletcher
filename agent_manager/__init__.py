"""Agent Manager - Manage Claude Code agents in isolated git clones."""

__version__ = "0.1.0"

from .manager import AgentManager
from .store import AgentStore

__all__ = ['AgentManager', 'AgentStore', 'AgentProcess']
