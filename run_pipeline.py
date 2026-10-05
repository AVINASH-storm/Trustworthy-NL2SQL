"""
Master Pipeline Orchestrator for Olist Data Engineering Foundation.
Executes Steps 1 through 6:
1. Organize raw dataset into data/raw/olist/
2. Run automated data profiler
3. Clean data & load into relational SQLite (olist.db) with true PK/FKs and indexes
4. Run comprehensive database & referential integrity audits
5. Automatically introspect schema and generate RAG schema documents
"""

import os
from pathlib import Path
import shutil
import sys
import time

# Add root directory to sys.path so src imports work reliably
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.profile_data import profile_all_csvs
from src.ingestion.load_database import load_database
from src.ingestion.validate_database import validate_database
from src.ingestion.schema_introspection import run_introspection


def organize_raw_dataset(root_dir: Path, target_dir: Path):
    """
    Ensure the 9 raw CSV files are neatly organized inside data/raw/olist/.
    If they are located in root, copy/move them to target_dir.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    existing_in_target = list(target_dir.glob("*.csv"))
    if len(existing_in_target) >= 9:
        print(f"[OK] Raw CSV files already organized in: {target_dir}")
        return
    
    # Check root directory for CSVs
    root_csvs = list(root_dir.glob("*.csv"))
    if root_csvs:
        print(f"Organizing {len(root_csvs)} raw CSV files from root into {target_dir}...")
        for csv_file in root_csvs:
            dest = target_dir / csv_file.name
            if not dest.exists():
                shutil.copy2(csv_file, dest)
        print("[OK] Raw dataset organized successfully.")
    else:
        raise FileNotFoundError(f"No CSV files found in {target_dir} or {root_dir}")


def main():
    start_total = time.time()
    print("=" * 70)
    print("      OLIST NL2SQL DATA ENGINEERING & DATABASE FOUNDATION PIPELINE     ")
    print("=" * 70)
    
    # Paths
    raw_dir = PROJECT_ROOT / "data" / "raw" / "olist"
    db_path = PROJECT_ROOT / "data" / "database" / "olist.db"
    reports_dir = PROJECT_ROOT / "data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Organize raw files
    print("\n--- STEP 1 & 2: Dataset Organization & Inspection ---")
    organize_raw_dataset(PROJECT_ROOT, raw_dir)
    
    # Step 2: Automatic Data Profiling
    print("\n--- STEP 3: Automated Data Profiling ---")
    profile_all_csvs(raw_dir, reports_dir)
    
    # Step 3: Clean & Load Relational Database
    print("\n--- STEP 4 & 5: Generic Cleaning & Relational SQLite Loading ---")
    conn = load_database(raw_dir, db_path)
    conn.close()
    
    # Step 4: Validate Database & Referential Integrity
    print("\n--- STEP 6: Database & Referential Integrity Audits ---")
    val_report = validate_database(db_path, raw_dir, reports_dir)
    if not val_report["all_passed"]:
        print("[ERROR] Database validation checks failed! Inspect data/reports/database_validation_report.json")
        sys.exit(1)
        
    # Step 5: Schema Introspection & Documentation Generation
    print("\n--- STEP 7: Automatic Schema Introspection & RAG Document Generation ---")
    run_introspection(db_path, reports_dir)
    
    elapsed = round(time.time() - start_total, 2)
    print("\n" + "=" * 70)
    print(f"PIPELINE COMPLETED SUCCESSFULLY IN {elapsed} SECONDS!")
    print("=" * 70)
    print(f"Relational Database:      {db_path}")
    print(f"Data Profiling Report:    {reports_dir / 'data_profile_summary.md'}")
    print(f"Validation Audit Report:  {reports_dir / 'database_validation_report.json'}")
    print(f"Schema Metadata JSON:     {reports_dir / 'schema_metadata.json'}")
    print(f"RAG Schema Documents:     {reports_dir / 'schema_docs'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
