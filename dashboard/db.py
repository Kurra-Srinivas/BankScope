import os
import urllib.parse
import warnings
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

# Locate and load root .env
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

def get_db_credentials() -> dict:
    """
    Retrieve database configuration supporting both:
    1. Streamlit Community Cloud: `st.secrets` (both flat keys and sectioned [postgres]/[connections.postgresql])
    2. Local Development: `.env` environment variables via python-dotenv

    Never raises exceptions on missing secrets and never leaks credentials.
    """
    creds = {
        "host": "localhost",
        "port": "5432",
        "database": "bankscope_db",
        "user": "postgres",
        "password": "",
        "sslmode": None,
    }

    # 1. Inspect Streamlit st.secrets if running inside Streamlit runtime
    try:
        if hasattr(st, "secrets") and st.secrets:
            # Check nested sections e.g. [postgres], [postgresql], [connections.postgresql], [database]
            for sec_name in ["postgres", "postgresql", "connections.postgresql", "database"]:
                if sec_name in st.secrets:
                    section = st.secrets[sec_name]
                    if isinstance(section, dict) or hasattr(section, "get"):
                        if "host" in section: creds["host"] = str(section["host"])
                        if "port" in section: creds["port"] = str(section["port"])
                        if "dbname" in section: creds["database"] = str(section["dbname"])
                        elif "database" in section: creds["database"] = str(section["database"])
                        if "user" in section: creds["user"] = str(section["user"])
                        elif "username" in section: creds["user"] = str(section["username"])
                        if "password" in section: creds["password"] = str(section["password"])
                        if "sslmode" in section: creds["sslmode"] = str(section["sslmode"])

            # Check flat keys e.g. DB_HOST, DB_NAME in st.secrets
            flat_map = [
                ("DB_HOST", "host"),
                ("DB_PORT", "port"),
                ("DB_NAME", "database"),
                ("DB_USER", "user"),
                ("DB_PASSWORD", "password"),
                ("DB_SSLMODE", "sslmode"),
            ]
            for key, target in flat_map:
                if key in st.secrets and st.secrets[key]:
                    creds[target] = str(st.secrets[key])
    except Exception:
        # Fall through to os.environ / .env
        pass

    # 2. Inspect environment variables (loaded from .env or system environment)
    env_host = os.getenv("DB_HOST") or os.getenv("PGHOST")
    if env_host: creds["host"] = env_host

    env_port = os.getenv("DB_PORT") or os.getenv("PGPORT")
    if env_port: creds["port"] = env_port

    env_name = os.getenv("DB_NAME")
    if env_name:
        creds["database"] = env_name
    elif not creds.get("database"):
        creds["database"] = "bankscope_db"

    env_user = os.getenv("DB_USER") or os.getenv("PGUSER")
    if env_user: creds["user"] = env_user

    env_pass = os.getenv("DB_PASSWORD") or os.getenv("PGPASSWORD")
    if env_pass is not None and env_pass != "": creds["password"] = env_pass

    env_ssl = os.getenv("DB_SSLMODE") or os.getenv("PGSSLMODE")
    if env_ssl: creds["sslmode"] = env_ssl

    return creds


# Backward-compatible configuration exports
_initial_creds = get_db_credentials()
DB_HOST = _initial_creds["host"]
DB_PORT = _initial_creds["port"]
DB_NAME = _initial_creds["database"]
DB_USER = _initial_creds["user"]
DB_PASSWORD = _initial_creds["password"]


@st.cache_resource
def get_engine():
    """Create and cache SQLAlchemy engine for connection pooling (Standard/App operations)."""
    creds = get_db_credentials()
    encoded_password = urllib.parse.quote_plus(creds["password"])
    url = f"postgresql+psycopg2://{creds['user']}:{encoded_password}@{creds['host']}:{creds['port']}/{creds['database']}"
    
    engine_kwargs = {"pool_size": 5, "max_overflow": 10}
    if creds.get("sslmode"):
        engine_kwargs["connect_args"] = {"sslmode": creds["sslmode"]}

    return create_engine(url, **engine_kwargs)


