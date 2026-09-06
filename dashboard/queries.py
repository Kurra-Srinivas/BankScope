"""
BankScope Dashboard Query Repository
Houses production SQL queries executed directly against PostgreSQL bankscope_db.
"""

from dashboard.db import execute_query
import pandas as pd


# -----------------------------------------------------------------------------
# 1. Executive Overview Queries
# -----------------------------------------------------------------------------
def get_executive_kpis() -> dict:
    """Fetch high-level portfolio counts, deposit sums, and loan exposure."""
    sql = """
    SELECT 
        (SELECT COUNT(*) FROM customers) AS total_customers,
        (SELECT COUNT(*) FROM accounts) AS total_accounts,
        (SELECT COUNT(*) FROM cards) AS total_cards,
        (SELECT COUNT(*) FROM loans) AS total_loans,
        (SELECT COUNT(*) FROM merchants) AS total_merchants,
        (SELECT COUNT(*) FROM transactions) AS total_transactions,
        (SELECT COALESCE(SUM(balance_usd), 0) FROM accounts) AS total_deposits_usd,
        (SELECT COALESCE(SUM(amount_usd), 0) FROM transactions) AS total_transaction_volume_usd,
        (SELECT COALESCE(SUM(loan_amount), 0) FROM loans) AS total_loan_exposure_usd;
    """
    df = execute_query(sql)
    return df.iloc[0].to_dict() if not df.empty else {}


def get_monthly_trend_overview() -> pd.DataFrame:
    """Monthly transaction volume and spend trajectory."""
    sql = """
    SELECT 
        DATE_TRUNC('month', transaction_date)::DATE AS transaction_month,
        COUNT(transaction_id) AS transaction_count,
        ROUND(SUM(amount_usd), 2) AS total_volume_usd,
        ROUND(AVG(amount_usd), 2) AS avg_ticket_usd
    FROM transactions
    GROUP BY DATE_TRUNC('month', transaction_date)::DATE
    ORDER BY transaction_month ASC;
    """
    return execute_query(sql)


# -----------------------------------------------------------------------------
# 2. Customer Analytics Queries
# -----------------------------------------------------------------------------
def get_city_distribution(limit: int = 15) -> pd.DataFrame:
    """Top cities by customer concentration and average balance."""
    sql = """
    SELECT 
        c.city,
        COUNT(DISTINCT c.customer_id) AS customer_count,
        COUNT(a.account_id) AS total_accounts,
        ROUND(COALESCE(SUM(a.balance_usd), 0), 2) AS total_balance_usd,
        ROUND(COALESCE(AVG(a.balance_usd), 0), 2) AS avg_account_balance_usd
    FROM customers c
    LEFT JOIN accounts a ON c.customer_id = a.customer_id
    GROUP BY c.city
    ORDER BY customer_count DESC
    LIMIT %s;
    """
    return execute_query(sql, params=(limit,))


def get_account_composition() -> pd.DataFrame:
    """Account breakdown by type, total balances, and market share."""
    sql = """
    SELECT 
        account_type,
        COUNT(account_id) AS total_accounts,
        ROUND(COUNT(account_id) * 100.0 / SUM(COUNT(account_id)) OVER (), 2) AS account_share_pct,
        ROUND(SUM(balance_usd), 2) AS total_balance_usd,
        ROUND(SUM(balance_usd) * 100.0 / SUM(SUM(balance_usd)) OVER (), 2) AS balance_share_pct,
        ROUND(AVG(balance_usd), 2) AS avg_balance_usd
    FROM accounts
    GROUP BY account_type
    ORDER BY total_balance_usd DESC;
    """
    return execute_query(sql)


def get_top_customers(limit: int = 15) -> pd.DataFrame:
    """Top multi-product customers by total relationship value (deposits + loans)."""
    sql = """
    WITH customer_accounts AS (
        SELECT customer_id, COUNT(account_id) AS total_accounts, SUM(balance_usd) AS total_deposits
        FROM accounts GROUP BY customer_id
    ),
    customer_loans AS (
        SELECT customer_id, COUNT(loan_id) AS total_loans, SUM(loan_amount) AS total_loans_usd
        FROM loans GROUP BY customer_id
    )
    SELECT 
        c.customer_id,
        c.first_name || ' ' || c.last_name AS customer_name,
        c.city,
        c.credit_score,
        COALESCE(ca.total_accounts, 0) AS total_accounts,
        ROUND(COALESCE(ca.total_deposits, 0), 2) AS total_deposits_usd,
        COALESCE(cl.total_loans, 0) AS total_loans,
        ROUND(COALESCE(cl.total_loans_usd, 0), 2) AS total_loans_usd,
        ROUND(COALESCE(ca.total_deposits, 0) + COALESCE(cl.total_loans_usd, 0), 2) AS total_relationship_value_usd,
        DENSE_RANK() OVER (ORDER BY (COALESCE(ca.total_deposits, 0) + COALESCE(cl.total_loans_usd, 0)) DESC) AS rank
    FROM customers c
    LEFT JOIN customer_accounts ca ON c.customer_id = ca.customer_id
    LEFT JOIN customer_loans cl ON c.customer_id = cl.customer_id
    ORDER BY total_relationship_value_usd DESC
    LIMIT %s;
    """
    return execute_query(sql, params=(limit,))


