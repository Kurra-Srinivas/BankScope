# BankScope — Analytical SQL Catalog & Business Intelligence Guide

**Document Version**: 1.0  
**Database**: PostgreSQL (`bankscope_db`)  
**Total Production Queries**: 30  
**Status**: All 30 Queries Tested & Verified against Live Database  

---

## 1. Catalog Summary by Analytics Domain

| Domain | Script Path | Query Count | Core Analytical Focus |
| :--- | :--- | :---: | :--- |
| **Customer Analytics** | [`sql/customer_analytics.sql`](../sql/customer_analytics.sql) | 4 | Demographics, credit risk tiers, wealth ranking, onboarding velocity, geographic benchmarks |
| **Account Analytics** | [`sql/account_analytics.sql`](../sql/account_analytics.sql) | 4 | Product mix, payment card attachment, deposit decile concentration, vintage balance retention |
| **Transaction Analytics** | [`sql/transaction_analytics.sql`](../sql/transaction_analytics.sql) | 4 | Monthly volume/spend trends, MoM growth rates, day/hour heatmap, 99th percentile outliers |
| **Loan Analytics** | [`sql/loan_analytics.sql`](../sql/loan_analytics.sql) | 4 | APR risk tiering, risk-based pricing audit, origination curves, debt-to-liquidity ratios |
| **Branch Analytics** | [`sql/branch_analytics.sql`](../sql/branch_analytics.sql) | 3 | Manager oversight workload, customer density vs branch gap analysis, regional clusters |
| **Merchant Analytics** | [`sql/merchant_analytics.sql`](../sql/merchant_analytics.sql) | 4 | Top merchant rankings, Pareto volume concentration (80/20 rule), commercial centers, stability |
| **RFM Segmentation** | [`sql/rfm_analysis.sql`](../sql/rfm_analysis.sql) | 4 | Raw RFM metrics, statistical quintile scoring (1-5), lifecycle matrix, cross-product wallet share |
| **Advanced SQL** | [`sql/advanced_analytics.sql`](../sql/advanced_analytics.sql) | 3 | Running spend ledger reconstruction, account dormancy/churn audit, cross-sell white space |
| **TOTAL** | **8 Scripts** | **30** | **End-to-End Enterprise Banking Analytics** |

---

## 2. Detailed Query Catalog

### Domain 1: Customer Analytics ([`sql/customer_analytics.sql`](../sql/customer_analytics.sql))

#### Query 01: Customer Demographics & Credit Risk Stratification
* **Business Question**: How are customers distributed across standard FICO credit score tiers (Poor, Fair, Good, Very Good, Exceptional), what is their average liquid deposit balance, and what proportion of the customer base belongs to each risk category?
* **Techniques Demonstrated**: `CASE` expressions, `LEFT JOIN`, `GROUP BY`, Aggregate functions (`COUNT`, `AVG`, `SUM`), Window function percentage share (`SUM(...) OVER ()`).
* **Output Metrics**: `credit_tier`, `customer_count`, `pct_of_customers`, `avg_credit_score`, `avg_total_balance_usd`, `aggregate_balance_usd`.

#### Query 02: Top 15 High-Net-Worth Multi-Product Customers
* **Business Question**: Who are the top 15 most financially engaged customers based on combined liquid balances across deposit accounts and active credit commitments in loans?
* **Techniques Demonstrated**: Multi-table `LEFT JOIN` (`customers`, `accounts`, `loans`), `COALESCE`, `SUM(DISTINCT ...)`, Window ranking `DENSE_RANK() OVER (ORDER BY ...)`, CTE.
* **Output Metrics**: `customer_id`, `customer_name`, `city`, `credit_score`, `total_accounts`, `total_deposit_balance_usd`, `total_loans`, `total_loan_commitment_usd`, `total_relationship_value_usd`, `wealth_rank`.

#### Query 03: Quarterly Customer Onboarding Velocity & Cumulative Growth
* **Business Question**: What has been the quarterly velocity of customer acquisition from 2019 to 2025, and what is the cumulative acquisition trajectory of the bank?
* **Techniques Demonstrated**: `DATE_TRUNC('quarter', ...)`, Window function `SUM(...) OVER (ORDER BY ...)`, `LAG()` for QoQ percentage growth calculation, CTE.
* **Output Metrics**: `onboarding_quarter`, `new_customers_acquired`, `cumulative_customers`, `qoq_growth_pct`.

