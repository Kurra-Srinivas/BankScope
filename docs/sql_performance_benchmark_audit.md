# BankScope — SQL Performance Benchmark Rigor Audit & Validation Report

**Audit Date**: September 6, 2026  
**Audited Component**: `scripts/benchmark_sql_performance.py` & `docs/sql_performance_benchmark.md`  
**Database**: PostgreSQL 18.0 (`bankscope_db`)  
**Ledger Volume**: 1,000,000 transaction rows (`transactions`)  
**Audit Protocol**:
* **20 timed executions per state** (40 executions per benchmark; 120 total runs)
* **Alternating execution order** (even iterations: Unindexed ➔ Indexed; odd iterations: Indexed ➔ Unindexed) to prevent sequential cache warming bias
* **Semantic & Result-Set Identity**: Strict result set row-by-row verification (`res_unindexed == res_indexed`)
* **Buffer & Plan Inspection**: Full extraction of `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`
* **Production Invariant**: **Zero production indexes or analytical queries were modified or dropped.**

---

## 1. Executive Summary & Audit Classifications

| Benchmark ID | Analytical Query Name | Target Index | Unindexed Median (ms) | Indexed Median (ms) | Median Gain (%) | Speedup Factor | Buffer Page Reduction | Audit Classification |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **BENCH_01** | Transaction Date-Range Aggregation (Q4 2025) | `idx_transactions_date` | 79.763 ms | **33.677 ms** | **57.78%** | **2.4x** | 12,452 ➔ 11,796 (-5.3%) | **ROBUST** |
| **BENCH_02** | Customer Account Activity Ledger Statement | `idx_transactions_account_date` | 70.053 ms | **0.060 ms** | **99.91%** | **1,167.5x** | 12,376 ➔ 18 (-99.85%) | **CAUTION** |
| **BENCH_03** | Merchant Monthly Time-Series Aggregation | `idx_transactions_merchant_date` | 71.424 ms | **0.595 ms** | **99.17%** | **120.0x** | 12,599 ➔ 258 (-97.95%) | **ROBUST** |

---

## 2. Detailed Benchmark Verification & Statistical Profiling

### BENCH_01: Transaction Date-Range Aggregation
* **Target Index**: `idx_transactions_date` on `transactions(transaction_date)`
* **SQL Query**:
  ```sql
  SELECT 
      DATE_TRUNC('month', transaction_date)::DATE AS transaction_month,
      COUNT(transaction_id) AS total_tx_count,
      ROUND(SUM(amount_usd), 2) AS total_volume_usd,
      ROUND(AVG(amount_usd), 2) AS avg_ticket_usd
  FROM transactions
  WHERE transaction_date >= '2025-10-01 00:00:00' 
    AND transaction_date < '2026-01-01 00:00:00'
  GROUP BY DATE_TRUNC('month', transaction_date)::DATE
  ORDER BY transaction_month;
  ```

#### Verification Checks
1. **Semantic Equivalence**: Verified. Both configurations execute identical SQL text with identical parameters.
2. **Result Set Identity**: **IDENTICAL**. Both unindexed and indexed executions returned exactly 3 rows with matching numeric aggregates.
3. **Plan Transformation**:
   * **Unindexed**: `Aggregate` ➔ `Gather Merge` ➔ `Sort` ➔ `Parallel Seq Scan` on `transactions` (Cost: 20,771.77 .. 26,267.24, 2 parallel workers).
   * **Indexed**: `Aggregate` ➔ `Sort` ➔ `Bitmap Heap Scan` on `transactions` using `Bitmap Index Scan` on `idx_transactions_date` (Cost: 1,061.79 .. 22,233.19).
   * The intended index `idx_transactions_date` was directly utilized in the plan.
4. **Buffer Block Access**:
   * Unindexed: 12,452 shared hit blocks (entire heap scan).
   * Indexed: 11,796 shared hit blocks (skips unreferenced blocks outside the Q4 2025 range).

#### 20-Run Statistical Profile (ms)
| Metric | Unindexed State | Indexed State | Variance / Shift |
| :--- | :---: | :---: | :--- |
| **Median** | **79.763 ms** | **33.677 ms** | **57.78% reduction (2.4x speedup)** |
| **Mean** | 103.472 ms | 34.879 ms | 66.29% reduction (3.0x speedup) |
| **Min** | 74.514 ms | 31.954 ms | Lowest observed latency |
| **Max** | 166.621 ms | 44.302 ms | Peak observed latency |
| **Std Dev** | **39.417 ms** | **3.514 ms** | **Indexed plan is 11.2x more predictable** |

#### Engineering Assessment: **ROBUST**
* The unindexed state shows significant variance (Std Dev 39.4 ms) caused by background worker thread coordination and parallel scan scheduling overhead.
* The indexed state converges tightly around ~33-35 ms (Std Dev 3.5 ms), demonstrating not only a ~2.4x latency improvement but dramatically stabilized execution performance under concurrent workloads.
* **Classification**: **ROBUST**. Real physical index scan on 35,840 matched tuples over a wide range filter.

