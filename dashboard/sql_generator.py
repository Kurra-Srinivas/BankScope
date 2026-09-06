"""
BankScope — Schema-Aware Natural-Language SQL Generator & Security Validator
Builds dynamic schema contexts from PostgreSQL, invokes configured LLM providers,
and enforces strict read-only (SELECT/WITH) query security guards.
"""

import os
import re
import pandas as pd
from sqlalchemy import text
from dashboard.db import get_engine
from dashboard.llm_provider import BaseLLMProvider, get_llm_provider

# Forbidden SQL keywords and statement modifiers
FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "COPY",
    "MERGE", "CALL", "RENAME", "REPLACE", "VACUUM", "ANALYZE"
]

CORE_BANKING_SCHEMA_SUMMARY = """
### Database: PostgreSQL 18 (Schema: public)
#### Tables & Core Relationships:
1. `customers` (50,000 rows):
   - Columns: customer_id (PK, varchar), first_name (varchar), last_name (varchar), email (varchar), city (varchar), credit_score (integer, 300-850), created_at (timestamp)
2. `accounts` (75,000 rows):
   - Columns: account_id (PK, varchar), customer_id (FK -> customers.customer_id), account_type (varchar: 'Checking', 'Savings', 'Business'), balance_usd (numeric), open_date (timestamp)
3. `cards` (100,000 rows):
   - Columns: card_id (PK, varchar), account_id (FK -> accounts.account_id), card_type (varchar: 'Debit', 'Credit'), expiration_date (timestamp)
4. `loans` (30,000 rows):
   - Columns: loan_id (PK, varchar), customer_id (FK -> customers.customer_id), loan_amount (numeric), interest_rate (numeric APR %), start_date (timestamp)
5. `merchants` (5,000 rows):
   - Columns: merchant_id (PK, varchar), merchant_name (varchar), city (varchar)
6. `transactions` (1,000,000 rows, Jan 2019 - Dec 2025):
   - Columns: transaction_id (PK, varchar), account_id (FK -> accounts.account_id), merchant_id (FK -> merchants.merchant_id), amount_usd (numeric, $1.02 to $9,999.98), transaction_date (timestamp)
7. `branches` (500 rows - standalone facility catalog):
   - Columns: branch_id (PK, varchar), branch_name (varchar), city (varchar, NULL), state (varchar)
   - Note: branches has NO foreign keys linking to customers or accounts.
"""


def clean_sql(raw_text: str) -> str:
    """
    Clean markdown code blocks, backticks, and extraneous commentary
    from model output to isolate the raw SQL query.
    """
    if not raw_text:
        return ""
        
    text_content = raw_text.strip()
    # Extract from ```sql ... ``` or ``` ... ```
    code_block_match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", text_content, re.IGNORECASE)
    if code_block_match:
        text_content = code_block_match.group(1).strip()
        
    # Remove leading comments if they precede SELECT/WITH
    lines = []
    found_sql = False
    for line in text_content.splitlines():
        trimmed = line.strip()
        if not found_sql:
            if trimmed.upper().startswith(("SELECT", "WITH")):
                found_sql = True
                lines.append(line)
            elif trimmed.startswith("--"):
                # Preserve inline comments if user added them
                continue
            else:
                continue
        else:
            lines.append(line)
            
    result = "\n".join(lines).strip()
    return result if result else text_content.strip()


def repair_postgres_numeric_casts(sql: str) -> str:
    """
    Repair PostgreSQL numeric/double precision type casting issues in generated SQL.
    PostgreSQL only supports round(numeric, integer), NOT round(double precision, integer).
    When expressions like AVG(col), SUM(col), or arithmetic inside ROUND(...) are not cast,
    PostgreSQL throws 'function round(double precision, integer) does not exist'.
    This function parses balanced parentheses inside ROUND(expr, n) and wraps expr in ::numeric
    unless it is already cast.
    """
    if not sql or "ROUND" not in sql.upper():
        return sql

    result = []
    i = 0
    n = len(sql)
    while i < n:
        match = re.search(r'\bROUND\s*\(', sql[i:], re.IGNORECASE)
        if not match:
            result.append(sql[i:])
            break
        
        start = i + match.start()
        result.append(sql[i:start])
        open_paren_idx = i + match.end() - 1
        paren_depth = 1
        j = open_paren_idx + 1
        comma_pos = -1
        while j < n and paren_depth > 0:
            if sql[j] == '(':
                paren_depth += 1
            elif sql[j] == ')':
                paren_depth -= 1
            elif sql[j] == ',' and paren_depth == 1:
                comma_pos = j
            j += 1
        
        if paren_depth == 0 and comma_pos != -1:
            expr = sql[open_paren_idx + 1:comma_pos].strip()
            decimals = sql[comma_pos + 1:j - 1].strip()
            if decimals.isdigit():
                expr_lower = expr.lower()
                if '::numeric' not in expr_lower and 'as numeric' not in expr_lower:
                    if expr.startswith('(') and expr.endswith(')'):
                        expr = expr[1:-1].strip()
                    result.append(f'ROUND(({expr})::numeric, {decimals})')
                else:
                    result.append(sql[start:j])
            else:
                result.append(sql[start:j])
            i = j
        else:
            result.append(sql[start:open_paren_idx + 1])
            i = open_paren_idx + 1
    return ''.join(result)


