"""
Unit Tests for SQLGlot AST Guardrails and Schema Validator.
"""

from pathlib import Path
import unittest

from src.guardrails.sql_validator import SQLValidator
from src.guardrails.schema_validator import SchemaValidator
from src.guardrails.safety import SafetyPolicy

PROJECT_ROOT = Path(__file__).resolve().parent.parent
META_PATH = PROJECT_ROOT / "data" / "reports" / "schema_metadata.json"


class TestSQLGuardrails(unittest.TestCase):
    """Test AST parsing, destructive statement blocking, and hallucination checks."""

    @classmethod
    def setUpClass(cls):
        cls.sql_val = SQLValidator(dialect="sqlite")
        cls.schema_val = SchemaValidator(META_PATH)
        cls.safety = SafetyPolicy(default_limit=100)

    def test_allows_safe_select_query(self):
        sql = "SELECT customer_id, customer_city FROM customers WHERE customer_state = 'SP' LIMIT 10;"
        res = self.sql_val.validate(sql)
        self.assertTrue(res["is_valid"])
        self.assertIn("customers", res["tables"])

    def test_allows_cte_select_query(self):
        sql = """
        WITH high_value_orders AS (
            SELECT order_id, SUM(price) as total_val
            FROM order_items
            GROUP BY order_id
            HAVING total_val > 500
        )
        SELECT * FROM high_value_orders LIMIT 10;
        """
        res = self.sql_val.validate(sql)
        self.assertTrue(res["is_valid"])

    def test_blocks_destructive_drop_table(self):
        sql = "DROP TABLE customers;"
        res = self.sql_val.validate(sql)
        self.assertFalse(res["is_valid"])
        self.assertIn("Security Violation", res["error"])

    def test_blocks_destructive_delete(self):
        sql = "DELETE FROM orders WHERE order_status = 'canceled';"
        res = self.sql_val.validate(sql)
        self.assertFalse(res["is_valid"])
        self.assertIn("Security Violation", res["error"])

    def test_blocks_destructive_insert(self):
        sql = "INSERT INTO customers (customer_id, customer_unique_id) VALUES ('123', '456');"
        res = self.sql_val.validate(sql)
        self.assertFalse(res["is_valid"])
        self.assertIn("Security Violation", res["error"])

    def test_blocks_destructive_update(self):
        sql = "UPDATE orders SET order_status = 'delivered' WHERE order_id = '123';"
        res = self.sql_val.validate(sql)
        self.assertFalse(res["is_valid"])
        self.assertIn("Security Violation", res["error"])

    def test_schema_validator_catches_nonexistent_table(self):
        tables = ["non_existent_clients"]
        columns = [(None, "client_id")]
        res = self.schema_val.validate_schema(tables, columns)
        self.assertFalse(res["is_valid"])
        self.assertIn("does not exist in database catalog", res["error"])

    def test_schema_validator_catches_hallucinated_column(self):
        tables = ["customers"]
        columns = [("customers", "customer_name")]
        res = self.schema_val.validate_schema(tables, columns, table_aliases={"customers": "customers"})
        self.assertFalse(res["is_valid"])
        self.assertIn("Column 'customer_name' does not exist in table 'customers'", res["error"])

    def test_safety_policy_blocks_multiple_statements(self):
        sql = "SELECT * FROM customers; DROP TABLE orders;"
        parsed = self.sql_val.validate("SELECT * FROM customers")["ast"]
        res = self.safety = SafetyPolicy().apply_safety_guardrails(parsed, sql)
        self.assertFalse(res["safe"])
        self.assertIn("Multiple chained SQL statements", res["error"])

    def test_safety_policy_injects_default_limit(self):
        sql = "SELECT customer_id FROM customers"
        parsed = self.sql_val.validate(sql)["ast"]
        res = SafetyPolicy(default_limit=50).apply_safety_guardrails(parsed, sql)
        self.assertTrue(res["safe"])
        self.assertIn("LIMIT 50", res["safe_sql"])


if __name__ == "__main__":
    unittest.main()
