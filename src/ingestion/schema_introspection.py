"""
Automatic Database Schema Introspection Module.
Dynamically introspects the relational SQLite database:
- Extracts tables, views, columns, data types, primary keys, foreign keys, indexes
- Builds a connected Schema Relationship Graph (nodes, edges, join paths)
- Generates structured schema documents for BM25/Vector RAG indexing and LLM context
- ZERO hardcoded table structures: purely driven by database catalog queries
"""

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Set


class SchemaIntrospector:
    """Introspects relational database catalog dynamically."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found at {self.db_path}")

    def introspect(self) -> Dict[str, Any]:
        """Perform comprehensive database introspection."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 1. Fetch all user tables
        cursor.execute("""
            SELECT name 
            FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name;
        """)
        table_names = [row[0] for row in cursor.fetchall()]
        
        tables_metadata = {}
        relationships = []
        
        for table in table_names:
            # Table row count
            try:
                row_count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except Exception:
                row_count = 0
            
            # Column info via PRAGMA table_info
            # (cid, name, type, notnull, dflt_value, pk)
            cursor.execute(f"PRAGMA table_info({table});")
            col_rows = cursor.fetchall()
            
            columns = []
            primary_keys = []
            for col in col_rows:
                cid, name, data_type, notnull, dflt_val, pk = col
                is_pk = bool(pk > 0)
                if is_pk:
                    primary_keys.append(name)
                columns.append({
                    "column_id": cid,
                    "name": name,
                    "type": data_type,
                    "not_null": bool(notnull),
                    "primary_key": is_pk,
                    "pk_order": pk if is_pk else None,
                })
            
            # Foreign keys via PRAGMA foreign_key_list
            # (id, seq, table, from, to, on_update, on_delete, match)
            cursor.execute(f"PRAGMA foreign_key_list({table});")
            fk_rows = cursor.fetchall()
            
            foreign_keys = []
            for fk in fk_rows:
                fk_id, seq, ref_table, from_col, to_col, on_upd, on_del, match = fk
                fk_info = {
                    "source_table": table,
                    "source_column": from_col,
                    "target_table": ref_table,
                    "target_column": to_col,
                }
                foreign_keys.append(fk_info)
                relationships.append(fk_info)
            
            # Indexes via PRAGMA index_list
            # (seq, name, unique, origin, partial)
            cursor.execute(f"PRAGMA index_list({table});")
            idx_rows = cursor.fetchall()
            indexes = []
            for idx in idx_rows:
                idx_name = idx[1]
                is_unique = bool(idx[2])
                # Index columns via PRAGMA index_info
                cursor.execute(f"PRAGMA index_info({idx_name});")
                idx_cols = [c[2] for c in cursor.fetchall()]
                indexes.append({
                    "name": idx_name,
                    "unique": is_unique,
                    "columns": idx_cols,
                })
            
            tables_metadata[table] = {
                "name": table,
                "row_count": row_count,
                "primary_keys": primary_keys,
                "is_composite_pk": len(primary_keys) > 1,
                "columns": columns,
                "foreign_keys": foreign_keys,
                "indexes": indexes,
            }
        
        # Enrich logical relationships between products and category_translation, and geo summary
        if "products" in tables_metadata and "category_translation" in tables_metadata:
            logical_edge = {
                "source_table": "products",
                "source_column": "product_category_name",
                "target_table": "category_translation",
                "target_column": "product_category_name",
                "is_logical": True,
            }
            if not any(r["source_table"] == "products" and r["target_table"] == "category_translation" for r in relationships):
                relationships.append(logical_edge)
                tables_metadata["products"]["foreign_keys"].append(logical_edge)

        if "customers" in tables_metadata and "geolocation_summary" in tables_metadata:
            geo_cust_edge = {
                "source_table": "customers",
                "source_column": "customer_zip_code_prefix",
                "target_table": "geolocation_summary",
                "target_column": "zip_code_prefix",
                "is_logical": True,
            }
            relationships.append(geo_cust_edge)
            tables_metadata["customers"]["foreign_keys"].append(geo_cust_edge)

        conn.close()
        
        # Build relationship graph adjacency list
        graph_adjacency = {}
        for t in table_names:
            graph_adjacency[t] = set()
            
        for rel in relationships:
            src = rel["source_table"]
            tgt = rel["target_table"]
            if src in graph_adjacency:
                graph_adjacency[src].add(tgt)
            if tgt in graph_adjacency:
                graph_adjacency[tgt].add(src)  # Bidirectional traversal
        
        # Convert sets to sorted lists for JSON serialization
        serializable_graph = {k: sorted(list(v)) for k, v in graph_adjacency.items()}
        
        schema_metadata = {
            "database_type": "SQLite",
            "database_path": str(self.db_path),
            "table_count": len(table_names),
            "tables": tables_metadata,
            "relationships": relationships,
            "relationship_graph": serializable_graph,
        }
        
        return schema_metadata


