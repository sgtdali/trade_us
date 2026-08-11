"""Typed exception hierarchy for the FX ingestion namespace.

Mirrors ``ingestion.eod.errors``'s bootstrap-vs-domain split exactly:
these are bootstrap/configuration/programmer-invariant failures. Ordinary
domain-invalid provider/economic data is reported as
:class:`~fundamental_pipeline.valuation.validation.findings.Finding`
objects instead, never raised.
"""

from __future__ import annotations


class FxIngestionError(Exception):
    """Base domain error for the FX ingestion namespace."""


class FxBundleIntegrityError(FxIngestionError):
    """A committed FX ingestion bundle is structurally malformed: an
    expected file is missing, a referenced content hash does not match, or
    the bundle-manifest's own file set does not match what is actually
    present under the bundle root."""
