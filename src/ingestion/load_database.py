"""
Relational Database Loader for Olist E-Commerce Dataset.
Creates SQLite database with:
- Strict relational DDL (Data Types, Primary Keys, Composite PKs, Foreign Keys)
- B-tree indexes on foreign keys and lookup columns for fast joins
- Clean batch ingestion preserving authentic NULL values (no synthetic data)
- High-performance SQLite PRAGMAs (WAL mode, transactions)
"""

import csv
import os
from pathlib import Path
import sqlite3
import sys
import time
from typing import Dict, List, Optional, Tuple

from src.ingestion.clean_data import (
    clean_cell_value,
    get_canonical_table_name,
    normalize_column_name,
)

# Table schemas with explicit DDL
DDL_STATEMENTS = {
    "customers": """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            customer_unique_id TEXT NOT NULL,
            customer_zip_code_prefix TEXT,
            customer_city TEXT,
            customer_state TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_customers_unique_id ON customers(customer_unique_id);
        CREATE INDEX IF NOT EXISTS idx_customers_zip ON customers(customer_zip_code_prefix);
        CREATE INDEX IF NOT EXISTS idx_customers_city_state ON customers(customer_city, customer_state);
    """,
    "category_translation": """
        CREATE TABLE IF NOT EXISTS category_translation (
            product_category_name TEXT PRIMARY KEY,
            product_category_name_english TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cat_trans_english ON category_translation(product_category_name_english);
    """,
    "products": """
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            product_category_name TEXT,
            product_name_length INTEGER,
            product_description_length INTEGER,
            product_photos_qty INTEGER,
            product_weight_g REAL,
            product_length_cm REAL,
            product_height_cm REAL,
            product_width_cm REAL
        );
        CREATE INDEX IF NOT EXISTS idx_products_category ON products(product_category_name);
    """,
    "sellers": """
        CREATE TABLE IF NOT EXISTS sellers (
            seller_id TEXT PRIMARY KEY,
            seller_zip_code_prefix TEXT,
            seller_city TEXT,
            seller_state TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_sellers_zip ON sellers(seller_zip_code_prefix);
        CREATE INDEX IF NOT EXISTS idx_sellers_city_state ON sellers(seller_city, seller_state);
    """,
    "orders": """
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            order_status TEXT,
            order_purchase_timestamp DATETIME,
            order_approved_at DATETIME,
            order_delivered_carrier_date DATETIME,
            order_delivered_customer_date DATETIME,
            order_estimated_delivery_date DATETIME,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );
        CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(order_status);
        CREATE INDEX IF NOT EXISTS idx_orders_purchase_ts ON orders(order_purchase_timestamp);
    """,
    "order_items": """
        CREATE TABLE IF NOT EXISTS order_items (
            order_id TEXT NOT NULL,
            order_item_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            seller_id TEXT NOT NULL,
            shipping_limit_date DATETIME,
            price REAL,
            freight_value REAL,
            PRIMARY KEY (order_id, order_item_id),
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id),
            FOREIGN KEY (seller_id) REFERENCES sellers(seller_id)
        );
        CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
        CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
        CREATE INDEX IF NOT EXISTS idx_order_items_seller_id ON order_items(seller_id);
    """,
    "order_payments": """
        CREATE TABLE IF NOT EXISTS order_payments (
            order_id TEXT NOT NULL,
            payment_sequential INTEGER NOT NULL,
            payment_type TEXT,
            payment_installments INTEGER,
            payment_value REAL,
            PRIMARY KEY (order_id, payment_sequential),
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        );
        CREATE INDEX IF NOT EXISTS idx_order_payments_order_id ON order_payments(order_id);
        CREATE INDEX IF NOT EXISTS idx_order_payments_type ON order_payments(payment_type);
    """,
    "order_reviews": """
        CREATE TABLE IF NOT EXISTS order_reviews (
            review_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            review_score INTEGER,
            review_comment_title TEXT,
            review_comment_message TEXT,
            review_creation_date DATETIME,
            review_answer_timestamp DATETIME,
            PRIMARY KEY (review_id, order_id),
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        );
        CREATE INDEX IF NOT EXISTS idx_order_reviews_order_id ON order_reviews(order_id);
        CREATE INDEX IF NOT EXISTS idx_order_reviews_score ON order_reviews(review_score);
    """,
    "geolocation": """
        CREATE TABLE IF NOT EXISTS geolocation (
            geolocation_zip_code_prefix TEXT,
            geolocation_lat REAL,
            geolocation_lng REAL,
            geolocation_city TEXT,
            geolocation_state TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_geolocation_zip ON geolocation(geolocation_zip_code_prefix);
        CREATE INDEX IF NOT EXISTS idx_geolocation_city_state ON geolocation(geolocation_city, geolocation_state);
    """,
}

