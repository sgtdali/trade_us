from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from engine.io import read_json, write_json_atomic

from .errors import FactSelectionError, SecDataError
from .models import FilingRef, SecFact

_US_GAAP_NAMESPACES = ("http://fasb.org/us-gaap/",)
_DEI_NAMESPACES = ("http://xbrl.sec.gov/dei/",)
_DURATION_WINDOWS = {
    "FY": (320, 400),
    "Q1": (60, 120),
    "Q2": (130, 220),
    "Q3": (220, 310),
}


def _quarter_from_year_to_date(facts: tuple[SecFact, ...]) -> str | None:
    """Kapak etiketi bozuksa ceyregi bildirimin KENDISINDEN geri kazan.

    Yil-basindan-bugune sure ucte bolunur. Ayni tablo (`_DURATION_WINDOWS`)
    ters yonde okunur; ayri bir esik uydurulmaz.

    Belge donemi sonunda biten, boyutsuz sureli fact'lerin EN UZUNU YTD'dir --
    Q2 ve Q3'te ayni tarihte biten bir de 3 aylik sutun bulunur ve o secilirse
    her ceyrek Q1 gorunur."""
    period_end_raw = _dei_value(facts, "DocumentPeriodEndDate")
    if not period_end_raw:
        return None
    try:
        period_end = date.fromisoformat(str(period_end_raw)[:10])
    except ValueError:
        return None
    spans = [
        (fact.end_date - fact.start_date).days
        for fact in facts
        if fact.start_date is not None
        and fact.end_date == period_end
        and not fact.dimensions
        and not fact.is_nil
    ]
    if not spans:
        return None
    longest = max(spans)
    for period, (low, high) in _DURATION_WINDOWS.items():
        if period != "FY" and low <= longest <= high:
            return period
    return None


