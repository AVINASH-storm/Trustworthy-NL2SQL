"""
Adaptive Schema Selector.
Synthesizes Hybrid Retrieval and Relationship Graph Expansion to construct the
minimal, sufficient, and relationally connected schema context for the LLM.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.retrieval.hybrid_retriever import HybridSchemaRetriever
from src.retrieval.relationship_graph import SchemaRelationshipGraph


class AdaptiveSchemaSelector:
    """Selects and expands schema context adaptively for a natural language query."""

    def __init__(self, schema_docs_dir: Path, metadata_path: Path):
        self.retriever = HybridSchemaRetriever(schema_docs_dir)
        self.graph = SchemaRelationshipGraph(metadata_path)
        self.metadata = self.graph.metadata

    def select_schema(self, query: str, top_candidates: int = 3) -> Dict[str, Any]:
        """
        Adaptively select and expand relevant schema for a user query.
        """
        # 1. Hybrid retrieval (top candidates)
        hybrid_results = self.retriever.retrieve(query, top_k=top_candidates)
        candidate_tables = [r["table"] for r in hybrid_results]

        # Domain-aware 1-hop heuristic:
        # If 'products' is selected and user mentions 'english', 'translate', or 'category', ensure 'category_translation' is included
        q_lower = query.lower()
        if "product" in candidate_tables or "products" in candidate_tables:
            if any(k in q_lower for k in ("english", "category", "categories", "translate", "name")):
                if "category_translation" not in candidate_tables:
                    candidate_tables.append("category_translation")

        # If user asks about customer locations/cities/states and customers is selected, consider geolocation_summary
        if "customers" in candidate_tables or "sellers" in candidate_tables:
            if any(k in q_lower for k in ("distance", "coordinate", "lat", "lng", "location", "geo")):
                if "geolocation_summary" not in candidate_tables:
                    candidate_tables.append("geolocation_summary")

        # 2. Graph expansion to bridge disconnected tables
        expanded_tables, active_joins = self.graph.expand_candidates(candidate_tables)
        bridged_tables = [t for t in expanded_tables if t not in candidate_tables]

        # 3. Construct Schema Context Text for LLM
        schema_context_lines = [
            "DATABASE DIALECT: SQLite",
            "\nRELEVANT TABLES & COLUMNS:"
        ]

        tables_meta = self.metadata.get("tables", {})
        for t_name in expanded_tables:
            t_info = tables_meta.get(t_name)
            if not t_info:
                continue
            pk_str = ", ".join(t_info["primary_keys"]) if t_info["primary_keys"] else "NONE"
            schema_context_lines.append(f"\nTABLE: {t_name}")
            schema_context_lines.append(f"  Primary Key: {pk_str}")
            schema_context_lines.append("  Columns:")
            for col in t_info["columns"]:
                pk_flag = " [PK]" if col["primary_key"] else ""
                schema_context_lines.append(f"    - {col['name']} ({col['type']}){pk_flag}")

        if active_joins:
            schema_context_lines.append("\nALLOWED TABLE RELATIONSHIPS (JOIN CONDITIONS):")
            for j in active_joins:
                schema_context_lines.append(
                    f"  - {j['source_table']}.{j['source_col']} = {j['target_table']}.{j['target_col']}"
                )

        schema_context_text = "\n".join(schema_context_lines)

        return {
            "query": query,
            "initial_candidates": candidate_tables,
            "bridged_tables": bridged_tables,
            "selected_tables": expanded_tables,
            "active_joins": active_joins,
            "hybrid_ranking": hybrid_results,
            "schema_context_text": schema_context_text
        }


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent.parent
    docs_dir = base / "data" / "reports" / "schema_docs"
    meta_file = base / "data" / "reports" / "schema_metadata.json"
    selector = AdaptiveSchemaSelector(docs_dir, meta_file)

    res = selector.select_schema("Which customers spent the most money on watches?")
    print("Selected Tables:", res["selected_tables"])
    print("Bridged Tables:", res["bridged_tables"])
    print("\n--- SCHEMA CONTEXT ---")
    print(res["schema_context_text"])
