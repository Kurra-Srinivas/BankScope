# BankScope — SQL Performance Benchmarking & Index Optimization Report

**Database**: PostgreSQL 18.0 (`bankscope_db`)  
**Ledger Table Volume**: 1,000,000 rows (`transactions`)  
**Benchmark Method**: `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`  
**Iterations**: Audited across 20 alternating runs per test state with warm-up  

---

## 1. Executive Performance Summary

| Benchmark ID | Analytical Query Name | Target Index | Unindexed Time (ms) | Indexed Time (ms) | Improvement (%) | Speedup Factor | Primary Scan Shift | Classification |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| **BENCH_01** | Transaction Date-Range Aggregation (Q4 2025) | `idx_transactions_date` | 79.763 ms | **33.677 ms** | **57.78%** | **2.4x** | `Parallel Seq Scan` ➔ `Bitmap Heap/Index Scan` | **ROBUST** |
| **BENCH_02** | Customer Account Activity Ledger Statement | `idx_transactions_account_date` | 70.053 ms | **0.060 ms** | **99.91%** | **1,167.5x\*** | `Parallel Seq Scan + Sort` ➔ `Index Scan` | **CAUTION\*** |
| **BENCH_03** | Merchant Monthly Time-Series Aggregation | `idx_transactions_merchant_date` | 71.424 ms | **0.595 ms** | **99.17%** | **120.0x** | `Seq Scan + Nested Loop` ➔ `Bitmap Scan + Index Scan` | **ROBUST** |

> [!CAUTION]
> **\*BENCH_02 Micro-Timing Classification**:
> The 0.060 ms in-engine execution time reflects pure buffer-cache residency (reading 18 pre-cached 8KB blocks) with zero physical disk I/O. In real-world multi-tier architectures, client-perceived latency is dominated by network round-trip time (RTT, typically 1.0–5.0 ms). Therefore, while the **99.85% physical buffer reduction (12,376 down to 18 blocks)** is mathematically verified, claiming an unqualified "1,100x–2,100x speedup" in client applications is technically misleading. See [`docs/sql_performance_benchmark_audit.md`](sql_performance_benchmark_audit.md) for full statistical profiling.

---

## 2. Detailed Query Benchmarks

### BENCH_01: Transaction Date-Range Aggregation

**Business Question**: Monthly transaction count, volume, and average ticket size for Q4 2025 across the 1,000,000 ledger rows.

**Target Index Under Test**: `idx_transactions_date` on `transactions(transaction_date)`

#### Tested SQL Statement:
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

#### Plan & Execution Metrics:

| Metric | Controlled Unindexed State | Optimized Indexed State | Variance / Gain |
| :--- | :--- | :--- | :--- |
| **Median Execution Time** | 79.763 ms | **33.677 ms** | **57.78% faster (2.4x)** |
| **Mean Execution Time** | 103.472 ms | **34.879 ms** | **66.29% faster (3.0x)** |
| **Standard Deviation** | 39.417 ms | **3.514 ms** | **11.2x tighter stability** |
| **Primary Execution Node** | `Aggregate` | `Aggregate` | |
| **Physical Scan Methods** | `['Parallel Seq Scan']` | `['Bitmap Heap Scan', 'Bitmap Index Scan']` | |
| **Index(es) Utilized** | *None (Sequential Scan)* | `['idx_transactions_date']` | |
| **Buffer Block Access** | 12,452 shared blocks | 11,796 shared blocks | -5.3% block reads |
| **Classification** | — | — | **ROBUST** |

#### Engineering Analysis:
* **Scan Shift**: Shifting from a parallel sequential scan across all 1,000,000 rows to a `Bitmap Index Scan` on `idx_transactions_date` allows the query engine to evaluate only page tuples falling within the Q4 date boundary, yielding a **57.78% reduction in median query latency** and an **11.2x reduction in execution variance**.

---

### BENCH_02: Customer Account Activity & Ledger Statement

**Business Question**: Filtered chronological transaction ledger for a specific customer account from 2024 onwards, ordered by transaction date descending.

**Target Index Under Test**: `idx_transactions_account_date` on `transactions(account_id, transaction_date DESC)`

#### Tested SQL Statement:
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

#### Plan & Execution Metrics:

| Metric | Controlled Unindexed State | Optimized Indexed State | Variance / Gain |
| :--- | :--- | :--- | :--- |
| **Median Execution Time** | 70.053 ms | **0.060 ms** | **99.91% faster** |
| **Mean Execution Time** | 101.388 ms | **0.061 ms** | **99.94% faster** |
| **Standard Deviation** | 39.044 ms | **0.030 ms** | High relative timing variance |
| **Primary Execution Node** | `Gather` ➔ `Sort` | `Index Scan` | Quicksort eliminated |
| **Physical Scan Methods** | `['Parallel Seq Scan']` | `['Index Scan']` | Direct B-Tree traversal |
| **Index(es) Utilized** | *None (Sequential Scan)* | `['idx_transactions_account_date']` | Pre-sorted tuples |
| **Buffer Block Access** | 12,376 shared blocks | **18 shared blocks** | **-99.85% physical block reads** |
| **Classification** | — | — | **CAUTION (Cache & RTT Dominance)** |

#### Engineering Analysis:
* **Scan Shift**: Without an index, PostgreSQL sequentially scans the entire 1,000,000-row heap (12,376 blocks) and performs an in-memory quicksort on `transaction_date DESC`.
* With composite index `idx_transactions_account_date`, PostgreSQL performs an instantaneous `Index Scan` on `(account_id, transaction_date DESC)`—fetching pre-sorted index tuples across only **18 blocks (99.85% I/O reduction)**.
* **Audit Caution**: Execution at 0.060 ms operates inside memory buffer hit limits. In production client workflows, network round-trip time (1–5 ms) dominates client-perceived performance.

---

### BENCH_03: Merchant Monthly Time-Series Aggregation

**Business Question**: Monthly revenue and transaction volume trends for a high-volume merchant partner joined with merchant metadata.

**Target Index Under Test**: `idx_transactions_merchant_date` on `transactions(merchant_id, transaction_date)` + `pk_merchants`

#### Tested SQL Statement:
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

#### Plan & Execution Metrics:

| Metric | Controlled Unindexed State | Optimized Indexed State | Variance / Gain |
| :--- | :--- | :--- | :--- |
| **Median Execution Time** | 71.424 ms | **0.595 ms** | **99.17% faster (120.0x)** |
| **Mean Execution Time** | 89.521 ms | **0.626 ms** | **99.30% faster (143.0x)** |
| **Standard Deviation** | 35.188 ms | **0.106 ms** | **332x reduction in variance** |
| **Primary Execution Node** | `Gather Merge` ➔ `Sort` | `Sort` ➔ `Aggregate` | |
| **Physical Scan Methods** | `['Seq Scan']` | `['Index Scan', 'Bitmap Heap Scan']`| |
| **Index(es) Utilized** | *None (Sequential Scan)* | `['idx_transactions_merchant_date', 'pk_merchants']` | |
| **Buffer Block Access** | 12,599 shared blocks | **258 shared blocks** | **-97.95% block reads** |
| **Classification** | — | — | **ROBUST** |

#### Engineering Analysis:
* **Scan Shift**: Shifting from a full 1M sequential scan to a composite B-tree lookup on `(merchant_id, transaction_date)` combined with an index scan on `merchants.merchant_id` slashes buffer reads from 12,599 to 258 blocks (**97.95% I/O reduction**), achieving a reproducible **120.0x speedup** (71.4 ms ➔ 0.595 ms).
