#!/usr/bin/env python3
"""Build a valuation_comparison_observations artifact for one sector_peer
method_family_id, mechanically, from each universe member's already-computed
pipeline output -- no NotebookLM/LLM call, no new calculation.

Two source shapes are supported:
- A valuation multiple/yield already present in a member's own
  data/valuation-results/{ticker}/{as_of}/{ctx}/current.json method_results[]
  (matched by method_id == method_family_id). Reads canonical_value.
- A derived ratio already present in a member's own most recent
  data/financial/{ticker}/{period}-derived-ratios.json (matched by
  metric_id == method_family_id, searched from the newest period backward
  until found).

Never invents a value: a member whose source is missing or whose value
status isn't "available" is written with status="unavailable" and an
explicit reason_code, exactly as the sector_peer engine already expects
(kap_oda_extract.py-style fail-closed convention used throughout this repo).

Usage:
    python -m fundamental_pipeline.valuation.comparison.build_peer_observations \\
        --universe config/valuation/comparison/peer-universes/durable-consumer-goods.json \\
        --method gross_margin --as-of 2026-07-28 \\
        --output config/valuation/comparison/observations/durable-consumer-goods.gross_margin.json
"""

from __future__ import annotations

import argparse
import glob
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]

# method_family_ids that live in valuation-results' method_results[] (keyed
# by method_id there) rather than in a period's derived-ratios.json.
VALUATION_METHOD_FAMILIES = {
    "val.method.pe.reported_parent",
    "val.method.earnings_yield.reported_parent",
    "val.method.price_to_book.parent_equity",
    "val.method.fcf_yield.standard_equity",
    "val.method.ev_to_ebit.core",
    "val.method.ev_to_ebitda.canonical",
}

