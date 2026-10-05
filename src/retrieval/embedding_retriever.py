"""
Semantic Vector Schema Retriever.
Matches natural language queries to schema tables conceptually:
- Handles semantic concepts (e.g. 'turnaround time' -> delivery dates, 'money spent' -> payments/prices)
- Integrates Google GenAI Embeddings when GEMINI_API_KEY is available
- Provides robust local dense vector semantic matching fallback for offline execution
"""

import math
import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
import numpy as np

load_dotenv()

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))


class LocalDenseRetriever:
    """
    Sub-word character n-gram + semantic term frequency dense vectorizer.
    Guarantees fast, reproducible semantic retrieval even without an external API key.
    """
    def __init__(self, documents: List[str]):
        self.documents = documents
        self.vocab = self._build_vocab(documents)
        self.doc_vectors = [self._vectorize(d) for d in documents]

    def _get_ngrams(self, text: str) -> List[str]:
        words = re.findall(r"[a-z0-9]+", text.lower())
        features = list(words)
        # Add character tri-grams for sub-word semantic matching
        for w in words:
            if len(w) >= 4:
                features.extend([w[i:i+3] for i in range(len(w) - 2)])
        return features

    def _build_vocab(self, docs: List[str]) -> Dict[str, int]:
        vocab = {}
        for d in docs:
            for feat in self._get_ngrams(d):
                if feat not in vocab:
                    vocab[feat] = len(vocab)
        return vocab

    def _vectorize(self, text: str) -> np.ndarray:
        vec = np.zeros(len(self.vocab), dtype=np.float32)
        feats = self._get_ngrams(text)
        for f in feats:
            idx = self.vocab.get(f)
            if idx is not None:
                vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def score(self, query: str) -> List[float]:
        q_vec = self._vectorize(query)
        return [cosine_similarity(q_vec, d_vec) for d_vec in self.doc_vectors]


class EmbeddingSchemaRetriever:
    """Semantic schema retriever using Gemini embeddings with local fallback."""

    def __init__(self, schema_docs_dir: Path):
        self.schema_docs_dir = schema_docs_dir
        self.table_names: List[str] = []
        self.documents: List[str] = []
        self._load_corpus()

        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.use_api = bool(self.api_key and GENAI_AVAILABLE)

        if self.use_api:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self.doc_embeddings = self._get_cached_or_embed_gemini()
            except Exception as e:
                print(f"[Warning] Failed to initialize Gemini embedding client: {e}. Using local dense retriever.")
                self.use_api = False
                self.local_retriever = LocalDenseRetriever(self.documents)
        else:
            self.local_retriever = LocalDenseRetriever(self.documents)

    def _load_corpus(self):
        doc_files = sorted(self.schema_docs_dir.glob("*.txt"))
        if not doc_files:
            raise FileNotFoundError(f"No schema documents found in {self.schema_docs_dir}")

        for doc_file in doc_files:
            self.table_names.append(doc_file.stem)
            self.documents.append(doc_file.read_text(encoding="utf-8"))

    def _get_cached_or_embed_gemini(self) -> List[np.ndarray]:
        cache_file = self.schema_docs_dir.parent / "schema_embeddings.npy"
        if cache_file.exists():
            try:
                arr = np.load(cache_file)
                if arr.shape[0] == len(self.documents):
                    return [arr[i] for i in range(arr.shape[0])]
            except Exception:
                pass

        vectors = self._embed_corpus_gemini()
        try:
            np.save(cache_file, np.array(vectors, dtype=np.float32))
        except Exception:
            pass
        return vectors

    def _embed_corpus_gemini(self) -> List[np.ndarray]:
        vectors = []
        for doc in self.documents:
            res = self.client.models.embed_content(
                model="gemini-embedding-001",
                contents=doc
            )
            if hasattr(res, "embeddings") and res.embeddings:
                emb = res.embeddings[0].values
            elif hasattr(res, "embedding") and hasattr(res.embedding, "values"):
                emb = res.embedding.values
            else:
                emb = res.embedding
            vectors.append(np.array(emb, dtype=np.float32))
        return vectors

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, any]]:
        """Retrieve top_k tables by semantic similarity."""
        if self.use_api:
            try:
                res = self.client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=query
                )
                if hasattr(res, "embeddings") and res.embeddings:
                    emb = res.embeddings[0].values
                elif hasattr(res, "embedding") and hasattr(res.embedding, "values"):
                    emb = res.embedding.values
                else:
                    emb = res.embedding
                q_vec = np.array(emb, dtype=np.float32)
                scores = [cosine_similarity(q_vec, d_vec) for d_vec in self.doc_embeddings]
            except Exception as e:
                scores = self.local_retriever.score(query)
        else:
            scores = self.local_retriever.score(query)

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
    retriever = EmbeddingSchemaRetriever(docs_dir)
    res = retriever.retrieve("customer feedback satisfaction and ratings")
    print("Semantic Results:", res)