# Column types for each table to apply appropriate cleaning without inventing data
COLUMN_TYPES = {
    "customers": {
        "customer_id": "TEXT",
        "customer_unique_id": "TEXT",
        "customer_zip_code_prefix": "TEXT",
        "customer_city": "TEXT",
        "customer_state": "TEXT",
    },
    "category_translation": {
        "product_category_name": "TEXT",
        "product_category_name_english": "TEXT",
    },
    "products": {
        "product_id": "TEXT",
        "product_category_name": "TEXT",
        "product_name_length": "INTEGER",
        "product_description_length": "INTEGER",
        "product_photos_qty": "INTEGER",
        "product_weight_g": "REAL",
        "product_length_cm": "REAL",
        "product_height_cm": "REAL",
        "product_width_cm": "REAL",
    },
    "sellers": {
        "seller_id": "TEXT",
        "seller_zip_code_prefix": "TEXT",
        "seller_city": "TEXT",
        "seller_state": "TEXT",
    },
    "orders": {
        "order_id": "TEXT",
        "customer_id": "TEXT",
        "order_status": "TEXT",
        "order_purchase_timestamp": "DATETIME",
        "order_approved_at": "DATETIME",
        "order_delivered_carrier_date": "DATETIME",
        "order_delivered_customer_date": "DATETIME",
        "order_estimated_delivery_date": "DATETIME",
    },
    "order_items": {
        "order_id": "TEXT",
        "order_item_id": "INTEGER",
        "product_id": "TEXT",
        "seller_id": "TEXT",
        "shipping_limit_date": "DATETIME",
        "price": "REAL",
        "freight_value": "REAL",
    },
    "order_payments": {
        "order_id": "TEXT",
        "payment_sequential": "INTEGER",
        "payment_type": "TEXT",
        "payment_installments": "INTEGER",
        "payment_value": "REAL",
    },
    "order_reviews": {
        "review_id": "TEXT",
        "order_id": "TEXT",
        "review_score": "INTEGER",
        "review_comment_title": "TEXT",
        "review_comment_message": "TEXT",
        "review_creation_date": "DATETIME",
        "review_answer_timestamp": "DATETIME",
    },
    "geolocation": {
        "geolocation_zip_code_prefix": "TEXT",
        "geolocation_lat": "REAL",
        "geolocation_lng": "REAL",
        "geolocation_city": "TEXT",
        "geolocation_state": "TEXT",
    },
}

# Order of loading to ensure parent tables precede child tables (FK satisfaction)
LOAD_ORDER = [
    "category_translation",
    "products",
    "sellers",
    "customers",
    "orders",
    "order_items",
    "order_payments",
    "order_reviews",
    "geolocation",
]


def create_schema(conn: sqlite3.Connection):
    """Execute DDL statements to set up schema."""
    cursor = conn.cursor()
    for table_name in LOAD_ORDER:
        ddl = DDL_STATEMENTS.get(table_name)
        if ddl:
            cursor.executescript(ddl)
    conn.commit()


