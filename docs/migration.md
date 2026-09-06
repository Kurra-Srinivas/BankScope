# BankScope — PostgreSQL Database Creation & Migration Guide

**Document Version**: 1.0  
**Status**: Ready for Execution  
**Canonical Source**: `data/raw/banking_dataset_kaggle/data/database/bank_sqlite.db`  
**Target Engine**: PostgreSQL (Local Server on `localhost:5432`)  

---

## 1. Migration Architecture & Strategy

Migrating 1,260,500 total records—including 1,000,000 transactions—requires high-throughput bulk ingestion rather than individual row-by-row `INSERT` statements.

### Optimized Pipeline Strategy
1. **Database Provisioning**:
   - The migration engine connects to the administrative `postgres` database and automatically creates the target database (`bankscope_db`) if it does not already exist.
2. **Schema Ingestion First (`sql/schema.sql`)**:
   - Tables and Primary Keys are created first.
   - Foreign keys and indexes are deferred during initial ingestion to avoid per-row constraint evaluation and index page updates.
3. **High-Throughput Bulk Streaming (`COPY FROM STDIN`)**:
   - Data is extracted from `bank_sqlite.db` using cursor chunking (50,000 rows per batch) and streamed into PostgreSQL using binary/text `COPY FROM STDIN`.
   - Streaming takes ~3–5 seconds for the entire 1,000,000 transaction table.
4. **Post-Load Constraint Application (`sql/constraints.sql`)**:
   - Foreign key relationships and empirical domain `CHECK` constraints are verified and applied in a single transactional batch.
5. **Post-Load Index Build (`sql/indexes.sql`)**:
   - B-tree and composite time-series indexes are built concurrently or sequentially directly on the populated tables.
6. **Automated Validation (`scripts/validate_postgres.py`)**:
   - Compares exact table row counts between SQLite and PostgreSQL.
   - Validates 100% Primary Key uniqueness.
   - Audits referential integrity (zero orphan records).
   - Confirms statistical bounds on transaction dates and monetary amounts.

---

## 2. Table Loading Sequence & Volume

Tables are loaded in parent-to-child order to maintain data integrity:

| Sequence | Table Name | Source Row Count | Relational Role |
| :---: | :--- | :---: | :--- |
| **1** | `customers` | 50,000 | Parent (Customer Master) |
| **2** | `merchants` | 5,000 | Parent (Merchant Master) |
| **3** | `branches` | 500 | Independent Reference Table |
| **4** | `accounts` | 75,000 | Child of `customers` |
| **5** | `cards` | 100,000 | Child of `accounts` |
| **6** | `loans` | 30,000 | Child of `customers` |
| **7** | `transactions`| 1,000,000 | Child of `accounts` & `merchants` |
| **TOTAL** | **7 Tables** | **1,260,500** | |

---

## 3. Configuration & Execution Guide

### Step 1: Configure `.env`
Ensure your local PostgreSQL credentials are configured in `.env` (derived from [`.env.example`](../.env.example)):

```ini
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bankscope_db
DB_USER=postgres
DB_PASSWORD=your_actual_password_here
```

### Step 2: Run Automated Migration
Execute the migration engine using the project virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/migrate_sqlite_to_postgres.py
```

### Step 3: Run Validation Suite
Verify data parity and constraint compliance:

```powershell
.\.venv\Scripts\python.exe scripts/validate_postgres.py
```

---

## 4. Script Reference
* [`scripts/migrate_sqlite_to_postgres.py`](../scripts/migrate_sqlite_to_postgres.py): Complete automated bulk migration engine.
* [`scripts/validate_postgres.py`](../scripts/validate_postgres.py): Integrity and statistical validation test suite.
* [`sql/schema.sql`](../sql/schema.sql): PostgreSQL table DDL.
* [`sql/constraints.sql`](../sql/constraints.sql): Referential FK and domain CHECK constraints.
* [`sql/indexes.sql`](../sql/indexes.sql): Analytical and join optimization indexes.
