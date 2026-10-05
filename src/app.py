"""
Streamlit Web Application for Trustworthy NL2SQL + RAG System.
Features:
- Natural Language Question Input & Benchmark Question Dropdown
- Real-time Hybrid Schema Retrieval & Graph Bridge Visualization
- SQLGlot Guardrail & Schema Verification Badges
- Read-Only SQL Execution & Interactive Data Table
- Executive Business Answer Summary
- Latency & Telemetry Profiler
"""

import os
from pathlib import Path
import sys
import time

from dotenv import load_dotenv
import pandas as pd
import streamlit as st

load_dotenv()

# Setup python path so src modules resolve
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import TrustworthyNL2SQLPipeline

st.set_page_config(
    page_title="Trustworthy NL2SQL | Olist E-Commerce",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for executive look
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-badge {
        display: inline-block;
        background-color: #EEF2FF;
        color: #3730A3;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 0.5rem;
    }
    .guardrail-pass {
        color: #065F46;
        background-color: #D1FAE5;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_pipeline():
    db_file = PROJECT_ROOT / "data" / "database" / "olist.db"
    docs_dir = PROJECT_ROOT / "data" / "reports" / "schema_docs"
    meta_file = PROJECT_ROOT / "data" / "reports" / "schema_metadata.json"

    if not db_file.exists() or not meta_file.exists() or not docs_dir.exists():
        return None

    try:
        return TrustworthyNL2SQLPipeline(db_file, docs_dir, meta_file)
    except FileNotFoundError:
        return None


pipeline = get_pipeline()
PIPELINE_READY = pipeline is not None

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://raw.githubusercontent.com/google/material-design-icons/master/png/action/lock/materialicons/48dp/2x/baseline_lock_black_48dp.png", width=48)
    st.title("Trust & Guardrails")
    st.markdown("""
    **Defense-in-Depth Architecture:**
    - 🔍 **Hybrid Retrieval**: BM25 + Embeddings + RRF
    - 🕸️ **Graph Expansion**: Auto-bridges FK join paths
    - 🛡️ **SQLGlot AST**: Enforces read-only SELECT
    - 🚫 **Schema Validator**: Catches column hallucinations
    - 🔒 **Read-Only SQLite**: Physical `mode=ro` URI
    """)

    st.divider()
    st.subheader("Benchmark Questions")
    benchmark_options = [
        "Select a benchmark question...",
        "Which sellers generated the highest revenue?",
        "Which product categories generated the most revenue in 2018?",
        "How many orders were delivered in 2018?",
        "How many customers are there?",
        "What is the average delivery time for customers in São Paulo?",
    ]
    selected_benchmark = st.selectbox("Sample Queries across Difficulty Levels", benchmark_options)

    st.divider()
    st.subheader("Database Catalog Stats")
    if PIPELINE_READY:
        st.caption(f"📁 `{pipeline.db_path.name}`")
        st.caption("🔒 Connection: **Read-Only (`mode=ro`)**")
        st.caption(f"📊 Tables: **{len(pipeline.schema_validator.catalog_tables)}**")
        st.caption("⚡ Indexes: B-tree on all Foreign Keys")
    else:
        st.warning("Database and schema artifacts are missing. Run `python run_pipeline.py` after adding the Olist CSV data.")


# --- MAIN PAGE ---
st.markdown('<div class="main-header">🛡️ Trustworthy NL2SQL + RAG System</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Autonomous, schema-aware relational text-to-SQL with AST guardrails, '
    'relationship graph expansion, and safe read-only execution on the Olist e-commerce dataset.</div>',
    unsafe_allow_html=True
)

default_text = ""
if selected_benchmark != "Select a benchmark question...":
    default_text = selected_benchmark

if not PIPELINE_READY:
    st.warning(
        "The Olist database and schema artifacts are not present in this checkout. "
        "The app will run in a degraded mode until you add the dataset and execute `python run_pipeline.py`."
    )

query_input = st.text_input(
    "Ask a question in natural language:",
    value=default_text,
    placeholder="e.g. Which product categories generated the highest revenue in 2018?",
)

col_btn, col_info = st.columns([1, 4])
with col_btn:
    analyze_clicked = st.button("🚀 Analyze Query", type="primary", use_container_width=True)

if analyze_clicked and query_input and PIPELINE_READY:
    with st.spinner("Processing through Trustworthy NL2SQL Pipeline..."):
        result = pipeline.process_query(query_input)

    # 1. Executive Answer
    st.subheader("💬 Executive Summary")
    if result["success"]:
        st.success(result["answer"])
    else:
        st.error(result["answer"])

    # 2. Key Metrics Row
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric("Query Status", "Passed Guardrails ✅" if result["success"] else "Blocked ❌")
    with m_col2:
        st.metric("Rows Returned", f"{result['row_count']:,}")
    with m_col3:
        st.metric("Tables Utilized", f"{len(result['selected_tables'])}")
    with m_col4:
        st.metric("Total Latency", f"{result['latencies'].get('total_pipeline_ms', 0):.1f} ms")

    # Tabs for detailed transparency
    tab_data, tab_sql, tab_schema, tab_telemetry = st.tabs([
        "📊 Query Result Data",
        "💻 Validated SQL",
        "🕸️ Retrieved Schema & Graph",
        "⚡ Observability & Guardrails"
    ])

    with tab_data:
        if result["success"] and not result["data"].empty:
            st.dataframe(result["data"], use_container_width=True)
        elif result["success"]:
            st.info("Query returned 0 rows.")
        else:
            st.warning("No data returned due to validation or execution stoppage.")

    with tab_sql:
        st.caption("Validated against SQLite dialect via SQLGlot AST parser:")
        st.code(result["sql"], language="sql")

    with tab_schema:
        st.markdown("#### Schema Resolution")
        st.markdown(f"**Directly Retrieved Tables**: `{'`, `'.join(result['selected_tables'])}`")
        if result["bridged_tables"]:
            st.markdown(f"**Relationship Graph Bridged Tables**: `{'`, `'.join(result['bridged_tables'])}`")
        else:
            st.markdown("*No additional bridging tables required; candidate set was already connected.*")

        st.markdown("#### Active Join Constraints")
        if result["active_joins"]:
            for j in result["active_joins"]:
                st.code(f"{j['source_table']}.{j['source_col']} = {j['target_table']}.{j['target_col']}", language="sql")
        else:
            st.caption("Single table query — no joins needed.")

    with tab_telemetry:
        st.markdown("#### Performance Latency Breakdown")
        lat = result["latencies"]
        lat_df = pd.DataFrame([
            {"Stage": "1. Hybrid Retrieval & Graph Expansion", "Latency (ms)": lat.get("retrieval_ms", 0)},
            {"Stage": "2. SQL Generation & Guardrail Validation", "Latency (ms)": lat.get("generation_ms", 0)},
            {"Stage": "3. Read-Only Database Execution", "Latency (ms)": lat.get("execution_ms", 0)},
            {"Stage": "4. Natural Language Synthesis", "Latency (ms)": lat.get("answer_synthesis_ms", 0)},
            {"Stage": "TOTAL End-to-End Pipeline", "Latency (ms)": lat.get("total_pipeline_ms", 0)},
        ])
        st.table(lat_df)

        st.markdown("#### Guardrail Audit Trail")
        for log in result.get("attempt_logs", []):
            st.json(log)
