"""Utility functions for agent management."""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional
import git


def check_claude_cli() -> bool:
    return shutil.which("claude") is not None


def get_claude_cli_path() -> Optional[str]:
    return shutil.which("claude")


def clone_repository(repo_url: str, target_dir: str, progress_callback=None) -> bool:
    try:
        target_path = Path(target_dir)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            git.Repo.clone_from(
                repo_url,
                target_dir,
                progress=progress_callback
            )
        else:
            git.Repo.clone_from(repo_url, target_dir)

        return True
    except git.exc.GitCommandError as e:
        raise e


def get_agent_base_dir(custom_path: Optional[str] = None) -> Path:
    if custom_path:
        base_dir = Path(custom_path).expanduser().resolve()
    else:
        env_path = os.environ.get('AGENT_MANAGER_BASE_DIR')
        if env_path:
            base_dir = Path(env_path).expanduser().resolve()
        else:
            base_dir = Path.cwd() / ".agents"

    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_agent_working_dir(agent_id: str) -> Path:
    return get_agent_base_dir() / agent_id


def remove_agent_directory(agent_id: str) -> bool:
    working_dir = get_agent_working_dir(agent_id)
    if working_dir.exists():
        shutil.rmtree(working_dir)
        return True
    return False


def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def terminate_process(pid: int, timeout: int = 5) -> bool:
    try:
        import signal
        os.kill(pid, signal.SIGTERM)
        return True
    except (OSError, TypeError):
        return False


def create_and_checkout_branch(repo_path: str, branch_name: str) -> bool:
    try:
        repo = git.Repo(repo_path)
        repo.git.checkout('-b', branch_name)
        return True
    except git.exc.GitCommandError as e:
        raise e


def validate_repo_url(repo_url: str) -> bool:
    valid_prefixes = ('http://', 'https://', 'git@', 'git://')
    return any(repo_url.startswith(prefix) for prefix in valid_prefixes)


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
