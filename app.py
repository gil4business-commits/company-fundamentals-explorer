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
    "revenue_concept",
    "net_income_concept",
    "operating_cash_flow_concept",
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

COMPANY_DISPLAY_NAMES = {
    "AMAZON COM INC": "Amazon",
    "MICROSOFT CORPORATION": "Microsoft",
    "NVIDIA CORP": "NVIDIA",
    "Apple Inc.": "Apple",
    "Meta Platforms, Inc.": "Meta",
}

ACCENT_COLOR = "#2563eb"
ACCENT_DARK = "#1e3a8a"
PASS_COLOR = "#15803d"
WARN_COLOR = "#b45309"
FAIL_COLOR = "#b91c1c"


st.set_page_config(
    page_title="Public Company Fundamentals Explorer",
    layout="wide",
)


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.25rem;
        padding-bottom: 3rem;
    }
    .app-header {
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 1.15rem 1.25rem;
        background: #ffffff;
        margin-bottom: 1rem;
    }
    .app-title {
        color: #111827;
        font-size: 2rem;
        font-weight: 750;
        line-height: 1.15;
        margin-bottom: 0.35rem;
    }
    .app-subtitle {
        color: #374151;
        font-size: 1rem;
        margin-bottom: 0.7rem;
    }
    .source-row {
        color: #6b7280;
        font-size: 0.85rem;
    }
    .source-pill {
        display: inline-block;
        border: 1px solid #bfdbfe;
        border-radius: 999px;
        background: #eff6ff;
        color: #1d4ed8;
        padding: 0.12rem 0.55rem;
        font-weight: 650;
        margin-right: 0.45rem;
    }
    .metric-card {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 0.95rem 1rem;
        background: #ffffff;
        min-height: 118px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }
    .metric-label {
        color: #4b5563;
        font-size: 0.83rem;
        line-height: 1.2;
        margin-bottom: 0.4rem;
    }
    .metric-value {
        color: #111827;
        font-size: 1.55rem;
        font-weight: 720;
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
    .insight-card {
        border: 1px solid #dbeafe;
        border-left: 4px solid #2563eb;
        border-radius: 8px;
        padding: 0.85rem 1rem;
        background: #f8fbff;
        min-height: 96px;
        color: #1f2937;
        font-size: 0.95rem;
        line-height: 1.45;
        margin-bottom: 0.75rem;
    }
    .tab-note {
        color: #6b7280;
        font-size: 0.9rem;
        margin-top: -0.35rem;
        margin-bottom: 1rem;
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


def display_company_name(company_name: str) -> str:
    return COMPANY_DISPLAY_NAMES.get(company_name, company_name)


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


def insight_card(text: str) -> None:
    st.markdown(f'<div class="insight-card">{text}</div>', unsafe_allow_html=True)


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

    fundamentals["display_company_name"] = fundamentals["company_name"].map(
        display_company_name
    )
    summary["display_company_name"] = summary["company_name"].map(display_company_name)

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


METRIC_OPTIONS = {
    "Revenue": {
        "column": "revenue",
        "unit": "$B",
        "axis": "Revenue ($B)",
        "formatter": format_usd_billions,
    },
    "Revenue Growth": {
        "column": "revenue_growth_pct",
        "unit": "%",
        "axis": "Revenue Growth (%)",
        "formatter": format_pct,
    },
    "Net Income": {
        "column": "net_income",
        "unit": "$B",
        "axis": "Net Income ($B)",
        "formatter": format_usd_billions,
    },
    "Net Margin": {
        "column": "net_margin_pct",
        "unit": "%",
        "axis": "Net Margin (%)",
        "formatter": format_pct,
    },
    "Operating Cash Flow": {
        "column": "operating_cash_flow",
        "unit": "$B",
        "axis": "Operating Cash Flow ($B)",
        "formatter": format_usd_billions,
    },
}


def build_executive_insights(summary: pd.DataFrame) -> list[str]:
    metrics = [
        ("revenue", "latest revenue", format_usd_billions),
        ("revenue_growth_pct", "latest revenue growth", format_pct),
        ("net_margin_pct", "latest net margin", format_pct),
        ("operating_cash_flow", "latest operating cash flow", format_usd_billions),
    ]
    insights = []
    for column, label, formatter in metrics:
        row = summary.sort_values(column, ascending=False).iloc[0]
        insights.append(
            f"{row['display_company_name']} has the highest {label} in the latest "
            f"reported annual results at {formatter(row[column])}, for the period "
            f"ending {row['period_end_date'].strftime('%Y-%m-%d')}."
        )
    return insights


def line_chart(df: pd.DataFrame, y_column: str, title: str, y_title: str) -> alt.Chart:
    chart_data = df.copy()
    if y_column in {"revenue", "net_income", "operating_cash_flow"}:
        chart_data[y_column] = chart_data[y_column] / 1_000_000_000
        tooltip_format = ",.1f"
    else:
        tooltip_format = ",.1f"

    return (
        alt.Chart(chart_data)
        .mark_line(point=True, strokeWidth=3, color=ACCENT_COLOR)
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
        .configure_axis(
            gridColor="#e5e7eb",
            labelColor="#4b5563",
            titleColor="#4b5563",
        )
        .configure_view(strokeOpacity=0)
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
        .mark_bar(
            cornerRadiusTopLeft=3,
            cornerRadiusTopRight=3,
            color=ACCENT_COLOR,
        )
        .encode(
            x=alt.X(
                "display_company_name:N",
                title="Company",
                sort="-y",
            ),
            y=alt.Y(f"{value_column}:Q", title=value_title),
            tooltip=[
                alt.Tooltip("ticker:N", title="Ticker"),
                alt.Tooltip("display_company_name:N", title="Company"),
                alt.Tooltip("period_end_date:T", title="Period end"),
                alt.Tooltip(f"{value_column}:Q", title=title, format=",.1f"),
            ],
        )
        .properties(height=300)
        .configure_axis(
            gridColor="#e5e7eb",
            labelColor="#4b5563",
            titleColor="#4b5563",
        )
        .configure_view(strokeOpacity=0)
    )


def display_comparison_table(summary: pd.DataFrame) -> None:
    table = summary.copy()
    table["Company"] = table["display_company_name"]
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


def metric_comparison_chart(summary: pd.DataFrame, metric_label: str) -> alt.Chart:
    metric = METRIC_OPTIONS[metric_label]
    column = metric["column"]
    chart_data = summary.copy()
    if column in {"revenue", "net_income", "operating_cash_flow"}:
        chart_data["chart_value"] = chart_data[column] / 1_000_000_000
        tooltip_format = ",.1f"
    else:
        chart_data["chart_value"] = chart_data[column]
        tooltip_format = ",.1f"

    chart_data["formatted_value"] = chart_data[column].map(metric["formatter"])

    return (
        alt.Chart(chart_data)
        .mark_bar(
            cornerRadiusTopLeft=3,
            cornerRadiusTopRight=3,
            color=ACCENT_COLOR,
        )
        .encode(
            x=alt.X(
                "display_company_name:N",
                title="Company",
                sort=alt.SortField(field="chart_value", order="descending"),
            ),
            y=alt.Y("chart_value:Q", title=metric["axis"]),
            tooltip=[
                alt.Tooltip("ticker:N", title="Ticker"),
                alt.Tooltip("display_company_name:N", title="Company"),
                alt.Tooltip("period_end_date:T", title="Period end"),
                alt.Tooltip("chart_value:Q", title=metric_label, format=tooltip_format),
            ],
        )
        .properties(height=340)
        .configure_axis(
            gridColor="#e5e7eb",
            labelColor="#4b5563",
            titleColor="#4b5563",
        )
        .configure_view(strokeOpacity=0)
    )


def latest_provenance_table(latest: pd.Series) -> pd.DataFrame:
    quality_notes = latest["quality_notes"]
    if pd.isna(quality_notes) or not str(quality_notes).strip():
        quality_notes = "No material issues."

    rows = [
        ("Ticker", latest["ticker"]),
        ("Fiscal period end", latest["period_end_date"].strftime("%Y-%m-%d")),
        ("Filing date", latest["filed_date"].strftime("%Y-%m-%d")),
        ("Revenue XBRL concept", latest["revenue_concept"]),
        ("Net income XBRL concept", latest["net_income_concept"]),
        ("Operating cash flow XBRL concept", latest["operating_cash_flow_concept"]),
        ("Quality status", latest["quality_status"]),
        ("Quality notes", quality_notes),
    ]
    return pd.DataFrame(rows, columns=["Field", "Value"])


def quality_matrix(fundamentals: pd.DataFrame) -> pd.DataFrame:
    matrix = fundamentals.pivot_table(
        index="display_company_name",
        columns="fiscal_year",
        values="quality_status",
        aggfunc="first",
    )
    matrix = matrix.reindex(sorted(matrix.columns), axis=1)
    matrix.index.name = "Company"
    return matrix.fillna("")


def metric_completeness_table(fundamentals: pd.DataFrame) -> pd.DataFrame:
    completeness = (
        fundamentals.groupby("display_company_name")[
            ["has_revenue", "has_net_income", "has_operating_cash_flow"]
        ]
        .sum()
        .astype(int)
        .reset_index()
    )
    completeness = completeness.rename(
        columns={
            "display_company_name": "Company",
            "has_revenue": "Revenue periods",
            "has_net_income": "Net income periods",
            "has_operating_cash_flow": "Operating cash flow periods",
        }
    )
    return completeness


def render_header() -> None:
    st.markdown(
        f"""
        <div class="app-header">
            <div class="app-title">Public Company Fundamentals Explorer</div>
            <div class="app-subtitle">
                Transforms public SEC company filings into comparable annual financial insights.
            </div>
            <div class="source-row">
                <span class="source-pill">SEC EDGAR</span>
                Latest processed data refresh: {latest_processed_timestamp()}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def style_quality_matrix(matrix: pd.DataFrame) -> pd.io.formats.style.Styler:
    def style_cell(value: str) -> str:
        if value == "PASS":
            return f"background-color: #dcfce7; color: {PASS_COLOR}; font-weight: 650;"
        if value == "WARN":
            return f"background-color: #fef3c7; color: {WARN_COLOR}; font-weight: 650;"
        if value == "FAIL":
            return f"background-color: #fee2e2; color: {FAIL_COLOR}; font-weight: 650;"
        return ""

    return matrix.style.map(style_cell)


def main() -> None:
    render_header()

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

    overview_tab, company_tab, quality_tab = st.tabs(
        ["Overview", "Company Explorer", "Data Quality"]
    )

    with overview_tab:
        st.subheader("Portfolio Snapshot")
        overview_cols = st.columns(6)
        with overview_cols[0]:
            metric_card("Companies", format_number(summary["ticker"].nunique()))
        with overview_cols[1]:
            metric_card("Annual Periods", format_number(len(fundamentals)))
        with overview_cols[2]:
            metric_card("Validated Rows", format_number(selected_counts["PASS"]))
        with overview_cols[3]:
            metric_card("Selected Warnings", format_number(selected_counts["WARN"]))
        with overview_cols[4]:
            metric_card("Selected Failures", format_number(selected_counts["FAIL"]))
        with overview_cols[5]:
            metric_card("Diagnostic Warnings", format_number(diagnostic_warn_count))

        if diagnostic_warn_count:
            st.info(
                f"The selected analytical dataset has {selected_counts['PASS']} validated rows. "
                f"The pipeline also recorded {diagnostic_warn_count} diagnostic WARN checks "
                "for historical SEC facts that were excluded before metrics were shown."
            )

        st.subheader("Executive Insights")
        st.caption(
            "Descriptive comparisons use each company's latest reported annual period; "
            "period-end dates differ by company."
        )
        insight_cols = st.columns(2)
        for index, insight in enumerate(build_executive_insights(summary)):
            with insight_cols[index % 2]:
                insight_card(insight)

        st.subheader("Latest Reported Annual Results")
        st.markdown(
            '<p class="section-note">Companies do not all share the same fiscal '
            "year-end date, so this section compares each company's latest reported "
            "annual period rather than a single calendar year.</p>",
            unsafe_allow_html=True,
        )
        display_comparison_table(summary.sort_values("ticker"))

        st.subheader("Compare Companies")
        selected_metric = st.selectbox(
            "Metric",
            list(METRIC_OPTIONS),
            index=0,
        )
        st.altair_chart(
            metric_comparison_chart(summary, selected_metric),
            width="stretch",
        )

    with company_tab:
        st.subheader("Company Explorer")
        selected_ticker = st.selectbox(
            "Company",
            sorted(fundamentals["ticker"].unique()),
            index=0,
            format_func=lambda ticker: (
                f"{ticker} - "
                f"{fundamentals.loc[fundamentals['ticker'] == ticker, 'display_company_name'].iloc[0]}"
            ),
        )

        company_rows = (
            fundamentals[fundamentals["ticker"] == selected_ticker]
            .sort_values("period_end_date")
            .reset_index(drop=True)
        )
        latest = company_rows.iloc[-1]

        st.markdown(
            f"### {display_company_name(latest['company_name'])} ({selected_ticker})"
        )
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
        st.caption(
            "Revenue growth is blank for the first displayed annual period because "
            "there is no prior annual observation in the selected 5-year window."
        )

        chart_cols = st.columns(3)
        with chart_cols[0]:
            st.subheader("5-Year Revenue Trend")
            st.altair_chart(
                line_chart(company_rows, "revenue", "Revenue", "Revenue ($B)"),
                width="stretch",
            )
        with chart_cols[1]:
            st.subheader("Net Income Trend")
            st.altair_chart(
                line_chart(company_rows, "net_income", "Net Income", "Net Income ($B)"),
                width="stretch",
            )
        with chart_cols[2]:
            st.subheader("Operating Cash Flow Trend")
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
            st.subheader("Revenue Growth Trend")
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
            st.subheader("Net Margin Trend")
            st.altair_chart(
                line_chart(company_rows, "net_margin_pct", "Net Margin", "Net Margin (%)"),
                width="stretch",
            )

        with st.expander("Why these numbers?"):
            st.dataframe(
                latest_provenance_table(latest),
                hide_index=True,
                width="stretch",
            )

        st.download_button(
            "Download company summary CSV",
            data=SUMMARY_PATH.read_bytes(),
            file_name="company_summary.csv",
            mime="text/csv",
        )

    with quality_tab:
        st.subheader("Data Quality & Reliability")
        quality_cols = st.columns(4)
        with quality_cols[0]:
            metric_card("Validated Rows", format_number(selected_counts["PASS"]))
        with quality_cols[1]:
            metric_card("Selected Warnings", format_number(selected_counts["WARN"]))
        with quality_cols[2]:
            metric_card("Selected Failures", format_number(selected_counts["FAIL"]))
        with quality_cols[3]:
            metric_card("Diagnostic Warnings", format_number(diagnostic_warn_count))

        missing_metric_counts = {
            "Missing revenue": int((~fundamentals["has_revenue"].astype(bool)).sum()),
            "Missing net income": int(
                (~fundamentals["has_net_income"].astype(bool)).sum()
            ),
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

        st.subheader("Selected Row Quality Matrix")
        st.dataframe(style_quality_matrix(quality_matrix(fundamentals)), width="stretch")

        st.subheader("Metric Completeness")
        missing_df = pd.DataFrame(
            [
                {"Metric": metric, "Missing selected rows": count}
                for metric, count in missing_metric_counts.items()
            ]
        )
        completeness_cols = st.columns(2)
        with completeness_cols[0]:
            st.dataframe(
                metric_completeness_table(fundamentals),
                hide_index=True,
                width="stretch",
            )
        with completeness_cols[1]:
            st.dataframe(missing_df, hide_index=True, width="stretch")

        st.subheader("Diagnostic Warnings")
        diagnostics_summary = (
            diagnostic_checks.groupby(["status", "check_name"], dropna=False)
            .size()
            .reset_index(name="count")
            .sort_values(["status", "check_name"])
        )
        st.dataframe(diagnostics_summary, hide_index=True, width="stretch")

        with st.expander("Diagnostic check details", expanded=False):
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
