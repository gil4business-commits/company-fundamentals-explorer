from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FUNDAMENTALS_PATH = PROCESSED_DIR / "company_fundamentals.csv"
SUMMARY_PATH = PROCESSED_DIR / "company_summary.csv"
QUALITY_PATH = PROCESSED_DIR / "data_quality_report.csv"

FUNDAMENTALS_COLUMNS = {
    "ticker",
    "cik",
    "company_name",
    "fiscal_year",
    "period_start_date",
    "period_end_date",
    "filed_date",
    "revenue",
    "net_income",
    "operating_cash_flow",
    "revenue_growth_pct",
    "net_margin_pct",
    "has_revenue",
    "has_net_income",
    "has_operating_cash_flow",
    "quality_status",
    "quality_issue_count",
    "quality_notes",
}

SUMMARY_COLUMNS = {
    "ticker",
    "company_name",
    "period_end_date",
    "revenue",
    "revenue_growth_pct",
    "net_income",
    "net_margin_pct",
    "operating_cash_flow",
    "quality_status",
}

QUALITY_COLUMNS = {"ticker", "fiscal_year", "check_name", "status", "details"}


st.set_page_config(
    page_title="Public Company Fundamentals Explorer",
    layout="wide",
)


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    .metric-card {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 0.95rem 1rem;
        background: #ffffff;
        min-height: 112px;
    }
    .metric-label {
        color: #4b5563;
        font-size: 0.83rem;
        line-height: 1.2;
        margin-bottom: 0.4rem;
    }
    .metric-value {
        color: #111827;
        font-size: 1.5rem;
        font-weight: 650;
        line-height: 1.15;
        word-break: break-word;
    }
    .metric-note {
        color: #6b7280;
        font-size: 0.78rem;
        margin-top: 0.35rem;
    }
    .section-note {
        color: #4b5563;
        font-size: 0.95rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def format_usd_billions(value: float | int | None) -> str:
    if pd.isna(value):
        return "N/A"
    return f"${float(value) / 1_000_000_000:,.1f}B"


def format_pct(value: float | int | None) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):,.1f}%"


def format_number(value: float | int | None) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{int(value):,}"


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def missing_files() -> list[Path]:
    return [
        path
        for path in (FUNDAMENTALS_PATH, SUMMARY_PATH, QUALITY_PATH)
        if not path.exists()
    ]


def validate_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        st.error(
            f"{name} is missing required columns: {', '.join(missing)}. "
            "Run `python etl.py` to regenerate processed outputs."
        )
        st.stop()


@st.cache_data
def read_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(FUNDAMENTALS_PATH),
        pd.read_csv(SUMMARY_PATH),
        pd.read_csv(QUALITY_PATH),
    )


def prepare_data(
    fundamentals: pd.DataFrame,
    summary: pd.DataFrame,
    quality: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    date_columns = ["period_start_date", "period_end_date", "filed_date"]
    for column in date_columns:
        fundamentals[column] = pd.to_datetime(fundamentals[column], errors="coerce")
    summary["period_end_date"] = pd.to_datetime(
        summary["period_end_date"], errors="coerce"
    )

    numeric_columns = [
        "fiscal_year",
        "revenue",
        "net_income",
        "operating_cash_flow",
        "revenue_growth_pct",
        "net_margin_pct",
        "quality_issue_count",
    ]
    for column in numeric_columns:
        fundamentals[column] = pd.to_numeric(fundamentals[column], errors="coerce")

    for column in [
        "revenue",
        "revenue_growth_pct",
        "net_income",
        "net_margin_pct",
        "operating_cash_flow",
    ]:
        summary[column] = pd.to_numeric(summary[column], errors="coerce")

    return fundamentals, summary, quality


def latest_processed_timestamp() -> str:
    timestamps = [
        path.stat().st_mtime
        for path in (FUNDAMENTALS_PATH, SUMMARY_PATH, QUALITY_PATH)
        if path.exists()
    ]
    if not timestamps:
        return "N/A"
    return pd.Timestamp(max(timestamps), unit="s").strftime("%Y-%m-%d %H:%M")


def status_counts(df: pd.DataFrame) -> dict[str, int]:
    counts = df["quality_status"].value_counts().to_dict()
    return {status: int(counts.get(status, 0)) for status in ("PASS", "WARN", "FAIL")}


def line_chart(df: pd.DataFrame, y_column: str, title: str, y_title: str) -> alt.Chart:
    chart_data = df.copy()
    if y_column in {"revenue", "net_income", "operating_cash_flow"}:
        chart_data[y_column] = chart_data[y_column] / 1_000_000_000
        tooltip_format = ",.1f"
    else:
        tooltip_format = ",.1f"

    return (
        alt.Chart(chart_data)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X(
                "fiscal_year:O",
                title="Fiscal year",
                sort="ascending",
            ),
            y=alt.Y(f"{y_column}:Q", title=y_title),
            tooltip=[
                alt.Tooltip("fiscal_year:O", title="Fiscal year"),
                alt.Tooltip("period_end_date:T", title="Period end"),
                alt.Tooltip(f"{y_column}:Q", title=title, format=tooltip_format),
            ],
        )
        .properties(height=260)
    )


