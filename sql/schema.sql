-- =============================================================================
-- BankScope — PostgreSQL Database DDL
-- Canonical Source: Verified SQLite Dataset (data/raw/.../bank_sqlite.db)
-- =============================================================================

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS cards CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;
DROP TABLE IF EXISTS loans CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS merchants CASCADE;
DROP TABLE IF EXISTS branches CASCADE;

-- -----------------------------------------------------------------------------
-- 1. Customers Table (Independent Core Entity)
-- -----------------------------------------------------------------------------
CREATE TABLE customers (
    customer_id     VARCHAR(20)     NOT NULL,
    first_name      VARCHAR(50)     NOT NULL,
    last_name       VARCHAR(50)     NOT NULL,
    email           VARCHAR(100)    NOT NULL,
    city            VARCHAR(50)     NOT NULL,
    credit_score    INTEGER         NOT NULL,
    created_at      TIMESTAMP       NOT NULL,
    CONSTRAINT pk_customers PRIMARY KEY (customer_id)
);

-- -----------------------------------------------------------------------------
-- 2. Merchants Table (Independent Merchant Entity)
-- -----------------------------------------------------------------------------
CREATE TABLE merchants (
    merchant_id     VARCHAR(20)     NOT NULL,
    merchant_name   VARCHAR(100)    NOT NULL,
    city            VARCHAR(50)     NOT NULL,
    CONSTRAINT pk_merchants PRIMARY KEY (merchant_id)
);

-- -----------------------------------------------------------------------------
-- 3. Branches Table (Independent Reference Entity)
-- Note: Discovered unlinked in forensic analysis (city & country are nullable)
-- -----------------------------------------------------------------------------
CREATE TABLE branches (
    branch_id       VARCHAR(20)     NOT NULL,
    branch_name     VARCHAR(100)    NOT NULL,
    manager_name    VARCHAR(100)    NOT NULL,
    city            VARCHAR(50),
    country         VARCHAR(50),
    CONSTRAINT pk_branches PRIMARY KEY (branch_id)
);

-- -----------------------------------------------------------------------------
-- 4. Accounts Table (Child of Customers)
-- -----------------------------------------------------------------------------
CREATE TABLE accounts (
    account_id      VARCHAR(20)     NOT NULL,
    customer_id     VARCHAR(20)     NOT NULL,
    account_type    VARCHAR(20)     NOT NULL,
    balance_usd     NUMERIC(12, 2)  NOT NULL,
    open_date       TIMESTAMP       NOT NULL,
    CONSTRAINT pk_accounts PRIMARY KEY (account_id)
);

-- -----------------------------------------------------------------------------
-- 5. Cards Table (Child of Accounts)
-- -----------------------------------------------------------------------------
CREATE TABLE cards (
    card_id         VARCHAR(20)     NOT NULL,
    account_id      VARCHAR(20)     NOT NULL,
    card_type       VARCHAR(20)     NOT NULL,
    expiration_date TIMESTAMP       NOT NULL,
    CONSTRAINT pk_cards PRIMARY KEY (card_id)
);

-- -----------------------------------------------------------------------------
-- 6. Loans Table (Child of Customers)
-- -----------------------------------------------------------------------------
CREATE TABLE loans (
    loan_id         VARCHAR(20)     NOT NULL,
    customer_id     VARCHAR(20)     NOT NULL,
    loan_amount     NUMERIC(12, 2)  NOT NULL,
    interest_rate   NUMERIC(5, 2)   NOT NULL,
    start_date      TIMESTAMP       NOT NULL,
    CONSTRAINT pk_loans PRIMARY KEY (loan_id)
);

-- -----------------------------------------------------------------------------
-- 7. Transactions Table (Child of Accounts and Merchants)
-- -----------------------------------------------------------------------------
CREATE TABLE transactions (
    transaction_id   VARCHAR(25)    NOT NULL,
    account_id       VARCHAR(20)    NOT NULL,
    merchant_id      VARCHAR(20)    NOT NULL,
    amount_usd       NUMERIC(12, 2) NOT NULL,
    transaction_date TIMESTAMP      NOT NULL,
    CONSTRAINT pk_transactions PRIMARY KEY (transaction_id)
);