---

### BENCH_02: Customer Account Activity & Ledger Statement
* **Target Index**: `idx_transactions_account_date` on `transactions(account_id, transaction_date DESC)`
* **SQL Query**:
  ```sql
  SELECT 
      transaction_id,
      account_id,
      merchant_id,
      amount_usd,
      transaction_date
  FROM transactions
  WHERE account_id = 'ACCB1WVS7GK7C9V'
    AND transaction_date >= '2024-01-01 00:00:00'
  ORDER BY transaction_date DESC;
  ```

#### Verification Checks
1. **Semantic Equivalence**: Verified. Both configurations execute identical query text.
2. **Result Set Identity**: **IDENTICAL**. Both unindexed and indexed executions returned exactly 15 rows with identical ordering.
3. **Plan Transformation**:
   * **Unindexed**: `Gather` ➔ `Sort` (quicksort in memory) ➔ `Parallel Seq Scan` on `transactions` (Cost: 19,414.73 .. 19,415.75).
   * **Indexed**: `Index Scan` using `idx_transactions_account_date` (Cost: 0.42 .. 27.68).
   * Sort operation completely eliminated because index tuples are already sorted in `(account_id, transaction_date DESC)` order.
4. **Buffer Block Access**:
   * Unindexed: 12,376 shared hit blocks (reads every heap page in the table).
   * Indexed: **18 shared hit blocks** (**99.85% reduction in page reads**).

#### 20-Run Statistical Profile (ms)
| Metric | Unindexed State | Indexed State | Variance / Shift |
| :--- | :---: | :---: | :--- |
| **Median** | **70.053 ms** | **0.060 ms** | **99.91% reduction (1,167.5x speedup)** |
| **Mean** | 101.388 ms | 0.061 ms | 99.94% reduction (1,662.1x speedup) |
| **Min** | 65.089 ms | 0.023 ms | Extreme cache-warm floor |
| **Max** | 149.925 ms | 0.140 ms | Cache/scheduling variance ceiling |
| **Std Dev** | **39.044 ms** | **0.030 ms** | **50.0% relative standard deviation** |

#### Deep-Dive on Micro-Timing (~0.031 – 0.060 ms) & Cache Dominance
* **Physical Reality**: The query engine reads only 18 blocks (144 KB), all of which reside in PostgreSQL's shared buffer pool. Zero physical disk I/O occurs.
* **Timing Limits & Cache Artifacts**:
  * An execution time of 60 microseconds (0.060 ms) approaches the measurement limits of the operating system clock and thread scheduler.
  * The relative standard deviation is ~50% (StdDev 0.030 ms on a 0.060 ms median), showing that context switches and memory bus latency account for a massive fraction of measured time.
  * In a production multi-tier application, client-to-database network round-trip time (RTT), TCP stack serialization, and application driver overhead (e.g., Psycopg, SQLAlchemy) typically add 1.0 to 5.0 ms. Therefore, the user-facing latency drops from ~75 ms to ~2 ms (a ~35x real-world speedup, not 1,000x+).
* **Classification**: **CAUTION**. The underlying index optimization and 99.85% buffer reduction are mathematically verified, but marketing this as a "1,100x – 2,100x speedup" or highlighting "0.03 ms" without stating buffer residency and network context is misleading to experienced engineers.

---

### BENCH_03: Merchant Monthly Time-Series Aggregation
* **Target Index**: `idx_transactions_merchant_date` on `transactions(merchant_id, transaction_date)` + `pk_merchants`
* **SQL Query**:
  ```sql
  SELECT 
      m.merchant_id,
      m.merchant_name,
      DATE_TRUNC('month', t.transaction_date)::DATE AS transaction_month,
      COUNT(t.transaction_id) AS monthly_tx_count,
      ROUND(SUM(t.amount_usd), 2) AS monthly_volume_usd,
      ROUND(AVG(t.amount_usd), 2) AS avg_ticket_usd
  FROM transactions t
  JOIN merchants m ON t.merchant_id = m.merchant_id
  WHERE t.merchant_id = 'MER6BHDTKK0NKCT'
  GROUP BY m.merchant_id, m.merchant_name, DATE_TRUNC('month', t.transaction_date)::DATE
  ORDER BY transaction_month;
  ```

#### Verification Checks
1. **Semantic Equivalence**: Verified. Identical query text across states.
2. **Result Set Identity**: **IDENTICAL**. Both states returned exactly 78 monthly aggregate rows.
3. **Plan Transformation**:
   * **Unindexed**: `Gather Merge` ➔ `Sort` ➔ `Aggregate` ➔ `Nested Loop` with `Seq Scan` on `transactions` (Cost: 20,404.97 .. 20,405.02).
   * **Indexed**: `Sort` ➔ `Aggregate` ➔ `Nested Loop` using `Index Scan` on `pk_merchants` and `Bitmap Heap Scan` on `transactions` via `idx_transactions_merchant_date` (Cost: 914.36 .. 915.93).
