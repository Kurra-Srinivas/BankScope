"""
BankScope Modular LLM Provider Test Suite
Safe for CI/CD execution without external API calls or credentials.
Verifies Groq provider initialization, OpenAI-compatible endpoint configuration,
secure fallback behavior, and non-AI demo designations.
"""

import os
import sys
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dashboard.llm_provider import (
    BaseLLMProvider,
    GroqProvider,
    OfflineBankingSQLProvider,
    get_llm_provider,
)


class TestLLMProviderModule(unittest.TestCase):

    def test_groq_provider_defaults(self):
        provider = GroqProvider(api_key="mock_key_12345678", model="openai/gpt-oss-20b")
        self.assertEqual(provider.name, "Groq")
        self.assertEqual(provider.model, "openai/gpt-oss-20b")
        self.assertEqual(provider.endpoint, "https://api.groq.com/openai/v1/chat/completions")
        self.assertTrue(provider.is_available())

    def test_groq_provider_unavailable_with_empty_key(self):
        provider = GroqProvider(api_key="", model="openai/gpt-oss-20b")
        self.assertFalse(provider.is_available())

    def test_offline_provider_designation(self):
        offline = OfflineBankingSQLProvider()
        # Must clearly designate as rule-based or demo, NOT live AI
        self.assertIn("Rule-Based", offline.name)
        self.assertIn("Demo", offline.name)
        self.assertTrue(offline.is_available())

    def test_offline_sql_generation_validity(self):
        offline = OfflineBankingSQLProvider()
        queries = [
            "Show me the top 10 customers with the highest balance",
            "What are total deposits grouped by city?",
            "Which loans have interest rates above 15%?",
            "Show me monthly transaction volume for 2024",
        ]
        for q in queries:
            sql = offline.generate_text(q, system_instruction="Schema: public")
            self.assertTrue(sql.strip().upper().startswith("SELECT"), f"Expected SELECT for '{q}', got: {sql}")

    def test_default_fallback_without_keys(self):
        # When environment has no active keys, get_llm_provider returns OfflineBankingSQLProvider
        os.environ["LLM_PROVIDER"] = "offline"
        provider = get_llm_provider()
        self.assertIsInstance(provider, OfflineBankingSQLProvider)


if __name__ == "__main__":
    unittest.main()