def load_table_from_csv(conn: sqlite3.Connection, table_name: str, csv_path: Path, batch_size: int = 20000) -> int:
    """Load and clean records from CSV directly into SQLite table using batch transactions."""
    types_map = COLUMN_TYPES.get(table_name, {})
    
    with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        try:
            raw_headers = next(reader)
        except StopIteration:
            return 0
        
        # Normalize column names
        norm_headers = [normalize_column_name(h) for h in raw_headers]
        
        # Ensure only known columns for this table are inserted
        col_indices = []
        target_cols = []
        for idx, h in enumerate(norm_headers):
            if h in types_map:
                col_indices.append(idx)
                target_cols.append(h)
        
        placeholders = ", ".join(["?"] * len(target_cols))
        cols_str = ", ".join(target_cols)
        sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
        
        cursor = conn.cursor()
        batch = []
        total_rows = 0
        
        for row in reader:
            cleaned_row = []
            for idx, col_name in zip(col_indices, target_cols):
                raw_val = row[idx] if idx < len(row) else None
                col_type = types_map.get(col_name)
                # Clean preserving authentic None/NULL
                val = clean_cell_value(raw_val, col_type)
                cleaned_row.append(val)
            
            batch.append(tuple(cleaned_row))
            if len(batch) >= batch_size:
                cursor.executemany(sql, batch)
                total_rows += len(batch)
                batch = []
        
        if batch:
            cursor.executemany(sql, batch)
            total_rows += len(batch)
        
        conn.commit()
    return total_rows


def build_geolocation_summary(conn: sqlite3.Connection):
    """
    Build a deduplicated summary table from geolocation (1 unique row per zip prefix)
    with average coordinates and primary city/state to avoid Cartesian join explosions.
    """
    print("Building geolocation_summary table (1 row per unique zip prefix)...")
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS geolocation_summary (
            zip_code_prefix TEXT PRIMARY KEY,
            lat REAL,
            lng REAL,
            city TEXT,
            state TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_geo_sum_city_state ON geolocation_summary(city, state);
        
        INSERT OR REPLACE INTO geolocation_summary (zip_code_prefix, lat, lng, city, state)
        SELECT 
            geolocation_zip_code_prefix AS zip_code_prefix,
            AVG(geolocation_lat) AS lat,
            AVG(geolocation_lng) AS lng,
            geolocation_city AS city,
            geolocation_state AS state
        FROM geolocation
        GROUP BY geolocation_zip_code_prefix;
    """)
    conn.commit()
    count = cursor.execute("SELECT COUNT(*) FROM geolocation_summary").fetchone()[0]
    print(f"geolocation_summary populated with {count:,} distinct zip codes.")


def load_database(raw_data_dir: Path, db_path: Path) -> sqlite3.Connection:
    """End-to-end database loading pipeline."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        print(f"Removing existing database at {db_path} to ensure clean load...")
        try:
            db_path.unlink()
        except Exception:
            pass

    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(str(db_path))
    
    # Configure high performance & safety PRAGMAs
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = 10000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    
    print("Creating relational schema with explicit constraints...")
    create_schema(conn)
    
    # Find CSV files in directory
    file_map = {}
    for f in raw_data_dir.glob("*.csv"):
        canonical = get_canonical_table_name(f.name)
        file_map[canonical] = f
    
    print("\nLoading tables in dependency order:")
    start_time = time.time()
    for table_name in LOAD_ORDER:
        csv_file = file_map.get(table_name)
        if not csv_file:
            print(f"  [WARNING] CSV file for table '{table_name}' not found!")
            continue
        
        t0 = time.time()
        print(f"  -> Loading '{table_name}' from {csv_file.name}...", end="", flush=True)
        rows = load_table_from_csv(conn, table_name, csv_file)
        elapsed = round(time.time() - t0, 2)
        print(f" Done ({rows:,} rows inserted in {elapsed}s)")
    
    # Generate geolocation summary for high-performance spatial joins
    if "geolocation" in file_map:
        build_geolocation_summary(conn)
    
    total_time = round(time.time() - start_time, 2)
    print(f"\nDatabase successfully loaded in {total_time}s!")
    return conn


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent.parent
    raw_dir = base_dir / "data" / "raw" / "olist"
    if not raw_dir.exists() or not list(raw_dir.glob("*.csv")):
        raw_dir = base_dir
    
    db_target = base_dir / "data" / "database" / "olist.db"
    conn = load_database(raw_dir, db_target)
    conn.close()
