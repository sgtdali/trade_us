from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable, Mapping

from .errors import SecRequestError


@dataclass
class SecClient:
    user_agent: str
    timeout_seconds: float = 40.0
    max_attempts: int = 3
    min_interval_seconds: float = 0.12
    sleep: Callable[[float], None] = time.sleep
    transport: Callable[[str, Mapping[str, str], float], bytes] | None = None
    _last_request_at: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.user_agent.strip():
            raise ValueError("SEC User-Agent must be non-empty")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")

    def get_json(self, url: str) -> dict:
        raw = self.get_bytes(url)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SecRequestError(f"SEC response was not valid UTF-8 JSON: {url}") from exc
        if not isinstance(value, dict):
            raise SecRequestError(f"SEC JSON root must be an object: {url}")
        return value

    def get_bytes(self, url: str) -> bytes:
        if not url.startswith(("https://www.sec.gov/", "https://data.sec.gov/")):
            raise SecRequestError(f"refusing non-SEC URL: {url}")

        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            self._throttle()
            headers = {
                "User-Agent": self.user_agent,
                "Accept-Encoding": "identity",
                "Accept": "application/json, application/zip, text/html, application/xml;q=0.9, */*;q=0.1",
            }
            try:
                payload = (
                    self.transport(url, headers, self.timeout_seconds)
                    if self.transport is not None
                    else _stdlib_transport(url, headers, self.timeout_seconds)
                )
                self._last_request_at = time.monotonic()
                return payload
            except Exception as exc:  # transport boundary; classified by status below
                self._last_request_at = time.monotonic()
                last_error = exc
                status = getattr(exc, "code", None)
                if status is not None and status not in (429, 500, 502, 503, 504):
                    break
                if attempt < self.max_attempts:
                    self.sleep(min(2 ** (attempt - 1), 4))

        raise SecRequestError(f"SEC request failed after {self.max_attempts} attempt(s): {url}") from last_error

    def _throttle(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            self.sleep(remaining)


def _stdlib_transport(url: str, headers: Mapping[str, str], timeout: float) -> bytes:
    # Lazy import keeps the offline valuation/test process free of network
    # client modules unless a real SEC request is actually executed.
    import urllib.request

    request = urllib.request.Request(url, headers=dict(headers))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()
