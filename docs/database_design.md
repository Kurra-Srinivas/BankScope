# BankScope — PostgreSQL Database Design Document

**Document Version**: 1.0  
**Status**: Ready for Schema Application (Migration Pending)  
**Canonical Data Source**: `data/raw/banking_dataset_kaggle/data/database/bank_sqlite.db`  

---

## 1. Design Overview & Architectural Principles

The BankScope database design translates the forensic findings from the verified SQLite database into an enterprise-grade, 3NF normalized PostgreSQL relational schema.

### Core Architectural Decisions
* **Strict Alignment with Verified Data**: All column names, data types, and nullability constraints reflect the actual empirical data present in `bank_sqlite.db`.
* **Zero Invented Relationships**: Relationships are established solely where foreign keys exist and are referentially valid across the 1,000,000 transaction records and related parent tables.
* **Separation of Concerns (DDL Modularization)**:
  - [`sql/schema.sql`](../sql/schema.sql): Table definitions and primary keys.
  - [`sql/constraints.sql`](../sql/constraints.sql): Foreign key relationships and domain CHECK constraints.
  - [`sql/indexes.sql`](../sql/indexes.sql): Performance and analytical query optimization indexes.
* **Independent Reference Entity for Branches**: Because `branches` is not referenced by `accounts`, `loans`, or `customers`, it is maintained as an independent table without artificial foreign keys.

---

## 2. Table-by-Table Specifications

### 1. `customers`
* **Role**: Primary customer master demographic and credit risk entity.
* **Volume**: 50,000 rows.
* **Primary Key**: `customer_id` (`VARCHAR(20)`).

| Column | PostgreSQL Data Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `customer_id` | `VARCHAR(20)` | **NO** | `PRIMARY KEY` | Unique customer identifier |
| `first_name` | `VARCHAR(50)` | **NO** | | Customer given name |
| `last_name` | `VARCHAR(50)` | **NO** | | Customer surname |
| `email` | `VARCHAR(100)` | **NO** | *(Non-unique in raw data)* | Contact email address |
| `city` | `VARCHAR(50)` | **NO** | | Residential city |
| `credit_score` | `INTEGER` | **NO** | `CHECK (credit_score BETWEEN 300 AND 850)` | FICO credit score |
| `created_at` | `TIMESTAMP` | **NO** | | Account onboarding timestamp |

---

### 2. `accounts`
* **Role**: Deposit, checking, and savings account holdings linked to customers.
* **Volume**: 75,000 rows.
* **Primary Key**: `account_id` (`VARCHAR(20)`).

| Column | PostgreSQL Data Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `account_id` | `VARCHAR(20)` | **NO** | `PRIMARY KEY` | Unique account identifier |
| `customer_id` | `VARCHAR(20)` | **NO** | `REFERENCES customers(customer_id)` | Owning customer foreign key |
| `account_type` | `VARCHAR(20)` | **NO** | `CHECK (account_type IN ('Checking', 'Business', 'Savings'))` | Account category |
| `balance_usd` | `NUMERIC(12, 2)` | **NO** | `CHECK (balance_usd >= 0)` | Current account ledger balance in USD |
| `open_date` | `TIMESTAMP` | **NO** | | Account opening timestamp |

---

### 3. `cards`
* **Role**: Payment cards (debit and credit) linked to customer bank accounts.
* **Volume**: 100,000 rows.
* **Primary Key**: `card_id` (`VARCHAR(20)`).

| Column | PostgreSQL Data Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `card_id` | `VARCHAR(20)` | **NO** | `PRIMARY KEY` | Unique card identifier |
| `account_id` | `VARCHAR(20)` | **NO** | `REFERENCES accounts(account_id)` | Associated bank account foreign key |
| `card_type` | `VARCHAR(20)` | **NO** | `CHECK (card_type IN ('Debit', 'Credit'))` | Card instrument type |
| `expiration_date`| `TIMESTAMP` | **NO** | | Card expiration date |

---

### 4. `loans`
* **Role**: Credit facilities and borrowing commitments issued to customers.
* **Volume**: 30,000 rows.
* **Primary Key**: `loan_id` (`VARCHAR(20)`).

| Column | PostgreSQL Data Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `loan_id` | `VARCHAR(20)` | **NO** | `PRIMARY KEY` | Unique loan contract identifier |
| `customer_id` | `VARCHAR(20)` | **NO** | `REFERENCES customers(customer_id)` | Borrower customer foreign key |
| `loan_amount` | `NUMERIC(12, 2)` | **NO** | `CHECK (loan_amount > 0)` | Disbursed principal amount in USD |
| `interest_rate`| `NUMERIC(5, 2)` | **NO** | `CHECK (interest_rate >= 0)` | Annual percentage rate (APR) |
| `start_date` | `TIMESTAMP` | **NO** | | Loan disbursement date |

---

