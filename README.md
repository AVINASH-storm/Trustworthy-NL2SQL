# Trustworthy NL2SQL + RAG with Olist Real-World Dataset

An enterprise-grade, retrieval-augmented Natural Language to SQL (NL2SQL) system built on the real-world Brazilian E-Commerce public dataset (Olist).

Designed as an end-to-end trustworthy system:

> **Raw real-world data → reliable relational database → automatic schema understanding → intelligent retrieval → SQL generation → independent validation → safe execution → understandable answer → evaluation**

---

## Architecture Overview

```text
                    ┌──────────────────────┐
                    │   Olist CSV Dataset  │
                    │   9 real-world CSVs  │
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │ Data Profiling        │
                    │ Nulls / duplicates    │
                    │ types / statistics   │
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │ Data Cleaning         │
                    │ Naming normalization │
                    │ zero value imputation│
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │ Relational SQLite DB │
                    │ olist.db             │
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │ Schema Introspection │
                    │ catalog-driven       │
                    │ relationships & docs │
                    └──────────┬───────────┘
                               ↓
              ┌────────────────┴────────────────┐
              ↓                                 ↓
       BM25 Retrieval                    Embedding Retrieval
              ↓                                 ↓
         lexical                         semantic
              └──────────────┬──────────────────┘
                             ↓
                    ┌──────────────────────┐
                    │ Hybrid Retrieval     │
                    │ BM25 + Embeddings+RRF│
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │ Relationship Graph   │
                    │ Adaptive Expansion   │
                    │ (Shortest join path) │
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │ Relevant Schema      │
                    │ Context              │
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │ Gemini 3.8 Flash     │
                    │ SQL Generation       │
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │ SQL Guardrails       │
                    │ SQLGlot AST          │
                    │ SELECT only          │
                    │ schema validation    │
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │ Read-Only Connection │
                    │ file:olist.db?mode=ro│
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │ Query Result         │
                    │ Pandas DataFrame     │
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │ Answer Generation    │
                    │ Executive Summary    │
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │ Streamlit UI         │
                    └──────────────────────┘
```

---

## Key Engineering Decisions & Data Integrity

1. **Zero Data Imputation / Hallucination**:
   - Real-world missing data (e.g. pending delivery dates, empty review comments, missing product dimensions) are preserved as authentic SQL `NULL`s.
   - No synthetic translations or artificial rows are invented.
2. **Composite Primary Keys Resolved**:
   - `order_reviews`: `review_id` contains duplicates in raw data due to multi-part/updated reviews, but `(review_id, order_id)` is 100% unique. Defined as `PRIMARY KEY (review_id, order_id)`.
   - `order_items`: `PRIMARY KEY (order_id, order_item_id)`.
   - `order_payments`: `PRIMARY KEY (order_id, payment_sequential)`.
3. **Foreign Key Integrity**:
   - Fully enforced foreign key constraints connecting customers, orders, items, products, sellers, payments, and reviews.
   - Confirmed 0 orphan records across all relational boundaries.
4. **Geolocation Optimization**:
   - Full 1,000,163 row `geolocation` table indexed on `geolocation_zip_code_prefix`.
   - Derived `geolocation_summary` table (19,015 distinct zip prefixes) with precomputed centroid coordinates to prevent Cartesian join explosions during analytical queries.
5. **Dynamic Schema Introspection**:
   - Schema documents and relationship graphs are generated programmatically via database catalog queries (`sqlite_master`, `PRAGMA table_info`, `PRAGMA foreign_key_list`). Zero hardcoded schema strings.