def bar_chart(
    df: pd.DataFrame,
    value_column: str,
    title: str,
    value_title: str,
) -> alt.Chart:
    chart_data = df.copy()
    if value_column in {"revenue", "net_income", "operating_cash_flow"}:
        chart_data[value_column] = chart_data[value_column] / 1_000_000_000

    return (
        alt.Chart(chart_data)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("ticker:N", title="Company", sort="-y"),
            y=alt.Y(f"{value_column}:Q", title=value_title),
            color=alt.Color("ticker:N", legend=None),
            tooltip=[
                alt.Tooltip("ticker:N", title="Ticker"),
                alt.Tooltip("company_name:N", title="Company"),
                alt.Tooltip("period_end_date:T", title="Period end"),
                alt.Tooltip(f"{value_column}:Q", title=title, format=",.1f"),
            ],
        )
        .properties(height=300)
    )


def display_comparison_table(summary: pd.DataFrame) -> None:
    table = summary.copy()
    table["Company"] = table["company_name"]
    table["Period End"] = table["period_end_date"].dt.strftime("%Y-%m-%d")
    table["Revenue"] = table["revenue"].map(format_usd_billions)
    table["Revenue Growth"] = table["revenue_growth_pct"].map(format_pct)
    table["Net Income"] = table["net_income"].map(format_usd_billions)
    table["Net Margin"] = table["net_margin_pct"].map(format_pct)
    table["Operating Cash Flow"] = table["operating_cash_flow"].map(
        format_usd_billions
    )
    table["Quality"] = table["quality_status"]

    st.dataframe(
        table[
            [
                "Company",
                "Period End",
                "Revenue",
                "Revenue Growth",
                "Net Income",
                "Net Margin",
                "Operating Cash Flow",
                "Quality",
            ]
        ],
        hide_index=True,
        width="stretch",
    )


