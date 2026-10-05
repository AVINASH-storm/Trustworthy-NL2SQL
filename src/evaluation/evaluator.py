"""
NL2SQL Benchmark Evaluator.
Executes standard test questions across 5 difficulty levels:
- Schema Retrieval Recall %
- SQL Validity % (SQLGlot AST + Schema)
- Safe Read-Only Execution Success %
- Latency profiling across all stages
- Writes structured evaluation reports
"""

import json
from pathlib import Path
import time
from typing import Any, Dict, List

from tabulate import tabulate

from src.pipeline import TrustworthyNL2SQLPipeline


def run_benchmark(
    pipeline: TrustworthyNL2SQLPipeline,
    questions_path: Path,
    output_report_path: Path = None,
) -> Dict[str, Any]:
    """Execute evaluation benchmark and compute performance metrics."""
    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print("=" * 75)
    print("      RUNNING TRUSTWORTHY NL2SQL + RAG EVALUATION BENCHMARK      ")
    print("=" * 75)
    print(f"Total Test Questions: {len(questions)}")

    results = []
    total_recall = 0.0
    valid_sql_count = 0
    exec_success_count = 0
    total_latencies = []

    for q in questions:
        q_id = q["id"]
        level = q["level"]
        difficulty = q["difficulty"]
        query_text = q["question"]
        expected_tables = set(q["expected_tables"])

        print(f"\n[Test #{q_id} | Level {level} - {difficulty}]")
        print(f"  Question: \"{query_text}\"")

        res = pipeline.process_query(query_text)

        # 1. Schema Recall
        retrieved_set = set(res["selected_tables"])
        matched_tables = expected_tables.intersection(retrieved_set)
        recall = len(matched_tables) / len(expected_tables) if expected_tables else 1.0
        total_recall += recall

        # 2. SQL Validity & Execution
        is_valid = res["attempts"] > 0 and res["attempt_logs"][-1]["status"] in ("SUCCESS", "EXECUTION_ERROR")
        is_exec_success = res["success"]

        if is_valid:
            valid_sql_count += 1
        if is_exec_success:
            exec_success_count += 1

        total_ms = res["latencies"].get("total_pipeline_ms", 0.0)
        total_latencies.append(total_ms)

        print(f"  Schema Recall:  {recall * 100:.1f}% (Found: {sorted(list(retrieved_set))})")
        print(f"  Execution:      {'PASSED' if is_exec_success else 'FAILED'} ({res['row_count']} rows returned)")
        print(f"  Latency:        {total_ms:.1f} ms")

        results.append({
            "id": q_id,
            "level": level,
            "difficulty": difficulty,
            "question": query_text,
            "expected_tables": list(expected_tables),
            "retrieved_tables": list(retrieved_set),
            "schema_recall": recall,
            "sql_valid": is_valid,
            "exec_success": is_exec_success,
            "rows_returned": res["row_count"],
            "generated_sql": res["sql"],
            "latencies": res["latencies"]
        })

    # Summary Metrics
    num_q = len(questions)
    avg_recall = (total_recall / num_q) * 100 if num_q else 0.0
    sql_validity_pct = (valid_sql_count / num_q) * 100 if num_q else 0.0
    exec_accuracy_pct = (exec_success_count / num_q) * 100 if num_q else 0.0
    avg_latency = sum(total_latencies) / num_q if num_q else 0.0

    summary_table = [
        ["Metric", "Score / Value"],
        ["Total Benchmark Questions", num_q],
        ["Schema Retrieval Recall", f"{avg_recall:.1f}%"],
        ["SQL Syntax & Guardrail Validity", f"{sql_validity_pct:.1f}%"],
        ["Safe Read-Only Execution Success", f"{exec_accuracy_pct:.1f}%"],
        ["Average Pipeline Latency", f"{avg_latency:.1f} ms"],
    ]

    print("\n" + "=" * 75)
    print("                     BENCHMARK EVALUATION SUMMARY                     ")
    print("=" * 75)
    print(tabulate(summary_table, headers="firstrow", tablefmt="github"))

    final_report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_questions": num_q,
        "metrics": {
            "schema_recall_pct": round(avg_recall, 2),
            "sql_validity_pct": round(sql_validity_pct, 2),
            "execution_accuracy_pct": round(exec_accuracy_pct, 2),
            "avg_latency_ms": round(avg_latency, 2),
        },
        "results": results,
    }

    if output_report_path:
        output_report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_report_path, "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2)
        print(f"\nDetailed evaluation benchmark report saved to: {output_report_path}")

    return final_report


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent.parent
    db_file = base / "data" / "database" / "olist.db"
    docs_dir = base / "data" / "reports" / "schema_docs"
    meta_file = base / "data" / "reports" / "schema_metadata.json"
    q_file = base / "src" / "evaluation" / "test_questions.json"
    rep_file = base / "data" / "reports" / "evaluation_benchmark_report.json"

    pipe = TrustworthyNL2SQLPipeline(db_file, docs_dir, meta_file)
    run_benchmark(pipe, q_file, rep_file)
