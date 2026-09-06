import os
import sys
import re

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
from dashboard.upload_engine import (
    validate_csv_file,
    ingest_csv,
    get_all_uploaded_tables,
    get_uploaded_table_data,
    profile_dataframe,
    delete_uploaded_table,
    table_exists_in_db,
)
from dashboard.sql_generator import (
    generate_sql_query,
    get_dataset_schema_context,
    validate_sql_security,
    validate_with_postgres_explain,
    execute_approved_sql,
)
from dashboard.sql_visualizer import generate_result_visualization
from dashboard.llm_provider import (
    get_llm_provider, 
    OfflineBankingSQLProvider,
    GroqProvider,
)
from dashboard.db import test_db_connection

# Page Configuration
st.set_page_config(
    page_title="BankScope — Banking Data Analytics & SQL Optimization",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session-scoped upload tracking
if "session_id" not in st.session_state:
    import uuid
    st.session_state["session_id"] = uuid.uuid4().hex[:8]

if "session_uploaded_tables" not in st.session_state:
    st.session_state["session_uploaded_tables"] = []

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
    st.error("🚨 Could not establish connection to the PostgreSQL database. Please verify that the database server is running and credentials are correctly configured in `.env` (for local development) or Streamlit Secrets (for cloud deployment).")
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
    "6. Upload & Explore Data",
    "7. Ask Your Data",
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


# =============================================================================
# SECTION 6: UPLOAD & EXPLORE DATA
# =============================================================================
elif section == "6. Upload & Explore Data":
    st.markdown('<div class="main-title">Upload & Explore Data</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Securely ingest external CSV datasets into an isolated PostgreSQL schema (<code>uploads</code>) with automated data quality profiling.</div>', unsafe_allow_html=True)

    tab_upload, tab_explore = st.tabs(["📤 Ingest New CSV", "🗂️ Explore Ingested Tables"])

    with tab_upload:
        st.markdown('<div class="section-header">Upload CSV Dataset</div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "Choose a CSV file to profile and load into PostgreSQL",
            type=["csv"],
            help="Maximum file size: 50 MB. Tables are loaded into an isolated 'uploads' schema."
        )

        if uploaded_file is not None:
            is_valid, err_msg = validate_csv_file(uploaded_file)
            if not is_valid:
                st.error(f"❌ {err_msg}")
            else:
                file_key = f"uploaded_{uploaded_file.name}_{uploaded_file.size}"
                if file_key in st.session_state:
                    cached_tbl = st.session_state[file_key].get("table_name", "")
                    if not table_exists_in_db(cached_tbl):
                        del st.session_state[file_key]
                        if cached_tbl in st.session_state.get("session_uploaded_tables", []):
                            st.session_state["session_uploaded_tables"].remove(cached_tbl)

                if file_key not in st.session_state:
                    with st.spinner("Analyzing CSV structure and ingesting into PostgreSQL..."):
                        try:
                            result = ingest_csv(uploaded_file, uploaded_file.name, session_id=st.session_state["session_id"])
                            st.session_state[file_key] = result
                            if result and result.get("status") == "SUCCESS":
                                tbl_name = result["table_name"]
                                if tbl_name not in st.session_state["session_uploaded_tables"]:
                                    st.session_state["session_uploaded_tables"].append(tbl_name)
                        except Exception as e:
                            st.error(f"❌ Ingestion failed: {str(e)}")
                            result = None
                else:
                    result = st.session_state[file_key]

                if result and result.get("status") == "SUCCESS":
                    st.success(f"✅ Successfully ingested into PostgreSQL table: **`{result['schema']}.{result['table_name']}`**")

                    profile = result["profile"]

                    # 4 Top KPI Cards
                    k1, k2, k3, k4 = st.columns(4)
                    with k1:
                        st.markdown(
                            f"""
                            <div class="kpi-card">
                                <div class="kpi-label">Total Rows Loaded</div>
                                <div class="kpi-val">{profile['total_rows']:,}</div>
                                <div class="kpi-sub">Dataset records</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with k2:
                        st.markdown(
                            f"""
                            <div class="kpi-card">
                                <div class="kpi-label">Total Columns</div>
                                <div class="kpi-val">{profile['total_cols']:,}</div>
                                <div class="kpi-sub">Detected fields</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with k3:
                        dup_color = "#EF4444" if profile['duplicate_rows'] > 0 else "#10B981"
                        st.markdown(
                            f"""
                            <div class="kpi-card">
                                <div class="kpi-label">Duplicate Rows</div>
                                <div class="kpi-val" style="color:{dup_color}">{profile['duplicate_rows']:,}</div>
                                <div class="kpi-sub">Exact duplicate lines</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with k4:
                        null_color = "#F59E0B" if profile['overall_null_pct'] > 5.0 else "#10B981"
                        st.markdown(
                            f"""
                            <div class="kpi-card">
                                <div class="kpi-label">Missing Data Rate</div>
                                <div class="kpi-val" style="color:{null_color}">{profile['overall_null_pct']}%</div>
                                <div class="kpi-sub">{profile['total_null_cells']:,} empty cells</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    # Schema Profiling & Data Quality Table
                    st.markdown('<div class="section-header">Schema & Data Quality Profile</div>', unsafe_allow_html=True)
                    df_profile = pd.DataFrame(profile["columns"])
                    st.dataframe(
                        df_profile[[
                            "column_name", "inferred_type", "non_null_count", 
                            "null_count", "null_pct", "unique_values", "sample_value"
                        ]].rename(columns={
                            "column_name": "Field Name (Sanitized)",
                            "inferred_type": "Inferred Type",
                            "non_null_count": "Populated Rows",
                            "null_count": "Null Count",
                            "null_pct": "Null %",
                            "unique_values": "Unique Values",
                            "sample_value": "Sample Value"
                        }),
                        use_container_width=True,
                    )

                    # Interactive Data Preview
                    st.markdown('<div class="section-header">Dataset Preview (First 100 Rows)</div>', unsafe_allow_html=True)
                    st.dataframe(result["preview_df"], use_container_width=True)

    with tab_explore:
        st.markdown('<div class="section-header">Explore Ingested PostgreSQL Tables</div>', unsafe_allow_html=True)
        session_tables = st.session_state.get("session_uploaded_tables", [])
        uploaded_meta = get_all_uploaded_tables(allowed_tables=session_tables)

        if uploaded_meta.empty:
            st.info("ℹ️ No custom datasets uploaded in this session yet. Upload a CSV in the tab above to explore and analyze it here.")
        else:
            table_choices = uploaded_meta["table_name"].tolist()
            col_tbl_sel, col_tbl_del = st.columns([3, 1])
            with col_tbl_sel:
                selected_table = st.selectbox(
                    "Select an ingested table to explore:",
                    table_choices,
                    format_func=lambda t: f"{t} ({uploaded_meta[uploaded_meta['table_name'] == t]['original_filename'].values[0]})"
                )
            with col_tbl_del:
                st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
                if st.button("🗑️ Delete Dataset", help="Permanently drop this table and remove its data from PostgreSQL"):
                    try:
                        delete_uploaded_table(selected_table)
                        if selected_table in st.session_state.get("session_uploaded_tables", []):
                            st.session_state["session_uploaded_tables"].remove(selected_table)
                        # Clean any cached file_key pointing to this table
                        for k in list(st.session_state.keys()):
                            if k.startswith("uploaded_"):
                                val = st.session_state[k]
                                if isinstance(val, dict) and val.get("table_name") == selected_table:
                                    del st.session_state[k]
                        # Clean NL-SQL state if it referenced this table
                        if "nl_sql_result" in st.session_state and selected_table in str(st.session_state["nl_sql_result"]):
                            del st.session_state["nl_sql_result"]
                        if "edited_sql" in st.session_state and selected_table in str(st.session_state["edited_sql"]):
                            del st.session_state["edited_sql"]
                        if "nl_exec_result" in st.session_state:
                            del st.session_state["nl_exec_result"]
                        st.success(f"Deleted dataset '{selected_table}'.")
                        st.rerun()
                    except Exception as del_err:
                        st.error(f"Deletion failed: {del_err}")

            if selected_table and selected_table in table_choices:
                meta_row = uploaded_meta[uploaded_meta["table_name"] == selected_table].iloc[0]
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Original File", str(meta_row["original_filename"]))
                m2.metric("Total Rows", f"{meta_row['row_count']:,}")
                m3.metric("Columns", f"{meta_row['column_count']}")
                m4.metric("File Size", f"{meta_row['size_kb']} KB")

                st.markdown(f"**PostgreSQL Target**: `uploads.{selected_table}` | **Uploaded At**: `{meta_row['uploaded_at']}` | **Scope**: `Session-Isolated`")
                
                with st.spinner("Fetching table records..."):
                    df_sample = get_uploaded_table_data(selected_table, limit=100, allowed_tables=session_tables)
                    st.dataframe(df_sample, use_container_width=True)


# =============================================================================
# SECTION 7: ASK YOUR DATA (NATURAL-LANGUAGE SQL ENGINE)
# =============================================================================
elif section == "7. Ask Your Data":
    st.markdown('<div class="main-title">Ask Your Data</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Synthesize schema-aware, read-only PostgreSQL queries from plain English questions across core banking tables and uploaded datasets.</div>', unsafe_allow_html=True)

    # 1. Dataset Selection & Session Synchronization
    st.markdown('<div class="section-header">1. Select Target Dataset</div>', unsafe_allow_html=True)
    
    # Synchronize session-scoped upload tracking with physical database reality
    raw_session_tables = st.session_state.get("session_uploaded_tables", [])
    session_tables = [t for t in raw_session_tables if table_exists_in_db(t)]
    if len(session_tables) != len(raw_session_tables):
        st.session_state["session_uploaded_tables"] = session_tables

    uploaded_meta = get_all_uploaded_tables(allowed_tables=session_tables)
    dataset_options = ["BankScope Banking Data"]
    if not uploaded_meta.empty:
        for _, r in uploaded_meta.iterrows():
            dataset_options.append(f"upload:{r['table_name']}")

    col_ds, col_provider = st.columns([2, 1])
    with col_ds:
        selected_dataset = st.selectbox(
            "Choose Dataset Context:",
            dataset_options,
            format_func=lambda d: "🏦 BankScope Core Warehouse (7 Tables, 1.26M rows)" if d == "BankScope Banking Data" else f"📁 Uploaded: {d.replace('upload:', '')} ({uploaded_meta[uploaded_meta['table_name'] == d.replace('upload:', '')]['original_filename'].values[0]})"
        )

    # Detect if selected uploaded dataset physically disappeared
    if selected_dataset.startswith("upload:"):
        target_check = selected_dataset.replace("upload:", "").strip()
        if not table_exists_in_db(target_check):
            st.error(f"⚠️ Uploaded dataset `{target_check}` is no longer available in PostgreSQL. Please re-upload it.")
            if target_check in st.session_state.get("session_uploaded_tables", []):
                st.session_state["session_uploaded_tables"].remove(target_check)
            if "nl_sql_result" in st.session_state:
                del st.session_state["nl_sql_result"]
            if "edited_sql" in st.session_state:
                del st.session_state["edited_sql"]
            if "nl_exec_result" in st.session_state:
                del st.session_state["nl_exec_result"]
            st.rerun()

    # Clear active query state if user switched to a different dataset in dropdown
    if "active_dataset_choice" not in st.session_state:
        st.session_state["active_dataset_choice"] = selected_dataset
    elif st.session_state["active_dataset_choice"] != selected_dataset:
        st.session_state["active_dataset_choice"] = selected_dataset
        for k in ["nl_sql_result", "edited_sql", "sql_editor_area", "nl_exec_result", "nl_sql_question"]:
            st.session_state.pop(k, None)

    with col_provider:
        llm_provider = get_llm_provider()
        is_offline = isinstance(llm_provider, OfflineBankingSQLProvider)
        is_groq = isinstance(llm_provider, GroqProvider)
        if is_offline:
            badge_header = "DEMO SYNTHESIS ENGINE (NON-AI)"
            badge_title = f"💡 {llm_provider.name}"
            badge_color = "#FBBF24"
        elif is_groq:
            badge_header = "ACTIVE AI PROVIDER (GROQ)"
            badge_title = f"⚡ Groq ({getattr(llm_provider, 'model', 'openai/gpt-oss-20b')})"
            badge_color = "#34D399"
        else:
            badge_header = "ACTIVE AI PROVIDER"
            badge_title = f"⚡ {llm_provider.name} ({getattr(llm_provider, 'model', 'Live API')})"
            badge_color = "#60A5FA"

        st.markdown(
            f"""
            <div style="background:#1E293B; border:1px solid #334155; border-radius:8px; padding:8px 12px; margin-top:24px;">
                <span style="color:#94A3B8; font-size:0.75rem; font-weight:600; text-transform:uppercase;">{badge_header}</span><br/>
                <span style="color:{badge_color}; font-weight:600; font-size:0.88rem;">{badge_title}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Schema Inspector Expander
    schema_ctx = get_dataset_schema_context(selected_dataset)
    with st.expander("🔍 View Active Dataset Schema & Available Fields", expanded=False):
        st.markdown(schema_ctx["context_string"])

    # 2. Question Input
    st.markdown('<div class="section-header">2. Enter Business Question</div>', unsafe_allow_html=True)
    
    if selected_dataset == "BankScope Banking Data":
        sample_questions = [
            "Who are the top 15 customers by total deposit balances across their accounts?",
            "What is the total transaction volume and count broken down by month?",
            "Which 15 merchants processed the highest dollar volume?",
            "What is the distribution of loans and total principal across interest rate tiers?",
            "Which cities have the highest customer concentration and total deposits?"
        ]
    else:
        sample_questions = [
            "What is the average credit limit by customer segment?",
            "Which card status has the highest total monthly spend?",
            "Compare average utilization percentage between credit and debit cards.",
            "Show the top 10 customer segments by total credit limit.",
            "What percentage of cards are active, blocked, and closed?"
        ]

    # Callback when user clicks an example question button
    def set_sample_question(q_text: str):
        st.session_state["nl_sql_question"] = q_text
        # Invalidate all downstream SQL, editor, and execution results
        for k in ["nl_sql_result", "edited_sql", "sql_editor_area", "nl_exec_result"]:
            st.session_state.pop(k, None)

    st.markdown("<span style='color:#94A3B8; font-size:0.85rem;'>💡 Example questions to try:</span>", unsafe_allow_html=True)
    cols_q = st.columns(len(sample_questions))
    for idx, (col, sq) in enumerate(zip(cols_q, sample_questions)):
        with col:
            st.button(
                f"Example {idx+1}", 
                key=f"ex_{idx}", 
                help=sq,
                on_click=set_sample_question,
                args=(sq,)
            )

    user_question = st.text_input(
        "Enter natural language question:",
        placeholder="e.g., Who are the top 15 customers by total deposit balances?",
        key="nl_sql_question"
    )

    col_btn1, col_btn2, _ = st.columns([1, 1, 3])
    with col_btn1:
        generate_clicked = st.button("✨ Generate SQL", type="primary")
    with col_btn2:
        regenerate_clicked = st.button("🔄 Regenerate", help="Re-synthesize SQL query")

    # Invalidate stale generated SQL if user changed the question text in the input box without generating yet
    active_question = st.session_state.get("nl_sql_question", "").strip()
    if "nl_sql_result" in st.session_state and not (generate_clicked or regenerate_clicked):
        prior_gen_q = st.session_state["nl_sql_result"].get("question", "").strip()
        if active_question != prior_gen_q:
            for k in ["nl_sql_result", "edited_sql", "sql_editor_area", "nl_exec_result"]:
                st.session_state.pop(k, None)

    # State management for generated query
    if generate_clicked or regenerate_clicked:
        current_question = st.session_state.get("nl_sql_question", user_question).strip()
        if not current_question:
            st.warning("⚠️ Please enter a question before generating SQL.")
        else:
            with st.spinner(f"Synthesizing PostgreSQL query via {llm_provider.name}..."):
                try:
                    res = generate_sql_query(current_question, selected_dataset, provider=llm_provider)
                except FileNotFoundError as fnf_err:
                    st.error(f"⚠️ {str(fnf_err)}")
                    target_tbl = selected_dataset.replace("upload:", "").strip()
                    if target_tbl in st.session_state.get("session_uploaded_tables", []):
                        st.session_state["session_uploaded_tables"].remove(target_tbl)
                    for k in ["nl_sql_result", "edited_sql", "sql_editor_area", "nl_exec_result"]:
                        st.session_state.pop(k, None)
                    st.rerun()
                except Exception as gen_err:
                    st.warning(f"⚠️ {llm_provider.name} error: {str(gen_err)}. Falling back to Rule-Based Demo Synthesis.")
                    fallback_prov = OfflineBankingSQLProvider()
                    res = generate_sql_query(current_question, selected_dataset, provider=fallback_prov)
                    
                st.session_state["nl_sql_result"] = res
                st.session_state["edited_sql"] = res["sql"]
                # CRITICAL: Overwrite the text_area widget state so the editor displays the fresh SQL!
                st.session_state["sql_editor_area"] = res["sql"]
                # Invalidate any previous execution result when query is regenerated
                st.session_state.pop("nl_exec_result", None)

    # 3. Display Generated SQL & Editor
    if "nl_sql_result" in st.session_state:
        res = st.session_state["nl_sql_result"]
        
        st.markdown('<div class="section-header">3. Review & Edit SQL Statement</div>', unsafe_allow_html=True)
        
        # Ensure sql_editor_area widget key has fresh SQL
        if "sql_editor_area" not in st.session_state:
            st.session_state["sql_editor_area"] = res["sql"]

        # Editable SQL Editor
        edited_sql = st.text_area(
            "Review & Edit SQL Statement:",
            height=220,
            key="sql_editor_area",
            help="You can inspect and modify this query. Query execution strictly requires explicit human approval."
        )
        st.session_state["edited_sql"] = edited_sql

        # If user manually edited the SQL after executing, invalidate stale execution result
        if "nl_exec_result" in st.session_state:
            executed_sql = st.session_state["nl_exec_result"].get("sql_executed", "").strip()
            if edited_sql.strip() != executed_sql:
                st.session_state.pop("nl_exec_result", None)

        # Live multi-tier validation of edited query
        is_sec_valid, sec_msg = validate_sql_security(edited_sql)
        explain_valid = False
        explain_msg = ""
        
        # Check target table existence for uploaded tables
        upload_ref_matches = re.findall(r'\buploads\.([a-zA-Z0-9_]+)\b', edited_sql, re.IGNORECASE)
        table_exists = True
        missing_tbl_name = ""
        if upload_ref_matches:
            for ut in upload_ref_matches:
                if not table_exists_in_db(ut):
                    table_exists = False
                    missing_tbl_name = ut
                    break

        if not table_exists:
            st.error(f"🚨 **Target Table Missing**: Uploaded table `uploads.{missing_tbl_name}` is no longer available in PostgreSQL. Please re-upload your dataset.")
        elif not is_sec_valid:
            st.error(f"🚨 **Security Policy Violation**: {sec_msg}")
        else:
            explain_valid, explain_msg = validate_with_postgres_explain(edited_sql)
            if explain_valid:
                st.success(f"🛡️ **Validation Passed**: Query plan verified by PostgreSQL. Read-only execution permitted on `{res['dataset_name']}`.")
            else:
                st.warning(f"⚠️ **PostgreSQL Catalog/Planner Notice**: {explain_msg}")

        # 4. Human-in-the-Loop Execution Gate
        st.markdown('<div class="section-header">4. Approval & Read-Only Execution</div>', unsafe_allow_html=True)
        
        col_gate_info, col_gate_btn = st.columns([3, 1])
        with col_gate_info:
            st.markdown(
                f"""
                <div style="background:#0F172A; border:1px solid #334155; border-radius:8px; padding:10px 14px;">
                    <span style="color:#94A3B8; font-size:0.8rem; font-weight:600;">TARGET DATASET:</span> 
                    <span style="color:#F8FAFC; font-weight:600;">{res['dataset_name']}</span> &nbsp;|&nbsp; 
                    <span style="color:#94A3B8; font-size:0.8rem; font-weight:600;">ROW LIMIT:</span> 
                    <span style="color:#34D399; font-weight:600;">500</span> &nbsp;|&nbsp;
                    <span style="color:#94A3B8; font-size:0.8rem; font-weight:600;">TIMEOUT:</span> 
                    <span style="color:#60A5FA; font-weight:600;">10s</span><br/>
                    <span style="color:#94A3B8; font-size:0.75rem;">🔒 Dedicated read-only connection. Zero write privileges. Requires explicit user approval.</span>
                </div>
                """,
                unsafe_allow_html=True
            )
        with col_gate_btn:
            can_execute = is_sec_valid and explain_valid and table_exists
            approve_and_run = st.button(
                "🚀 Approve & Run",
                type="primary",
                disabled=not can_execute,
                help="Approve and execute this read-only query on PostgreSQL"
            )

        if approve_and_run:
            with st.spinner("Executing approved read-only query on PostgreSQL..."):
                exec_result = execute_approved_sql(edited_sql, max_rows=500)
                st.session_state["nl_exec_result"] = exec_result

        # 5. Query Results & Visualizations
        if "nl_exec_result" in st.session_state:
            exec_res = st.session_state["nl_exec_result"]
            st.markdown('<div class="section-header">5. Query Results & Analytics</div>', unsafe_allow_html=True)
            
            if not exec_res["success"]:
                st.error(f"❌ **Execution Error**: {exec_res['error_message']}")
            else:
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                with col_m1:
                    st.metric("Status", "Success")
                with col_m2:
                    st.metric("Rows Returned", f"{exec_res['row_count']:,}")
                with col_m3:
                    st.metric("Latency", f"{exec_res['execution_time_ms']} ms")
                with col_m4:
                    st.metric("Connection", "Read-Only Isolated")

                df_res = exec_res["df"]
                if df_res.empty:
                    st.info("ℹ️ Query executed successfully but returned 0 rows.")
                else:
                    # Dynamic Plotly Visualization
                    fig = generate_result_visualization(df_res)
                    if fig is not None:
                        st.plotly_chart(fig, use_container_width=True)

                    # Result Data Table
                    st.markdown("#### **Result Data Table**")
                    st.dataframe(df_res, use_container_width=True, hide_index=True)



