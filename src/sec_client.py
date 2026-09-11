import time
from typing import Any

import requests

from src.config import (
    MAX_RETRIES,
    REQUEST_PAUSE_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    RETRY_BACKOFF_SECONDS,
    RETRYABLE_STATUS_CODES,
    SEC_USER_AGENT,
)


class SecRequestError(RuntimeError):
    """Raised when a SEC request fails after retries."""


class SecClient:
    def __init__(
        self,
        user_agent: str = SEC_USER_AGENT,
        timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
        pause_seconds: float = REQUEST_PAUSE_SECONDS,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json",
            }
        )
        self.timeout_seconds = timeout_seconds
        self.pause_seconds = pause_seconds
        self.max_retries = max_retries

    def get_json(self, url: str) -> Any:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            if attempt > 1:
                time.sleep(RETRY_BACKOFF_SECONDS * (2 ** (attempt - 2)))

            time.sleep(self.pause_seconds)

            try:
                response = self.session.get(url, timeout=self.timeout_seconds)
            except requests.RequestException as exc:
                last_error = exc
                continue

            if response.status_code in RETRYABLE_STATUS_CODES:
                last_error = SecRequestError(
                    f"SEC request returned retryable status "
                    f"{response.status_code} for {url}"
                )
                continue

            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                raise SecRequestError(
                    f"SEC request failed with status {response.status_code} for {url}"
                ) from exc

            try:
                return response.json()
            except ValueError as exc:
                raise SecRequestError(f"SEC response was not valid JSON for {url}") from exc

        raise SecRequestError(f"SEC request failed after retries for {url}") from last_error
