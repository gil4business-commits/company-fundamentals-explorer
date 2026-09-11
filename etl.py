from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.config import (
    COMPANY_FACTS_URL_TEMPLATE,
    COMPANY_TICKERS_URL,
    INITIAL_TICKERS,
    RAW_DATA_DIR,
)
from src.sec_client import SecClient, SecRequestError
from src.storage import write_json


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


def print_summary(metadata: list[dict[str, Any]]) -> None:
    company_records = [
        record for record in metadata if record["ticker"] != "COMPANY_TICKERS"
    ]
    successes = [record for record in company_records if record["status"] == "SUCCESS"]
    failures = [record for record in company_records if record["status"] != "SUCCESS"]

    print("Extraction complete.")
    print(f"Ticker mapping: {metadata[0]['status']}")
    print(f"Companyfacts successes: {len(successes)}")
    print(f"Companyfacts failures: {len(failures)}")

    if successes:
        print("Succeeded:", ", ".join(record["ticker"] for record in successes))
    if failures:
        print("Failed:")
        for record in failures:
            print(f"- {record['ticker']}: {record['error_message']}")


def main() -> None:
    metadata = extract()
    print_summary(metadata)


if __name__ == "__main__":
    main()