### 5. `merchants`
* **Role**: Commercial merchant entities accepting payments from accounts.
* **Volume**: 5,000 rows.
* **Primary Key**: `merchant_id` (`VARCHAR(20)`).

| Column | PostgreSQL Data Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `merchant_id` | `VARCHAR(20)` | **NO** | `PRIMARY KEY` | Unique merchant identifier |
| `merchant_name`| `VARCHAR(100)` | **NO** | | Business trade name |
| `city` | `VARCHAR(50)` | **NO** | | Business physical location |

---

### 6. `branches`
* **Role**: Physical branch network reference entity.
* **Volume**: 500 rows.
* **Primary Key**: `branch_id` (`VARCHAR(20)`).
* **Forensic Status**: Independent reference table. `city` and `country` are nullable to maintain compatibility with `bank_sqlite.db` (where they are null) while allowing ingestion from `branches_inserts.sql`.

| Column | PostgreSQL Data Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `branch_id` | `VARCHAR(20)` | **NO** | `PRIMARY KEY` | Unique branch identifier |
| `branch_name` | `VARCHAR(100)` | **NO** | | Branch office name |
| `manager_name` | `VARCHAR(100)` | **NO** | | Branch manager name |
| `city` | `VARCHAR(50)` | YES | | Branch city |
| `country` | `VARCHAR(50)` | YES | | Branch country |

---

### 7. `transactions`
* **Role**: High-volume core ledger fact recording account payment flow to merchants.
* **Volume**: 1,000,000 rows.
* **Primary Key**: `transaction_id` (`VARCHAR(25)`).

| Column | PostgreSQL Data Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `transaction_id` | `VARCHAR(25)` | **NO** | `PRIMARY KEY` | Unique ledger transaction ID |
| `account_id` | `VARCHAR(20)` | **NO** | `REFERENCES accounts(account_id)` | Originating account foreign key |
| `merchant_id` | `VARCHAR(20)` | **NO** | `REFERENCES merchants(merchant_id)` | Destination merchant foreign key |
| `amount_usd` | `NUMERIC(12, 2)` | **NO** | `CHECK (amount_usd > 0)` | Transaction monetary amount |
| `transaction_date`| `TIMESTAMP` | **NO** | | Transaction settlement timestamp |

---

## 3. Relational Structure & Cardinality Summary

```
  ┌──────────────┐
  │  customers   │
  └──────┬───────┘
         │
         ├─── (1 : M) ───► accounts ─── (1 : M) ───► cards
         │                    │
         │                    └─── (1 : M) ───┐
         │                                    │
         └─── (1 : M) ───► loans              ▼
                                        transactions ◄─── (1 : M) ─── merchants
                                              
  ┌──────────────┐
  │   branches   │  (Independent reference entity; unlinked in source schema)
  └──────────────┘
```

| Parent Entity | Parent Key | Child Entity | Child Key | Cardinality | Enforced Action |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `customers` | `customer_id` | `accounts` | `customer_id` | 1 to Many | `ON DELETE RESTRICT ON UPDATE CASCADE` |
| `customers` | `customer_id` | `loans` | `customer_id` | 1 to Many | `ON DELETE RESTRICT ON UPDATE CASCADE` |
| `accounts` | `account_id` | `cards` | `account_id` | 1 to Many | `ON DELETE RESTRICT ON UPDATE CASCADE` |
| `accounts` | `account_id` | `transactions`| `account_id` | 1 to Many | `ON DELETE RESTRICT ON UPDATE CASCADE` |
| `merchants` | `merchant_id` | `transactions`| `merchant_id` | 1 to Many | `ON DELETE RESTRICT ON UPDATE CASCADE` |

---

## 4. Index Architecture & Query Optimization Plan

1. **Foreign Key Acceleration**:
   - `idx_accounts_customer_id`: Eliminates sequential scans on `accounts` when joining from `customers`.
   - `idx_cards_account_id`: Accelerates card inventory lookups per account.
   - `idx_loans_customer_id`: Accelerates customer loan exposure aggregations.
   - `idx_transactions_account_id`: Critical index enabling fast transaction lookups on the 1,000,000-row ledger for specific accounts.
   - `idx_transactions_merchant_id`: Enables fast merchant settlement aggregations.
2. **Analytical Composite & Time-Series Indexes**:
   - `idx_transactions_date`: Accelerates date range queries (monthly, quarterly, year-over-year).
   - `idx_transactions_account_date`: Composite index on `(account_id, transaction_date DESC)` supporting running balance calculations, recent transaction lookups, and windowed CTEs.
   - `idx_transactions_merchant_date`: Composite index on `(merchant_id, transaction_date DESC)` for merchant trend analysis.
   - `idx_transactions_amount`: Accelerates monetary band and outlier queries.
3. **Dimension Slicing Indexes**:
   - `idx_customers_city`, `idx_customers_credit_score`, `idx_accounts_type`, `idx_cards_type`, `idx_merchants_city`.
