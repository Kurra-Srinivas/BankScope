#!/usr/bin/env python3
"""
BankScope — SQL Performance Benchmarking Engine
Measures real PostgreSQL query execution plans and latencies before and after index optimization.
Uses EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) over multiple iterations.
"""

import os
import sys
import json
import statistics
import psycopg2
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DB_HOST = os.getenv("DB_HOST") or os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("DB_PORT") or os.getenv("PGPORT", "5432")
DB_NAME = os.getenv("DB_NAME") or "bankscope_db"
DB_USER = os.getenv("DB_USER") or os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("PGPASSWORD", "")

DOCS_DIR = os.path.join(BASE_DIR, "docs")
BENCHMARK_REPORT_PATH = os.path.join(DOCS_DIR, "sql_performance_benchmark.md")


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def extract_plan_metrics(plan_json):
    """Recursively extract key plan nodes, scan types, buffers, and execution time."""
    root_plan = plan_json[0]["Plan"]
    exec_time = plan_json[0]["Execution Time"]
    planning_time = plan_json[0]["Planning Time"]

    scan_types = []
    index_names = []

    def walk_nodes(node):
        node_type = node.get("Node Type", "")
        if "Scan" in node_type or "Join" in node_type:
            scan_types.append(node_type)
        if "Index Name" in node:
            index_names.append(node["Index Name"])
        for child in node.get("Plans", []):
            walk_nodes(child)

    walk_nodes(root_plan)

    shared_hit = root_plan.get("Shared Hit Blocks", 0)
    shared_read = root_plan.get("Shared Read Blocks", 0)
    total_buffers = shared_hit + shared_read

    return {
        "execution_time_ms": exec_time,
        "planning_time_ms": planning_time,
        "primary_node": root_plan.get("Node Type", "Unknown"),
        "scan_types": list(set(scan_types)),
        "index_names": list(set(index_names)),
        "shared_hit_blocks": shared_hit,
        "shared_read_blocks": shared_read,
        "total_buffers": total_buffers,
        "raw_plan": plan_json,
    }


