-- =============================================================================
-- BankScope — Customer Analytics SQL
-- Canonical Database: bankscope_db
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Query 01: Customer Demographics & Credit Risk Stratification
-- Business Question: How are customers distributed across standard FICO credit score
-- tiers (Poor, Fair, Good, Very Good, Exceptional), what is their average liquid deposit
-- balance, and what proportion of the customer base belongs to each risk category?
-- SQL Techniques: CASE expressions, LEFT JOIN, GROUP BY, Aggregate functions, Window functions.
-- -----------------------------------------------------------------------------
WITH customer_tiers AS (
    SELECT 
        c.customer_id,
        c.credit_score,
        CASE 
            WHEN c.credit_score BETWEEN 300 AND 579 THEN '1. Poor (300-579)'
            WHEN c.credit_score BETWEEN 580 AND 669 THEN '2. Fair (580-669)'
            WHEN c.credit_score BETWEEN 670 AND 739 THEN '3. Good (670-739)'
            WHEN c.credit_score BETWEEN 740 AND 799 THEN '4. Very Good (740-799)'
            WHEN c.credit_score BETWEEN 800 AND 850 THEN '5. Exceptional (800-850)'
            ELSE 'Unknown'
        END AS credit_tier,
        COALESCE(SUM(a.balance_usd), 0) AS total_customer_balance
    FROM customers c
    LEFT JOIN accounts a ON c.customer_id = a.customer_id
    GROUP BY c.customer_id, c.credit_score
)
SELECT 
    credit_tier,
    COUNT(customer_id) AS customer_count,
    ROUND(COUNT(customer_id) * 100.0 / SUM(COUNT(customer_id)) OVER (), 2) AS pct_of_customers,
    ROUND(AVG(credit_score), 1) AS avg_credit_score,
    ROUND(AVG(total_customer_balance), 2) AS avg_total_balance_usd,
    ROUND(SUM(total_customer_balance), 2) AS aggregate_balance_usd
FROM customer_tiers
GROUP BY credit_tier
ORDER BY credit_tier;


-- -----------------------------------------------------------------------------
-- Query 02: Top 15 High-Net-Worth Multi-Product Customers
-- Business Question: Who are the top 15 most financially engaged customers based on
-- combined liquid balances across deposit accounts and active credit exposure in loans?
-- SQL Techniques: Multi-table LEFT JOIN, COALESCE, DENSE_RANK window function, CTE.
-- -----------------------------------------------------------------------------
WITH customer_accounts AS (
    SELECT 
        customer_id,
        COUNT(account_id) AS total_accounts,
        SUM(balance_usd) AS total_deposit_balance
    FROM accounts
    GROUP BY customer_id
),
customer_loans AS (
    SELECT 
        customer_id,
        COUNT(loan_id) AS total_loans,
        SUM(loan_amount) AS total_loan_commitment
    FROM loans
    GROUP BY customer_id
),
customer_portfolio AS (
    SELECT 
        c.customer_id,
        c.first_name || ' ' || c.last_name AS customer_name,
        c.city,
        c.credit_score,
        COALESCE(ca.total_accounts, 0) AS total_accounts,
        COALESCE(ca.total_deposit_balance, 0) AS total_deposit_balance,
        COALESCE(cl.total_loans, 0) AS total_loans,
        COALESCE(cl.total_loan_commitment, 0) AS total_loan_commitment,
        COALESCE(ca.total_deposit_balance, 0) + COALESCE(cl.total_loan_commitment, 0) AS total_relationship_value
    FROM customers c
    LEFT JOIN customer_accounts ca ON c.customer_id = ca.customer_id
    LEFT JOIN customer_loans cl ON c.customer_id = cl.customer_id
)
SELECT 
    customer_id,
    customer_name,
    city,
    credit_score,
    total_accounts,
    ROUND(total_deposit_balance, 2) AS total_deposit_balance_usd,
    total_loans,
    ROUND(total_loan_commitment, 2) AS total_loan_commitment_usd,
    ROUND(total_relationship_value, 2) AS total_relationship_value_usd,
    DENSE_RANK() OVER (ORDER BY total_relationship_value DESC) AS wealth_rank
FROM customer_portfolio
ORDER BY wealth_rank
LIMIT 15;


-- -----------------------------------------------------------------------------
-- Query 03: Quarterly Customer Onboarding Velocity & Cumulative Growth
-- Business Question: What has been the quarterly velocity of customer acquisition
-- from 2019 to 2025, and what is the cumulative acquisition curve of the bank?
-- SQL Techniques: DATE_TRUNC, Window function SUM() OVER (ORDER BY ...), Running Total CTE.
-- -----------------------------------------------------------------------------
WITH quarterly_acquisitions AS (
    SELECT 
        DATE_TRUNC('quarter', created_at)::DATE AS onboarding_quarter,
        COUNT(customer_id) AS new_customers_acquired
    FROM customers
    GROUP BY DATE_TRUNC('quarter', created_at)::DATE
)
SELECT 
    onboarding_quarter,
    new_customers_acquired,
    SUM(new_customers_acquired) OVER (ORDER BY onboarding_quarter) AS cumulative_customers,
    ROUND(
        (new_customers_acquired - LAG(new_customers_acquired, 1) OVER (ORDER BY onboarding_quarter)) * 100.0 /
        NULLIF(LAG(new_customers_acquired, 1) OVER (ORDER BY onboarding_quarter), 0), 
        2
    ) AS qoq_growth_pct
FROM quarterly_acquisitions
ORDER BY onboarding_quarter;


-- -----------------------------------------------------------------------------
-- Query 04: Top Geographic Markets & City-Level Liquidity Benchmarking
-- Business Question: In the top 15 cities with highest customer concentration, how does
-- each city's average liquid balance per customer compare against the overall national bank average?
-- SQL Techniques: JOIN, GROUP BY, Window function benchmark, Difference calculation, HAVING.
-- -----------------------------------------------------------------------------
WITH city_aggregates AS (
    SELECT 
        c.city,
        COUNT(DISTINCT c.customer_id) AS city_customer_count,
        COUNT(a.account_id) AS city_account_count,
        COALESCE(SUM(a.balance_usd), 0) AS city_total_balance_usd,
        ROUND(COALESCE(AVG(a.balance_usd), 0), 2) AS city_avg_balance_per_account
    FROM customers c
    LEFT JOIN accounts a ON c.customer_id = a.customer_id
    GROUP BY c.city
    HAVING COUNT(DISTINCT c.customer_id) >= 10
),
benchmark AS (
    SELECT ROUND(AVG(balance_usd), 2) AS national_avg_account_balance FROM accounts
)
SELECT 
    ca.city,
    ca.city_customer_count,
    ca.city_account_count,
    ca.city_total_balance_usd,
    ca.city_avg_balance_per_account,
    b.national_avg_account_balance,
    ROUND(ca.city_avg_balance_per_account - b.national_avg_account_balance, 2) AS variance_from_national_avg,
    ROUND(((ca.city_avg_balance_per_account - b.national_avg_account_balance) / b.national_avg_account_balance) * 100.0, 2) AS variance_pct
FROM city_aggregates ca
CROSS JOIN benchmark b
ORDER BY ca.city_customer_count DESC
LIMIT 15;
