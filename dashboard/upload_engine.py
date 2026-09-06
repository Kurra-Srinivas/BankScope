"""
BankScope — CSV Upload & Exploration Engine
Handles secure validation, profiling, sanitization, and ingestion of custom CSV datasets
into an isolated PostgreSQL schema ('uploads') with strict session-scoped access control.
"""

import os
import re
import datetime
import pandas as pd
import numpy as np
from sqlalchemy import text
from dashboard.db import get_engine

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB limit
UPLOAD_SCHEMA = "uploads"
METADATA_TABLE = "_upload_metadata"


def sanitize_identifier(name: str, max_length: int = 60) -> str:
    """
    Sanitize an arbitrary string into a safe, valid PostgreSQL identifier.
    Only allows lowercase a-z, 0-9, and underscores.
    """
    if not name:
        return "unnamed_col"
    
    cleaned = name.strip().lower()
    cleaned = re.sub(r"[^a-z0-9_]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    
    if cleaned and cleaned[0].isdigit():
        cleaned = f"col_{cleaned}"
        
    if not cleaned:
        cleaned = "unnamed_col"
        
    return cleaned[:max_length]


def generate_unique_table_name(original_filename: str, session_id: str | None = None) -> str:
    """
    Generate a unique, collision-resistant, session-scoped table name:
    Format: sess_<session_token>_<timestamp>_<sanitized_name>
    """
    base_name, _ = os.path.splitext(original_filename)
    safe_base = sanitize_identifier(base_name, max_length=24)
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if session_id:
        safe_sess = sanitize_identifier(session_id, max_length=12)
        return f"sess_{safe_sess}_{timestamp_str}_{safe_base}"[:60]
    return f"upload_{timestamp_str}_{safe_base}"[:60]


def validate_csv_file(uploaded_file) -> tuple[bool, str]:
    """
    Validate uploaded file format and size constraints.
    Returns (is_valid, error_message).
    """
    if uploaded_file is None:
        return False, "No file provided."
        
    filename = getattr(uploaded_file, "name", "")
    if not filename.lower().endswith(".csv"):
        return False, f"Invalid file extension for '{filename}'. Only CSV files (.csv) are supported."
        
    file_size = getattr(uploaded_file, "size", None)
    if file_size is not None:
        if file_size == 0:
            return False, f"Uploaded file '{filename}' is empty (0 bytes)."
        if file_size > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
            size_mb = file_size / (1024 * 1024)
            return False, f"File size ({size_mb:.1f} MB) exceeds maximum allowed limit of {max_mb:.0f} MB."
            
    return True, ""


def profile_dataframe(df: pd.DataFrame) -> dict:
    """
    Profile an in-memory DataFrame: row/column counts, null counts,
    duplicate rows, and inferred schema types.
    """
    total_rows = len(df)
    total_cols = len(df.columns)
    duplicate_rows = int(df.duplicated().sum())
    
    columns_profile = []
    total_cells = total_rows * total_cols if total_rows and total_cols else 0
    total_null_cells = 0
    
    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        total_null_cells += null_count
        non_null_count = total_rows - null_count
        null_pct = round((null_count / total_rows * 100.0), 2) if total_rows > 0 else 0.0
        unique_count = int(series.nunique(dropna=True))
        
        dtype_str = str(series.dtype)
        if pd.api.types.is_numeric_dtype(series):
            if pd.api.types.is_integer_dtype(series):
                inferred_type = "Integer"
            else:
                inferred_type = "Numeric (Float)"
        elif pd.api.types.is_datetime64_any_dtype(series):
            inferred_type = "Timestamp / Date"
        elif pd.api.types.is_bool_dtype(series):
            inferred_type = "Boolean"
        else:
            inferred_type = "Text / Categorical"
            
        sample_val = None
        non_null_series = series.dropna()
        if not non_null_series.empty:
            sample_val = str(non_null_series.iloc[0])
            if len(sample_val) > 40:
                sample_val = sample_val[:37] + "..."
                
        columns_profile.append({
            "column_name": col,
            "inferred_type": inferred_type,
            "dtype": dtype_str,
            "non_null_count": non_null_count,
            "null_count": null_count,
            "null_pct": null_pct,
            "unique_values": unique_count,
            "sample_value": sample_val if sample_val is not None else "—",
        })
        
    overall_null_pct = round((total_null_cells / total_cells * 100.0), 2) if total_cells > 0 else 0.0
    
    return {
        "total_rows": total_rows,
        "total_cols": total_cols,
        "duplicate_rows": duplicate_rows,
        "total_null_cells": total_null_cells,
        "overall_null_pct": overall_null_pct,
        "columns": columns_profile,
    }


def ensure_upload_schema_and_metadata():
    """
    Ensure the isolated 'uploads' schema and tracking table exist in PostgreSQL.
    """
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {UPLOAD_SCHEMA};"))
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {UPLOAD_SCHEMA}.{METADATA_TABLE} (
                upload_id SERIAL PRIMARY KEY,
                table_name VARCHAR(100) UNIQUE NOT NULL,
                original_filename VARCHAR(255) NOT NULL,
                row_count INTEGER NOT NULL,
                column_count INTEGER NOT NULL,
                duplicate_rows INTEGER NOT NULL,
                file_size_bytes BIGINT,
                session_id VARCHAR(64),
                uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """))
        # Add session_id column if migrating from older schema
        conn.execute(text(f"""
            ALTER TABLE {UPLOAD_SCHEMA}.{METADATA_TABLE} 
            ADD COLUMN IF NOT EXISTS session_id VARCHAR(64);
        """))


def ingest_csv(file_or_buffer, original_filename: str, session_id: str | None = None) -> dict:
    """
    Complete ingestion pipeline:
    1. Parse CSV into DataFrame.
    2. Profile raw data.
    3. Sanitize column names for safe SQL compatibility.
    4. Persist to PostgreSQL under uploads.<unique_table_name> with session scoping.
    5. Record entry in uploads._upload_metadata.
    Returns a dictionary of ingestion results and profiling metadata.
    """
    ensure_upload_schema_and_metadata()
    
    try:
        if hasattr(file_or_buffer, "seek"):
            file_or_buffer.seek(0)
        df = pd.read_csv(file_or_buffer)
    except Exception as e:
        raise ValueError(f"Failed to parse CSV file: {str(e)}")
        
    if df.empty:
        raise ValueError("Uploaded CSV contains no rows.")
        
    raw_profile = profile_dataframe(df)
    
    # Deduplicate and sanitize column names
    sanitized_cols = []
    seen_cols = {}
    for original_col in df.columns:
        safe_col = sanitize_identifier(str(original_col))
        if safe_col in seen_cols:
            seen_cols[safe_col] += 1
            safe_col = f"{safe_col}_{seen_cols[safe_col]}"
        else:
            seen_cols[safe_col] = 1
        sanitized_cols.append(safe_col)
        
    df_clean = df.copy()
    df_clean.columns = sanitized_cols
    
    # Generate session-scoped table name
    target_table = generate_unique_table_name(original_filename, session_id=session_id)
    
    engine = get_engine()
    
    # Determine file size
    file_size_bytes = 0
    if hasattr(file_or_buffer, "size"):
        file_size_bytes = file_or_buffer.size
    elif hasattr(file_or_buffer, "tell") and hasattr(file_or_buffer, "seek"):
        file_or_buffer.seek(0, os.SEEK_END)
        file_size_bytes = file_or_buffer.tell()
        file_or_buffer.seek(0)
        
    # Persist DataFrame to uploads schema
    df_clean.to_sql(
        name=target_table,
        con=engine,
        schema=UPLOAD_SCHEMA,
        if_exists="fail",
        index=False,
        chunksize=5000,
        method="multi"
    )
    
    # Register metadata with session tracking
    with engine.begin() as conn:
        conn.execute(
            text(f"""
                INSERT INTO {UPLOAD_SCHEMA}.{METADATA_TABLE} 
                (table_name, original_filename, row_count, column_count, duplicate_rows, file_size_bytes, session_id, uploaded_at)
                VALUES (:table_name, :original_filename, :row_count, :column_count, :duplicate_rows, :file_size_bytes, :session_id, CURRENT_TIMESTAMP);
            """),
            {
                "table_name": target_table,
                "original_filename": original_filename,
                "row_count": raw_profile["total_rows"],
                "column_count": raw_profile["total_cols"],
                "duplicate_rows": raw_profile["duplicate_rows"],
                "file_size_bytes": file_size_bytes,
                "session_id": session_id or "",
            }
        )
        
    return {
        "status": "SUCCESS",
        "schema": UPLOAD_SCHEMA,
        "table_name": target_table,
        "original_filename": original_filename,
        "session_id": session_id,
        "profile": raw_profile,
        "preview_df": df_clean.head(100),
    }


def get_all_uploaded_tables(allowed_tables: list[str] | None = None) -> pd.DataFrame:
    """
    Fetch tracked uploads from the metadata table.
    When allowed_tables is provided (session whitelist), strictly filters to return
    ONLY tables uploaded in the active session. If allowed_tables is empty, returns empty DataFrame.
    """
    ensure_upload_schema_and_metadata()
    engine = get_engine()
    
    if allowed_tables is not None:
        if not allowed_tables:
            return pd.DataFrame()
        placeholders = ", ".join([f":t{i}" for i in range(len(allowed_tables))])
        params = {f"t{i}": name for i, name in enumerate(allowed_tables)}
        query = f"""
            SELECT 
                upload_id,
                table_name,
                original_filename,
                row_count,
                column_count,
                duplicate_rows,
                ROUND(file_size_bytes / 1024.0, 1) AS size_kb,
                uploaded_at
            FROM {UPLOAD_SCHEMA}.{METADATA_TABLE}
            WHERE table_name IN ({placeholders})
            ORDER BY upload_id DESC;
        """
    else:
        query = f"""
            SELECT 
                upload_id,
                table_name,
                original_filename,
                row_count,
                column_count,
                duplicate_rows,
                ROUND(file_size_bytes / 1024.0, 1) AS size_kb,
                uploaded_at
            FROM {UPLOAD_SCHEMA}.{METADATA_TABLE}
            ORDER BY upload_id DESC;
        """
        params = {}

    try:
        with engine.connect() as conn:
            return pd.read_sql_query(text(query), conn, params=params)
    except Exception:
        return pd.DataFrame()


def get_uploaded_table_data(table_name: str, limit: int = 100, allowed_tables: list[str] | None = None) -> pd.DataFrame:
    """
    Safely query an uploaded table from the uploads schema.
    Validates table_name against alphanumeric underscore pattern and session access whitelist.
    """
    if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
        raise ValueError("Invalid table identifier.")
    if allowed_tables is not None and table_name not in allowed_tables:
        raise PermissionError(f"Access denied: table '{table_name}' does not belong to the current session.")
        
    engine = get_engine()
    query = f'SELECT * FROM "{UPLOAD_SCHEMA}"."{table_name}" LIMIT :limit;'
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn, params={"limit": limit})


def delete_uploaded_table(table_name: str) -> bool:
    """
    Safely drop an uploaded table from the uploads schema and remove its metadata entry.
    """
    if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
        raise ValueError("Invalid table identifier.")
        
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS "{UPLOAD_SCHEMA}"."{table_name}" CASCADE;'))
        conn.execute(
            text(f'DELETE FROM "{UPLOAD_SCHEMA}"."{METADATA_TABLE}" WHERE table_name = :table_name;'),
            {"table_name": table_name}
        )
    return True