import sqlparse


def validate_sql_security(sql: str) -> tuple[bool, str]:
    """
    Strict security validation:
    1. Must contain exactly one statement (enforced by sqlparse).
    2. Must start with SELECT or WITH.
    3. Must NOT contain any forbidden mutation/DDL keywords (INSERT, UPDATE, DELETE, DROP, etc.).
    4. Must NOT contain multiple semicolon-separated statements.
    Returns (is_safe, error_message).
    """
    if not sql or not sql.strip():
        return False, "Query is empty."

    # Parse with sqlparse to enforce single-statement rule
    parsed = sqlparse.parse(sql)
    non_empty_stmts = [s for s in parsed if str(s).strip()]
    if len(non_empty_stmts) == 0:
        return False, "Query contains only comments or whitespace."
    if len(non_empty_stmts) > 1:
        return False, "Security Policy Violation: Multiple chained SQL statements detected. Only a single query is permitted."

    stmt = non_empty_stmts[0]
    raw_str = str(stmt)

    # Strip single-line and multi-line comments for keyword checking
    no_comments = re.sub(r"--.*?$", "", raw_str, flags=re.MULTILINE)
    no_comments = re.sub(r"/\*.*?\*/", "", no_comments, flags=re.DOTALL).strip()

    if not no_comments:
        return False, "Query contains only comments."

    # Verify starting keyword
    first_token_match = re.match(r"^\s*([a-zA-Z]+)", no_comments)
    if not first_token_match:
        return False, "Unable to detect starting SQL token."

    first_token = first_token_match.group(1).upper()
    if first_token not in ("SELECT", "WITH"):
        return False, f"Security Policy Violation: Only read-only SELECT or WITH statements are permitted. Found: '{first_token}'."

    # Check for forbidden mutation and DDL keywords with word boundaries
    for keyword in FORBIDDEN_KEYWORDS:
        pattern = rf"\b{keyword}\b"
        if re.search(pattern, no_comments, re.IGNORECASE):
            return False, f"Security Policy Violation: Forbidden operation '{keyword}' detected. Only read-only analytical queries are permitted."

    # Check for multiple chained statements (e.g., SELECT ...; DROP ...)
    # Remove trailing semicolon if present
    trimmed_stmts = [s.strip() for s in no_comments.rstrip(";").split(";") if s.strip()]
    if len(trimmed_stmts) > 1:
        return False, "Security Policy Violation: Multiple chained SQL statements separated by semicolons are not permitted."

    return True, ""


def validate_with_postgres_explain(sql: str) -> tuple[bool, str]:
    """
    Validate SQL query using PostgreSQL's query planner (EXPLAIN).
    Verifies valid table references, column references, data types, and syntax
    without executing the query. Runs strictly on the read-only engine.
    """
    is_safe, sec_err = validate_sql_security(sql)
    if not is_safe:
        return False, sec_err

    # Verify physical existence of any referenced upload table
    upload_tbl_matches = re.findall(r'\buploads\.([a-zA-Z0-9_]+)\b', sql, re.IGNORECASE)
    if upload_tbl_matches:
        from dashboard.upload_engine import table_exists_in_db
        for tbl in upload_tbl_matches:
            if not table_exists_in_db(tbl, "uploads"):
                return False, f"Target table 'uploads.{tbl}' does not exist in PostgreSQL. Please re-upload your dataset."

    from dashboard.db import get_readonly_engine
    cleaned = sql.strip().rstrip(";")
    explain_query = f"EXPLAIN (FORMAT TEXT) {cleaned};"

    try:
        engine = get_readonly_engine()
        with engine.connect() as conn:
            conn.execute(text(explain_query))
        return True, "PostgreSQL query plan verified successfully."
    except Exception as ex:
        raw_msg = str(ex)
        # Sanitize any passwords or URIs
        sanitized = re.sub(r"://[^@]+@", "://***:***@", raw_msg)
        lines = [line.strip() for line in sanitized.splitlines() if line.strip()]
        error_line = lines[0] if lines else "Syntax or catalog verification error."
        return False, f"PostgreSQL Planner Error: {error_line}"


