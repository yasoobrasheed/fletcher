"""Container-based process management for Claude Code CLI agents."""
import os
import time
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from .store import AgentStore
from . import docker_utils
from . import utils


class ContainerAgentProcess:

    def __init__(self, agent_id: str, working_dir: str, store: AgentStore):
        self.agent_id = agent_id
        self.working_dir = working_dir
        self.store = store
        self.container_name = f"agent-{agent_id}"
        self.container_id: Optional[str] = None

    def spawn_interactive(self) -> str:
        if docker_utils.image_exists():
            docker_utils.remove_image('claude-agent:latest', force=True)

        print("Building agent Docker image (this may take a few minutes)...")
        if not docker_utils.build_agent_image():
            raise RuntimeError("Failed to build agent Docker image")

        try:
            if docker_utils.container_exists(self.container_name):
                docker_utils.remove_container(self.container_name, force=True)

            env_vars = self._load_env_vars()
            print(f"Creating isolated container for agent {self.agent_id}...")
            self.container_id = docker_utils.create_container(
                container_name=self.container_name,
                working_dir=self.working_dir,
                network_mode="bridge",
                auto_remove=True,
                env_vars=env_vars,
            )
            print(f"Container created: {self.container_id[:12]}")

            self._start_claude()
            return self.container_id
        except Exception as e:
            if self.container_id:
                docker_utils.remove_container(self.container_id, force=True)
            raise RuntimeError(f"Failed to spawn agent in container: {e}")

    def _start_claude(self):
        try:
            docker_utils.exec_in_container(
                self.container_id,
                ['bash', '-c', 'echo "2" | claude --dangerously-skip-permissions'],
                detach=True
            )
            time.sleep(1.5)
        except Exception as e:
            raise RuntimeError(f"Failed to start Claude: {e}")

    def attach_interactive(self):
        if not self.container_id:
            if docker_utils.container_exists(self.container_name):
                print(f"Attaching to container {self.container_name}...")
            else:
                raise RuntimeError(
                    f"No container found for agent {self.agent_id}. "
                    "The agent may have exited."
                )

        print(f"Attaching to agent {self.agent_id} in container...")
        print("Type 'exit' or press Ctrl+D to detach from the container.\n")

        try:
            docker_utils.attach_to_container(self.container_name)
        except RuntimeError as e:
            raise RuntimeError(f"Failed to attach to container: {e}")
        except KeyboardInterrupt:
            print("Detached from agent.")

    def stop(self):
        container_ref = self.container_id or self.container_name
        if container_ref:
            docker_utils.stop_container(container_ref)

    def remove(self, force: bool = True):
        container_ref = self.container_id or self.container_name
        if container_ref:
            docker_utils.remove_container(container_ref, force=force)

    def is_running(self) -> bool:
        container_ref = self.container_id or self.container_name
        if not container_ref:
            return False

        info = docker_utils.get_container_info(container_ref)
        return info.get('State', {}).get('Running', False) if info else False

    def _load_env_vars(self) -> dict:
        """Load environment variables from .env file and environment."""
        # Load .env file from the project root (two levels up from this file)
        project_root = Path(__file__).parent.parent
        env_file = project_root / '.env'

        if env_file.exists():
            try:
                load_dotenv(env_file)
            except:
                pass  # dotenv not installed, fall back to os.getenv

        env_vars = {}

        # Get ANTHROPIC_API_KEY from environment
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            env_vars['ANTHROPIC_API_KEY'] = api_key
        else:
            print("Warning: ANTHROPIC_API_KEY not found in environment or .env file")
            print(f"Please create a .env file at {env_file} with your API key")

        return env_vars
