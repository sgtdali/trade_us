"""Deterministic, module-aware summary generation."""

from __future__ import annotations

from .. import completeness as _completeness
from ..context import AnalysisContext
from ..io import read_json
from ..paths import repo_path
from .policies import SECTION_POLICIES
from .section_builders import build_risk_section, build_signal_section


def _applicable_signal_ids(context: AnalysisContext) -> set[str]:
    """Signal ids registered in config/pipeline/signal-rules.json that apply
    to this context's company_type/sector_module, plus (defensively) any
    signal id a section policy names that isn't registered there at all --
    an unrecognized id is kept rather than silently filtered out, matching
    the pre-filtering behavior for anything the registry doesn't cover."""
    rules_config = read_json(repo_path("config/pipeline/signal-rules.json"))
    registered_ids: set[str] = set()
    eligible_ids: set[str] = set()
    for definition in rules_config.get("signals", []):
        registered_ids.add(definition["signal_id"])
        if (
            context.company_type in definition.get("applicable_company_types", [])
            and context.sector_module_id in definition.get("applicable_sector_modules", [])
        ):
            eligible_ids.add(definition["signal_id"])

    policy_ids = {sid for policy in SECTION_POLICIES for sid in policy.signal_ids}
    unregistered_ids = policy_ids - registered_ids
    return eligible_ids | unregistered_ids


def generate_summaries(context: AnalysisContext, signals_data: dict, authored_risks: dict | None) -> dict:
    """Compute the full summaries contract from generated signals and
    authored risks. Pure function: does not read or write any file."""
    signals_by_id = {s["signal_id"]: s for s in signals_data.get("signals", [])}
    risks = (authored_risks or {}).get("risks", [])
    applicable_signal_ids = _applicable_signal_ids(context)
    rules_config = read_json(repo_path("config/pipeline/signal-rules.json"))
    summary_context_policies = rules_config.get("summary_context_policies", {})

    summaries: dict[str, dict] = {}
    for policy in SECTION_POLICIES:
        if context.sector_module_id not in policy.applicable_sector_modules:
            continue
        if policy.uses_risks:
            summaries[policy.section_id] = build_risk_section(
                risks, policy.min_available_signals, policy.min_completeness_pct
            )
        else:
            summaries[policy.section_id] = build_signal_section(
                policy,
                signals_by_id,
                applicable_signal_ids,
                summary_context_policies.get(policy.section_id),
            )

    # Overall input/metric completeness (distinct from each section's own
    # signal completeness above): reproducible from the same normalized
    # inputs the derivation/signal engines already consumed, via the
    # central completeness engine. Reported once at file level rather than
    # duplicated inside every section.
    input_completeness = _completeness.calculate(
        context.company_type,
        context.sector_module_id,
        context.direct_financials or {},
        context.financial_operational_data or {},
    )

    return {
        "schema_version": 1,
        "ticker": context.ticker,
        "period": context.period_id,
        "generated_from": {
            "signals": f"data/signals/{context.ticker}/{context.period_id}.json",
            "risks": f"data/risks/{context.ticker}/{context.period_id}.json",
        },
        "input_completeness": input_completeness,
        "summaries": summaries,
    }
