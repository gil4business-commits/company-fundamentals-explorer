from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.config import (
    COMPANY_FACTS_URL_TEMPLATE,
    COMPANY_TICKERS_URL,
    INITIAL_TICKERS,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
)
from src.quality import quality_status_counts, validate_fundamentals
from src.sec_client import SecClient, SecRequestError
from src.storage import write_csv, write_json
from src.transform import build_company_summary, transform_raw_files


FUNDAMENTALS_FIELDS = [
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
]

SUMMARY_FIELDS = [
    "ticker",
    "company_name",
    "period_end_date",
    "revenue",
    "revenue_growth_pct",
    "net_income",
    "net_margin_pct",
    "operating_cash_flow",
    "quality_status",
]

QUALITY_REPORT_FIELDS = [
    "ticker",
    "fiscal_year",
    "check_name",
    "status",
    "details",
]

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cik_10_digits(cik: int | str) -> str:
    return str(cik).zfill(10)


def load_ticker_mapping(company_tickers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for company in company_tickers.values():
        ticker = str(company["ticker"]).upper()
        mapping[ticker] = company
    return mapping


def metadata_record(
    ticker: str,
    cik: str | None,
    source_url: str,
    status: str,
    error_message: str | None = None,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "cik": cik,
        "source_url": source_url,
        "fetched_at_utc": utc_now_iso(),
        "status": status,
        "error_message": error_message,
    }


def extract() -> list[dict[str, Any]]:
    client = SecClient()
    metadata: list[dict[str, Any]] = []

    try:
        company_tickers = client.get_json(COMPANY_TICKERS_URL)
    except SecRequestError as exc:
        metadata.append(
            metadata_record(
                ticker="COMPANY_TICKERS",
                cik=None,
                source_url=COMPANY_TICKERS_URL,
                status="FAIL",
                error_message=str(exc),
            )
        )
        write_json(RAW_DATA_DIR / "extraction_metadata.json", metadata)
        raise RuntimeError("Failed to retrieve SEC company ticker mapping.") from exc

    write_json(RAW_DATA_DIR / "company_tickers.json", company_tickers)
    metadata.append(
        metadata_record(
            ticker="COMPANY_TICKERS",
            cik=None,
            source_url=COMPANY_TICKERS_URL,
            status="SUCCESS",
        )
    )

    ticker_mapping = load_ticker_mapping(company_tickers)

    for ticker in INITIAL_TICKERS:
        company = ticker_mapping.get(ticker)
        if company is None:
            metadata.append(
                metadata_record(
                    ticker=ticker,
                    cik=None,
                    source_url=COMPANY_TICKERS_URL,
                    status="FAIL",
                    error_message="Ticker was not found in SEC company_tickers.json.",
                )
            )
            continue

        cik = cik_10_digits(company["cik_str"])
        source_url = COMPANY_FACTS_URL_TEMPLATE.format(cik=cik)

        try:
            companyfacts = client.get_json(source_url)
        except SecRequestError as exc:
            metadata.append(
                metadata_record(
                    ticker=ticker,
                    cik=cik,
                    source_url=source_url,
                    status="FAIL",
                    error_message=str(exc),
                )
            )
            continue

        write_json(RAW_DATA_DIR / f"{ticker}_companyfacts.json", companyfacts)
        metadata.append(
            metadata_record(
                ticker=ticker,
                cik=cik,
                source_url=source_url,
                status="SUCCESS",
            )
        )

    write_json(RAW_DATA_DIR / "extraction_metadata.json", metadata)
    return metadata


def log_summary(metadata: list[dict[str, Any]]) -> None:
    company_records = [
        record for record in metadata if record["ticker"] != "COMPANY_TICKERS"
    ]
    successes = [record for record in company_records if record["status"] == "SUCCESS"]
    failures = [record for record in company_records if record["status"] != "SUCCESS"]

    LOGGER.info("Extraction complete.")
    LOGGER.info("Ticker mapping: %s", metadata[0]["status"])
    LOGGER.info("Companyfacts successes: %s", len(successes))
    LOGGER.info("Companyfacts failures: %s", len(failures))

    if successes:
        LOGGER.info("Succeeded: %s", ", ".join(record["ticker"] for record in successes))
    if failures:
        LOGGER.info("Failed:")
        for record in failures:
            LOGGER.info("- %s: %s", record["ticker"], record["error_message"])


def successful_company_tickers(metadata: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(
        record["ticker"]
        for record in metadata
        if record["ticker"] != "COMPANY_TICKERS" and record["status"] == "SUCCESS"
    )


def save_processed_outputs(
    rows: list[dict[str, Any]],
    company_summary: list[dict[str, Any]],
    quality_report: list[dict[str, Any]],
) -> dict[str, str]:
    fundamentals_path = PROCESSED_DATA_DIR / "company_fundamentals.csv"
    summary_path = PROCESSED_DATA_DIR / "company_summary.csv"
    quality_path = PROCESSED_DATA_DIR / "data_quality_report.csv"

    write_csv(fundamentals_path, rows, FUNDAMENTALS_FIELDS)
    write_csv(summary_path, company_summary, SUMMARY_FIELDS)
    write_csv(quality_path, quality_report, QUALITY_REPORT_FIELDS)

    return {
        "company_fundamentals": str(fundamentals_path),
        "company_summary": str(summary_path),
        "data_quality_report": str(quality_path),
    }


def log_etl_summary(
    metadata: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    output_paths: dict[str, str],
) -> None:
    company_records = [
        record for record in metadata if record["ticker"] != "COMPANY_TICKERS"
    ]
    successes = [record for record in company_records if record["status"] == "SUCCESS"]
    failures = [record for record in company_records if record["status"] != "SUCCESS"]
    companies = sorted({row["ticker"] for row in rows})
    quality_counts = quality_status_counts(rows)

    LOGGER.info("ETL complete.")
    LOGGER.info("Extraction successes: %s", len(successes))
    LOGGER.info("Extraction failures: %s", len(failures))
    LOGGER.info("Processed rows: %s", len(rows))
    LOGGER.info("Companies represented: %s", ", ".join(companies) if companies else "None")
    LOGGER.info(
        "Quality counts: "
        f"PASS={quality_counts['PASS']}, "
        f"WARN={quality_counts['WARN']}, "
        f"FAIL={quality_counts['FAIL']}"
    )
    LOGGER.info("Outputs:")
    for name, path in output_paths.items():
        LOGGER.info("- %s: %s", name, path)


def main() -> None:
    metadata = extract()
    eligible_tickers = successful_company_tickers(metadata)
    rows, selection_events = transform_raw_files(tickers=eligible_tickers)
    validated_rows, quality_report = validate_fundamentals(rows, selection_events)
    company_summary = build_company_summary(validated_rows)
    output_paths = save_processed_outputs(
        validated_rows,
        company_summary,
        quality_report,
    )
    log_etl_summary(metadata, validated_rows, output_paths)


if __name__ == "__main__":
    configure_logging()
    main()
