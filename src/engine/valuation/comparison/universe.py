"""Immutable model and lifecycle/review verification for an authored
``valuation_peer_universe`` artifact (T74-A;
docs/valuation-t74-02-comparison-schema-policy-universe-specification.md
Sections 10-13, docs/valuation-t67-06-comparison-ranking-policy-catalog.md
Section 6).

Any described lifecycle state is comparison-eligible when the universe's
effective window covers the requested as-of date. Nothing in this module
can approve a universe or add/remove a member -- there is no mutating
function here at all, only parsing and read-only verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from ..errors import ComparisonUniverseLifecycleError

UNIVERSE_LIFECYCLE_STATES = ("draft", "in_review", "approved", "superseded")
COHORT_TIERS = ("primary", "secondary_diagnostic")


@dataclass(frozen=True)
class PeerUniverseMember:
    member_id: str
    ticker: str
    cohort_tier: str
    inclusion_rationale_code: str
    classification_refs: tuple[str, ...]
    effective_from: str
    effective_to: str | None
    applicable_method_family_ids: tuple[str, ...]
    is_subject: bool = False

    def effective_at(self, as_of_date: str) -> bool:
        if as_of_date < self.effective_from:
            return False
        if self.effective_to is not None and as_of_date > self.effective_to:
            return False
        return True


@dataclass(frozen=True)
class PeerUniverse:
    artifact_id: str
    universe_id: str
    universe_version: int
    sector_family: str
    method_family_ids: tuple[str, ...]
    effective_from: str
    effective_to: str | None
    members: tuple[PeerUniverseMember, ...]
    inclusion_policy_ref: str
    review: Mapping[str, Any]
    lifecycle: str
    supersedes_ref: str | None
    raw: Mapping[str, Any]

    def primary_members_at(self, as_of_date: str, *, method_family_id: str, exclude_subject: bool = True) -> tuple[PeerUniverseMember, ...]:
        """The exact primary-cohort candidate list at
        ``as_of_date`` for ``method_family_id`` -- the denominator T67.6's
        ``method_coverage_ratio`` is computed against, subject excluded
        exactly once (T74 invariant 31)."""
        return tuple(
            m for m in self.members
            if m.cohort_tier == "primary"
            and method_family_id in m.applicable_method_family_ids
            and m.effective_at(as_of_date)
            and not (exclude_subject and m.is_subject)
        )


def parse_peer_universe(artifact: Mapping[str, Any]) -> PeerUniverse:
    """Structure an already schema-validated ``valuation_peer_universe``
    JSON object. Assumes the caller has run it through
    ``schemas.iter_schema_errors("valuation-peer-universe", ...)`` first."""
    members = tuple(
        PeerUniverseMember(
            member_id=m["member_id"], ticker=m["ticker"], cohort_tier=m["cohort_tier"],
            inclusion_rationale_code=m["inclusion_rationale_code"], classification_refs=tuple(m["classification_refs"]),
            effective_from=m["effective_from"], effective_to=m.get("effective_to"),
            applicable_method_family_ids=tuple(m["applicable_method_family_ids"]), is_subject=m.get("is_subject", False),
        )
        for m in artifact["members"]
    )
    return PeerUniverse(
        artifact_id=artifact["artifact_id"], universe_id=artifact["universe_id"],
        universe_version=artifact["universe_version"], sector_family=artifact["sector_family"],
        method_family_ids=tuple(artifact["method_family_ids"]), effective_from=artifact["effective_from"],
        effective_to=artifact.get("effective_to"), members=members, inclusion_policy_ref=artifact["inclusion_policy_ref"],
        review=MappingProxyType(dict(artifact["review"])), lifecycle=artifact["lifecycle"],
        supersedes_ref=artifact.get("supersedes_ref"), raw=MappingProxyType(dict(artifact)),
    )


def verify_universe_canonical_eligible(universe: PeerUniverse, *, as_of_date: str) -> None:
    """Raise :class:`~..errors.ComparisonUniverseLifecycleError` when the
    universe's effective window does not cover ``as_of_date``.

    ``lifecycle`` remains descriptive metadata and never gates peer
    comparison generation.
    """
    if as_of_date < universe.effective_from:
        raise ComparisonUniverseLifecycleError(
            f"peer universe {universe.universe_id!r} v{universe.universe_version} is not yet effective at {as_of_date!r} "
            f"(effective_from={universe.effective_from!r})"
        )
    if universe.effective_to is not None and as_of_date > universe.effective_to:
        raise ComparisonUniverseLifecycleError(
            f"peer universe {universe.universe_id!r} v{universe.universe_version} is no longer effective at {as_of_date!r} "
            f"(effective_to={universe.effective_to!r})"
        )