def get_rfm_distribution() -> pd.DataFrame:
    """Customer counts, spend volume, and averages across 7 RFM segments."""
    sql = """
    WITH customer_rfm_raw AS (
        SELECT 
            c.customer_id,
            DATE '2025-12-31' - MAX(t.transaction_date)::DATE AS recency_days,
            COUNT(t.transaction_id) AS frequency,
            SUM(t.amount_usd) AS monetary_usd
        FROM customers c
        JOIN accounts a ON c.customer_id = a.customer_id
        JOIN transactions t ON a.account_id = t.account_id
        GROUP BY c.customer_id
    ),
    rfm_scores AS (
        SELECT 
            customer_id, recency_days, frequency, monetary_usd,
            NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
            NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
            NTILE(5) OVER (ORDER BY monetary_usd ASC) AS m_score
        FROM customer_rfm_raw
    ),
    rfm_segments AS (
        SELECT 
            customer_id, recency_days, frequency, monetary_usd,
            CASE 
                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '1. Champions'
                WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN '2. Loyal Customers'
                WHEN r_score >= 4 AND f_score <= 2 THEN '3. Recent Promising Customers'
                WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN '4. At Risk'
                WHEN r_score <= 2 AND f_score <= 2 AND m_score >= 3 THEN '5. Need Attention'
                WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN '6. Hibernating / Lost'
                ELSE '7. Average / Steady'
            END AS rfm_segment
        FROM rfm_scores
    )
    SELECT 
        rfm_segment,
        COUNT(customer_id) AS customer_count,
        ROUND(COUNT(customer_id) * 100.0 / SUM(COUNT(customer_id)) OVER (), 2) AS customer_pct,
        ROUND(SUM(monetary_usd), 2) AS total_spend_usd,
        ROUND(SUM(monetary_usd) * 100.0 / SUM(SUM(monetary_usd)) OVER (), 2) AS spend_share_pct,
        ROUND(AVG(recency_days), 1) AS avg_recency_days,
        ROUND(AVG(frequency), 1) AS avg_frequency,
        ROUND(AVG(monetary_usd), 2) AS avg_monetary_usd
    FROM rfm_segments
    GROUP BY rfm_segment
    ORDER BY rfm_segment;
    """
    return execute_query(sql)


# -----------------------------------------------------------------------------
# 3. Transaction Analytics Queries
# -----------------------------------------------------------------------------
def get_filtered_transactions_monthly(start_date=None, end_date=None) -> pd.DataFrame:
    """Monthly transaction metrics filtered by date range."""
    sql = """
    SELECT 
        DATE_TRUNC('month', transaction_date)::DATE AS month,
        COUNT(transaction_id) AS tx_count,
        ROUND(SUM(amount_usd), 2) AS total_volume_usd,
        ROUND(AVG(amount_usd), 2) AS avg_ticket_usd
    FROM transactions
    WHERE (%s::DATE IS NULL OR transaction_date >= %s::DATE)
      AND (%s::DATE IS NULL OR transaction_date <= (%s::DATE + INTERVAL '1 day'))
    GROUP BY DATE_TRUNC('month', transaction_date)::DATE
    ORDER BY month ASC;
    """
    return execute_query(sql, params=(start_date, start_date, end_date, end_date))


def get_top_merchants(limit: int = 15) -> pd.DataFrame:
    """Top merchants by processed volume."""
    sql = """
    SELECT 
        m.merchant_id,
        m.merchant_name,
        m.city,
        COUNT(t.transaction_id) AS transaction_count,
        ROUND(SUM(t.amount_usd), 2) AS total_volume_usd,
        ROUND(AVG(t.amount_usd), 2) AS avg_ticket_usd,
        DENSE_RANK() OVER (ORDER BY SUM(t.amount_usd) DESC) AS rank
    FROM merchants m
    JOIN transactions t ON m.merchant_id = t.merchant_id
    GROUP BY m.merchant_id, m.merchant_name, m.city
    ORDER BY total_volume_usd DESC
    LIMIT %s;
    """
    return execute_query(sql, params=(limit,))


def get_high_value_transactions(limit: int = 20) -> pd.DataFrame:
    """Top high-value transaction outliers."""
    sql = """
    SELECT 
        t.transaction_id,
        t.account_id,
        a.account_type,
        m.merchant_name,
        m.city AS merchant_city,
        t.amount_usd,
        t.transaction_date
    FROM transactions t
    JOIN accounts a ON t.account_id = a.account_id
    JOIN merchants m ON t.merchant_id = m.merchant_id
    ORDER BY t.amount_usd DESC
    LIMIT %s;
    """
    return execute_query(sql, params=(limit,))


