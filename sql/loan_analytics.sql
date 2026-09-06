-- =============================================================================
-- BankScope — Loan Analytics SQL
-- Canonical Database: bankscope_db
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Query 13: Loan Portfolio Exposure & APR Risk Tier Stratification
-- Business Question: How is the total loan exposure distributed across interest rate
-- risk tiers (Low <5%, Prime 5-8%, Standard 8-12%, Subprime >12%), and what is the weighted
-- average APR in each tier?
-- SQL Techniques: CASE expressions, Aggregate functions, Weighted average calculations, Window percentage.
-- -----------------------------------------------------------------------------
WITH loan_tiers AS (
    SELECT 
        loan_id,
        customer_id,
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
    ROUND(COUNT(loan_id) * 100.0 / SUM(COUNT(loan_id)) OVER (), 2) AS loan_count_share_pct,
    ROUND(SUM(loan_amount), 2) AS total_principal_usd,
    ROUND(SUM(loan_amount) * 100.0 / SUM(SUM(loan_amount)) OVER (), 2) AS principal_share_pct,
    ROUND(AVG(loan_amount), 2) AS avg_loan_size_usd,
    ROUND(SUM(loan_amount * interest_rate) / SUM(loan_amount), 2) AS weighted_avg_interest_rate,
    ROUND(MIN(interest_rate), 2) AS min_interest_rate,
    ROUND(MAX(interest_rate), 2) AS max_interest_rate
FROM loan_tiers
GROUP BY interest_rate_tier
ORDER BY interest_rate_tier;


-- -----------------------------------------------------------------------------
-- Query 14: Credit Score vs Interest Rate Risk-Based Pricing Audit
-- Business Question: Does the bank effectively implement risk-based pricing by assigning
-- lower interest rates to higher credit-score borrowers across customer tiers?
-- SQL Techniques: INNER JOIN, CASE credit tiers, AVG, STDDEV, MIN, MAX, Correlation check.
-- -----------------------------------------------------------------------------
SELECT 
    CASE 
        WHEN c.credit_score BETWEEN 300 AND 579 THEN '1. Poor (300-579)'
        WHEN c.credit_score BETWEEN 580 AND 669 THEN '2. Fair (580-669)'
        WHEN c.credit_score BETWEEN 670 AND 739 THEN '3. Good (670-739)'
        WHEN c.credit_score BETWEEN 740 AND 799 THEN '4. Very Good (740-799)'
        WHEN c.credit_score BETWEEN 800 AND 850 THEN '5. Exceptional (800-850)'
        ELSE 'Unknown'
    END AS borrower_credit_tier,
    COUNT(l.loan_id) AS total_loans_issued,
    ROUND(AVG(c.credit_score), 1) AS avg_credit_score,
    ROUND(AVG(l.interest_rate), 2) AS avg_interest_rate,
    ROUND(MIN(l.interest_rate), 2) AS min_interest_rate,
    ROUND(MAX(l.interest_rate), 2) AS max_interest_rate,
    ROUND(AVG(l.loan_amount), 2) AS avg_loan_amount_usd,
    ROUND(SUM(l.loan_amount), 2) AS total_loan_exposure_usd
FROM loans l
JOIN customers c ON l.customer_id = c.customer_id
GROUP BY 
    CASE 
        WHEN c.credit_score BETWEEN 300 AND 579 THEN '1. Poor (300-579)'
        WHEN c.credit_score BETWEEN 580 AND 669 THEN '2. Fair (580-669)'
        WHEN c.credit_score BETWEEN 670 AND 739 THEN '3. Good (670-739)'
        WHEN c.credit_score BETWEEN 740 AND 799 THEN '4. Very Good (740-799)'
        WHEN c.credit_score BETWEEN 800 AND 850 THEN '5. Exceptional (800-850)'
        ELSE 'Unknown'
    END
ORDER BY borrower_credit_tier;


-- -----------------------------------------------------------------------------
-- Query 15: Annual Loan Origination Velocity & Cumulative Capital Exposure
-- Business Question: What is the year-over-year progression of newly originated loan capital,
-- and what is the cumulative loan book exposure over the bank's operational history?
-- SQL Techniques: EXTRACT(YEAR FROM ...), Window function SUM() OVER (), YoY growth calculation.
-- -----------------------------------------------------------------------------
WITH annual_loans AS (
    SELECT 
        EXTRACT(YEAR FROM start_date)::INT AS origination_year,
        COUNT(loan_id) AS loans_originated,
        SUM(loan_amount) AS annual_origination_volume_usd,
        AVG(interest_rate) AS avg_annual_interest_rate
    FROM loans
    GROUP BY EXTRACT(YEAR FROM start_date)::INT
)
SELECT 
    origination_year,
    loans_originated,
    ROUND(annual_origination_volume_usd, 2) AS annual_volume_usd,
    ROUND(
        (annual_origination_volume_usd - LAG(annual_origination_volume_usd, 1) OVER (ORDER BY origination_year)) * 100.0 /
        NULLIF(LAG(annual_origination_volume_usd, 1) OVER (ORDER BY origination_year), 0),
        2
    ) AS yoy_volume_growth_pct,
    ROUND(SUM(annual_origination_volume_usd) OVER (ORDER BY origination_year), 2) AS cumulative_loan_exposure_usd,
    ROUND(avg_annual_interest_rate, 2) AS avg_origination_rate
FROM annual_loans
ORDER BY origination_year;


-- -----------------------------------------------------------------------------
-- Query 16: Customer Debt-to-Liquidity Leverage Audit (High-Risk Borrowers)
-- Business Question: Which borrowers have an extreme debt-to-liquidity ratio where their
-- loan commitments exceed 5x their total liquid deposit balances, representing default vulnerability?
-- SQL Techniques: CTEs, Multi-table aggregation, Debt-to-deposit ratio, Filtering.
-- -----------------------------------------------------------------------------
WITH customer_deposits AS (
    SELECT 
        customer_id,
        COALESCE(SUM(balance_usd), 0) AS total_deposits_usd
    FROM accounts
    GROUP BY customer_id
),
customer_debt AS (
    SELECT 
        customer_id,
        COUNT(loan_id) AS active_loan_count,
        SUM(loan_amount) AS total_debt_usd,
        ROUND(AVG(interest_rate), 2) AS avg_borrowing_rate
    FROM loans
    GROUP BY customer_id
)
SELECT 
    c.customer_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.city,
    c.credit_score,
    d.active_loan_count,
    ROUND(d.total_debt_usd, 2) AS total_debt_usd,
    ROUND(COALESCE(dep.total_deposits_usd, 0), 2) AS total_deposits_usd,
    ROUND(d.total_debt_usd / NULLIF(COALESCE(dep.total_deposits_usd, 0), 0), 2) AS debt_to_deposit_ratio,
    d.avg_borrowing_rate
FROM customer_debt d
JOIN customers c ON d.customer_id = c.customer_id
LEFT JOIN customer_deposits dep ON d.customer_id = dep.customer_id
WHERE COALESCE(dep.total_deposits_usd, 0) > 0 
  AND (d.total_debt_usd / dep.total_deposits_usd) >= 5.0
ORDER BY debt_to_deposit_ratio DESC
LIMIT 20;
