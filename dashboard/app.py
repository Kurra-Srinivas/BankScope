import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

from dashboard.queries import (
    get_executive_kpis,
    get_monthly_trend_overview,
    get_city_distribution,
    get_account_composition,
    get_top_customers,
    get_rfm_distribution,
    get_filtered_transactions_monthly,
    get_top_merchants,
    get_high_value_transactions,
    get_loan_apr_tiers,
    get_credit_score_vs_apr,
    get_annual_loan_trend,
    get_benchmark_summary,
)
from dashboard.db import test_db_connection

# Page Configuration
st.set_page_config(
    page_title="BankScope — Banking Data Analytics & SQL Optimization",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling (CSS) - High Contrast & Dark Theme Accessible
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #60A5FA;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #CBD5E1;
        margin-bottom: 1.5rem;
    }
    .kpi-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.25);
    }
    .kpi-title {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        color: #94A3B8;
        margin-bottom: 6px;
    }
    .kpi-val {
        font-size: 1.6rem;
        font-weight: 700;
        color: #F8FAFC;
    }
    .kpi-sub {
        font-size: 0.78rem;
        color: #34D399;
        margin-top: 4px;
    }
    .section-header {
        font-size: 1.4rem;
        font-weight: 600;
        color: #93C5FD;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        border-bottom: 2px solid #334155;
        padding-bottom: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# Verify Database Reachability
if not test_db_connection():
    st.error("🚨 Could not connect to PostgreSQL `bankscope_db`. Please verify that PostgreSQL is running and `.env` credentials are correct.")
    st.stop()

# Sidebar Navigation & Filter Controls
st.sidebar.image("https://img.icons8.com/isometric/100/bank-building.png", width=64)
st.sidebar.markdown("## **BankScope**")
st.sidebar.markdown("*Enterprise Banking BI & SQL Optimization*")
st.sidebar.markdown("---")

section_options = [
    "1. Executive Overview",
    "2. Customer Analytics",
    "3. Transaction Analytics",
    "4. Loans & Lending",
    "5. SQL Performance",
]

query_sec = st.query_params.get("section", "")
default_idx = 0
if query_sec:
    for i, opt in enumerate(section_options):
        if query_sec.lower() in opt.lower():
            default_idx = i
            break

section = st.sidebar.radio(
    "Navigate to Section:",
    section_options,
    index=default_idx,
)


st.sidebar.markdown("---")
st.sidebar.caption("Canonical Source: PostgreSQL `bankscope_db`")
st.sidebar.caption("Data: Kaggle Banking Dataset (1.26M Rows)")


# =============================================================================
# SECTION 1: EXECUTIVE OVERVIEW
# =============================================================================
if section == "1. Executive Overview":
    st.markdown('<div class="main-title">Executive Banking Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">High-level portfolio snapshot of retail customers, deposit accounts, lending commitments, and payment volume.</div>', unsafe_allow_html=True)

    kpis = get_executive_kpis()

    # Top Row KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">Total Customers</div>
                <div class="kpi-val">{int(kpis.get('total_customers', 0)):,}</div>
                <div class="kpi-sub">50,000 customer records</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">Total Deposit Holdings</div>
                <div class="kpi-val">${kpis.get('total_deposits_usd', 0) / 1e9:.2f}B</div>
                <div class="kpi-sub">{int(kpis.get('total_accounts', 0)):,} total accounts</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">Total Transaction Volume</div>
                <div class="kpi-val">${kpis.get('total_transaction_volume_usd', 0) / 1e9:.2f}B</div>
                <div class="kpi-sub">{int(kpis.get('total_transactions', 0)):,} transactions</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">Total Loan Exposure</div>
                <div class="kpi-val">${kpis.get('total_loan_exposure_usd', 0) / 1e9:.2f}B</div>
                <div class="kpi-sub">{int(kpis.get('total_loans', 0)):,} loan accounts</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Secondary Row KPI Cards
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        st.metric("Total Accounts", f"{int(kpis.get('total_accounts', 0)):,}")
    with sc2:
        st.metric("Payment Cards", f"{int(kpis.get('total_cards', 0)):,}")
    with sc3:
        st.metric("Merchant Network", f"{int(kpis.get('total_merchants', 0)):,}")
    with sc4:
        st.metric("Total Loans", f"{int(kpis.get('total_loans', 0)):,}")

    st.markdown('<div class="section-header">Monthly Transaction Trend (2019 – 2025)</div>', unsafe_allow_html=True)
    df_trend = get_monthly_trend_overview()

    fig_trend = go.Figure()
    fig_trend.add_trace(
        go.Scatter(
            x=df_trend["transaction_month"],
            y=df_trend["total_volume_usd"],
            name="Gross Volume ($)",
            line=dict(color="#2563EB", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(37, 99, 235, 0.1)",
        )
    )
    fig_trend.update_layout(
        title="Gross Payment Transaction Volume Trajectory",
        xaxis_title="Month",
        yaxis_title="Volume (USD)",
        template="plotly_white",
        height=380,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig_trend, use_container_width=True)


# =============================================================================
# SECTION 2: CUSTOMER ANALYTICS
# =============================================================================
elif section == "2. Customer Analytics":
    st.markdown('<div class="main-title">Customer Portfolio & Demographics</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Segmentation, credit risk tiering, deposit composition, and RFM value contribution.</div>', unsafe_allow_html=True)

    # Customer & City Distribution + Account Composition
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Top 15 Customer Cities")
        df_cities = get_city_distribution(limit=15)
        fig_cities = px.bar(
            df_cities,
            x="customer_count",
            y="city",
            orientation="h",
            color="customer_count",
            color_continuous_scale="Blues",
            labels={"customer_count": "Customers", "city": "City"},
            height=400,
        )
        fig_cities.update_layout(yaxis=dict(autorange="reversed"), template="plotly_white", margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_cities, use_container_width=True)

    with col_right:
        st.markdown("#### Deposit Account Product Mix")
        df_acc = get_account_composition()
        fig_acc = px.pie(
            df_acc,
            names="account_type",
            values="total_balance_usd",
            hole=0.45,
            color="account_type",
            color_discrete_map={"Checking": "#3B82F6", "Savings": "#10B981", "Business": "#F59E0B"},
            height=400,
        )
        fig_acc.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_acc, use_container_width=True)

    # RFM Segmentation Analysis
    st.markdown('<div class="section-header">RFM Customer Segmentation Matrix (38,849 Transacting Customers)</div>', unsafe_allow_html=True)
    df_rfm = get_rfm_distribution()

    rfm_col1, rfm_col2 = st.columns([3, 2])
    with rfm_col1:
        fig_rfm_spend = px.bar(
            df_rfm,
            x="rfm_segment",
            y="total_spend_usd",
            color="rfm_segment",
            text="spend_share_pct",
            labels={"total_spend_usd": "Total Spend (USD)", "rfm_segment": "RFM Segment"},
            title="Spend Contribution by Segment (% of Total Spend)",
            height=380,
        )
        fig_rfm_spend.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_rfm_spend.update_layout(showlegend=False, template="plotly_white")
        st.plotly_chart(fig_rfm_spend, use_container_width=True)

    with rfm_col2:
        fig_rfm_cust = px.pie(
            df_rfm,
            names="rfm_segment",
            values="customer_count",
            title="Customer Base Share by Segment",
            height=380,
            hole=0.4,
        )
        fig_rfm_cust.update_layout(template="plotly_white")
        st.plotly_chart(fig_rfm_cust, use_container_width=True)

    st.markdown("#### RFM Segment Performance Metrics")
    st.dataframe(
        df_rfm.style.format(
            {
                "customer_count": "{:,}",
                "customer_pct": "{:.2f}%",
                "total_spend_usd": "${:,.2f}",
                "spend_share_pct": "{:.2f}%",
                "avg_recency_days": "{:.1f} d",
                "avg_frequency": "{:.1f}",
                "avg_monetary_usd": "${:,.2f}",
            }
        ),
        use_container_width=True,
    )

    # Top Customers Table
    st.markdown('<div class="section-header">Top 15 Customers by Total Relationship Value (Deposits + Loans)</div>', unsafe_allow_html=True)
    df_top_cust = get_top_customers(limit=15)
    st.dataframe(
        df_top_cust.style.format(
            {
                "credit_score": "{:d}",
                "total_accounts": "{:d}",
                "total_deposits_usd": "${:,.2f}",
                "total_loans": "{:d}",
                "total_loans_usd": "${:,.2f}",
                "total_relationship_value_usd": "${:,.2f}",
            }
        ),
        use_container_width=True,
    )


# =============================================================================
# SECTION 3: TRANSACTION ANALYTICS
# =============================================================================
elif section == "3. Transaction Analytics":
    st.markdown('<div class="main-title">Payment Transaction Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">1,000,000-row ledger analytics, merchant processing performance, and high-value transactions.</div>', unsafe_allow_html=True)

    # Date Filter in Sidebar
    st.sidebar.markdown("### Transaction Filters")
    min_date = date(2019, 1, 1)
    max_date = date(2025, 12, 31)
    selected_dates = st.sidebar.date_input(
        "Select Date Interval:",
        value=(date(2023, 1, 1), max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        start_d, end_d = selected_dates
    elif isinstance(selected_dates, tuple) and len(selected_dates) == 1:
        start_d, end_d = selected_dates[0], max_date
    else:
        start_d, end_d = min_date, max_date

    df_filtered_tx = get_filtered_transactions_monthly(start_d, end_d)

    # Volume and Spend Dual Chart
    fig_dual = go.Figure()
    fig_dual.add_trace(
        go.Bar(
            x=df_filtered_tx["month"],
            y=df_filtered_tx["tx_count"],
            name="Transaction Count",
            marker_color="#93C5FD",
            yaxis="y2",
        )
    )
    fig_dual.add_trace(
        go.Scatter(
            x=df_filtered_tx["month"],
            y=df_filtered_tx["total_volume_usd"],
            name="Volume ($)",
            line=dict(color="#1E40AF", width=2.5),
            yaxis="y1",
        )
    )
    fig_dual.update_layout(
        title=f"Transaction Volume & Gross Dollar Flow ({start_d} to {end_d})",
        yaxis=dict(title="Volume (USD)"),
        yaxis2=dict(title="Transaction Count", overlaying="y", side="right"),
        template="plotly_white",
        height=400,
        legend=dict(x=0.01, y=0.99),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig_dual, use_container_width=True)

    col_mer, col_high = st.columns(2)

    with col_mer:
        st.markdown("#### Top 15 Merchants by Gross Transaction Volume")
        df_merchants = get_top_merchants(limit=15)
        fig_mer = px.bar(
            df_merchants,
            x="total_volume_usd",
            y="merchant_name",
            orientation="h",
            color="total_volume_usd",
            color_continuous_scale="Viridis",
            labels={"total_volume_usd": "Gross Volume (USD)", "merchant_name": "Merchant"},
            height=420,
        )
        fig_mer.update_layout(yaxis=dict(autorange="reversed"), template="plotly_white", margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_mer, use_container_width=True)

    with col_high:
        st.markdown("#### High-Value Transaction Outliers (Top 10)")
        df_high = get_high_value_transactions(limit=10)
        st.dataframe(
            df_high.style.format(
                {
                    "amount_usd": "${:,.2f}",
                }
            ),
            use_container_width=True,
            height=420,
        )


# =============================================================================
# SECTION 4: LOANS & LENDING
# =============================================================================
elif section == "4. Loans & Lending":
    st.markdown('<div class="main-title">Lending Portfolio & Credit Risk Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">$4.51 Billion loan portfolio, interest rate distribution, and credit score pricing breakdown.</div>', unsafe_allow_html=True)

    col_l1, col_l2 = st.columns(2)

    with col_l1:
        st.markdown("#### Loan Capital by APR Interest Tier")
        df_tiers = get_loan_apr_tiers()
        fig_tiers = px.bar(
            df_tiers,
            x="interest_rate_tier",
            y="total_loan_volume_usd",
            color="interest_rate_tier",
            text="volume_share_pct",
            labels={"total_loan_volume_usd": "Principal ($)", "interest_rate_tier": "APR Tier"},
            height=380,
        )
        fig_tiers.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_tiers.update_layout(showlegend=False, template="plotly_white")
        st.plotly_chart(fig_tiers, use_container_width=True)

    with col_l2:
        st.markdown("#### Annual Loan Origination Volume")
        df_annual = get_annual_loan_trend()
        fig_annual = px.line(
            df_annual,
            x="origination_year",
            y="annual_volume_usd",
            markers=True,
            line_shape="spline",
            labels={"annual_volume_usd": "Originated Volume ($)", "origination_year": "Year"},
            height=380,
        )
        fig_annual.update_traces(line_color="#10B981", line_width=3)
        fig_annual.update_layout(template="plotly_white")
        st.plotly_chart(fig_annual, use_container_width=True)

    st.markdown('<div class="section-header">Credit Score vs Interest Rate Distribution</div>', unsafe_allow_html=True)
    df_pricing = get_credit_score_vs_apr()

    st.dataframe(
        df_pricing.style.format(
            {
                "total_loans": "{:,}",
                "avg_credit_score": "{:.1f}",
                "avg_interest_rate": "{:.2f}%",
                "min_interest_rate": "{:.2f}%",
                "max_interest_rate": "{:.2f}%",
                "total_principal_usd": "${:,.2f}",
            }
        ),
        use_container_width=True,
    )


# =============================================================================
# SECTION 5: SQL PERFORMANCE BENCHMARKS
# =============================================================================
elif section == "5. SQL Performance":
    st.markdown('<div class="main-title">SQL Performance & Index Benchmarks</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Controlled EXPLAIN ANALYZE benchmarks measuring latency reduction and physical scan shifts across 1,000,000 ledger records.</div>', unsafe_allow_html=True)

    benchmarks = get_benchmark_summary()

    st.info("ℹ️ **Performance Audit Note on BENCH_02**: BENCH_02 achieved a **99.85% reduction in buffer page reads** (12,376 down to 18 blocks). Its sub-millisecond execution (0.060 ms) is classified as **CAUTION** because execution is entirely shared buffer-cache resident, and client-to-database network round-trip time (1–5 ms) dominates in distributed production environments.")

    # Cards for the 3 benchmarks
    bcol1, bcol2, bcol3 = st.columns(3)

    with bcol1:
        st.markdown(
            """
            <div class="kpi-card">
                <div class="kpi-title">BENCH_01: Date Range Slicing</div>
                <div class="kpi-val" style="color:#60A5FA;">57.78%</div>
                <div class="kpi-sub" style="color:#CBD5E1;">79.8 ms ➔ 33.7 ms (2.4x speedup)</div>
                <div style="font-size:0.75rem; color:#34D399; font-weight:600; margin-top:6px;">Status: ROBUST | Target: idx_transactions_date</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with bcol2:
        st.markdown(
            """
            <div class="kpi-card">
                <div class="kpi-title">BENCH_02: Account Ledger Statement</div>
                <div class="kpi-val" style="color:#34D399;">99.85% Buffer Cut</div>
                <div class="kpi-sub" style="color:#CBD5E1;">70.1 ms ➔ 0.060 ms (12,376 ➔ 18 blocks)</div>
                <div style="font-size:0.75rem; color:#FBBF24; font-weight:600; margin-top:6px;">Status: CAUTION (Buffer cache hit; network RTT dominates)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with bcol3:
        st.markdown(
            """
            <div class="kpi-card">
                <div class="kpi-title">BENCH_03: Merchant Time-Series</div>
                <div class="kpi-val" style="color:#FBBF24;">99.17%</div>
                <div class="kpi-sub" style="color:#CBD5E1;">71.4 ms ➔ 0.595 ms (120.0x speedup)</div>
                <div style="font-size:0.75rem; color:#34D399; font-weight:600; margin-top:6px;">Status: ROBUST | Target: idx_transactions_merchant_date</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Benchmark Comparison Chart
    df_bench_chart = pd.DataFrame(
        [
            {"Workload": "BENCH_01 (Date Range)", "State": "Unindexed (Seq Scan)", "Time (ms)": 79.763},
            {"Workload": "BENCH_01 (Date Range)", "State": "Optimized (Bitmap Index)", "Time (ms)": 33.677},
            {"Workload": "BENCH_02 (Account Ledger)", "State": "Unindexed (Seq Scan)", "Time (ms)": 70.053},
            {"Workload": "BENCH_02 (Account Ledger)", "State": "Optimized (Index Scan)", "Time (ms)": 0.060},
            {"Workload": "BENCH_03 (Merchant Series)", "State": "Unindexed (Seq Scan)", "Time (ms)": 71.424},
            {"Workload": "BENCH_03 (Merchant Series)", "State": "Optimized (Index Scan)", "Time (ms)": 0.595},
        ]
    )

    fig_bench = px.bar(
        df_bench_chart,
        x="Workload",
        y="Time (ms)",
        color="State",
        barmode="group",
        title="Audited 20-Run Median Latency Before vs After Index Optimization",
        color_discrete_map={"Unindexed (Seq Scan)": "#EF4444", "Optimized (Bitmap Index)": "#10B981", "Optimized (Index Scan)": "#10B981"},
        height=380,
    )
    fig_bench.update_layout(template="plotly_white")
    st.plotly_chart(fig_bench, use_container_width=True)

    # Benchmark Detail Table
    st.markdown('<div class="section-header">Empirical Benchmark Audit Log (20 Alternating Runs)</div>', unsafe_allow_html=True)
    df_bench_table = pd.DataFrame(benchmarks)
    st.dataframe(
        df_bench_table[
            [
                "id",
                "name",
                "target_index",
                "unindexed_ms",
                "indexed_ms",
                "pct_improvement",
                "speedup_factor",
                "classification",
                "plan_shift",
            ]
        ].style.format(
            {
                "unindexed_ms": "{:.3f} ms",
                "indexed_ms": "{:.3f} ms",
                "pct_improvement": "{:.2f}%",
                "speedup_factor": "{:.1f}x",
            }
        ),
        use_container_width=True,
    )

