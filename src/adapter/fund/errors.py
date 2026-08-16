from __future__ import annotations

from ..errors import UsPipelineError


class FundError(UsPipelineError):
    """Base exception for the portfolio decision journal."""


class SchemaViolation(FundError):
    """A document failed its JSON Schema, or a policy pointer resolved nowhere."""


class LedgerError(FundError):
    """A write violated the ledger's rules: duplicate, out-of-order, or immutable."""


class ProjectionError(FundError):
    """The event stream cannot be folded into a coherent position or cash state."""
