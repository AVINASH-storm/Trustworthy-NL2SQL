"""
Unit Tests for Retrieval, RRF, and Schema Relationship Graph.
"""

from pathlib import Path
import unittest

from src.retrieval.bm25_retriever import BM25SchemaRetriever
from src.retrieval.embedding_retriever import EmbeddingSchemaRetriever
from src.retrieval.hybrid_retriever import HybridSchemaRetriever
from src.retrieval.relationship_graph import SchemaRelationshipGraph

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "data" / "reports" / "schema_docs"
META_PATH = PROJECT_ROOT / "data" / "reports" / "schema_metadata.json"


class TestRetrievalAndGraph(unittest.TestCase):
    """Test retrieval components and graph bridging."""

    @classmethod
    def setUpClass(cls):
        if not DOCS_DIR.exists() or not META_PATH.exists():
            raise unittest.SkipTest("Schema documents or metadata not found. Run pipeline first.")

    def test_bm25_retriever(self):
        retriever = BM25SchemaRetriever(DOCS_DIR)
        res = retriever.retrieve("Which sellers have the highest ratings?", top_k=3)
        self.assertGreater(len(res), 0)
        table_names = [r["table"] for r in res]
        self.assertTrue("sellers" in table_names or "order_reviews" in table_names)

    def test_embedding_retriever(self):
        retriever = EmbeddingSchemaRetriever(DOCS_DIR)
        res = retriever.retrieve("customer spending and purchase totals", top_k=3)
        self.assertGreater(len(res), 0)
        table_names = [r["table"] for r in res]
        self.assertTrue(any(t in table_names for t in ["customers", "orders", "order_payments", "order_items"]))

    def test_hybrid_rrf_retrieval(self):
        retriever = HybridSchemaRetriever(DOCS_DIR)
        res = retriever.retrieve("freight cost and delivery dates", top_k=4)
        table_names = [r["table"] for r in res]
        self.assertIn("order_items", table_names)
        # Verify RRF scores are non-zero and properly sorted
        scores = [r["rrf_score"] for r in res]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_relationship_graph_path_finding(self):
        graph = SchemaRelationshipGraph(META_PATH)
        path = graph.find_shortest_path("customers", "products")
        self.assertIsNotNone(path)
        # Expected path: customers -> orders -> order_items -> products
        self.assertEqual(path[0], "customers")
        self.assertEqual(path[-1], "products")
        self.assertIn("orders", path)
        self.assertIn("order_items", path)

    def test_relationship_graph_candidate_expansion(self):
        graph = SchemaRelationshipGraph(META_PATH)
        expanded, joins = graph.expand_candidates(["customers", "products"])
        self.assertIn("customers", expanded)
        self.assertIn("products", expanded)
        self.assertIn("orders", expanded)
        self.assertIn("order_items", expanded)
        self.assertGreater(len(joins), 0)


if __name__ == "__main__":
    unittest.main()
