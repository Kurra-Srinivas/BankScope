"""
BankScope CSV Upload Safety & Session Scoping Tests
Safe for CI/CD execution without external database credentials.
Verifies file format constraints, 50MB file size limits, SQL identifier
sanitization, session table naming, and access permission checks.
"""

import os
import sys
import io
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dashboard.upload_engine import (
    validate_csv_file,
    generate_unique_table_name,
    sanitize_identifier,
    get_all_uploaded_tables,
    get_uploaded_table_data,
    MAX_FILE_SIZE_BYTES,
)


class MockUploadedFile:
    def __init__(self, name: str, size: int, content: bytes = b""):
        self.name = name
        self.size = size
        self._buffer = io.BytesIO(content)

    def read(self, *args):
        return self._buffer.read(*args)

    def seek(self, *args):
        return self._buffer.seek(*args)


class TestCSVUploadSafety(unittest.TestCase):

    def test_file_format_and_extension_validation(self):
        # Non-CSV extensions must be rejected
        for bad_name in ["data.xlsx", "data.json", "data.parquet", "script.py", "data.csv.exe"]:
            valid, msg = validate_csv_file(MockUploadedFile(bad_name, 1024))
            self.assertFalse(valid)
            self.assertIn("Only CSV files", msg)

        # Empty file (0 bytes) must be rejected
        valid, msg = validate_csv_file(MockUploadedFile("empty.csv", 0))
        self.assertFalse(valid)
        self.assertIn("empty (0 bytes)", msg)

        # File exceeding 50 MB limit must be rejected
        valid, msg = validate_csv_file(MockUploadedFile("big.csv", MAX_FILE_SIZE_BYTES + 1024))
        self.assertFalse(valid)
        self.assertIn("exceeds maximum allowed limit of 50 MB", msg)

        # Valid CSV passes
        valid, msg = validate_csv_file(MockUploadedFile("valid.csv", 2048, b"a,b\n1,2"))
        self.assertTrue(valid)
        self.assertEqual(msg, "")

    def test_identifier_sanitization(self):
        cases = [
            ("Customer Name!", "customer_name"),
            ("123 Total Volume", "col_123_total_volume"),
            ("balance (USD)", "balance_usd"),
            ("DROP TABLE;--", "drop_table"),
            ("___weird___name___", "weird_name"),
            ("", "unnamed_col"),
        ]
        for raw, expected in cases:
            cleaned = sanitize_identifier(raw)
            self.assertEqual(cleaned, expected)
            self.assertRegex(cleaned, r"^[a-z0-9_]+$")

    def test_session_scoped_table_naming(self):
        # When session_id is provided, table name must start with sess_ and include sanitized session token
        name = generate_unique_table_name("loan_records_2026.csv", session_id="user_sess_abc123")
        self.assertTrue(name.startswith("sess_user_sess_a"))
        self.assertIn("loan_records_2026", name)
        self.assertRegex(name, r"^[a-z0-9_]+$")
        self.assertLessEqual(len(name), 60)

    def test_unauthorized_cross_session_table_access_blocked(self):
        # Accessing an uploaded table not belonging to this session must raise PermissionError
        with self.assertRaises(PermissionError):
            get_uploaded_table_data("sess_alien_table_123", limit=10, allowed_tables=["sess_my_table"])

        # Invalid table name format must raise ValueError
        with self.assertRaises(ValueError):
            get_uploaded_table_data("sess_table; DROP TABLE users;--", limit=10, allowed_tables=None)


if __name__ == "__main__":
    unittest.main()
