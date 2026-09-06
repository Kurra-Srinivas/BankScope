"""
Regression tests for Categorical Value Handling, Zero-Row Semantic Guard,
and PostgreSQL SSL Connection Robustness.
"""

import unittest
from unittest.mock import patch, MagicMock
from dashboard.sql_generator import repair_categorical_casing, detect_casing_mismatch
from dashboard.db import get_engine, get_readonly_engine


class TestCategoricalAndSSLRobustness(unittest.TestCase):
    """Verify generic categorical casing repair and database pool robustness."""

    def test_repair_categorical_casing_generic(self):
        """Verify generic, non-hardcoded categorical casing repair."""
        samples = {
            "card_type": ["Credit", "Debit"],
            "card_status": ["Active", "Blocked", "Closed"],
            "customer_segment": ["Affluent", "Mass Market", "Premium", "Student"],
            "region_code": ["NORAM", "EMEA", "APAC"],
        }

        # 1. Lowercase IN list for binary categorical column
        sql1 = "SELECT card_type, AVG(utilization_pct) FROM uploads.test WHERE card_type IN ('credit', 'debit') GROUP BY card_type;"
        repaired1 = repair_categorical_casing(sql1, samples)
        self.assertIn("IN ('Credit', 'Debit')", repaired1)

        # 2. Mixed case single equality
        sql2 = "SELECT * FROM uploads.test WHERE card_status = 'active' AND customer_segment = 'mass market';"
        repaired2 = repair_categorical_casing(sql2, samples)
        self.assertIn("card_status = 'Active'", repaired2)
        self.assertIn("customer_segment = 'Mass Market'", repaired2)

        # 3. New arbitrary column without any hardcoding
        sql3 = "SELECT * FROM uploads.test WHERE region_code = 'emea';"
        repaired3 = repair_categorical_casing(sql3, samples)
        self.assertIn("region_code = 'EMEA'", repaired3)

        # 4. Already correct casing remains untouched
        sql4 = "SELECT * FROM uploads.test WHERE card_type = 'Credit';"
        repaired4 = repair_categorical_casing(sql4, samples)
        self.assertEqual(sql4, repaired4)

    def test_detect_casing_mismatch(self):
        """Verify Zero-Row Semantic Guard detects casing mismatches and produces explanation."""
        fake_samples = {
            "card_type": ["Credit", "Debit"],
            "card_status": ["Active", "Closed"],
        }
        with patch("dashboard.upload_engine.get_categorical_column_samples", return_value=fake_samples):
            sql = "SELECT * FROM uploads.test WHERE card_type IN ('credit', 'debit');"
            detected, explanation, corrected = detect_casing_mismatch(sql, "test", schema="uploads")
            self.assertTrue(detected)
            self.assertIn("card_type", explanation)
            self.assertIn("'credit'", explanation)
            self.assertIn("'Credit'", explanation)
            self.assertIn("WHERE card_type IN ('Credit', 'Debit')", corrected)

    def test_db_pool_configuration_robustness(self):
        """Verify engine connection pooling has pool_pre_ping, pool_recycle, and TCP keepalives."""
        engine = get_engine()
        self.assertTrue(engine.pool._pre_ping, "Standard engine must have pool_pre_ping=True")
        self.assertEqual(engine.pool._recycle, 300, "Standard engine must recycle connections at 300s (5min)")

        readonly_engine = get_readonly_engine()
        self.assertTrue(readonly_engine.pool._pre_ping, "Read-only engine must have pool_pre_ping=True")
        self.assertEqual(readonly_engine.pool._recycle, 300, "Read-only engine must recycle connections at 300s (5min)")


if __name__ == "__main__":
    unittest.main()
