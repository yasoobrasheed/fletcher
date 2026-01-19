"""Process management for Claude Code CLI agents."""
import shutil
import subprocess
import time
from typing import Optional
from .store import AgentStore


class AgentProcess:

    def __init__(self, agent_id: str, working_dir: str, store: AgentStore):
        self.agent_id = agent_id
        self.working_dir = working_dir
        self.store = store
        self._tmux_session: Optional[str] = None

    def _start_claude_with_skip_permissions(self, session_name: str):
        subprocess.run(
            ['tmux', 'send-keys', '-t', session_name, 'claude --dangerously-skip-permissions'],
            check=True,
            capture_output=True
        )

        time.sleep(1.0)

        subprocess.run(
            ['tmux', 'send-keys', '-t', session_name, 'Down', 'C-m'],
            check=True,
            capture_output=True
        )

        time.sleep(0.5)

    def spawn_interactive(self, skip_permissions: bool = False) -> int:
        if not shutil.which('tmux'):
            raise RuntimeError(
                "tmux not found. Please install tmux to use interactive mode:\n"
                "  macOS: brew install tmux\n"
                "  Linux: sudo apt-get install tmux"
            )

        try:
            session_name = f"agent-{self.agent_id}"

            subprocess.run(
                ['tmux', 'kill-session', '-t', session_name],
                capture_output=True,
                check=False
            )

            subprocess.run(
                ['tmux', 'new-session', '-d', '-s', session_name, '-c', self.working_dir],
                check=True,
                capture_output=True
            )

            if skip_permissions:
                self._start_claude_with_skip_permissions(session_name)
            else:
                subprocess.run(
                    ['tmux', 'send-keys', '-t', session_name, 'claude', 'C-m'],
                    check=True,
                    capture_output=True
                )
                time.sleep(0.5)

            result = subprocess.run(
                ['tmux', 'list-panes', '-t', session_name, '-F', '#{pane_pid}'],
                capture_output=True,
                text=True,
                check=True
            )

            pane_pid = int(result.stdout.strip())

            result = subprocess.run(
                ['pgrep', '-P', str(pane_pid), 'claude'],
                capture_output=True,
                text=True,
                check=False
            )

            if result.stdout.strip():
                claude_pid = int(result.stdout.strip().split('\n')[0])
            else:
                claude_pid = pane_pid

            self._tmux_session = session_name

            return claude_pid

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to spawn agent in tmux: {e}")
        except FileNotFoundError:
            raise RuntimeError("Claude Code CLI not found. Please ensure 'claude' is in your PATH.")
        except Exception as e:
            raise RuntimeError(f"Failed to spawn agent: {e}")

    def attach_interactive(self):
        session_name = f"agent-{self.agent_id}"

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

        try:
            subprocess.run(
                ['tmux', 'attach-session', '-t', session_name],
                check=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to attach to tmux session: {e}")
        except KeyboardInterrupt:
            print("\n" + "-" * 60)
            print("Detached from agent.")
