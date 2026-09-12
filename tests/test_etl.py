import json

from etl import successful_company_tickers
from src.config import (
    NET_INCOME_CONCEPTS,
    OPERATING_CASH_FLOW_CONCEPTS,
    REVENUE_CONCEPTS,
)
from src.transform import transform_raw_files


def annual_fact(value):
    return {
        "val": value,
        "start": "2023-01-01",
        "end": "2023-12-31",
        "filed": "2024-02-01",
        "form": "10-K",
        "fp": "FY",
        "fy": 2023,
        "accn": "test-accession",
    }


def raw_companyfacts(cik, entity_name, revenue):
    return {
        "cik": cik,
        "entityName": entity_name,
        "facts": {
            "us-gaap": {
                REVENUE_CONCEPTS[0]: {"units": {"USD": [annual_fact(revenue)]}},
                NET_INCOME_CONCEPTS[0]: {"units": {"USD": [annual_fact(10)]}},
                OPERATING_CASH_FLOW_CONCEPTS[0]: {"units": {"USD": [annual_fact(15)]}},
            }
        },
    }


def write_raw_companyfacts(raw_dir, ticker, payload):
    path = raw_dir / f"{ticker}_companyfacts.json"
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_failed_current_extraction_is_not_processed_from_stale_raw_file(tmp_path):
    write_raw_companyfacts(tmp_path, "FAILCO", raw_companyfacts(1, "Failed Co", 100))
    write_raw_companyfacts(tmp_path, "OKCO", raw_companyfacts(2, "OK Co", 200))

    metadata = [
        {"ticker": "COMPANY_TICKERS", "status": "SUCCESS"},
        {"ticker": "FAILCO", "status": "FAIL"},
        {"ticker": "OKCO", "status": "SUCCESS"},
    ]

    eligible_tickers = successful_company_tickers(metadata)
    rows, events = transform_raw_files(tickers=eligible_tickers, raw_dir=tmp_path)

    assert eligible_tickers == ("OKCO",)
    assert {row["ticker"] for row in rows} == {"OKCO"}
    assert rows[0]["revenue"] == 200
    assert not [event for event in events if event["ticker"] == "FAILCO"]
