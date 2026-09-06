"""
BankScope — SQL Result Visualization Engine
Automatically detects chartable patterns in SQL query results and produces
responsive, dark-themed Plotly figures (Time-Series, Category Rankings, Donut Distributions).
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def get_bankscope_chart_layout(title: str | None = None) -> dict:
    """Standardized dark-theme layout settings matching BankScope UI."""
    layout_dict = dict(
        paper_bgcolor="#0F172A",
        plot_bgcolor="#1E293B",
        font=dict(color="#F8FAFC", family="Inter, system-ui, sans-serif"),
        margin=dict(l=40, r=20, t=40, b=40),
        xaxis=dict(
            gridcolor="#334155",
            zerolinecolor="#475569",
            tickfont=dict(color="#94A3B8"),
        ),
        yaxis=dict(
            gridcolor="#334155",
            zerolinecolor="#475569",
            tickfont=dict(color="#94A3B8"),
        ),
        legend=dict(
            bgcolor="rgba(30, 41, 59, 0.7)",
            bordercolor="#334155",
            font=dict(color="#F8FAFC"),
        ),
    )
    if title:
        layout_dict["title"] = dict(text=title, font=dict(size=14, color="#93C5FD"))
    return layout_dict


def generate_result_visualization(df: pd.DataFrame) -> go.Figure | None:
    """
    Intelligently and deterministically select an appropriate Plotly chart for an executed SQL result.
    Enforces semantic rules:
    1. Categorical + 1 Metric -> BAR chart (vertical for comparisons, horizontal for rankings).
    2. Explicit composition / proportion -> DONUT / PIE chart (only when additive share is explicit).
       NEVER use pie for averages, rates, limits, spend, or ranking metrics.
    3. Categorical + 2 Metrics:
       - If scales are comparable (ratio <= 3.0) -> Grouped BAR chart.
       - If scales differ substantially (ratio > 3.0) -> Dual-axis Grouped BAR chart (secondary_y).
    4. Date / Time + Metric -> LINE chart.
    5. Single row with single metric -> None (rendered as KPI / table in UI).
    """
    if df is None or df.empty:
        return None

    cols = list(df.columns)
    if len(cols) < 2:
        return None

    # Classify columns: numeric columns must never be classified as date columns
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c]) and not c.lower().endswith(("_id", "id"))]
    date_cols = [
        c for c in cols 
        if c not in numeric_cols and (
            pd.api.types.is_datetime64_any_dtype(df[c]) 
            or any(k in c.lower() for k in ["date", "month", "year", "time", "day", "period"])
        )
    ]
    cat_cols = [c for c in cols if c not in numeric_cols and c not in date_cols]

    # Pattern 1: Time-Series Trend (Date/Month column + Numeric column) -> LINE chart
    if date_cols and numeric_cols:
        date_col = date_cols[0]
        df_sorted = df.copy()
        try:
            df_sorted[date_col] = pd.to_datetime(df_sorted[date_col])
            df_sorted = df_sorted.sort_values(date_col)
        except Exception:
            pass

        if len(numeric_cols) == 1:
            num_col = numeric_cols[0]
            title_text = f"Trend: {num_col.replace('_', ' ').title()} over {date_col.replace('_', ' ').title()}"
            fig = px.line(
                df_sorted,
                x=date_col,
                y=num_col,
                markers=True,
                title=title_text,
                color_discrete_sequence=["#60A5FA"],
            )
            fig.update_layout(**get_bankscope_chart_layout())
            fig.update_traces(line=dict(width=2.5), marker=dict(size=6, color="#93C5FD"))
            return fig
        else:
            # Multi-metric time series
            m_cols = numeric_cols[:3]
            fig = px.line(
                df_sorted,
                x=date_col,
                y=m_cols,
                markers=True,
                title=f"Trend Comparison over {date_col.replace('_', ' ').title()}",
                color_discrete_sequence=["#60A5FA", "#34D399", "#FBBF24"],
            )
            fig.update_layout(**get_bankscope_chart_layout())
            return fig

    # Pattern 2: Categorical + TWO or more Numerical Metrics
    if cat_cols and len(numeric_cols) >= 2 and len(df) <= 30:
        cat_col = cat_cols[0]
        m1, m2 = numeric_cols[0], numeric_cols[1]
        
        # Determine scale ratio between the two metrics
        max1 = float(df[m1].abs().max()) if not df[m1].empty else 0.0
        max2 = float(df[m2].abs().max()) if not df[m2].empty else 0.0
        scale_ratio = max(max1, max2) / max(min(max1, max2), 1e-9) if max1 > 0 and max2 > 0 else 1.0

        m1_title = m1.replace('_', ' ').title()
        m2_title = m2.replace('_', ' ').title()

        if scale_ratio > 3.0:
            # Substantially different scales: use dual-axis grouped bar to prevent visual squashing
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(
                go.Bar(
                    name=m1_title,
                    x=df[cat_col],
                    y=df[m1],
                    marker_color="#60A5FA",
                    offsetgroup=1,
                    text=df[m1].apply(lambda v: f"{v:,.2f}" if isinstance(v, (int, float)) else str(v)),
                    textposition="auto",
                ),
                secondary_y=False,
            )
            fig.add_trace(
                go.Bar(
                    name=m2_title,
                    x=df[cat_col],
                    y=df[m2],
                    marker_color="#34D399",
                    offsetgroup=2,
                    text=df[m2].apply(lambda v: f"{v:,.2f}" if isinstance(v, (int, float)) else str(v)),
                    textposition="auto",
                ),
                secondary_y=True,
            )
            layout_settings = get_bankscope_chart_layout(f"Comparative Breakdown: {m1_title} vs {m2_title}")
            fig.update_layout(
                **layout_settings,
                barmode="group",
            )
            fig.update_yaxes(title_text=m1_title, secondary_y=False, gridcolor="#334155")
            fig.update_yaxes(title_text=m2_title, secondary_y=True, gridcolor="#1E293B")
            return fig
        else:
            # Comparable scales: standard grouped bar chart
            fig = px.bar(
                df,
                x=cat_col,
                y=[m1, m2],
                barmode="group",
                title=f"Comparative Breakdown: {m1_title} vs {m2_title}",
                color_discrete_sequence=["#60A5FA", "#34D399"],
            )
            fig.update_layout(**get_bankscope_chart_layout())
            return fig

    # Pattern 3: Categorical + ONE Numerical Metric
    if cat_cols and len(numeric_cols) == 1:
        cat_col = cat_cols[0]
        num_col = numeric_cols[0]
        unique_cats = df[cat_col].nunique()
        num_col_lower = num_col.lower()

        # Semantic Check for Explicit Composition / Share Queries (DONUT/PIE Chart)
        # ONLY apply donut/pie when column name or values explicitly represent additive proportions/shares,
        # and NEVER for averages, rates, limits, spend, or ranking metrics!
        has_share_keyword = any(k in num_col_lower for k in ["percent", "percentage", "pct_share", "share", "proportion"])
        has_non_additive_keyword = any(k in num_col_lower for k in ["avg", "average", "mean", "utilization", "rate", "limit", "spend", "balance"])
        
        is_additive_sum = False
        try:
            total_sum = float(df[num_col].sum())
            is_additive_sum = (98.0 <= total_sum <= 102.0) or (0.98 <= total_sum <= 1.02)
        except Exception:
            pass

        is_explicit_composition = (has_share_keyword and not has_non_additive_keyword) or (is_additive_sum and not has_non_additive_keyword)

        if is_explicit_composition and 2 <= unique_cats <= 7 and len(df) <= 10:
            fig = px.pie(
                df,
                names=cat_col,
                values=num_col,
                hole=0.5,
                title=f"Distribution: {num_col.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}",
                color_discrete_sequence=["#60A5FA", "#34D399", "#FBBF24", "#F87171", "#A78BFA", "#38BDF8"],
            )
            fig.update_layout(**get_bankscope_chart_layout())
            fig.update_traces(textposition="inside", textinfo="percent+label")
            return fig

        # Default for Categorical + One Metric: BAR CHART
        # Ranking queries (> 6 categories, or spend/ranking keywords) -> Horizontal Bar
        is_ranking = (
            len(df) > 6 
            or any(k in num_col_lower for k in ["spend", "revenue", "rank", "volume", "total"])
            or any(k in cat_col.lower() for k in ["merchant", "branch", "name", "city"])
        )

        if is_ranking and len(df) <= 30:
            # Horizontal Bar Chart for Rankings
            df_sorted = df.sort_values(num_col, ascending=True)
            fig = px.bar(
                df_sorted,
                x=num_col,
                y=cat_col,
                orientation="h",
                title=f"Rankings: {num_col.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}",
                color_discrete_sequence=["#38BDF8"],
                text=num_col,
            )
            fig.update_layout(**get_bankscope_chart_layout())
            fig.update_traces(
                marker=dict(line=dict(color="#1E40AF", width=1)),
                texttemplate="%{text:,.2s}",
                textposition="outside",
            )
            return fig
        elif len(df) <= 30:
            # Vertical Bar Chart for Comparisons (e.g. Credit vs Debit, Segment vs Avg Limit)
            num_title = num_col.replace('_', ' ').title()
            cat_title = cat_col.replace('_', ' ').title()
            fig = px.bar(
                df,
                x=cat_col,
                y=num_col,
                title=f"{num_title} by {cat_title}",
                color=cat_col if unique_cats <= 6 else None,
                color_discrete_sequence=["#60A5FA", "#34D399", "#FBBF24", "#A78BFA", "#F87171", "#38BDF8"],
                text=num_col,
            )
            fig.update_layout(**get_bankscope_chart_layout())
            fig.update_traces(
                texttemplate="%{text:,.2f}",
                textposition="outside",
            )
            fig.update_yaxes(title_text=num_title)
            fig.update_xaxes(title_text=cat_title)
            return fig

    return None