#### Query 04: Top Geographic Markets & City-Level Liquidity Benchmarking
* **Business Question**: In the top 15 cities with highest customer concentration, how does each city's average liquid balance per customer compare against the overall national bank average?
* **Techniques Demonstrated**: `LEFT JOIN`, `GROUP BY`, `HAVING`, Cross Join benchmark with window calculation, Absolute and percentage variance derivations.
* **Output Metrics**: `city`, `city_customer_count`, `city_account_count`, `city_total_balance_usd`, `city_avg_balance_per_account`, `national_avg_account_balance`, `variance_from_national_avg`, `variance_pct`.

---

### Domain 2: Account Analytics ([`sql/account_analytics.sql`](../sql/account_analytics.sql))

#### Query 05: Account Portfolio Composition & Balance Market Share
* **Business Question**: What is the distribution of deposit accounts across product types (Checking, Savings, Business), their aggregate balance, and balance market share?
* **Techniques Demonstrated**: `GROUP BY`, Aggregate functions (`SUM`, `AVG`, `MIN`, `MAX`), Window function `SUM(SUM(...)) OVER ()` for relative market share.
* **Output Metrics**: `account_type`, `total_accounts`, `account_share_pct`, `total_balance_usd`, `balance_share_pct`, `avg_balance_usd`, `min_balance_usd`, `max_balance_usd`.

#### Query 06: Payment Card Attachment & Penetration by Account Type
* **Business Question**: What proportion of accounts across each product category have debit cards, credit cards, or multiple cards attached to them?
* **Techniques Demonstrated**: `LEFT JOIN`, Conditional Aggregation (`SUM(CASE WHEN ...)`), CTE, Penetration ratio derivations.
* **Output Metrics**: `account_type`, `total_accounts`, `accounts_without_card`, `uncarded_pct`, `accounts_with_debit`, `debit_penetration_pct`, `accounts_with_credit`, `credit_penetration_pct`, `avg_cards_per_account`.

#### Query 07: Balance Decile Stratification & Deposit Concentration
* **Business Question**: How concentrated are deposits across the 10 balance deciles, and what proportion of total liquid capital is controlled by the top 10% of accounts?
* **Techniques Demonstrated**: `NTILE(10)` window function, CTE, Cumulative Window `SUM(SUM(...)) OVER (ORDER BY decile)` for wealth Pareto distribution.
* **Output Metrics**: `balance_decile`, `accounts_in_decile`, `min_balance_usd`, `max_balance_usd`, `decile_total_balance_usd`, `decile_balance_share_pct`, `cumulative_balance_share_pct`.

#### Query 08: Account Vintage & Opening Cohort Liquidity Dynamics
* **Business Question**: How does account vintage (year of opening) relate to average balance retention and customer longevity?
* **Techniques Demonstrated**: `EXTRACT(YEAR FROM open_date)`, Two-stage CTE, Window function `LAG()` for Year-over-Year (YoY) balance trajectory.
* **Output Metrics**: `opening_year`, `accounts_opened`, `cohort_total_balance_usd`, `cohort_avg_balance_usd`, `yoy_avg_balance_growth_pct`.

---

### Domain 3: Transaction Analytics ([`sql/transaction_analytics.sql`](../sql/transaction_analytics.sql))

#### Query 09: Monthly Transaction Volume, Total Value, and Average Ticket Size
* **Business Question**: What is the monthly trajectory of payment transactions, gross dollar volume, and average transaction ticket size from 2019 through 2025?
* **Techniques Demonstrated**: `DATE_TRUNC('month', ...)`, Temporal grouping, Aggregate functions over 1,000,000 records.
* **Output Metrics**: `transaction_month`, `total_transactions`, `gross_transaction_value_usd`, `avg_ticket_size_usd`, `min_transaction_usd`, `max_transaction_usd`.

#### Query 10: Month-over-Month (MoM) Transaction Volume & Spend Growth Rates
* **Business Question**: What is the month-over-month growth rate of transactional spending, and which months experienced the sharpest acceleration or contraction in volume?
* **Techniques Demonstrated**: CTE, Window function `LAG()` for both transaction counts and dollar volume, MoM percentage formulas.
* **Output Metrics**: `month_start`, `monthly_tx_count`, `prev_month_tx_count`, `tx_count_mom_pct`, `monthly_volume_usd`, `prev_month_volume_usd`, `volume_mom_pct`.

