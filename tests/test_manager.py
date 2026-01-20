"""Tests for Fletcher agent manager."""
import pytest
import tempfile
import shutil
from pathlib import Path

from fletcher.manager import AgentManager
from fletcher.store import AgentStore


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    store = AgentStore(str(db_path))

    yield store

    # Cleanup
    store.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def manager(temp_db):
    """Create a manager instance with temporary database."""
    return AgentManager(store=temp_db)


def test_manager_initialization(manager):
    """Test that manager initializes correctly."""
    assert manager is not None
    assert manager.store is not None
    assert len(manager.active_processes) == 0


def test_list_agents_empty(manager):
    """Test listing agents when none exist."""
    agents = manager.list_agents()
    assert agents == []


def test_get_nonexistent_agent(manager):
    """Test getting an agent that doesn't exist."""
    agent = manager.get_agent("nonexistent")
    assert agent is None


# Note: Additional tests would require mocking git clone and Claude CLI
# or using integration tests with real repositories
