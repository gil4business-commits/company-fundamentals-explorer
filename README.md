Public Company Fundamentals Explorer
====================================

Project Overview
----------------

Public Company Fundamentals Explorer is a small Python and Streamlit application that extracts public SEC EDGAR company facts, transforms selected annual financial facts into local analytical datasets, validates the outputs, and presents the results in a business-facing dashboard.

The initial coverage is:

- AAPL
- MSFT
- NVDA
- AMZN
- META

The project is designed for a take-home AI Data Engineer assignment. It prioritizes reproducibility, transparent ETL decisions, local file persistence, and clear data-quality reporting over unnecessary infrastructure.

Product Use Case
----------------

The dashboard helps a reviewer quickly understand latest reported annual fundamentals and 5-year trends for selected public companies. It supports:

- latest reported annual results
- company-level revenue, profitability, and operating cash flow trends
- cross-company comparison by selected metric
- traceability from displayed metrics back to selected SEC/XBRL concepts
- data-quality visibility for selected analytical rows and excluded diagnostic SEC facts

The application is descriptive only. It does not provide investment advice, rankings, recommendations, scoring, or forecasts.

Architecture
------------

The project uses a simple local pipeline:

```text
SEC EDGAR public APIs
  -> etl.py extraction
  -> raw JSON files in data/raw/
  -> deterministic transformation and validation
  -> processed CSV files in data/processed/
  -> Streamlit dashboard reads processed CSVs only
```

There is no Docker, no external database, no paid API, and no private credentials.

Repository Structure
--------------------

```text
.
├── app.py
├── etl.py
├── requirements.txt
├── README.md
├── dashboard_screenshot.png
├── ai_transcript/
│   └── README.md
├── data/
│   ├── raw/
│   │   ├── company_tickers.json
│   │   ├── AAPL_companyfacts.json
│   │   ├── MSFT_companyfacts.json
│   │   ├── NVDA_companyfacts.json
│   │   ├── AMZN_companyfacts.json
│   │   ├── META_companyfacts.json
│   │   └── extraction_metadata.json
│   └── processed/
│       ├── company_fundamentals.csv
│       ├── company_summary.csv
│       └── data_quality_report.csv
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── quality.py
│   ├── sec_client.py
│   ├── storage.py
│   └── transform.py
└── tests/
    ├── conftest.py
    ├── test_quality.py
    └── test_transform.py
```

SEC EDGAR Data Source
---------------------

The project uses public SEC EDGAR endpoints that do not require an API key:

- Ticker to CIK mapping:
  `https://www.sec.gov/files/company_tickers.json`