#### Query 11: Day-of-Week and Hourly Velocity Patterns (Peak Traffic Profiling)
* **Business Question**: Which days of the week and hours of the day generate the highest transaction frequency and monetary volume?
* **Techniques Demonstrated**: `TO_CHAR(..., 'Day')`, `EXTRACT(DOW FROM ...)`, `EXTRACT(HOUR FROM ...)`, Multi-dimensional grouping, Total share window calculation.
* **Output Metrics**: `day_of_week`, `day_of_week_num`, `transaction_hour`, `transaction_count`, `total_volume_usd`, `avg_amount_usd`, `pct_of_all_transactions`.

#### Query 12: High-Value & Outlier Transaction Detection (99th Percentile Audit)
* **Business Question**: What are the transactions that exceed the 99th percentile dollar threshold, and which accounts and merchants represent the greatest concentration of these high-value transactions?
* **Techniques Demonstrated**: `PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY ...)`, Multi-table `JOIN`, CTE, Explicit numeric typecasting, Outlier filtering.
* **Output Metrics**: `account_type`, `p99_transaction_count`, `p99_aggregate_volume_usd`, `p99_avg_amount_usd`, `p99_min_amount_usd`, `p99_max_amount_usd`, `p99_cut_off_usd`.

---

### Domain 4: Loan Analytics ([`sql/loan_analytics.sql`](../sql/loan_analytics.sql))

#### Query 13: Loan Portfolio Exposure & APR Risk Tier Stratification
* **Business Question**: How is total loan exposure distributed across interest rate risk tiers (Low <5%, Prime 5-8%, Standard 8-12%, Subprime >12%), and what is the weighted average APR in each tier?
* **Techniques Demonstrated**: `CASE` tiering, Weighted average calculation `SUM(amount * rate) / SUM(amount)`, Window percentage share.
* **Output Metrics**: `interest_rate_tier`, `loan_count`, `loan_count_share_pct`, `total_principal_usd`, `principal_share_pct`, `avg_loan_size_usd`, `weighted_avg_interest_rate`, `min_interest_rate`, `max_interest_rate`.

#### Query 14: Credit Score vs Interest Rate Risk-Based Pricing Audit
* **Business Question**: Does the bank effectively implement risk-based pricing by assigning lower interest rates to higher credit-score borrowers across customer tiers?
* **Techniques Demonstrated**: `INNER JOIN`, Credit score categorization, Multi-tier statistical aggregation (`AVG`, `MIN`, `MAX`).
* **Output Metrics**: `borrower_credit_tier`, `total_loans_issued`, `avg_credit_score`, `avg_interest_rate`, `min_interest_rate`, `max_interest_rate`, `avg_loan_amount_usd`, `total_loan_exposure_usd`.

#### Query 15: Annual Loan Origination Velocity & Cumulative Capital Exposure
* **Business Question**: What is the year-over-year progression of newly originated loan capital, and what is the cumulative loan book exposure over the bank's operational history?
* **Techniques Demonstrated**: `EXTRACT(YEAR FROM ...)`, CTE, Window function `LAG()` for YoY growth, Window function `SUM(...) OVER (ORDER BY year)` for cumulative capital curve.
* **Output Metrics**: `origination_year`, `loans_originated`, `annual_volume_usd`, `yoy_volume_growth_pct`, `cumulative_loan_exposure_usd`, `avg_origination_rate`.

#### Query 16: Customer Debt-to-Liquidity Leverage Audit (High-Risk Borrowers)
* **Business Question**: Which borrowers have an extreme debt-to-liquidity ratio where their loan commitments exceed 5x their total liquid deposit balances, representing default vulnerability?
* **Techniques Demonstrated**: Multiple CTEs aggregating deposits and loans independently per customer, Ratio calculation, Threshold filtering (`debt_to_deposit >= 5.0`).
* **Output Metrics**: `customer_id`, `customer_name`, `city`, `credit_score`, `active_loan_count`, `total_debt_usd`, `total_deposits_usd`, `debt_to_deposit_ratio`, `avg_borrowing_rate`.

---

### Domain 5: Branch Analytics ([`sql/branch_analytics.sql`](../sql/branch_analytics.sql))

