"""Database layer for agent state management."""
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


class AgentStore:

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = Path.home() / ".agent-manager"
            base_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(base_dir / "agents.db")

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self):
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                repo_url TEXT NOT NULL,
                working_dir TEXT NOT NULL,
                pid INTEGER,
                status TEXT NOT NULL,
                container_mode INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        try:
            cursor.execute("SELECT container_mode FROM agents LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE agents ADD COLUMN container_mode INTEGER DEFAULT 0")
            self.conn.commit()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                output_type TEXT NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_outputs_agent_id
            ON agent_outputs(agent_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_outputs_timestamp
            ON agent_outputs(timestamp)
        """)

        self.conn.commit()

    def create_agent(self, agent_id: str, repo_url: str, working_dir: str,
                     pid: Optional[int] = None, status: str = "spawning",
                     container_mode: bool = False) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO agents (id, repo_url, working_dir, pid, status, container_mode, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (agent_id, repo_url, working_dir, pid, status, 1 if container_mode else 0, now, now))

        self.conn.commit()
        return self.get_agent(agent_id)

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_agents(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()

        if status:
            cursor.execute("SELECT * FROM agents WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            cursor.execute("SELECT * FROM agents ORDER BY created_at DESC")

        return [dict(row) for row in cursor.fetchall()]

    def update_agent(self, agent_id: str, **kwargs) -> bool:
        if not kwargs:
            return False

        kwargs['updated_at'] = datetime.utcnow().isoformat()

        fields = ', '.join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [agent_id]

        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE agents SET {fields} WHERE id = ?", values)
        self.conn.commit()

        return cursor.rowcount > 0

    def delete_agent(self, agent_id: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def add_output(self, agent_id: str, output_type: str, content: str):
        cursor = self.conn.cursor()
        timestamp = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO agent_outputs (agent_id, timestamp, output_type, content)
            VALUES (?, ?, ?, ?)
        """, (agent_id, timestamp, output_type, content))

        self.conn.commit()

    def get_outputs(self, agent_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()

        query = """
            SELECT * FROM agent_outputs
            WHERE agent_id = ?
            ORDER BY timestamp ASC
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, (agent_id,))
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        self.conn.close()
