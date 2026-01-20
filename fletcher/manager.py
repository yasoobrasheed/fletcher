"""Agent lifecycle management."""
import shutil
from typing import Optional, Dict
from pathlib import Path

from .store import AgentStore
from .container_process import ContainerAgentProcess
from . import utils
from . import docker_utils


class AgentManager:

    def __init__(self, store: Optional[AgentStore] = None):
        self.store = store or AgentStore()
        self.active_processes: Dict[str, ContainerAgentProcess] = {}

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
                status="spawning"
            )

            print(f"Cloning repository to {working_dir}...")
            utils.clone_repository(repo_url, str(working_dir))

            branch_name = f"fletcher/{agent_id}"
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
        agent = self.store.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        process = ContainerAgentProcess(agent_id, agent['working_dir'], self.store)

        if not docker_utils.container_exists(f"agent-{agent_id}"):
            if agent['status'] == 'running':
                self.store.update_agent(agent_id, status='stopped')
            raise RuntimeError(
                f"No container found for agent {agent_id}. "
                "The agent may have exited."
            )

        if not process.is_running():
            if agent['status'] == 'running':
                self.store.update_agent(agent_id, status='stopped')
            raise RuntimeError(
                f"Container for agent {agent_id} is not running. "
                "The agent may have exited."
            )

        agent = self.store.get_agent(agent_id)
        process = ContainerAgentProcess(agent_id, agent['working_dir'], self.store)
        process.attach_interactive()

    def list_agents(self, status: Optional[str] = None) -> list[Dict]:
        agents = self.store.list_agents(status=status)

        for agent in agents:
            self._sync_agent_status(agent)

        return agents

    def get_agent(self, agent_id: str) -> Optional[Dict]:
        agent = self.store.get_agent(agent_id)

        if agent:
            self._sync_agent_status(agent)

        return agent

    def stop_agent(self, agent_id: str, remove_workdir: bool = True) -> bool:
        agent = self.store.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        container_name = f"agent-{agent_id}"
        if docker_utils.container_exists(container_name):
            print(f"Stopping container {container_name}...")
            docker_utils.stop_container(container_name)
            docker_utils.remove_container(container_name, force=True)

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

            try:
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

    def _sync_agent_status(self, agent: Dict) -> None:
        if agent['status'] == 'running':
            process = ContainerAgentProcess(agent['id'], agent['working_dir'], self.store)
            if not process.is_running():
                self.store.update_agent(agent['id'], status='stopped')
                agent['status'] = 'stopped'
