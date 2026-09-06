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

DB_HOST = os.getenv("DB_HOST") or os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("DB_PORT") or os.getenv("PGPORT", "5432")
DB_NAME = os.getenv("DB_NAME") or "bankscope_db"
DB_USER = os.getenv("DB_USER") or os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("PGPASSWORD", "")


@st.cache_resource
def get_engine():
    """Create and cache SQLAlchemy engine for connection pooling."""
    encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
    url = f"postgresql+psycopg2://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url, pool_size=5, max_overflow=10)


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


def test_db_connection() -> bool:
    """Check database reachability."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return True
    except Exception:
        return False
