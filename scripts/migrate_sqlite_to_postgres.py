#!/usr/bin/env python3
"""
BankScope — SQLite to PostgreSQL Migration Engine
Canonical Source: data/raw/banking_dataset_kaggle/data/database/bank_sqlite.db
"""

import os
import sys
import io
import csv
import time
import sqlite3
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure root directory is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DB_HOST = os.getenv("DB_HOST") or os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("DB_PORT") or os.getenv("PGPORT", "5432")
DB_NAME = os.getenv("DB_NAME") or "bankscope_db"
DB_USER = os.getenv("DB_USER") or os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("PGPASSWORD", "")
DB_SSLMODE = os.getenv("DB_SSLMODE") or os.getenv("PGSSLMODE")

SQLITE_PATH = os.path.join(
    BASE_DIR, "data", "raw", "banking_dataset_kaggle", "data", "database", "bank_sqlite.db"
)
SCHEMA_SQL_PATH = os.path.join(BASE_DIR, "sql", "schema.sql")
CONSTRAINTS_SQL_PATH = os.path.join(BASE_DIR, "sql", "constraints.sql")
INDEXES_SQL_PATH = os.path.join(BASE_DIR, "sql", "indexes.sql")

TABLES_ORDER = [
    ("customers", ["customer_id", "first_name", "last_name", "email", "city", "credit_score", "created_at"]),
    ("merchants", ["merchant_id", "merchant_name", "city"]),
    ("branches", ["branch_id", "branch_name", "manager_name", "city", "country"]),
    ("accounts", ["account_id", "customer_id", "account_type", "balance_usd", "open_date"]),
    ("cards", ["card_id", "account_id", "card_type", "expiration_date"]),
    ("loans", ["loan_id", "customer_id", "loan_amount", "interest_rate", "start_date"]),
    ("transactions", ["transaction_id", "account_id", "merchant_id", "amount_usd", "transaction_date"]),
]


def get_pg_admin_connection():
    """Connect to default 'postgres' database to check/create target database."""
    params = {
        "host": DB_HOST,
        "port": DB_PORT,
        "dbname": "postgres",
        "user": DB_USER,
        "password": DB_PASSWORD,
    }
    if DB_SSLMODE:
        params["sslmode"] = DB_SSLMODE
    return psycopg2.connect(**params)


def get_pg_connection():
    """Connect to target BankScope database."""
    params = {
        "host": DB_HOST,
        "port": DB_PORT,
        "dbname": DB_NAME,
        "user": DB_USER,
        "password": DB_PASSWORD,
    }
    if DB_SSLMODE:
        params["sslmode"] = DB_SSLMODE
    return psycopg2.connect(**params)


def create_database_if_not_exists():
    """Ensure BankScope PostgreSQL database exists."""
    print(f"[*] Checking PostgreSQL database '{DB_NAME}' on {DB_HOST}:{DB_PORT}...")
    try:
        conn = get_pg_connection()
        conn.close()
        print(f"[OK] Database '{DB_NAME}' is ready for schema creation.")
        return
    except Exception:
        pass

    try:
        conn = get_pg_admin_connection()
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (DB_NAME,))
        exists = cursor.fetchone()
        if not exists:
            print(f"[+] Creating database '{DB_NAME}'...")
            cursor.execute(f'CREATE DATABASE "{DB_NAME}";')
            print(f"[OK] Database '{DB_NAME}' created successfully.")
        else:
            print(f"[OK] Database '{DB_NAME}' already exists.")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[*] Note on database verification: {e}")


def execute_sql_file(conn, filepath, description):
    """Execute all SQL statements in a file."""
    print(f"[*] Applying {description} ({os.path.basename(filepath)})...")
    start_t = time.time()
    with open(filepath, "r", encoding="utf-8") as f:
        sql_content = f.read()

    with conn.cursor() as cursor:
        cursor.execute(sql_content)
    conn.commit()
    elapsed = round(time.time() - start_t, 2)
    print(f"[OK] Applied {description} in {elapsed}s.")


def bulk_copy_table(sqlite_conn, pg_conn, table_name, columns, chunk_size=50000):
    """Bulk stream data from SQLite to PostgreSQL using COPY FROM STDIN."""
    print(f"[*] Migrating table '{table_name}'...")
    start_t = time.time()
    sqlite_cursor = sqlite_conn.cursor()

    col_str = ", ".join([f'"{c}"' for c in columns])
    sqlite_cursor.execute(f"SELECT {col_str} FROM `{table_name}`;")

    pg_cursor = pg_conn.cursor()
    copy_sql = f"COPY {table_name} ({col_str}) FROM STDIN WITH (FORMAT CSV, HEADER FALSE, NULL '\\N');"

    total_rows = 0
    while True:
        rows = sqlite_cursor.fetchmany(chunk_size)
        if not rows:
            break

        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        for row in rows:
            # Replace None with \N for postgres CSV null handling
            clean_row = [("\\N" if val is None else str(val)) for val in row]
            buf.write("\t".join(clean_row) + "\n")

        buf.seek(0)
        pg_cursor.copy_from(buf, table_name, columns=columns, null="\\N")
        total_rows += len(rows)

    pg_conn.commit()
    pg_cursor.close()
    sqlite_cursor.close()
    elapsed = round(time.time() - start_t, 2)
    print(f"[OK] Migrated '{table_name}': {total_rows:,} rows in {elapsed}s.")
    return total_rows, elapsed


def run_migration():
    """Main migration entrypoint."""
    overall_start = time.time()
    print("=================================================================")
    print(f"BankScope Database Migration Engine")
    print(f"Canonical Source : {SQLITE_PATH}")
    print(f"Target Database  : {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print("=================================================================")

    if not os.path.exists(SQLITE_PATH):
        raise FileNotFoundError(f"Canonical SQLite database not found at: {SQLITE_PATH}")

    # 1. Check/Create database
    create_database_if_not_exists()

    # 2. Connect to target DB
    pg_conn = get_pg_connection()

    # 3. Apply schema (Base tables + PKs, without FKs/indexes for high-speed ingestion)
    execute_sql_file(pg_conn, SCHEMA_SQL_PATH, "Base Schema & Primary Keys")

    # 4. Connect to SQLite read-only
    sqlite_conn = sqlite3.connect(f"file:{SQLITE_PATH}?mode=ro", uri=True)

    # 5. Bulk copy data table by table
    loaded_stats = {}
    for table_name, columns in TABLES_ORDER:
        rows, elap = bulk_copy_table(sqlite_conn, pg_conn, table_name, columns)
        loaded_stats[table_name] = {"rows": rows, "time_s": elap}

    sqlite_conn.close()

    # 6. Apply foreign keys and business check constraints
    execute_sql_file(pg_conn, CONSTRAINTS_SQL_PATH, "Relational & CHECK Constraints")

    # 7. Apply analytical and join indexes
    execute_sql_file(pg_conn, INDEXES_SQL_PATH, "Performance & Analytical Indexes")

    pg_conn.close()

    total_time = round(time.time() - overall_start, 2)
    print("=================================================================")
    print(f"[OK] Migration completed successfully in {total_time} seconds!")
    print("=================================================================")
    return loaded_stats, total_time


if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"\n[!] Migration Failed: {e}", file=sys.stderr)
        sys.exit(1)
