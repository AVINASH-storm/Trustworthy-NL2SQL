"""
Trustworthy NL2SQL End-to-End Orchestrator Pipeline.
Coordinates:
1. Adaptive Hybrid Retrieval & Relationship Graph Expansion
2. Gemini SQL Generation with Self-Correction Feedback Loop
3. SQLGlot AST Validation (SELECT-only check, destructive operations blocked)
4. Database Catalog Schema Validation (Hallucination detection)
5. Physical Read-Only Execution against SQLite (file:olist.db?mode=ro)
6. Natural-Language Answer Synthesis
7. Latency and Execution Observability
"""

from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import pandas as pd

load_dotenv()

from src.execution.query_executor import SafeQueryExecutor
from src.generation.answer_generator import AnswerGenerator
from src.generation.sql_generator import GeminiSQLGenerator
from src.guardrails.safety import SafetyPolicy
from src.guardrails.schema_validator import SchemaValidator
from src.guardrails.sql_validator import SQLValidator
from src.retrieval.schema_selector import AdaptiveSchemaSelector


class TrustworthyNL2SQLPipeline:
    """Production-grade trustworthy NL2SQL pipeline with defense-in-depth guardrails."""

    def __init__(
        self,
        db_path: Path,
        schema_docs_dir: Path,
        metadata_path: Path,
        max_correction_attempts: int = 2,
    ):
        self.db_path = db_path
        self.schema_docs_dir = schema_docs_dir
        self.metadata_path = metadata_path
        self.max_attempts = max_correction_attempts

        # Subsystems
        self.schema_selector = AdaptiveSchemaSelector(schema_docs_dir, metadata_path)
        self.sql_generator = GeminiSQLGenerator()
        self.sql_validator = SQLValidator(dialect="sqlite")
        self.schema_validator = SchemaValidator(metadata_path)
        self.safety_policy = SafetyPolicy(default_limit=100)
        self.executor = SafeQueryExecutor(db_path)
        self.answer_generator = AnswerGenerator()

    def process_query(self, question: str) -> Dict[str, Any]:
        """
        Execute the complete trustworthy NL2SQL flow for a user question.
        """
        t_start = time.time()
        latencies = {}

        # 1. Retrieval & Graph Expansion
        t0 = time.time()
        retrieval_res = self.schema_selector.select_schema(question)
        latencies["retrieval_ms"] = round((time.time() - t0) * 1000, 2)

        schema_context = retrieval_res["schema_context_text"]
        selected_tables = retrieval_res["selected_tables"]
        bridged_tables = retrieval_res["bridged_tables"]

        error_feedback: Optional[str] = None
        final_sql: str = ""
        validated_sql: str = ""
        exec_result: Optional[Dict[str, Any]] = None
        attempt_logs = []
        is_success = False

        # 2. Self-Correction Generation & Validation Loop
        t_gen_start = time.time()
        for attempt in range(1, self.max_attempts + 1):
            attempt_info = {"attempt": attempt}

            # Generate SQL
            generated_sql = self.sql_generator.generate_sql(
                question, schema_context, error_feedback=error_feedback
            )
            attempt_info["generated_sql"] = generated_sql
            final_sql = generated_sql

            # Guardrail 1: SQLGlot AST Syntax & Read-Only Check
            t_val = time.time()
            ast_res = self.sql_validator.validate(generated_sql)
            latencies[f"validation_attempt_{attempt}_ms"] = round((time.time() - t_val) * 1000, 2)

            if not ast_res["is_valid"]:
                error_feedback = ast_res["error"]
                attempt_info["status"] = "AST_VALIDATION_FAILED"
                attempt_info["error"] = error_feedback
                attempt_logs.append(attempt_info)
                continue

            # Guardrail 2: Catalog Schema Hallucination Check
            schema_res = self.schema_validator.validate_schema(
                ast_res["tables"],
                ast_res["columns"],
                table_aliases=ast_res.get("table_aliases")
            )
            if not schema_res["is_valid"]:
                error_feedback = schema_res["error"]
                attempt_info["status"] = "SCHEMA_VALIDATION_FAILED"
                attempt_info["error"] = error_feedback
                attempt_logs.append(attempt_info)
                continue

            # Guardrail 3: Safety Policy (Limits, No statement chaining)
            safety_res = self.safety_policy.apply_safety_guardrails(
                ast_res["ast"], generated_sql
            )
            if not safety_res["safe"]:
                error_feedback = safety_res["error"]
                attempt_info["status"] = "SAFETY_VIOLATION"
                attempt_info["error"] = error_feedback
                attempt_logs.append(attempt_info)
                continue

            safe_sql = safety_res["safe_sql"]
            validated_sql = safe_sql

            # 3. Read-Only Database Execution
            t_exec = time.time()
            exec_result = self.executor.execute(safe_sql)
            latencies["execution_ms"] = exec_result["latency_ms"]

            if not exec_result["success"]:
                error_feedback = exec_result["error"]
                attempt_info["status"] = "EXECUTION_ERROR"
                attempt_info["error"] = error_feedback
                attempt_logs.append(attempt_info)
                continue

            # Execution succeeded
            attempt_info["status"] = "SUCCESS"
            attempt_logs.append(attempt_info)
            is_success = True
            break

        latencies["generation_ms"] = round((time.time() - t_gen_start) * 1000, 2)

        # 4. Natural Language Answer Generation
        t_ans = time.time()
        if is_success and exec_result:
            answer = self.answer_generator.generate_answer(
                question, validated_sql, exec_result["data"]
            )
            data_df = exec_result["data"]
            row_count = exec_result["row_count"]
        else:
            answer = f"Query could not be completed reliably after {len(attempt_logs)} attempts. Error: {error_feedback}"
            data_df = pd.DataFrame()
            row_count = 0
        latencies["answer_synthesis_ms"] = round((time.time() - t_ans) * 1000, 2)

        latencies["total_pipeline_ms"] = round((time.time() - t_start) * 1000, 2)

        return {
            "question": question,
            "success": is_success,
            "answer": answer,
            "sql": validated_sql or final_sql,
            "data": data_df,
            "row_count": row_count,
            "selected_tables": selected_tables,
            "bridged_tables": bridged_tables,
            "active_joins": retrieval_res["active_joins"],
            "attempts": len(attempt_logs),
            "attempt_logs": attempt_logs,
            "latencies": latencies,
            "error": error_feedback if not is_success else None,
        }


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    db_file = base / "data" / "database" / "olist.db"
    docs_dir = base / "data" / "reports" / "schema_docs"
    meta_file = base / "data" / "reports" / "schema_metadata.json"

    pipe = TrustworthyNL2SQLPipeline(db_file, docs_dir, meta_file)

    test_q = "Which sellers generated the highest revenue?"
    res = pipe.process_query(test_q)
    print("Answer:\n", res["answer"])
    print("\nSQL:\n", res["sql"])
    print("\nData Head:\n", res["data"].head(3))
    print("\nLatencies:\n", res["latencies"])
