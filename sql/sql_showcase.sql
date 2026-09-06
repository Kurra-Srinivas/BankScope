-- =============================================================================
-- BankScope — SQL Showcase: Advanced Analytical Query Engineering
-- =============================================================================
-- This file curates the 7 strongest, battle-tested SQL query patterns from the
-- BankScope analytical layer. All queries run against PostgreSQL 18 (bankscope_db)
-- across the 1.26-million-row financial data warehouse.
--
-- Query Patterns Demonstrated:
--   1. Safe Multi-Table Pre-Aggregation (Eliminating Cartesian Fan-Out)
--   2. Time-Series Analysis with CTE + LAG() (Month-over-Month Velocity)
--   3. Window Function Ranking (DENSE_RANK across Merchant Network)
--   4. Behavioral Customer Segmentation (RFM Matrix with NTILE)
--   5. Cumulative & Pareto Concentration Analysis (Running Totals)
--   6. Portfolio Risk Tiering & Exposure Concentration (CASE Expressions)
--   7. Index Optimization & Buffer Investigation (EXPLAIN ANALYZE)
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. SAFE MULTI-TABLE PRE-AGGREGATION (ELIMINATING CARTESIAN FAN-OUT)
-- -----------------------------------------------------------------------------
-- Business Question: What is the total relationship value (deposits + loans) for
--   each customer?
-- Technical Note: A naive join of customers -> accounts -> loans multiplies rows
--   if a customer has multiple accounts and multiple loans. To prevent artificial
--   inflation of deposit and loan totals, each child table is pre-aggregated
--   in isolated CTEs before joining to the customer master.
-- -----------------------------------------------------------------------------
WITH customer_accounts AS (
    SELECT 
        customer_id,
        COUNT(account_id) AS total_accounts,
        COALESCE(SUM(balance_usd), 0) AS total_deposits_usd
    FROM accounts
    GROUP BY customer_id
),
customer_loans AS (
    SELECT 
        customer_id,
        COUNT(loan_id) AS total_loans,
        COALESCE(SUM(loan_amount), 0) AS total_loans_usd
    FROM loans
    GROUP BY customer_id
)
SELECT 
    c.customer_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.city,
    c.credit_score,
    COALESCE(ca.total_accounts, 0) AS total_accounts,
    ROUND(COALESCE(ca.total_deposits_usd, 0), 2) AS total_deposits_usd,
    COALESCE(cl.total_loans, 0) AS total_loans,
    ROUND(COALESCE(cl.total_loans_usd, 0), 2) AS total_loans_usd,
    ROUND(COALESCE(ca.total_deposits_usd, 0) + COALESCE(cl.total_loans_usd, 0), 2) AS total_relationship_value_usd,
    DENSE_RANK() OVER (ORDER BY (COALESCE(ca.total_deposits_usd, 0) + COALESCE(cl.total_loans_usd, 0)) DESC) AS wealth_rank
FROM customers c
LEFT JOIN customer_accounts ca ON c.customer_id = ca.customer_id
LEFT JOIN customer_loans cl ON c.customer_id = cl.customer_id
ORDER BY total_relationship_value_usd DESC
LIMIT 15;