def main() -> None:
    st.title("Public Company Fundamentals Explorer")
    st.markdown(
        "Transforms public SEC company filings into comparable annual financial "
        "insights for selected large public companies."
    )
    st.caption("Source: U.S. SEC EDGAR company facts API")

    missing = missing_files()
    if missing:
        st.error(
            "Processed data files are missing. Run `python etl.py` before opening "
            "the dashboard."
        )
        st.write("Missing files:")
        for path in missing:
            st.code(str(path.relative_to(PROJECT_ROOT)))
        st.stop()

    fundamentals, summary, quality = read_data()
    validate_columns(fundamentals, FUNDAMENTALS_COLUMNS, "company_fundamentals.csv")
    validate_columns(summary, SUMMARY_COLUMNS, "company_summary.csv")
    validate_columns(quality, QUALITY_COLUMNS, "data_quality_report.csv")
    fundamentals, summary, quality = prepare_data(fundamentals, summary, quality)

    selected_counts = status_counts(fundamentals)
    diagnostic_checks = quality[quality["check_name"] != "row_quality_status"]
    diagnostic_warn_count = int((diagnostic_checks["status"] == "WARN").sum())

    st.divider()
    overview_cols = st.columns(6)
    with overview_cols[0]:
        metric_card("Companies", format_number(summary["ticker"].nunique()))
    with overview_cols[1]:
        metric_card("Annual Periods", format_number(len(fundamentals)))
    with overview_cols[2]:
        metric_card("Selected PASS", format_number(selected_counts["PASS"]))
    with overview_cols[3]:
        metric_card("Selected WARN", format_number(selected_counts["WARN"]))
    with overview_cols[4]:
        metric_card("Selected FAIL", format_number(selected_counts["FAIL"]))
    with overview_cols[5]:
        metric_card("Processed Data Updated", latest_processed_timestamp())

    if diagnostic_warn_count:
        st.info(
            f"The selected analytical dataset has {selected_counts['PASS']} PASS rows. "
            f"The pipeline also recorded {diagnostic_warn_count} diagnostic WARN checks "
            "for historical SEC facts that were excluded before metrics were shown."
        )

    st.header("Company Detail")
    selected_ticker = st.selectbox(
        "Company",
        sorted(fundamentals["ticker"].unique()),
        index=0,
    )

    company_rows = (
        fundamentals[fundamentals["ticker"] == selected_ticker]
        .sort_values("period_end_date")
        .reset_index(drop=True)
    )
    latest = company_rows.iloc[-1]

    st.subheader(f"{latest['company_name']} ({selected_ticker})")
    st.caption(
        "Latest reported annual values, based on the company's own fiscal reporting "
        f"period ending {latest['period_end_date'].strftime('%Y-%m-%d')}."
    )

    kpi_cols = st.columns(5)
    with kpi_cols[0]:
        metric_card("Revenue", format_usd_billions(latest["revenue"]))
    with kpi_cols[1]:
        metric_card("Revenue Growth", format_pct(latest["revenue_growth_pct"]))
    with kpi_cols[2]:
        metric_card("Net Income", format_usd_billions(latest["net_income"]))
    with kpi_cols[3]:
        metric_card("Net Margin", format_pct(latest["net_margin_pct"]))
    with kpi_cols[4]:
        metric_card(
            "Operating Cash Flow",
            format_usd_billions(latest["operating_cash_flow"]),
            latest["quality_status"],
        )

    chart_cols = st.columns(3)
    with chart_cols[0]:
        st.altair_chart(
            line_chart(company_rows, "revenue", "Revenue", "Revenue ($B)"),
            width="stretch",
        )
    with chart_cols[1]:
        st.altair_chart(
            line_chart(company_rows, "net_income", "Net Income", "Net Income ($B)"),
            width="stretch",
        )
    with chart_cols[2]:
        st.altair_chart(
            line_chart(
                company_rows,
                "operating_cash_flow",
                "Operating Cash Flow",
                "Operating Cash Flow ($B)",
            ),
            width="stretch",
        )

    trend_cols = st.columns(2)
    with trend_cols[0]:
        st.altair_chart(
            line_chart(
                company_rows,
                "revenue_growth_pct",
                "Revenue Growth",
                "Revenue Growth (%)",
            ),
            width="stretch",
        )
    with trend_cols[1]:
        st.altair_chart(
            line_chart(company_rows, "net_margin_pct", "Net Margin", "Net Margin (%)"),
            width="stretch",
        )

    st.header("Latest Reported Annual Results")
    st.markdown(
        '<p class="section-note">Companies do not all share the same fiscal '
        "year-end date, so this section compares each company's latest reported "
        "annual period rather than a single calendar year.</p>",
        unsafe_allow_html=True,
    )
    display_comparison_table(summary.sort_values("ticker"))

    comparison_cols = st.columns(2)
    with comparison_cols[0]:
        st.altair_chart(
            bar_chart(summary, "revenue", "Revenue", "Revenue ($B)"),
            width="stretch",
        )
    with comparison_cols[1]:
        st.altair_chart(
            bar_chart(summary, "net_margin_pct", "Net Margin", "Net Margin (%)"),
            width="stretch",
        )

    st.header("Data Quality & Reliability")
    quality_cols = st.columns(4)
    with quality_cols[0]:
        metric_card("Selected Row PASS", format_number(selected_counts["PASS"]))
    with quality_cols[1]:
        metric_card("Selected Row WARN", format_number(selected_counts["WARN"]))
    with quality_cols[2]:
        metric_card("Selected Row FAIL", format_number(selected_counts["FAIL"]))
    with quality_cols[3]:
        metric_card("Diagnostic WARN", format_number(diagnostic_warn_count))

    missing_metric_counts = {
        "Missing revenue": int((~fundamentals["has_revenue"].astype(bool)).sum()),
        "Missing net income": int((~fundamentals["has_net_income"].astype(bool)).sum()),
        "Missing operating cash flow": int(
            (~fundamentals["has_operating_cash_flow"].astype(bool)).sum()
        ),
    }

    st.markdown(
        "SEC XBRL facts can include comparative, duplicate, amended, or non-annual "
        "observations. The ETL applies deterministic filtering before metrics are "
        "shown. Diagnostic warnings describe excluded facts and do not necessarily "
        "mean the final selected analytical row is unreliable."
    )

    missing_df = pd.DataFrame(
        [
            {"Metric": metric, "Missing selected rows": count}
            for metric, count in missing_metric_counts.items()
        ]
    )
    st.dataframe(missing_df, hide_index=True, width="stretch")

    diagnostics_summary = (
        diagnostic_checks.groupby(["status", "check_name"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["status", "check_name"])
    )
    st.dataframe(diagnostics_summary, hide_index=True, width="stretch")

    with st.expander("Diagnostic check details"):
        st.dataframe(
            quality.sort_values(["status", "ticker", "fiscal_year", "check_name"]),
            hide_index=True,
            width="stretch",
        )

    with st.expander("Methodology"):
        st.markdown(
            """
            - Source data comes from the public SEC EDGAR company facts API.
            - The dashboard reads local processed CSV files generated by `python etl.py`.
            - Metrics use USD facts from annual 10-K observations.
            - The ETL requires plausible annual durations of approximately 300-430 days.
            - Revenue uses prioritized concepts: `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, then `SalesRevenueNet`.
            - When duplicate annual facts remain for the same reporting period, the latest filed fact is selected and conflicts are reported.
            - Revenue growth is calculated only when consecutive annual revenue observations exist and prior revenue is positive.
            - Net margin is calculated only when revenue and net income exist and revenue is positive.
            - Architecture: SEC extraction to `data/raw/`, deterministic transformation and validation to `data/processed/`, then Streamlit reads the processed outputs.
            """
        )


if __name__ == "__main__":
    main()
