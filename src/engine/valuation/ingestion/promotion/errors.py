"""Typed exception hierarchy for the EOD-close promotion bridge.

These are bootstrap/configuration/programmer-invariant failures -- a source
bundle/manifest/policy that cannot be trusted structurally at all, or an
unsafe output path. Ordinary domain-invalid eligibility outcomes (research-
only bundle, expired temporary authorization, quarantined-only rows, no
eligible row within the policy lag, retrieval after cutoff, ...) are
reported as :class:`~engine.valuation.validation.findings.Finding`
objects in a still-written, ``overall_status: "invalid"`` promotion bundle
instead, never raised -- mirroring the sibling EOD ingestion namespace's
own bootstrap-vs-domain split (``ingestion/eod/errors.py``).
"""

from __future__ import annotations


class PromotionError(Exception):
    """Base bootstrap-class error for the EOD-close promotion bridge."""


class PromotionPolicyError(PromotionError):
    """The promotion policy file is missing, malformed, or fails structural
    validation/hash verification."""


class SourceBundleUntrustedError(PromotionError):
    """The source EOD ingestion bundle cannot be trusted structurally: it
    fails ``bundle validate`` or ``bundle replay --check`` drift-free
    re-derivation. Promotion never reads economic data out of a bundle it
    has not first proven byte-for-byte reproducible from its own immutable
    ``provider-extract.json``."""


class PromotionImmutabilityError(PromotionError):
    """The requested ``--output-dir`` already contains a byte-different
    promotion run. A promotion output is immutable once written; rerunning
    with identical inputs against the same directory is a no-op, but
    different inputs must target a new directory, never silently overwrite
    the prior one."""
