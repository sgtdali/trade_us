"""Typed exception hierarchy for the FX-close promotion bridge.

Mirrors ``ingestion.promotion.errors``'s bootstrap-vs-domain split exactly
(see that module's docstring). Ordinary domain-invalid eligibility
outcomes are reported as
:class:`~engine.valuation.validation.findings.Finding`
objects in a still-written, ``overall_status: "invalid"`` promotion
bundle instead, never raised.
"""

from __future__ import annotations


class FxPromotionError(Exception):
    """Base bootstrap-class error for the FX-close promotion bridge."""


class FxPromotionPolicyError(FxPromotionError):
    """The FX promotion policy file is missing, malformed, or fails
    structural validation/hash verification."""


class FxSourceBundleUntrustedError(FxPromotionError):
    """The source FX ingestion bundle cannot be trusted structurally: it
    fails ``fx-bundle validate`` or ``fx-bundle replay --check`` drift-free
    re-derivation."""


class FxPromotionImmutabilityError(FxPromotionError):
    """The requested ``--output-dir`` already contains a byte-different
    promotion run. An FX promotion output is immutable once written."""
