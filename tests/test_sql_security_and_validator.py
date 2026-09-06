"""
BankScope NL-SQL Security and Validation Test Suite
Safe for CI/CD execution without external database credentials.
Verifies single-statement SELECT/WITH enforcement, DDL/DML rejection,
comment stripping, CTE handling, and markdown cleaning.
"""

import os
import sys
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dashboard.sql_generator import (
    validate_sql_security,
    clean_sql,
    get_dataset_schema_context,
    FORBIDDEN_KEYWORDS,
)


class TestSQLSecurityValidator(unittest.TestCase):
    """Test SQL safety and security validation rules."""

    def test_clean_sql_markdown_removal(self):
        markdown_sql = "```sql\nSELECT * FROM customers;\n```"
        self.assertEqual(clean_sql(markdown_sql), "SELECT * FROM customers;")

        generic_markdown = "```\nSELECT account_id FROM accounts LIMIT 5;\n```"
        self.assertEqual(clean_sql(generic_markdown), "SELECT account_id FROM accounts LIMIT 5;")

        raw_sql = "  SELECT balance_usd FROM accounts;  "
        self.assertEqual(clean_sql(raw_sql), "SELECT balance_usd FROM accounts;")

    def test_valid_select_queries(self):
        valid_queries = [
            "SELECT * FROM customers LIMIT 10;",
            "SELECT account_type, SUM(balance_usd) FROM accounts GROUP BY account_type;",
            "select count(*) from transactions where amount_usd > 500;",
            """
            SELECT 
                c.customer_id, 
                c.first_name || ' ' || c.last_name AS full_name,
                SUM(a.balance_usd) AS total_balance
            FROM customers c
            JOIN accounts a ON c.customer_id = a.customer_id
            GROUP BY c.customer_id, full_name
            ORDER BY total_balance DESC
            LIMIT 15;
            """,
        ]
        for q in valid_queries:
            is_valid, msg = validate_sql_security(q)
            self.assertTrue(is_valid, f"Expected valid query: {q}, got error: {msg}")
            self.assertEqual(msg, "")

    def test_valid_cte_with_queries(self):
        valid_cte = [
            """
            WITH ranked_customers AS (
                SELECT 
                    customer_id,
                    credit_score,
                    DENSE_RANK() OVER (ORDER BY credit_score DESC) as rk
                FROM customers
            )
            SELECT * FROM ranked_customers WHERE rk <= 10;
            """,
            """
            WITH monthly_vol AS (
                SELECT 
                    DATE_TRUNC('month', transaction_date)::DATE AS txn_month,
                    SUM(amount_usd) AS volume
                FROM transactions
                GROUP BY 1
            )
            SELECT txn_month, volume FROM monthly_vol ORDER BY txn_month;
            """
        ]
        for q in valid_cte:
            is_valid, msg = validate_sql_security(q)
            self.assertTrue(is_valid, f"Expected valid CTE: {q}, got error: {msg}")
            self.assertEqual(msg, "")

    def test_rejection_of_forbidden_dml_and_ddl(self):
        forbidden_test_cases = [
            ("INSERT INTO customers (customer_id) VALUES ('123');", "INSERT"),
            ("UPDATE accounts SET balance_usd = 0 WHERE account_id = 'A1';", "UPDATE"),
            ("DELETE FROM transactions WHERE amount_usd < 10;", "DELETE"),
            ("DROP TABLE customers;", "DROP"),
            ("ALTER TABLE accounts ADD COLUMN test_col int;", "ALTER"),
            ("TRUNCATE TABLE cards;", "TRUNCATE"),
            ("CREATE TABLE test_tbl (id int);", "CREATE"),
            ("GRANT ALL ON customers TO public;", "GRANT"),
            ("REVOKE ALL ON customers FROM public;", "REVOKE"),
            ("VACUUM FULL accounts;", "VACUUM"),
            ("ANALYZE transactions;", "ANALYZE"),
            ("COPY customers TO '/tmp/out.csv';", "COPY"),
        ]
        for q, kw in forbidden_test_cases:
            is_valid, msg = validate_sql_security(q)
            self.assertFalse(is_valid, f"Expected rejection of forbidden statement: {q}")
            self.assertIn("Security Policy Violation", msg)

    def test_rejection_of_embedded_forbidden_keywords(self):
        embedded_tests = [
            "SELECT * FROM customers; DROP TABLE accounts;",
            "SELECT 1; DELETE FROM cards;",
            "SELECT * FROM accounts WHERE balance_usd > (SELECT 0); ALTER TABLE accounts DROP COLUMN balance_usd;",
            "SELECT * FROM customers; INSERT INTO audit_log VALUES (1);",
        ]
        for q in embedded_tests:
            is_valid, msg = validate_sql_security(q)
            self.assertFalse(is_valid, f"Expected rejection of embedded payload: {q}")
            self.assertIn("Security Policy Violation", msg)

    def test_rejection_of_multiple_semicolons(self):
        chained = "SELECT 1; SELECT 2;"
        is_valid, msg = validate_sql_security(chained)
        self.assertFalse(is_valid)
        self.assertIn("Multiple chained SQL statements", msg)

    def test_rejection_of_empty_or_comments_only(self):
        self.assertFalse(validate_sql_security("")[0])
        self.assertFalse(validate_sql_security("   ")[0])
        self.assertFalse(validate_sql_security("-- Just a comment")[0])
        self.assertFalse(validate_sql_security("/* Multi line comment */")[0])

    def test_core_banking_schema_context_assembly(self):
        ctx = get_dataset_schema_context("BankScope Banking Data")
        self.assertEqual(ctx["dataset_name"], "BankScope Core Banking Warehouse (public)")
        self.assertIn("`customers` (50,000 rows)", ctx["context_string"])
        self.assertIn("`accounts` (75,000 rows)", ctx["context_string"])
        self.assertIn("`cards` (100,000 rows)", ctx["context_string"])
        self.assertIn("`loans` (30,000 rows)", ctx["context_string"])
        self.assertIn("`merchants` (5,000 rows)", ctx["context_string"])
        self.assertIn("`transactions` (1,000,000 rows", ctx["context_string"])
        self.assertIn("`branches` (500 rows", ctx["context_string"])
        self.assertEqual(len(ctx["tables"]), 7)


if __name__ == "__main__":
    unittest.main()
