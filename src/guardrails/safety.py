"""
Safety Policy and Query Complexity Guardrails.
Enforces execution safety policies:
- Prevents multiple chained statements
- Detects unbound queries and injects safe default LIMIT
- Protects against resource exhaustion
"""

from typing import Any, Dict, Optional
import sqlglot
from sqlglot import exp


class SafetyPolicy:
    """Enforces execution safety guardrails."""

    def __init__(self, default_limit: int = 100, max_limit: int = 1000):
        self.default_limit = default_limit
        self.max_limit = max_limit

    def apply_safety_guardrails(self, parsed_ast: exp.Expression, raw_sql: str) -> Dict[str, Any]:
        """
        Check query safety and modify AST if necessary (e.g., adding LIMIT).
        """
        # Guardrail 1: Multiple statements check
        # Count semicolons outside string literals
        trimmed = raw_sql.strip().rstrip(";")
        if ";" in trimmed:
            return {
                "safe": False,
                "error": "Security Violation: Multiple chained SQL statements detected. Only a single query is permitted.",
                "safe_sql": None
            }

        # Guardrail 2: Enforce or cap LIMIT
        limit_clause = parsed_ast.find(exp.Limit)
        if limit_clause is None:
            # Check if it's a scalar aggregation with no group by (returns 1 row naturally)
            is_scalar_agg = (
                not parsed_ast.find(exp.Group)
                and any(parsed_ast.find_all(exp.AggFunc))
            )
            if not is_scalar_agg:
                if hasattr(parsed_ast, "limit"):
                    parsed_ast = parsed_ast.limit(self.default_limit)
                else:
                    parsed_ast.set("limit", exp.Limit(expression=exp.Literal.number(self.default_limit)))
        else:
            # Check if limit exceeds maximum allowed
            try:
                limit_expr = limit_clause.expression
                limit_val = int(limit_expr.this if hasattr(limit_expr, "this") else limit_expr)
                if limit_val > self.max_limit:
                    limit_clause.set("expression", exp.Literal.number(self.max_limit))
            except Exception:
                pass

        return {
            "safe": True,
            "error": None,
            "safe_sql": parsed_ast.sql(dialect="sqlite")
        }
