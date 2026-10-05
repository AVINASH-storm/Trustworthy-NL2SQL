"""
Safe Query Executor.
Executes validated SQL queries against the read-only SQLite database.
Returns Pandas DataFrame, row count, execution latency, and error tracking.
"""

from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from src.execution.database import ReadOnlyDatabaseManager


class SafeQueryExecutor:
    """Executes queries safely and returns results as structured DataFrames."""

    def __init__(self, db_path: Path, timeout_seconds: float = 10.0):
        self.db_manager = ReadOnlyDatabaseManager(db_path, timeout_seconds)

    def execute(self, sql: str) -> Dict[str, Any]:
        """
        Execute read-only SQL query and return execution metrics and DataFrame.
        """
        t0 = time.time()
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description] if cursor.description else []
            conn.close()

            latency_ms = round((time.time() - t0) * 1000, 2)
            df = pd.DataFrame([dict(r) for r in rows], columns=col_names)

            return {
                "success": True,
                "error": None,
                "row_count": len(df),
                "columns": col_names,
                "data": df,
                "latency_ms": latency_ms
            }
        except sqlite3.OperationalError as e:
            latency_ms = round((time.time() - t0) * 1000, 2)
            return {
                "success": False,
                "error": f"Database Execution Error: {str(e)}",
                "row_count": 0,
                "columns": [],
                "data": pd.DataFrame(),
                "latency_ms": latency_ms
            }
        except Exception as e:
            latency_ms = round((time.time() - t0) * 1000, 2)
            return {
                "success": False,
                "error": f"Unexpected Execution Error: {str(e)}",
                "row_count": 0,
                "columns": [],
                "data": pd.DataFrame(),
                "latency_ms": latency_ms
            }


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent.parent
    db_file = base / "data" / "database" / "olist.db"
    executor = SafeQueryExecutor(db_file)

    res = executor.execute("SELECT customer_city, count(*) as count FROM customers GROUP BY customer_city ORDER BY count DESC LIMIT 5;")
    print("Success:", res["success"])
    print("Latency:", res["latency_ms"], "ms")
    print(res["data"])
