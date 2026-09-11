from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.config import (
    INITIAL_TICKERS,
    LATEST_ANNUAL_PERIODS,
    NET_INCOME_CONCEPTS,
    OPERATING_CASH_FLOW_CONCEPTS,
    RAW_DATA_DIR,
    REVENUE_CONCEPTS,
)
from src.storage import read_json


ANNUAL_DURATION_MIN_DAYS = 300
ANNUAL_DURATION_MAX_DAYS = 430


@dataclass(frozen=True)
class AnnualFact:
    concept: str
    value: float
    start: date
    end: date
    filed: date
    accession: str
    fiscal_period: str | None
    sec_fiscal_year: int | None
    duration_days: int

    @property
    def period_key(self) -> tuple[date, date]:
        return (self.start, self.end)

    @property
    def fiscal_year(self) -> int:
        return self.end.year


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def annual_duration_days(fact: dict[str, Any]) -> int | None:
    start = parse_date(fact.get("start"))
    end = parse_date(fact.get("end"))
    if start is None or end is None:
        return None
    return (end - start).days + 1


def is_plausible_annual_duration(fact: dict[str, Any]) -> bool:
    duration = annual_duration_days(fact)
    if duration is None:
        return False
    return ANNUAL_DURATION_MIN_DAYS <= duration <= ANNUAL_DURATION_MAX_DAYS


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


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _fact_sort_key(fact: AnnualFact) -> tuple[date, str]:
    return (fact.filed, fact.accession)


def select_annual_facts(
    companyfacts: dict[str, Any],
    concept: str,
    ticker: str,
) -> tuple[dict[tuple[date, date], AnnualFact], list[dict[str, Any]]]:
    """Select one deterministic annual USD 10-K fact per reporting period.

    The SEC companyfacts feed includes quarterly facts, comparative prior-year
    facts, amendments, and restatements. This selector filters to plausible
    annual USD 10-K duration facts, prefers fp == FY within a reporting period
    when available, and then chooses the latest filed fact for duplicates.
    Conflicting duplicate values are surfaced as quality events.
    """

    events: list[dict[str, Any]] = []
    gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    concept_node = gaap.get(concept)
    if not concept_node:
        return {}, events

    usd_facts = concept_node.get("units", {}).get("USD", [])
    annual_candidates: list[AnnualFact] = []
    implausible_count = 0

    for fact in usd_facts:
        if fact.get("form") != "10-K":
            continue

        duration = annual_duration_days(fact)
        if duration is None or not is_plausible_annual_duration(fact):
            implausible_count += 1
            continue

        start = parse_date(fact.get("start"))
        end = parse_date(fact.get("end"))
        filed = parse_date(fact.get("filed"))
        value = _coerce_number(fact.get("val"))
        if start is None or end is None or filed is None or value is None:
            continue

        annual_candidates.append(
            AnnualFact(
                concept=concept,
                value=value,
                start=start,
                end=end,
                filed=filed,
                accession=str(fact.get("accn") or ""),
                fiscal_period=fact.get("fp"),
                sec_fiscal_year=fact.get("fy"),
                duration_days=duration,
            )
        )

    if implausible_count:
        events.append(
            quality_event(
                ticker=ticker,
                fiscal_year=None,
                check_name="implausible_annual_duration",
                status="WARN",
                details=(
                    f"{implausible_count} 10-K USD facts for {concept} were excluded "
                    "because their durations were outside 300-430 days or missing."
                ),
            )
        )

    grouped: dict[tuple[date, date], list[AnnualFact]] = {}
    for fact in annual_candidates:
        grouped.setdefault(fact.period_key, []).append(fact)

    selected: dict[tuple[date, date], AnnualFact] = {}
    for period_key, facts in grouped.items():
        fy_facts = [fact for fact in facts if fact.fiscal_period == "FY"]
        facts_to_rank = fy_facts if fy_facts else facts

        values = {fact.value for fact in facts_to_rank}
        if len(values) > 1:
            fiscal_year = period_key[1].year
            events.append(
                quality_event(
                    ticker=ticker,
                    fiscal_year=fiscal_year,
                    check_name="conflicting_duplicate_annual_facts",
                    status="WARN",
                    details=(
                        f"{concept} has {len(values)} distinct values for "
                        f"{period_key[0]} to {period_key[1]}; selected latest filed."
                    ),
                )
            )

        selected[period_key] = sorted(facts_to_rank, key=_fact_sort_key)[-1]

    return selected, events


def choose_prioritized_fact(
    facts_by_concept: dict[str, dict[tuple[date, date], AnnualFact]],
    concepts: tuple[str, ...],
    period_key: tuple[date, date],
) -> AnnualFact | None:
    for concept in concepts:
        fact = facts_by_concept.get(concept, {}).get(period_key)
        if fact is not None:
            return fact
    return None