-- -----------------------------------------------------------------------------
-- 2. TIME-SERIES ANALYSIS WITH CTE + LAG() (MONTH-OVER-MONTH VELOCITY)
-- -----------------------------------------------------------------------------
-- Business Question: What is the monthly gross transaction volume, transaction
--   count, and month-over-month dollar and percentage growth rate?
-- Technical Note: Aggregates the 1,000,000-row transaction ledger into monthly
--   buckets, then applies the LAG() window function to evaluate period-over-period
--   flow changes.
-- -----------------------------------------------------------------------------
WITH monthly_metrics AS (
    SELECT 
        DATE_TRUNC('month', transaction_date)::DATE AS transaction_month,
        COUNT(transaction_id) AS transaction_count,
        ROUND(SUM(amount_usd), 2) AS total_volume_usd,
        ROUND(AVG(amount_usd), 2) AS avg_ticket_usd
    FROM transactions
    GROUP BY DATE_TRUNC('month', transaction_date)::DATE
)
SELECT 
    transaction_month,
    transaction_count,
    total_volume_usd,
    avg_ticket_usd,
    LAG(total_volume_usd, 1) OVER (ORDER BY transaction_month) AS prev_month_volume_usd,
    ROUND(total_volume_usd - LAG(total_volume_usd, 1) OVER (ORDER BY transaction_month), 2) AS mom_growth_usd,
    ROUND(
        (total_volume_usd - LAG(total_volume_usd, 1) OVER (ORDER BY transaction_month)) 
        * 100.0 / NULLIF(LAG(total_volume_usd, 1) OVER (ORDER BY transaction_month), 0), 
        2
    ) AS mom_growth_pct
FROM monthly_metrics
ORDER BY transaction_month DESC
LIMIT 24;


-- -----------------------------------------------------------------------------
-- 3. WINDOW FUNCTION RANKING (DENSE_RANK ACROSS COMMERCIAL NETWORK)
-- -----------------------------------------------------------------------------
-- Business Question: Who are the top 15 commercial merchants ranked by gross
--   processed dollar volume, and what is their average ticket size?
-- Technical Note: Joins the 1,000,000 transactions table with the 5,000 merchants
--   dimension, computing aggregate volume and strict dense ranking.
-- -----------------------------------------------------------------------------
SELECT 
    m.merchant_id,
    m.merchant_name,
    m.city,
    COUNT(t.transaction_id) AS transaction_count,
    ROUND(SUM(t.amount_usd), 2) AS total_volume_usd,
    ROUND(AVG(t.amount_usd), 2) AS avg_ticket_usd,
    DENSE_RANK() OVER (ORDER BY SUM(t.amount_usd) DESC) AS volume_rank
FROM merchants m
JOIN transactions t ON m.merchant_id = t.merchant_id
GROUP BY m.merchant_id, m.merchant_name, m.city
ORDER BY total_volume_usd DESC
LIMIT 15;


