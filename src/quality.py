from __future__ import annotations

from collections import Counter
from typing import Any


STATUS_RANK = {"PASS": 0, "WARN": 1, "FAIL": 2}


def quality_event(
    ticker: str,
    fiscal_year: int | None,
    check_name: str,
    status: str,
    details: str,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "check_name": check_name,
        "status": status,
        "details": details,
    }


def worst_status(statuses: list[str]) -> str:
    if not statuses:
        return "PASS"
    return max(statuses, key=lambda status: STATUS_RANK[status])


def _format_notes(events: list[dict[str, Any]]) -> str:
    if not events:
        return ""
    return "; ".join(f"{event['check_name']}: {event['details']}" for event in events)


def validate_fundamentals(
    rows: list[dict[str, Any]],
    initial_events: list[dict[str, Any]] | None = None,
    expected_periods: int = 5,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    report: list[dict[str, Any]] = list(initial_events or [])
    row_events: dict[tuple[str, int], list[dict[str, Any]]] = {}

    for event in initial_events or []:
        fiscal_year = event.get("fiscal_year")
        if fiscal_year is None:
            continue
        key = (event["ticker"], int(fiscal_year))
        row_events.setdefault(key, []).append(event)

    counts = Counter((row["ticker"], row["fiscal_year"]) for row in rows)
    for row in rows:
        key = (row["ticker"], row["fiscal_year"])
        if counts[key] > 1:
            event = quality_event(
                row["ticker"],
                row["fiscal_year"],
                "duplicate_ticker_fiscal_year",
                "FAIL",
                "More than one processed row exists for this ticker and fiscal year.",
            )
            report.append(event)
            row_events.setdefault(key, []).append(event)

    rows_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        rows_by_ticker.setdefault(row["ticker"], []).append(row)

    for ticker, ticker_rows in rows_by_ticker.items():
        if len(ticker_rows) < expected_periods:
            report.append(
                quality_event(
                    ticker,
                    None,
                    "fewer_than_expected_annual_periods",
                    "WARN",
                    f"{len(ticker_rows)} annual periods available; expected up to {expected_periods}.",
                )
            )

    for row in rows:
        key = (row["ticker"], row["fiscal_year"])
        events = row_events.setdefault(key, [])

        revenue = row.get("revenue")
        net_income = row.get("net_income")
        operating_cash_flow = row.get("operating_cash_flow")

        if revenue is None:
            event = quality_event(
                row["ticker"],
                row["fiscal_year"],
                "missing_core_metric",
                "FAIL",
                "Revenue is missing; core analysis for this row is not reliable.",
            )
            events.append(event)
            report.append(event)
        elif revenue <= 0:
            event = quality_event(
                row["ticker"],
                row["fiscal_year"],
                "invalid_non_positive_revenue",
                "FAIL",
                f"Revenue must be positive for analysis, found {revenue}.",
            )
            events.append(event)
            report.append(event)

        if net_income is None:
            event = quality_event(
                row["ticker"],
                row["fiscal_year"],
                "missing_core_metric",
                "WARN",
                "Net income is missing.",
            )
            events.append(event)
            report.append(event)

        if operating_cash_flow is None:
            event = quality_event(
                row["ticker"],
                row["fiscal_year"],
                "missing_core_metric",
                "WARN",
                "Operating cash flow is missing.",
            )
            events.append(event)
            report.append(event)

        growth = row.get("revenue_growth_pct")
        if growth is not None and (growth > 300 or growth < -80):
            event = quality_event(
                row["ticker"],
                row["fiscal_year"],
                "extreme_revenue_growth",
                "WARN",
                f"Revenue growth of {growth:.2f}% is outside the expected range.",
            )
            events.append(event)
            report.append(event)

    for row in rows:
        key = (row["ticker"], row["fiscal_year"])
        events = row_events.get(key, [])
        material_events = [event for event in events if event["status"] != "PASS"]
        row["quality_status"] = worst_status([event["status"] for event in material_events])
        row["quality_issue_count"] = len(material_events)
        row["quality_notes"] = _format_notes(material_events)

        report.append(
            quality_event(
                row["ticker"],
                row["fiscal_year"],
                "row_quality_status",
                row["quality_status"],
                row["quality_notes"] or "No material issues.",
            )
        )

    return rows, report


def quality_status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row.get("quality_status") or "UNKNOWN" for row in rows)
    return {status: counts.get(status, 0) for status in ("PASS", "WARN", "FAIL")}