def transform_companyfacts(
    ticker: str,
    companyfacts: dict[str, Any],
    latest_periods: int = LATEST_ANNUAL_PERIODS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []

    if not isinstance(companyfacts, dict):
        return [], [
            quality_event(ticker, None, "malformed_sec_structure", "FAIL", "Raw SEC JSON is not an object.")
        ]

    facts = companyfacts.get("facts")
    if not isinstance(facts, dict):
        return [], [
            quality_event(ticker, None, "malformed_sec_structure", "FAIL", "Raw SEC JSON is missing facts.")
        ]

    if not isinstance(facts.get("us-gaap"), dict):
        return [], [
            quality_event(ticker, None, "facts_us_gaap_missing", "FAIL", "Raw SEC JSON is missing facts.us-gaap.")
        ]

    company_name = companyfacts.get("entityName") or ""
    cik = str(companyfacts.get("cik") or "").zfill(10)

    metric_concepts = {
        "revenue": REVENUE_CONCEPTS,
        "net_income": NET_INCOME_CONCEPTS,
        "operating_cash_flow": OPERATING_CASH_FLOW_CONCEPTS,
    }
    selected: dict[str, dict[str, dict[tuple[date, date], AnnualFact]]] = {}

    for metric, concepts in metric_concepts.items():
        selected[metric] = {}
        for concept in concepts:
            concept_facts, concept_events = select_annual_facts(companyfacts, concept, ticker)
            selected[metric][concept] = concept_facts
            events.extend(concept_events)

    revenue_periods = sorted(
        {
            period_key
            for concept_facts in selected["revenue"].values()
            for period_key in concept_facts
        },
        key=lambda period: period[1],
        reverse=True,
    )

    if not revenue_periods:
        events.append(
            quality_event(
                ticker,
                None,
                "no_usable_annual_revenue",
                "FAIL",
                "No usable annual revenue fact found after applying SEC/XBRL selection rules.",
            )
        )
        return [], events

    rows: list[dict[str, Any]] = []
    for period_key in revenue_periods[:latest_periods]:
        revenue_fact = choose_prioritized_fact(
            selected["revenue"], REVENUE_CONCEPTS, period_key
        )
        net_income_fact = choose_prioritized_fact(
            selected["net_income"], NET_INCOME_CONCEPTS, period_key
        )
        operating_cash_flow_fact = choose_prioritized_fact(
            selected["operating_cash_flow"], OPERATING_CASH_FLOW_CONCEPTS, period_key
        )

        assert revenue_fact is not None

        rows.append(
            {
                "ticker": ticker,
                "cik": cik,
                "company_name": company_name,
                "fiscal_year": revenue_fact.fiscal_year,
                "period_start_date": revenue_fact.start.isoformat(),
                "period_end_date": revenue_fact.end.isoformat(),
                "filed_date": revenue_fact.filed.isoformat(),
                "revenue": revenue_fact.value,
                "net_income": net_income_fact.value if net_income_fact else None,
                "operating_cash_flow": (
                    operating_cash_flow_fact.value if operating_cash_flow_fact else None
                ),
                "revenue_growth_pct": None,
                "net_margin_pct": None,
                "has_revenue": revenue_fact is not None,
                "has_net_income": net_income_fact is not None,
                "has_operating_cash_flow": operating_cash_flow_fact is not None,
                "quality_status": None,
                "quality_issue_count": None,
                "quality_notes": None,
                "revenue_concept": revenue_fact.concept,
                "net_income_concept": net_income_fact.concept if net_income_fact else None,
                "operating_cash_flow_concept": (
                    operating_cash_flow_fact.concept if operating_cash_flow_fact else None
                ),
            }
        )

    rows.sort(key=lambda row: (row["ticker"], row["period_end_date"]))
    calculate_derived_metrics(rows)
    return rows, events


def calculate_derived_metrics(rows: list[dict[str, Any]]) -> None:
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_ticker.setdefault(row["ticker"], []).append(row)

    for ticker_rows in by_ticker.values():
        ticker_rows.sort(key=lambda row: row["period_end_date"])
        previous: dict[str, Any] | None = None
        for row in ticker_rows:
            revenue = row.get("revenue")
            net_income = row.get("net_income")

            if revenue is not None and revenue > 0 and net_income is not None:
                row["net_margin_pct"] = (net_income / revenue) * 100

            if previous is not None:
                previous_revenue = previous.get("revenue")
                consecutive_year = row["fiscal_year"] == previous["fiscal_year"] + 1
                if (
                    consecutive_year
                    and revenue is not None
                    and previous_revenue is not None
                    and previous_revenue > 0
                ):
                    row["revenue_growth_pct"] = (
                        (revenue / previous_revenue) - 1
                    ) * 100

            previous = row


def transform_raw_files(
    tickers: tuple[str, ...] = INITIAL_TICKERS,
    raw_dir: Path = RAW_DATA_DIR,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    for ticker in tickers:
        raw_path = raw_dir / f"{ticker}_companyfacts.json"
        if not raw_path.exists():
            events.append(
                quality_event(
                    ticker,
                    None,
                    "raw_file_missing",
                    "FAIL",
                    f"Expected raw file was not found: {raw_path}",
                )
            )
            continue

        try:
            companyfacts = read_json(raw_path)
        except (OSError, ValueError) as exc:
            events.append(
                quality_event(
                    ticker,
                    None,
                    "malformed_sec_structure",
                    "FAIL",
                    f"Could not read valid JSON from {raw_path}: {exc}",
                )
            )
            continue

        company_rows, company_events = transform_companyfacts(ticker, companyfacts)
        rows.extend(company_rows)
        events.extend(company_events)

    return rows, events


def build_company_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for ticker in sorted({row["ticker"] for row in rows}):
        ticker_rows = [row for row in rows if row["ticker"] == ticker]
        latest = sorted(ticker_rows, key=lambda row: row["period_end_date"])[-1]
        summary.append(
            {
                "ticker": latest["ticker"],
                "company_name": latest["company_name"],
                "period_end_date": latest["period_end_date"],
                "revenue": latest["revenue"],
                "revenue_growth_pct": latest["revenue_growth_pct"],
                "net_income": latest["net_income"],
                "net_margin_pct": latest["net_margin_pct"],
                "operating_cash_flow": latest["operating_cash_flow"],
                "quality_status": latest["quality_status"],
            }
        )
    return summary
