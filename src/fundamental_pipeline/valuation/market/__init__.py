"""Offline market observation/manifest boundary, pure resolver, and
service adapter (T70-B, docs/valuation-t70-04-market-registry-snapshot-specification.md).

No module in this package performs network access or reads provider
credentials. Evidence is always injected locally: an approved
``market-source-manifest`` document plus a closed, in-memory bundle of
:class:`~fundamental_pipeline.valuation.market.observations.MarketObservation`
records.
"""
