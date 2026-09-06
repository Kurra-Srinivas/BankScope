# BankScope — Dataset Forensic Analysis Report

**Date**: 2026-09-06  
**Scope**: Raw Banking Dataset Forensic Inventory  
**Target Directory**: `data/raw/banking_dataset_kaggle/data/`  
**Analyzed Artifacts**: 6 CSV files, 1 SQLite database (`bank_sqlite.db`), 9 SQL scripts  

---

## 1. Executive Summary & Critical Findings

1. **Transaction Data Location**:
   - There is **NO `transactions.csv`** file in the raw dataset.
   - The complete transaction dataset is stored in **`database/bank_sqlite.db`** (table `transactions`, exactly **1,000,000 rows**) and in **`sql/transactions_inserts.sql`** (189.58 MB, 1,000,000 SQL INSERT statements).
2. **Dataset Divergence (Two Generation Runs)**:
   - Forensic analysis revealed that the standalone CSV files (`customers.csv`, `accounts.csv`, etc.) and `bank_sqlite.db` represent two different random-seed generation runs from the synthetic generator.
   - **`bank_sqlite.db` is 100% internally consistent across all 7 tables** (`customers`, `accounts`, `cards`, `loans`, `merchants`, `transactions`, `branches`). Foreign keys between `transactions -> accounts` and `transactions -> merchants` match with zero orphan records in `bank_sqlite.db`.
   - `bank.sql` (230.15 MB) matches `bank_sqlite.db` exactly.
3. **The Branches Discrepancy**:
   - In `bank_sqlite.db`, `branches` has 500 rows, but `city` and `country` are 100% `NULL` (0/500 populated).
   - In `branches.csv`, there are only 3 columns (`branch_id`, `branch_name`, `manager_name`).
   - In `branches_inserts.sql`, `branches` has all 5 columns populated (`branch_id`, `branch_name`, `city`, `country`, `manager_name`).
4. **Branches Relational Linkage**:
   - `branches` is currently an unlinked/isolated reference table. Neither `accounts`, `loans`, nor `customers` contain a `branch_id` column. A geographic or synthetic assignment can link branches to customers/accounts during downstream modeling.

---

## 2. File Inventory & Storage Summary

| Source Subdirectory | File Name | Size (MB) | Format | Description / Role |
| :--- | :--- | :--- | :--- | :--- |
| `csv/` | `accounts.csv` | 4.36 MB | CSV | 75,000 account records |
| `csv/` | `branches.csv` | 0.02 MB | CSV | 500 branch records (3 columns) |
| `csv/` | `cards.csv` | 4.72 MB | CSV | 100,000 payment card records |
| `csv/` | `customers.csv` | 3.86 MB | CSV | 50,000 customer profile records |
| `csv/` | `loans.csv` | 1.65 MB | CSV | 30,000 loan records |
| `csv/` | `merchants.csv` | 0.23 MB | CSV | 5,000 merchant records |
| `database/` | `bank_sqlite.db` | 102.30 MB | SQLite3 | Complete relational database with 7 tables |
| `sql/` | `schema.sql` | <0.01 MB | SQL DDL | Target schema definitions with constraints |
| `sql/` | `bank.sql` | 230.15 MB | SQL Dump | Consolidated database dump (matches SQLite) |
| `sql/` | `accounts_inserts.sql` | 12.80 MB | SQL | Individual INSERTs for accounts |
| `sql/` | `branches_inserts.sql` | 0.08 MB | SQL | Individual INSERTs for branches (with city/country) |
| `sql/` | `cards_inserts.sql` | 14.07 MB | SQL | Individual INSERTs for cards |
| `sql/` | `customers_inserts.sql` | 10.39 MB | SQL | Individual INSERTs for customers |
| `sql/` | `loans_inserts.sql` | 4.92 MB | SQL | Individual INSERTs for loans |
| `sql/` | `merchants_inserts.sql` | 0.58 MB | SQL | Individual INSERTs for merchants |
| `sql/` | `transactions_inserts.sql`| 189.58 MB | SQL | 1,000,000 INSERT statements for transactions |

---

## 3. CSV Dataset Profiles

| CSV File | Row Count | Column Count | Column Names | Inferred Data Types |
| :--- | :--- | :--- | :--- | :--- |
| `customers.csv` | 50,000 | 7 | `customer_id`, `first_name`, `last_name`, `email`, `city`, `credit_score`, `created_at` | `customer_id`: string<br>`first_name`: string<br>`last_name`: string<br>`email`: string<br>`city`: string<br>`credit_score`: int64<br>`created_at`: timestamp |
| `accounts.csv` | 75,000 | 5 | `account_id`, `customer_id`, `account_type`, `balance_usd`, `open_date` | `account_id`: string<br>`customer_id`: string<br>`account_type`: string<br>`balance_usd`: float64<br>`open_date`: timestamp |
| `cards.csv` | 100,000 | 4 | `card_id`, `account_id`, `card_type`, `expiration_date` | `card_id`: string<br>`account_id`: string<br>`card_type`: string<br>`expiration_date`: timestamp |
| `loans.csv` | 30,000 | 5 | `loan_id`, `customer_id`, `loan_amount`, `interest_rate`, `start_date` | `loan_id`: string<br>`customer_id`: string<br>`loan_amount`: float64<br>`interest_rate`: float64<br>`start_date`: timestamp |
| `merchants.csv` | 5,000 | 3 | `merchant_id`, `merchant_name`, `city` | `merchant_id`: string<br>`merchant_name`: string<br>`city`: string |
| `branches.csv` | 500 | 3 | `branch_id`, `branch_name`, `manager_name` | `branch_id`: string<br>`branch_name`: string<br>`manager_name`: string |