#### Query 17: Branch Manager Portfolio Breadth & Multi-Branch Oversight
* **Business Question**: What is the distribution of physical branch oversight among bank managers, and which managers are responsible for multi-branch portfolios?
* **Techniques Demonstrated**: `GROUP BY`, `COUNT`, `STRING_AGG`, `DENSE_RANK() OVER (ORDER BY COUNT(*) DESC)`.
* **Output Metrics**: `manager_name`, `branches_managed`, `branch_names_list`, `manager_workload_rank`.

#### Query 18: Branch Geographic Gap Analysis (High-Density Customer Cities vs Branch Presence)
* **Business Question**: Which top customer population centers have zero direct local branch infrastructure, highlighting prime expansion opportunities for digital-only vs brick-and-mortar strategies?
* **Techniques Demonstrated**: CTEs, `LEFT JOIN` between customer city density and branch presence, `COALESCE`, `CASE`, `DENSE_RANK()`.
* **Output Metrics**: `city`, `customer_count`, `local_branch_count`, `service_model`, `customer_density_rank`.

#### Query 19: Branch Network Nomenclature & Regional Cluster Distribution
* **Business Question**: How are physical branches categorized across directional identifiers (North, South, East, West, Lake, Port), and what is the distribution across regional designations?
* **Techniques Demonstrated**: `CASE` pattern matching with `LIKE`, `COUNT(*)`, Window function share `SUM(...) OVER ()`, `COUNT(DISTINCT)`.
* **Output Metrics**: `regional_cluster`, `total_branches`, `branch_share_pct`, `distinct_managers`.

---

### Domain 6: Merchant Analytics ([`sql/merchant_analytics.sql`](../sql/merchant_analytics.sql))

#### Query 20: Top 20 Merchants by Processed Transaction Volume & Value
* **Business Question**: Which top 20 merchant partners process the greatest dollar volume and transaction volume across our payment network?
* **Techniques Demonstrated**: `INNER JOIN`, Aggregate functions, Window ranking `DENSE_RANK() OVER (ORDER BY volume DESC)`.
* **Output Metrics**: `merchant_id`, `merchant_name`, `merchant_city`, `total_transactions`, `total_processed_volume_usd`, `avg_ticket_size_usd`, `min_ticket_usd`, `max_ticket_usd`, `revenue_rank`.

#### Query 21: Merchant Concentration & Pareto Principle (Cumulative Volume Share)
* **Business Question**: What percentage of aggregate bank transaction volume is concentrated among the top 5%, 10%, and 20% of merchants?
* **Techniques Demonstrated**: CTEs, `NTILE(20)` window function, Cumulative Window function `SUM(SUM(...)) OVER (ORDER BY ventile)` for 80/20 Pareto audit.
* **Output Metrics**: `top_5_pct_bracket`, `merchants_in_bracket`, `bracket_volume_usd`, `bracket_share_pct`, `cumulative_volume_share_pct`.

#### Query 22: Commercial Centers & City-Level Merchant Ticket Benchmarking
* **Business Question**: In which cities do merchants process the highest average transaction values, and which cities represent the largest commercial merchant clusters?
* **Techniques Demonstrated**: `INNER JOIN`, `GROUP BY`, Aggregate functions, `HAVING COUNT(DISTINCT merchant_id) >= 5`.
* **Output Metrics**: `commercial_city`, `active_merchant_count`, `total_city_transactions`, `total_city_volume_usd`, `avg_city_ticket_size_usd`, `avg_volume_per_merchant_usd`.

#### Query 23: Merchant Annual Activity Consistency & Stability Profiling
* **Business Question**: Which merchants have transacted consistently across all 7 operational years (2019 through 2025), demonstrating resilient ongoing business relationships?
* **Techniques Demonstrated**: `EXTRACT(YEAR FROM ...)`, `COUNT(DISTINCT year)`, `HAVING COUNT(...) = 7`, `INNER JOIN`.
* **Output Metrics**: `merchant_id`, `merchant_name`, `city`, `active_years_count`, `lifetime_transactions`, `lifetime_volume_usd`, `lifetime_avg_ticket_usd`.

---

### Domain 7: RFM Customer Segmentation ([`sql/rfm_analysis.sql`](../sql/rfm_analysis.sql))