DERIVED_RATIO_SECTIONS = ("growth", "margins", "liquidity", "leverage", "returns", "cash_generation")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_valuation_result(ticker: str, as_of: str, root: Path = REPO_ROOT) -> Path | None:
    candidates = sorted(root.glob(f"data/valuation-results/{ticker}/{as_of}/*/current.json"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: (
        _read_json(path).get("temporal_context", {}).get("valuation_cutoff_at") or "",
        path.as_posix(),
    ))


def _latest_derived_ratios(ticker: str, root: Path = REPO_ROOT) -> Path | None:
    candidates = sorted(root.glob(f"data/financial/{ticker}/*-derived-ratios.json"))
    return candidates[-1] if candidates else None


def _relative(path: Path, root: Path = REPO_ROOT) -> str:
    return path.relative_to(root).as_posix()


def _observation_from_valuation_method(
    ticker: str, method_family_id: str, as_of: str, root: Path = REPO_ROOT
) -> dict[str, Any]:
    path = _latest_valuation_result(ticker, as_of, root)
    if path is None:
        return _unavailable(
            ticker, "comparison.source_missing",
            provenance=[_expected_source("valuation_results", ticker,
                                         f"data/valuation-results/{ticker}/{as_of}")],
        )
    doc = _read_json(path)
    match = next((m for m in doc.get("method_results", []) if m.get("method_id") == method_family_id), None)
    if match is None:
        return _unavailable(ticker, "comparison.method_not_present", provenance=[_prov("valuation_results", doc.get("artifact_id", ""), path, root)])
    canonical = match.get("canonical_value") or {}
    if canonical.get("status") != "available" or canonical.get("value") is None:
        return _unavailable(ticker, "comparison.method_regime_mismatch", provenance=[_prov("valuation_results", doc.get("artifact_id", ""), path, root)])
    cutoff = doc.get("temporal_context", {}).get("valuation_cutoff_at") or f"{as_of}T20:59:59Z"
    return _available(
        ticker=ticker, value=str(canonical["value"]), as_of=as_of, cutoff_instant=cutoff,
        formula_ref=match.get("formula_ref", {}).get("formula_id", method_family_id),
        provenance=[_prov("valuation_results", doc.get("artifact_id", ""), path, root)],
    )


def _observation_from_derived_ratio(
    ticker: str, method_family_id: str, as_of: str, root: Path = REPO_ROOT
) -> dict[str, Any]:
    path = _latest_derived_ratios(ticker, root)
    if path is None:
        return _unavailable(
            ticker, "comparison.source_missing",
            provenance=[_expected_source("financial_derived", ticker,
                                         f"data/financial/{ticker}")],
        )
    doc = _read_json(path)
    match = None
    for section in DERIVED_RATIO_SECTIONS:
        match = next((m for m in doc.get(section, []) if m.get("metric_id") == method_family_id), None)
        if match is not None:
            break
    period = doc.get("period", as_of)
    prov = [_prov("financial_derived_ratios", f"financial-derived-ratios:{ticker}:{period}", path, root)]
    if match is None:
        return _unavailable(ticker, "comparison.method_not_present", provenance=prov)
    value = match.get("value")
    status = match.get("status")
    if status == "unavailable" or value is None:
        return _unavailable(ticker, "comparison.rank_ineligible_value", provenance=prov)
    return _available(
        ticker=ticker, value=str(value), as_of=as_of, cutoff_instant=f"{as_of}T20:59:59Z",
        formula_ref=match.get("formula_id", method_family_id), provenance=prov,
    )



def _expected_source(artifact_type: str, ticker: str, relative_path: str) -> dict[str, Any]:
    """Provenance for a member whose source artifact was looked for and not found.

    ``provenance_refs`` is required to carry at least one entry, so the
    ``source_missing`` branch could never produce a schema-valid observation --
    it passed no provenance at all. That branch had simply never been reached:
    every universe member always had a valuation result. It becomes reachable
    as soon as one member is skipped for an unrelated reason, and then the whole
    peer comparison fails on ``[] should be non-empty`` naming an innocent
    subject (found 2026-08-06, when NVDA and AVGO were skipped for an
    unresolved corporate action and AAPL's comparison was the one that failed).

    An absence is still evidence, and it has a location: the path that was
    searched. Recording it keeps the member inside the coverage denominator,
    which is the honest reading -- the peer exists and has no usable value.
    """
    return {
        "artifact_type": artifact_type,
        "artifact_id": f"{artifact_type}:{ticker}:absent",
        "relative_path": relative_path,
    }

def _prov(artifact_type: str, artifact_id: str, path: Path, root: Path = REPO_ROOT) -> dict[str, Any]:
    return {"artifact_type": artifact_type, "artifact_id": artifact_id or artifact_type, "relative_path": _relative(path, root)}


def _available(*, ticker: str, value: str, as_of: str, cutoff_instant: str, formula_ref: str, provenance: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "as_of_date": as_of,
        "cutoff_instant": cutoff_instant,
        "value": {"status": "available", "value": _canonical_decimal(value)},
        "status": "available",
        "financial_anchor_ref": None,
        "claim_basis": "reported",
        "lease_basis": None,
        "corporate_action_basis": "none",
        "formula_ref": formula_ref,
        "policy_version": "1.0.0",
        "confidence": "high",
        "provenance_refs": provenance,
    }


def _canonical_decimal(value: str) -> str:
    """Normalize lexical float forms to the governed decimal envelope syntax."""
    try:
        normalized = format(Decimal(value), "f")
    except InvalidOperation:
        return value
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "0" if normalized in {"-0", ""} else normalized


def _unavailable(ticker: str, reason_code: str, provenance: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "as_of_date": None,
        "cutoff_instant": None,
        "value": {"status": "unavailable", "reason_codes": [{"code": reason_code, "severity": "info"}]},
        "status": "unavailable",
        "financial_anchor_ref": None,
        "claim_basis": "reported",
        "lease_basis": None,
        "corporate_action_basis": "none",
        "formula_ref": "not_applicable",
        "policy_version": "1.0.0",
        "confidence": "insufficient",
        "provenance_refs": provenance or [],
    }


def build_observations(
    universe_path: Path, method_family_id: str, as_of: str, *,
    root: Path = REPO_ROOT, currency: str = "TRY", accounting_basis: str = "reported",
) -> dict[str, Any]:
    universe = _read_json(universe_path)
    observations: list[dict[str, Any]] = []
    for member in universe["members"]:
        ticker = member["ticker"]
        if method_family_id in VALUATION_METHOD_FAMILIES:
            obs = _observation_from_valuation_method(ticker, method_family_id, as_of, root)
        else:
            obs = _observation_from_derived_ratio(ticker, method_family_id, as_of, root)
        # Schema requires as_of_date/cutoff_instant to be present even for
        # unavailable observations (not nullable) -- backfill with the
        # requested as-of so the record is still schema-valid and dated.
        if obs["as_of_date"] is None:
            obs["as_of_date"] = as_of
            obs["cutoff_instant"] = f"{as_of}T20:59:59Z"
        obs["observation_id"] = f"obs-{member['member_id']}"
        obs["company_or_member_id"] = member["member_id"]
        observations.append(obs)

    # Strip the common "val.method."/"val.formula.method." namespace prefix
    # before sanitizing -- keeps the artifact_id's identifying segment under
    # the schema's 64-char cap even for the longest method_family_id here
    # (val.method.earnings_yield.reported_parent), while method_family_id
    # itself (the field the engine actually matches on) stays untouched.
    short_method = re.sub(r"^val\.(method|formula)\.", "", method_family_id)
    safe_method = re.sub(r"[^a-z0-9_.\-]", "_", short_method.lower())
    observation_set_id = f"{universe['universe_id']}_{safe_method}"[:64]
    return {
        "schema_version": "1.0.0",
        "artifact_type": "valuation_comparison_observations",
        "artifact_id": f"valuation-comparison-observations:{observation_set_id}:1",
        "owner_type": "authored",
        "observation_set_id": observation_set_id,
        "observation_kind": "peer_member",
        "method_family_id": method_family_id,
        "method_variant_id": "standard",
        "currency": currency,
        "accounting_basis": accounting_basis,
        "consolidation": "consolidated",
        "observations": observations,
        "lineage": {"dag": {"nodes": [{"node_id": "n1", "node_type": "observation_set", "owner_type": "authored"}], "edges": []}},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--method", required=True, help="method_family_id, e.g. gross_margin or val.method.earnings_yield.reported_parent")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = build_observations(Path(args.universe), args.method, args.as_of)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] {output_path} ({len(result['observations'])} gözlem)")


if __name__ == "__main__":
    main()
