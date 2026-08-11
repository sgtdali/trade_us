"""Deterministic listed-investee identity and issued-share resolution."""

from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any


_LEGAL_SUFFIXES = {
    "a", "s", "as", "anonim", "sirketi", "sirket", "ta", "tas",
}
_SCALE = {
    "unit": Decimal(1),
    "thousand": Decimal(1_000),
    "million": Decimal(1_000_000),
    "billion": Decimal(1_000_000_000),
}


@dataclass(frozen=True)
class CompanyIdentity:
    ticker: str
    company_name: str


def normalize_company_name(value: str) -> str:
    translated = value.translate(str.maketrans("ıİşŞğĞüÜöÖçÇ", "iIsSgGuUoOcC"))
    ascii_value = unicodedata.normalize("NFKD", translated).encode("ascii", "ignore").decode("ascii")
    tokens = re.findall(r"[a-z0-9]+", ascii_value.lower())
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def load_company_identities(companies_dir: Path) -> list[CompanyIdentity]:
    identities: list[CompanyIdentity] = []
    if not companies_dir.exists():
        return identities
    for path in sorted(companies_dir.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("is_active") is False or not document.get("ticker") or not document.get("company_name"):
            continue
        identities.append(
            CompanyIdentity(
                ticker=str(document["ticker"]).upper(),
                company_name=str(document["company_name"]),
            )
        )
    return identities


def match_company_identity(
    name: str,
    identities: list[CompanyIdentity],
) -> CompanyIdentity | None:
    target = normalize_company_name(name)
    exact = [identity for identity in identities if normalize_company_name(identity.company_name) == target]
    if len(exact) == 1:
        return exact[0]
    target_tokens = target.split()
    if len(target_tokens) < 3:
        return None
    contained = []
    for identity in identities:
        candidate = normalize_company_name(identity.company_name)
        candidate_tokens = candidate.split()
        shorter, longer = (
            (target_tokens, candidate_tokens)
            if len(target_tokens) <= len(candidate_tokens)
            else (candidate_tokens, target_tokens)
        )
        if len(shorter) >= 3 and " ".join(shorter) in " ".join(longer):
            contained.append(identity)
    return contained[0] if len(contained) == 1 else None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _eligible_date(value: str | None, as_of_date: str) -> bool:
    return bool(value and dt.date.fromisoformat(value[:10]) <= dt.date.fromisoformat(as_of_date))


def resolve_investee_share_basis(
    repo_root: Path,
    ticker: str,
    as_of_date: str,
) -> dict[str, Any]:
    """Resolve issued BIST quote units from the investee's own governed data."""
    ticker = ticker.upper()
    ledger_path = repo_root / "data" / "market-input-ledgers" / ticker / "share-count-ledger.json"
    if ledger_path.exists():
        ledger = _read_json(ledger_path)
        candidates = [
            record
            for record in ledger.get("records", [])
            if record.get("concept") == "issued_shares"
            and _eligible_date(record.get("effective_at"), as_of_date)
            and _eligible_date(record.get("available_at") or record.get("published_at"), as_of_date)
        ]
        if candidates:
            record = max(candidates, key=lambda item: item["effective_at"])
            return {
                "status": "available",
                "total_quote_units": str(record["value"]),
                "effective_date": record["effective_at"][:10],
                "source_refs": sorted(set(record.get("source_refs", []))),
                "basis": "investee_share_count_ledger",
                "reason_codes": [],
            }

    financial_dir = repo_root / "data" / "financial" / ticker
    candidates: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    if financial_dir.exists():
        for path in financial_dir.glob("*.json"):
            if path.name.endswith("-derived-ratios.json"):
                continue
            document = _read_json(path)
            if not _eligible_date(document.get("period_end"), as_of_date):
                continue
            if not _eligible_date(document.get("publication_date"), as_of_date):
                continue
            metric = next(
                (
                    item
                    for item in document.get("balance_sheet", [])
                    if item.get("metric_id") == "paid_in_capital" and item.get("value") is not None
                ),
                None,
            )
            if metric is not None:
                candidates.append((document["period_end"], document, metric))
    if candidates:
        _period_end, document, metric = max(candidates, key=lambda item: item[0])
        scale = _SCALE.get(document.get("scale", "unit"))
        if scale is not None and document.get("currency") == "TRY":
            quote_units = Decimal(str(metric["value"])) * scale
            provenance = metric.get("provenance", {})
            return {
                "status": "available",
                "total_quote_units": format(quote_units, "f"),
                "effective_date": document["period_end"],
                "source_refs": [provenance["source_id"]] if provenance.get("source_id") else [],
                "basis": "investee_verified_paid_in_capital",
                "reason_codes": [],
            }
    return {
        "status": "unavailable",
        "total_quote_units": None,
        "effective_date": None,
        "source_refs": [],
        "basis": None,
        "reason_codes": ["holding_investee_share_data_missing"],
    }