#### Query 24: Customer Raw RFM Metrics Derivation
* **Business Question**: What are the individual Recency (days since last payment relative to 2025-12-31), Frequency (lifetime transaction count), and Monetary (lifetime spend) metrics for each customer?
* **Techniques Demonstrated**: Multi-table `INNER JOIN` (`customers ➔ accounts ➔ transactions`), Fixed anchor date difference (`DATE '2025-12-31' - MAX(date)`), CTE.
* **Output Metrics**: `customer_id`, `customer_name`, `city`, `credit_score`, `recency_days`, `frequency`, `monetary_usd`.

#### Query 25: Statistical RFM Quintile Scoring (1 to 5 Scores)
* **Business Question**: How are customers ranked into statistical quintiles (1-5) for Recency (5 = most recent), Frequency (5 = highest volume), and Monetary (5 = highest spend)?
* **Techniques Demonstrated**: Three-way `NTILE(5)` window functions, Reverse ranking for Recency, String concatenation for combined RFM code.
* **Output Metrics**: `customer_id`, `recency_days`, `frequency`, `monetary_usd`, `r_score`, `f_score`, `m_score`, `rfm_combined_code`.

#### Query 26: Customer RFM Segmentation Matrix & Segment Distribution
* **Business Question**: When classifying customers into standard strategic segments (Champions, Loyal Customers, Recent Promising, At-Risk, Need Attention, Hibernating), how many customers belong to each tier and what is each tier's revenue contribution?
* **Techniques Demonstrated**: Multi-level CTEs, Multi-condition `CASE` rules, Percentage of wallet share window function.
* **Output Metrics**: `rfm_segment`, `segment_customer_count`, `segment_customer_pct`, `segment_total_volume_usd`, `segment_volume_share_pct`, `avg_recency_days`, `avg_frequency`, `avg_monetary_spend_usd`.

#### Query 27: Cross-Product Financial Profile by RFM Segment
* **Business Question**: What are the liquid deposit holdings and borrowing exposures across each customer RFM tier, identifying high-spending customers with untapped loan potential?
* **Techniques Demonstrated**: Multi-CTE integration joining RFM segment classifications with independent `accounts` and `loans` aggregations.
* **Output Metrics**: `rfm_segment`, `total_customers`, `segment_total_deposits_usd`, `segment_avg_deposit_usd`, `customers_with_loans`, `segment_total_loans_usd`, `segment_avg_loan_usd`.

---

### Domain 8: Advanced SQL & Complex Engineering ([`sql/advanced_analytics.sql`](../sql/advanced_analytics.sql))

#### Query 28: Account Chronological Ledger Statement & Running Spend Reconstruction
* **Business Question**: How can we reconstruct an account's chronological transaction ledger with running cumulative spend and moving averages for forensic auditing?
* **Techniques Demonstrated**: Window function `ROW_NUMBER()`, Window function `SUM(...) OVER (PARTITION BY account_id ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`, Window function moving average `AVG(...) OVER (... ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)`.
* **Output Metrics**: `account_id`, `tx_sequence_num`, `transaction_id`, `transaction_date`, `merchant_name`, `merchant_city`, `amount_usd`, `running_cumulative_spend_usd`, `rolling_3tx_moving_avg_usd`.

#### Query 29: Account Inactivity & Dormancy Risk Audit (Positive Balance Without Transactions)
* **Business Question**: Which deposit accounts have held positive balances (>$1,000) but recorded zero transactions in the final 180 days of the dataset (post 2025-07-04), signaling churn?
* **Techniques Demonstrated**: `LEFT JOIN`, `DATE` subtraction with `INTERVAL '180 days'`, `HAVING` clause temporal filtering, Churn exposure ranking.
* **Output Metrics**: `account_id`, `customer_id`, `customer_name`, `email`, `customer_city`, `account_type`, `dormant_balance_usd`, `open_date`, `last_active_transaction_date`, `days_inactive`.

#### Query 30: Cross-Selling White-Space Opportunity Identification
* **Business Question**: Which high-credit-score customers (credit score >= 720) hold only a single checking account without any secondary deposit account, loan, or credit card, representing prime cross-sell targets?
* **Techniques Demonstrated**: Multi-table `LEFT JOIN` (`customers`, `accounts`, `cards`, `loans`), Conditional Aggregation (`SUM(CASE WHEN ...)`), CTE, Multi-condition white-space filtering.
* **Output Metrics**: `customer_id`, `customer_name`, `city`, `credit_score`, `total_deposit_balance_usd`, `total_accounts`, `total_cards`, `total_loans`, `recommended_campaign`.
