"""Process management for Claude Code CLI agents."""
import shutil
import subprocess
import time
from typing import Optional
from .store import AgentStore


class AgentProcess:
    """Manages a Claude Code CLI subprocess."""

    def __init__(self, agent_id: str, working_dir: str, store: AgentStore):
        """Initialize the agent process manager.

        Args:
            agent_id: Agent identifier
            working_dir: Working directory for the agent
            store: Database store for output persistence
        """
        self.agent_id = agent_id
        self.working_dir = working_dir
        self.store = store
        self._tmux_session: Optional[str] = None

    def _start_claude_with_skip_permissions(self, session_name: str):
        """Start Claude with skip permissions flag and auto-accept the prompt.

        Args:
            session_name: The tmux session name
        """
        # Send command to start claude with skip permissions flag
        subprocess.run(
            ['tmux', 'send-keys', '-t', session_name, 'claude --dangerously-skip-permissions'],
            check=True,
            capture_output=True
        )

        # Give Claude a moment to show the permissions prompt
        time.sleep(1.0)

        # Navigate to "Yes, I accept" option (down arrow) and confirm
        subprocess.run(
            ['tmux', 'send-keys', '-t', session_name, 'Down', 'C-m'],
            check=True,
            capture_output=True
        )

        # Give Claude a moment to start after accepting
        time.sleep(0.5)

    def spawn_interactive(self, skip_permissions: bool = False) -> int:
        """Spawn agent in interactive mode using tmux.

        Args:
            skip_permissions: If True, skip Claude's permission prompts (USE WITH CAUTION)

        Returns:
            Process ID of the Claude process

        Raises:
            RuntimeError: If spawn fails or tmux is not available
        """
        # Check if tmux is available
        if not shutil.which('tmux'):
            raise RuntimeError(
                "tmux not found. Please install tmux to use interactive mode:\n"
                "  macOS: brew install tmux\n"
                "  Linux: sudo apt-get install tmux"
            )

        try:
            session_name = f"agent-{self.agent_id}"

            # Kill existing session if it exists
            subprocess.run(
                ['tmux', 'kill-session', '-t', session_name],
                capture_output=True,
                check=False
            )

            # Create new tmux session and run Claude in it
            subprocess.run(
                ['tmux', 'new-session', '-d', '-s', session_name, '-c', self.working_dir],
                check=True,
                capture_output=True
            )

            # Start Claude in the tmux session
            if skip_permissions:
                self._start_claude_with_skip_permissions(session_name)
            else:
                # Send command to start claude normally
                subprocess.run(
                    ['tmux', 'send-keys', '-t', session_name, 'claude', 'C-m'],
                    check=True,
                    capture_output=True
                )
                # Give Claude a moment to start
                time.sleep(0.5)

            # Get the PID of the Claude process
            result = subprocess.run(
                ['tmux', 'list-panes', '-t', session_name, '-F', '#{pane_pid}'],
                capture_output=True,
                text=True,
                check=True
            )

            pane_pid = int(result.stdout.strip())

            # Get the actual Claude process PID (child of the shell)
            result = subprocess.run(
                ['pgrep', '-P', str(pane_pid), 'claude'],
                capture_output=True,
                text=True,
                check=False
            )

            if result.stdout.strip():
                claude_pid = int(result.stdout.strip().split('\n')[0])
            else:
                # Fallback to pane PID if we can't find claude process
                claude_pid = pane_pid

            # Store session name for later attachment
            self._tmux_session = session_name

            return claude_pid

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to spawn agent in tmux: {e}")
        except FileNotFoundError:
            raise RuntimeError("Claude Code CLI not found. Please ensure 'claude' is in your PATH.")
        except Exception as e:
            raise RuntimeError(f"Failed to spawn agent: {e}")

    def attach_interactive(self):
        """Attach to the agent's tmux session.

        This allows user input/output directly with the agent.
        """
        session_name = f"agent-{self.agent_id}"

        # Check if tmux session exists
        result = subprocess.run(
            ['tmux', 'has-session', '-t', session_name],
            capture_output=True,
            check=False
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"No tmux session found for agent {self.agent_id}. "
                "The agent may have exited or was not started in interactive mode."
            )

        print(f"Attaching to agent {self.agent_id}...")
        print("Press Ctrl+B then D to detach from the session.")
        print("-" * 60)

        # Attach to tmux session
        try:
            subprocess.run(
                ['tmux', 'attach-session', '-t', session_name],
                check=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to attach to tmux session: {e}")
        except KeyboardInterrupt:
            # User pressed Ctrl+C, just exit gracefully
            print("\n" + "-" * 60)
            print("Detached from agent.")
