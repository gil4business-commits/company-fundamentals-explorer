from pathlib import Path


INITIAL_TICKERS = ("AAPL", "MSFT", "NVDA", "AMZN", "META")

SEC_BASE_URL = "https://www.sec.gov"
SEC_DATA_BASE_URL = "https://data.sec.gov"
COMPANY_TICKERS_URL = f"{SEC_BASE_URL}/files/company_tickers.json"
COMPANY_FACTS_URL_TEMPLATE = (
    f"{SEC_DATA_BASE_URL}/api/xbrl/companyfacts/CIK{{cik}}.json"
)

SEC_USER_AGENT = (
    "PublicCompanyFundamentalsExplorer/0.1 "
    "(AI data engineering take-home; contact: example@example.com)"
)

REQUEST_TIMEOUT_SECONDS = 20
REQUEST_PAUSE_SECONDS = 0.25
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
