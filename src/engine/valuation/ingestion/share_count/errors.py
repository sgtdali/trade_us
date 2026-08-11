"""Typed exception hierarchy for the share-count/corporate-action promotion
bridge, mirroring ``ingestion/promotion/errors.py``'s bootstrap-vs-domain
split.

These are bootstrap/configuration/programmer-invariant failures. Ordinary
domain-ineligibility outcomes (missing treasury record, non-reconciling
values, insufficient corporate-action coverage, ...) are reported as
:class:`~engine.valuation.validation.findings.Finding`
objects in a still-written, ``overall_status: "invalid"`` promotion bundle
instead, never raised.
"""

from __future__ import annotations


class ShareCountError(Exception):
    """Base bootstrap-class error for the share-count promotion bridge."""


class LedgerError(ShareCountError):
    """The share-count ledger file is missing, malformed, or fails
    structural validation/hash verification."""


class PromotionPolicyError(ShareCountError):
    """The share-count promotion policy file is missing, malformed, or
    fails structural validation/hash verification."""


class PromotionImmutabilityError(ShareCountError):
    """The requested ``--output-dir`` already contains a byte-different
    promotion run. A promotion output is immutable once written; rerunning
    with identical inputs against the same directory is a no-op, but
    different inputs must target a new directory, never silently overwrite
    the prior one."""
