-- =============================================================================
-- BankScope — PostgreSQL Foreign Key & Data Integrity Constraints
-- Canonical Source: Verified SQLite Dataset (data/raw/.../bank_sqlite.db)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Foreign Key Constraints (Enforcing Verified Relational Integrity)
-- -----------------------------------------------------------------------------

-- accounts -> customers
ALTER TABLE accounts
    ADD CONSTRAINT fk_accounts_customers
    FOREIGN KEY (customer_id)
    REFERENCES customers (customer_id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE;

-- cards -> accounts
ALTER TABLE cards
    ADD CONSTRAINT fk_cards_accounts
    FOREIGN KEY (account_id)
    REFERENCES accounts (account_id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE;

-- loans -> customers
ALTER TABLE loans
    ADD CONSTRAINT fk_loans_customers
    FOREIGN KEY (customer_id)
    REFERENCES customers (customer_id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE;

-- transactions -> accounts
ALTER TABLE transactions
    ADD CONSTRAINT fk_transactions_accounts
    FOREIGN KEY (account_id)
    REFERENCES accounts (account_id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE;

-- transactions -> merchants
ALTER TABLE transactions
    ADD CONSTRAINT fk_transactions_merchants
    FOREIGN KEY (merchant_id)
    REFERENCES merchants (merchant_id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE;

-- -----------------------------------------------------------------------------
-- 2. Domain & Business Check Constraints (Supported by Empirical Data)
-- -----------------------------------------------------------------------------

-- Standard FICO credit score boundary [300, 850]
ALTER TABLE customers
    ADD CONSTRAINT chk_customers_credit_score
    CHECK (credit_score BETWEEN 300 AND 850);

-- Valid account types observed: 'Checking', 'Business', 'Savings'
ALTER TABLE accounts
    ADD CONSTRAINT chk_accounts_type
    CHECK (account_type IN ('Checking', 'Business', 'Savings'));

-- Non-negative account balance
ALTER TABLE accounts
    ADD CONSTRAINT chk_accounts_balance_usd
    CHECK (balance_usd >= 0);

-- Valid card types observed: 'Debit', 'Credit'
ALTER TABLE cards
    ADD CONSTRAINT chk_cards_type
    CHECK (card_type IN ('Debit', 'Credit'));

-- Positive loan principal amount
ALTER TABLE loans
    ADD CONSTRAINT chk_loans_loan_amount
    CHECK (loan_amount > 0);

-- Non-negative loan interest rate
ALTER TABLE loans
    ADD CONSTRAINT chk_loans_interest_rate
    CHECK (interest_rate >= 0);

-- Strictly positive transaction amount
ALTER TABLE transactions
    ADD CONSTRAINT chk_transactions_amount_usd
    CHECK (amount_usd > 0);