def execute_approved_sql(sql: str, max_rows: int = 500) -> dict:
    """
    Execute user-approved SQL on the dedicated read-only PostgreSQL connection.
    Guarantees:
    1. Static & sqlparse security validation.
    2. Physical target table existence.
    3. Zero write permissions (PostgreSQL default_transaction_read_only=on).
    4. Truncation to max_rows.
    5. 10s execution timeout.

    Returns:
        {
            "success": bool,
            "df": pd.DataFrame,
            "row_count": int,
            "execution_time_ms": float,
            "error_message": str | None,
            "sql_executed": str
        }
    """
    is_safe, sec_err = validate_sql_security(sql)
    if not is_safe:
        return {
            "success": False,
            "df": pd.DataFrame(),
            "row_count": 0,
            "execution_time_ms": 0.0,
            "error_message": sec_err,
            "sql_executed": sql,
        }

    # Verify physical existence of any referenced upload table
    upload_tbl_matches = re.findall(r'\buploads\.([a-zA-Z0-9_]+)\b', sql, re.IGNORECASE)
    if upload_tbl_matches:
        from dashboard.upload_engine import table_exists_in_db
        for tbl in upload_tbl_matches:
            if not table_exists_in_db(tbl, "uploads"):
                return {
                    "success": False,
                    "df": pd.DataFrame(),
                    "row_count": 0,
                    "execution_time_ms": 0.0,
                    "error_message": f"Target table 'uploads.{tbl}' does not exist in PostgreSQL. Please re-upload your dataset.",
                    "sql_executed": sql,
                }

    from dashboard.db import execute_readonly_query

    df, elapsed_ms, err = execute_readonly_query(sql, max_rows=max_rows)

    return {
        "success": err is None,
        "df": df,
        "row_count": len(df),
        "execution_time_ms": elapsed_ms,
        "error_message": err,
        "sql_executed": sql,
    }


def get_dataset_schema_context(dataset_choice: str) -> dict:
    """
    Extract dynamic schema context for the selected dataset:
    - 'BankScope Banking Data' -> public 7 tables
    - 'upload:<table_name>' -> uploads.<table_name> dynamic inspection
    Returns a dictionary with formatted context string and structural schema metadata.
    """
    if dataset_choice == "BankScope Banking Data":
        return {
            "dataset_name": "BankScope Core Banking Warehouse (public)",
            "context_string": CORE_BANKING_SCHEMA_SUMMARY,
            "tables": [
                {"table_name": "customers", "schema": "public", "columns": "customer_id, first_name, last_name, email, city, credit_score, created_at"},
                {"table_name": "accounts", "schema": "public", "columns": "account_id, customer_id, account_type, balance_usd, open_date"},
                {"table_name": "cards", "schema": "public", "columns": "card_id, account_id, card_type, expiration_date"},
                {"table_name": "loans", "schema": "public", "columns": "loan_id, customer_id, loan_amount, interest_rate, start_date"},
                {"table_name": "merchants", "schema": "public", "columns": "merchant_id, merchant_name, city"},
                {"table_name": "transactions", "schema": "public", "columns": "transaction_id, account_id, merchant_id, amount_usd, transaction_date"},
                {"table_name": "branches", "schema": "public", "columns": "branch_id, branch_name, city, state"},
            ]
        }
        
    # Dynamic uploaded table from uploads schema
    table_name = dataset_choice.replace("upload:", "").strip()
    if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
        raise ValueError("Invalid table identifier.")
        
    from dashboard.upload_engine import table_exists_in_db
    if not table_exists_in_db(table_name, "uploads"):
        raise FileNotFoundError(f"Target table 'uploads.{table_name}' does not exist in PostgreSQL. Please re-upload your dataset.")
        
    engine = get_engine()
    
    query = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'uploads' AND table_name = :table_name
        ORDER BY ordinal_position;
    """
    
    try:
        with engine.connect() as conn:
            df_cols = pd.read_sql_query(text(query), conn, params={"table_name": table_name})
            
            # Fetch row count
            cnt_query = f'SELECT COUNT(*) FROM "uploads"."{table_name}";'
            row_count = conn.execute(text(cnt_query)).scalar() or 0
    except Exception as e:
        df_cols = pd.DataFrame()
        row_count = 0
        
    cols_desc = []
    for _, r in df_cols.iterrows():
        cols_desc.append(f"   - `{r['column_name']}` ({r['data_type']})")
        
    cols_str = "\n".join(cols_desc) if cols_desc else "   - (No columns found)"
    
    context_str = f"""
