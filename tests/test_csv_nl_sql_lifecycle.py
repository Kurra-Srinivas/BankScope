"""
BankScope CSV -> NL-SQL Lifecycle, Stale Detection, and Numeric Cast Test Suite
Tests all 13 production regression requirements for the CSV -> NL-SQL flow.
Safe for both local execution and CI/CD execution.
"""

import os
import sys
import unittest
import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dashboard.upload_engine import (
    sanitize_identifier,
    generate_unique_table_name,
    table_exists_in_db,
    get_all_uploaded_tables,
    get_uploaded_table_data,
    delete_uploaded_table,
)
from dashboard.sql_generator import (
    repair_postgres_numeric_casts,
    validate_sql_security,
    validate_with_postgres_explain,
    execute_approved_sql,
    get_dataset_schema_context,
)
from dashboard.llm_provider import OfflineBankingSQLProvider


class TestCSVNLSQLProductionLifecycle(unittest.TestCase):

    def test_01_numeric_cast_repair_avg(self):
        """Test generic repair of ROUND(AVG(col), 2) for PostgreSQL double precision."""
        raw_sql = "SELECT customer_segment, ROUND(AVG(credit_limit), 2) AS avg_limit FROM uploads.cards GROUP BY 1;"
        repaired = repair_postgres_numeric_casts(raw_sql)
        self.assertIn("::numeric", repaired)
        self.assertIn("ROUND((AVG(credit_limit))::numeric, 2)", repaired)

    def test_02_numeric_cast_repair_sum_and_multi(self):
        """Test generic repair of multiple ROUND calls in one query."""
        raw_sql = (
            "SELECT card_status, "
            "ROUND(SUM(monthly_spend), 2) AS total_spend, "
            "ROUND(AVG(utilization_pct), 4) AS avg_util "
            "FROM uploads.cards GROUP BY 1;"
        )
        repaired = repair_postgres_numeric_casts(raw_sql)
        self.assertIn("ROUND((SUM(monthly_spend))::numeric, 2)", repaired)
        self.assertIn("ROUND((AVG(utilization_pct))::numeric, 4)", repaired)

    def test_03_numeric_cast_idempotent(self):
        """Test that already-cast queries are NOT altered."""
        proper_sql = "SELECT ROUND(AVG(credit_limit)::numeric, 2) FROM uploads.cards;"
        repaired = repair_postgres_numeric_casts(proper_sql)
        self.assertEqual(repaired, proper_sql)

    def test_04_numeric_cast_percentage_calculation(self):
        """Test repair of percentage arithmetic expressions inside ROUND."""
        raw_sql = "SELECT card_status, ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct FROM uploads.cards GROUP BY 1;"
        repaired = repair_postgres_numeric_casts(raw_sql)
        self.assertIn("::numeric", repaired)

    def test_05_physical_table_existence_check(self):
        """Test table_exists_in_db rejects malicious names and missing tables."""
        self.assertFalse(table_exists_in_db("nonexistent_table_xyz_999"))
        self.assertFalse(table_exists_in_db(""))
        self.assertFalse(table_exists_in_db("table; DROP TABLE users;--"))

    def test_06_stale_table_detection_in_schema_context(self):
        """Test get_dataset_schema_context raises FileNotFoundError if upload table is gone."""
        with self.assertRaises(FileNotFoundError):
            get_dataset_schema_context("upload:sess_missing_table_2026")

    def test_07_stale_table_detection_in_explain(self):
        """Test validate_with_postgres_explain rejects queries targeting nonexistent upload tables."""
        sql = "SELECT * FROM uploads.sess_ghost_table_xyz_999 LIMIT 10;"
        is_valid, msg = validate_with_postgres_explain(sql)
        self.assertFalse(is_valid)
        self.assertIn("does not exist in PostgreSQL", msg)

    def test_08_stale_table_detection_in_execution(self):
        """Test execute_approved_sql blocks execution on nonexistent upload tables."""
        sql = "SELECT * FROM uploads.sess_ghost_table_xyz_999 LIMIT 10;"
        res = execute_approved_sql(sql)
        self.assertFalse(res["success"])
        self.assertIn("does not exist in PostgreSQL", res["error_message"])

    def test_09_offline_provider_generates_valid_numeric_sql(self):
        """Test that OfflineBankingSQLProvider generates valid ::numeric cast SQL."""
        provider = OfflineBankingSQLProvider()
        sys_inst = "Schema: uploads\nTarget Table: `uploads.sess_test_table`"
        
        q1 = "What is the average credit limit by customer segment?"
        sql1 = provider.generate_text(q1, system_instruction=sys_inst)
        self.assertIn("::numeric", sql1)
        self.assertIn("customer_segment", sql1)

        q2 = "Which card status has the highest total monthly spend?"
        sql2 = provider.generate_text(q2, system_instruction=sys_inst)
        self.assertIn("::numeric", sql2)
        self.assertIn("monthly_spend", sql2)

        q3 = "Compare average utilization percentage between credit and debit cards."
        sql3 = provider.generate_text(q3, system_instruction=sys_inst)
        self.assertIn("::numeric", sql3)
        self.assertIn("utilization_pct", sql3)

    def test_10_cross_session_isolation(self):
        """Test that session A table is not accessible to session B."""
        # Querying an unwhitelisted table must raise PermissionError
        with self.assertRaises(PermissionError):
            get_uploaded_table_data("sess_userA_secret_table", allowed_tables=["sess_userB_table"])

        # An empty session whitelist returns an empty DataFrame
        df = get_all_uploaded_tables(allowed_tables=[])
        self.assertTrue(df.empty)

    def test_11_sql_security_guardrails_intact(self):
        """Test that DML, DDL, and multi-statement injection remain blocked."""
        self.assertFalse(validate_sql_security("DROP TABLE accounts;")[0])
        self.assertFalse(validate_sql_security("DELETE FROM transactions;")[0])
        self.assertFalse(validate_sql_security("SELECT 1; DROP TABLE cards;")[0])
        self.assertFalse(validate_sql_security("INSERT INTO customers VALUES (1);")[0])


if __name__ == "__main__":
    unittest.main()
