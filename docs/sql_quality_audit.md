# BankScope — Analytical SQL Quality Audit & Validation Report

**Document Version**: 1.0  
**Database**: PostgreSQL (`bankscope_db`)  
**Scope**: Comprehensive Quality, Referential, and Semantic Audit across all 30 Analytical Queries  
**Date**: 2026-09-06  
**Audit Outcome**: **All 30 Queries Passed Strict Enterprise Auditing**  

---

## 1. Executive Summary

A forensic quality audit was conducted across all 30 production analytical queries in BankScope. The audit reviewed query logic, join cardinalities, aggregation correctness, NULL propagation, window framing, and banking business interpretations.

### Audit Highlights
* **Zero Cartesian Fan-Out**: Multi-child entity joins (e.g. joining both `accounts` and `loans` to `customers`) were refactored into independent CTE aggregations, eliminating accidental row multiplication.
* **Precise Type Handling**: Ensured mathematical functions such as `ROUND()` have explicit `::NUMERIC` casts on floating-point/double-precision statistical aggregates (`PERCENTILE_CONT`).
* **RFM Mathematical Soundness**: Verified that all 38,849 transacting customers are segmented across 7 strategic tiers with zero overlap and realistic monetary, frequency, and recency distributions.
* **Truth in Schema**: Branch queries explicitly reflect the source dataset reality: `branches` is an unlinked reference entity where `city` and `country` are NULL in the canonical SQLite/PostgreSQL database.

---

## 2. Issues Found and Remediated

| Query ID | File | Initial Finding / Risk | Remediation Applied | Impact & Benefit |
| :---: | :--- | :--- | :--- | :--- |
| **Q02** | `sql/customer_analytics.sql` | `customers` joined directly to both `accounts` and `loans` simultaneously. If a customer holds multiple accounts and multiple loans, a Cartesian product occurs. `SUM(DISTINCT balance_usd)` was susceptible to dropping duplicate balances. | Refactored into two independent CTEs (`customer_accounts` and `customer_loans`) that pre-aggregate metrics per `customer_id` before joining to `customers`. | Guaranteed zero fan-out; accurate arithmetic summation; query latency reduced by **51%** (from 0.503s to 0.246s). |
| **Q08** | `sql/account_analytics.sql` | `LAG(AVG(balance_usd), 1) OVER (ORDER BY EXTRACT(YEAR FROM open_date))` failed PostgreSQL's strict aggregation grouping parser without repeating expressions. | Introduced clean `yearly_vintage` CTE aggregating annual metrics first, then applied `LAG()` cleanly in the outer query. | Eliminates grouping syntax errors across diverse PostgreSQL minor versions. |
| **Q12** | `sql/transaction_analytics.sql` | `PERCENTILE_CONT(0.99)` returns `DOUBLE PRECISION`. Calling `ROUND(..., 2)` caused `psycopg2.errors.UndefinedFunction` because PostgreSQL requires `NUMERIC` for two-argument rounding. | Applied explicit typecast: `ROUND(MAX(p99_threshold_usd)::NUMERIC, 2)`. | Prevents runtime type-mismatch crashes. |
| **Q18** | `sql/branch_analytics.sql` | Query joined `branches` on `city` to assess coverage. In the canonical dataset (`bank_sqlite.db`), `branches.city` is 100% NULL. | Added documentation and `COALESCE` logic highlighting that `branches` currently functions as a remote/unlinked network, preventing misleading business claims. | Transparent reporting aligned strictly with actual empirical data. |
| **Q30** | `sql/advanced_analytics.sql` | Simultaneous joins from `customers` across `accounts`, `cards`, and `loans` posed fan-out risk for customers holding multiple cards across multiple accounts. | Refactored into three modular CTEs (`customer_accounts`, `customer_cards`, `customer_loans`) with pre-aggregated counts. | Completely isolates child cardinalities and ensures accurate white-space qualification. |

---

## 3. Important Sanity-Check Totals

These totals serve as the verified baseline for the entire BankScope portfolio:

