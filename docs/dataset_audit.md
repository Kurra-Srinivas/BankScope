# BankScope — Canonical Dataset Audit & Forensic Parity Report

**Target Database**: PostgreSQL 18.0 (`bankscope_db`)  
**Canonical Source**: SQLite 3 (`data/raw/banking_dataset_kaggle/data/database/bank_sqlite.db`)  
**Audit Protocol**: Fresh, direct validation comparing live PostgreSQL engine against canonical SQLite source. Zero reliance on cached documents or static approximations.

---

## 1. Executive Summary & Verification Matrix

Automated live queries executed directly against both databases confirm **100.00% statistical and referential parity** across all 7 relational entities:

| Entity Name | Canonical SQLite Rows | Live PostgreSQL Rows | Match Status | Primary Key Uniqueness | Foreign Key Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`customers`** | 50,000 | 50,000 | **PASS** | 50,000 / 50,000 (100% Unique) | Root Dimension Entity |
| **`accounts`** | 75,000 | 75,000 | **PASS** | 75,000 / 75,000 (100% Unique) | 0 Orphans ➔ `customers` |
| **`cards`** | 100,000 | 100,000 | **PASS** | 100,000 / 100,000 (100% Unique) | 0 Orphans ➔ `accounts` |
| **`loans`** | 30,000 | 30,000 | **PASS** | 30,000 / 30,000 (100% Unique) | 0 Orphans ➔ `customers` |
| **`merchants`** | 5,000 | 5,000 | **PASS** | 5,000 / 5,000 (100% Unique) | Root Dimension Entity |
| **`branches`** | 500 | 500 | **PASS** | 500 / 500 (100% Unique) | Standalone Entity (0 FKs) |
| **`transactions`** | 1,000,000 | 1,000,000 | **PASS** | 1,000,000 / 1,000,000 (100% Unique) | 0 Orphans ➔ `accounts`, `merchants` |
| **Total Warehouse** | **1,260,500** | **1,260,500** | **PASS** | **Zero Collisions** | **Zero Orphan Records** |

---

## 2. Canonical Financial Ledger Metrics

Fresh aggregation queries executed directly against PostgreSQL and SQLite verify identical ledger totals:

### A. Deposit Ledger (`accounts`)
* **Live Query**: `SELECT SUM(balance_usd), AVG(balance_usd), MIN(balance_usd), MAX(balance_usd) FROM accounts;`
* **Total Deposits**: **$7,494,138,742.77** (PostgreSQL) | **$7,494,138,742.77** (SQLite)
* **Average Account Balance**: **$99,921.85**
* **Balance Range**: $0.00 to $199,999.55

### B. Lending Portfolio (`loans`)
* **Live Query**: `SELECT SUM(loan_amount), AVG(loan_amount), MIN(loan_amount), MAX(loan_amount), AVG(interest_rate) FROM loans;`
* **Total Loan Principal**: **$4,513,099,925.48** (PostgreSQL) | **$4,513,099,925.48** (SQLite)
* **Average Loan Principal**: **$150,436.66**
* **Loan Principal Range**: $5,000.00 to $250,000.00
* **Average APR**: **8.50%** (Range: 3.00% to 15.00%)

### C. Payment Transactions (`transactions`)
* **Live Query**: `SELECT MIN(transaction_date), MAX(transaction_date), SUM(amount_usd), AVG(amount_usd), MIN(amount_usd), MAX(amount_usd) FROM transactions;`
* **Temporal Horizon**: `2019-01-01 00:00:23` to `2025-12-31 23:55:27` (7 Full Calendar Years)
* **Total Transaction Volume**: **$5,001,164,534.00** (PostgreSQL) | **$5,001,164,534.00** (SQLite)
* **Average Ticket Size**: **$5,001.16**
* **Transaction Ticket Range**: **$1.02** to **$9,999.98**
* **Transacting Customer Base**: **38,849 unique customers** out of 50,000 customer profiles

---

## 3. Referential Integrity & Foreign Key Audit

All 5 foreign key constraints enforce strict referential boundaries with **zero orphan records**:

```
[PASS] accounts.customer_id     ➔ customers.customer_id     (75,000 child records | 0 orphans)
[PASS] cards.account_id         ➔ accounts.account_id       (100,000 child records | 0 orphans)
[PASS] loans.customer_id        ➔ customers.customer_id     (30,000 child records | 0 orphans)
[PASS] transactions.account_id  ➔ accounts.account_id       (1,000,000 child records | 0 orphans)
[PASS] transactions.merchant_id ➔ merchants.merchant_id     (1,000,000 child records | 0 orphans)
```

---

## 4. Empirical Boundary: Standalone `branches` Catalog

* **Table Size**: 500 rows (`branch_id`, `branch_name`, `city`, `state`).
* **Foreign Key Links**: **0**. No table in the canonical SQLite schema (`accounts`, `loans`, `customers`, or `transactions`) contains a `branch_id` column.
* **Data Quality Issue in Source**: In canonical SQLite (`bank_sqlite.db`), `branches.city` is **100% NULL** (500 / 500 null values).
* **Architecture Treatment**: Maintained as an unlinked physical facility reference directory. No synthetic foreign keys or artificial linkages have been introduced.
