"""
Hybrid Schema Retriever using Reciprocal Rank Fusion (RRF).
Merges lexical BM25 ranking and semantic vector ranking into a unified score:
RRF(d) = sum(1 / (k + rank_i(d)))
Standard constant k = 60.
"""

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from src.retrieval.bm25_retriever import BM25SchemaRetriever
from src.retrieval.embedding_retriever import EmbeddingSchemaRetriever


class HybridSchemaRetriever:
    """Combines BM25 and Semantic Embeddings using Reciprocal Rank Fusion."""

    def __init__(self, schema_docs_dir: Path, rrf_k: int = 60):
        self.schema_docs_dir = schema_docs_dir
        self.rrf_k = rrf_k
        self.bm25_retriever = BM25SchemaRetriever(schema_docs_dir)
        self.embedding_retriever = EmbeddingSchemaRetriever(schema_docs_dir)

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, any]]:
        """
        Execute hybrid retrieval for a query using RRF.
        Returns sorted list of tables with combined RRF scores and individual ranks.
        """
        # Retrieve from both systems
        bm25_results = self.bm25_retriever.retrieve(query, top_k=top_k * 2)
        emb_results = self.embedding_retriever.retrieve(query, top_k=top_k * 2)

        bm25_ranks = {item["table"]: item["rank"] for item in bm25_results}
        emb_ranks = {item["table"]: item["rank"] for item in emb_results}

        all_tables = set(bm25_ranks.keys()).union(set(emb_ranks.keys()))
        rrf_scores = {}

        for table in all_tables:
            score = 0.0
            if table in bm25_ranks:
                score += 1.0 / (self.rrf_k + bm25_ranks[table])
            else:
                # Penalty rank
                score += 1.0 / (self.rrf_k + 100)

            if table in emb_ranks:
                score += 1.0 / (self.rrf_k + emb_ranks[table])
            else:
                score += 1.0 / (self.rrf_k + 100)

            rrf_scores[table] = score

        ranked_tables = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for rank, (table, score) in enumerate(ranked_tables[:top_k], start=1):
            results.append({
                "table": table,
                "rrf_score": round(score, 6),
                "bm25_rank": bm25_ranks.get(table, None),
                "embedding_rank": emb_ranks.get(table, None),
                "final_rank": rank,
            })
        return results


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent.parent
    docs_dir = base / "data" / "reports" / "schema_docs"
    retriever = HybridSchemaRetriever(docs_dir)
    res = retriever.retrieve("Which sellers generated the highest revenue?")
    print("Hybrid RRF Results:")
    for r in res:
        print(f"  Rank {r['final_rank']}: {r['table']} (RRF: {r['rrf_score']}, BM25: {r['bm25_rank']}, Emb: {r['embedding_rank']})")