---

## 4. SQLite Database (`bank_sqlite.db`) Table Profiles

| Table Name | Exact Row Count | Primary Key Candidate | Candidate Unique? | Null Issues Found | Columns & SQLite Types |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `customers` | 50,000 | `customer_id` | **Yes** (50,000 distinct) | 0 nulls | `customer_id` TEXT, `first_name` TEXT, `last_name` TEXT, `email` TEXT, `city` TEXT, `credit_score` INTEGER, `created_at` TIMESTAMP |
| `accounts` | 75,000 | `account_id` | **Yes** (75,000 distinct) | 0 nulls | `account_id` TEXT, `customer_id` TEXT, `account_type` TEXT, `balance_usd` REAL, `open_date` TIMESTAMP |
| `cards` | 100,000 | `card_id` | **Yes** (100,000 distinct) | 0 nulls | `card_id` TEXT, `account_id` TEXT, `card_type` TEXT, `expiration_date` TIMESTAMP |
| `loans` | 30,000 | `loan_id` | **Yes** (30,000 distinct) | 0 nulls | `loan_id` TEXT, `customer_id` TEXT, `loan_amount` REAL, `interest_rate` REAL, `start_date` TIMESTAMP |
| `merchants` | 5,000 | `merchant_id` | **Yes** (5,000 distinct) | 0 nulls | `merchant_id` TEXT, `merchant_name` TEXT, `city` TEXT |
| `branches` | 500 | `branch_id` | **Yes** (500 distinct) | **`city` (500), `country` (500)** | `branch_id` TEXT, `branch_name` TEXT, `manager_name` TEXT, `city` TEXT, `country` TEXT |
| `transactions` | 1,000,000 | `transaction_id` | **Yes** (1,000,000 distinct) | 0 nulls | `transaction_id` TEXT, `account_id` TEXT, `merchant_id` TEXT, `amount_usd` REAL, `transaction_date` TIMESTAMP |

---

## 5. Transactions Table Deep Investigation

* **Presence in SQLite**: Confirmed (`bank_sqlite.db` holds the complete table).
* **Row Count**: Exactly **1,000,000 rows**.
* **Columns**:
  1. `transaction_id` (Primary Key candidate, 100% unique)
  2. `account_id` (Foreign Key -> `accounts.account_id`, 0 orphan records in SQLite)
  3. `merchant_id` (Foreign Key -> `merchants.merchant_id`, 0 orphan records in SQLite)
  4. `amount_usd` (Transaction amount in USD)
  5. `transaction_date` (Timestamp)
* **Statistical Distribution**:
  - **Date Range**: `2019-01-01 00:00:23` to `2025-12-31 23:55:27` (7 complete calendar years)
  - **Minimum Amount**: `$1.02`
  - **Maximum Amount**: `$9,999.98`
  - **Average Amount**: `$5,001.16`
  - **Null Counts**: `0` across all 5 columns.
* **Migration Recommendation**:
  - Direct export from `bank_sqlite.db` using Python/SQLAlchemy chunked streams into PostgreSQL `COPY` or parquet/CSV extraction is orders of magnitude faster and safer than parsing the 189 MB `transactions_inserts.sql` text file.

---

## 6. Relational Structure & Foreign Key Candidates

```
  customers (customer_id)
     │
     ├── 1:M ──> accounts (account_id, customer_id)
     │               │
     │               ├── 1:M ──> cards (card_id, account_id)
     │               │
     │               └── 1:M ──> transactions (transaction_id, account_id, merchant_id)
     │                                     ▲
     │                                     │ 1:M
     │                               merchants (merchant_id)
     │
     └── 1:M ──> loans (loan_id, customer_id)

  branches (branch_id, branch_name, manager_name, city, country)  <-- [Isolated Reference Entity]
```

### Relational Matrix

| Parent Table | Parent Key | Child Table | Child Key | Cardinality | SQLite Integrity Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `customers` | `customer_id` | `accounts` | `customer_id` | 1 : Many | Supported, clean |
| `customers` | `customer_id` | `loans` | `customer_id` | 1 : Many | Supported, clean |
| `accounts` | `account_id` | `cards` | `account_id` | 1 : Many | Supported, clean |
| `accounts` | `account_id` | `transactions`| `account_id` | 1 : Many | Supported, 0 orphans in SQLite |
| `merchants` | `merchant_id` | `transactions`| `merchant_id` | 1 : Many | Supported, 0 orphans in SQLite |
| `branches` | `branch_id` | *None* | *None* | Isolated | No foreign key reference found in any table |

---

## 7. Major Data Quality & Structural Findings

1. **Missing `transactions.csv`**: Transactions only exist in `bank_sqlite.db` (1M rows) and SQL INSERT dumps.
2. **Null Values in SQLite `branches`**: 100% of rows in SQLite `branches` have `NULL` for `city` and `country`. However, `branches_inserts.sql` contains full values for all 500 branches.
3. **Dataset Divergence**: The CSV folder and the SQLite database were generated from different generator runs. To preserve relational integrity between transactions and accounts/merchants, `bank_sqlite.db` should serve as the golden source of truth.
4. **No Direct Branch Foreign Key**: No table contains `branch_id`. Accounts and customers only possess a `city` attribute.

---

## 8. Migration Recommendation for PostgreSQL
- Use `bank_sqlite.db` as the unified source database.
- Stream data directly from `bank_sqlite.db` into PostgreSQL tables using bulk insertion or direct `COPY` commands.
- For `branches`, ingest `city` and `country` from `branches_inserts.sql` to remediate the missing columns in SQLite.
