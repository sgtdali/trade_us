"""Provider-neutral fetch interface. No implementation in this module ever
imports pandas or yfinance -- both stay isolated to
``providers/yfinance_provider.py``, so the rest of the ingestion subsystem
is fully testable without either installed."""

from __future__ import annotations

from typing import Protocol, Sequence

from ..models import EndOfDayFetchRequest, ProviderSeries


class EndOfDayMarketProvider(Protocol):
    def fetch(self, requests: Sequence[EndOfDayFetchRequest]) -> Sequence[ProviderSeries]:
        """Fetch each request independently. A failure fetching or
        converting one ticker must be isolated into that ticker's own
        ``ProviderSeries(status="failed", ...)`` entry, never raised out of
        this call and never allowed to drop or corrupt another ticker's
        result. Implementations must preserve the input ``requests``
        ordering in the returned sequence."""
        ...