### Database: PostgreSQL 18 (Schema: uploads)
#### Target Table: `uploads.{table_name}` ({row_count:,} rows):
{cols_str}

Important: Always reference this table with schema qualification: `uploads.{table_name}`.
"""
    return {
        "dataset_name": f"Uploaded Dataset (uploads.{table_name})",
        "context_string": context_str,
        "tables": [
            {
                "table_name": table_name,
                "schema": "uploads",
                "columns": ", ".join(df_cols["column_name"].tolist()) if not df_cols.empty else "N/A",
                "row_count": row_count
            }
        ]
    }


def generate_sql_query(question: str, dataset_choice: str, provider: BaseLLMProvider = None) -> dict:
    """
    End-to-end SQL generation:
    1. Resolve schema context (validates physical table existence).
    2. Format prompt and system rules (instructing ::numeric casts on AVG/SUM/ROUND).
    3. Invoke LLM provider (Groq primary / fallback).
    4. Clean output and repair numeric casts.
    5. Enforce static security validation.
    Returns result dict with SQL, validation status, and metadata.
    """
    if provider is None:
        provider = get_llm_provider()
        
    schema_info = get_dataset_schema_context(dataset_choice)
    
    system_instruction = f"""
You are BankScope's expert PostgreSQL SQL generation assistant.
Generate clean, valid, standard PostgreSQL 18 SQL queries based strictly on the user's natural language question and the provided schema.

Strict Rules:
1. ONLY generate SELECT or WITH queries. NEVER generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE.
2. Output ONLY the raw SQL query. Do not wrap in conversational markdown or explanations outside the query.
3. Use proper PostgreSQL syntax:
   - For monthly dates: DATE_TRUNC('month', date_col)::DATE
   - For window ranking: DENSE_RANK() OVER (ORDER BY ...) or ROW_NUMBER()
   - For rounding monetary amounts and averages: In PostgreSQL, ROUND(val, n) strictly requires numeric type.
     When rounding AVG, SUM, division, or floating-point columns, ALWAYS cast to ::numeric before rounding!
     Example: ROUND(AVG(col)::numeric, 2), ROUND(SUM(col)::numeric, 2), ROUND((val * 100.0 / total)::numeric, 2).
     NEVER write ROUND(AVG(col), 2) because round(double precision, integer) does not exist in PostgreSQL!
   - For string concatenation: first_name || ' ' || last_name
4. Do NOT hallucinate tables or columns not present in the provided schema.
5. If tables from the uploads schema are used, qualify them explicitly with `uploads.<table_name>`.

{schema_info['context_string']}
"""

    prompt = f"User Question: {question}\n\nGenerate the corresponding PostgreSQL SELECT query:"

    try:
        raw_response = provider.generate_text(prompt, system_instruction=system_instruction)
        provider_name = provider.name
    except Exception as api_err:
        from dashboard.llm_provider import OfflineBankingSQLProvider
        if not isinstance(provider, OfflineBankingSQLProvider):
            fallback_provider = OfflineBankingSQLProvider()
            raw_response = fallback_provider.generate_text(prompt, system_instruction=system_instruction)
            provider_name = f"{fallback_provider.name} (Fallback after {provider.name} error)"
        else:
            raise api_err

    clean_query = clean_sql(raw_response)
    repaired_query = repair_postgres_numeric_casts(clean_query)
    is_valid, validation_msg = validate_sql_security(repaired_query)
    
    return {
        "question": question,
        "dataset_choice": dataset_choice,
        "dataset_name": schema_info["dataset_name"],
        "schema_context": schema_info["context_string"],
        "provider_name": provider_name,
        "raw_response": raw_response,
        "sql": repaired_query,
        "is_valid": is_valid,
        "validation_message": validation_msg,
    }
