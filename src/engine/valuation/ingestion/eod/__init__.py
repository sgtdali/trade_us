"""End-of-day market-data ingestion: provider-neutral models, the YFinance
pilot adapter, canonical provider-extract capture, strict normalization,
quality validation/quarantine, and a transactional, replayable run bundle.

See ``docs/yfinance-eod-pilot.md`` for the operational runbook.
"""

from __future__ import annotations
