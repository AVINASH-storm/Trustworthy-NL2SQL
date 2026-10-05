"""
Unit Tests for Read-Only Database Execution and Safety Limits.
"""

from pathlib import Path
import sqlite3
import unittest

from src.execution.database import ReadOnlyDatabaseManager
from src.execution.query_executor import SafeQueryExecutor

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "database" / "olist.db"


class TestDatabaseExecution(unittest.TestCase):
    """Test read-only execution safety and performance tracking."""

    @classmethod
    def setUpClass(cls):
        if not DB_PATH.exists():
            raise unittest.SkipTest("Database not found. Run pipeline first.")
        cls.db_manager = ReadOnlyDatabaseManager(DB_PATH)
        cls.executor = SafeQueryExecutor(DB_PATH)

    def test_readonly_connection_allows_select(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM customers;")
        count = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(count, 99441)

    def test_readonly_connection_physically_blocks_writes(self):
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        with self.assertRaises(sqlite3.OperationalError) as ctx:
            cursor.execute("CREATE TABLE malicious_table (id INT);")
        self.assertIn("readonly database", str(ctx.exception).lower())
        conn.close()

    def test_query_executor_returns_dataframe_and_latency(self):
        res = self.executor.execute("SELECT customer_state, COUNT(*) as cnt FROM customers GROUP BY customer_state ORDER BY cnt DESC LIMIT 5;")
        self.assertTrue(res["success"])
        self.assertEqual(res["row_count"], 5)
        self.assertGreater(res["latency_ms"], 0.0)
        self.assertIn("customer_state", res["columns"])
        self.assertIn("cnt", res["columns"])
        self.assertFalse(res["data"].empty)

    def test_query_executor_handles_syntax_errors_gracefully(self):
        res = self.executor.execute("SELECT * FROM non_existent_table_xyz;")
        self.assertFalse(res["success"])
        self.assertIn("Database Execution Error", res["error"])
        self.assertEqual(res["row_count"], 0)


if __name__ == "__main__":
    unittest.main()