def normalize_filing(
    *,
    workspace: Path,
    ticker: str,
    filing: FilingRef,
    facts: tuple[SecFact, ...],
    mapping_path: Path,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    fiscal_year = _dei_value(facts, "DocumentFiscalYearFocus")
    fiscal_period = _dei_value(facts, "DocumentFiscalPeriodFocus")
    if fiscal_period == "Q4" and filing.form.startswith("10-K"):
        # A 10-K is an annual report by definition, and US issuers file no
        # fourth-quarter 10-Q -- the fourth quarter is covered by the annual
        # report. Some filers still tag the cover page Q4 rather than FY
        # (COST's fiscal 2019 10-K, period ending 2019-09-01), which is a
        # cover-page labelling convention and not a different period. Trusting
        # the tag over the form stopped eight historical quarters outright
        # (found 2026-08-05).
        fiscal_period = "FY"
    if fiscal_period == "FY" and filing.form.startswith("10-Q"):
        # The mirror of the rule above, and the more damaging direction. A 10-Q
        # is a quarterly report by definition; no US issuer files its annual
        # report on Form 10-Q. Dell tagged the cover page of two consecutive
        # fiscal-2024 10-Qs "FY" -- the quarters ending 2023-05-05 and
        # 2023-08-04 -- while every other Dell 10-Q is tagged correctly.
        #
        # Two harms, and the quiet one is worse. The loud one is a quarterly
        # period carrying an annual id, which fails validation outright and
        # took six consecutive months out of the 2021-2024 control run. The
        # quiet one is COLLISION: both mistagged 10-Qs and the real 10-K all
        # resolve to "2024-FY", so an annual artifact can be silently
        # overwritten by a quarter's figures whenever validation happens not to
        # catch it.
        #
        # The quarter is recovered from the filing itself rather than guessed:
        # year-to-date duration divided by three. That is the same table the
        # focus tag is checked against, read in the other direction.
        recovered = _quarter_from_year_to_date(facts)
        if recovered is None:
            raise SecDataError(
                f"{ticker}: 10-Q {filing.accession} is tagged fiscal period FY and its "
                "year-to-date duration does not identify a quarter"
            )
        fiscal_period = recovered
    if not fiscal_year or fiscal_period not in _DURATION_WINDOWS:
        raise SecDataError(f"unsupported fiscal focus: year={fiscal_year!r}, period={fiscal_period!r}")
    period_id = f"{fiscal_year}-{fiscal_period}"
    period_type = "annual" if fiscal_period == "FY" else "quarterly"

    mapping = read_json(mapping_path)
    selected_evidence: list[dict[str, Any]] = []
    statements = {"income_statement": [], "balance_sheet": [], "cash_flow_statement": []}
    source_id = f"sec-{filing.accession.lower()}"
    evidence_rel = f"raw/sec-filings/{ticker}/{filing.accession}.json"

    def _build_metric(rule: dict[str, Any], selection: tuple[SecFact, SecFact | None]) -> dict[str, Any]:
        current, comparison = selection
        unit_kind = rule.get("unit_kind", "money")
        sign = Decimal(str(rule.get("sign", 1)))
        value = _scaled_value(current, unit_kind=unit_kind, sign=sign)
        comparison_value = _scaled_value(comparison, unit_kind=unit_kind, sign=sign) if comparison else None
        unit = "usd_per_share" if unit_kind == "per_share" else "million_usd"
        return {
            "metric_id": rule["metric_id"],
            "name": rule["name"],
            "value": value,
            "unit": unit,
            "period": period_id,
            "comparison_value": comparison_value,
            "comparison_period": _comparison_period(period_id) if comparison else None,
            "change": None,
            "change_unit": None,
            "data_type": "direct",
            "status": "available",
            "reason": None,
            "provenance": {
                "source_file": evidence_rel,
                "source_type": "sec_inline_xbrl",
                "source_id": source_id,
                "page": None,
                "sheet": rule["statement"],
                "cell_or_range": f"{current.qualified_name}#{current.context_id}",
                "formula": None,
                "notes": f"SEC accession {filing.accession}; dimensionless entity-wide fact.",
            },
        }

    for rule in mapping.get("metrics", []):
        selected = _select_fact(facts, filing.report_date, fiscal_period, rule)
        if selected is None:
            continue
        current, comparison = selected
        statements[rule["statement"]].append(_build_metric(rule, selected))
        selected_evidence.append({
            "metric_id": rule["metric_id"],
            "current": _fact_record(current),
            "comparison": _fact_record(comparison) if comparison else None,
        })

    _include_derived_gross_profit(statements)

    def _rebuild_revenue(trial: dict[str, list[dict[str, Any]]], selection: tuple[SecFact, SecFact | None]) -> None:
        rule = next(r for r in mapping.get("metrics", []) if r["metric_id"] == "revenue_total")
        trial["income_statement"] = [
            metric for metric in trial["income_statement"]
            if metric["metric_id"] != "revenue_total"
            and not (metric["metric_id"] == "gross_profit" and metric.get("data_type") == "derived")
        ]
        trial["income_statement"].append(_build_metric(rule, selection))

    _resolve_incoherent_revenue(
        statements, selected_evidence, facts=facts, period_end=filing.report_date,
        fiscal_period=fiscal_period, rules=mapping.get("metrics", []),
        rebuild_metric=_rebuild_revenue,
    )

    _include_uncosted_revenue(
        statements, selected_evidence, facts=facts, period_end=filing.report_date,
        rules=mapping.get("metrics", []), build_metric=_build_metric,
    )

    _include_derived_consolidated_net_income(statements)
    _include_derived_parent_net_income(statements)
    _correct_noncontrolling_sign(statements)

    _include_temporary_equity(
        statements=statements, selected_evidence=selected_evidence, facts=facts,
        period_end=filing.report_date, fiscal_period=fiscal_period,
    )

    duration_starts = [
        fact.start_date
        for fact in facts
        if fact.start_date is not None
        and fact.end_date == filing.report_date
        and not fact.dimensions
        and _duration_in_window(fact, fiscal_period)
    ]
    period_start = min(duration_starts).isoformat() if duration_starts else None
    direct = {
        "schema_version": 1,
        "ticker": ticker,
        "period": period_id,
        "period_start": period_start,
        "period_end": filing.report_date.isoformat(),
        "period_type": period_type,
        "currency": "USD",
        "scale": "million",
        "consolidation": "consolidated",
        "audit_status": "audited" if filing.form.startswith("10-K") else "unaudited",
        "accounting_basis": "US_GAAP",
        "inflation_adjustment": {"status": "not_applicable", "standard": None},
        "restatement": {"status": "original", "restated_from_publication_date": None},
        "publication_date": filing.filing_date.isoformat(),
        "source_revision": filing.accession,
        "rounding": "Values normalized from SEC XBRL unit amounts to million USD.",
        **statements,
    }
    evidence = {
        "schema_version": 1,
        "ticker": ticker,
        "period": period_id,
        "filing": {
            **asdict(filing),
            "filing_date": filing.filing_date.isoformat(),
            "report_date": filing.report_date.isoformat(),
        },
        "selected_facts": selected_evidence,
    }
    return period_id, direct, evidence


def write_normalized_filing(
    *, workspace: Path, ticker: str, period_id: str, filing: FilingRef,
    direct: dict[str, Any], evidence: dict[str, Any], cache_metadata: dict[str, Any],
    comparison_direct: dict[str, Any] | None = None,
) -> None:
    evidence_path = workspace / "raw" / "sec-filings" / ticker / f"{filing.accession}.json"
    write_json_atomic(evidence_path, evidence)
    financial_path = workspace / "data" / "financial" / ticker / f"{period_id}.json"
    write_json_atomic(financial_path, direct)
    if comparison_direct is not None:
        comparison_path = (
            workspace / "data" / "financial" / ticker / f"{comparison_direct['period']}.json"
        )
        write_json_atomic(comparison_path, comparison_direct)
    risks_path = workspace / "data" / "risks" / ticker / f"{period_id}.json"
    write_json_atomic(risks_path, {
        "schema_version": 1, "ticker": ticker, "period": period_id,
        "analysis_status": "unavailable", "unavailable_reason_code": "risk_not_authored",
        "validation_findings": [], "risks": [],
    })
    covered_periods = [period_id]
    if comparison_direct is not None:
        covered_periods.append(comparison_direct["period"])
    _upsert_source_manifest(
        workspace, ticker, covered_periods, filing, evidence_path, cache_metadata
    )


def build_comparison_period_artifact(
    direct: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any] | None:
    """Materialize the prior-year YTD column embedded in a 10-Q.

    The shared valuation engine intentionally requires three independently
    addressable authored periods for true TTM. SEC 10-Q statements already
    contain the prior-year YTD leg, so the US adapter exposes that filed column
    as a small flow-only artifact instead of downloading or guessing another
    filing. Instant balance-sheet comparisons are excluded because they normally
    represent the preceding fiscal year end, not Qn(Y-1).
    """
    if direct.get("period_type") not in {"quarterly", "annual"}:
        return None

    evidence_by_metric = {
        item["metric_id"]: item
        for item in evidence.get("selected_facts", [])
        if item.get("comparison") is not None
    }
    statements: dict[str, list[dict[str, Any]]] = {
        "income_statement": [],
        "balance_sheet": [],
        "cash_flow_statement": [],
    }
    starts: set[str] = set()
    ends: set[str] = set()

    statement_names = ["income_statement", "cash_flow_statement"]
    if direct["period_type"] == "annual":
        statement_names.append("balance_sheet")
    for statement_name in statement_names:
        for metric in direct.get(statement_name, []):
            comparison_value = metric.get("comparison_value")
            selected = evidence_by_metric.get(metric.get("metric_id"))
            comparison = (selected or {}).get("comparison")
            if comparison_value is None or comparison is None:
                continue
            if comparison.get("start_date") is not None:
                starts.add(comparison["start_date"])
            ends.add(comparison["end_date"])
            projected = dict(metric)
            projected["value"] = comparison_value
            projected["period"] = metric.get("comparison_period")
            projected["comparison_value"] = None
            projected["comparison_period"] = None
            projected["change"] = None
            projected["change_unit"] = None
            provenance = dict(metric["provenance"])
            provenance["cell_or_range"] = (
                f"{comparison['namespace']}:{comparison['concept']}#{comparison['context_id']}"
            )
            provenance["notes"] = (
                f"SEC accession {evidence['filing']['accession']}; prior-year YTD "
                "comparison column embedded in the current 10-Q."
            )
            projected["provenance"] = provenance
            statements[statement_name].append(projected)

    _include_derived_gross_profit(statements)
    _include_derived_consolidated_net_income(statements)
    _include_derived_parent_net_income(
        statements, nci_reference=direct.get("balance_sheet"))
    _correct_noncontrolling_sign(statements)

    period_id = _comparison_period(direct["period"])
    if not any(statements.values()) or len(ends) != 1:
        return None
    period_start = min(starts) if starts else None
    period_end = next(iter(ends))
    return {
        "schema_version": 1,
        "ticker": direct["ticker"],
        "period": period_id,
        "period_start": period_start,
        "period_end": period_end,
        "period_type": direct["period_type"],
        "currency": direct["currency"],
        "scale": direct["scale"],
        "consolidation": direct.get("consolidation"),
        "audit_status": "audited" if direct["period_type"] == "annual" else "unaudited",
        "accounting_basis": direct["accounting_basis"],
        "inflation_adjustment": direct["inflation_adjustment"],
        "restatement": direct["restatement"],
        "publication_date": direct.get("publication_date"),
        "source_revision": direct.get("source_revision"),
        "rounding": (
            "Prior-year YTD comparison column normalized from the cited SEC 10-Q "
            "to million USD."
        ),
        **statements,
    }


def _upsert_source_manifest(
    workspace: Path, ticker: str, period_ids: list[str], filing: FilingRef,
    evidence_path: Path, cache_metadata: dict[str, Any],
) -> None:
    path = workspace / "data" / "source-manifests" / f"{ticker}.json"
    manifest = read_json(path) if path.exists() else {"schema_version": 1, "ticker": ticker, "sources": []}
    source_id = f"sec-{filing.accession.lower()}"
    relative = evidence_path.relative_to(workspace).as_posix()
    source = {
        "source_id": source_id,
        "path": relative,
        "source_type": "sec_inline_xbrl",
        "language": "en",
        "publication_date": filing.filing_date.isoformat(),
        "periods_covered": period_ids,
        "currency": "USD",
        "scale": "million",
        "consolidation": "consolidated",
        "audit_status": "audited" if filing.form.startswith("10-K") else "unaudited",
        "accounting_basis": "US_GAAP",
        "is_primary": True,
        "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        "notes": f"SEC accession {filing.accession}; source archive hash {cache_metadata['xbrl_zip_sha256']}.",
    }
    manifest["sources"] = [item for item in manifest["sources"] if item.get("source_id") != source_id] + [source]
    manifest["sources"].sort(key=lambda item: (item.get("publication_date") or "", item["source_id"]))
    write_json_atomic(path, manifest)


def _dei_value(facts: tuple[SecFact, ...], concept: str) -> str | None:
    values = {
        fact.value.strip()
        for fact in facts
        if fact.concept == concept and any(fact.namespace.startswith(ns) for ns in _DEI_NAMESPACES)
        and not fact.dimensions and not fact.is_nil
    }
    if len(values) > 1:
        raise FactSelectionError(f"multiple DEI values for {concept}: {sorted(values)}")
    return next(iter(values), None)


def _select_fact(
    facts: tuple[SecFact, ...], period_end: date, fiscal_period: str, rule: dict[str, Any],
    *, skip_concepts: frozenset[str] = frozenset(),
) -> tuple[SecFact, SecFact | None] | None:
    """Selects by the mapping's concept order, which encodes a deliberate
    semantic preference (``OperatingLeaseLiabilityNoncurrent`` before
    ``FinanceLeaseLiabilityNoncurrent``, ``Revenues`` before
    ``RevenueFromContractWithCustomerExcludingAssessedTax``). Several
    concepts producing different values is normal and is NOT ambiguity --
    they measure different things. ``skip_concepts`` lets a caller walk to
    the next preference when the preferred one has been positively
    falsified by the statement's own arithmetic."""
    for concept in rule["concepts"]:
        if concept in skip_concepts:
            continue
        candidates = [
            fact for fact in facts
            if fact.concept == concept and not fact.is_nil and not fact.dimensions
            and fact.end_date == period_end and _period_kind_matches(fact, fiscal_period, rule["period_kind"])
            and _unit_matches(fact, rule.get("unit_kind", "money"))
            and _is_numeric_fact(fact)
        ]
        current = _unique_fact(candidates, metric_id=rule["metric_id"], concept=concept)
        if current is None:
            continue
        comparison_candidates = [
            fact for fact in facts
            if fact.concept == concept and not fact.is_nil and not fact.dimensions
            and 320 <= (period_end - fact.end_date).days <= 410
            and _period_kind_matches(fact, fiscal_period, rule["period_kind"])
            and _unit_matches(fact, rule.get("unit_kind", "money"))
            and _is_numeric_fact(fact)
        ]
        comparison_candidates = _closest_to_one_year_prior(comparison_candidates, period_end)
        comparison = _unique_fact(comparison_candidates, metric_id=rule["metric_id"], concept=concept)
        return current, comparison
    return None


def _closest_to_one_year_prior(candidates: list[SecFact], period_end: date) -> list[SecFact]:
    """Narrows a comparison window to the balance-sheet date nearest exactly one
    year before ``period_end``.

    The window spans 320-410 days to absorb 52/53-week fiscal calendars, which
    means two instants a single day apart can both fall inside it. That happens
    routinely around a standard adoption: a filer reporting 2018-12-31 also tags
    an opening balance at 2019-01-01 for the restated ASC 842 position, and the
    two carry different amounts, so the pair is a genuine conflict to
    ``_unique_fact`` and every affected quarter stopped (found 2026-08-05,
    property_plant_equipment: 598.2 million at 2018-12-31 against 563.0 million
    at 2019-01-01).

    The prior-year comparison column of a financial statement is the balance
    sheet one year earlier, so distance from that anniversary resolves it on
    economic grounds rather than by preferring whichever fact was seen first.
    A true tie is left intact and still fails closed."""
    if len(candidates) < 2:
        return candidates
    anniversary = period_end - timedelta(days=365)
    best = min(abs((fact.end_date - anniversary).days) for fact in candidates)
    return [fact for fact in candidates if abs((fact.end_date - anniversary).days) == best]


def _unique_fact(candidates: list[SecFact], *, metric_id: str, concept: str) -> SecFact | None:
    if not candidates:
        return None
    def numeric_value(fact: SecFact) -> Decimal | str:
        try:
            return Decimal(fact.value)
        except InvalidOperation:
            return fact.value

    groups = {(numeric_value(fact), fact.start_date, fact.end_date, fact.unit): fact for fact in candidates}
    if len(groups) != 1:
        # Inline XBRL may repeat the same context/unit at different declared
        # precisions (for example an exact statement value and a rounded
        # narrative value). XBRL ``decimals`` is authoritative: the larger
        # integer is the more precise fact. Equal-precision disagreements
        # remain ambiguous and fail closed.
        precision_ranked = [fact for fact in candidates if _decimal_precision(fact.decimals) is not None]
        if precision_ranked:
            best_precision = max(_decimal_precision(fact.decimals) for fact in precision_ranked)
            best = [fact for fact in precision_ranked if _decimal_precision(fact.decimals) == best_precision]
            best_values = {numeric_value(fact) for fact in best}
            if len(best_values) == 1:
                return sorted(best, key=lambda fact: fact.context_id)[0]
        detail = sorted((value, str(start), str(end), str(unit)) for value, start, end, unit in groups)
        raise FactSelectionError(f"ambiguous fact for {metric_id} via {concept}: {detail}")
    return next(iter(groups.values()))


def _decimal_precision(decimals: str | None) -> int | None:
    if decimals is None or decimals.upper() == "INF":
        return 1_000_000 if decimals else None
    try:
        return int(decimals)
    except ValueError:
        return None


def _period_kind_matches(fact: SecFact, fiscal_period: str, period_kind: str) -> bool:
    if period_kind == "instant":
        return fact.is_instant
    return not fact.is_instant and _duration_in_window(fact, fiscal_period)


def _duration_in_window(fact: SecFact, fiscal_period: str) -> bool:
    days = fact.duration_days
    low, high = _DURATION_WINDOWS[fiscal_period]
    return days is not None and low <= days <= high


def _unit_matches(fact: SecFact, unit_kind: str) -> bool:
    unit = (fact.unit or "").lower()
    return unit in ({"usd", "iso4217:usd"} if unit_kind == "money" else {"usdshares", "usd/shares", "usd-per-shares"})


def _is_numeric_fact(fact: SecFact) -> bool:
    try:
        Decimal(fact.value)
    except InvalidOperation:
        return False
    return True


def _scaled_value(fact: SecFact, *, unit_kind: str, sign: Decimal) -> int | float:
    try:
        value = Decimal(fact.value) * sign
    except InvalidOperation as exc:
        raise FactSelectionError(f"non-numeric fact selected: {fact.qualified_name}={fact.value!r}") from exc
    if unit_kind == "money":
        value /= Decimal(1_000_000)
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _comparison_period(period_id: str) -> str:
    year, suffix = period_id.split("-", 1)
    return f"{int(year) - 1}-{suffix}"


def _fact_record(fact: SecFact) -> dict[str, Any]:
    return {
        "namespace": fact.namespace, "concept": fact.concept, "value": fact.value,
        "unit": fact.unit, "context_id": fact.context_id,
        "start_date": fact.start_date.isoformat() if fact.start_date else None,
        "end_date": fact.end_date.isoformat(), "dimensions": list(fact.dimensions),
        "decimals": fact.decimals,
    }


def _resolve_incoherent_revenue(
    statements: dict[str, list[dict[str, Any]]],
    selected_evidence: list[dict[str, Any]],
    *,
    facts: tuple[SecFact, ...],
    period_end: date,
    fiscal_period: str,
    rules: list[dict[str, Any]],
    rebuild_metric: Any,
) -> None:
    """Walks ``revenue_total`` to its next mapped concept when the preferred
    one leaves the income statement arithmetically impossible.

    The concept ordering itself is never reordered: it is correct for every
    other issuer in the universe (Walmart's total ``Revenues`` legitimately
    exceeds its contract revenue by membership and other income). Only a
    positive falsification by the statement's own arithmetic justifies
    departing from it, exactly one alternative may resolve it, and the
    substitution is recorded in provenance. If no alternative resolves the
    contradiction, or more than one does, production stops rather than
    guessing which revenue the issuer meant."""
    violation = _coherence_violation(statements["income_statement"])
    if violation is None:
        return
    rule = next((r for r in rules if r["metric_id"] == "revenue_total"), None)
    current_metric = next(
        (m for m in statements["income_statement"] if m["metric_id"] == "revenue_total"), None
    )
    if rule is None or current_metric is None:
        raise FactSelectionError(f"income statement is internally impossible: {violation}")

    selected_cell = (current_metric.get("provenance") or {}).get("cell_or_range") or ""
    rejected = {selected_cell.split("}")[-1].split("#")[0]} or {rule["concepts"][0]}

    resolutions = []
    for _ in range(len(rule["concepts"])):
        selection = _select_fact(
            facts, period_end, fiscal_period, rule, skip_concepts=frozenset(rejected)
        )
        if selection is None:
            break
        candidate_concept = selection[0].concept
        rejected = rejected | {candidate_concept}
        trial = {name: list(rows) for name, rows in statements.items()}
        rebuild_metric(trial, selection)
        _include_derived_gross_profit(trial)
        if _coherence_violation(trial["income_statement"]) is None:
            resolutions.append((candidate_concept, selection, trial))

    if len(resolutions) != 1:
        raise FactSelectionError(
            f"income statement is internally impossible and "
            f"{len(resolutions)} alternative revenue concepts resolve it: {violation}"
        )
    concept, selection, trial = resolutions[0]
    original = (current_metric.get("provenance") or {}).get("cell_or_range")
    statements["income_statement"][:] = trial["income_statement"]
    for metric in statements["income_statement"]:
        if metric["metric_id"] == "revenue_total":
            metric["provenance"]["notes"] = (
                f"{metric['provenance'].get('notes', '')} Preferred concept rejected "
                f"({original}): it left the income statement arithmetically impossible "
                f"({violation}); {concept} is the only mapped alternative that resolves it."
            ).strip()
    for evidence in selected_evidence:
        if evidence["metric_id"] == "revenue_total":
            evidence["current"] = _fact_record(selection[0])
            evidence["comparison"] = _fact_record(selection[1]) if selection[1] else None


def _include_derived_consolidated_net_income(
    statements: dict[str, list[dict[str, Any]]]
) -> None:
    """Fills a missing consolidated net income from its definition.

    ``ProfitLoss`` is the consolidated total in US-GAAP and ``NetIncomeLoss``
    is the parent-attributable figure. Treating the latter as a fallback for
    the former made consolidated income equal parent income while a
    noncontrolling interest was reported separately, and the attribution
    identity then failed by exactly that interest (NWL 2018-Q2: parent 185.0,
    noncontrolling 3.7, "consolidated" 185.0). ``NetIncomeLoss`` has therefore
    been removed from the consolidated mapping.

    When an issuer tags no consolidated total, the figure is the sum of its
    two independently reported components rather than a substitute for one of
    them. It is marked derived so the attribution check can skip a comparison
    that would be true by construction."""
    by_id = {metric["metric_id"]: metric for metric in statements["income_statement"]}
    if "net_profit_for_period" in by_id:
        return
    parent = by_id.get("net_profit_attributable_parent")
    noncontrolling = by_id.get("net_profit_attributable_noncontrolling")
    if not parent or parent.get("value") is None:
        return
    nci_value = (noncontrolling or {}).get("value") or 0
    comparison_value = None
    if parent.get("comparison_value") is not None:
        comparison_value = parent["comparison_value"] + (
            (noncontrolling or {}).get("comparison_value") or 0
        )
    provenance = dict(parent["provenance"])
    provenance["formula"] = (
        "net_profit_for_period = net_profit_attributable_parent "
        "+ net_profit_attributable_noncontrolling"
    )
    provenance["notes"] = (
        "Issuer tagged no consolidated ProfitLoss; summed from the two reported "
        "attribution components."
    )
    statements["income_statement"].append({
        "metric_id": "net_profit_for_period",
        "name": "Net Profit for the Period",
        "value": parent["value"] + nci_value,
        "unit": parent["unit"],
        "period": parent.get("period"),
        "comparison_value": comparison_value,
        "comparison_period": parent.get("comparison_period") if comparison_value is not None else None,
        "change": None,
        "change_unit": None,
        "data_type": "derived",
        "status": "available",
        "reason": None,
        "provenance": provenance,
    })


def _correct_noncontrolling_sign(statements: dict[str, Any]) -> None:
    """Azinlik payi ZARARININ isareti bazen ters etiketlenir.

    Merck ayni gercegi iki bildirimde ters isaretle verdi. 2022-Q1'in kendi
    10-Q'sunda `NetIncomeLossAttributableToNoncontrollingInterest` -3.000.000;
    2023-Q1 10-Q'sunun karsilastirma sutununda ayni donem icin +3.000.000 --
    ayni belgede duran `IncomeLossFromContinuingOperationsAttributable-
    ToNoncontrollingEntity` ise hâlâ -3.000.000. 4310 - 3 = 4307 tutuyor,
    4310 + 3 = 4313 tutmuyor.

    Duzeltme yalniz TAM esitlikte yapilir: etiketli deger ozdesligi bozuyor ve
    tam tersi ozdesligi birebir sagliyorsa. Bu, tesadufen olamaz -- ozdeslik
    nci = konsolide - ana ortaklik ister, ters isaret nci = ana ortaklik -
    konsolide demektir ve ikisi yalnizca nci sifirken cakisir. Baska her
    durumda dokunulmaz ve dogrulama hatayi vermeye devam eder.

    Iki sutun bagimsiz degerlendirilir: bir sutunun etiketi dogru, digerininki
    bozuk olabilir -- MRK'da tam olarak bu oldu."""
    by_id = {metric["metric_id"]: metric for metric in statements["income_statement"]}
    parent = by_id.get("net_profit_attributable_parent")
    nci = by_id.get("net_profit_attributable_noncontrolling")
    total = by_id.get("net_profit_for_period")
    if not parent or not nci or not total:
        return
    corrected = []
    for field, label in (("value", "cari"), ("comparison_value", "karsilastirma")):
        p, n, t = parent.get(field), nci.get(field), total.get(field)
        if p is None or n is None or t is None or n == 0:
            continue
        if p + n == t:
            continue
        if p - n != t:
            continue
        nci[field] = -n
        corrected.append(f"{label}: {n} -> {-n}")
    if corrected:
        provenance = dict(nci.get("provenance") or {})
        note = (
            "Issuer tagged the noncontrolling attribution with the wrong sign; "
            "the negation satisfies parent + noncontrolling = consolidated exactly. "
            + "; ".join(corrected)
        )
        provenance["notes"] = (
            f"{provenance['notes']} {note}" if provenance.get("notes") else note
        )
        nci["provenance"] = provenance


def _include_derived_parent_net_income(
    statements: dict[str, list[dict[str, Any]]],
    *,
    nci_reference: list[dict[str, Any]] | None = None,
) -> None:
    """Fills a missing parent-attributable net income from its definition.

    The mirror of ``_include_derived_consolidated_net_income``. An issuer that
    tags ``ProfitLoss`` but never ``NetIncomeLoss`` leaves the parent line
    empty, and since every earnings method is defined on parent income --
    P/E, earnings yield, EV/EBIT -- all of them fall at once. Seven of the
    sixty companies in the score-IC universe do exactly this (AVGO, BSX, CAT,
    CMI, ITW, MNST, PH) and sat at two or fewer available methods in all
    twenty-five months (found 2026-08-06).

    Two cases, and the second is the one that needs care:

    * a noncontrolling interest is reported, so the parent share is the
      attribution identity ``consolidated - noncontrolling``;
    * nothing is reported for the noncontrolling interest. Its absence is not
      by itself proof of zero, so the balance sheet is consulted: only when
      there is no noncontrolling interest in equity either does the company
      genuinely have none, and consolidated income is then the parent's. If
      equity does carry one, the parent line stays unavailable rather than
      being guessed.
    """
    by_id = {metric["metric_id"]: metric for metric in statements["income_statement"]}
    if "net_profit_attributable_parent" in by_id:
        return
    consolidated = by_id.get("net_profit_for_period")
    if not consolidated or consolidated.get("value") is None:
        return
    noncontrolling = by_id.get("net_profit_attributable_noncontrolling")

    if noncontrolling is None or noncontrolling.get("value") is None:
        # Azinlik payinin VARLIGI sirket duzeyinde bir olgudur, sutun duzeyinde
        # degil. 10-Q'nun karsilastirma sutunu bilanco tasimaz (o an-degeri
        # onceki mali yil sonudur, Qn(Y-1) degil) -- bu bilincli bir karar. O
        # yuzden karsilastirma artifact'i icin ayni FILING'in cari sutunundaki
        # bilanco referans alinir. Aksi halde sonuc sirketin ekonomisine degil
        # artifact'in dolulguna baglanir: ITW'nin 2023-Q1 karsilastirmasinda
        # turetilip 2023-FY'sinde turetilmemesi, ya da AVGO/MNST'nin cari
        # sutunda turetilip karsilastirma bacaginda turetilememesi yuzunden
        # TTM zincirinin kopmasi (ikisi de 2026-08-06'da bulundu).
        balance_sheet = statements.get("balance_sheet") or nci_reference or []
        if not balance_sheet:
            return
        equity_nci = next(
            (m for m in balance_sheet if m["metric_id"] == "noncontrolling_interests"), None,
        )
        if equity_nci is not None and (equity_nci.get("value") or 0) != 0:
            return
        nci_value = 0
        nci_comparison = 0
        formula = "net_profit_attributable_parent = net_profit_for_period"
        note = (
            "Issuer tagged no NetIncomeLoss and reports no noncontrolling interest "
            "in income or in equity, so consolidated income is the parent's."
        )
    else:
        nci_value = noncontrolling["value"]
        nci_comparison = noncontrolling.get("comparison_value")
        formula = (
            "net_profit_attributable_parent = net_profit_for_period "
            "- net_profit_attributable_noncontrolling"
        )
        note = (
            "Issuer tagged no NetIncomeLoss; derived from the attribution identity "
            "against the reported noncontrolling interest."
        )

    comparison_value = None
    if consolidated.get("comparison_value") is not None and nci_comparison is not None:
        comparison_value = consolidated["comparison_value"] - nci_comparison

    provenance = dict(consolidated["provenance"])
    provenance["formula"] = formula
    provenance["notes"] = note
    statements["income_statement"].append({
        "metric_id": "net_profit_attributable_parent",
        "name": "Net Profit Attributable to Parent",
        "value": consolidated["value"] - nci_value,
        "unit": consolidated["unit"],
        "period": consolidated.get("period"),
        "comparison_value": comparison_value,
        "comparison_period": (
            consolidated.get("comparison_period") if comparison_value is not None else None
        ),
        "change": None,
        "change_unit": None,
        "data_type": "derived",
        "status": "available",
        "reason": None,
        "provenance": provenance,
    })


def _include_uncosted_revenue(
    statements: dict[str, list[dict[str, Any]]],
    selected_evidence: list[dict[str, Any]],
    *,
    facts: tuple[SecFact, ...],
    period_end: date,
    rules: list[dict[str, Any]],
    build_metric: Any,
) -> None:
    """Extracts the revenue component that carries no cost of sales, when the
    issuer discloses one and the reported gross profit requires it.

    Gross profit is struck against merchandise sales, not against every
    revenue stream. A membership warehouse books membership fees inside total
    revenue with no matched cost, so ``revenue_total + cost_of_sales`` exceeds
    the reported gross profit by exactly those fees (COST fiscal 2019 Q1:
    35,069 total revenue, 30,623 merchandise costs, 3,688 gross profit, 758
    residual). Fifteen historical quarters stopped on that gap.

    The residual is never taken as the answer -- that would close the identity
    by construction and make it unfalsifiable. It only says how much to look
    for. The amount is accepted solely when a disclosed revenue component,
    reported as a dimensioned breakdown of the same period, matches it; if no
    single component matches, nothing is written and the validator still
    fails."""
    by_id = {metric["metric_id"]: metric for metric in statements["income_statement"]}
    revenue, cost = by_id.get("revenue_total"), by_id.get("cost_of_sales")
    gross = by_id.get("gross_profit")
    if not revenue or not cost or not gross or gross.get("data_type") == "derived":
        return
    values = (revenue.get("value"), cost.get("value"), gross.get("value"))
    if any(value is None for value in values):
        return
    residual = values[0] + values[1] - values[2]
    if residual <= 0:
        return

    rule = next((item for item in rules if item["metric_id"] == "revenue_total"), None)
    if rule is None:
        return
    scale = Decimal(str(residual)) * Decimal("1000000")
    matches = [
        fact for fact in facts
        if fact.concept in rule["concepts"] and fact.dimensions and not fact.is_nil
        and fact.end_date == period_end and _is_numeric_fact(fact)
        and abs(Decimal(fact.value) - scale) <= Decimal("500000")
    ]
    unique = {fact.value for fact in matches}
    if len(unique) != 1:
        return

    metric = build_metric(
        {**rule, "metric_id": "revenue_without_matched_cost_of_sales",
         "name": "Revenue Without Matched Cost of Sales"},
        (matches[0], None),
    )
    metric["provenance"]["notes"] = (
        f"{metric['provenance'].get('notes', '')} Disclosed revenue component carrying no "
        "cost of sales; identified because reported gross profit excludes it, and accepted "
        "only because a disclosed breakdown matches that amount."
    ).strip()
    statements["income_statement"].append(metric)
    selected_evidence.append({
        "metric_id": "revenue_without_matched_cost_of_sales",
        "current": _fact_record(matches[0]), "comparison": None,
    })


def _coherence_violation(income_statement: list[dict[str, Any]]) -> str | None:
    """Returns a description when the income statement is arithmetically
    impossible, else None.

    Operating profit exceeding gross profit is NOT a violation: other
    operating income -- equity-method earnings from joint ventures,
    benefit-plan non-service income, divestiture gains -- legitimately
    lifts it above the gross line. GIS reports exactly that (2026-Q1:
    1,532.8 gross, 1,725.8 operating), so a rule keyed on that comparison
    halts valid data.

    What is genuinely impossible is a derived gross profit that is
    negative by MORE than the issuer's entire total revenue while
    operating profit is positive: closing that gap would require other
    operating income larger than all revenue, contradicting the meaning of
    ``revenue_total``. That signature identifies a mis-selected revenue
    concept rather than a bad year.

    This gate exists because ``gross_profit`` is usually derived from
    ``revenue_total + cost_of_sales`` when the issuer omits the GrossProfit
    concept, which makes the shared ``gross_profit_mismatch`` identity
    check tautological: it compares the derived subtotal against the two
    operands it was just built from and can never fail. Found 2026-08-04,
    GIS: ``us-gaap:Revenues`` was tagged 2,037.8 million USD for a fiscal
    year whose cost of goods sold was 12,925.1 million USD, producing a
    -10,887.3 million USD "gross profit" alongside +3,431.7 million USD of
    operating profit. Every file-local validation passed and the decision
    layer rejected the company as untrustworthy data for months."""
    by_id = {metric["metric_id"]: metric for metric in income_statement}
    gross = by_id.get("gross_profit")
    operating = by_id.get("operating_profit_before_investment_activities")
    if not gross or not operating:
        return None
    if gross.get("data_type") != "derived":
        # A reported GrossProfit fact is cross-checked by the shared
        # income-statement identity, which is falsifiable on its own.
        return None
    revenue = by_id.get("revenue_total")
    gross_value = gross.get("value")
    operating_value = operating.get("value")
    revenue_value = revenue.get("value") if revenue else None
    if None in (gross_value, operating_value, revenue_value):
        return None
    if not (gross_value < 0 and operating_value > 0 and abs(gross_value) > revenue_value):
        return None
    return (
        f"derived gross_profit ({gross_value}) is negative by more than total "
        f"revenue ({revenue_value}) while operating_profit_before_investment_activities "
        f"is positive ({operating_value}); closing that gap would need other "
        "operating income exceeding all revenue"
    )


def _include_derived_gross_profit(
    statements: dict[str, list[dict[str, Any]]]
) -> None:
    """Fill a missing US-GAAP gross-profit subtotal from its exact identity.

    Some retailers and consumer issuers present revenue and cost of sales but
    omit the GrossProfit XBRL concept. ``cost_of_sales`` is normalized as a
    negative amount, so revenue + cost is the filed subtotal. A directly
    reported gross-profit fact always wins.
    """
    by_id = {
        metric["metric_id"]: metric
        for metric in statements["income_statement"]
    }
    if "gross_profit" in by_id:
        return
    revenue = by_id.get("revenue_total")
    cost = by_id.get("cost_of_sales")
    if not revenue or not cost or revenue.get("value") is None or cost.get("value") is None:
        return
    comparison_value = None
    if revenue.get("comparison_value") is not None and cost.get("comparison_value") is not None:
        comparison_value = revenue["comparison_value"] + cost["comparison_value"]
    provenance = dict(revenue["provenance"])
    provenance["cell_or_range"] = (
        f"{revenue['provenance'].get('cell_or_range')} + "
        f"{cost['provenance'].get('cell_or_range')}"
    )
    provenance["formula"] = "gross_profit = revenue_total + cost_of_sales"
    provenance["notes"] = (
        "Mechanically derived from two facts in the same SEC filing; "
        "cost_of_sales uses the canonical negative-outflow sign."
    )
    statements["income_statement"].append({
        "metric_id": "gross_profit",
        "name": "Gross Profit",
        "value": revenue["value"] + cost["value"],
        "unit": revenue["unit"],
        "period": revenue.get("period"),
        "comparison_value": comparison_value,
        "comparison_period": revenue.get("comparison_period") if comparison_value is not None else None,
        "change": None,
        "change_unit": None,
        "data_type": "derived",
        "status": "available",
        "reason": None,
        "provenance": provenance,
    })


def _include_temporary_equity(
    *, statements: dict[str, list[dict[str, Any]]], selected_evidence: list[dict[str, Any]],
    facts: tuple[SecFact, ...], period_end: date, fiscal_period: str,
) -> None:
    specifications = (
        (
            "redeemable_noncontrolling_interests_adjustment",
            [
                "RedeemableNoncontrollingInterestEquityCarryingAmount",
                "TemporaryEquityCarryingAmountAttributableToNoncontrollingInterest",
                # A redeemable interest measured at fair value rather than
                # carrying amount is tagged with a different element, and the
                # mezzanine section is otherwise identical. GIS reports its
                # redeemable interest this way (778.9 million at 2015-05-31),
                # which left assets short of liabilities plus equity by exactly
                # that amount and stopped thirteen historical quarters on
                # balance_sheet_inequality (found 2026-08-05).
                "RedeemableNoncontrollingInterestEquityOtherFairValue",
                "RedeemableNoncontrollingInterestEquityFairValue",
                "RedeemableNoncontrollingInterestEquityCommonFairValue",
            ],
            ("noncontrolling_interests", "total_equity"),
        ),
        (
            "temporary_equity_attributable_parent_adjustment",
            [
                "TemporaryEquityCarryingAmountAttributableToParent",
                "PreferredStockValue",
                "PreferredStockValueOutstanding",
                # Zorunlu donusturulebilir imtiyazli hisse ihrac eden sirketler
                # birikmis temettu yukumlulugunu ayri bir mezzanine satiri
                # olarak sunar: yukumluluk degildir (odeme sirketin elinde),
                # ozkaynak da degildir (imtiyazli pay sahibine aittir). AVGO'nun
                # 2021-10-31 bilancosu bu 27M yuzunden 27M acik veriyordu
                # (bulundu 2026-08-05).
                "TemporaryEquityPreferredStockDividendObligation",
            ],
            ("equity_attributable_to_parent", "total_equity"),
        ),
    )
    by_id = {metric["metric_id"]: metric for metric in statements["balance_sheet"]}

    # A sheet can carry more than one mezzanine line at once, and only their
    # SUM is the residual. KHC's 2015 column sits 8,343 short with 8,320 of
    # preferred stock beside 23 of redeemable noncontrolling interest, so
    # testing each candidate on its own rejected both and left the year
    # unbalanced (found 2026-08-05). Candidates are therefore gathered first
    # and the combination that closes the gap is chosen; an ambiguous or
    # unexplained gap still applies nothing.
    candidates = []
    for evidence_id, concepts, target_metric_ids in specifications:
        selected = _select_temporary_equity(
            facts, period_end, fiscal_period, evidence_id, concepts,
        )
        if selected is None:
            continue
        current, comparison = selected
        candidates.append((
            evidence_id, target_metric_ids, current,
            _scaled_value(current, unit_kind="money", sign=Decimal(1)) if current else None,
            comparison,
            _scaled_value(comparison, unit_kind="money", sign=Decimal(1)) if comparison else None,
        ))

    applied_current = _closing_combination(by_id, [c[3] for c in candidates], field="value")
    applied_comparison = _closing_combination(
        by_id, [c[5] for c in candidates], field="comparison_value",
    )

    # Iki sutun iki ayri bilancodur ve bagimsiz kapanir. Bir mezzanine kalemi
    # yil icinde itfa edilmisse karsilastirma sutununda maddi, cari sutunda
    # sifir olur: AVGO'nun zorunlu donusturulebilir imtiyazli temettu
    # yukumlulugu 2021-10-31'de 27M, 2022-10-30'da 0'dir. Karsilastirma
    # duzeltmesi cari duzeltmenin arkasina kilitliyken bu kalem hic
    # uygulanmiyordu ve 2021 sutunu 27M acik kaliyordu (bulundu 2026-08-05).
    # KHC'de gizli kalmisti cunku orada ayni satir iki sutunda da vardi.
    for index, (evidence_id, target_metric_ids, current, current_value, comparison, comparison_value) in enumerate(candidates):
        current_applies = index in applied_current
        comparison_applies = index in applied_comparison
        if not current_applies and not comparison_applies:
            continue
        for metric_id in target_metric_ids:
            metric = by_id.get(metric_id)
            if metric is None:
                continue
            if current_applies and current_value is not None:
                metric["value"] += current_value
            if (
                metric.get("comparison_value") is not None
                and comparison_value is not None
                and comparison_applies
            ):
                metric["comparison_value"] += comparison_value
            metric["data_type"] = "derived"
            evidence_fact = current or comparison
            metric["provenance"]["formula"] = (
                f"reported {metric_id} + {evidence_fact.qualified_name}"
            )
            metric["provenance"]["cell_or_range"] += (
                f" + {evidence_fact.qualified_name}#{evidence_fact.context_id}"
            )
            metric["provenance"]["notes"] += (
                " Includes separately presented temporary equity."
            )
        selected_evidence.append({
            "metric_id": evidence_id,
            "current": _fact_record(current) if current else None,
            "comparison": _fact_record(comparison) if comparison else None,
        })


def _closing_combination(
    by_id: dict[str, dict[str, Any]], amounts: list[Any], *, field: str,
) -> set[int]:
    """Indices of the mezzanine amounts whose sum is the balance-sheet residual.

    Returns an empty set when the gap is already closed, when no combination
    explains it, or when more than one does -- an unexplained or ambiguous gap
    is never papered over."""
    from itertools import combinations

    usable = [(index, value) for index, value in enumerate(amounts) if value is not None]
    matching = [
        set(index for index, _ in subset)
        for size in range(len(usable), 0, -1)
        for subset in combinations(usable, size)
        if _temporary_equity_closes_balance_gap(
            by_id, sum(value for _, value in subset), field=field,
        )
    ]
    if not matching:
        # A sheet that already balances needs no adjustment, which is the same
        # answer as one nothing explains: apply nothing either way.
        return set()
    largest = max(len(item) for item in matching)
    winners = [item for item in matching if len(item) == largest]
    return winners[0] if len(winners) == 1 else set()


def _temporary_equity_closes_balance_gap(
    by_id: dict[str, dict[str, Any]], adjustment: int | float, *, field: str = "value",
) -> bool:
    """Whether a mezzanine amount is the exact residual of the balance sheet.

    ``field`` selects which column is tested. The prior-year column has its own
    balance sheet and needs its own test: an issuer can present the mezzanine
    line outside equity in one year and inside it in the next. PEP's fiscal
    2018 sheet needs its 41 of preferred stock added, while the 2017 column
    already balances at 68,823 + 10,981 = 79,804, so carrying the adjustment
    across unconditionally overstated that year by exactly 41 and failed every
    quarter reaching back to it (found 2026-08-05)."""
    assets = by_id.get("total_assets", {}).get(field)
    liabilities = by_id.get("total_liabilities", {}).get(field)
    equity = by_id.get("total_equity", {}).get(field)
    if assets is None or liabilities is None or equity is None:
        return True
    gap = Decimal(str(assets)) - Decimal(str(liabilities)) - Decimal(str(equity))
    candidate = Decimal(str(adjustment))
    tolerance = max(Decimal("0.001"), abs(Decimal(str(assets))) * Decimal("0.000001"))
    return abs(gap - candidate) <= tolerance


def _is_zero(fact: SecFact | None) -> bool:
    if fact is None:
        return True
    try:
        return Decimal(fact.value) == 0
    except (InvalidOperation, TypeError):
        return False


def _select_comparison_only(
    facts: tuple[SecFact, ...], period_end: date, concepts: list[str],
) -> tuple[None, SecFact] | None:
    """Yalniz onceki-yil sutununda bulunan bir mezzanine kalemi.

    Cari donemde ayni konseptten hicbir fact yoksa aranir. Aday tarih penceresi
    `_select_temporary_equity`'nin diger dallariyla ayni: bir yil oncesine
    karsilik gelen 320-410 gunluk aralik. Birden fazla aday tarih varsa en
    yakini alinir; hicbiri yoksa None doner ve eski davranis surer."""
    window = sorted(
        {fact.end_date for fact in facts if 320 <= (period_end - fact.end_date).days <= 410},
        reverse=True,
    )
    for concept in concepts:
        if any(f.concept == concept and not f.dimensions and not f.is_nil
               and f.is_instant and f.end_date == period_end for f in facts):
            return None                      # cari donemde var; bu dal onun isi degil
        for candidate_date in window:
            match = [f for f in facts
                     if f.concept == concept and not f.dimensions and not f.is_nil
                     and f.is_instant and f.end_date == candidate_date and f.unit == "USD"]
            if len(match) == 1:
                return None, match[0]
    return None


def _select_temporary_equity(
    facts: tuple[SecFact, ...], period_end: date, fiscal_period: str,
    metric_id: str, concepts: list[str],
) -> tuple[SecFact | None, SecFact | None] | None:
    # Konsept listesi bir tercih siralamasidir ve sirf ESLESEN ilk konsepti
    # almak yetmiyor: sifir degerli bir kalem bir mezzanine sunumu degildir,
    # ama listede once geliyorsa arkasindaki maddi kalemi golgeler. AVGO 2022
    # 10-K'sinda `PreferredStockValue` iki sutunda da 0'dir ve zorunlu
    # donusturulebilir imtiyazli temettu yukumlulugunu (2021'de 27M) gizliyordu
    # (bulundu 2026-08-05). Bu yuzden once iki sutundan birinde sifir olmayan
    # bir konsept aranir; hepsi sifirsa eski davranis korunur.
    fallback: tuple[SecFact, SecFact | None] | None = None
    for concept in concepts:
        selected = _select_fact(
            facts, period_end, fiscal_period,
            {"metric_id": metric_id, "period_kind": "instant", "concepts": [concept]},
        )
        if selected is None:
            continue
        if fallback is None:
            fallback = selected
        if not (_is_zero(selected[0]) and _is_zero(selected[1])):
            return selected
    if fallback is not None:
        return fallback
    # Kalem YALNIZ karsilastirma sutununda olabilir. Bir mezzanine satiri yil
    # icinde tamamen ortadan kalkarsa filing onu cari donem icin hic
    # etiketlemez, yalniz onceki yil icin tasir: DE'nin FY2020 10-K'si
    # `RedeemableNoncontrollingInterestEquityCarryingAmount`i tek bir fact
    # olarak, 2019-11-03 icin 14M seklinde bildirir ve 2020 icin hicbir sey
    # yazmaz. Aday uretimi cari doneme capali oldugu icin hic aday olusmuyor,
    # 2019 sutunu 14 acik kaliyor ve 2021-2022'nin butun aylari bu tek satir
    # yuzunden dusuyordu (bulundu 2026-08-06).
    #
    # AVGO'daki hâlin daha derini: orada kalem cari sutunda SIFIR'di, burada
    # HIC YOK. Bu yuzden (None, comparison) donmek gerekiyor -- cari sutuna
    # hicbir sey uygulanmaz, karsilastirma sutunu kendi basina kapanabilir.
    comparison_only = _select_comparison_only(facts, period_end, concepts)
    if comparison_only is not None:
        return comparison_only
    current = _aggregate_stock_class_facts(facts, period_end, concepts, metric_id)
    if current is None:
        return None
    comparison_dates = sorted({
        fact.end_date for fact in facts
        if 320 <= (period_end - fact.end_date).days <= 410
    }, reverse=True)
    comparison = next((
        aggregate for candidate_date in comparison_dates
        if (aggregate := _aggregate_stock_class_facts(
            facts, candidate_date, concepts, metric_id,
        )) is not None
    ), None)
    return current, comparison


def _aggregate_stock_class_facts(
    facts: tuple[SecFact, ...], period_end: date, concepts: list[str], metric_id: str,
) -> SecFact | None:
    for concept in concepts:
        candidates = [
            fact for fact in facts
            if fact.concept == concept and not fact.is_nil and fact.is_instant
            and fact.end_date == period_end and _unit_matches(fact, "money")
            and _is_numeric_fact(fact) and len(fact.dimensions) == 1
            and fact.dimensions[0][0].endswith("}StatementClassOfStockAxis")
        ]
        if not candidates:
            continue
        by_member: dict[str, list[SecFact]] = {}
        for fact in candidates:
            by_member.setdefault(fact.dimensions[0][1], []).append(fact)
        selected_members = []
        for member, member_facts in by_member.items():
            values = {Decimal(fact.value) for fact in member_facts}
            if len(values) != 1:
                raise FactSelectionError(
                    f"ambiguous stock-class fact for {metric_id} via {concept}, "
                    f"member {member}: {sorted(values)}"
                )
            selected_members.append(sorted(member_facts, key=lambda fact: fact.context_id)[0])
        total = sum(Decimal(fact.value) for fact in selected_members)
        base = sorted(selected_members, key=lambda fact: fact.context_id)[0]
        return SecFact(
            namespace=base.namespace,
            concept=base.concept,
            value=format(total, "f"),
            unit=base.unit,
            context_id="class-sum:" + "+".join(
                fact.context_id for fact in sorted(selected_members, key=lambda fact: fact.context_id)
            ),
            start_date=None,
            end_date=period_end,
            dimensions=(),
            decimals=base.decimals,
            is_nil=False,
        )
    return None
