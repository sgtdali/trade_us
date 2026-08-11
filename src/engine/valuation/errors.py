"""Typed exception hierarchy for the valuation namespace.

These are bootstrap/configuration/programming-invariant failures. Ordinary
parseable artifact/catalog/schema contract violations are reported as
collected :class:`~engine.valuation.validation.findings.Finding`
objects instead, never raised as exceptions.
"""

from __future__ import annotations


class ValuationError(Exception):
    """Base domain error for the valuation namespace."""


class CanonicalizationError(ValuationError):
    """A value could not be turned into canonical bytes/text (binary float,
    NaN/infinity, negative zero, invalid decimal string, duplicate key after
    normalization, or another canonical-byte-contract violation)."""


class IdentityError(ValuationError):
    """A context ID, artifact ID, or dependency hash could not be derived
    from its declared dimensions."""


class ArtifactReferenceError(ValuationError):
    """An exact artifact reference failed verification (type, ID, hash, or
    relative path mismatch) or a relative path failed the safety check."""


class SchemaError(ValuationError):
    """A schema resource is missing, unknown, fails its own meta-schema, or
    a `$ref` could not be resolved offline against the allowlisted registry."""


class CatalogError(ValuationError):
    """A catalog, the catalog manifest, or the version lock is missing,
    malformed, or fails identity/hash/membership verification."""


class ResourceLimitError(ValuationError):
    """A configured, named resource bound (byte size, nesting depth, object
    member count, array length) was exceeded while parsing untrusted JSON."""


class DuplicateKeyError(ValuationError):
    """A JSON object contained a duplicate raw key, or two keys that collide
    after NFC normalization."""


class BootstrapError(ValuationError):
    """The valuation CLI or a registry could not initialize (unreadable
    required resource, unsupported invocation, invariant-breaking
    configuration)."""


class FinancialBasisError(ValuationError):
    """A public FinancialBasis boundary invariant was violated."""


class MarketResolutionError(ValuationError):
    """The market resolver or its service adapter could not proceed at all
    (bootstrap/programmer-invariant failure) -- ordinary domain-invalid
    evidence is reported as findings instead, never raised."""


class TransactionError(ValuationError):
    """A multi-file governed-root write failed during staging or promotion
    and was rolled back to its pre-call state."""


class RollbackError(TransactionError):
    """A multi-file governed-root write failed AND the rollback itself
    could not fully restore one or more targets. The exception message
    names every path that could not be restored."""


class MethodCatalogError(ValuationError):
    """A ``valuation.formulas.methods`` catalog entry is missing a required
    meta-contract field, references an unknown economic family, arithmetic
    context, or display policy, or otherwise fails method-catalog-level
    structural verification (distinct from :class:`FormulaCompileError`,
    which is specifically the AST/guard/unit compilation of one entry)."""


class FormulaCompileError(ValuationError):
    """One method-formula catalog entry could not be safely compiled: an
    unknown or dynamic AST node, excessive AST depth/node count, an
    undeclared or unused operand symbol, an unguarded division, or a unit
    equation that does not match the declared operand/output units."""


class UnitCompatibilityError(ValuationError):
    """A compiled method formula's declared unit equation is internally
    inconsistent (operand unit families do not compose into the declared
    output unit)."""


class ApplicabilityError(ValuationError):
    """No policy resolves a method set/row for a given company selector,
    or a configured row references an unknown applicability policy --
    always fail-closed, never a generic heuristic fallback."""


class OperandBindingError(ValuationError):
    """A structural (programmer/catalog) failure while binding a compiled
    plan's operands against a ``valuation-inputs`` artifact -- distinct
    from an ordinary missing/unavailable operand, which becomes a bound
    operand with a non-``available`` status instead of raising."""


class MethodEvaluationError(ValuationError):
    """A structural failure while evaluating a compiled method plan against
    its bound operands (e.g. an internal invariant violated by a
    corrupted plan) -- distinct from an ordinary guard failure or
    division-by-zero, which become a method status, never an exception."""


class ComparisonPolicyCompileError(ValuationError):
    """One comparison/diagnostic policy entry could not be safely
    compiled: an unknown operator/direction/eligibility-state ID, a gate
    table that is not total, or an excessive rule/operand count. The
    closed policy grammar compiler produces no partial or best-effort
    plan (same discipline as :class:`AssessmentPolicyCompileError`)."""


class ComparisonStatisticsError(ValuationError):
    """A structural precondition of an exact statistics primitive
    (:mod:`~.comparison.statistics`) was violated by its caller -- an
    empty sample, an out-of-range probability, or an unrankable
    direction passed to a rank-only function. Never raised for an
    ordinary insufficient-data economic outcome, which is instead a
    first-class ``excluded_insufficient_data``/``provisional`` result."""


class ComparisonUniverseLifecycleError(ValuationError):
    """An authored peer-universe state is not ``draft``/``in_review``/
    ``approved``/``superseded``, or a canonical comparison attempted to
    use a universe whose lifecycle is not ``approved`` at the requested
    as-of date."""

