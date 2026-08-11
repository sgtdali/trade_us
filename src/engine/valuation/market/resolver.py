"""Pure, side-effect-free offline market snapshot resolver
(docs/valuation-t70-04-market-registry-snapshot-specification.md).

:func:`resolve_market_snapshot` performs no file I/O, no network access,
and reads no environment variable or process clock -- every timestamp it
reasons about (cutoff, as-of, observation timestamps) is caller-supplied
data. Given the same request twice, it returns byte-for-byte identical
results (deterministic sort keys everywhere; no ``dict``/``set`` iteration
order ever reaches the output).

Deliberate T70-B scope simplifications (documented, not silently assumed):

* Freshness classification approximates T04's session-lag thresholds
  (docs/valuation-t04-freshness-staleness-contract.md Section 3.1) using
  weekday lag between an observation's effective date and the as-of date.
  Weekends therefore do not make a Friday close stale on Sunday. Exchange
  holidays are not modeled because no trading-session calendar authority is
  in scope. The threshold boundaries (0/1/2-3/>=4 -> fresh/acceptable/
  stale/expired) are applied unchanged.
* ``corporate_action_state`` defaults to ``coverage_status: "unknown"`` and
  an empty ``events`` array, because the closed T70-B observation
  transport contract (``observations.py``) does not model a
  corporate-action observation type -- an explicit, visible "we do not
  know" rather than a false claim of completeness. A caller may instead
  supply a governed :class:`~.corporate_actions.CorporateActionBundle` via
  ``MarketResolutionRequest.corporate_action_bundle`` (e.g. produced by
  ``engine.valuation.ingestion.share_count``'s promotion
  engine); when present, its cutoff-eligible, as-of-effective, non-withdrawn
  events and its own
  ``coverage_status`` populate this field instead, and a
  ``current_valuation``-purpose snapshot is blocked
  (``freshness_summary.current_use_state: "blocked"``, ``VAL-MI-010``)
  whenever that coverage is not ``"complete"``. Absent a supplied bundle,
  behavior is byte-for-byte identical to before this bundle existed.
* ``capital_claim_observations`` is omitted (schema-optional) for the same
  reason -- no capital-claim observation type is modeled in T70-B.
* Authority ranking across independent sources (docs/valuation-t05-price-basis-contract.md
  Section 11.1, docs/valuation-t08-market-data-provenance-contract.md
  Section 2) is a fixed, explicit, code-owned ordering -- never inferred
  from JSON Schema enum declaration order.
* T68.3 ``VAL-MI-004`` ("same effective adjustment basis; no split
  mismatch") is not checked: ``price_observation.adjustment_basis`` is
  always the literal ``"unadjusted"`` and no corporate-action/split
  observation type exists in T70-B's closed transport contract (see
  ``corporate_action_state`` above), so there is no second adjustment
  basis for a genuine mismatch to ever arise against. This is the same
  honest "not yet modeled" gap as ``corporate_action_state``, not a
  silently skipped check -- implementing it would require inventing a
  corporate-action model this PR does not have grounds to invent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping, Sequence

from ..basis.capital import Operand, evaluate_formula
from ..canonical import normalize_decimal
from ..catalogs import CatalogRegistry
from ..identity import PRICE_MODE_PURPOSES
from ..validation.findings import Finding
from .corporate_actions import CorporateActionBundle
from .observations import MarketObservation, PRICE_MODES

#: Explicit, code-owned authority ranking (lower rank number = higher
#: authority). Source: docs/valuation-t05-price-basis-contract.md Section
#: 11.1 and docs/valuation-t08-market-data-provenance-contract.md Section 2
#: -- this is transcribed from that prose, never derived from the JSON
#: Schema enum array order (which the T70-B prompt explicitly forbids).
AUTHORITY_RANK: Mapping[str, int] = {
    "primary_official": 0,
    "regulated_market": 1,
    "governed_benchmark": 2,
    "issuer_official": 3,
    "licensed_vendor": 4,
    "secondary_reference": 5,
    "manual_exception": 6,
}

_SESSION_LAG_FRESHNESS = (
    (0, "fresh"),
    (1, "acceptable"),
    (3, "stale"),
)  # anything above the last bound is "expired"


def _instant_key(instant: str) -> str:
    """Zero-pad the fractional-second component of a UTC instant so plain
    string comparison is always chronologically correct, regardless of how
    many fractional digits (0-6) the source used."""
    body = instant[:-1]  # strip trailing 'Z'
    if "." in body:
        whole, frac = body.split(".", 1)
    else:
        whole, frac = body, ""
    return f"{whole}.{frac.ljust(6, '0')}Z"


def _date_of(instant_or_date: str) -> str:
    return instant_or_date[:10]


def _weekday_lag(later: str, earlier: str) -> int:
    from datetime import date, timedelta

    y1, m1, d1 = (int(p) for p in later.split("-"))
    y2, m2, d2 = (int(p) for p in earlier.split("-"))
    later_date = date(y1, m1, d1)
    earlier_date = date(y2, m2, d2)
    if later_date < earlier_date:
        return -1
    lag = 0
    cursor = earlier_date + timedelta(days=1)
    while cursor <= later_date:
        if cursor.weekday() < 5:
            lag += 1
        cursor += timedelta(days=1)
    return lag


def _freshness_class(effective_date: str, as_of_date: str) -> str:
    lag = _weekday_lag(as_of_date, effective_date)
    if lag < 0:
        return "unknown"
    for bound, label in _SESSION_LAG_FRESHNESS:
        if lag <= bound:
            return label
    return "expired"


def _is_cutoff_eligible(observation: MarketObservation, cutoff_instant: str, as_of_date: str) -> bool:
    """An observation is eligible only if it was actually known by cutoff
    (published/available) AND its own effective date is not in the future
    relative to ``as_of_date`` -- docs/valuation-t05-price-basis-contract.md
    Section 7: "Official close yayımlanmadan session başında veya session
    içinde gelecekte oluşacak close kullanılamaz." Without this check, a
    same-manifest observation whose ``effective_at`` postdates the
    snapshot's own as-of date could otherwise pass cutoff eligibility
    purely because it happened to be published/available early."""
    cutoff_key = _instant_key(cutoff_instant)
    if _instant_key(observation.published_at) > cutoff_key:
        return False
    if _instant_key(observation.available_at) > cutoff_key:
        return False
    if _date_of(observation.effective_at) > as_of_date:
        return False
    return True


def _is_superseded(observation: MarketObservation, all_observations: Sequence[MarketObservation], cutoff_instant: str, as_of_date: str) -> bool:
    """True when some other eligible-at-cutoff observation supersedes this
    one's revision. A superseding revision that is itself not yet eligible
    at cutoff never displaces the earlier, still-eligible revision."""
    if not observation.revision_id:
        return False
    for other in all_observations:
        if other.supersedes_revision_id == observation.revision_id and _is_cutoff_eligible(other, cutoff_instant, as_of_date):
            return True
    return False


def _eligible_pool(observations: Sequence[MarketObservation], *, observation_type: str, cutoff_instant: str, as_of_date: str) -> list[MarketObservation]:
    pool = [o for o in observations if o.observation_type == observation_type]
    pool = [o for o in pool if o.revision_status != "withdrawn"]
    pool = [o for o in pool if _is_cutoff_eligible(o, cutoff_instant, as_of_date)]
    pool = [o for o in pool if not _is_superseded(o, observations, cutoff_instant, as_of_date)]
    return pool


@dataclass(frozen=True)
class MarketResolutionRequest:
    """``manifest``/``manifest_reference`` are the primary (and, in the
    common single-source case, only) market-source manifest. Independent
    additional sources -- e.g. a ``primary_official`` exchange feed and a
    ``licensed_vendor`` cross-check -- are supplied via
    ``additional_manifests``/``additional_manifest_references`` (paired by
    position) so authority-first comparison can rank observations across
    genuinely different sources rather than only within one
    (docs/valuation-t05-price-basis-contract.md Section 11.1,
    docs/valuation-t08-market-data-provenance-contract.md Section 2)."""

    ticker: str
    instrument_id: str
    instrument_type: str
    trading_currency: str
    as_of_date: str
    cutoff_instant: str
    context_id: str
    manifest: Mapping[str, Any]
    manifest_reference: Mapping[str, str]
    observations: tuple[MarketObservation, ...]
    catalog_registry: CatalogRegistry
    purpose: str = "current_valuation"
    primary_price_mode: str = "official_close"
    #: Optional FX-mode constraint for the FX pass-through (docs/valuation-
    #: t07-currency-fx-contract.md Section 4). When ``None`` (the default),
    #: FX pass-through and the emitted snapshot's ``fx_observations`` are
    #: byte-for-byte identical to prior behavior -- no ``fx_mode``
    #: filtering is applied and no ``fx_mode`` field is emitted. When set,
    #: only eligible FX observations whose own ``fx_mode`` matches are
    #: passed through, and each emitted fx_observations entry carries its
    #: ``fx_mode``.
    primary_fx_mode: str | None = None
    additional_manifests: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    additional_manifest_references: tuple[Mapping[str, str], ...] = field(default_factory=tuple)
    #: Zero or more governed manual override records (docs/valuation-t70-04-
    #: market-registry-snapshot-specification.md Section 11), each
    #: conforming to schemas/market-snapshot.schema.json's
    #: ``governedOverride`` definition. Only consumed when normal source
    #: resolution leaves an unresolved conflict on a matching
    #: ``target_dimension`` -- an override is never applied when normal
    #: sources already resolved the value.
    overrides: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    #: A governed corporate-action bundle (schemas/corporate-action-
    #: bundle.schema.json), already parsed via
    #: :func:`~.corporate_actions.parse_corporate_action_bundle`. Optional
    #: -- when absent, ``corporate_action_state`` keeps its prior
    #: byte-for-byte default (``events: []``, ``coverage_status:
    #: "unknown"``).
    corporate_action_bundle: CorporateActionBundle | None = None

    def manifests_by_id(self) -> dict[str, Mapping[str, Any]]:
        result: dict[str, Mapping[str, Any]] = {self.manifest.get("manifest_id"): self.manifest}
        for m in self.additional_manifests:
            result[m.get("manifest_id")] = m
        return result

    def manifest_ref_by_manifest_id(self) -> dict[str, Mapping[str, str]]:
        result: dict[str, Mapping[str, str]] = {self.manifest.get("manifest_id"): self.manifest_reference}
        for m, ref in zip(self.additional_manifests, self.additional_manifest_references):
            result[m.get("manifest_id")] = ref
        return result


def _mode_purpose_finding(request: MarketResolutionRequest) -> Finding | None:
    if request.primary_price_mode not in PRICE_MODES:
        return Finding(
            rule_id="VAL-MI-003", severity="blocker", scope="artifact",
            reason_code="identity.schema_violation",
            message=f"primary_price_mode must be one of {PRICE_MODES}, got {request.primary_price_mode!r}",
        )
    allowed = PRICE_MODE_PURPOSES[request.primary_price_mode]
    if request.purpose not in allowed:
        return Finding(
            rule_id="VAL-MI-003", severity="blocker", scope="artifact",
            reason_code="capital.price_purpose_mismatch",
            message=f"primary_price_mode {request.primary_price_mode!r} is not compatible with purpose {request.purpose!r}",
        )
    return None

@dataclass(frozen=True)
class MarketResolutionResult:
    snapshot: Mapping[str, Any] | None
    findings: tuple[Finding, ...] = field(default_factory=tuple)


def _conflict_entry(conflict_id: str, field_path: str, candidates: Sequence[MarketObservation], *, selected: MarketObservation | None, resolution_status: str, rationale_code: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "conflict_id": conflict_id,
        "field_path": field_path,
        "candidate_observation_refs": sorted(c.observation_id for c in candidates),
        "materiality": "blocking" if resolution_status.startswith("unresolved") else "diagnostic",
        "resolution_status": resolution_status,
        "rationale_code": rationale_code,
    }
    entry["selected_ref"] = selected.observation_id if selected is not None else None
    return entry


def _authority_rank_for(observation: MarketObservation, manifests_by_id: Mapping[str, Mapping[str, Any]]) -> int:
    """Authority rank of the specific manifest that sourced ``observation``
    -- computed per-observation, never from one single request-wide
    manifest, so that two genuinely independent sources (e.g. a
    ``primary_official`` exchange feed vs. a ``licensed_vendor``
    cross-check) can actually be compared authority-first against each
    other rather than each silently inheriting a shared rank."""
    source_manifest = manifests_by_id.get(observation.source_manifest_id, {})
    return AUTHORITY_RANK.get(source_manifest.get("source_authority", {}).get("authority_class"), 99)


def _select_best_price(
    candidates: list[MarketObservation], manifests_by_id: Mapping[str, Mapping[str, Any]], as_of_date: str, primary_price_mode: str,
) -> tuple[MarketObservation | None, list[MarketObservation], dict[str, Any] | None]:
    """Returns ``(selected, tied_candidates, conflict_or_None)``. Selection
    order: same-session official_close -> nearest prior official_close ->
    any other eligible mode, each level tie-broken by authority rank
    (computed per-observation from its own source manifest), then *most
    recent* effective_at, then most recent publication, then
    observation_id. No averaging ever occurs.

    Revision recency is handled upstream by ``_eligible_pool``'s
    supersession filtering (a later revision that explicitly supersedes an
    earlier one via ``supersedes_revision_id`` excludes the earlier one
    from the pool entirely) -- ``revision_id`` itself is an opaque
    identifier, not a sortable sequence number, so it is never used as a
    tie-break key here.
    """
    if not candidates:
        return None, [], None

    candidates = [o for o in candidates if o.price_mode == primary_price_mode]
    if not candidates:
        return None, [], None

    same_session = [o for o in candidates if o.observation_type == "price" and _date_of(o.effective_at) == as_of_date]
    prior_session = [o for o in candidates if o.observation_type == "price" and _date_of(o.effective_at) < as_of_date]

    for pool in (same_session, prior_session, candidates):
        if not pool:
            continue
        if pool is prior_session:
            latest_date = max(_date_of(o.effective_at) for o in pool)
            pool = [o for o in pool if _date_of(o.effective_at) == latest_date]
        # Sorted least-significant-key-first (stable sort) so the final,
        # most-significant ordering is: authority_rank ascending (lower
        # rank = higher authority), then effective_at descending (most
        # recent evidence wins over an earlier same-session tick), then
        # published_at descending (prefer the most recently published
        # among truly simultaneous-effective revisions), then
        # observation_id ascending as the final deterministic tie-break.
        ordered = sorted(pool, key=lambda o: o.observation_id)
        ordered = sorted(ordered, key=lambda o: _instant_key(o.published_at), reverse=True)
        ordered = sorted(ordered, key=lambda o: _instant_key(o.effective_at), reverse=True)
        ordered = sorted(ordered, key=lambda o: _authority_rank_for(o, manifests_by_id))
        best = ordered[0]
        best_rank = _authority_rank_for(best, manifests_by_id)
        # A lower-authority source disagreeing at the same effective_at is
        # not a conflict -- authority-first means the higher-authority
        # source simply wins outright. Only same-authority-tier
        # disagreement is a genuine, unresolved conflict.
        tied = [
            o for o in ordered
            if o is not best
            and _authority_rank_for(o, manifests_by_id) == best_rank
            and o.effective_at == best.effective_at
            and o.decimal_value != best.decimal_value
        ]
        if tied:
            all_tied = [best] + tied
            return None, sorted(all_tied, key=lambda o: o.observation_id), _conflict_entry(
                f"conflict-price-{as_of_date}", "/price_observation", all_tied,
                selected=None, resolution_status="unresolved_blocking", rationale_code="capital.price_share_basis_mismatch",
            )
        identical = [o for o in ordered if o.effective_at == best.effective_at]
        return best, identical, None

    return None, [], None


def _matching_override(
    overrides: Sequence[Mapping[str, Any]], *, target_dimension: str, candidate_ids: set[str],
    cutoff_instant: str, as_of_date: str,
) -> Mapping[str, Any] | None:
    """Returns the first governed override that validly resolves an
    unresolved conflict on ``target_dimension`` covering exactly the given
    ``candidate_ids`` -- or ``None`` if no override applies, in which case
    the conflict remains unresolved (docs/valuation-t70-04-market-registry-
    snapshot-specification.md Section 11). An override never silently
    applies to evidence it does not explicitly name as displaced, never
    approves itself after the fact (``approved_at`` must not be after
    cutoff), and never survives past its own review date."""
    for override in overrides:
        if override.get("target_dimension") != target_dimension:
            continue
        if _instant_key(override["approved_at"]) > _instant_key(cutoff_instant):
            continue
        if override["expiration_or_review_date"] < as_of_date:
            continue
        displaced = set(override.get("displaced_observation_refs", ()))
        if not candidate_ids.issubset(displaced):
            continue
        return override
    return None


def _observation_from_override(override: Mapping[str, Any], *, observation_type: str, instrument_or_pair: str) -> MarketObservation:
    """A governed override supplies its own replacement value, unit and
    currency directly -- represented as a synthetic
    :class:`MarketObservation` (never schema-parsed, since it never
    existed as raw injected evidence) purely so downstream selection code
    can treat an override-resolved dimension identically to a normally
    resolved one, rather than duplicating every consumer's field access."""
    return MarketObservation(
        observation_id=f"override-{override['override_id']}",
        observation_type=observation_type,
        instrument_or_pair=instrument_or_pair,
        value=override["replacement_value"],
        unit=override["replacement_unit"],
        currency=override.get("replacement_currency"),
        price_mode="diagnostic_reference" if observation_type == "price" else None,
        effective_at=override["approved_at"],
        published_at=override["approved_at"],
        available_at=override["approved_at"],
        source_manifest_id="governed_override",
        revision_status="original",
    )


