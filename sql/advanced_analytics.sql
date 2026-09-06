-- =============================================================================
-- BankScope — Advanced SQL & Complex Analytical Engineering
-- Canonical Database: bankscope_db
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Query 28: Account Chronological Ledger Statement & Running Spend Reconstruction
-- Business Question: How can we reconstruct an account's chronological transaction ledger
-- with running cumulative spend and transaction sequence numbers for auditing?
-- SQL Techniques: Window functions SUM() OVER (PARTITION BY ... ROWS BETWEEN ...), ROW_NUMBER().
-- -----------------------------------------------------------------------------
WITH sample_account AS (
    -- Select an active checking account with frequent transactions
    SELECT account_id
    FROM transactions
    GROUP BY account_id
    HAVING COUNT(transaction_id) >= 20
    LIMIT 1
)
SELECT 
    t.account_id,
    ROW_NUMBER() OVER (PARTITION BY t.account_id ORDER BY t.transaction_date ASC) AS tx_sequence_num,
    t.transaction_id,
    t.transaction_date,
    m.merchant_name,
    m.city AS merchant_city,
    t.amount_usd,
    ROUND(
        SUM(t.amount_usd) OVER (
            PARTITION BY t.account_id 
            ORDER BY t.transaction_date ASC 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ), 
        2
    ) AS running_cumulative_spend_usd,
    ROUND(
        AVG(t.amount_usd) OVER (
            PARTITION BY t.account_id 
            ORDER BY t.transaction_date ASC 
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ), 
        2
    ) AS rolling_3tx_moving_avg_usd
FROM transactions t
JOIN merchants m ON t.merchant_id = m.merchant_id
WHERE t.account_id IN (SELECT account_id FROM sample_account)
ORDER BY t.transaction_date ASC;


-- -----------------------------------------------------------------------------
-- Query 29: Account Inactivity & Dormancy Risk Audit (Positive Balance Without Transactions)
-- Business Question: Which deposit accounts have held positive balances but recorded
-- zero transactions in the final 180 days of the dataset (post 2025-07-04), signaling churn?
-- SQL Techniques: Correlated Subquery / NOT EXISTS, Date math INTERVAL, LEFT JOIN, Filtering.
-- -----------------------------------------------------------------------------
SELECT 
    a.account_id,
    a.customer_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.email,
    c.city AS customer_city,
    a.account_type,
    ROUND(a.balance_usd, 2) AS dormant_balance_usd,
    a.open_date,
    MAX(t.transaction_date) AS last_active_transaction_date,
    DATE '2025-12-31' - MAX(t.transaction_date)::DATE AS days_inactive
FROM accounts a
JOIN customers c ON a.customer_id = c.customer_id
LEFT JOIN transactions t ON a.account_id = t.account_id
WHERE a.balance_usd > 1000.00
GROUP BY a.account_id, a.customer_id, c.first_name, c.last_name, c.email, c.city, a.account_type, a.balance_usd, a.open_date
HAVING MAX(t.transaction_date) < (DATE '2025-12-31' - INTERVAL '180 days')
    OR MAX(t.transaction_date) IS NULL
ORDER BY a.balance_usd DESC
LIMIT 20;


-- -----------------------------------------------------------------------------
-- Query 30: Cross-Selling White-Space Opportunity Identification
-- Business Question: Which high-credit-score customers (credit score >= 720) hold only a single
-- checking account without any secondary deposit account, loan, or credit card, representing prime cross-sell targets?
-- SQL Techniques: Multi-table LEFT JOIN, GROUP BY, HAVING, Conditional Aggregation, Array Aggregation.
-- -----------------------------------------------------------------------------
WITH customer_accounts AS (
    SELECT 
        customer_id,
        COUNT(account_id) AS total_accounts,
        SUM(CASE WHEN account_type = 'Checking' THEN 1 ELSE 0 END) AS checking_count,
        SUM(CASE WHEN account_type = 'Savings' THEN 1 ELSE 0 END) AS savings_count,
        SUM(CASE WHEN account_type = 'Business' THEN 1 ELSE 0 END) AS business_count,
        SUM(balance_usd) AS total_deposit_balance
    FROM accounts
    GROUP BY customer_id
),
customer_cards AS (
    SELECT 
        a.customer_id,
        COUNT(c.card_id) AS total_cards,
        SUM(CASE WHEN c.card_type = 'Credit' THEN 1 ELSE 0 END) AS credit_card_count
    FROM accounts a
    JOIN cards c ON a.account_id = c.account_id
    GROUP BY a.customer_id
),
customer_loans AS (
    SELECT 
        customer_id,
        COUNT(loan_id) AS total_loans
    FROM loans
    GROUP BY customer_id
),
customer_holdings AS (
    SELECT 
        c.customer_id,
        c.first_name || ' ' || c.last_name AS customer_name,
        c.email,
        c.city,
        c.credit_score,
        COALESCE(ca.total_accounts, 0) AS total_accounts,
        COALESCE(ca.checking_count, 0) AS checking_count,
        COALESCE(ca.savings_count, 0) AS savings_count,
        COALESCE(ca.business_count, 0) AS business_count,
        COALESCE(ca.total_deposit_balance, 0) AS total_deposit_balance,
        COALESCE(cc.total_cards, 0) AS total_cards,
        COALESCE(cc.credit_card_count, 0) AS credit_card_count,
        COALESCE(cl.total_loans, 0) AS total_loans
    FROM customers c
    JOIN customer_accounts ca ON c.customer_id = ca.customer_id
    LEFT JOIN customer_cards cc ON c.customer_id = cc.customer_id
    LEFT JOIN customer_loans cl ON c.customer_id = cl.customer_id
    WHERE c.credit_score >= 720
)
SELECT 
    customer_id,
    customer_name,
    city,
    credit_score,
    ROUND(total_deposit_balance, 2) AS total_deposit_balance_usd,
    total_accounts,
    total_cards,
    total_loans,
    'Prime Candidate for Savings / Credit Card / Personal Loan' AS recommended_campaign
FROM customer_holdings
WHERE total_accounts = 1 
  AND checking_count = 1 
  AND savings_count = 0 
  AND credit_card_count = 0 
  AND total_loans = 0
ORDER BY total_deposit_balance DESC
LIMIT 20;