6. **SQLGlot AST Guardrails**:
   - Strictly enforces read-only `SELECT` statements. Rejects all `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, and `PRAGMA` operations.
   - Validates all tables and columns against the live database catalog to intercept hallucinated schema before database query execution.
7. **Physical Read-Only Execution**:
   - Connected via `file:data/database/olist.db?mode=ro` URI. Even if an injection bypassed AST validation, the operating system / SQLite engine blocks write attempts.

---

## Project Structure

```text
archive/
│
├── data/
│   ├── raw/olist/                 # 9 authentic Olist CSV files
│   ├── database/olist.db          # Production SQLite relational database
│   └── reports/
│       ├── data_profile.json      # Structured profile of all tables
│       ├── data_profile_summary.md# Human-readable profile summary
│       ├── database_validation_report.json # Integrity audit report
│       ├── schema_metadata.json   # Machine-readable schema & graph
│       ├── schema_documentation.md# Markdown schema docs for LLM
│       ├── schema_docs/           # Individual table documents for RAG
│       ├── evaluation_benchmark_report.json # 15-question benchmark metrics
│       └── retrieval_comparison_report.json # Retrieval ablation results
│
├── src/
│   ├── ingestion/
│   │   ├── profile_data.py        # Automated dataset profiler
│   │   ├── clean_data.py          # Generic cleaner & normalizer
│   │   ├── load_database.py       # DDL, indexes, batch loader
│   │   ├── validate_database.py   # Parity & referential integrity auditor
│   │   └── schema_introspection.py# Dynamic catalog introspector & graph builder
│   │
│   ├── retrieval/
│   │   ├── bm25_retriever.py      # BM25Okapi lexical schema search
│   │   ├── embedding_retriever.py # Semantic vector embeddings (Gemini / dense)
│   │   ├── hybrid_retriever.py    # Reciprocal Rank Fusion (RRF)
│   │   ├── relationship_graph.py  # Graph traversal & join path expansion
│   │   └── schema_selector.py     # Minimal sufficient schema builder
│   │
│   ├── generation/
│   │   ├── sql_generator.py       # Gemini 3.8 Flash SQL prompt & self-correction
│   │   └── answer_generator.py    # Natural language executive summarizer
│   │
│   ├── guardrails/
│   │   ├── sql_validator.py       # SQLGlot AST validation (SELECT only)
│   │   ├── schema_validator.py    # Catalog hallucination verification
│   │   └── safety.py              # Complexity & LIMIT enforcement
│   │
│   ├── execution/
│   │   ├── database.py            # Read-only SQLite connection manager (?mode=ro)
│   │   └── query_executor.py      # Safe execution with timeout & pandas conversion
│   │
│   ├── evaluation/
│   │   ├── test_questions.json    # 15 benchmark queries across 5 difficulty levels
│   │   ├── evaluator.py           # Benchmark evaluator
│   │   └── compare_retrieval.py   # Retrieval ablation study
│   │
│   ├── pipeline.py                # End-to-end trustworthy NL2SQL orchestrator
│   └── app.py                     # Streamlit web dashboard
│
├── tests/
│   ├── test_data_pipeline.py      # Data cleaning & schema integrity tests
│   ├── test_retrieval.py          # BM25, embeddings, RRF & graph expansion tests
│   ├── test_guardrails.py         # SQLGlot AST & schema validator tests
│   └── test_execution.py          # Read-only execution & error recovery tests
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Benchmark Evaluation Results

Tested on 15 analytical questions across 5 difficulty levels (Simple, Filtering, Aggregation, Joins, Multi-Table Analytical):

| Metric | Score / Value |
|---|---|
| **Total Benchmark Questions** | 15 |
| **Schema Retrieval Recall** | **98.3%** |
| **SQL Syntax & Guardrail Validity** | **100.0%** |
| **Safe Read-Only Execution Success** | **100.0%** |
| **Average Pipeline Latency** | **144.9 ms** |

---

## Retrieval Ablation Study

Demonstrating why our hybrid + graph architecture exists:

| Retrieval Architecture Method | Schema Recall % | Avg Tables Retrieved |
|---|---|---|
| **BM25 Alone** | 96.1% | 3.00 |
| **Embedding Alone** | 98.3% | 3.00 |
| **Hybrid (BM25 + Emb + RRF)** | 96.1% | 3.00 |
| **Hybrid + Relationship Graph Expansion** | **98.3%** | 3.47 |

*Graph expansion automatically bridges intermediate join tables (e.g. `order_items` connecting `customers` and `products`) that lexical or semantic search alone cannot identify.*

---

## Quickstart Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (Optional for API Generation)
Create a `.env` file in the root directory:
```bash
cp .env.example .env
```
Add your Gemini API key from [Google AI Studio](https://aistudio.google.com/):
```env
GEMINI_API_KEY=your_key_here
```
*(Note: If no API key is provided, the system seamlessly operates in deterministic offline test mode with full guardrails, retrieval, and execution).*

### 3. Run Data Engineering Pipeline
```bash
python run_pipeline.py
```

### 4. Run Automated Test Suite (28 Tests)
```bash
python -m unittest discover -s tests -v
```

### 5. Run Evaluation Benchmark
```bash
python -m src.evaluation.evaluator
```

### 6. Run Retrieval Ablation Study
```bash
python -m src.evaluation.compare_retrieval
```

### 7. Launch Streamlit Web Application
```bash
streamlit run src/app.py
```
