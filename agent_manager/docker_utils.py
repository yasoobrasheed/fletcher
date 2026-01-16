"""Docker container utilities for agent isolation."""
import subprocess
import shutil
from typing import Optional, Dict, List
from pathlib import Path


def check_docker_available() -> bool:
    """Check if Docker is installed and accessible.

    Returns:
        True if Docker is available, False otherwise
    """
    return shutil.which('docker') is not None


def check_docker_running() -> bool:
    """Check if Docker daemon is running.

    Returns:
        True if Docker daemon is running, False otherwise
    """
    try:
        result = subprocess.run(
            ['docker', 'info'],
            capture_output=True,
            check=False,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def build_agent_image(image_name: str = "claude-agent:latest") -> bool:
    """Build the Docker image for agents.

    Args:
        image_name: Name and tag for the Docker image

    Returns:
        True if build successful, False otherwise
    """
    try:
        # Get the project root directory (where Dockerfile is located)
        dockerfile_dir = Path(__file__).parent.parent

        result = subprocess.run(
            ['docker', 'build', '-t', image_name, str(dockerfile_dir)],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to build Docker image: {e.stderr}")
        return False


def image_exists(image_name: str = "claude-agent:latest") -> bool:
    """Check if the agent Docker image exists.

    Args:
        image_name: Name and tag of the Docker image

    Returns:
        True if image exists, False otherwise
    """
    try:
        result = subprocess.run(
            ['docker', 'image', 'inspect', image_name],
            capture_output=True,
            check=False
        )
        return result.returncode == 0
    except Exception:
        return False


def create_container(
    container_name: str,
    working_dir: str,
    image_name: str = "claude-agent:latest",
    network_mode: str = "none",
    auto_remove: bool = True,
    additional_args: Optional[List[str]] = None
) -> str:
    """Create a Docker container for an agent.

    Args:
        container_name: Unique name for the container
        working_dir: Host directory to mount as workspace
        image_name: Docker image to use
        network_mode: Docker network mode (none, bridge, host)
        auto_remove: Automatically remove container when it stops
        additional_args: Additional docker run arguments

    Returns:
        Container ID

    Raises:
        RuntimeError: If container creation fails
    """
    try:
        cmd = [
            'docker', 'run',
            '-d',  # Detached mode
            '--name', container_name,
            '--network', network_mode,
            '-v', f'{working_dir}:/workspace',  # Mount workspace
            '-w', '/workspace',  # Set working directory
            '--init',  # Use init process
        ]

        if auto_remove:
            cmd.append('--rm')

        # Add resource limits for safety
        cmd.extend([
            '--memory', '2g',  # 2GB memory limit
            '--cpus', '2',  # 2 CPU limit
            '--pids-limit', '100',  # Limit number of processes
        ])

        if additional_args:
            cmd.extend(additional_args)

        cmd.extend([
            image_name,
            'sleep', 'infinity'  # Keep container running
        ])

        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )

        container_id = result.stdout.strip()
        return container_id

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create container: {e.stderr}")


def exec_in_container(
    container_id: str,
    command: List[str],
    detach: bool = False,
    interactive: bool = False
) -> subprocess.CompletedProcess:
    """Execute a command in a running container.

    Args:
        container_id: Container ID or name
        command: Command to execute as list
        detach: Run command in background
        interactive: Attach stdin/stdout/stderr

    Returns:
        CompletedProcess result

    Raises:
        RuntimeError: If execution fails
    """
    try:
        cmd = ['docker', 'exec']

        if detach:
            cmd.append('-d')

        if interactive:
            cmd.extend(['-it'])

        cmd.append(container_id)
        cmd.extend(command)

        result = subprocess.run(
            cmd,
            check=True,
            capture_output=not interactive,
            text=True
        )

        return result

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to execute command in container: {e}")


def stop_container(container_id: str, timeout: int = 10) -> bool:
    """Stop a running container.

    Args:
        container_id: Container ID or name
        timeout: Seconds to wait before killing

    Returns:
        True if successful, False otherwise
    """
    try:
        subprocess.run(
            ['docker', 'stop', '-t', str(timeout), container_id],
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def remove_container(container_id: str, force: bool = False) -> bool:
    """Remove a container.

    Args:
        container_id: Container ID or name
        force: Force removal even if running

    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = ['docker', 'rm']
        if force:
            cmd.append('-f')
        cmd.append(container_id)

        subprocess.run(
            cmd,
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_container_info(container_id: str) -> Optional[Dict]:
    """Get information about a container.

    Args:
        container_id: Container ID or name

    Returns:
        Container info dict or None if not found
    """
    try:
        import json

        result = subprocess.run(
            ['docker', 'inspect', container_id],
            check=True,
            capture_output=True,
            text=True
        )

        info = json.loads(result.stdout)
        return info[0] if info else None

    except (subprocess.CalledProcessError, json.JSONDecodeError, IndexError):
        return None


def container_exists(container_name: str) -> bool:
    """Check if a container exists.

    Args:
        container_name: Container name

    Returns:
        True if container exists, False otherwise
    """
    try:
        result = subprocess.run(
            ['docker', 'ps', '-a', '--filter', f'name={container_name}', '--format', '{{.Names}}'],
            check=True,
            capture_output=True,
            text=True
        )
        return container_name in result.stdout.strip().split('\n')
    except subprocess.CalledProcessError:
        return False


def attach_to_container(container_id: str):
    """Attach to a running container's main process.

    Args:
        container_id: Container ID or name

    Raises:
        RuntimeError: If attach fails
    """
    try:
        subprocess.run(
            ['docker', 'exec', '-it', container_id, '/bin/bash'],
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to attach to container: {e}")


def remove_image(image_name: str, force: bool = False) -> bool:
    """Remove a Docker image.

    Args:
        image_name: Image name or ID
        force: Force removal even if containers are using it

    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = ['docker', 'rmi']
        if force:
            cmd.append('-f')
        cmd.append(image_name)

        subprocess.run(
            cmd,
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def prune_images(all_images: bool = False) -> bool:
    """Remove unused Docker images.

    Args:
        all_images: Remove all unused images, not just dangling ones

    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = ['docker', 'image', 'prune', '-f']
        if all_images:
            cmd.append('-a')

        subprocess.run(
            cmd,
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def list_containers(all_containers: bool = True, filter_name: Optional[str] = None) -> List[str]:
    """List Docker containers.

    Args:
        all_containers: Include stopped containers
        filter_name: Filter by name pattern (e.g., "agent-*")

    Returns:
        List of container names
    """
    try:
        cmd = ['docker', 'ps', '--format', '{{.Names}}']
        if all_containers:
            cmd.append('-a')
        if filter_name:
            cmd.extend(['--filter', f'name={filter_name}'])

        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        containers = result.stdout.strip().split('\n')
        return [c for c in containers if c]  # Filter empty strings
    except subprocess.CalledProcessError:
        return []
