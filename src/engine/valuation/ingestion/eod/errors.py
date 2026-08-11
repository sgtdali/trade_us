"""Typed exception hierarchy for the EOD ingestion namespace.

These are bootstrap/configuration/programmer-invariant failures. Ordinary
domain-invalid provider/economic data is reported as
:class:`~engine.valuation.validation.findings.Finding` objects
instead, never raised.
"""

from __future__ import annotations


class IngestionError(Exception):
    """Base domain error for the EOD ingestion namespace."""


class ProviderConfigError(IngestionError):
    """The provider configuration file (``config/market-data/providers/
    yfinance.json``) is missing, malformed, or fails structural validation."""


class ProviderBootstrapError(IngestionError):
    """The optional ``market`` dependency group (``yfinance``) is not
    installed, or the provider library could not be imported/initialized.
    Never a raw ``ImportError`` reaching the CLI -- always this typed,
    actionable error instead."""


class RequestConstructionError(IngestionError):
    """An ``EndOfDayFetchRequest`` could not be constructed because one of
    its fixed, non-negotiable economic options was violated (e.g. an
    invalid date range, or an attempt to enable auto-adjust)."""


class BundleIntegrityError(IngestionError):
    """A committed ingestion bundle is structurally malformed: an expected
    file is missing, a referenced content hash does not match, or the
    bundle-manifest's own file set does not match what is actually present
    under the bundle root."""
