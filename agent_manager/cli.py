"""CLI interface for agent management."""
import click
import sys
from tabulate import tabulate
from typing import Optional

from .manager import AgentManager
from . import utils


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Agent Manager - Manage Claude Code agents in isolated git clones.

    Each agent runs in its own fresh repository clone with full isolation.
    """
    pass


@cli.command()
@click.argument('repo_url')
def spawn(repo_url: str):
    if not utils.check_claude_cli():
        click.echo(click.style("Error: Claude Code CLI not found in PATH.", fg='red'))
        click.echo("Please install Claude Code first: https://github.com/anthropics/claude-code")
        sys.exit(1)

    if not utils.check_docker_available():
        click.echo(click.style("Error: Docker not found in PATH.", fg='red'))
        click.echo("Please install Docker first:")
        click.echo("  macOS: https://docs.docker.com/desktop/install/mac-install/")
        click.echo("  Linux: https://docs.docker.com/engine/install/")
        sys.exit(1)

    if not utils.check_docker_running():
        click.echo(click.style("Error: Docker daemon is not running.", fg='red'))
        click.echo("Please start Docker and try again.")
        sys.exit(1)

    manager = AgentManager()

    try:
        click.echo(f"Spawning agent for repository: {repo_url}")
        click.echo(click.style("Using isolated Docker container with network access", fg='yellow'))

        agent_id = manager.spawn_agent(
            repo_url=repo_url,
            skip_permissions=True,
            use_container=True
        )

        click.echo(click.style(f"\nAgent spawned successfully!", fg='green'))
        click.echo(f"Agent ID: {agent_id}")

        agent = manager.get_agent(agent_id)
        click.echo(f"Working directory: {agent['working_dir']}")
        click.echo(f"\nUse 'am attach {agent_id}' to connect to the agent.")

    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@cli.command()
@click.option('--status', '-s', type=click.Choice(['spawning', 'running', 'stopped', 'error']),
              help='Filter by status')
def list(status: Optional[str]):
    manager = AgentManager()

    try:
        agents = manager.list_agents(status=status)

        if not agents:
            if status:
                click.echo(f"No agents found with status: {status}")
            else:
                click.echo("No agents found. Use 'am spawn' to create one.")
            return

        headers = ['ID', 'Status', 'Repository', 'PID', 'Created']
        rows = []

        for agent in agents:
            repo = agent['repo_url']
            if len(repo) > 50:
                repo = '...' + repo[-47:]

            created = agent['created_at'].split('T')[0]

            status_display = agent['status']
            if agent['status'] == 'running':
                status_display = click.style(status_display, fg='green')
            elif agent['status'] == 'error':
                status_display = click.style(status_display, fg='red')
            elif agent['status'] == 'stopped':
                status_display = click.style(status_display, fg='yellow')

            rows.append([
                agent['id'],
                status_display,
                repo,
                agent['pid'] or '-',
                created
            ])

        click.echo(tabulate(rows, headers=headers, tablefmt='simple'))
        click.echo(f"\nTotal: {len(agents)} agent(s)")

    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@cli.command()
@click.argument('agent_id', required=False)
@click.option('--all', '-a', 'attach_all', is_flag=True,
              help='Attach to all running agents in split view')
def attach(agent_id: Optional[str], attach_all: bool):
    manager = AgentManager()

    try:
        if attach_all:
            manager.attach_all_agents()
        elif agent_id:
            click.echo(f"Attaching to agent {agent_id}...")
            manager.attach_agent(agent_id)
        else:
            click.echo(click.style("Error: Must provide AGENT_ID or use --all flag", fg='red'))
            sys.exit(1)

    except ValueError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)
    except RuntimeError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@cli.command()
@click.argument('agent_id')
def info(agent_id: str):
    manager = AgentManager()

    try:
        agent = manager.get_agent(agent_id)

        if not agent:
            click.echo(click.style(f"Agent not found: {agent_id}", fg='red'))
            sys.exit(1)

        click.echo(f"Agent ID: {agent['id']}")
        click.echo(f"Status: {agent['status']}")
        click.echo(f"Repository: {agent['repo_url']}")
        click.echo(f"Working Directory: {agent['working_dir']}")
        click.echo(f"Process ID: {agent['pid'] or 'N/A'}")
        click.echo(f"Created: {agent['created_at']}")
        click.echo(f"Updated: {agent['updated_at']}")

    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@cli.command()
@click.argument('agent_id')
@click.option('--keep-workdir', '-k', is_flag=True,
              help='Keep the working directory (only stop the process)')
def stop(agent_id: str, keep_workdir: bool):
    manager = AgentManager()

    try:
        manager.stop_agent(agent_id, remove_workdir=not keep_workdir)

        if keep_workdir:
            click.echo(click.style(f"Agent {agent_id} stopped (working directory preserved).", fg='green'))
        else:
            click.echo(click.style(f"Agent {agent_id} stopped and removed.", fg='green'))

    except ValueError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@cli.command()
@click.argument('agent_id')
@click.confirmation_option(prompt='Are you sure you want to delete this agent?')
def delete(agent_id: str):
    manager = AgentManager()

    try:
        manager.delete_agent(agent_id)
        click.echo(click.style(f"Agent {agent_id} deleted successfully.", fg='green'))

    except ValueError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@cli.command()
@click.option('--status', '-s', type=click.Choice(['spawning', 'running', 'stopped', 'error']),
              default='stopped', help='Status filter (default: stopped)')
@click.option('--all', '-a', 'clean_all', is_flag=True,
              help='Clean all agents regardless of status')
@click.confirmation_option(prompt='Are you sure you want to clean agents?')
def clean(status: Optional[str], clean_all: bool):
    manager = AgentManager()

    try:
        if clean_all:
            count = manager.clean_agents(status=None)
        else:
            count = manager.clean_agents(status=status)

        if count > 0:
            click.echo(click.style(f"Cleaned {count} agent(s).", fg='green'))
        else:
            filter_msg = "any" if clean_all else status
            click.echo(f"No {filter_msg} agents to clean.")

    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


@cli.command()
@click.option('--containers', is_flag=True,
              help='Clean up orphaned agent containers')
@click.option('--images', is_flag=True,
              help='Remove agent Docker images')
@click.option('--all', '-a', 'clean_all', is_flag=True,
              help='Clean both containers and images')
@click.confirmation_option(prompt='Are you sure you want to clean Docker resources?')
def docker_clean(containers: bool, images: bool, clean_all: bool):
    from . import docker_utils

    if not utils.check_docker_available():
        click.echo(click.style("Error: Docker not found.", fg='red'))
        sys.exit(1)

    if not utils.check_docker_running():
        click.echo(click.style("Error: Docker daemon is not running.", fg='red'))
        sys.exit(1)

    try:
        cleaned_containers = 0
        cleaned_images = 0

        if containers or clean_all:
            click.echo("Cleaning up agent containers...")
            agent_containers = docker_utils.list_containers(
                all_containers=True,
                filter_name='agent-'
            )
            for container in agent_containers:
                if docker_utils.remove_container(container, force=True):
                    cleaned_containers += 1
                    click.echo(f"  Removed container: {container}")

        if images or clean_all:
            click.echo("Cleaning up agent images...")
            if docker_utils.remove_image('claude-agent:latest', force=True):
                cleaned_images += 1
                click.echo("  Removed image: claude-agent:latest")

            docker_utils.prune_images()

        click.echo()
        if cleaned_containers > 0:
            click.echo(click.style(f"Cleaned {cleaned_containers} container(s).", fg='green'))
        if cleaned_images > 0:
            click.echo(click.style(f"Cleaned {cleaned_images} image(s).", fg='green'))

        if cleaned_containers == 0 and cleaned_images == 0:
            click.echo("No Docker resources to clean.")

    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)


if __name__ == '__main__':
    cli()
