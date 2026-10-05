"""
Schema Relationship Graph & Adaptive Path Expander.
Models tables as nodes and foreign key relationships as edges.
Finds bridging tables and constructs valid relational join paths between disconnected candidate tables.
"""

from collections import deque
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class SchemaRelationshipGraph:
    """Graph representation of the introspected database schema."""

    def __init__(self, metadata_path: Path):
        self.metadata_path = metadata_path
        self.metadata = self._load_metadata()
        self.tables: Set[str] = set(self.metadata.get("tables", {}).keys())
        self.relationships: List[Dict[str, any]] = self.metadata.get("relationships", [])
        self.adjacency: Dict[str, Dict[str, List[Dict[str, str]]]] = self._build_graph()

    def _load_metadata(self) -> Dict[str, any]:
        if not self.metadata_path.exists():
            raise FileNotFoundError(f"Schema metadata not found at {self.metadata_path}")
        with open(self.metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_graph(self) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
        """Build graph where adjacency[u][v] contains the list of join constraints between u and v."""
        adj = {t: {} for t in self.tables}
        for rel in self.relationships:
            src = rel["source_table"]
            tgt = rel["target_table"]
            if src not in adj:
                adj[src] = {}
            if tgt not in adj:
                adj[tgt] = {}

            edge_info = {
                "source_table": src,
                "source_col": rel["source_column"],
                "target_table": tgt,
                "target_col": rel["target_column"]
            }
            if tgt not in adj[src]:
                adj[src][tgt] = []
            adj[src][tgt].append(edge_info)

            # Bidirectional edge
            reverse_edge = {
                "source_table": tgt,
                "source_col": rel["target_column"],
                "target_table": src,
                "target_col": rel["source_column"]
            }
            if src not in adj[tgt]:
                adj[tgt][src] = []
            adj[tgt][src].append(reverse_edge)

        return adj

    def get_neighbors(self, table: str) -> List[str]:
        """Get 1-hop neighboring tables directly connected by a foreign key."""
        return list(self.adjacency.get(table, {}).keys())

    def find_shortest_path(self, start: str, end: str) -> Optional[List[str]]:
        """Find the shortest join path between two tables using BFS."""
        if start == end:
            return [start]
        if start not in self.adjacency or end not in self.adjacency:
            return None

        queue = deque([[start]])
        visited = {start}

        while queue:
            path = queue.popleft()
            curr = path[-1]

            for neighbor in self.adjacency.get(curr, {}):
                if neighbor == end:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return None

    def expand_candidates(self, initial_tables: List[str]) -> Tuple[List[str], List[Dict[str, str]]]:
        """
        Adaptively expand a set of candidate tables to ensure relational connectivity:
        - If tables are disconnected, finds shortest bridging paths
        - Returns (expanded_table_list, join_conditions)
        """
        if not initial_tables:
            return [], []

        valid_initial = [t for t in initial_tables if t in self.tables]
        if not valid_initial:
            return [], []

        if len(valid_initial) == 1:
            return valid_initial, []

        connected_tables: Set[str] = set()
        # Find paths between consecutive initial tables
        root = valid_initial[0]
        connected_tables.add(root)

        for other in valid_initial[1:]:
            path = self.find_shortest_path(root, other)
            if path:
                connected_tables.update(path)
            else:
                connected_tables.add(other)

        # Collect all active join edges between connected tables
        active_joins = []
        seen_edges = set()
        for t1 in connected_tables:
            for t2 in connected_tables:
                if t1 < t2 and t2 in self.adjacency.get(t1, {}):
                    for edge in self.adjacency[t1][t2]:
                        edge_id = f"{edge['source_table']}.{edge['source_col']}={edge['target_table']}.{edge['target_col']}"
                        if edge_id not in seen_edges:
                            seen_edges.add(edge_id)
                            active_joins.append(edge)

        # Preserve ordering: initial tables first, then bridge tables
        bridges = [t for t in connected_tables if t not in valid_initial]
        ordered_tables = valid_initial + sorted(bridges)
        return ordered_tables, active_joins


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent.parent
    meta_file = base / "data" / "reports" / "schema_metadata.json"
    graph = SchemaRelationshipGraph(meta_file)
    
    # Test path from customers to products
    path = graph.find_shortest_path("customers", "products")
    print("Path customers -> products:", path)

    # Test expansion
    expanded, joins = graph.expand_candidates(["customers", "products"])
    print("Expanded tables:", expanded)
    print("Joins needed:", joins)
