"""Builds a single summary section's structured content from a policy and
the signals/risks available for the period.

A section distinguishes six signal buckets, not three:

- ``positive_signals`` / ``negative_signals``: an evaluated signal whose
  contextual presentation status is unambiguously directional. The raw
  evaluator value remains unchanged in the signal artifact.
- ``neutral_signals``: an evaluated signal whose value is ``neutral`` or
  ``mixed`` -- it *has* usable data, it just isn't directional.
- ``unavailable_signals``: the signal object exists but its evaluator could
  not produce a value (``value == "unavailable"``). This is data the
  section does not have, not a neutral opinion about the data, and it must
  never be silently folded into ``neutral_signals``.
- ``missing_signals``: the section's policy names this signal, the signal
  is applicable to the current company/sector combination, but no signal
  object with that id was generated at all. A signal id that a
  cross-sector policy lists but that is categorically inapplicable to this
  sector module (e.g. an aviation-only id inside a policy also used by
  generic companies) is excluded before bucketing entirely -- see
  ``applicable_signal_ids`` on :func:`build_signal_section` -- since it was
  never going to exist for this company and is not "missing" data.

Only ``positive``/``negative``/``neutral``/``mixed`` signals count as
*available* for completeness purposes; ``unavailable`` and ``missing`` both
reduce ``data_completeness`` (see the ``completeness`` block).
"""

from __future__ import annotations

from .policies import SectionPolicy, bucket_status

_DIRECTIONAL_BUCKET = {"positive": "positive", "negative": "negative"}


def _bucket_of(value: str) -> str:
    """positive/negative are their own bucket; neutral and mixed are both
    'neutral' (available, non-directional); unavailable is handled by the
    caller before this is reached."""
    return _DIRECTIONAL_BUCKET.get(value, "neutral")


def _presentation_value(signal: dict) -> str:
    """Use the v2 contextual status, with a v1 fallback for old fixtures."""
    return signal.get("context", {}).get("presentation_status", signal["value"])


def _section_completeness(applicable: int, unavailable_count: int, missing_count: int) -> dict:
    available = applicable - unavailable_count - missing_count
    completeness_pct = round((available / applicable * 100) if applicable else 100.0, 1)
    return {
        "applicable": applicable,
        "available": available,
        "unavailable": unavailable_count,
        "missing": missing_count,
        "completeness_pct": completeness_pct,
    }, available, completeness_pct


def build_signal_section(
    policy: SectionPolicy,
    signals_by_id: dict,
    applicable_signal_ids: set[str] | None = None,
    context_policy: dict | None = None,
) -> dict:
    if policy.uses_all_signals:
        # Every signal the pipeline actually generated is, by construction,
        # "configured" for this section -- there is no separate applicable
        # list to compare against, so nothing can ever be "missing" here.
        configured_ids = list(signals_by_id)
    else:
        configured_ids = list(policy.signal_ids)
        if applicable_signal_ids is not None:
            # A policy may list signal ids spanning more than one sector
            # module (e.g. profitability_summary lists both generic and
            # aviation-only ids). A signal id that is categorically
            # inapplicable to the current company/sector combination is not
            # "missing data" -- it was never going to be generated for this
            # company, so it must not be counted against completeness or
            # surfaced as a missing signal. The caller is responsible for
            # including any id it doesn't recognize in ``applicable_signal_ids``
            # (defensive keep-unknown), so this is a plain membership filter.
            configured_ids = [sid for sid in configured_ids if sid in applicable_signal_ids]

    positive: list[str] = []
    negative: list[str] = []
    neutral: list[str] = []
    unavailable: list[str] = []
    missing: list[str] = []

    for signal_id in configured_ids:
        signal = signals_by_id.get(signal_id)
        if signal is None:
            missing.append(signal_id)
            continue
        value = _presentation_value(signal)
        if value == "unavailable":
            unavailable.append(signal_id)
            continue
        {"positive": positive, "negative": negative, "neutral": neutral}[_bucket_of(value)].append(signal_id)

    section_signals, available, completeness_pct = _section_completeness(
        len(configured_ids), len(unavailable), len(missing)
    )

    dominant_value = None
    if policy.dominant_signal_id and policy.dominant_signal_id in signals_by_id:
        dv = _presentation_value(signals_by_id[policy.dominant_signal_id])
        if dv in ("positive", "negative"):
            dominant_value = dv

    context_policy = context_policy or {}
    required_signal_ids = context_policy.get("required_signal_ids", [])
    required_signals_available = all(
        sid in signals_by_id and _presentation_value(signals_by_id[sid]) != "unavailable"
        for sid in required_signal_ids
    )
    min_available_signals = context_policy.get("min_available_signals", policy.min_available_signals)
    min_completeness_pct = context_policy.get("min_completeness_pct", policy.min_completeness_pct)

    base_insufficient = available < policy.min_available_signals or completeness_pct < policy.min_completeness_pct
    context_limited = (
        available < min_available_signals
        or completeness_pct < min_completeness_pct
        or not required_signals_available
    )

    if base_insufficient:
        status = "insufficient_data"
    else:
        status = bucket_status(positive, negative, neutral, dominant_value)
        if context_limited and status in ("positive", "neutral"):
            status = "insufficient_data"

    key_drivers = [signals_by_id[sid]["reason"] for sid in (positive[:2] + negative[:2])]

    return {
        "status": status,
        "positive_signals": positive,
        "negative_signals": negative,
        "neutral_signals": neutral,
        "unavailable_signals": unavailable,
        "missing_signals": missing,
        "key_drivers": key_drivers,
        "completeness": {"section_signals": section_signals},
        "data_completeness": completeness_pct,
        "investment_signal": False,
    }


def build_risk_section(risks: list[dict], min_available_signals: int = 1, min_completeness_pct: float = 0.0) -> dict:
    positive, negative, neutral = [], [], []
    for risk in risks:
        direction = risk.get("direction")
        bucket = "negative" if direction == "negative" else ("positive" if direction == "positive" else "neutral")
        {"positive": positive, "negative": negative, "neutral": neutral}[bucket].append(risk["risk_id"])

    applicable = len(risks)
    # Every authored risk record is, definitionally, "available" data (there
    # is no "unavailable risk" concept) -- evidence completeness is tracked
    # separately below and does not gate classifiability on its own.
    available = applicable
    with_evidence = sum(1 for r in risks if r.get("evidence"))
    completeness_pct = round((with_evidence / applicable * 100) if applicable else 100.0, 1)
    section_signals = {
        "applicable": applicable,
        "available": available,
        "unavailable": 0,
        "missing": 0,
        "completeness_pct": completeness_pct,
    }

    if available < min_available_signals or completeness_pct < min_completeness_pct:
        status = "insufficient_data"
    else:
        status = bucket_status(positive, negative, neutral)

    high_severity = [r["title"] for r in risks if r.get("severity") == "high"]

    return {
        "status": status,
        "positive_signals": positive,
        "negative_signals": negative,
        "neutral_signals": neutral,
        "unavailable_signals": [],
        "missing_signals": [],
        "key_risks": high_severity[:5],
        "completeness": {"section_signals": section_signals},
        "data_completeness": completeness_pct,
        "investment_signal": False,
    }
