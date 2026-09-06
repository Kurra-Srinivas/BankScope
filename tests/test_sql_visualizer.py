"""
Unit and regression tests for BankScope SQL Result Visualization Engine (sql_visualizer.py).
Verifies deterministic chart selection based on result semantics and data geometry.
"""

import unittest
import pandas as pd
import plotly.graph_objects as go
from dashboard.sql_visualizer import generate_result_visualization


class TestSQLVisualizer(unittest.TestCase):
    """Test suite for deterministic Plotly visualization selection."""

    def test_avg_utilization_by_card_type_uses_bar_chart(self):
        """
        Query: 'Compare average utilization percentage between credit and debit cards.'
        Must produce a BAR chart (NOT a pie/donut chart showing 50%/50%).
        """
        df = pd.DataFrame({
            "card_type": ["Credit", "Debit"],
            "avg_utilization_pct": [28.23, 28.24]
        })
        fig = generate_result_visualization(df)
        self.assertIsNotNone(fig, "Chart must be generated")
        
        # Verify it is a bar chart, not a pie chart
        trace_types = [t.type for t in fig.data]
        self.assertIn("bar", trace_types, f"Expected 'bar' trace, got {trace_types}")
        self.assertNotIn("pie", trace_types, "Pie/donut chart must NOT be used for average utilization!")

        # Verify values in chart traces
        y_vals = []
        for t in fig.data:
            if hasattr(t, "y") and t.y is not None:
                y_vals.extend(list(t.y))
        self.assertIn(28.23, y_vals)
        self.assertIn(28.24, y_vals)

    def test_avg_credit_limit_by_segment_uses_bar_chart(self):
        """
        Query: 'What is the average credit limit by customer segment?'
        Must produce a BAR chart.
        """
        df = pd.DataFrame({
            "customer_segment": ["Mass Market", "Student", "Affluent", "Premium"],
            "avg_credit_limit": [36904.09, 16890.99, 95937.29, 202590.20]
        })
        fig = generate_result_visualization(df)
        self.assertIsNotNone(fig)
        trace_types = [t.type for t in fig.data]
        self.assertIn("bar", trace_types)
        self.assertNotIn("pie", trace_types)

    def test_highest_monthly_spend_ranking_uses_horizontal_bar(self):
        """
        Query: 'Which card status has the highest total monthly spend?'
        Must produce a ranking BAR chart (horizontal).
        """
        df = pd.DataFrame({
            "card_status": ["Active", "Closed", "Blocked"],
            "total_monthly_spend": [13502116.71, 2100000.0, 1500000.0]
        })
        fig = generate_result_visualization(df)
        self.assertIsNotNone(fig)
        self.assertEqual(fig.data[0].type, "bar")
        self.assertEqual(fig.data[0].orientation, "h", "Ranking query should use horizontal bar orientation")

    def test_time_series_uses_line_chart(self):
        """
        Monthly volume / timeline queries must produce a LINE chart.
        """
        df = pd.DataFrame({
            "transaction_month": ["2024-01-01", "2024-02-01", "2024-03-01"],
            "total_volume_usd": [5000000.0, 5200000.0, 5100000.0]
        })
        fig = generate_result_visualization(df)
        self.assertIsNotNone(fig)
        self.assertEqual(fig.data[0].type, "scatter")
        self.assertIn("lines", fig.data[0].mode)

    def test_explicit_percentage_composition_uses_donut_chart(self):
        """
        Query: 'What percentage of cards are active, blocked, and closed?'
        Explicit composition / distribution query sums to 100% -> DONUT chart.
        """
        df = pd.DataFrame({
            "card_status": ["Active", "Closed", "Blocked"],
            "percentage": [71.4, 16.3, 12.3]
        })
        fig = generate_result_visualization(df)
        self.assertIsNotNone(fig)
        self.assertEqual(fig.data[0].type, "pie")
        self.assertGreaterEqual(fig.data[0].hole, 0.4, "Must be a donut chart with hole >= 0.4")

    def test_two_metrics_with_large_scale_difference_uses_dual_axis(self):
        """
        Query: 'For each customer segment, show the average credit limit and average monthly spend.'
        Credit limit ($100k) vs Monthly spend ($5k) has ~20x scale ratio.
        Must use dual-axis bar chart (secondary_y).
        """
        df = pd.DataFrame({
            "customer_segment": ["Mass Market", "Student", "Affluent", "Premium"],
            "avg_credit_limit": [36904.09, 16890.99, 95937.29, 202590.20],
            "avg_monthly_spend": [1500.0, 600.0, 4500.0, 12000.0]
        })
        fig = generate_result_visualization(df)
        self.assertIsNotNone(fig)
        self.assertEqual(len(fig.data), 2, "Must have two bar traces")
        self.assertEqual(fig.data[0].type, "bar")
        self.assertEqual(fig.data[1].type, "bar")
        # Check secondary y-axis assignment
        self.assertEqual(fig.data[1].yaxis, "y2", "Second trace must be mapped to secondary y-axis (y2)")

    def test_two_metrics_with_comparable_scales_uses_grouped_bar(self):
        """
        Two metrics with similar scales (ratio <= 3.0) should use standard grouped bar.
        """
        df = pd.DataFrame({
            "customer_segment": ["Mass Market", "Student", "Affluent", "Premium"],
            "metric_a": [100.0, 200.0, 300.0, 400.0],
            "metric_b": [120.0, 180.0, 250.0, 380.0]
        })
        fig = generate_result_visualization(df)
        self.assertIsNotNone(fig)
        self.assertEqual(fig.data[0].type, "bar")

    def test_empty_or_single_column_returns_none(self):
        """
        Empty DataFrame or single scalar value should not generate a chart.
        """
        self.assertIsNone(generate_result_visualization(pd.DataFrame()))
        self.assertIsNone(generate_result_visualization(pd.DataFrame({"total": [12345]})))


if __name__ == "__main__":
    unittest.main()
