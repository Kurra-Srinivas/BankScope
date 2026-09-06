-- =============================================================================
-- BankScope — Account Analytics SQL
-- Canonical Database: bankscope_db
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Query 05: Account Portfolio Composition & Balance Market Share
-- Business Question: What is the distribution of deposit accounts across product types
-- (Checking, Savings, Business), their aggregate balance, and balance market share?
-- SQL Techniques: GROUP BY, Aggregate functions, Window functions (SUM OVER ()), Percentage share.
-- -----------------------------------------------------------------------------
SELECT 
    account_type,
    COUNT(account_id) AS total_accounts,
    ROUND(COUNT(account_id) * 100.0 / SUM(COUNT(account_id)) OVER (), 2) AS account_share_pct,
    ROUND(SUM(balance_usd), 2) AS total_balance_usd,
    ROUND(SUM(balance_usd) * 100.0 / SUM(SUM(balance_usd)) OVER (), 2) AS balance_share_pct,
    ROUND(AVG(balance_usd), 2) AS avg_balance_usd,
    ROUND(MIN(balance_usd), 2) AS min_balance_usd,
    ROUND(MAX(balance_usd), 2) AS max_balance_usd
FROM accounts
GROUP BY account_type
ORDER BY total_balance_usd DESC;


-- -----------------------------------------------------------------------------
-- Query 06: Payment Card Attachment & Penetration by Account Type
-- Business Question: What proportion of accounts across each product category have debit
-- cards, credit cards, or multiple cards attached to them?
-- SQL Techniques: LEFT JOIN, Conditional Aggregation (CASE WHEN), CTE, Ratio calculations.
-- -----------------------------------------------------------------------------
WITH account_cards AS (
    SELECT 
        a.account_id,
        a.account_type,
        COUNT(c.card_id) AS total_cards,
        SUM(CASE WHEN c.card_type = 'Debit' THEN 1 ELSE 0 END) AS debit_card_count,
        SUM(CASE WHEN c.card_type = 'Credit' THEN 1 ELSE 0 END) AS credit_card_count
    FROM accounts a
    LEFT JOIN cards c ON a.account_id = c.account_id
    GROUP BY a.account_id, a.account_type
)
SELECT 
    account_type,
    COUNT(account_id) AS total_accounts,
    SUM(CASE WHEN total_cards = 0 THEN 1 ELSE 0 END) AS accounts_without_card,
    ROUND(SUM(CASE WHEN total_cards = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(account_id), 2) AS uncarded_pct,
    SUM(CASE WHEN debit_card_count > 0 THEN 1 ELSE 0 END) AS accounts_with_debit,
    ROUND(SUM(CASE WHEN debit_card_count > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(account_id), 2) AS debit_penetration_pct,
    SUM(CASE WHEN credit_card_count > 0 THEN 1 ELSE 0 END) AS accounts_with_credit,
    ROUND(SUM(CASE WHEN credit_card_count > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(account_id), 2) AS credit_penetration_pct,
    ROUND(AVG(total_cards), 2) AS avg_cards_per_account
FROM account_cards
GROUP BY account_type
ORDER BY total_accounts DESC;


-- -----------------------------------------------------------------------------
-- Query 07: Balance Decile Stratification & Deposit Concentration
-- Business Question: How concentrated are deposits across the 10 balance deciles,
-- and what proportion of total liquid capital is controlled by the top 10% of accounts?
-- SQL Techniques: NTILE(10) window function, CTE, Cumulative Window SUM OVER (), Pareto analysis.
-- -----------------------------------------------------------------------------
WITH decile_ranking AS (
    SELECT 
        account_id,
        balance_usd,
        NTILE(10) OVER (ORDER BY balance_usd ASC) AS balance_decile
    FROM accounts
)
SELECT 
    balance_decile,
    COUNT(account_id) AS accounts_in_decile,
    ROUND(MIN(balance_usd), 2) AS min_balance_usd,
    ROUND(MAX(balance_usd), 2) AS max_balance_usd,
    ROUND(SUM(balance_usd), 2) AS decile_total_balance_usd,
    ROUND(SUM(balance_usd) * 100.0 / SUM(SUM(balance_usd)) OVER (), 2) AS decile_balance_share_pct,
    ROUND(SUM(SUM(balance_usd)) OVER (ORDER BY balance_decile) * 100.0 / SUM(SUM(balance_usd)) OVER (), 2) AS cumulative_balance_share_pct
FROM decile_ranking
GROUP BY balance_decile
ORDER BY balance_decile DESC;


-- -----------------------------------------------------------------------------
-- Query 08: Account Vintage & Opening Cohort Liquidity Dynamics
-- Business Question: How does account vintage (year of opening) relate to average balance
-- retention and customer longevity?
-- SQL Techniques: EXTRACT(YEAR FROM ...), GROUP BY, Window function LAG() for YoY trends.
-- -----------------------------------------------------------------------------
WITH yearly_vintage AS (
    SELECT 
        EXTRACT(YEAR FROM open_date)::INT AS opening_year,
        COUNT(account_id) AS accounts_opened,
        ROUND(SUM(balance_usd), 2) AS cohort_total_balance_usd,
        ROUND(AVG(balance_usd), 2) AS cohort_avg_balance_usd
    FROM accounts
    GROUP BY EXTRACT(YEAR FROM open_date)::INT
)
SELECT 
    opening_year,
    accounts_opened,
    cohort_total_balance_usd,
    cohort_avg_balance_usd,
    ROUND(
        (cohort_avg_balance_usd - LAG(cohort_avg_balance_usd, 1) OVER (ORDER BY opening_year)) * 100.0 /
        NULLIF(LAG(cohort_avg_balance_usd, 1) OVER (ORDER BY opening_year), 0),
        2
    ) AS yoy_avg_balance_growth_pct
FROM yearly_vintage
ORDER BY opening_year;
