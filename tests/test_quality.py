from src.quality import validate_fundamentals


def base_row(**overrides):
    row = {
        "ticker": "TEST",
        "cik": "0000000001",
        "company_name": "Example Corp",
        "fiscal_year": 2023,
        "period_start_date": "2023-01-01",
        "period_end_date": "2023-12-31",
        "filed_date": "2024-02-01",
        "revenue": 100,
        "net_income": 10,
        "operating_cash_flow": 15,
        "revenue_growth_pct": None,
        "net_margin_pct": 10,
        "has_revenue": True,
        "has_net_income": True,
        "has_operating_cash_flow": True,
        "quality_status": None,
        "quality_issue_count": None,
        "quality_notes": None,
    }
    row.update(overrides)
    return row


def test_duplicate_company_year_validation():
    rows = [base_row(), base_row()]

    validated, report = validate_fundamentals(rows)

    assert all(row["quality_status"] == "FAIL" for row in validated)
    assert any(
        event["check_name"] == "duplicate_ticker_fiscal_year"
        and event["status"] == "FAIL"
        for event in report
    )


def test_quality_status_warns_for_missing_non_revenue_metrics():
    rows = [
        base_row(
            net_income=None,
            operating_cash_flow=None,
            has_net_income=False,
            has_operating_cash_flow=False,
        )
    ]

    validated, report = validate_fundamentals(rows)

    assert validated[0]["quality_status"] == "WARN"
    assert validated[0]["quality_issue_count"] == 2
    assert "Net income is missing" in validated[0]["quality_notes"]
    assert "Operating cash flow is missing" in validated[0]["quality_notes"]
    assert any(event["status"] == "WARN" for event in report)
