"""
Schema Hallucination Validator.
Verifies that all tables and columns extracted from the generated SQL query AST
actually exist in the database catalog, preventing hallucinated schemas from executing.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class SchemaValidator:
    """Validates SQL tables and columns against database catalog metadata."""

    def __init__(self, metadata_path: Path):
        self.metadata_path = metadata_path
        self.metadata = self._load_metadata()
        self.catalog_tables: Dict[str, Set[str]] = self._build_catalog_map()

    def _load_metadata(self) -> Dict[str, Any]:
        if not self.metadata_path.exists():
            raise FileNotFoundError(f"Catalog metadata not found at {self.metadata_path}")
        with open(self.metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_catalog_map(self) -> Dict[str, Set[str]]:
        """Map table_name -> set of column names."""
        catalog = {}
        for t_name, t_info in self.metadata.get("tables", {}).items():
            cols = {col["name"].lower() for col in t_info.get("columns", [])}
            catalog[t_name.lower()] = cols
        return catalog

    def validate_schema(
        self,
        tables: List[str],
        columns: List[Tuple[Optional[str], str]],
        table_aliases: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Validate referenced tables and columns against the catalog.
        - tables: list of table names extracted from AST
        - columns: list of (table_alias_or_name, column_name)
        - table_aliases: optional dict mapping alias -> canonical table name
        """
        aliases = table_aliases or {}

        # 1. Validate Tables
        for table in tables:
            canonical_t = aliases.get(table, table)
            if canonical_t not in self.catalog_tables:
                available = ", ".join(sorted(self.catalog_tables.keys()))
                return {
                    "is_valid": False,
                    "error": f"Schema Validation Error: Table '{table}' does not exist in database catalog. Available tables: {available}",
                    "offending_entity": table,
                    "entity_type": "table"
                }

        # Collect all columns present across all referenced tables
        active_table_cols: Dict[str, Set[str]] = {}
        for t in tables:
            can_t = aliases.get(t, t)
            if can_t in self.catalog_tables:
                active_table_cols[can_t] = self.catalog_tables[can_t]

        all_referenced_pool = set()
        for cols in active_table_cols.values():
            all_referenced_pool.update(cols)

        # Standard SQL alias/function keywords to ignore if parsed as columns
        ignored_col_names = {"count", "sum", "avg", "min", "max", "as", "distinct", "null", "like", "in"}

        # 2. Validate Columns
        for table_prefix, col_name in columns:
            if col_name in ignored_col_names:
                continue

            target_table = aliases.get(table_prefix, table_prefix) if table_prefix else None

            if target_table and target_table in self.catalog_tables:
                # Table explicitly specified, verify column in that specific table
                if col_name not in self.catalog_tables[target_table]:
                    avail = ", ".join(sorted(self.catalog_tables[target_table]))
                    return {
                        "is_valid": False,
                        "error": (
                            f"Schema Validation Error: Column '{col_name}' does not exist in table '{target_table}'. "
                            f"Available columns in '{target_table}' are: {avail}"
                        ),
                        "offending_entity": f"{target_table}.{col_name}",
                        "entity_type": "column"
                    }
            else:
                # Table not prefixed or alias unresolved, verify column exists in at least one of the queried tables
                if col_name not in all_referenced_pool:
                    table_summary = "; ".join(
                        f"{t} ({', '.join(sorted(cols))})" for t, cols in active_table_cols.items()
                    )
                    return {
                        "is_valid": False,
                        "error": (
                            f"Schema Validation Error: Column '{col_name}' does not exist in queried tables {list(active_table_cols.keys())}. "
                            f"Table column schemas: {table_summary}"
                        ),
                        "offending_entity": col_name,
                        "entity_type": "column"
                    }

        return {
            "is_valid": True,
            "error": None,
            "validated_tables": tables,
            "validated_columns": columns
        }


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent.parent
    meta = base / "data" / "reports" / "schema_metadata.json"
    validator = SchemaValidator(meta)

    # Test valid columns
    v1 = validator.validate_schema(["customers"], [("customers", "customer_id"), (None, "customer_city")])
    print("Valid Schema Test:", v1["is_valid"])

    # Test hallucinated column
    v2 = validator.validate_schema(["customers"], [("customers", "customer_name")])
    print("Hallucinated Col Test:", v2["is_valid"], "Error:", v2["error"])
