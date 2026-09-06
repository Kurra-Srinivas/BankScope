-- =============================================================================
-- BankScope — Transaction Analytics SQL
-- Canonical Database: bankscope_db
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Query 09: Monthly Transaction Volume, Total Value, and Average Ticket Size Trends
-- Business Question: What is the monthly trajectory of payment transactions, gross dollar volume,
-- and average transaction ticket size from 2019 through 2025?
-- SQL Techniques: DATE_TRUNC, Aggregation, Time-series formatting.
-- -----------------------------------------------------------------------------
SELECT 
    DATE_TRUNC('month', transaction_date)::DATE AS transaction_month,
    COUNT(transaction_id) AS total_transactions,
    ROUND(SUM(amount_usd), 2) AS gross_transaction_value_usd,
    ROUND(AVG(amount_usd), 2) AS avg_ticket_size_usd,
    ROUND(MIN(amount_usd), 2) AS min_transaction_usd,
    ROUND(MAX(amount_usd), 2) AS max_transaction_usd
FROM transactions
GROUP BY DATE_TRUNC('month', transaction_date)::DATE
ORDER BY transaction_month;


-- -----------------------------------------------------------------------------
-- Query 10: Month-over-Month (MoM) Transaction Volume & Spend Growth Analysis
-- Business Question: What is the month-over-month growth rate of transactional spending,
-- and which months experienced the sharpest acceleration or contraction in volume?
-- SQL Techniques: CTE, Window function LAG(), MoM growth percentage calculation.
-- -----------------------------------------------------------------------------
WITH monthly_metrics AS (
    SELECT 
        DATE_TRUNC('month', transaction_date)::DATE AS month_start,
        COUNT(transaction_id) AS monthly_tx_count,
        SUM(amount_usd) AS monthly_volume_usd
    FROM transactions
    GROUP BY DATE_TRUNC('month', transaction_date)::DATE
)
SELECT 
    month_start,
    monthly_tx_count,
    LAG(monthly_tx_count, 1) OVER (ORDER BY month_start) AS prev_month_tx_count,
    ROUND(
        (monthly_tx_count - LAG(monthly_tx_count, 1) OVER (ORDER BY month_start)) * 100.0 /
        NULLIF(LAG(monthly_tx_count, 1) OVER (ORDER BY month_start), 0),
        2
    ) AS tx_count_mom_pct,
    ROUND(monthly_volume_usd, 2) AS monthly_volume_usd,
    ROUND(LAG(monthly_volume_usd, 1) OVER (ORDER BY month_start), 2) AS prev_month_volume_usd,
    ROUND(
        (monthly_volume_usd - LAG(monthly_volume_usd, 1) OVER (ORDER BY month_start)) * 100.0 /
        NULLIF(LAG(monthly_volume_usd, 1) OVER (ORDER BY month_start), 0),
        2
    ) AS volume_mom_pct
FROM monthly_metrics
ORDER BY month_start;


-- -----------------------------------------------------------------------------
-- Query 11: Day-of-Week and Hourly Velocity Patterns (Peak Traffic Profiling)
-- Business Question: Which days of the week and hours of the day generate the highest
-- transaction frequency and monetary volume?
-- SQL Techniques: EXTRACT(DOW FROM ...), EXTRACT(HOUR FROM ...), TO_CHAR, Multi-dimensional aggregation.
-- -----------------------------------------------------------------------------
SELECT 
    TO_CHAR(transaction_date, 'Day') AS day_of_week,
    EXTRACT(DOW FROM transaction_date)::INT AS day_of_week_num,
    EXTRACT(HOUR FROM transaction_date)::INT AS transaction_hour,
    COUNT(transaction_id) AS transaction_count,
    ROUND(SUM(amount_usd), 2) AS total_volume_usd,
    ROUND(AVG(amount_usd), 2) AS avg_amount_usd,
    ROUND(COUNT(transaction_id) * 100.0 / SUM(COUNT(transaction_id)) OVER (), 2) AS pct_of_all_transactions
FROM transactions
GROUP BY 
    TO_CHAR(transaction_date, 'Day'),
    EXTRACT(DOW FROM transaction_date)::INT,
    EXTRACT(HOUR FROM transaction_date)::INT
ORDER BY day_of_week_num, transaction_hour;


-- -----------------------------------------------------------------------------
-- Query 12: High-Value & Outlier Transaction Detection (99th Percentile Audit)
-- Business Question: What are the transactions that exceed the 99th percentile dollar threshold,
-- and which accounts and merchants represent the greatest concentration of these high-value transactions?
-- SQL Techniques: PERCENTILE_CONT(0.99) WITHIN GROUP, CTE, JOIN, High-value threshold filtering.
-- -----------------------------------------------------------------------------
WITH p99_benchmark AS (
    SELECT 
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY amount_usd) AS p99_threshold_usd
    FROM transactions
),
high_value_txns AS (
    SELECT 
        t.transaction_id,
        t.account_id,
        a.account_type,
        t.merchant_id,
        m.merchant_name,
        t.amount_usd,
        t.transaction_date,
        b.p99_threshold_usd
    FROM transactions t
    JOIN accounts a ON t.account_id = a.account_id
    JOIN merchants m ON t.merchant_id = m.merchant_id
    CROSS JOIN p99_benchmark b
    WHERE t.amount_usd >= b.p99_threshold_usd
)
SELECT 
    account_type,
    COUNT(transaction_id) AS p99_transaction_count,
    ROUND(SUM(amount_usd), 2) AS p99_aggregate_volume_usd,
    ROUND(AVG(amount_usd), 2) AS p99_avg_amount_usd,
    ROUND(MIN(amount_usd), 2) AS p99_min_amount_usd,
    ROUND(MAX(amount_usd), 2) AS p99_max_amount_usd,
    ROUND(MAX(p99_threshold_usd)::NUMERIC, 2) AS p99_cut_off_usd
FROM high_value_txns
GROUP BY account_type
ORDER BY p99_aggregate_volume_usd DESC;