# -----------------------------------------------------------------------------
# 4. Loans & Portfolio Queries
# -----------------------------------------------------------------------------
def get_loan_apr_tiers() -> pd.DataFrame:
    """Loan distribution across interest rate tiers."""
    sql = """
    WITH loan_tiers AS (
        SELECT 
            loan_id,
            loan_amount,
            interest_rate,
            CASE 
                WHEN interest_rate < 5.00 THEN '1. Low (<5%)'
                WHEN interest_rate BETWEEN 5.00 AND 7.99 THEN '2. Prime (5%-7.99%)'
                WHEN interest_rate BETWEEN 8.00 AND 11.99 THEN '3. Standard (8%-11.99%)'
                ELSE '4. High / Subprime (>=12%)'
            END AS interest_rate_tier
        FROM loans
    )
    SELECT 
        interest_rate_tier,
        COUNT(loan_id) AS loan_count,
        ROUND(COUNT(loan_id) * 100.0 / SUM(COUNT(loan_id)) OVER (), 2) AS loan_count_pct,
        ROUND(SUM(loan_amount), 2) AS total_loan_volume_usd,
        ROUND(SUM(loan_amount) * 100.0 / SUM(SUM(loan_amount)) OVER (), 2) AS volume_share_pct,
        ROUND(AVG(loan_amount), 2) AS avg_loan_size_usd,
        ROUND(SUM(loan_amount * interest_rate) / SUM(loan_amount), 2) AS weighted_avg_apr
    FROM loan_tiers
    GROUP BY interest_rate_tier
    ORDER BY interest_rate_tier ASC;
    """
    return execute_query(sql)


def get_credit_score_vs_apr() -> pd.DataFrame:
    """Pricing analysis comparing credit score tiers against average interest rate."""
    sql = """
    SELECT 
        CASE 
            WHEN c.credit_score BETWEEN 300 AND 579 THEN '1. Poor (300-579)'
            WHEN c.credit_score BETWEEN 580 AND 669 THEN '2. Fair (580-669)'
            WHEN c.credit_score BETWEEN 670 AND 739 THEN '3. Good (670-739)'
            WHEN c.credit_score BETWEEN 740 AND 799 THEN '4. Very Good (740-799)'
            WHEN c.credit_score BETWEEN 800 AND 850 THEN '5. Exceptional (800-850)'
            ELSE 'Unknown'
        END AS credit_tier,
        COUNT(l.loan_id) AS total_loans,
        ROUND(AVG(c.credit_score), 1) AS avg_credit_score,
        ROUND(AVG(l.interest_rate), 2) AS avg_interest_rate,
        ROUND(MIN(l.interest_rate), 2) AS min_interest_rate,
        ROUND(MAX(l.interest_rate), 2) AS max_interest_rate,
        ROUND(SUM(l.loan_amount), 2) AS total_principal_usd
    FROM loans l
    JOIN customers c ON l.customer_id = c.customer_id
    GROUP BY credit_tier
    ORDER BY credit_tier ASC;
    """
    return execute_query(sql)


def get_annual_loan_trend() -> pd.DataFrame:
    """Yearly loan origination counts and capital exposure."""
    sql = """
    SELECT 
        EXTRACT(YEAR FROM start_date)::INT AS origination_year,
        COUNT(loan_id) AS loans_originated,
        ROUND(SUM(loan_amount), 2) AS annual_volume_usd,
        ROUND(AVG(interest_rate), 2) AS avg_annual_apr
    FROM loans
    GROUP BY EXTRACT(YEAR FROM start_date)::INT
    ORDER BY origination_year ASC;
    """
    return execute_query(sql)


# -----------------------------------------------------------------------------
# 5. SQL Performance Benchmark Results
# -----------------------------------------------------------------------------
def get_benchmark_summary() -> list:
    """Return empirical benchmark data from the performance audit (20 alternating runs)."""
    return [
        {
            "id": "BENCH_01",
            "name": "Transaction Date-Range Slicing",
            "workload": "Quarterly ledger aggregation on 1M rows",
            "target_index": "idx_transactions_date",
            "unindexed_ms": 79.763,
            "indexed_ms": 33.677,
            "pct_improvement": 57.78,
            "speedup_factor": 2.4,
            "classification": "ROBUST",
            "plan_shift": "Parallel Seq Scan (12,452 blocks) -> Bitmap Index Scan (11,796 blocks)",
        },
        {
            "id": "BENCH_02",
            "name": "Account Activity & Ledger Statement",
            "workload": "Account timeline lookups & chronological sort",
            "target_index": "idx_transactions_account_date",
            "unindexed_ms": 70.053,
            "indexed_ms": 0.060,
            "pct_improvement": 99.91,
            "speedup_factor": 1167.5,
            "classification": "CAUTION",
            "plan_shift": "Parallel Seq Scan + Sort (12,376 blocks) -> Index Scan (18 blocks)",
        },
        {
            "id": "BENCH_03",
            "name": "Merchant Monthly Time-Series Aggregation",
            "workload": "Monthly merchant settlement aggregation & join",
            "target_index": "idx_transactions_merchant_date",
            "unindexed_ms": 71.424,
            "indexed_ms": 0.595,
            "pct_improvement": 99.17,
            "speedup_factor": 120.0,
            "classification": "ROBUST",
            "plan_shift": "Parallel Seq Scan + Join (12,599 blocks) -> Index Scan (258 blocks)",
        },
    ]