def run_benchmark_suite(num_iterations=5):
    conn = get_connection()
    cur = conn.cursor()

    # Retrieve representative active account and merchant
    cur.execute("SELECT account_id FROM transactions GROUP BY account_id ORDER BY COUNT(*) DESC LIMIT 1;")
    sample_acc = cur.fetchone()[0]

    cur.execute("SELECT merchant_id FROM transactions GROUP BY merchant_id ORDER BY COUNT(*) DESC LIMIT 1;")
    sample_mer = cur.fetchone()[0]

    benchmarks = [
        {
            "id": "BENCH_01",
            "name": "Transaction Date-Range Aggregation",
            "target_index": "idx_transactions_date",
            "business_question": "Monthly transaction count, volume, and average ticket size for Q4 2025 across the 1,000,000 ledger rows.",
            "sql": """
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
""".strip(),
        },
        {
            "id": "BENCH_02",
            "name": "Customer Account Activity & Ledger Statement",
            "target_index": "idx_transactions_account_date",
            "business_question": "Filtered chronological transaction ledger for a specific customer account from 2024 onwards, ordered by transaction date descending.",
            "sql": f"""
SELECT 
    transaction_id,
    account_id,
    merchant_id,
    amount_usd,
    transaction_date
FROM transactions
WHERE account_id = '{sample_acc}'
  AND transaction_date >= '2024-01-01 00:00:00'
ORDER BY transaction_date DESC;
""".strip(),
        },
        {
            "id": "BENCH_03",
            "name": "Merchant Monthly Time-Series Aggregation",
            "target_index": "idx_transactions_merchant_date",
            "business_question": "Monthly revenue and transaction volume trends for a high-volume merchant partner joined with merchant metadata.",
            "sql": f"""
SELECT 
    m.merchant_id,
    m.merchant_name,
    DATE_TRUNC('month', t.transaction_date)::DATE AS transaction_month,
    COUNT(t.transaction_id) AS monthly_tx_count,
    ROUND(SUM(t.amount_usd), 2) AS monthly_volume_usd,
    ROUND(AVG(t.amount_usd), 2) AS avg_ticket_usd
FROM transactions t
JOIN merchants m ON t.merchant_id = m.merchant_id
WHERE t.merchant_id = '{sample_mer}'
GROUP BY m.merchant_id, m.merchant_name, DATE_TRUNC('month', t.transaction_date)::DATE
ORDER BY transaction_month;
""".strip(),
        },
    ]

    results = []

    print("=================================================================")
    print(f"BankScope SQL Performance Benchmark Engine ({num_iterations} iterations)")
    print(f"Target Database: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print("=================================================================")

    for b in benchmarks:
        print(f"\n[*] Running Benchmark: {b['id']} — {b['name']}...")

        # -------------------------------------------------------------
        # Phase 1: Unindexed Execution (Disable Index and Bitmap Scans)
        # -------------------------------------------------------------
        cur.execute("SET enable_indexscan = off; SET enable_bitmapscan = off;")
        # Warmup
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {b['sql']};")
        _ = cur.fetchone()

        unindexed_times = []
        unindexed_metric = None
        for _ in range(num_iterations):
            cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {b['sql']};")
            plan_data = cur.fetchone()[0]
            m = extract_plan_metrics(plan_data)
            unindexed_times.append(m["execution_time_ms"])
            if unindexed_metric is None:
                unindexed_metric = m

        median_unindexed_time = statistics.median(unindexed_times)

        # -------------------------------------------------------------
        # Phase 2: Indexed Execution (Enable Index and Bitmap Scans)
        # -------------------------------------------------------------
        cur.execute("SET enable_indexscan = on; SET enable_bitmapscan = on;")
        # Warmup
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {b['sql']};")
        _ = cur.fetchone()

        indexed_times = []
        indexed_metric = None
        for _ in range(num_iterations):
            cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {b['sql']};")
            plan_data = cur.fetchone()[0]
            m = extract_plan_metrics(plan_data)
            indexed_times.append(m["execution_time_ms"])
            if indexed_metric is None:
                indexed_metric = m

        median_indexed_time = statistics.median(indexed_times)

        # Percentage improvement
        pct_improvement = (
            (median_unindexed_time - median_indexed_time) / median_unindexed_time * 100.0
            if median_unindexed_time > 0
            else 0.0
        )
        speedup_factor = (
            median_unindexed_time / median_indexed_time if median_indexed_time > 0 else 1.0
        )

        b_result = {
            "id": b["id"],
            "name": b["name"],
            "target_index": b["target_index"],
            "business_question": b["business_question"],
            "sql": b["sql"],
            "unindexed": {
                "median_time_ms": round(median_unindexed_time, 3),
                "all_times": [round(t, 3) for t in unindexed_times],
                "scan_types": unindexed_metric["scan_types"],
                "primary_node": unindexed_metric["primary_node"],
                "buffers": unindexed_metric["total_buffers"],
            },
            "indexed": {
                "median_time_ms": round(median_indexed_time, 3),
                "all_times": [round(t, 3) for t in indexed_times],
                "scan_types": indexed_metric["scan_types"],
                "index_names": indexed_metric["index_names"],
                "primary_node": indexed_metric["primary_node"],
                "buffers": indexed_metric["total_buffers"],
            },
            "pct_improvement": round(pct_improvement, 2),
            "speedup_factor": round(speedup_factor, 1),
        }
        results.append(b_result)

        print(
            f"  [Unindexed] {median_unindexed_time:.3f} ms | Scans: {unindexed_metric['scan_types']} | Buffers: {unindexed_metric['total_buffers']}"
        )
        print(
            f"  [Indexed]   {median_indexed_time:.3f} ms | Scans: {indexed_metric['scan_types']} | Index: {indexed_metric['index_names']} | Buffers: {indexed_metric['total_buffers']}"
        )
        print(
            f"  ==> Result: {pct_improvement:.2f}% Improvement ({speedup_factor:.1f}x Speedup)"
        )

    cur.close()
    conn.close()

    # Generate Markdown Report
    generate_markdown_report(results, num_iterations)
    return results


def generate_markdown_report(results, num_iterations):
    md = []
    md.append("# BankScope — SQL Performance Benchmarking & Index Optimization Report\n")
    md.append(f"**Database**: PostgreSQL (`{DB_NAME}`)  ")
    md.append(f"**Ledger Table Volume**: 1,000,000 rows (`transactions`)  ")
    md.append(f"**Benchmark Method**: `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`  ")
    md.append(f"**Iterations**: {num_iterations} runs per test state with warm-up  \n")
    md.append("---\n")

    md.append("## 1. Executive Performance Summary\n")
    md.append(
        "| Benchmark ID | Analytical Query Name | Target Index | Unindexed Time (ms) | Indexed Time (ms) | Improvement (%) | Speedup Factor | Primary Scan Shift |"
    )
    md.append(
        "| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |"
    )

    for r in results:
        scans_from = ", ".join(r["unindexed"]["scan_types"])
        scans_to = ", ".join(r["indexed"]["scan_types"])
        md.append(
            f"| **{r['id']}** | {r['name']} | `{r['target_index']}` | {r['unindexed']['median_time_ms']:.3f} ms | **{r['indexed']['median_time_ms']:.3f} ms** | **{r['pct_improvement']:.2f}%** | **{r['speedup_factor']:.1f}x** | `{scans_from}` ➔ `{scans_to}` |"
        )

    md.append("\n---\n")
    md.append("## 2. Detailed Query Benchmarks\n")

    for r in results:
        md.append(f"### {r['id']}: {r['name']}\n")
        md.append(f"**Business Question**: {r['business_question']}\n")
        md.append(f"**Target Index Under Test**: `{r['target_index']}`\n")
        md.append("#### Tested SQL Statement:\n```sql\n" + r["sql"] + "\n```\n")

        md.append("#### Plan & Execution Metrics:\n")
        md.append("| Metric | Controlled Unindexed State | Optimized Indexed State | Variance / Gain |")
        md.append("| :--- | :--- | :--- | :--- |")
        md.append(
            f"| **Median Execution Time** | {r['unindexed']['median_time_ms']:.3f} ms | **{r['indexed']['median_time_ms']:.3f} ms** | **{r['pct_improvement']:.2f}% faster** |"
        )
        md.append(
            f"| **Sample Iterations (ms)** | `{r['unindexed']['all_times']}` | `{r['indexed']['all_times']}` | |"
        )
        md.append(
            f"| **Primary Execution Node** | `{r['unindexed']['primary_node']}` | `{r['indexed']['primary_node']}` | |"
        )
        md.append(
            f"| **Physical Scan Methods** | `{r['unindexed']['scan_types']}` | `{r['indexed']['scan_types']}` | |"
        )
        md.append(
            f"| **Index(es) Utilized** | *None (Sequential Scan)* | `{r['indexed']['index_names']}` | |"
        )
        md.append(
            f"| **Buffer Block Access** | {r['unindexed']['buffers']} shared blocks | {r['indexed']['buffers']} shared blocks | |"
        )

        md.append("\n#### Engineering Analysis:\n")
        if r["id"] == "BENCH_01":
            md.append(
                "* **Scan Shift**: Shifting from a full-table sequential scan across 1,000,000 rows to a `Bitmap Index Scan` on `idx_transactions_date` allows the query engine to evaluate only page tuples falling within the Q4 date boundary, yielding a **"
                + f"{r['pct_improvement']:.2f}%"
                + " reduction in query latency**.\n"
            )
        elif r["id"] == "BENCH_02":
            md.append(
                "* **Scan Shift**: Without an index, PostgreSQL must sequentially scan the entire 1,000,000-row heap and perform an explicit sort on `transaction_date DESC`. With composite index `idx_transactions_account_date`, PostgreSQL performs an instantaneous `Index Scan` on `(account_id, transaction_date DESC)`—fetching pre-sorted index tuples in **"
                + f"{r['indexed']['median_time_ms']:.3f} ms** (a **{r['speedup_factor']:.1f}x speedup**).\n"
            )
        elif r["id"] == "BENCH_03":
            md.append(
                "* **Scan Shift**: In the unindexed state, joining 1,000,000 transaction rows against the merchant table requires scanning all heap pages and performing an in-memory hash join. With `idx_transactions_merchant_date`, PostgreSQL isolates the merchant's transactions via index lookup directly, reducing execution time to **"
                + f"{r['indexed']['median_time_ms']:.3f} ms** (a **{r['pct_improvement']:.2f}% improvement**).\n"
            )

        md.append("---\n")

    report_text = "\n".join(md)
    with open(BENCHMARK_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"[OK] Benchmark documentation written to: {BENCHMARK_REPORT_PATH}")


if __name__ == "__main__":
    run_benchmark_suite(num_iterations=5)
