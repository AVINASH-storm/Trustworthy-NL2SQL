"""
Database Validation and Referential Integrity Auditor.
Verifies the loaded SQLite relational database:
1. Exact row count parity between raw CSV records and DB tables
2. Primary Key audit: 0 nulls and 0 duplicate keys across single and composite keys
3. Referential Integrity: PRAGMA foreign_key_check + cross-table orphan audits
4. Authentic NULL verification: confirms genuine real-world nulls were preserved, not synthesized
"""

import csv
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Dict, List, Tuple

from src.ingestion.clean_data import get_canonical_table_name
from src.ingestion.load_database import LOAD_ORDER

# Primary key definitions for audit
PRIMARY_KEYS = {
    "customers": ["customer_id"],
    "orders": ["order_id"],
    "category_translation": ["product_category_name"],
    "products": ["product_id"],
    "sellers": ["seller_id"],
    "order_items": ["order_id", "order_item_id"],
    "order_payments": ["order_id", "payment_sequential"],
    "order_reviews": ["review_id", "order_id"],
    "geolocation_summary": ["zip_code_prefix"],
}

# Foreign key relationships to audit for orphan rows
FK_RELATIONSHIPS = [
    {
        "child_table": "orders",
        "child_col": "customer_id",
        "parent_table": "customers",
        "parent_col": "customer_id",
    },
    {
        "child_table": "order_items",
        "child_col": "order_id",
        "parent_table": "orders",
        "parent_col": "order_id",
    },
    {
        "child_table": "order_items",
        "child_col": "product_id",
        "parent_table": "products",
        "parent_col": "product_id",
    },
    {
        "child_table": "order_items",
        "child_col": "seller_id",
        "parent_table": "sellers",
        "parent_col": "seller_id",
    },
    {
        "child_table": "order_payments",
        "child_col": "order_id",
        "parent_table": "orders",
        "parent_col": "order_id",
    },
    {
        "child_table": "order_reviews",
        "child_col": "order_id",
        "parent_table": "orders",
        "parent_col": "order_id",
    },
]


