"""Agent lifecycle management."""
import uuid
import shutil
from typing import Optional, Dict
from pathlib import Path

from .store import AgentStore
from .process import AgentProcess
from .container_process import ContainerAgentProcess
from . import utils
from . import docker_utils


class AgentManager:
    """Manages Claude Code agent spawning and attachment."""

    def __init__(self, store: Optional[AgentStore] = None):
        """Initialize the agent manager.

        Args:
            store: Database store (creates default if not provided)
        """
        self.store = store or AgentStore()
        self.active_processes: Dict[str, AgentProcess] = {}

    def spawn_agent(
        self,
        repo_url: str,
        skip_permissions: bool = False,
        use_container: bool = False
    ) -> str:
        """Spawn a new agent with a fresh repository clone in interactive mode.

        Args:
            repo_url: Git repository URL to clone
            skip_permissions: If True, skip Claude's permission prompts (USE WITH CAUTION)
            use_container: If True, spawn agent in isolated Docker container

        Returns:
            Agent ID

        Raises:
            RuntimeError: If Claude CLI not available or spawn fails
            ValueError: If repo_url is invalid
        """
        # Validate prerequisites
        if not utils.check_claude_cli():
            raise RuntimeError(
                "Claude Code CLI not found in PATH. "
                "Please install Claude Code first: https://github.com/anthropics/claude-code"
            )

        if not utils.validate_repo_url(repo_url):
            raise ValueError(f"Invalid repository URL: {repo_url}")

        # Generate agent ID
        agent_id = str(uuid.uuid4())[:8]

        # Create working directory
        working_dir = utils.get_agent_working_dir(agent_id)
        working_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Create agent record
            self.store.create_agent(
                agent_id=agent_id,
                repo_url=repo_url,
                working_dir=str(working_dir),
                status="spawning",
                container_mode=use_container
            )

            # Clone repository
            print(f"Cloning repository to {working_dir}...")
            utils.clone_repository(repo_url, str(working_dir))

            # Create and checkout agent-specific branch
            branch_name = f"agent-dev/{agent_id}"
            print(f"Creating branch: {branch_name}")
            utils.create_and_checkout_branch(str(working_dir), branch_name)

            # Create process manager based on mode
            if use_container:
                process = ContainerAgentProcess(agent_id, str(working_dir), self.store)
                # For containers, we store the container ID instead of PID
                container_id = process.spawn_interactive(skip_permissions=skip_permissions)
                status = "running"
                # Update agent record with container ID as "pid" for now
                self.store.update_agent(agent_id, pid=container_id, status=status)
            else:
                process = AgentProcess(agent_id, str(working_dir), self.store)
                # Spawn in interactive mode
                pid = process.spawn_interactive(skip_permissions=skip_permissions)
                status = "running"
                # Update agent record with PID and status
                self.store.update_agent(agent_id, pid=pid, status=status)

            # Track active process
            self.active_processes[agent_id] = process

            return agent_id

        except Exception as e:
            # Cleanup on failure
            self.store.update_agent(agent_id, status="error")
            if working_dir.exists():
                shutil.rmtree(working_dir)
            raise RuntimeError(f"Failed to spawn agent: {e}")

    def attach_agent(self, agent_id: str):
        """Attach to an agent's interactive session (tmux or container).

        Args:
            agent_id: Agent identifier

        Raises:
            ValueError: If agent not found
            RuntimeError: If session/container not found
        """
        import subprocess

        agent = self.store.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        # Check if agent is in container mode
        is_container = agent.get('container_mode', 0) == 1

        if is_container:
            # Attach to container
            container_name = f"agent-{agent_id}"

            # Check if container exists and is running
            if not docker_utils.container_exists(container_name):
                if agent['status'] == 'running':
                    self.store.update_agent(agent_id, status='stopped')
                raise RuntimeError(
                    f"No container found for agent {agent_id}. "
                    "The agent may have exited."
                )

            # Use ContainerAgentProcess to attach
            process = ContainerAgentProcess(agent_id, agent['working_dir'], self.store)
            process.container_name = container_name
            process.attach_interactive()
        else:
            # Attach to tmux session
            session_name = f"agent-{agent_id}"
            result = subprocess.run(
                ['tmux', 'has-session', '-t', session_name],
                capture_output=True,
                check=False
            )

            if result.returncode != 0:
                # Update status if process is not running
                if agent['status'] == 'running':
                    self.store.update_agent(agent_id, status='stopped')
                raise RuntimeError(
                    f"No tmux session found for agent {agent_id}. "
                    "The agent may have exited or was not started in interactive mode."
                )

            # Attach directly via tmux (works across sessions)
            print(f"Attaching to agent {agent_id}...")
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

    def list_agents(self, status: Optional[str] = None) -> list[Dict]:
        """List all agents with their information.

        Args:
            status: Optional status filter (e.g., 'running', 'stopped', 'error')

        Returns:
            List of agent records with id, repo_url, working_dir, pid, status,
            created_at, and updated_at
        """
        agents = self.store.list_agents(status=status)

        # Update status for agents that may have terminated
        for agent in agents:
            if agent['status'] == 'running' and agent['pid']:
                if not utils.is_process_running(agent['pid']):
                    self.store.update_agent(agent['id'], status='stopped')
                    agent['status'] = 'stopped'

        return agents

    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """Get detailed information about a specific agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent record with id, repo_url, working_dir, pid, status,
            created_at, and updated_at, or None if not found
        """
        agent = self.store.get_agent(agent_id)

        if agent and agent['status'] == 'running' and agent['pid']:
            # Update status if process has terminated
            if not utils.is_process_running(agent['pid']):
                self.store.update_agent(agent['id'], status='stopped')
                agent['status'] = 'stopped'

        return agent

    def stop_agent(self, agent_id: str, remove_workdir: bool = True) -> bool:
        """Stop a running agent and optionally remove its working directory.

        Args:
            agent_id: Agent identifier
            remove_workdir: If True, remove the working directory (default: True)

        Returns:
            True if stopped successfully

        Raises:
            ValueError: If agent not found
        """
        import subprocess

        agent = self.store.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        is_container = agent.get('container_mode', 0) == 1

        if is_container:
            # Stop and remove container
            container_name = f"agent-{agent_id}"
            if docker_utils.container_exists(container_name):
                print(f"Stopping container {container_name}...")
                docker_utils.stop_container(container_name)
                docker_utils.remove_container(container_name, force=True)
        else:
            # Kill the tmux session if it exists
            session_name = f"agent-{agent_id}"
            subprocess.run(
                ['tmux', 'kill-session', '-t', session_name],
                capture_output=True,
                check=False
            )

            # Try to terminate the process if it's still running
            if agent['pid'] and utils.is_process_running(agent['pid']):
                utils.terminate_process(agent['pid'])

        # Remove from active processes
        self.active_processes.pop(agent_id, None)

        # Remove working directory if requested
        if remove_workdir:
            working_dir = Path(agent['working_dir'])
            if working_dir.exists():
                shutil.rmtree(working_dir)

            # Remove from database
            self.store.delete_agent(agent_id)
        else:
            # Just update status to stopped
            self.store.update_agent(agent_id, status='stopped')

        return True

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent and its working directory.

        Args:
            agent_id: Agent identifier

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If agent not found
        """
        agent = self.store.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        is_container = agent.get('container_mode', 0) == 1

        # Stop and remove container if it exists
        if is_container:
            container_name = f"agent-{agent_id}"
            if docker_utils.container_exists(container_name):
                docker_utils.stop_container(container_name)
                docker_utils.remove_container(container_name, force=True)

        # Remove working directory if it exists
        working_dir = Path(agent['working_dir'])
        if working_dir.exists():
            shutil.rmtree(working_dir)

        # Remove from database
        return self.store.delete_agent(agent_id)

    def clean_agents(self, status: Optional[str] = 'stopped') -> int:
        """Remove agents and their working directories.

        Args:
            status: Status filter (default: 'stopped'). Use None to clean all agents.

        Returns:
            Number of agents cleaned
        """
        agents = self.store.list_agents(status=status)
        cleaned = 0

        for agent in agents:
            agent_id = agent['id']
            is_container = agent.get('container_mode', 0) == 1

            try:
                # Stop and remove container if it exists
                if is_container:
                    container_name = f"agent-{agent_id}"
                    if docker_utils.container_exists(container_name):
                        docker_utils.stop_container(container_name)
                        docker_utils.remove_container(container_name, force=True)

                # Remove working directory
                working_dir = Path(agent['working_dir'])
                if working_dir.exists():
                    shutil.rmtree(working_dir)

                # Remove from database
                self.store.delete_agent(agent_id)
                cleaned += 1
            except Exception:
                # Continue cleaning other agents even if one fails
                pass

        return cleaned

    def attach_all_agents(self) -> bool:
        """Attach to all running agents in a single tmux window with split panes.

        Creates a new tmux session with all agent sessions linked in split panes.

        Returns:
            True if successful

        Raises:
            RuntimeError: If tmux not available or no running agents
        """
        import shutil
        import subprocess

        if not shutil.which('tmux'):
            raise RuntimeError("tmux not found. Please install tmux.")

        # Get all running agents
        agents = self.list_agents(status='running')
        if not agents:
            raise RuntimeError("No running agents found.")

        try:
            # Create a new tmux session for the dashboard
            dashboard_session = "agents-dashboard"

            # Kill existing dashboard session if it exists
            subprocess.run(
                ['tmux', 'kill-session', '-t', dashboard_session],
                capture_output=True,
                check=False
            )

            # Link first agent session as the initial window
            first_agent = agents[0]
            subprocess.run(
                ['tmux', 'new-session', '-d', '-s', dashboard_session, '-t', f"agent-{first_agent['id']}"],
                check=True,
                capture_output=True
            )

            # Split the window and link remaining agent sessions
            for i, agent in enumerate(agents[1:], 1):
                agent_session = f"agent-{agent['id']}"

                # Check if agent session exists
                result = subprocess.run(
                    ['tmux', 'has-session', '-t', agent_session],
                    capture_output=True,
                    check=False
                )

                if result.returncode == 0:
                    # Split horizontally or vertically based on count
                    split_flag = '-h' if i % 2 == 0 else '-v'

                    # Create a new pane linked to the agent session
                    subprocess.run(
                        ['tmux', 'split-window', split_flag, '-t', dashboard_session, '-d'],
                        check=True,
                        capture_output=True
                    )

                    # Link the new pane to the agent session
                    # Note: This is tricky - we'll send the attach command instead
                    subprocess.run(
                        ['tmux', 'send-keys', '-t', f"{dashboard_session}:{i}", f"tmux attach -t {agent_session}", 'Enter'],
                        check=True,
                        capture_output=True
                    )

            # Tile all panes evenly
            subprocess.run(
                ['tmux', 'select-layout', '-t', dashboard_session, 'tiled'],
                check=True,
                capture_output=True
            )

            # Attach to the dashboard session
            print(f"Attaching to {len(agents)} agent(s) in split view...")
            print("Press Ctrl+B then D to detach from the dashboard.")
            print("Press Ctrl+B then arrow keys to navigate between panes.")
            print("Press Ctrl+B then Z to zoom/unzoom a pane.")
            print("-" * 60)

            subprocess.run(
                ['tmux', 'attach-session', '-t', dashboard_session],
                check=True
            )

            return True

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create agents dashboard: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to attach to agents: {e}")
