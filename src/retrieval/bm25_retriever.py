"""
BM25 Lexical Schema Retriever.
Scores database table documents based on exact and morphological keyword matches:
- Expands snake_case tokens (e.g., freight_value -> freight, value, freight_value)
- Computes BM25Okapi relevance scores against table metadata and column documents
"""

import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi


def tokenize_schema_text(text: str) -> List[str]:
    """
    Tokenize schema text with snake_case and alphanumeric decomposition:
    e.g. 'order_purchase_timestamp' -> ['order', 'purchase', 'timestamp', 'order_purchase_timestamp']
    """
    raw_tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    expanded = []
    for token in raw_tokens:
        expanded.append(token)
        if "_" in token:
            subparts = [p for p in token.split("_") if p]
            expanded.extend(subparts)
    return expanded


class BM25SchemaRetriever:
    """Lexical schema retriever powered by BM25Okapi."""

    def __init__(self, schema_docs_dir: Path):
        self.schema_docs_dir = schema_docs_dir
        self.table_names: List[str] = []
        self.documents: List[str] = []
        self.tokenized_corpus: List[List[str]] = []
        self._load_corpus()
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def _load_corpus(self):
        doc_files = sorted(self.schema_docs_dir.glob("*.txt"))
        if not doc_files:
            raise FileNotFoundError(f"No schema documents found in {self.schema_docs_dir}")

        for doc_file in doc_files:
            table_name = doc_file.stem
            content = doc_file.read_text(encoding="utf-8")
            self.table_names.append(table_name)
            self.documents.append(content)
            self.tokenized_corpus.append(tokenize_schema_text(content))

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, any]]:
        """
        Retrieve top_k most relevant tables for a user query.
        Returns a list of dicts: [{'table': str, 'score': float, 'rank': int}]
        """
        query_tokens = tokenize_schema_text(query)
        if not query_tokens:
            return [{"table": t, "score": 0.0, "rank": idx + 1} for idx, t in enumerate(self.table_names[:top_k])]

        scores = self.bm25.get_scores(query_tokens)
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        results = []
        for rank, idx in enumerate(ranked_indices[:top_k], start=1):
            results.append({
                "table": self.table_names[idx],
                "score": float(scores[idx]),
                "rank": rank
            })
        return results


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent.parent
    docs_dir = base / "data" / "reports" / "schema_docs"
    retriever = BM25SchemaRetriever(docs_dir)
    res = retriever.retrieve("Which sellers had the highest revenue and review score?")
    print("BM25 Results:", res)
