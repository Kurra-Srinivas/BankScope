-- =============================================================================
-- BankScope — PostgreSQL Index Architecture & Performance Optimization
-- Canonical Source: Verified SQLite Dataset (data/raw/.../bank_sqlite.db)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Foreign Key Join Indexes
-- PostgreSQL does not index foreign keys by default. These indexes prevent 
-- full-table scans during relational JOINs and referential integrity checks.
-- -----------------------------------------------------------------------------

-- Index for customer -> accounts lookups
CREATE INDEX IF NOT EXISTS idx_accounts_customer_id
    ON accounts (customer_id);

-- Index for account -> cards lookups
CREATE INDEX IF NOT EXISTS idx_cards_account_id
    ON cards (account_id);

-- Index for customer -> loans lookups
CREATE INDEX IF NOT EXISTS idx_loans_customer_id
    ON loans (customer_id);

-- Index for account -> transactions lookups (high volume: 1,000,000 rows)
CREATE INDEX IF NOT EXISTS idx_transactions_account_id
    ON transactions (account_id);

-- Index for merchant -> transactions lookups
CREATE INDEX IF NOT EXISTS idx_transactions_merchant_id
    ON transactions (merchant_id);

-- -----------------------------------------------------------------------------
-- 2. Transaction Analytics & Time-Series Slicing Indexes
-- Optimizes queries filtering on temporal intervals, cohorting, and RFM calculations.
-- -----------------------------------------------------------------------------

-- Pure date-range slicing (e.g. WHERE transaction_date >= '2024-01-01')
CREATE INDEX IF NOT EXISTS idx_transactions_date
    ON transactions (transaction_date);

-- Composite index for account timeline, running balances, and statement queries
CREATE INDEX IF NOT EXISTS idx_transactions_account_date
    ON transactions (account_id, transaction_date DESC);

-- Composite index for merchant performance and revenue tracking over time
CREATE INDEX IF NOT EXISTS idx_transactions_merchant_date
    ON transactions (merchant_id, transaction_date DESC);

-- Index for high-value transaction filtering and percentile/distribution analytics
CREATE INDEX IF NOT EXISTS idx_transactions_amount
    ON transactions (amount_usd);

-- -----------------------------------------------------------------------------
-- 3. Dimension Filtering & Segmentation Indexes
-- -----------------------------------------------------------------------------

-- Geographic customer distribution and segmentation
CREATE INDEX IF NOT EXISTS idx_customers_city
    ON customers (city);

-- Credit risk banding and score stratification
CREATE INDEX IF NOT EXISTS idx_customers_credit_score
    ON customers (credit_score);

-- Account type stratification (Checking, Savings, Business)
CREATE INDEX IF NOT EXISTS idx_accounts_type
    ON accounts (account_type);

-- Card product categorization (Debit, Credit)
CREATE INDEX IF NOT EXISTS idx_cards_type
    ON cards (card_type);

-- Merchant location analysis
CREATE INDEX IF NOT EXISTS idx_merchants_city
    ON merchants (city);