- Company facts:
  `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

The ETL includes a SEC User-Agent header, timeout handling, conservative request pacing, and retry/backoff behavior for transient errors such as HTTP 429 and 5xx responses.

Local Run Instructions
----------------------

```bash
git clone <repository-url>
cd <repository-folder>
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python etl.py
streamlit run app.py
```

ETL and Data Model
------------------

Running `python etl.py` performs:

```text
extract
-> persist raw SEC JSON
-> transform annual facts
-> validate rows and diagnostics
-> save processed analytical CSVs
```

Raw outputs are written to `data/raw/`:

- `company_tickers.json`
- one `*_companyfacts.json` file per configured ticker
- `extraction_metadata.json`

Processed outputs are written to `data/processed/`:

- `company_fundamentals.csv`: one row per company and selected fiscal year
- `company_summary.csv`: one row per company with latest reported annual results
- `data_quality_report.csv`: row-level quality status plus diagnostic checks

The main analytical fields include:

- ticker
- CIK
- company name
- fiscal year
- period start and end dates
- filing date
- revenue
- net income
- operating cash flow
- revenue growth
- net margin
- metric completeness flags
- quality status, issue count, and notes
- selected XBRL concepts for traceability

Metrics
-------

The dashboard and processed data include:

- revenue
- revenue growth
- net income
- net margin
- operating cash flow
- latest reported annual comparison
- 5-year company trends

Revenue uses prioritized XBRL concepts:

1. `RevenueFromContractWithCustomerExcludingAssessedTax`
2. `Revenues`
3. `SalesRevenueNet`

Net income uses:

- `NetIncomeLoss`

Operating cash flow uses:

- `NetCashProvidedByUsedInOperatingActivities`

Revenue growth is calculated only when consecutive annual observations exist and prior revenue is positive. Net margin is calculated only when revenue and net income are available and revenue is positive.

Data Quality and Validation
---------------------------

The ETL applies deterministic annual fact selection rules:

- USD unit only
- `form == "10-K"`
- prefer `fp == "FY"` where available
- require start and end dates
- require plausible annual duration, approximately 300 to 430 days
- exclude quarterly or otherwise non-annual duration facts
- when duplicate annual facts remain for the same reporting period, choose the latest filed fact
- surface conflicting duplicates in diagnostics instead of silently hiding them

Quality fields are transparent:

- `quality_status`: `PASS`, `WARN`, or `FAIL`
- `quality_issue_count`
- `quality_notes`

Checks include:

- missing raw files
- malformed SEC structure
- missing `facts.us-gaap`
- no usable annual revenue
- missing core metrics
- duplicate ticker and fiscal year rows
- invalid or non-positive revenue
- implausible annual duration
- extreme revenue growth
- conflicting duplicate annual facts
- fewer than expected annual periods

The current selected analytical dataset has 25 selected rows, all `PASS`. The quality report also includes diagnostic `WARN` records for historical SEC facts that were excluded during deterministic selection. Those diagnostics are intentionally visible because they demonstrate how the pipeline handles ambiguous, comparative, duplicate, amended, or non-annual SEC/XBRL observations.

Dashboard Functionality
-----------------------

Run the dashboard with:

```bash
streamlit run app.py
```

The app reads only local processed files under `data/processed/`. It does not call the SEC API directly.

The dashboard includes:

- overview metrics
- deterministic executive insights
- selected company detail view
- latest reported annual KPIs
- 5-year trend charts
- a provenance expander explaining which SEC/XBRL concepts support the latest values
- company comparison by selected metric
- latest reported annual comparison table
- data-quality matrix by company and fiscal year
- metric completeness table
- diagnostic quality details
- methodology notes
- CSV download for reviewer inspection

Companies may have different fiscal year-end dates, so cross-company comparisons are described as "latest reported annual results" rather than a single calendar-year comparison.

Testing
-------

Tests use synthetic fixtures and do not call live SEC APIs.

Run:

```bash
pytest
```

Coverage focuses on:

- annual-duration filtering
- duplicate fact resolution
- revenue fallback concept behavior
- revenue growth calculation
- net margin calculation
- duplicate company/year validation
- quality status behavior for missing metrics

Assumptions
-----------

- The five configured tickers are sufficient for the assignment MVP.
- Company facts are retrieved from SEC EDGAR public APIs.
- Annual financial metrics should be based on selected 10-K annual duration facts.
- Fiscal year is derived from the annual period end year for deterministic comparison.
- Raw SEC JSON files are kept in the repository for reproducibility and reviewer inspection.
- The dashboard is a local analytical app, not a production-hosted service.

Known Limitations
-----------------

- SEC XBRL reporting conventions differ across companies and over time.
- Revenue concepts are prioritized but not universally perfect for every possible public company.
- The app covers only five configured companies.
- The pipeline focuses on annual data and does not analyze quarterly trends.
- No external database is used; persistence is local CSV and JSON files.
- No authentication, deployment, scheduled refresh, or incremental loading is included.
- The dashboard is descriptive and does not include forecasting or investment recommendations.

AI Usage
--------

AI assistance was used to help plan, implement, test, and polish this take-home project. AI was used for code generation, debugging, documentation drafting, and iterative product refinement.

The implementation decisions were kept within the assignment constraints:

- no private credentials
- no paid APIs
- no proprietary scoring logic
- no external database
- no LLM calls inside the application
- no investment advice language

The `ai_transcript/` directory documents the transcript status for submission.

What I Would Improve With More Time
-----------------------------------

- Add a small configuration file or CLI flags for choosing tickers.
- Add more companies and industry grouping.
- Persist richer provenance fields such as accession number and source filing URL.
- Add optional incremental refresh to avoid re-downloading unchanged raw data.
- Add more robust concept mapping for additional sectors.
- Add CI to run tests and basic linting on every commit.
- Add a lightweight data dictionary for processed outputs.
- Add more browser-based UI regression checks.