@st.cache_resource
def get_readonly_engine():
    """
    Create a dedicated, strictly isolated read-only SQLAlchemy engine for user-generated queries.
    PostgreSQL protocol-level guarantees:
    - default_transaction_read_only = on (rejects INSERT, UPDATE, DELETE, DROP, CREATE, etc.)
    - statement_timeout = 10000 (10-second hard query timeout)
    """
    creds = get_db_credentials()
    encoded_password = urllib.parse.quote_plus(creds["password"])
    url = f"postgresql+psycopg2://{creds['user']}:{encoded_password}@{creds['host']}:{creds['port']}/{creds['database']}"
    
    connect_args = {
        "options": "-c default_transaction_read_only=on -c statement_timeout=10000"
    }
    if creds.get("sslmode"):
        connect_args["sslmode"] = creds["sslmode"]

    return create_engine(url, pool_size=3, max_overflow=5, connect_args=connect_args)


@st.cache_data(ttl=600, show_spinner=False)
def execute_query(sql: str, params=None) -> pd.DataFrame:
    """Execute a parameterized SQL query and return results as a Pandas DataFrame."""
    engine = get_engine()
    with engine.connect() as conn:
        if params is not None:
            # Handle tuple/dict parameters
            df = pd.read_sql_query(sql, conn.connection, params=params)
        else:
            df = pd.read_sql_query(sql, conn.connection)
    return df


def execute_readonly_query(sql: str, max_rows: int = 500) -> tuple[pd.DataFrame, float, str | None]:
    """
    Execute an approved read-only analytical query on the dedicated read-only connection.
    Enforces:
    1. Isolated read-only engine (zero write capability).
    2. Server-side statement timeout (10s).
    3. Row-level cap via subquery wrapper.
    4. Credential sanitation on all database exceptions.

    Returns:
        (df: pd.DataFrame, execution_time_ms: float, error_message: str | None)
    """
    import time
    import re

    cleaned_sql = sql.strip().rstrip(";")
    if not cleaned_sql:
        return pd.DataFrame(), 0.0, "Empty SQL query."

    # Subquery wrapper guarantees hard row limit without breaking CTEs or ORDER BY
    limited_sql = f"SELECT * FROM (\n{cleaned_sql}\n) AS _bankscope_subquery LIMIT {int(max_rows)};"

    engine = get_readonly_engine()
    start_time = time.perf_counter()

    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(limited_sql, conn.connection)
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return df, elapsed_ms, None
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        raw_err = str(e)

        # Sanitize any passwords, hosts, or connection URIs
        sanitized = re.sub(r"://[^@]+@", "://***:***@", raw_err)
        sanitized = re.sub(r"password='[^']*'", "password='***'", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"password=[^\s;]+", "password=***", sanitized, flags=re.IGNORECASE)

        # User-friendly explanation for common database security errors
        if "ReadOnlySqlTransaction" in sanitized or "read-only transaction" in sanitized:
            return (
                pd.DataFrame(),
                elapsed_ms,
                "Database Engine Security Violation: Cannot execute modifying operations in a read-only transaction.",
            )
        elif "canceling statement due to statement timeout" in sanitized or "QueryCanceledError" in sanitized:
            return (
                pd.DataFrame(),
                elapsed_ms,
                "Query Timeout: Execution exceeded the 10-second safety limit.",
            )

        # Extract the most descriptive PostgreSQL error line
        err_lines = [line.strip() for line in sanitized.splitlines() if line.strip()]
        user_err = "Unknown database execution error."
        for line in err_lines:
            if "psycopg2.errors" in line or "error" in line.lower():
                if not line.startswith("Execution failed on sql"):
                    user_err = line
                    break
        if user_err == "Unknown database execution error." and err_lines:
            user_err = err_lines[-1]
        return pd.DataFrame(), elapsed_ms, user_err


def test_db_connection() -> bool:
    """Check database reachability."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return True
    except Exception:
        return False