def _override_conflict_entry(conflict_id: str, field_path: str, candidates: Sequence[MarketObservation], override: Mapping[str, Any]) -> dict[str, Any]:
    entry = _conflict_entry(
        conflict_id, field_path, candidates, selected=None,
        resolution_status="resolved_by_override", rationale_code=override["rationale_code"],
    )
    entry["override"] = dict(override)
    return entry


def resolve_market_snapshot(request: MarketResolutionRequest) -> MarketResolutionResult:
    findings: list[Finding] = []
    compatibility_finding = _mode_purpose_finding(request)
    if compatibility_finding is not None:
        return MarketResolutionResult(snapshot=None, findings=(compatibility_finding,))

    observations = request.observations
    manifests_by_id = request.manifests_by_id()
    manifest_ref_by_id = request.manifest_ref_by_manifest_id()

    wrong_manifest = [o for o in observations if o.source_manifest_id not in manifests_by_id]
    if wrong_manifest:
        findings.append(Finding(
            rule_id="VAL-MI-001", severity="blocker", scope="artifact",
            reason_code="identity.reference_invalid",
            message=f"{len(wrong_manifest)} observation(s) declare a source_manifest_id that does not match any requested manifest",
            related_reference_ids=tuple(sorted(o.observation_id for o in wrong_manifest)),
        ))
    observations = tuple(o for o in observations if o.source_manifest_id in manifests_by_id)

    wrong_instrument = [
        o for o in observations
        if o.observation_type != "fx" and o.instrument_id != request.instrument_id
    ]
    if wrong_instrument:
        findings.append(Finding(
            rule_id="VAL-MI-001", severity="blocker", scope="artifact",
            reason_code="identity.reference_invalid",
            message=f"{len(wrong_instrument)} observation(s) reference an instrument other than {request.instrument_id!r}",
            related_reference_ids=tuple(sorted(o.observation_id for o in wrong_instrument)),
        ))
    observations = tuple(
        o for o in observations
        if o.observation_type == "fx" or o.instrument_id == request.instrument_id
    )

    conflicts: list[dict[str, Any]] = []
    lineage: list[dict[str, Any]] = []

    # --- Price selection -------------------------------------------------
    price_pool = _eligible_pool(observations, observation_type="price", cutoff_instant=request.cutoff_instant, as_of_date=request.as_of_date)
    if request.purpose == "current_valuation" and price_pool and all(o.price_mode == "diagnostic_reference" for o in price_pool):
        findings.append(Finding(
            rule_id="VAL-MI-009", severity="blocker", scope="artifact",
            reason_code="capital.diagnostic_reference_not_primary",
            message="diagnostic_reference price observations are not eligible as primary current-valuation prices",
            related_reference_ids=tuple(sorted(o.observation_id for o in price_pool)),
        ))
        return MarketResolutionResult(snapshot=None, findings=tuple(findings))
    selected_price, price_lineage, price_conflict = _select_best_price(price_pool, manifests_by_id, request.as_of_date, request.primary_price_mode)

    price_override = None
    if selected_price is None and price_conflict is not None:
        price_override = _matching_override(
            request.overrides, target_dimension="price", candidate_ids={c.observation_id for c in price_lineage},
            cutoff_instant=request.cutoff_instant, as_of_date=request.as_of_date,
        )
        if price_override is not None:
            price_conflict = _override_conflict_entry(price_conflict["conflict_id"], "/price_observation", price_lineage, price_override)

    if price_conflict:
        conflicts.append(price_conflict)

    if selected_price is None and price_override is None:
        findings.append(Finding(
            rule_id="VAL-MI-003", severity="error", scope="artifact",
            reason_code="status.required_observation_missing",
            message="no eligible primary price observation could be selected",
        ))
        return MarketResolutionResult(snapshot=None, findings=tuple(findings))

    if price_override is not None:
        # A governed override supplies its own replacement value -- it is
        # not any one of the displaced candidate observations, so it never
        # gets a real official_close/intraday/historical_close mode; it is
        # carried as diagnostic_reference (the closest of the four schema
        # modes to "an exceptional, human-approved substitution", used only
        # when normal sources genuinely could not resolve).
        for candidate in price_lineage:
            lineage.append({"node_id": candidate.observation_id, "node_type": "market_observation", "relation": "observed_from"})
        price_freshness = "acceptable"
        price_observation = {
            "observation_id": f"override-{price_override['override_id']}",
            "mode": "diagnostic_reference",
            "price": normalize_decimal(price_override["replacement_value"]),
            "observed_at": price_override["approved_at"],
            "published_at": price_override["approved_at"],
            "available_at": price_override["approved_at"],
            "session_date": request.as_of_date,
            "adjustment_basis": "unadjusted",
            "is_primary": True,
            "source_ref": {"source_id": "governed_override", "effective_at": price_override["approved_at"]},
            "freshness": price_freshness,
            "status": "selected",
        }
    else:
        price_freshness = _freshness_class(_date_of(selected_price.effective_at), request.as_of_date)
        for other in price_lineage:
            lineage.append({"node_id": other.observation_id, "node_type": "market_observation", "relation": "selected_from" if other is selected_price else "observed_from"})
        if len(price_lineage) > 1:
            conflicts.append(_conflict_entry(
                f"conflict-price-{request.as_of_date}", "/price_observation", price_lineage,
                selected=selected_price, resolution_status="resolved_by_policy", rationale_code="capital.price_share_basis_mismatch",
            ))

        price_observation = {
            "observation_id": selected_price.observation_id,
            "mode": selected_price.price_mode,
            "price": normalize_decimal(selected_price.value),
            "observed_at": selected_price.effective_at,
            "published_at": selected_price.published_at,
            "available_at": selected_price.available_at,
            "session_date": _date_of(selected_price.effective_at),
            "adjustment_basis": "unadjusted",
            "is_primary": True,
            "source_ref": {"source_id": selected_price.source_manifest_id, "effective_at": selected_price.effective_at},
            "freshness": price_freshness,
            "status": "selected",
        }

    # T68.3 VAL-MI-009: "Diagnostic/adjusted reference cannot become
    # primary current input." A diagnostic_reference-mode observation is
    # explicitly not an official/intraday/historical market tick; it must
    # never silently become the primary price for a current_valuation
    # snapshot. A governed override is the sole, explicit exception -- its
    # diagnostic_reference mode reflects that it is not a raw market tick
    # either, but it reached primary status through explicit human
    # approval (Section 11), not through ordinary selection leakage.
    if (
        request.purpose == "current_valuation"
        and price_observation["mode"] == "diagnostic_reference"
        and price_observation["source_ref"]["source_id"] != "governed_override"
    ):
        findings.append(Finding(
            rule_id="VAL-MI-009", severity="blocker", scope="artifact",
            reason_code="identity.reference_invalid",
            message=f"observation {price_observation['observation_id']!r} has price_mode 'diagnostic_reference' "
                    "and cannot become the primary current-valuation input",
        ))
        return MarketResolutionResult(snapshot=None, findings=tuple(findings))

    # --- Share-count selection -------------------------------------------
    share_pool = _eligible_pool(observations, observation_type="share_count", cutoff_instant=request.cutoff_instant, as_of_date=request.as_of_date)
    issued_pool = [o for o in share_pool if o.is_issued_shares]
    treasury_pool = [o for o in share_pool if o.is_treasury_shares]
    direct_outstanding_pool = [o for o in share_pool if o.is_spot_basic_shares_outstanding]

    def _select_share(pool: list[MarketObservation], *, target_dimension: str) -> tuple[MarketObservation | None, dict[str, Any] | None]:
        if not pool:
            return None, None
        latest = max(_instant_key(o.effective_at) for o in pool)
        top = sorted([o for o in pool if _instant_key(o.effective_at) == latest], key=lambda o: o.observation_id)
        distinct_values = {o.value for o in top}
        if len(distinct_values) > 1:
            override = _matching_override(
                request.overrides, target_dimension=target_dimension, candidate_ids={o.observation_id for o in top},
                cutoff_instant=request.cutoff_instant, as_of_date=request.as_of_date,
            )
            if override is not None:
                synthetic = _observation_from_override(override, observation_type="share_count", instrument_or_pair=top[0].instrument_or_pair)
                return synthetic, _override_conflict_entry(f"conflict-share-{top[0].instrument_or_pair}", "/share_basis", top, override)
            return None, _conflict_entry(
                f"conflict-share-{top[0].instrument_or_pair}", "/share_basis", top,
                selected=None, resolution_status="unresolved_blocking", rationale_code="capital.price_share_basis_mismatch",
            )
        return top[0], None

    selected_issued, issued_conflict = _select_share(issued_pool, target_dimension="issued_shares")
    selected_treasury, treasury_conflict = _select_share(treasury_pool, target_dimension="treasury_shares")
    selected_direct, direct_conflict = _select_share(
        direct_outstanding_pool, target_dimension="spot_basic_shares_outstanding"
    )
    for c in (issued_conflict, treasury_conflict, direct_conflict):
        if c:
            conflicts.append(c)

    share_basis: dict[str, Any] | None = None
    if selected_issued is not None and selected_treasury is not None:
        outcome = evaluate_formula(
            request.catalog_registry.select_entry("valuation.formulas.capital_basis", "val.formula.capital.spot_basic_shares").entry,
            {
                "issued_shares": Operand("available", selected_issued.decimal_value),
                "treasury_shares": Operand("available", selected_treasury.decimal_value),
            },
        )
        effective_date = max(_date_of(selected_issued.effective_at), _date_of(selected_treasury.effective_at))
        if outcome.status == "available":
            if selected_direct is not None and selected_direct.decimal_value != outcome.value:
                findings.append(Finding(
                    rule_id="VAL-MI-005", severity="blocker", scope="artifact",
                    reason_code="capital.price_share_basis_mismatch",
                    message="directly reported spot basic shares do not reconcile with issued_shares - treasury_shares",
                ))
                return MarketResolutionResult(snapshot=None, findings=tuple(findings))
            share_basis = {
                "basis_id": f"share-basis-{request.instrument_id}-{effective_date}",
                "basis_type": "spot_basic_shares_outstanding",
                "issued_shares": normalize_decimal(selected_issued.value),
                "treasury_shares": normalize_decimal(selected_treasury.value),
                "spot_basic_shares_outstanding": normalize_decimal(outcome.value),
                "effective_date": effective_date,
                "reconciliation_status": "reconciled",
                "source_refs": [
                    {"source_id": selected_issued.source_manifest_id, "effective_at": selected_issued.effective_at},
                    {"source_id": selected_treasury.source_manifest_id, "effective_at": selected_treasury.effective_at},
                ],
                "freshness": _freshness_class(effective_date, request.as_of_date),
            }
            lineage.append({"node_id": selected_issued.observation_id, "node_type": "market_observation", "relation": "selected_from"})
            lineage.append({"node_id": selected_treasury.observation_id, "node_type": "market_observation", "relation": "selected_from"})
            if selected_direct is not None:
                share_basis["source_refs"].append(
                    {"source_id": selected_direct.source_manifest_id, "effective_at": selected_direct.effective_at}
                )
                lineage.append({"node_id": selected_direct.observation_id, "node_type": "market_observation", "relation": "reconciled_with"})
        else:
            findings.append(Finding(
                rule_id="VAL-MI-005", severity="blocker", scope="artifact",
                reason_code="capital.nonpositive_basic_shares" if outcome.status == "calculation_blocked" else "status.required_observation_missing",
                message="issued_shares - treasury_shares did not reconcile to a positive spot basic share count",
            ))
    elif selected_direct is not None:
        effective_date = _date_of(selected_direct.effective_at)
        share_basis = {
            "basis_id": f"share-basis-{request.instrument_id}-{effective_date}",
            "basis_type": "spot_basic_shares_outstanding",
            "spot_basic_shares_outstanding": normalize_decimal(selected_direct.value),
            "effective_date": effective_date,
            "derivation_method": "direct_reported",
            "reconciliation_status": "direct_reported",
            "source_refs": [
                {"source_id": selected_direct.source_manifest_id, "effective_at": selected_direct.effective_at},
            ],
            "freshness": _freshness_class(effective_date, request.as_of_date),
        }
        lineage.append({"node_id": selected_direct.observation_id, "node_type": "market_observation", "relation": "selected_from"})
    else:
        findings.append(Finding(
            rule_id="VAL-MI-005", severity="error", scope="artifact",
            reason_code="status.required_observation_missing",
            message="no eligible direct outstanding-shares observation or issued_shares/treasury_shares pair could be selected",
        ))

    if share_basis is None:
        return MarketResolutionResult(snapshot=None, findings=tuple(findings))

    # --- FX pass-through (raw eligible evidence only; selection against a
    # target reporting currency happens in the valuation-input resolver) --
    fx_pool = _eligible_pool(observations, observation_type="fx", cutoff_instant=request.cutoff_instant, as_of_date=request.as_of_date)
    if request.primary_fx_mode is not None:
        fx_pool = [o for o in fx_pool if o.fx_mode == request.primary_fx_mode]
    fx_observations = []
    seen_pairs: dict[str, MarketObservation] = {}
    for obs in sorted(fx_pool, key=lambda o: (o.instrument_or_pair, _instant_key(o.effective_at), o.observation_id)):
        prior = seen_pairs.get(obs.instrument_or_pair)
        if prior is not None and prior.value != obs.value and prior.effective_at == obs.effective_at:
            conflicts.append(_conflict_entry(
                f"conflict-fx-{obs.instrument_or_pair}", "/fx_observations", [prior, obs],
                selected=None, resolution_status="unresolved_blocking", rationale_code="capital.fx_missing_or_invalid",
            ))
            continue
        seen_pairs[obs.instrument_or_pair] = obs
        base, quote = obs.instrument_or_pair.split("/")
        fx_entry: dict[str, Any] = {
            "fx_observation_id": obs.observation_id,
            "base_currency": base,
            "quote_currency": quote,
            "rate": normalize_decimal(obs.value),
            "path_type": "direct",
            "observed_at": obs.effective_at,
            "published_at": obs.published_at,
            "available_at": obs.available_at,
            "source_ref": {"source_id": obs.source_manifest_id, "effective_at": obs.effective_at},
            "freshness": _freshness_class(_date_of(obs.effective_at), request.as_of_date),
        }
        if request.primary_fx_mode is not None:
            fx_entry["fx_mode"] = obs.fx_mode
        fx_observations.append(fx_entry)
        lineage.append({"node_id": obs.observation_id, "node_type": "market_observation", "relation": "selected_from"})

    # --- Corporate-action state -------------------------------------------
    corporate_action_coverage_blocking = False
    if request.corporate_action_bundle is not None:
        bundle = request.corporate_action_bundle
        bundle_events = [e for e in bundle.events if e.instrument_id == request.instrument_id]
        eligible_events = [
            e for e in bundle_events
            if _instant_key(e.available_at) <= _instant_key(request.cutoff_instant)
            and e.effective_date <= request.as_of_date
            and e.revision_status != "withdrawn"
        ]
        corporate_action_state = {
            "state_id": f"ca-{request.instrument_id}-{request.as_of_date}",
            "as_of_date": request.as_of_date,
            "events": [e.to_snapshot_event() for e in sorted(eligible_events, key=lambda e: e.event_id)],
            "coverage_status": bundle.coverage.coverage_status,
        }
        if bundle.coverage.unresolved_gap_refs:
            corporate_action_state["unresolved_event_refs"] = sorted(bundle.coverage.unresolved_gap_refs)
        for event in sorted(eligible_events, key=lambda e: e.event_id):
            lineage.append({"node_id": event.event_id, "node_type": "corporate_action_event", "relation": "observed_from"})
        if request.purpose == "current_valuation" and bundle.coverage.coverage_status != "complete":
            corporate_action_coverage_blocking = True
            findings.append(Finding(
                rule_id="VAL-MI-010", severity="blocker", scope="artifact",
                reason_code="status.corporate_action_coverage_gap",
                message=(
                    f"corporate-action coverage_status is {bundle.coverage.coverage_status!r}, not 'complete', "
                    "which current_valuation purpose requires before this snapshot can be current-use eligible"
                ),
            ))
    else:
        corporate_action_state = {
            "state_id": f"ca-{request.instrument_id}-{request.as_of_date}",
            "as_of_date": request.as_of_date,
            "events": [],
            "coverage_status": "unknown",
        }

    blocking_conflicts = [c for c in conflicts if c["resolution_status"] == "unresolved_blocking"]
    current_use_state = "blocked" if blocking_conflicts or price_freshness == "expired" or corporate_action_coverage_blocking else (
        "eligible" if price_freshness in ("fresh", "acceptable") else "diagnostic_only"
    )
    confidence_level = "insufficient" if current_use_state == "blocked" else (
        "high" if price_freshness == "fresh" and not conflicts else
        "medium" if price_freshness == "acceptable" else "low"
    )

    # Only the manifest(s) that actually sourced a *used* observation are
    # referenced here -- not every manifest the caller happened to supply
    # -- so lineage reflects what genuinely contributed to this snapshot.
    used_manifest_ids: set[str] = {price_observation["source_ref"]["source_id"]}
    if share_basis is not None:
        for ref in share_basis["source_refs"]:
            used_manifest_ids.add(ref["source_id"])
    for fx in fx_observations:
        used_manifest_ids.add(fx["source_ref"]["source_id"])

    used_manifest_refs = [
        dict(manifest_ref_by_id[manifest_id]) for manifest_id in sorted(used_manifest_ids) if manifest_id in manifest_ref_by_id
    ]
    for manifest_id in sorted(used_manifest_ids):
        if manifest_id not in manifest_ref_by_id:
            continue
        lineage.append({
            "node_id": manifest_id,
            "node_type": "market_source_manifest",
            "relation": "observed_from",
            "artifact_ref": dict(manifest_ref_by_id[manifest_id]),
        })

    policy_catalog = request.catalog_registry.catalog("valuation.policies.market_input")

    snapshot: dict[str, Any] = {
        "schema_version": "1.0.0",
        "artifact_type": "market_snapshot",
        "owner_type": "generated",
        "snapshot_identity": {
            "ticker": request.ticker,
            "instrument_id": request.instrument_id,
            "context_id": request.context_id,
            "purpose": request.purpose,
        },
        "temporal_context": {
            "as_of_date": request.as_of_date,
            "cutoff_instant": request.cutoff_instant,
            "market_session_date": price_observation["session_date"],
            "market_session_status": "completed" if price_observation["session_date"] == request.as_of_date else "unknown",
        },
        "selection_policy_ref": {
            "catalog_id": policy_catalog["catalog_id"],
            "catalog_version": policy_catalog["catalog_version"],
        },
        "instrument": {
            "instrument_id": request.instrument_id,
            "instrument_type": request.instrument_type,
            "trading_currency": request.trading_currency,
            "price_unit": "per_share",
            "unit_multiplier": "1",
            "listing_status": "active",
        },
        "price_observation": price_observation,
        "share_basis": share_basis,
        "corporate_action_state": corporate_action_state,
        "source_manifest_refs": used_manifest_refs,
        "freshness_summary": {"current_use_state": current_use_state},
        "data_confidence": {"level": confidence_level},
        "lineage": sorted(lineage, key=lambda entry: (entry["node_id"], entry["relation"])),
        "acceptance": {
            "acceptance_status": "rejected" if current_use_state == "blocked" else "accepted",
            "accepted_at": request.cutoff_instant,
            "current_use_eligible": current_use_state == "eligible",
        },
    }
    if fx_observations:
        snapshot["fx_observations"] = sorted(fx_observations, key=lambda o: o["fx_observation_id"])
    if conflicts:
        snapshot["conflicts"] = sorted(conflicts, key=lambda c: c["conflict_id"])

    if current_use_state == "blocked":
        findings.append(Finding(
            rule_id="VAL-MI-008", severity="blocker", scope="artifact",
            reason_code="capital.price_share_basis_mismatch",
            message="an unresolved blocking conflict prevents this snapshot from being current-use eligible",
        ))

    return MarketResolutionResult(snapshot=snapshot, findings=tuple(findings))
