from src.config import (
    NET_INCOME_CONCEPTS,
    OPERATING_CASH_FLOW_CONCEPTS,
    REVENUE_CONCEPTS,
)
from src.transform import (
    calculate_derived_metrics,
    is_plausible_annual_duration,
    select_annual_facts,
    transform_companyfacts,
)


def fact(
    value,
    start="2023-01-01",
    end="2023-12-31",
    filed="2024-02-01",
    concept_form="10-K",
    fp="FY",
):
    return {
        "val": value,
        "start": start,
        "end": end,
        "filed": filed,
        "form": concept_form,
        "fp": fp,
        "fy": int(end[:4]),
        "accn": f"accn-{filed}",
    }


def companyfacts(concept_facts):
    return {
        "cik": 123456,
        "entityName": "Example Corp",
        "facts": {
            "us-gaap": {
                concept: {"units": {"USD": facts}}
                for concept, facts in concept_facts.items()
            }
        },
    }


def test_annual_duration_filtering():
    annual_fact = fact(100)
    quarterly_fact = fact(25, start="2023-10-01", end="2023-12-31")

    assert is_plausible_annual_duration(annual_fact)
    assert not is_plausible_annual_duration(quarterly_fact)

    selected, _ = select_annual_facts(
        companyfacts({"Revenues": [annual_fact, quarterly_fact]}),
        "Revenues",
        "TEST",
    )

    assert len(selected) == 1
    assert next(iter(selected.values())).value == 100


def test_duplicate_fact_resolution_chooses_latest_filed_fact():
    older = fact(100, filed="2024-02-01")
    newer = fact(110, filed="2024-03-01")

    selected, events = select_annual_facts(
        companyfacts({"Revenues": [older, newer]}),
        "Revenues",
        "TEST",
    )

    selected_fact = next(iter(selected.values()))
    assert selected_fact.value == 110
    assert selected_fact.filed.isoformat() == "2024-03-01"
    assert events[0]["check_name"] == "conflicting_duplicate_annual_facts"


def test_revenue_fallback_concept_behavior():
    raw = companyfacts(
        {
            REVENUE_CONCEPTS[1]: [fact(200)],
            NET_INCOME_CONCEPTS[0]: [fact(40)],
            OPERATING_CASH_FLOW_CONCEPTS[0]: [fact(50)],
        }
    )

    rows, events = transform_companyfacts("TEST", raw)

    assert not [event for event in events if event["status"] == "FAIL"]
    assert len(rows) == 1
    assert rows[0]["revenue"] == 200
    assert rows[0]["revenue_concept"] == REVENUE_CONCEPTS[1]


def test_revenue_growth_calculation():
    rows = [
        {"ticker": "TEST", "fiscal_year": 2022, "period_end_date": "2022-12-31", "revenue": 100, "net_income": None},
        {"ticker": "TEST", "fiscal_year": 2023, "period_end_date": "2023-12-31", "revenue": 125, "net_income": None},
    ]

    calculate_derived_metrics(rows)

    assert rows[1]["revenue_growth_pct"] == 25


def test_net_margin_calculation():
    rows = [
        {"ticker": "TEST", "fiscal_year": 2023, "period_end_date": "2023-12-31", "revenue": 200, "net_income": 50},
    ]

    calculate_derived_metrics(rows)

    assert rows[0]["net_margin_pct"] == 25