4. **Buffer Block Access**:
   * Unindexed: 12,599 shared hit blocks (1M row scan + merchant join).
   * Indexed: **258 shared hit blocks** (**97.95% reduction in block reads**).

#### 20-Run Statistical Profile (ms)
| Metric | Unindexed State | Indexed State | Variance / Shift |
| :--- | :---: | :---: | :--- |
| **Median** | **71.424 ms** | **0.595 ms** | **99.17% reduction (120.0x speedup)** |
| **Mean** | 89.521 ms | 0.626 ms | 99.30% reduction (143.0x speedup) |
| **Min** | 64.381 ms | 0.456 ms | Lowest observed latency |
| **Max** | 152.812 ms | 0.939 ms | Peak observed latency |
| **Std Dev** | **35.188 ms** | **0.106 ms** | **332x reduction in absolute variance** |

#### Engineering Assessment: **ROBUST**
* At ~0.60 ms, the execution time is comfortably above OS timer noise thresholds while remaining firmly in the sub-millisecond bracket.
* The query aggregates 200+ transactions into 78 monthly summary records, demonstrating real computational grouping while avoiding a full scan of 1M ledger records.
* **Classification**: **ROBUST**. Defensible, reproducible 120x execution gain driven by targeted composite index lookup and 98% buffer elimination.

---

## 3. Benchmark Classification Matrix

```
+--------------------------------------------------------------------------------------------------+
| BENCHMARK AUDIT CLASSIFICATION MATRIX                                                            |
+-----------+-----------------------------------------------+----------------+---------------------+
| ID        | Query Profile                                 | Classification | Justification       |
+-----------+-----------------------------------------------+----------------+---------------------+
| BENCH_01  | Date-Range Aggregation (Q4 2025)              | ROBUST         | Multi-page bitmap   |
|           |                                               |                | scan; tight stddev; |
|           |                                               |                | realistic 2.4x gain |
+-----------+-----------------------------------------------+----------------+---------------------+
| BENCH_02  | Customer Account Activity Statement           | CAUTION        | 99.85% buffer drop  |
|           |                                               |                | is genuine, but     |
|           |                                               |                | 0.06ms is timer- and|
|           |                                               |                | cache-dominated     |
+-----------+-----------------------------------------------+----------------+---------------------+
| BENCH_03  | Merchant Monthly Revenue Time Series          | ROBUST         | Stable sub-ms (0.6ms|
|           |                                               |                | clean 120x speedup; |
|           |                                               |                | 98% buffer drop     |
+-----------+-----------------------------------------------+----------------+---------------------+
```

---

## 4. Conservative Recommendations for CV / Resume Wording

Inflated or unqualified claims (such as "optimized queries by 2,100x" or "achieved 0.03ms query latency") are immediate red flags to principal database engineers and technical hiring managers. They indicate a lack of awareness regarding network latency, cache residency, and timer precision.

Below are conservative, defensible formulations that highlight senior-level database engineering competence:

### What NOT to Put on a CV
* ❌ *"Achieved 2,100x query speedup on 1,000,000 records using PostgreSQL indexes."*  
  *(Red Flag: Sounds fabricated or represents an artificial micro-benchmark where an unindexed full table scan is compared against an in-memory point lookup).*
* ❌ *"Optimized SQL queries to run in 0.03 milliseconds."*  
  *(Red Flag: Client network latency in production is 2-10 ms; quoting sub-0.1 ms in-engine execution reveals inexperience with production distributed systems).*
* ❌ *"Eliminated 99.9% of database execution time across the analytics suite."*  
  *(Red Flag: Unrealistic across mixed analytical workloads).*

### Recommended Conservative & High-Impact Formulations

#### Option A (Focus on Index Strategy & I/O Reduction — Recommended)
> **"Engineered B-tree composite index strategies on a 1M-row PostgreSQL transaction ledger, eliminating full-table sequential scans and reducing buffer cache page reads by up to 99.8% (12,376 to 18 blocks) on high-frequency account statements."**

#### Option B (Focus on Analytical Throughput & Plan Optimization)
> **"Profiled and optimized analytical PostgreSQL workloads using `EXPLAIN (ANALYZE, BUFFERS)`, replacing parallel seq-scans with targeted bitmap and composite index scans to achieve a 120x latency reduction (71ms to 0.6ms) on merchant time-series aggregations."**

#### Option C (Compact Resume Bullet Point)
> **"Designed production indexing architecture across 1M transactions in PostgreSQL, achieving a 58% latency reduction on multi-month range aggregations and sub-millisecond execution on targeted account and merchant queries."**

---

## 5. Audit Invariants & Safeguards
* **Zero Production Changes**: No production tables, indexes, views, or queries were modified or dropped during this audit.
* **Controlled Session-Level Testing**: Unindexed states were evaluated strictly using session-level planner switches (`SET LOCAL enable_indexscan = off; SET LOCAL enable_bitmapscan = off;`).
* **Empirical Integrity**: All statistics reflect exact 20-run empirical measurements without artificial smoothing or cherry-picked samples.