def generate_schema_documents(metadata: Dict[str, Any]) -> Dict[str, str]:
    """
    Format schema metadata into standardized text documents for BM25 and Vector indexing.
    Each table produces a clean, self-contained semantic document.
    """
    documents = {}
    tables = metadata.get("tables", {})
    
    for table_name, t_info in tables.items():
        doc_lines = [
            f"TABLE: {table_name}",
            f"ROW_COUNT: {t_info['row_count']:,}",
            "PRIMARY_KEY: " + (", ".join(t_info["primary_keys"]) if t_info["primary_keys"] else "NONE"),
            "COLUMNS:",
        ]
        for col in t_info["columns"]:
            pk_mark = " [PRIMARY KEY]" if col["primary_key"] else ""
            nn_mark = " NOT NULL" if col["not_null"] else ""
            doc_lines.append(f"  - {col['name']} ({col['type']}{nn_mark}){pk_mark}")
        
        if t_info["foreign_keys"]:
            doc_lines.append("RELATIONSHIPS:")
            for fk in t_info["foreign_keys"]:
                doc_lines.append(f"  - {fk['source_table']}.{fk['source_column']} -> {fk['target_table']}.{fk['target_column']}")
        
        documents[table_name] = "\n".join(doc_lines)
    
    return documents


def run_introspection(db_path: Path, output_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Run introspection and persist structured documents."""
    introspector = SchemaIntrospector(db_path)
    metadata = introspector.introspect()
    documents = generate_schema_documents(metadata)
    
    print("\n" + "=" * 60)
    print("DATABASE SCHEMA INTROSPECTION COMPLETED")
    print("=" * 60)
    print(f"Total Tables Discovered: {metadata['table_count']}")
    print(f"Total Relationships:     {len(metadata['relationships'])}")
    print("\nDiscovered Relationship Graph:")
    for src, targets in metadata["relationship_graph"].items():
        if targets:
            print(f"  {src:20} <---> {', '.join(targets)}")
            
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        # JSON Schema Metadata
        meta_file = output_dir / "schema_metadata.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        print(f"\nSaved schema metadata JSON to: {meta_file}")
        
        # Schema documentation markdown (combining all tables)
        doc_file = output_dir / "schema_documentation.md"
        with open(doc_file, "w", encoding="utf-8") as f:
            f.write("# Olist Database Schema Documentation\n\n")
            f.write(f"*Auto-generated from live SQLite database catalog at `{metadata['database_path']}`*\n\n")
            for t_name, doc_text in documents.items():
                f.write(f"```text\n{doc_text}\n```\n\n")
        print(f"Saved schema documentation Markdown to: {doc_file}")
        
        # Also store individual table documents for RAG indexing
        rag_dir = output_dir / "schema_docs"
        rag_dir.mkdir(parents=True, exist_ok=True)
        for t_name, doc_text in documents.items():
            t_doc_path = rag_dir / f"{t_name}.txt"
            with open(t_doc_path, "w", encoding="utf-8") as f:
                f.write(doc_text)
        print(f"Saved individual schema documents for RAG in: {rag_dir}")
        
    return metadata


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent.parent
    db_target = base_dir / "data" / "database" / "olist.db"
    report_target = base_dir / "data" / "reports"
    run_introspection(db_target, report_target)
