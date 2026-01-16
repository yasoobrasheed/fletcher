"""Container-based process management for Claude Code CLI agents."""
import subprocess
import time
from typing import Optional
from .store import AgentStore
from . import docker_utils


class ContainerAgentProcess:
    """Manages a Claude Code CLI subprocess in an isolated Docker container."""

    def __init__(self, agent_id: str, working_dir: str, store: AgentStore):
        """Initialize the container agent process manager.

        Args:
            agent_id: Agent identifier
            working_dir: Working directory for the agent (host path)
            store: Database store for output persistence
        """
        self.agent_id = agent_id
        self.working_dir = working_dir
        self.store = store
        self.container_name = f"agent-{agent_id}"
        self.container_id: Optional[str] = None

    def spawn_interactive(self, skip_permissions: bool = False) -> str:
        """Spawn agent in interactive mode using Docker container.

        Args:
            skip_permissions: If True, skip Claude's permission prompts (USE WITH CAUTION)

        Returns:
            Container ID

        Raises:
            RuntimeError: If spawn fails or Docker is not available
        """
        # Check Docker availability
        if not docker_utils.check_docker_available():
            raise RuntimeError(
                "Docker not found. Please install Docker:\n"
                "  macOS: https://docs.docker.com/desktop/install/mac-install/\n"
                "  Linux: https://docs.docker.com/engine/install/"
            )

        if not docker_utils.check_docker_running():
            raise RuntimeError(
                "Docker daemon is not running. Please start Docker."
            )

        # Ensure image exists
        if not docker_utils.image_exists():
            print("Building agent Docker image (this may take a few minutes)...")
            if not docker_utils.build_agent_image():
                raise RuntimeError("Failed to build agent Docker image")

        try:
            # Remove existing container if it exists
            if docker_utils.container_exists(self.container_name):
                docker_utils.remove_container(self.container_name, force=True)

            # Create container with network access for Claude Code API
            print(f"Creating isolated container for agent {self.agent_id}...")
            self.container_id = docker_utils.create_container(
                container_name=self.container_name,
                working_dir=self.working_dir,
                network_mode="bridge",  # Network access required for Claude API
                auto_remove=True
            )

            print(f"Container created: {self.container_id[:12]}")

            # Start Claude inside the container
            if skip_permissions:
                self._start_claude_with_skip_permissions()
            else:
                self._start_claude_normal()

            return self.container_id

        except Exception as e:
            # Cleanup on failure
            if self.container_id:
                docker_utils.remove_container(self.container_id, force=True)
            raise RuntimeError(f"Failed to spawn agent in container: {e}")

    def _start_claude_normal(self):
        """Start Claude normally in the container."""
        try:
            # Execute Claude in detached mode
            docker_utils.exec_in_container(
                self.container_id,
                ['claude'],
                detach=True
            )
            time.sleep(0.5)
        except Exception as e:
            raise RuntimeError(f"Failed to start Claude in container: {e}")

    def _start_claude_with_skip_permissions(self):
        """Start Claude with skip permissions flag in the container.

        Note: This uses a shell script approach since we can't send interactive
        key presses to a container the same way we do with tmux.
        """
        try:
            # Create a script that auto-accepts the permission prompt
            script = """#!/bin/bash
# Start Claude with skip permissions and auto-accept
(echo "2" | claude --dangerously-skip-permissions) &
"""
            # Write script to container
            subprocess.run(
                ['docker', 'exec', self.container_id, 'bash', '-c',
                 f'echo {repr(script)} > /tmp/start_claude.sh && chmod +x /tmp/start_claude.sh'],
                check=True,
                capture_output=True
            )

            # Execute the script
            docker_utils.exec_in_container(
                self.container_id,
                ['/tmp/start_claude.sh'],
                detach=True
            )

            time.sleep(1.5)  # Give it time to start and accept

        except Exception as e:
            raise RuntimeError(f"Failed to start Claude with skip permissions: {e}")

    def attach_interactive(self):
        """Attach to the agent's container for interactive session.

        This opens a bash shell in the container where Claude is running.
        """
        if not self.container_id and self.container_name:
            # Try to find container by name
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
        """Stop the agent's container."""
        if self.container_id or docker_utils.container_exists(self.container_name):
            container_ref = self.container_id or self.container_name
            docker_utils.stop_container(container_ref)

    def remove(self, force: bool = True):
        """Remove the agent's container.

        Args:
            force: Force removal even if running
        """
        if self.container_id or docker_utils.container_exists(self.container_name):
            container_ref = self.container_id or self.container_name
            docker_utils.remove_container(container_ref, force=force)

    def is_running(self) -> bool:
        """Check if the container is running.

        Returns:
            True if container is running, False otherwise
        """
        if not (self.container_id or docker_utils.container_exists(self.container_name)):
            return False

        container_ref = self.container_id or self.container_name
        info = docker_utils.get_container_info(container_ref)

        if not info:
            return False

        return info.get('State', {}).get('Running', False)
