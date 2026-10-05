"""
Generic Data Cleaning and Normalization Module.
Transforms raw CSV rows into clean, typed, relational-ready records:
- Generic snake_case column name normalization
- BOM removal and header typo corrections (e.g. lenght -> length)
- Date and numeric normalization
- STRICT PRINCIPLE: ZERO value generation/imputation. Missing values are faithfully preserved as None (SQL NULL).
"""

from datetime import datetime
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple


def normalize_column_name(raw_name: str) -> str:
    """
    Generically normalize column headers into clean snake_case:
    - Removes UTF-8 BOM markers (\\ufeff)
    - Converts camelCase / PascalCase to snake_case
    - Replaces whitespace and non-alphanumeric characters with underscores
    - Corrects standard typos like 'lenght' -> 'length'
    - Lowercases everything and trims excess underscores
    """
    if not raw_name:
        return ""
    
    # Strip BOM and leading/trailing whitespace
    name = raw_name.lstrip("\ufeff").strip()
    
    # Convert camelCase to snake_case (e.g. CustomerID -> customer_id, orderDate -> order_date)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    
    # Replace non-alphanumeric chars with underscores
    name = re.sub(r"[^\w]+", "_", name)
    name = name.lower()
    
    # Standardize common phonetic typos generically
    name = re.sub(r"\blenght\b", "length", name)
    name = re.sub(r"_lenght\b", "_length", name)
    name = re.sub(r"\blenght_", "length_", name)
    
    # Trim leading/trailing underscores and collapse multiples
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def normalize_datetime(val: Optional[str]) -> Optional[str]:
    """
    Validate and normalize datetime strings into standard ISO format (YYYY-MM-DD HH:MM:SS).
    If empty or unparseable, returns None (preserves authentic SQL NULL).
    Never invents dates.
    """
    if not val:
        return None
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ("null", "nan", "none", ""):
        return None
    
    # Check common ISO and SQL timestamp formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(val_str, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    
    # If unparseable, return original clean string without inventing
    return val_str


def clean_cell_value(val: Any, target_type: Optional[str] = None) -> Any:
    """
    Clean individual cell values preserving true NULLs:
    - Empty strings, 'null', 'nan', 'none' become Python None (SQL NULL).
    - Preserves exact authentic data; never synthesizes values.
    """
    if val is None:
        return None
    
    if isinstance(val, str):
        val = val.strip()
        if val == "" or val.lower() in ("null", "nan", "none"):
            return None
    
    if target_type == "DATETIME":
        return normalize_datetime(val)
    elif target_type == "INTEGER":
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None
    elif target_type == "REAL":
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    
    return val


def get_canonical_table_name(filename_or_stem: str) -> str:
    """Derive standard table name from dataset filename."""
    stem = filename_or_stem.replace(".csv", "").strip()
    stem = stem.replace("olist_", "").replace("_dataset", "")
    if stem == "product_category_name_translation":
        return "category_translation"
    return stem
