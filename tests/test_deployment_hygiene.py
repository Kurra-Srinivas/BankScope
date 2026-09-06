"""
BankScope Deployment Hygiene & Repository Security Test Suite
Safe for CI/CD execution.
Verifies requirement completeness, gitignore rules, absence of committed secrets,
and configuration correctness.
"""

import os
import sys
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestDeploymentHygiene(unittest.TestCase):

    def test_requirements_file(self):
        req_path = os.path.join(BASE_DIR, "requirements.txt")
        self.assertTrue(os.path.isfile(req_path), "requirements.txt must exist.")
        with open(req_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_packages = [
            "streamlit",
            "pandas",
            "numpy",
            "sqlalchemy",
            "psycopg2-binary",
            "plotly",
            "python-dotenv",
            "requests",
            "sqlparse",
        ]
        for pkg in required_packages:
            self.assertIn(pkg, content, f"Required package '{pkg}' missing from requirements.txt")

    def test_gitignore_covers_sensitive_files(self):
        gitignore_path = os.path.join(BASE_DIR, ".gitignore")
        self.assertTrue(os.path.isfile(gitignore_path), ".gitignore must exist.")
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()

        sensitive_patterns = [
            ".env",
            ".streamlit/secrets.toml",
            "secrets.toml",
            "*.db",
            "*.sqlite",
            "data/",
            "scratch/",
        ]
        for pattern in sensitive_patterns:
            self.assertIn(pattern, content, f"Pattern '{pattern}' missing from .gitignore")

    def test_streamlit_config_integrity(self):
        config_path = os.path.join(BASE_DIR, ".streamlit", "config.toml")
        self.assertTrue(os.path.isfile(config_path), ".streamlit/config.toml must exist.")
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read().lower()

        # Must enforce dark theme
        self.assertIn('base = "dark"', content)
        # Must never contain secrets or credentials
        self.assertNotIn("password", content)
        self.assertNotIn("secret", content)
        self.assertNotIn("api_key", content)
        self.assertNotIn("gsk_", content)

    def test_env_example_has_placeholders_only(self):
        env_ex_path = os.path.join(BASE_DIR, ".env.example")
        self.assertTrue(os.path.isfile(env_ex_path), ".env.example must exist.")
        with open(env_ex_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Placeholders only
        self.assertIn("your_password_here", content)
        self.assertIn("your_groq_api_key_here", content)
        self.assertNotIn("gsk_c", content)


if __name__ == "__main__":
    unittest.main()
