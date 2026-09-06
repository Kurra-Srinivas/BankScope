"""
BankScope — SQL Result Visualization Engine
Automatically detects chartable patterns in SQL query results and produces
responsive, dark-themed Plotly figures (Time-Series, Category Rankings, Donut Distributions).
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


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
    Intelligently select and construct an appropriate Plotly chart for an executed SQL result.
    Returns:
        Plotly Figure if data is chartable, otherwise None.
    """
    if df is None or df.empty or len(df) <= 1:
        # 0 or 1 rows are best displayed as pure tables or metrics
        return None

    cols = list(df.columns)
    if len(cols) < 2:
        return None

    # Classify columns
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c]) and not c.lower().endswith(('_id', 'id'))]
    date_cols = [c for c in cols if any(k in c.lower() for k in ["date", "month", "year", "time", "day", "period"])]
    cat_cols = [c for c in cols if c not in numeric_cols and c not in date_cols]

    # Pattern 1: Time-Series Trend (Date/Month column + Numeric column)
    if date_cols and numeric_cols:
        date_col = date_cols[0]
        num_col = numeric_cols[0]
        
        # Sort by date for chronological presentation
        df_sorted = df.copy()
        try:
            df_sorted[date_col] = pd.to_datetime(df_sorted[date_col])
            df_sorted = df_sorted.sort_values(date_col)
        except Exception:
            pass

        fig = px.line(
            df_sorted,
            x=date_col,
            y=num_col,
            markers=True,
            title=f"Trend: {num_col.replace('_', ' ').title()} over {date_col.replace('_', ' ').title()}",
            color_discrete_sequence=["#60A5FA"],
        )
        fig.update_layout(**get_bankscope_chart_layout())
        fig.update_traces(line=dict(width=2.5), marker=dict(size=6, color="#93C5FD"))
        return fig

    # Pattern 2: Low-Cardinality Proportions (2-6 distinct categories -> Donut Chart)
    if cat_cols and numeric_cols:
        cat_col = cat_cols[0]
        num_col = numeric_cols[0]
        unique_cats = df[cat_col].nunique()

        if 2 <= unique_cats <= 6 and len(df) <= 10:
            fig = px.pie(
                df,
                names=cat_col,
                values=num_col,
                hole=0.5,
                title=f"Distribution of {num_col.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}",
                color_discrete_sequence=["#60A5FA", "#34D399", "#FBBF24", "#F87171", "#A78BFA", "#38BDF8"],
            )
            fig.update_layout(**get_bankscope_chart_layout())
            fig.update_traces(textposition="inside", textinfo="percent+label")
            return fig

    # Pattern 3: Categorical Ranking / Top-N Bar Chart (<= 30 categories)
    if cat_cols and numeric_cols:
        cat_col = cat_cols[0]
        num_col = numeric_cols[0]

        if len(df) <= 30:
            # Sort for visual hierarchy
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

    # Pattern 4: Dual-metric comparison across items
    if len(numeric_cols) >= 2 and cat_cols and len(df) <= 20:
        cat_col = cat_cols[0]
        m1, m2 = numeric_cols[0], numeric_cols[1]
        fig = px.bar(
            df,
            x=cat_col,
            y=[m1, m2],
            barmode="group",
            title=f"Comparative Breakdown: {m1.replace('_', ' ').title()} vs {m2.replace('_', ' ').title()}",
            color_discrete_sequence=["#60A5FA", "#34D399"],
        )
        fig.update_layout(**get_bankscope_chart_layout())
        return fig

    return None
