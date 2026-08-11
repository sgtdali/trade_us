"""Provider-neutral FX ingestion (fetch/capture/normalize/validate/bundle).

Structurally parallel to the sibling ``ingestion.eod`` package, but for FX
pairs rather than equity tickers. Reuses ``ingestion.eod.models`` (
``EndOfDayFetchRequest``/``ProviderRow``/``ProviderSeries``/``FieldValue``)
and ``ingestion.eod.providers.yfinance_provider`` (the network adapter)
unchanged -- this package never duplicates either. ``capture.py``/
``normalize.py``/``validation.py``/``service.py`` are new, FX-specific
modules because the bundle schemas and field semantics genuinely differ
(no OHLC-derivative dividend/split concepts for FX, and the FX bundle's
own schemas -- ``fx-provider-extract``/``fx-rate-series``/
``fx-ingestion-validation``/``fx-ingestion-bundle`` -- are distinct
allowlisted artifacts)."""

from __future__ import annotations
