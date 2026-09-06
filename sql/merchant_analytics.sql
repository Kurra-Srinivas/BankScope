-- =============================================================================
-- BankScope — Merchant Analytics SQL
-- Canonical Database: bankscope_db
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Query 20: Top 20 Merchants by Processed Transaction Volume & Value
-- Business Question: Which top 20 merchant partners process the greatest dollar volume
-- and transaction volume across our payment network?
-- SQL Techniques: INNER JOIN, Aggregate functions, DENSE_RANK() window function.
-- -----------------------------------------------------------------------------
SELECT 
    m.merchant_id,
    m.merchant_name,
    m.city AS merchant_city,
    COUNT(t.transaction_id) AS total_transactions,
    ROUND(SUM(t.amount_usd), 2) AS total_processed_volume_usd,
    ROUND(AVG(t.amount_usd), 2) AS avg_ticket_size_usd,
    ROUND(MIN(t.amount_usd), 2) AS min_ticket_usd,
    ROUND(MAX(t.amount_usd), 2) AS max_ticket_usd,
    DENSE_RANK() OVER (ORDER BY SUM(t.amount_usd) DESC) AS revenue_rank
FROM merchants m
JOIN transactions t ON m.merchant_id = t.merchant_id
GROUP BY m.merchant_id, m.merchant_name, m.city
ORDER BY revenue_rank
LIMIT 20;


-- -----------------------------------------------------------------------------
-- Query 21: Merchant Concentration & Pareto Principle (Cumulative Volume Share)
-- Business Question: What percentage of aggregate bank transaction volume is concentrated
-- among the top 5%, 10%, and 20% of merchants?
-- SQL Techniques: CTEs, NTILE(20) window function, Cumulative SUM OVER (), Pareto analysis.
-- -----------------------------------------------------------------------------
WITH merchant_volumes AS (
    SELECT 
        merchant_id,
        SUM(amount_usd) AS merchant_volume_usd
    FROM transactions
    GROUP BY merchant_id
),
merchant_ventiles AS (
    SELECT 
        merchant_id,
        merchant_volume_usd,
        NTILE(20) OVER (ORDER BY merchant_volume_usd DESC) AS ventile_rank
    FROM merchant_volumes
)
SELECT 
    ventile_rank AS top_5_pct_bracket,
    COUNT(merchant_id) AS merchants_in_bracket,
    ROUND(SUM(merchant_volume_usd), 2) AS bracket_volume_usd,
    ROUND(SUM(merchant_volume_usd) * 100.0 / SUM(SUM(merchant_volume_usd)) OVER (), 2) AS bracket_share_pct,
    ROUND(SUM(SUM(merchant_volume_usd)) OVER (ORDER BY ventile_rank) * 100.0 / SUM(SUM(merchant_volume_usd)) OVER (), 2) AS cumulative_volume_share_pct
FROM merchant_ventiles
GROUP BY ventile_rank
ORDER BY ventile_rank ASC;


-- -----------------------------------------------------------------------------
-- Query 22: Commercial Centers & City-Level Merchant Ticket Benchmarking
-- Business Question: In which cities do merchants process the highest average transaction values,
-- and which cities represent the largest commercial merchant clusters?
-- SQL Techniques: INNER JOIN, GROUP BY, Aggregate functions, HAVING filter.
-- -----------------------------------------------------------------------------
SELECT 
    m.city AS commercial_city,
    COUNT(DISTINCT m.merchant_id) AS active_merchant_count,
    COUNT(t.transaction_id) AS total_city_transactions,
    ROUND(SUM(t.amount_usd), 2) AS total_city_volume_usd,
    ROUND(AVG(t.amount_usd), 2) AS avg_city_ticket_size_usd,
    ROUND(SUM(t.amount_usd) / COUNT(DISTINCT m.merchant_id), 2) AS avg_volume_per_merchant_usd
FROM merchants m
JOIN transactions t ON m.merchant_id = t.merchant_id
GROUP BY m.city
HAVING COUNT(DISTINCT m.merchant_id) >= 5
ORDER BY total_city_volume_usd DESC
LIMIT 15;


-- -----------------------------------------------------------------------------
-- Query 23: Merchant Annual Activity Consistency & Stability Profiling
-- Business Question: Which merchants have transacted consistently across all 7 operational
-- years (2019 through 2025), demonstrating resilient ongoing business relationships?
-- SQL Techniques: EXTRACT(YEAR FROM ...), COUNT(DISTINCT year), HAVING, JOIN.
-- -----------------------------------------------------------------------------
SELECT 
    m.merchant_id,
    m.merchant_name,
    m.city,
    COUNT(DISTINCT EXTRACT(YEAR FROM t.transaction_date)) AS active_years_count,
    COUNT(t.transaction_id) AS lifetime_transactions,
    ROUND(SUM(t.amount_usd), 2) AS lifetime_volume_usd,
    ROUND(AVG(t.amount_usd), 2) AS lifetime_avg_ticket_usd
FROM merchants m
JOIN transactions t ON m.merchant_id = t.merchant_id
GROUP BY m.merchant_id, m.merchant_name, m.city
HAVING COUNT(DISTINCT EXTRACT(YEAR FROM t.transaction_date)) = 7
ORDER BY lifetime_volume_usd DESC
LIMIT 20;
