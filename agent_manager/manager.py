"""Agent lifecycle management."""
import shutil
from typing import Optional, Dict
from pathlib import Path

from .store import AgentStore
from .process import AgentProcess
from .container_process import ContainerAgentProcess
from . import utils
from . import docker_utils


class AgentManager:

    def __init__(self, store: Optional[AgentStore] = None):
        self.store = store or AgentStore()
        self.active_processes: Dict[str, AgentProcess] = {}

    def spawn_agent(
        self,
        repo_url: str,
    ) -> str:
        agent_id = utils.generate_agent_id()

        working_dir = utils.get_agent_working_dir(agent_id)
        working_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.store.create_agent(
                agent_id=agent_id,
                repo_url=repo_url,
                working_dir=str(working_dir),
                status="spawning",
                container_mode=True
            )

            print(f"Cloning repository to {working_dir}...")
            utils.clone_repository(repo_url, str(working_dir))

            branch_name = f"agent-dev/{agent_id}"
            print(f"Creating branch: {branch_name}")
            utils.create_and_checkout_branch(str(working_dir), branch_name)

            process = ContainerAgentProcess(agent_id, str(working_dir), self.store)
            container_id = process.spawn_interactive()
            self.store.update_agent(agent_id, pid=container_id, status="running")

            self.active_processes[agent_id] = process

            return agent_id

        except Exception as e:
            self.store.update_agent(agent_id, status="error")
            if working_dir.exists():
                shutil.rmtree(working_dir)
            raise RuntimeError(f"Failed to spawn agent: {e}")

    def attach_agent(self, agent_id: str):
        import subprocess

        agent = self.store.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        is_container = agent.get('container_mode', 0) == 1

        if is_container:
            container_name = f"agent-{agent_id}"

            if not docker_utils.container_exists(container_name):
                if agent['status'] == 'running':
                    self.store.update_agent(agent_id, status='stopped')
                raise RuntimeError(
                    f"No container found for agent {agent_id}. "
                    "The agent may have exited."
                )

            process = ContainerAgentProcess(agent_id, agent['working_dir'], self.store)
            process.container_name = container_name
            process.attach_interactive()
        else:
            session_name = f"agent-{agent_id}"
            result = subprocess.run(
                ['tmux', 'has-session', '-t', session_name],
                capture_output=True,
                check=False
            )

            if result.returncode != 0:
                if agent['status'] == 'running':
                    self.store.update_agent(agent_id, status='stopped')
                raise RuntimeError(
                    f"No tmux session found for agent {agent_id}. "
                    "The agent may have exited or was not started in interactive mode."
                )

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
        agents = self.store.list_agents(status=status)

        for agent in agents:
            if agent['status'] == 'running' and agent['pid']:
                if not utils.is_process_running(agent['pid']):
                    self.store.update_agent(agent['id'], status='stopped')
                    agent['status'] = 'stopped'

        return agents

    def get_agent(self, agent_id: str) -> Optional[Dict]:
        agent = self.store.get_agent(agent_id)

        if agent and agent['status'] == 'running' and agent['pid']:
            if not utils.is_process_running(agent['pid']):
                self.store.update_agent(agent['id'], status='stopped')
                agent['status'] = 'stopped'

        return agent

    def stop_agent(self, agent_id: str, remove_workdir: bool = True) -> bool:
        import subprocess

        agent = self.store.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        is_container = agent.get('container_mode', 0) == 1

        if is_container:
            container_name = f"agent-{agent_id}"
            if docker_utils.container_exists(container_name):
                print(f"Stopping container {container_name}...")
                docker_utils.stop_container(container_name)
                docker_utils.remove_container(container_name, force=True)
        else:
            session_name = f"agent-{agent_id}"
            subprocess.run(
                ['tmux', 'kill-session', '-t', session_name],
                capture_output=True,
                check=False
            )

            if agent['pid'] and utils.is_process_running(agent['pid']):
                utils.terminate_process(agent['pid'])

        self.active_processes.pop(agent_id, None)

        if remove_workdir:
            working_dir = Path(agent['working_dir'])
            if working_dir.exists():
                shutil.rmtree(working_dir)

            self.store.delete_agent(agent_id)
        else:
            self.store.update_agent(agent_id, status='stopped')

        return True

    def delete_agent(self, agent_id: str) -> bool:
        agent = self.store.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        is_container = agent.get('container_mode', 0) == 1

        if is_container:
            container_name = f"agent-{agent_id}"
            if docker_utils.container_exists(container_name):
                docker_utils.stop_container(container_name)
                docker_utils.remove_container(container_name, force=True)

        working_dir = Path(agent['working_dir'])
        if working_dir.exists():
            shutil.rmtree(working_dir)

        return self.store.delete_agent(agent_id)

    def clean_agents(self, status: Optional[str] = 'stopped') -> int:
        agents = self.store.list_agents(status=status)
        cleaned = 0

        for agent in agents:
            agent_id = agent['id']
            is_container = agent.get('container_mode', 0) == 1

            try:
                if is_container:
                    container_name = f"agent-{agent_id}"
                    if docker_utils.container_exists(container_name):
                        docker_utils.stop_container(container_name)
                        docker_utils.remove_container(container_name, force=True)

                working_dir = Path(agent['working_dir'])
                if working_dir.exists():
                    shutil.rmtree(working_dir)

                self.store.delete_agent(agent_id)
                cleaned += 1
            except Exception:
                pass

        return cleaned

    def attach_all_agents(self) -> bool:
        import shutil
        import subprocess

        if not shutil.which('tmux'):
            raise RuntimeError("tmux not found. Please install tmux.")

        agents = self.list_agents(status='running')
        if not agents:
            raise RuntimeError("No running agents found.")

        try:
            dashboard_session = "agents-dashboard"

            subprocess.run(
                ['tmux', 'kill-session', '-t', dashboard_session],
                capture_output=True,
                check=False
            )

            first_agent = agents[0]
            subprocess.run(
                ['tmux', 'new-session', '-d', '-s', dashboard_session, '-t', f"agent-{first_agent['id']}"],
                check=True,
                capture_output=True
            )

            for i, agent in enumerate(agents[1:], 1):
                agent_session = f"agent-{agent['id']}"

                result = subprocess.run(
                    ['tmux', 'has-session', '-t', agent_session],
                    capture_output=True,
                    check=False
                )

                if result.returncode == 0:
                    split_flag = '-h' if i % 2 == 0 else '-v'

                    subprocess.run(
                        ['tmux', 'split-window', split_flag, '-t', dashboard_session, '-d'],
                        check=True,
                        capture_output=True
                    )

                    subprocess.run(
                        ['tmux', 'send-keys', '-t', f"{dashboard_session}:{i}", f"tmux attach -t {agent_session}", 'Enter'],
                        check=True,
                        capture_output=True
                    )

            subprocess.run(
                ['tmux', 'select-layout', '-t', dashboard_session, 'tiled'],
                check=True,
                capture_output=True
            )

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
