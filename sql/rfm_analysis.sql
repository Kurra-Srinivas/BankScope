-- =============================================================================
-- BankScope — RFM (Recency, Frequency, Monetary) Customer Segmentation SQL
-- Canonical Database: bankscope_db
-- Reference Date Anchor: 2025-12-31 (Maximum transaction date in dataset)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Query 24: Customer Raw RFM Metrics Derivation
-- Business Question: What are the individual Recency (days since last payment), Frequency
-- (lifetime transaction count), and Monetary (lifetime spend) metrics for each customer?
-- SQL Techniques: Multi-table INNER JOIN, MAX date diff, Aggregation, CTE.
-- -----------------------------------------------------------------------------
WITH customer_rfm_raw AS (
    SELECT 
        c.customer_id,
        c.first_name || ' ' || c.last_name AS customer_name,
        c.city,
        c.credit_score,
        DATE '2025-12-31' - MAX(t.transaction_date)::DATE AS recency_days,
        COUNT(t.transaction_id) AS frequency,
        ROUND(SUM(t.amount_usd), 2) AS monetary_usd
    FROM customers c
    JOIN accounts a ON c.customer_id = a.customer_id
    JOIN transactions t ON a.account_id = t.account_id
    GROUP BY c.customer_id, c.first_name, c.last_name, c.city, c.credit_score
)
SELECT 
    customer_id,
    customer_name,
    city,
    credit_score,
    recency_days,
    frequency,
    monetary_usd
FROM customer_rfm_raw
ORDER BY monetary_usd DESC
LIMIT 20;


-- -----------------------------------------------------------------------------
-- Query 25: Statistical RFM Quintile Scoring (1 to 5 Scores)
-- Business Question: How are customers ranked into statistical quintiles (1-5) for Recency
-- (5 = most recently active), Frequency (5 = highest volume), and Monetary (5 = highest spend)?
-- SQL Techniques: NTILE(5) window functions, Nested CTEs, Combined RFM score generation.
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
        -- Recency: lower days = higher score (5 = most recent)
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        -- Frequency: higher count = higher score
        NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
        -- Monetary: higher spend = higher score
        NTILE(5) OVER (ORDER BY monetary_usd ASC) AS m_score
    FROM customer_rfm_raw
)
SELECT 
    customer_id,
    recency_days,
    frequency,
    ROUND(monetary_usd, 2) AS monetary_usd,
    r_score,
    f_score,
    m_score,
    (r_score::TEXT || f_score::TEXT || m_score::TEXT) AS rfm_combined_code
FROM rfm_scores
ORDER BY r_score DESC, m_score DESC, f_score DESC
LIMIT 20;


-- -----------------------------------------------------------------------------
-- Query 26: Customer RFM Segmentation Matrix & Segment Distribution
-- Business Question: When classifying customers into standard strategic segments
-- (Champions, Loyal Customers, Potential Loyalists, At-Risk, Hibernating, Lost),
-- how many customers belong to each tier and what is each tier's revenue contribution?
-- SQL Techniques: Multi-level CTEs, CASE-based segmentation rules, Percentage share of wallet.
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
        r_score, f_score, m_score,
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
    COUNT(customer_id) AS segment_customer_count,
    ROUND(COUNT(customer_id) * 100.0 / SUM(COUNT(customer_id)) OVER (), 2) AS segment_customer_pct,
    ROUND(SUM(monetary_usd), 2) AS segment_total_volume_usd,
    ROUND(SUM(monetary_usd) * 100.0 / SUM(SUM(monetary_usd)) OVER (), 2) AS segment_volume_share_pct,
    ROUND(AVG(recency_days), 1) AS avg_recency_days,
    ROUND(AVG(frequency), 1) AS avg_frequency,
    ROUND(AVG(monetary_usd), 2) AS avg_monetary_spend_usd
FROM rfm_segments
GROUP BY rfm_segment
ORDER BY rfm_segment;


-- -----------------------------------------------------------------------------
-- Query 27: Cross-Product Financial Profile by RFM Segment
-- Business Question: What are the liquid deposit holdings and borrowing exposures
-- across each customer RFM tier, identifying high-spending customers with untapped loan potential?
-- SQL Techniques: Multi-table JOINs across CTEs, Aggregation, Cross-product profiling.
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
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
        NTILE(5) OVER (ORDER BY monetary_usd ASC) AS m_score
    FROM customer_rfm_raw
),
rfm_segments AS (
    SELECT 
        customer_id,
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
),
customer_balances AS (
    SELECT customer_id, SUM(balance_usd) AS total_balance FROM accounts GROUP BY customer_id
),
customer_loans AS (
    SELECT customer_id, SUM(loan_amount) AS total_loans FROM loans GROUP BY customer_id
)
SELECT 
    s.rfm_segment,
    COUNT(s.customer_id) AS total_customers,
    ROUND(SUM(COALESCE(b.total_balance, 0)), 2) AS segment_total_deposits_usd,
    ROUND(AVG(COALESCE(b.total_balance, 0)), 2) AS segment_avg_deposit_usd,
    COUNT(l.customer_id) AS customers_with_loans,
    ROUND(SUM(COALESCE(l.total_loans, 0)), 2) AS segment_total_loans_usd,
    ROUND(AVG(COALESCE(l.total_loans, 0)), 2) AS segment_avg_loan_usd
FROM rfm_segments s
LEFT JOIN customer_balances b ON s.customer_id = b.customer_id
LEFT JOIN customer_loans l ON s.customer_id = l.customer_id
GROUP BY s.rfm_segment
ORDER BY s.rfm_segment;