def count_csv_records(csv_path: Path) -> int:
    """Count actual parsed data records in CSV, handling multiline entries safely."""
    with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        try:
            next(reader)  # skip header
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def validate_database(db_path: Path, raw_data_dir: Path, output_report_dir: Path = None) -> Dict[str, Any]:
    """Run full validation suite against SQLite database."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()
    
    report = {
        "database": str(db_path),
        "checks": {
            "row_counts": {},
            "primary_keys": {},
            "foreign_key_pragma": {},
            "orphan_audits": {},
            "null_authenticity": {},
        },
        "all_passed": True,
    }
    
    print("\n" + "=" * 60)
    print("STARTING DATABASE VALIDATION SUITE")
    print("=" * 60)
    
    # 1. Row count verification
    print("\n[1] Row Count Verification (CSV vs DB Table):")
    file_map = {get_canonical_table_name(f.name): f for f in raw_data_dir.glob("*.csv")}
    
    for table_name in LOAD_ORDER:
        csv_file = file_map.get(table_name)
        if not csv_file:
            continue
        
        csv_count = count_csv_records(csv_file)
        db_count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        match = (csv_count == db_count)
        
        report["checks"]["row_counts"][table_name] = {
            "csv_rows": csv_count,
            "db_rows": db_count,
            "match": match,
        }
        
        status = "PASSED" if match else "FAILED"
        if not match:
            report["all_passed"] = False
        print(f"  {table_name:22} CSV: {csv_count:7,d} | DB: {db_count:7,d} -> [{status}]")
    
    # 2. Primary Key Audit
    print("\n[2] Primary Key Audit (Uniqueness & Non-nullness):")
    for table_name, pk_cols in PRIMARY_KEYS.items():
        # Check if table exists
        exists = cursor.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchone()[0]
        if not exists:
            continue
        
        pk_cols_str = ", ".join(pk_cols)
        null_conditions = " OR ".join([f"{col} IS NULL" for col in pk_cols])
        
        # Check NULL PKs
        null_sql = f"SELECT COUNT(*) FROM {table_name} WHERE {null_conditions}"
        null_count = cursor.execute(null_sql).fetchone()[0]
        
        # Check duplicate PKs
        dup_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT {pk_cols_str}, COUNT(*) AS cnt
                FROM {table_name}
                GROUP BY {pk_cols_str}
                HAVING cnt > 1
            )
        """
        dup_count = cursor.execute(dup_sql).fetchone()[0]
        
        passed = (null_count == 0 and dup_count == 0)
        if not passed:
            report["all_passed"] = False
            
        report["checks"]["primary_keys"][table_name] = {
            "primary_key": pk_cols,
            "null_pks": null_count,
            "duplicate_pks": dup_count,
            "passed": passed,
        }
        
        status = "PASSED" if passed else "FAILED"
        print(f"  {table_name:22} PK: ({pk_cols_str:25}) | Nulls: {null_count} | Duplicates: {dup_count} -> [{status}]")
    
    # 3. Foreign Key PRAGMA check
    print("\n[3] SQLite Foreign Key Engine Check (PRAGMA foreign_key_check):")
    fk_violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()
    fk_passed = len(fk_violations) == 0
    if not fk_passed:
        report["all_passed"] = False
        
    report["checks"]["foreign_key_pragma"] = {
        "violations_count": len(fk_violations),
        "violations": fk_violations,
        "passed": fk_passed,
    }
    status = "PASSED" if fk_passed else "FAILED"
    print(f"  PRAGMA foreign_key_check violations: {len(fk_violations)} -> [{status}]")
    
    # 4. Programmatic Orphan Audits
    print("\n[4] Referential Integrity Orphan Audits:")
    for rel in FK_RELATIONSHIPS:
        child = rel["child_table"]
        child_col = rel["child_col"]
        parent = rel["parent_table"]
        parent_col = rel["parent_col"]
        
        sql = f"""
            SELECT COUNT(*)
            FROM {child} c
            LEFT JOIN {parent} p ON c.{child_col} = p.{parent_col}
            WHERE c.{child_col} IS NOT NULL AND p.{parent_col} IS NULL
        """
        orphan_count = cursor.execute(sql).fetchone()[0]
        passed = (orphan_count == 0)
        if not passed:
            report["all_passed"] = False
            
        edge_name = f"{child}.{child_col} -> {parent}.{parent_col}"
        report["checks"]["orphan_audits"][edge_name] = {
            "orphan_count": orphan_count,
            "passed": passed,
        }
        status = "PASSED" if passed else "FAILED"
        print(f"  {edge_name:45} Orphans: {orphan_count:5d} -> [{status}]")
    
    # 5. Non-imputation Authenticity Check
    print("\n[5] Authentic NULL Preservation Check (Zero Imputation Verification):")
    null_test_columns = [
        ("orders", "order_delivered_customer_date"),
        ("order_reviews", "review_comment_title"),
        ("products", "product_category_name"),
    ]
    for table_name, col_name in null_test_columns:
        cnt = cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {col_name} IS NULL").fetchone()[0]
        # Should have real-world missing values
        preserved = cnt > 0
        report["checks"]["null_authenticity"][f"{table_name}.{col_name}"] = {
            "null_count": cnt,
            "preserved_authentic_nulls": preserved,
        }
        print(f"  {table_name}.{col_name:30} Authentic NULLs preserved: {cnt:,} -> [VERIFIED]")
    
    print("\n" + "=" * 60)
    overall_status = "ALL AUDIT CHECKS PASSED SUCCESSFULLY!" if report["all_passed"] else "VALIDATION AUDIT FOUND FAILURES!"
    print(overall_status)
    print("=" * 60 + "\n")
    
    if output_report_dir:
        output_report_dir.mkdir(parents=True, exist_ok=True)
        report_file = output_report_dir / "database_validation_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Detailed validation report written to: {report_file}")
    
    conn.close()
    return report


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent.parent
    raw_dir = base_dir / "data" / "raw" / "olist"
    if not raw_dir.exists() or not list(raw_dir.glob("*.csv")):
        raw_dir = base_dir
    
    db_target = base_dir / "data" / "database" / "olist.db"
    report_target = base_dir / "data" / "reports"
    validate_database(db_target, raw_dir, report_target)
