"""Container-based process management for Claude Code CLI agents."""
import time
from typing import Optional
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
        if not docker_utils.image_exists():
            print("Building agent Docker image (this may take a few minutes)...")
            if not docker_utils.build_agent_image():
                raise RuntimeError("Failed to build agent Docker image")

        try:
            if docker_utils.container_exists(self.container_name):
                docker_utils.remove_container(self.container_name, force=True)

            print(f"Creating isolated container for agent {self.agent_id}...")
            self.container_id = docker_utils.create_container(
                container_name=self.container_name,
                working_dir=self.working_dir,
                network_mode="bridge",
                auto_remove=True
            )
            print(f"Container created: {self.container_id[:12]}")

            self._start_claude_with_skip_permissions()

            return self.container_id

        except Exception as e:
            if self.container_id:
                docker_utils.remove_container(self.container_id, force=True)
            raise RuntimeError(f"Failed to spawn agent in container: {e}")

    def _start_claude_with_skip_permissions(self):
        try:
            docker_utils.exec_in_container(
                self.container_id,
                ['bash', '-c', 'echo "2" | claude --dangerously-skip-permissions'],
                detach=True
            )
            time.sleep(1.5)
        except Exception as e:
            raise RuntimeError(f"Failed to start Claude with skip permissions: {e}")

    def attach_interactive(self):
        if not self.container_id and self.container_name:
            if docker_utils.container_exists(self.container_name):
                print(f"Attaching to container {self.container_name}...")
            else:
                raise RuntimeError(
                    f"No container found for agent {self.agent_id}. "
                    "The agent may have exited."
                )
        elif not self.container_id:
            raise RuntimeError("No container ID available")

        print(f"Attaching to agent {self.agent_id} in container...")
        print("Type 'exit' or press Ctrl+D to detach from the container.")
        print("-" * 60)

        try:
            docker_utils.attach_to_container(self.container_name)
        except RuntimeError as e:
            raise RuntimeError(f"Failed to attach to container: {e}")
        except KeyboardInterrupt:
            print("\n" + "-" * 60)
            print("Detached from agent.")

    def stop(self):
        if self.container_id or docker_utils.container_exists(self.container_name):
            container_ref = self.container_id or self.container_name
            docker_utils.stop_container(container_ref)

    def remove(self, force: bool = True):
        if self.container_id or docker_utils.container_exists(self.container_name):
            container_ref = self.container_id or self.container_name
            docker_utils.remove_container(container_ref, force=force)

    def is_running(self) -> bool:
        if not (self.container_id or docker_utils.container_exists(self.container_name)):
            return False

        container_ref = self.container_id or self.container_name
        info = docker_utils.get_container_info(container_ref)

        if not info:
            return False

        return info.get('State', {}).get('Running', False)
