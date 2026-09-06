#!/usr/bin/env python3
"""
BankScope — PostgreSQL Data & Referential Integrity Validation Engine
Validates migrated PostgreSQL tables against canonical SQLite source.
"""

import os
import sys
import sqlite3
import psycopg2
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

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

TABLES = ["customers", "accounts", "cards", "loans", "merchants", "branches", "transactions"]
PK_MAP = {
    "customers": "customer_id",
    "accounts": "account_id",
    "cards": "card_id",
    "loans": "loan_id",
    "merchants": "merchant_id",
    "branches": "branch_id",
    "transactions": "transaction_id",
}


def run_validation():
    print("=================================================================")
    print("BankScope PostgreSQL Post-Migration Validation Engine")
    print(f"PostgreSQL Target: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"Canonical Source : {SQLITE_PATH}")
    print("=================================================================")

    pg_params = {
        "host": DB_HOST,
        "port": DB_PORT,
        "dbname": DB_NAME,
        "user": DB_USER,
        "password": DB_PASSWORD,
    }
    if DB_SSLMODE:
        pg_params["sslmode"] = DB_SSLMODE

    pg_conn = psycopg2.connect(**pg_params)
    sqlite_conn = sqlite3.connect(f"file:{SQLITE_PATH}?mode=ro", uri=True)

    pg_cur = pg_conn.cursor()
    sq_cur = sqlite_conn.cursor()

    all_passed = True
    validation_results = {}

    # 1. Row Count Validation
    print("\n--- 1. Row Count Verification ---")
    row_count_results = {}
    for tbl in TABLES:
        sq_cur.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
        sq_cnt = sq_cur.fetchone()[0]

        pg_cur.execute(f'SELECT COUNT(*) FROM "{tbl}";')
        pg_cnt = pg_cur.fetchone()[0]

        status = "PASS" if sq_cnt == pg_cnt else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] {tbl:14} | SQLite: {sq_cnt:9,} | PostgreSQL: {pg_cnt:9,}")
        row_count_results[tbl] = {"sqlite": sq_cnt, "postgres": pg_cnt, "status": status}

    validation_results["row_counts"] = row_count_results

    # 2. Primary Key Uniqueness
    print("\n--- 2. Primary Key Uniqueness Verification ---")
    pk_results = {}
    for tbl, pk in PK_MAP.items():
        pg_cur.execute(f'SELECT COUNT(*), COUNT(DISTINCT "{pk}") FROM "{tbl}";')
        total, distinct = pg_cur.fetchone()
        status = "PASS" if total == distinct else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] {tbl:14} ({pk}) | Total: {total:9,} | Unique: {distinct:9,}")
        pk_results[tbl] = {"total": total, "distinct": distinct, "status": status}

    validation_results["primary_keys"] = pk_results

    # 3. Foreign Key Integrity Audit
    print("\n--- 3. Referential Foreign Key Integrity Audit ---")
    fk_checks = [
        ("accounts", "customer_id", "customers", "customer_id"),
        ("cards", "account_id", "accounts", "account_id"),
        ("loans", "customer_id", "customers", "customer_id"),
        ("transactions", "account_id", "accounts", "account_id"),
        ("transactions", "merchant_id", "merchants", "merchant_id"),
    ]
    fk_results = {}
    for child_tbl, child_fk, parent_tbl, parent_pk in fk_checks:
        query = f"""
            SELECT COUNT(*) 
            FROM "{child_tbl}" c 
            LEFT JOIN "{parent_tbl}" p ON c."{child_fk}" = p."{parent_pk}" 
            WHERE p."{parent_pk}" IS NULL;
        """
        pg_cur.execute(query)
        orphans = pg_cur.fetchone()[0]
        status = "PASS" if orphans == 0 else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] {child_tbl}.{child_fk} -> {parent_tbl}.{parent_pk} | Orphans: {orphans}")
        fk_results[f"{child_tbl}->{parent_tbl}"] = {"orphans": orphans, "status": status}

    validation_results["foreign_keys"] = fk_results

    # 4. Statistical Bounds & Ledger Audit
    print("\n--- 4. Transactions Statistical Parity Audit ---")
    sq_cur.execute("SELECT MIN(transaction_date), MAX(transaction_date), MIN(amount_usd), MAX(amount_usd), ROUND(AVG(amount_usd), 2) FROM transactions;")
    sq_stats = sq_cur.fetchone()

    pg_cur.execute("SELECT MIN(transaction_date)::TEXT, MAX(transaction_date)::TEXT, MIN(amount_usd)::NUMERIC, MAX(amount_usd)::NUMERIC, ROUND(AVG(amount_usd), 2)::NUMERIC FROM transactions;")
    pg_stats = pg_cur.fetchone()

    stats_match = (
        str(sq_stats[0]) == str(pg_stats[0])
        and str(sq_stats[1]) == str(pg_stats[1])
        and float(sq_stats[2]) == float(pg_stats[2])
        and float(sq_stats[3]) == float(pg_stats[3])
    )
    status = "PASS" if stats_match else "FAIL"
    if status == "FAIL":
        all_passed = False

    print(f"  [{status}] Date Range : SQLite [{sq_stats[0]} to {sq_stats[1]}]")
    print(f"         Postgres [{pg_stats[0]} to {pg_stats[1]}]")
    print(f"  [{status}] Amount Min/Max/Avg : SQLite [{sq_stats[2]} / {sq_stats[3]} / {sq_stats[4]}]")
    print(f"                       Postgres [{pg_stats[2]} / {pg_stats[3]} / {pg_stats[4]}]")
    validation_results["transaction_stats"] = {"status": status}

    # 5. Financial Exposure & Ledger Totals Audit
    print("\n--- 5. Financial Exposure & Ledger Totals Audit ---")
    sq_cur.execute("SELECT SUM(amount_usd) FROM transactions;")
    sq_txn_sum = sq_cur.fetchone()[0]
    pg_cur.execute("SELECT SUM(amount_usd)::NUMERIC FROM transactions;")
    pg_txn_sum = pg_cur.fetchone()[0]
    txn_match = abs(float(sq_txn_sum) - float(pg_txn_sum)) < 0.01

    sq_cur.execute("SELECT SUM(balance_usd) FROM accounts;")
    sq_dep_sum = sq_cur.fetchone()[0]
    pg_cur.execute("SELECT SUM(balance_usd)::NUMERIC FROM accounts;")
    pg_dep_sum = pg_cur.fetchone()[0]
    dep_match = abs(float(sq_dep_sum) - float(pg_dep_sum)) < 0.01

    sq_cur.execute("SELECT SUM(loan_amount) FROM loans;")
    sq_loan_sum = sq_cur.fetchone()[0]
    pg_cur.execute("SELECT SUM(loan_amount)::NUMERIC FROM loans;")
    pg_loan_sum = pg_cur.fetchone()[0]
    loan_match = abs(float(sq_loan_sum) - float(pg_loan_sum)) < 0.01

    print(f"  [{'PASS' if txn_match else 'FAIL'}] Transaction Vol : SQLite [${sq_txn_sum:,.2f}] | Postgres [${pg_txn_sum:,.2f}]")
    print(f"  [{'PASS' if dep_match else 'FAIL'}] Total Deposits  : SQLite [${sq_dep_sum:,.2f}] | Postgres [${pg_dep_sum:,.2f}]")
    print(f"  [{'PASS' if loan_match else 'FAIL'}] Loan Exposure   : SQLite [${sq_loan_sum:,.2f}] | Postgres [${pg_loan_sum:,.2f}]")

    if not (txn_match and dep_match and loan_match):
        all_passed = False

    pg_cur.close()
    pg_conn.close()
    sq_cur.close()
    sqlite_conn.close()

    print("\n=================================================================")
    if all_passed:
        print("[ALL PASSED] ALL VALIDATION CHECKS PASSED PERFECTLY!")
    else:
        print("[FAILED] ONE OR MORE VALIDATION CHECKS FAILED.")
    print("=================================================================")
    return all_passed, validation_results


if __name__ == "__main__":
    passed, _ = run_validation()
    sys.exit(0 if passed else 1)
