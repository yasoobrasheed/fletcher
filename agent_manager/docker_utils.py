"""Docker container utilities for agent isolation."""
import subprocess
import shutil
from typing import Optional, Dict, List
from pathlib import Path


def check_docker_available() -> bool:
    return shutil.which('docker') is not None


def check_docker_running() -> bool:
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
    try:
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
    try:
        cmd = [
            'docker', 'run',
            '-d',
            '--name', container_name,
            '--network', network_mode,
            '-v', f'{working_dir}:/workspace',
            '-w', '/workspace',
            '--init',
        ]

        if auto_remove:
            cmd.append('--rm')

        cmd.extend([
            '--memory', '2g',
            '--cpus', '2',
            '--pids-limit', '100',
        ])

        if additional_args:
            cmd.extend(additional_args)

        cmd.extend([
            image_name,
            'sleep', 'infinity'
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
    try:
        subprocess.run(
            ['docker', 'exec', '-it', container_id, '/bin/bash'],
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to attach to container: {e}")


def remove_image(image_name: str, force: bool = False) -> bool:
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
        return [c for c in containers if c]
    except subprocess.CalledProcessError:
        return []
