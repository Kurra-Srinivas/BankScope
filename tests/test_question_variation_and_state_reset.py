"""
Unit tests proving that different questions produce different SQL
and that state/caching never reuses previous SQL across questions.
"""

import os
import sys
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dashboard.sql_generator import generate_sql_query, clean_sql
from dashboard.llm_provider import OfflineBankingSQLProvider, BaseLLMProvider


class TestQuestionVariationAndStateReset(unittest.TestCase):

    def setUp(self):
        self.provider = OfflineBankingSQLProvider()
        # Mock schema context string for uploads
        self.fake_dataset = "BankScope Banking Data"

    def test_distinct_sql_for_distinct_questions_offline(self):
        """Prove that different questions generate completely distinct SQL queries."""
        q1 = "What is the average credit limit by customer segment?"
        q2 = "Which card status has the highest total monthly spend?"
        q3 = "Compare average utilization percentage between credit and debit cards."
        q4 = "What percentage of cards are active, blocked, and closed?"

        # We test on an uploads dataset context
        # OfflineBankingSQLProvider generates uploads queries when schema mentions uploads
        prompt_sys = "Schema: uploads\nTarget Table: `uploads.test_cards`"
        
        sql1 = self.provider.generate_text(f"User Question: {q1}", system_instruction=prompt_sys)
        sql2 = self.provider.generate_text(f"User Question: {q2}", system_instruction=prompt_sys)
        sql3 = self.provider.generate_text(f"User Question: {q3}", system_instruction=prompt_sys)
        sql4 = self.provider.generate_text(f"User Question: {q4}", system_instruction=prompt_sys)

        # Assert Q1 SQL is NOT reused for Q2, Q3, or Q4
        self.assertNotEqual(sql1, sql2, "Q2 must NOT produce Q1 SQL!")
        self.assertNotEqual(sql1, sql3, "Q3 must NOT produce Q1 SQL!")
        self.assertNotEqual(sql1, sql4, "Q4 must NOT produce Q1 SQL!")
        self.assertNotEqual(sql2, sql3, "Q3 must NOT produce Q2 SQL!")
        self.assertNotEqual(sql2, sql4, "Q4 must NOT produce Q2 SQL!")
        self.assertNotEqual(sql3, sql4, "Q4 must NOT produce Q3 SQL!")

        # Q1 assertions
        self.assertIn("customer_segment", sql1.lower())
        self.assertIn("credit_limit", sql1.lower())
        self.assertIn("avg", sql1.lower())

        # Q2 assertions
        self.assertIn("card_status", sql2.lower())
        self.assertIn("monthly_spend", sql2.lower())
        self.assertIn("sum", sql2.lower())
        self.assertIn("order by", sql2.lower())

        # Q3 assertions
        self.assertIn("card_type", sql3.lower())
        self.assertIn("utilization_pct", sql3.lower())
        self.assertIn("avg", sql3.lower())

        # Q4 assertions
        self.assertIn("card_status", sql4.lower())
        self.assertIn("count", sql4.lower())
        self.assertTrue("percent" in sql4.lower() or "100.0" in sql4)

    def test_generate_sql_query_does_not_cache_across_invocations(self):
        """Prove that generate_sql_query evaluates the current question dynamically."""
        q1 = "Who are the top 15 customers by total deposit balances across their accounts?"
        q2 = "What is the total transaction volume and count broken down by month?"

        res1 = generate_sql_query(q1, "BankScope Banking Data", provider=self.provider)
        res2 = generate_sql_query(q2, "BankScope Banking Data", provider=self.provider)

        self.assertNotEqual(res1["sql"], res2["sql"])
        self.assertEqual(res1["question"], q1)
        self.assertEqual(res2["question"], q2)
        self.assertIn("customers", res1["sql"].lower())
        self.assertIn("transactions", res2["sql"].lower())

    def test_custom_provider_dynamic_response(self):
        """Simulate an LLM provider receiving sequential calls and ensure outputs are not cached."""
        class MockLLM(BaseLLMProvider):
            name = "MockLLM"
            def is_available(self):
                return True
            def generate_text(self, prompt: str, system_instruction: str = "") -> str:
                if "spend" in prompt:
                    return "SELECT card_status, SUM(monthly_spend) FROM uploads.cards GROUP BY 1;"
                return "SELECT customer_segment, AVG(credit_limit) FROM uploads.cards GROUP BY 1;"

        mock = MockLLM()
        res_a = generate_sql_query("Q with spend", "BankScope Banking Data", provider=mock)
        res_b = generate_sql_query("Q with segment", "BankScope Banking Data", provider=mock)

        self.assertIn("monthly_spend", res_a["sql"])
        self.assertIn("credit_limit", res_b["sql"])
        self.assertNotEqual(res_a["sql"], res_b["sql"])


if __name__ == "__main__":
    unittest.main()