-- -----------------------------------------------------------------------------
-- 4. BEHAVIORAL CUSTOMER SEGMENTATION (RFM MATRIX WITH NTILE)
-- -----------------------------------------------------------------------------
-- Business Question: Segment transacting customers into 7 actionable tiers
--   based on Recency (days since last transaction), Frequency (total transaction
--   count), and Monetary value (total spend).
-- Technical Note: Uses 2025-12-31 as fixed portfolio baseline. Scores 38,849
--   transacting customers into quintiles (1-5) using NTILE(5), then classifies
--   them into segments (Champions, Loyal, At Risk, Hibernating, etc.).
-- -----------------------------------------------------------------------------
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
        customer_id,
        recency_days,
        frequency,
        monetary_usd,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
        NTILE(5) OVER (ORDER BY monetary_usd ASC) AS m_score
    FROM customer_rfm_raw
),
rfm_segments AS (
    SELECT 
        customer_id,
        recency_days,
        frequency,
        monetary_usd,
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
ORDER BY rfm_segment ASC;


-- -----------------------------------------------------------------------------
-- 5. CUMULATIVE & PARETO CONCENTRATION ANALYSIS (RUNNING TOTALS)
-- -----------------------------------------------------------------------------
-- Business Question: What percentage of total ledger volume is driven by the
--   top spending customers (Pareto 80/20 distribution)?
-- Technical Note: Employs cumulative window summation SUM() OVER (ROWS BETWEEN
--   UNBOUNDED PRECEDING AND CURRENT ROW) to compute running spend and cumulative
--   percentage of total portfolio volume.
-- -----------------------------------------------------------------------------
WITH customer_spends AS (
    SELECT 
        c.customer_id,
        c.first_name || ' ' || c.last_name AS customer_name,
        SUM(t.amount_usd) AS customer_total_spend
    FROM customers c
    JOIN accounts a ON c.customer_id = a.customer_id
    JOIN transactions t ON a.account_id = t.account_id
    GROUP BY c.customer_id, c.first_name, c.last_name
),
ranked_spends AS (
    SELECT 
        customer_id,
        customer_name,
        customer_total_spend,
        ROW_NUMBER() OVER (ORDER BY customer_total_spend DESC) AS spend_rank,
        COUNT(*) OVER () AS total_transacting_customers,
        SUM(customer_total_spend) OVER () AS total_portfolio_spend
    FROM customer_spends
)
SELECT 
    spend_rank,
    customer_id,
    customer_name,
    ROUND(customer_total_spend, 2) AS customer_total_spend,
    ROUND(spend_rank * 100.0 / total_transacting_customers, 2) AS customer_percentile,
    ROUND(
        SUM(customer_total_spend) OVER (ORDER BY spend_rank ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 
        2
    ) AS cumulative_volume_usd,
    ROUND(
        SUM(customer_total_spend) OVER (ORDER BY spend_rank ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) 
        * 100.0 / total_portfolio_spend, 
        2
    ) AS cumulative_volume_pct
FROM ranked_spends
WHERE spend_rank <= 20
ORDER BY spend_rank ASC;


-- -----------------------------------------------------------------------------
-- 6. PORTFOLIO RISK TIERING & EXPOSURE CONCENTRATION (CASE EXPRESSIONS)
-- -----------------------------------------------------------------------------
-- Business Question: What is the loan book exposure and weighted average APR
--   across low, prime, standard, and subprime interest rate tiers?
-- Technical Note: Uses conditional CASE categorization combined with principal-
--   weighted interest rate calculations across 30,000 loan commitments.
-- -----------------------------------------------------------------------------
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
    COUNT(loan_id) AS total_loans,
    ROUND(COUNT(loan_id) * 100.0 / SUM(COUNT(loan_id)) OVER (), 2) AS loan_count_pct,
    ROUND(SUM(loan_amount), 2) AS total_principal_usd,
    ROUND(SUM(loan_amount) * 100.0 / SUM(SUM(loan_amount)) OVER (), 2) AS volume_share_pct,
    ROUND(AVG(loan_amount), 2) AS avg_loan_size_usd,
    ROUND(SUM(loan_amount * interest_rate) / SUM(loan_amount), 2) AS weighted_avg_apr
FROM loan_tiers
GROUP BY interest_rate_tier
ORDER BY interest_rate_tier ASC;


-- -----------------------------------------------------------------------------
-- 7. INDEX OPTIMIZATION & BUFFER INVESTIGATION (EXPLAIN ANALYZE)
-- -----------------------------------------------------------------------------
-- Business Question: Evaluate the execution plan shift and buffer block reads
--   for a customer account transaction ledger statement.
-- Optimization Target: idx_transactions_account_date ON transactions(account_id, transaction_date DESC)
-- Technical Note:
--   - Unindexed State: Requires scanning all 12,376 heap blocks of the 1,000,000-row
--     table, followed by an in-memory quicksort (~70ms latency).
--   - Indexed State: Directly seeks index tuples in pre-sorted order, reducing
--     buffer page reads from 12,376 to 18 blocks (99.85% I/O reduction).
-- Audit Note (CAUTION):
--   While the 99.85% physical buffer reduction is mathematically verified,
--   sub-0.1ms execution is buffer-cache resident. In real production systems,
--   network round-trip time (1-5 ms) dominates client-observed latency.
-- -----------------------------------------------------------------------------
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
SELECT 
    transaction_id,
    account_id,
    merchant_id,
    amount_usd,
    transaction_date
FROM transactions
WHERE account_id = 'ACCB1WVS7GK7C9V'
  AND transaction_date >= '2024-01-01 00:00:00'
ORDER BY transaction_date DESC;
