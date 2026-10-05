"""
Automated Test Suite for Olist Data Engineering & Relational Database Pipeline.
"""

from pathlib import Path
import sqlite3
import unittest

from src.ingestion.clean_data import (
    clean_cell_value,
    normalize_column_name,
    normalize_datetime,
    get_canonical_table_name,
)
from src.ingestion.schema_introspection import SchemaIntrospector

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "database" / "olist.db"


class TestDataCleaning(unittest.TestCase):
    """Test generic cleaning and normalization functions."""

    def test_snake_case_normalization(self):
        self.assertEqual(normalize_column_name("CustomerID"), "customer_id")
        self.assertEqual(normalize_column_name("orderPurchaseTimestamp"), "order_purchase_timestamp")
        self.assertEqual(normalize_column_name("Product Price ($)"), "product_price")
        self.assertEqual(normalize_column_name("\ufeffproduct_category_name"), "product_category_name")
        self.assertEqual(normalize_column_name("product_name_lenght"), "product_name_length")
        self.assertEqual(normalize_column_name("product_description_lenght"), "product_description_length")

    def test_preserves_authentic_nulls_without_imputation(self):
        # Empty values must become Python None (SQL NULL), never fabricated
        self.assertIsNone(clean_cell_value("", "TEXT"))
        self.assertIsNone(clean_cell_value("   ", "TEXT"))
        self.assertIsNone(clean_cell_value("null", "TEXT"))
        self.assertIsNone(clean_cell_value("nan", "TEXT"))
        self.assertIsNone(clean_cell_value("", "INTEGER"))
        self.assertIsNone(clean_cell_value("", "REAL"))
        self.assertIsNone(clean_cell_value("", "DATETIME"))

    def test_datetime_normalization(self):
        self.assertEqual(
            normalize_datetime("2018-05-16 11:58:18"),
            "2018-05-16 11:58:18"
        )
        self.assertEqual(
            normalize_datetime("2018-05-16 11:58:18.000"),
            "2018-05-16 11:58:18"
        )
        self.assertIsNone(normalize_datetime(""))
        self.assertIsNone(normalize_datetime(None))

    def test_canonical_table_names(self):
        self.assertEqual(get_canonical_table_name("olist_orders_dataset.csv"), "orders")
        self.assertEqual(get_canonical_table_name("olist_order_items_dataset.csv"), "order_items")
        self.assertEqual(get_canonical_table_name("product_category_name_translation.csv"), "category_translation")


class TestDatabaseIntegrity(unittest.TestCase):
    """Test the generated SQLite database integrity and constraints."""

    @classmethod
    def setUpClass(cls):
        if not DB_PATH.exists():
            raise unittest.SkipTest(f"Database at {DB_PATH} not yet built. Run pipeline first.")
        cls.conn = sqlite3.connect(str(DB_PATH))
        cls.conn.execute("PRAGMA foreign_keys = ON;")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "conn"):
            cls.conn.close()

    def test_all_expected_tables_exist(self):
        expected_tables = {
            "customers",
            "orders",
            "order_items",
            "order_payments",
            "order_reviews",
            "products",
            "sellers",
            "category_translation",
            "geolocation",
            "geolocation_summary",
        }
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        actual_tables = {row[0] for row in cursor.fetchall()}
        self.assertTrue(expected_tables.issubset(actual_tables), f"Missing tables: {expected_tables - actual_tables}")

    def test_foreign_key_pragma_zero_violations(self):
        cursor = self.conn.cursor()
        violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()
        self.assertEqual(len(violations), 0, f"Found foreign key violations: {violations}")

    def test_composite_primary_keys_uniqueness(self):
        cursor = self.conn.cursor()
        # order_items composite PK
        dup_items = cursor.execute("""
            SELECT order_id, order_item_id, count(*) 
            FROM order_items 
            GROUP BY order_id, order_item_id 
            HAVING count(*) > 1;
        """).fetchall()
        self.assertEqual(len(dup_items), 0)

        # order_payments composite PK
        dup_payments = cursor.execute("""
            SELECT order_id, payment_sequential, count(*) 
            FROM order_payments 
            GROUP BY order_id, payment_sequential 
            HAVING count(*) > 1;
        """).fetchall()
        self.assertEqual(len(dup_payments), 0)

        # order_reviews composite PK
        dup_reviews = cursor.execute("""
            SELECT review_id, order_id, count(*) 
            FROM order_reviews 
            GROUP BY review_id, order_id 
            HAVING count(*) > 1;
        """).fetchall()
        self.assertEqual(len(dup_reviews), 0)

    def test_referential_integrity_no_orphan_orders_or_items(self):
        cursor = self.conn.cursor()
        # Orders without customers
        orphan_orders = cursor.execute("""
            SELECT COUNT(*) FROM orders o 
            LEFT JOIN customers c ON o.customer_id = c.customer_id 
            WHERE c.customer_id IS NULL;
        """).fetchone()[0]
        self.assertEqual(orphan_orders, 0)

        # Items without orders
        orphan_items = cursor.execute("""
            SELECT COUNT(*) FROM order_items i 
            LEFT JOIN orders o ON i.order_id = o.order_id 
            WHERE o.order_id IS NULL;
        """).fetchone()[0]
        self.assertEqual(orphan_items, 0)


class TestSchemaIntrospection(unittest.TestCase):
    """Test that schema introspection dynamically captures metadata."""

    @classmethod
    def setUpClass(cls):
        if not DB_PATH.exists():
            raise unittest.SkipTest(f"Database at {DB_PATH} not yet built. Run pipeline first.")

    def test_introspection_extracts_schema_graph(self):
        introspector = SchemaIntrospector(DB_PATH)
        metadata = introspector.introspect()
        
        self.assertIn("tables", metadata)
        self.assertIn("relationship_graph", metadata)
        self.assertGreaterEqual(metadata["table_count"], 9)
        
        graph = metadata["relationship_graph"]
        self.assertIn("customers", graph)
        self.assertIn("orders", graph["customers"])
        self.assertIn("order_items", graph["orders"])


if __name__ == "__main__":
    unittest.main()
