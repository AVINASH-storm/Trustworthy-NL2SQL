"""
SQLGlot AST-Based SQL Validator.
Parses generated SQL queries into an Abstract Syntax Tree (AST):
- Strictly enforces SELECT-only read access (including WITH ... SELECT CTEs)
- Blocks all destructive statements (INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, PRAGMA)
- Extracts referenced tables and columns for schema validation
"""

from typing import Any, Dict, List, Optional, Set
import sqlglot
from sqlglot import exp


# Destructive/administrative statement types strictly forbidden
FORBIDDEN_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,
    exp.Pragma,
)


class SQLValidator:
    """Validates SQL query syntax and read-only compliance via SQLGlot."""

    def __init__(self, dialect: str = "sqlite"):
        self.dialect = dialect

    def validate(self, sql: str) -> Dict[str, Any]:
        """
        Validate SQL string:
        - Check syntax validity in target dialect
        - Verify query is strictly read-only (SELECT)
        - Extract referenced tables and columns
        """
        if not sql or not sql.strip():
            return {
                "is_valid": False,
                "error": "Empty SQL query.",
                "tables": [],
                "columns": [],
                "ast": None
            }

        clean_sql = sql.strip().rstrip(";")
        
        try:
            parsed = sqlglot.parse_one(clean_sql, read=self.dialect)
        except sqlglot.errors.ParseError as e:
            return {
                "is_valid": False,
                "error": f"SQL syntax parsing error: {str(e)}",
                "tables": [],
                "columns": [],
                "ast": None
            }
        except Exception as e:
            return {
                "is_valid": False,
                "error": f"Unexpected SQL parsing error: {str(e)}",
                "tables": [],
                "columns": [],
                "ast": None
            }

        # Verify no forbidden expressions anywhere in the AST
        for forbidden_type in FORBIDDEN_EXPRESSIONS:
            found = list(parsed.find_all(forbidden_type))
            if found:
                action = forbidden_type.__name__.replace("exp.", "").upper()
                return {
                    "is_valid": False,
                    "error": f"Security Violation: Query contains prohibited operation '{action}'. Only read-only SELECT queries are permitted.",
                    "tables": [],
                    "columns": [],
                    "ast": parsed
                }

        # Check that top-level statement is a Select or CTE with Select
        is_select = isinstance(parsed, exp.Select)
        is_cte_select = isinstance(parsed, exp.Select) or (
            hasattr(parsed, "this") and isinstance(parsed.this, exp.Select)
        )
        if not is_select and not is_cte_select:
            return {
                "is_valid": False,
                "error": f"Query statement type '{type(parsed).__name__}' is not permitted. Only SELECT statements are allowed.",
                "tables": [],
                "columns": [],
                "ast": parsed
            }

        # Extract referenced tables and table aliases (excluding CTE aliases)
        cte_aliases = {cte.alias.lower() for cte in parsed.find_all(exp.CTE) if cte.alias}
        tables = set()
        table_aliases = {}
        for t in parsed.find_all(exp.Table):
            table_name = t.name.lower()
            if table_name and table_name not in cte_aliases:
                tables.add(table_name)
                table_aliases[table_name] = table_name
                if t.alias:
                    table_aliases[t.alias.lower()] = table_name

        # Extract projection aliases (e.g. AS total_revenue) so they aren't flagged as missing columns
        projection_aliases = {
            a.alias_or_name.lower() for a in parsed.find_all(exp.Alias) if a.alias_or_name
        }

        # Extract referenced columns (excluding projection aliases and wildcard)
        columns = set()
        for c in parsed.find_all(exp.Column):
            col_name = c.name.lower()
            if col_name and col_name != "*" and col_name not in projection_aliases:
                table_prefix = c.table.lower() if c.table else None
                columns.add((table_prefix, col_name))

        return {
            "is_valid": True,
            "error": None,
            "tables": sorted(list(tables)),
            "table_aliases": table_aliases,
            "projection_aliases": projection_aliases,
            "columns": sorted(list(columns), key=lambda x: (x[0] or "", x[1])),
            "ast": parsed,
            "formatted_sql": parsed.sql(dialect=self.dialect, pretty=True)
        }


if __name__ == "__main__":
    validator = SQLValidator()

    # Test safe query
    safe_res = validator.validate("SELECT customer_id, customer_city FROM customers WHERE customer_state = 'SP' LIMIT 10")
    print("Safe Query Valid:", safe_res["is_valid"], safe_res["tables"], safe_res["columns"])

    # Test malicious query
    mal_res = validator.validate("DROP TABLE customers; SELECT 1;")
    print("Malicious Query Valid:", mal_res["is_valid"], "Error:", mal_res["error"])
