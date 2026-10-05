"""
Read-Only Database Connection Manager.
Opens SQLite in strictly read-only mode using URI syntax (mode=ro).
Physically prevents any modifications at the database engine level.
"""

from pathlib import Path
import sqlite3
from typing import Optional


class ReadOnlyDatabaseManager:
    """Manages secure, read-only connections to SQLite database."""

    def __init__(self, db_path: Path, timeout_seconds: float = 10.0):
        self.db_path = db_path
        self.timeout = timeout_seconds
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database does not exist at {self.db_path}")

    def get_connection(self) -> sqlite3.Connection:
        """
        Open a strictly read-only SQLite connection.
        Using URI mode=ro ensures the database file cannot be written to.
        """
        # Convert path to posix URI for SQLite
        resolved = self.db_path.resolve().as_posix()
        uri = f"file:{resolved}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        return conn
