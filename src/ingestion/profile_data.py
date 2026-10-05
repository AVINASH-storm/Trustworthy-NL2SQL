"""
Data Profiling Module for Real-World Relational Datasets.
Analyzes raw CSV files programmatically:
- Row/column dimensions
- Null & uniqueness statistics
- Generic data type inference
- Single & composite candidate Primary Key detection
- Potential Foreign Key overlap detection
- Generates JSON and Markdown profile reports

Guarantees: Zero data imputation or synthesis. Real data is profiled as-is.
"""

from collections import Counter
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple


def infer_value_type(val: str) -> str:
    """Infer the primitive type of a string value."""
    if val is None or val == "":
        return "NULL"
    # Integer check
    if re.fullmatch(r"[-+]?\d+", val):
        return "INTEGER"
    # Float check
    if re.fullmatch(r"[-+]?\d*\.\d+", val):
        return "REAL"
    # Datetime check (ISO formats, common date formats)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            datetime.strptime(val, fmt)
            return "DATETIME"
        except ValueError:
            pass
    # Boolean check
    if val.lower() in ("true", "false", "t", "f"):
        return "BOOLEAN"
    return "TEXT"


def profile_csv_file(file_path: Path) -> Dict[str, Any]:
    """Profile a single CSV file comprehensively."""
    table_name = file_path.stem.replace("olist_", "").replace("_dataset", "")
    
    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        try:
            raw_headers = next(reader)
        except StopIteration:
            return {"table_name": table_name, "error": "Empty file"}
        
        # Clean header names (strip BOM, whitespace)
        headers = [h.strip().lstrip("\ufeff") for h in raw_headers]
        num_cols = len(headers)
        
        row_count = 0
        null_counts = [0] * num_cols
        unique_sets: List[Set[str]] = [set() for _ in range(num_cols)]
        type_counters: List[Counter] = [Counter() for _ in range(num_cols)]
        samples: List[List[str]] = [[] for _ in range(num_cols)]
        
        # Single-pass row aggregation
        raw_rows = []
        for row in reader:
            row_count += 1
            raw_rows.append(row)
            for i in range(num_cols):
                val = row[i].strip() if i < len(row) else ""
                if val == "":
                    null_counts[i] += 1
                    type_counters[i]["NULL"] += 1
                else:
                    unique_sets[i].add(val)
                    val_type = infer_value_type(val)
                    type_counters[i][val_type] += 1
                    if len(samples[i]) < 3 and val not in samples[i]:
                        samples[i].append(val)
    
    columns_profile = []
    single_pks = []
    
    for i, col_name in enumerate(headers):
        unique_count = len(unique_sets[i])
        null_count = null_counts[i]
        null_pct = round((null_count / row_count * 100), 2) if row_count > 0 else 0.0
        
        # Determine predominant non-null type
        non_null_types = {k: v for k, v in type_counters[i].items() if k != "NULL"}
        if non_null_types:
            predominant_type = max(non_null_types.items(), key=lambda x: x[1])[0]
        else:
            predominant_type = "TEXT"
        
        is_candidate_pk = (null_count == 0 and unique_count == row_count and row_count > 0)
        if is_candidate_pk:
            single_pks.append(col_name)
        
        columns_profile.append({
            "name": col_name,
            "inferred_type": predominant_type,
            "null_count": null_count,
            "null_percentage": null_pct,
            "unique_count": unique_count,
            "is_candidate_pk": is_candidate_pk,
            "sample_values": samples[i]
        })
    
    # If no single PK found and row count > 0, check candidate 2-column composite keys
    composite_pks = []
    if not single_pks and row_count > 0 and num_cols > 1:
        # Check pairs of columns that each have 0 nulls
        zero_null_indices = [idx for idx, c in enumerate(null_counts) if c == 0]
        for idx1 in range(len(zero_null_indices)):
            for idx2 in range(idx1 + 1, len(zero_null_indices)):
                i1, i2 = zero_null_indices[idx1], zero_null_indices[idx2]
                composite_set = set()
                for row in raw_rows:
                    v1 = row[i1].strip() if i1 < len(row) else ""
                    v2 = row[i2].strip() if i2 < len(row) else ""
                    composite_set.add((v1, v2))
                if len(composite_set) == row_count:
                    composite_pks.append([headers[i1], headers[i2]])
                    if len(composite_pks) >= 3:
                        break
            if composite_pks:
                break

    return {
        "file_name": file_path.name,
        "table_name": table_name,
        "row_count": row_count,
        "column_count": num_cols,
        "candidate_primary_keys": single_pks or (composite_pks[0] if composite_pks else []),
        "is_composite_pk": bool(not single_pks and composite_pks),
        "columns": columns_profile
    }


def profile_all_csvs(data_dir: Path, output_report_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Scan and profile all CSV files in the data directory."""
    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    
    profiles = {}
    print(f"Profiling {len(csv_files)} CSV files in {data_dir}...")
    
    for f in csv_files:
        print(f"  -> Profiling {f.name}...")
        p = profile_csv_file(f)
        profiles[p["table_name"]] = p
    
    full_report = {
        "generated_at": datetime.now().isoformat(),
        "total_tables": len(profiles),
        "tables": profiles
    }
    
    if output_report_dir:
        output_report_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_report_dir / "data_profile.json"
        with open(json_path, "w", encoding="utf-8") as out:
            json.dump(full_report, out, indent=2)
        print(f"Structured JSON profile saved to: {json_path}")
        
        # Also write readable Markdown summary
        md_path = output_report_dir / "data_profile_summary.md"
        with open(md_path, "w", encoding="utf-8") as out:
            out.write("# Dataset Profiling Summary\n\n")
            out.write(f"Generated at: {full_report['generated_at']}\n\n")
            out.write("| Table | Rows | Cols | Candidate Primary Key | Composite? |\n")
            out.write("|---|---:|---:|---|---|\n")
            for t_name, t_info in profiles.items():
                pk_str = ", ".join(t_info.get("candidate_primary_keys", [])) or "None"
                comp = "Yes" if t_info.get("is_composite_pk") else "No"
                out.write(f"| `{t_name}` | {t_info['row_count']:,} | {t_info['column_count']} | `{pk_str}` | {comp} |\n")
            
            out.write("\n\n## Detailed Column Profiles\n\n")
            for t_name, t_info in profiles.items():
                out.write(f"### Table: `{t_name}` ({t_info['row_count']:,} rows)\n\n")
                out.write("| Column | Inferred Type | Nulls | Null % | Unique | Sample Values |\n")
                out.write("|---|---|---:|---:|---:|---|\n")
                for c in t_info["columns"]:
                    samples_str = ", ".join(f'"{s}"' for s in c["sample_values"][:2])
                    out.write(f"| `{c['name']}` | {c['inferred_type']} | {c['null_count']:,} | {c['null_percentage']}% | {c['unique_count']:,} | {samples_str} |\n")
                out.write("\n")
        print(f"Markdown profile summary saved to: {md_path}")
    
    return full_report


if __name__ == "__main__":
    import sys
    base_dir = Path(__file__).resolve().parent.parent.parent
    raw_dir = base_dir / "data" / "raw" / "olist"
    if not raw_dir.exists() or not list(raw_dir.glob("*.csv")):
        raw_dir = base_dir  # fallback to workspace root
    
    report_dir = base_dir / "data" / "reports"
    profile_all_csvs(raw_dir, report_dir)
