"""Utility functions for agent management."""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional
import git


def check_claude_cli() -> bool:
    """Check if Claude Code CLI is available in PATH.

    Returns:
        True if 'claude' command is available, False otherwise
    """
    return shutil.which("claude") is not None


def get_claude_cli_path() -> Optional[str]:
    """Get the path to Claude Code CLI executable.

    Returns:
        Path to claude CLI or None if not found
    """
    return shutil.which("claude")


def clone_repository(repo_url: str, target_dir: str, progress_callback=None) -> bool:
    """Clone a git repository to the target directory.

    Args:
        repo_url: Repository URL (https or git)
        target_dir: Destination directory path
        progress_callback: Optional callback for progress updates

    Returns:
        True if clone successful, False otherwise

    Raises:
        git.exc.GitCommandError: If clone fails
    """
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
    """Get the base directory for agent working directories.

    Args:
        custom_path: Optional custom path for agent directories

    Returns:
        Path to agent base directory (default: ./agents/)
    """
    if custom_path:
        base_dir = Path(custom_path).expanduser().resolve()
    else:
        # Check for environment variable override
        env_path = os.environ.get('AGENT_MANAGER_BASE_DIR')
        if env_path:
            base_dir = Path(env_path).expanduser().resolve()
        else:
            # Default to ./.agents in current directory (hidden)
            base_dir = Path.cwd() / ".agents"

    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_agent_working_dir(agent_id: str) -> Path:
    """Get the working directory path for an agent.

    Args:
        agent_id: Agent identifier

    Returns:
        Path to agent's working directory
    """
    return get_agent_base_dir() / agent_id


def remove_agent_directory(agent_id: str) -> bool:
    """Remove an agent's working directory.

    Args:
        agent_id: Agent identifier

    Returns:
        True if removed, False if directory doesn't exist
    """
    working_dir = get_agent_working_dir(agent_id)
    if working_dir.exists():
        shutil.rmtree(working_dir)
        return True
    return False


def is_process_running(pid: int) -> bool:
    """Check if a process is running.

    Args:
        pid: Process ID

    Returns:
        True if process exists, False otherwise
    """
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def terminate_process(pid: int, timeout: int = 5) -> bool:
    """Terminate a process gracefully.

    Args:
        pid: Process ID
        timeout: Seconds to wait for graceful termination

    Returns:
        True if terminated, False if process doesn't exist
    """
    try:
        import signal
        os.kill(pid, signal.SIGTERM)
        return True
    except (OSError, TypeError):
        return False


def create_and_checkout_branch(repo_path: str, branch_name: str) -> bool:
    """Create and checkout a new branch in a git repository.

    Args:
        repo_path: Path to the git repository
        branch_name: Name of the branch to create

    Returns:
        True if successful

    Raises:
        git.exc.GitCommandError: If branch creation fails
    """
    try:
        repo = git.Repo(repo_path)
        # Create and checkout new branch
        repo.git.checkout('-b', branch_name)
        return True
    except git.exc.GitCommandError as e:
        raise e


def validate_repo_url(repo_url: str) -> bool:
    """Validate a repository URL format.

    Args:
        repo_url: Repository URL

    Returns:
        True if URL appears valid
    """
    # Basic validation for git URLs
    valid_prefixes = ('http://', 'https://', 'git@', 'git://')
    return any(repo_url.startswith(prefix) for prefix in valid_prefixes)
