# BankScope — Interactive Banking Analytics Dashboard

An enterprise-grade, portfolio-quality Streamlit dashboard built on top of the PostgreSQL `bankscope_db` database, providing interactive business intelligence, customer RFM segmentation, and SQL query performance benchmarks.

---

## 1. Dashboard Architecture & Sections

The dashboard is structured into five distinct operational views:

### 1. Executive Overview
* **High-Level KPIs**: Real-time aggregation of total customers (50,000), accounts (75,000), payment cards (100,000), loans (30,000), merchants (5,000), and transactions (1,000,000).
* **Capital Totals**: Total deposit balances ($7.49B), transaction volume ($5.00B), and loan commitments ($4.51B).
* **Payment Volume Trajectory**: Interactive Plotly area chart visualizing monthly gross volume across the 7-year timeline.

### 2. Customer Analytics
* **Geographic Concentration**: Horizontal bar chart of top 15 customer cities and liquid balances.
* **Product Composition**: Interactive donut chart analyzing Checking, Savings, and Business account shares.
* **RFM Segmentation Matrix**: Full breakdown of 38,849 transacting customers across 7 strategic tiers (Champions, Loyal, Recent Promising, At-Risk, Need Attention, Hibernating, Average) with share of wallet.
* **Top Relationship Customers**: Multi-product ranking of top 15 customers by combined deposit and loan exposure.

### 3. Transaction Analytics
* **Dynamic Time Interval Filtering**: Interactive sidebar date range picker querying the 1,000,000-row ledger using parameterized SQL.
* **Dual-Axis Volume & Flow**: Combined bar and spline chart tracking transaction counts alongside gross dollar volume.
* **Merchant Revenue Leaders**: Top 15 commercial merchants by processed payment volume.
* **High-Value Outlier Audit**: Top transaction outlier records exceeding the 99th percentile threshold ($9,900+).

### 4. Loans & Lending Portfolio
* **Interest Rate Risk Tiers**: Capital distribution across Low (<5%), Prime (5–8%), Standard (8–12%), and High/Subprime (≥12%) APR bands.
* **Annual Origination Velocity**: Multi-year trend of new loan issuances.
* **Risk-Based Pricing Audit**: Empirical evaluation of borrowing APR across customer credit score tiers.

### 5. SQL Performance Benchmarking
* **Audited EXPLAIN (ANALYZE, BUFFERS) Metrics**: Rigorous 20-run median benchmarks comparing sequential full-table scans against targeted B-tree indexing:
  1. *Date-Range Slicing*: **57.78% latency reduction** (79.8 ms ➔ 33.7 ms, **2.4x speedup**, **ROBUST** via `idx_transactions_date`).
  2. *Account Ledger Statement*: **99.85% buffer-page reduction** (12,376 ➔ 18 blocks, **CAUTION**; sub-0.1ms execution is buffer-cache resident and client-perceived performance is dominated by 1–5 ms network RTT).
  3. *Merchant Time-Series*: **99.17% latency reduction** (71.4 ms ➔ 0.595 ms, **120.0x speedup**, **ROBUST** via composite `idx_transactions_merchant_date`).
* **Physical Scan Shift**: Transparent logging of heap sequential scans versus composite index traversals.

---

## 2. Prerequisites & Setup

1. **Virtual Environment**:
   Ensure dependencies from `requirements.txt` are installed:
   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. **Environment Configuration**:
   Ensure `.env` in the project root contains valid PostgreSQL credentials:
   ```ini
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=bankscope_db
   DB_USER=postgres
   DB_PASSWORD=your_password
   ```

---

## 3. Running the Dashboard

To launch the dashboard locally:

```powershell
.\.venv\Scripts\streamlit.exe run dashboard/app.py
```

The application will open automatically in your browser at `http://localhost:8501`.