```
========================================================================================
                               BANKSCOPE PORTFOLIO TOTALS
========================================================================================
Entity / Metric                          Count / Value                   Integrity Check
----------------------------------------------------------------------------------------
Total Customers                                50,000                   100% Unique PKs
Total Deposit Accounts                         75,000                   0 Orphaned Cust
Total Payment Cards                           100,000                   0 Orphaned Acc
Total Issued Loans                             30,000                   0 Orphaned Cust
Total Commercial Merchants                      5,000                   100% Unique PKs
Total Physical Branches                           500                   Isolated Entity
Total Ledger Transactions                   1,000,000                   0 Orphaned FKs
----------------------------------------------------------------------------------------
Total Deposit Holdings             $7,494,138,742.77                    ~$7.49 Billion
Average Account Balance                   $99,921.85                    Min $13.67 / Max $199.9k
Total Loan Exposure                $4,513,099,925.48                    ~$4.51 Billion
Average Loan Interest Rate                     8.54%                    Min 2.0% / Max 15.0%
Total Transacted Volume            $5,001,164,534.00                    ~$5.00 Billion
Average Transaction Ticket                 $5,001.16                    Min $1.02 / Max $9,999.98
Transaction Date Span          2019-01-01 to 2025-12-31                 7 Calendar Years
========================================================================================
```

---

## 4. Final RFM Customer Segmentation Distribution

Using reference anchor date **2025-12-31** (maximum transaction date in the 1,000,000-row ledger), all **38,849 transacting customers** were classified into 7 strategic tiers:

| Segment ID | RFM Segment Name | Customer Count | Customer Share (%) | Total Spend Volume ($) | Volume Share (%) | Avg Recency (Days) | Avg Frequency (Txns) | Avg Customer Spend ($) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | **Champions** | 8,365 | **21.53%** | $1,825,765,726.78 | **36.51%** | 22.8 d | 43.4 | $218,262.49 |
| **2** | **Loyal Customers** | 8,137 | **20.95%** | $1,235,425,625.28 | **24.70%** | 57.1 d | 30.4 | $151,828.15 |
| **3** | **Recent Promising** | 3,651 | **9.40%** | $240,523,662.00 | **4.81%** | 26.1 d | 13.2 | $65,878.84 |
| **4** | **At Risk** | 5,791 | **14.91%** | $875,450,958.46 | **17.50%** | 190.9 d | 29.9 | $151,174.40 |
| **5** | **Need Attention** | 549 | **1.41%** | $53,536,652.24 | **1.07%** | 247.3 d | 16.4 | $97,516.67 |
| **6** | **Hibernating / Lost** | 8,759 | **22.55%** | $516,886,779.00 | **10.34%** | 310.3 d | 12.0 | $59,012.08 |
| **7** | **Average / Steady** | 3,597 | **9.26%** | $253,575,130.24 | **5.07%** | 92.3 d | 15.0 | $70,496.28 |
| **TOTAL**| **All Transacting** | **38,849** | **100.00%** | **$5,001,164,534.00** | **100.00%** | **128.8 d** | **25.7** | **$128,733.42** |

### Strategic Business Insights
1. **Pareto Dominance**: Champions and Loyal Customers constitute **42.48%** of the transacting customer base but command **61.21%** ($3.06 Billion) of all transaction flow.
2. **At-Risk Capital Exposure**: The "At Risk" cohort represents **$875.45 Million** in historical volume. Customers in this group were historically high spenders (avg 29.9 transactions) but have not transacted in over 6 months (avg recency 190.9 days), representing the bank's highest-priority retention target.
3. **Non-Transacting Deposit Base**: Out of 50,000 total customers, 38,849 have accounts with transactions. The remaining 11,151 customers hold accounts or loans without recorded ledger activity, representing dormant accounts.

---

## 5. Analytical Limitations & Guardrails

To maintain portfolio credibility and avoid overstating analytical conclusions:

1. **Unlinked Branch Hierarchy**:
   - The raw Kaggle banking dataset does not include a `branch_id` foreign key in `accounts`, `loans`, or `customers`.
   - In `bank_sqlite.db`, `branches.city` and `branches.country` are entirely NULL.
   - *Guardrail*: Branch queries analyze manager workloads and network nomenclature, but do not claim branch-level financial P&L.
2. **Synthetic Uniformity in Amounts**:
   - Synthetic transaction amounts are uniformly distributed between $1.00 and $10,000.00 (avg $5,001.16).
   - *Guardrail*: Queries focus on volume velocity, customer frequency, and time-series patterns rather than heavy-tail power-law fraud modeling.
3. **Non-Unique Customer Emails**:
   - Forensic analysis revealed 45,718 distinct email addresses across 50,000 customer records.
   - *Guardrail*: All joins and aggregations strictly use `customer_id` as the primary key. Email is treated purely as a contact attribute.
