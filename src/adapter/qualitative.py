from __future__ import annotations

import hashlib
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from lxml import html

from engine.io import read_json, write_json_atomic

from .models import FilingRef
from .models import SecFact


_RISK_CATEGORIES = (
    (
        "competition_and_demand",
        "market",
        "Rekabet ve Tüketici Talebi Riski",
        ("competition", "competitive", "consumer demand", "customer preference"),
        "Şirket, rekabet koşulları veya tüketici talebindeki değişimlerin faaliyet sonuçlarını olumsuz etkileyebileceğini bildiriyor.",
    ),
    (
        "supply_chain_and_inputs",
        "operational",
        "Tedarik Zinciri ve Girdi Maliyeti Riski",
        ("supply chain", "raw material", "commodity", "supplier", "transportation"),
        "Şirket, tedarik zinciri kesintileri veya girdi maliyetlerindeki değişimlerin operasyonlarını ve marjlarını etkileyebileceğini bildiriyor.",
    ),
    (
        "cybersecurity_and_systems",
        "operational",
        "Siber Güvenlik ve Bilgi Sistemleri Riski",
        ("cybersecurity", "cyber attack", "information system", "data breach"),
        "Şirket, siber olayların veya bilgi sistemi kesintilerinin operasyonları ve itibarı üzerinde olumsuz etki yaratabileceğini bildiriyor.",
    ),
    (
        "regulation_and_litigation",
        "regulatory",
        "Düzenleyici ve Hukuki Riskler",
        ("regulation", "regulatory", "litigation", "legal proceeding", "tax law"),
        "Şirket, düzenleme, vergi veya hukuki süreçlerdeki değişimlerin maliyet ve faaliyet sonuçlarını etkileyebileceğini bildiriyor.",
    ),
    (
        "foreign_currency_and_macro",
        "financial",
        "Döviz ve Makroekonomik Riskler",
        ("foreign currency", "exchange rate", "inflation", "interest rate", "economic condition"),
        "Şirket, döviz, enflasyon, faiz veya genel ekonomik koşullardaki değişimlerin sonuçlarını olumsuz etkileyebileceğini bildiriyor.",
    ),
    (
        "climate_and_environment",
        "regulatory",
        "İklim ve Çevresel Düzenleme Riski",
        ("climate change", "environmental", "greenhouse gas", "water scarcity"),
        "Şirket, iklim olayları veya çevresel düzenlemelerin operasyon ve maliyet yapısını etkileyebileceğini bildiriyor.",
    ),
)


def build_and_write_risk_artifact(
    *, workspace: Path, ticker: str, period_id: str, filing: FilingRef,
    primary_document: Path,
) -> dict[str, Any]:
    section = _extract_item_1a(primary_document)
    if not section:
        artifact = _unavailable_risk_artifact(ticker, period_id, filing.filing_date)
        write_json_atomic(workspace / "data" / "risks" / ticker / f"{period_id}.json", artifact)
        return artifact

    relative_source = f"raw/sec-filings/{ticker}/{filing.accession}-risk-factors.txt"
    source_path = workspace / relative_source
    _write_text_atomic(source_path, section)
    source_id = f"sec-{filing.accession.lower()}-risk-factors"
    _upsert_text_source(workspace, ticker, filing, source_id, relative_source, source_path)

    normalized = section.lower()
    sentences = _sentences(section)
    risks: list[dict[str, Any]] = []
    used_evidence_sentences: set[str] = set()
    for risk_id, category, title, keywords, description in _RISK_CATEGORIES:
        if not any(keyword in normalized for keyword in keywords):
            continue
        evidence_sentence = _select_risk_evidence(
            sentences, keywords, used_evidence_sentences
        )
        if evidence_sentence is None:
            continue
        used_evidence_sentences.add(evidence_sentence)
        risks.append({
            "risk_id": risk_id,
            "category": category,
            "title": title,
            "description": description,
            "direction": "negative",
            "severity": "medium",
            "severity_rationale": (
                "Önem derecesi, SEC filingindeki risk açıklamasının varlığını gösterir; "
                "olasılık veya parasal etki tahmin edilmemiştir."
            ),
            "time_horizon": "long",
            "evidence": [{
                "source_id": source_id,
                "source_file": relative_source,
                "page": None,
                "summary": _keyword_centered_excerpt(evidence_sentence, keywords, 30),
            }],
            "mitigants": None,
            "quantified_effect": None,
            "notes": "SEC Item 1A metninden deterministik anahtar kelime eşlemesiyle sınıflandırıldı.",
        })

    artifact = {
        "schema_version": 1,
        "ticker": ticker,
        "period": period_id,
        "as_of": filing.filing_date.isoformat(),
        "scope_note": (
            f"{filing.form} Item 1A risk metninden deterministik olarak çıkarılmıştır; "
            "önem derecesi ve parasal etki tahmin edilmemiştir."
        ),
        "analysis_status": "available" if risks else "unavailable",
        "unavailable_reason_code": None if risks else "risk_extraction_failed",
        "validation_findings": [],
        "risks": risks,
    }
    write_json_atomic(workspace / "data" / "risks" / ticker / f"{period_id}.json", artifact)
    return artifact


def inherit_annual_risks(
    *, workspace: Path, ticker: str, latest_period: str, latest_filing: FilingRef,
    annual_artifact: dict[str, Any],
) -> dict[str, Any]:
    inherited = {
        **annual_artifact,
        "period": latest_period,
        "as_of": latest_filing.filing_date.isoformat(),
        "scope_note": (
            f"Son {latest_filing.form} yeni ve ayrıntılı Item 1A riskleri sunmadığı için "
            "son 10-K risk bazını devralır; üç aylık filing ayrıca kontrol edilmiştir."
        ),
    }
    write_json_atomic(workspace / "data" / "risks" / ticker / f"{latest_period}.json", inherited)
    return inherited


def build_and_write_debt_profile(
    *, workspace: Path, ticker: str, period_id: str, direct: dict[str, Any],
    filing: FilingRef, facts: tuple[SecFact, ...] = (),
    inherited_note_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = {
        metric["metric_id"]: metric
        for metric in direct.get("balance_sheet", [])
        if metric.get("status") == "available"
    }
    metric_ids = {
        "short_term_financial_debt": "borrowings_short_term",
        "current_portion_long_term_debt": "borrowings_long_term_current_portion",
        "long_term_financial_debt": "borrowings_long_term",
        "lease_liabilities_current": "lease_liabilities_short_term",
        "lease_liabilities_noncurrent": "lease_liabilities_long_term",
        "cash_and_cash_equivalents": "cash_and_equivalents",
    }
    totals = {
        output_id: _amount_observation(metrics.get(metric_id), direct)
        for output_id, metric_id in metric_ids.items()
    }
    source_file = f"raw/sec-filings/{ticker}/{filing.accession}.json"
    source_id = f"sec-{filing.accession.lower()}"
    short = _reported_value(totals["short_term_financial_debt"])
    current = _reported_value(totals["current_portion_long_term_debt"])
    long_term = _reported_value(totals["long_term_financial_debt"])
    cash = _reported_value(totals["cash_and_cash_equivalents"])
    debt_values = [value for value in (short, current, long_term) if value is not None]
    total_debt = sum(debt_values) if debt_values else None
    near_term = sum(value for value in (short, current) if value is not None) if short is not None or current is not None else None
    cash_ratio = cash / near_term if cash is not None and near_term not in (None, 0) else None
    near_share = near_term / total_debt if near_term is not None and total_debt not in (None, 0) else None
    pressure, reasons = _pressure(cash_ratio, near_share)

    note_details = (
        _extract_debt_and_lease_note_details(facts, filing, ticker)
        if filing.form == "10-K" and facts
        else inherited_note_details or _empty_note_details()
    )
    artifact = {
        "schema_version": 1,
        "ticker": ticker,
        "period": period_id,
        "period_end": direct["period_end"],
        "currency": direct["currency"],
        "scale": direct["scale"],
        "extracted_at": filing.filing_date.isoformat(),
        "extraction_method": "sec_xbrl",
        "source_documents": _merge_source_documents(
            [{"source_id": source_id, "source_file": source_file}],
            note_details["source_documents"],
        ),
        "debt_totals": totals,
        "maturity_profile": note_details["maturity_profile"],
        "currency_profile": note_details["currency_profile"],
        "interest_profile": {
            "fixed_rate_debt": _missing_amount(),
            "floating_rate_debt": _missing_amount(),
            "weighted_average_rates": note_details["weighted_average_rates"],
        },
        "risk_sensitivities": {"fx_sensitivity": [], "interest_rate_sensitivity": []},
        "liquidity_support": {
            "undrawn_credit_facilities": _missing_amount(),
            "committed_facilities": _missing_amount(),
            "covenants_or_defaults": {"value": None, "status": "not_disclosed", "evidence": None},
        },
        "refinancing_disclosures": [],
        "diagnostics": {
            "total_financial_debt": _diagnostic(total_debt, "source_scale"),
            "near_term_financial_debt": _diagnostic(near_term, "source_scale"),
            "cash_to_near_term_debt": _diagnostic(cash_ratio, "ratio"),
            "near_term_debt_share": _diagnostic(near_share, "ratio"),
            "floating_rate_debt_share": _diagnostic(None, "ratio"),
            "refinancing_pressure": {
                "status": "available" if pressure is not None else "insufficient_data",
                "level": pressure,
                "confidence": "medium" if pressure is not None else "low",
                "reason_codes": reasons,
            },
        },
    }
    write_json_atomic(workspace / "data" / "debt-profile" / ticker / f"{period_id}.json", artifact)
    return artifact


_MATURITY_CONCEPTS = (
    ("Long-term debt", "next 12 months", "LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths"),
    ("Long-term debt", "year 2", "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo"),
    ("Long-term debt", "year 3", "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree"),
    ("Long-term debt", "year 4", "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour"),
    ("Long-term debt", "year 5", "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive"),
    ("Long-term debt", "after year 5", "LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive"),
    ("Operating leases", "next 12 months", "LesseeOperatingLeaseLiabilityPaymentsDueNextTwelveMonths"),
    ("Operating leases", "year 2", "LesseeOperatingLeaseLiabilityPaymentsDueYearTwo"),
    ("Operating leases", "year 3", "LesseeOperatingLeaseLiabilityPaymentsDueYearThree"),
    ("Operating leases", "year 4", "LesseeOperatingLeaseLiabilityPaymentsDueYearFour"),
    ("Operating leases", "year 5", "LesseeOperatingLeaseLiabilityPaymentsDueYearFive"),
    ("Operating leases", "after year 5", "LesseeOperatingLeaseLiabilityPaymentsDueAfterYearFive"),
    ("Finance leases", "next 12 months", "FinanceLeaseLiabilityPaymentsDueNextTwelveMonths"),
    ("Finance leases", "year 2", "FinanceLeaseLiabilityPaymentsDueYearTwo"),
    ("Finance leases", "year 3", "FinanceLeaseLiabilityPaymentsDueYearThree"),
    ("Finance leases", "year 4", "FinanceLeaseLiabilityPaymentsDueYearFour"),
    ("Finance leases", "year 5", "FinanceLeaseLiabilityPaymentsDueYearFive"),
    ("Finance leases", "after year 5", "FinanceLeaseLiabilityPaymentsDueAfterYearFive"),
)

_RATE_CONCEPTS = (
    ("Total debt", "DebtWeightedAverageInterestRate"),
    ("Long-term debt", "LongtermDebtWeightedAverageInterestRate"),
    ("Short-term debt", "ShortTermDebtWeightedAverageInterestRate"),
    ("Operating leases", "OperatingLeaseWeightedAverageDiscountRatePercent"),
    ("Finance leases", "FinanceLeaseWeightedAverageDiscountRatePercent"),
)


def _extract_debt_and_lease_note_details(
    facts: tuple[SecFact, ...], filing: FilingRef, ticker: str,
) -> dict[str, Any]:
    source_id = f"sec-{filing.accession.lower()}"
    source_file = f"raw/sec-filings/{ticker}/{filing.accession}.json"
    evidence_file = source_file
    rows: list[dict[str, Any]] = []
    for scope, bucket, concept in _MATURITY_CONCEPTS:
        fact = _note_fact(facts, concept, filing.report_date)
        if fact is None:
            continue
        rows.append(_note_amount(
            fact, source_id=source_id, source_file=evidence_file,
            liability_scope=scope, maturity_bucket=bucket,
        ))
    rates: list[dict[str, Any]] = []
    for debt_type, concept in _RATE_CONCEPTS:
        fact = _note_fact(facts, concept, filing.report_date, unit="number")
        if fact is None:
            continue
        value = _numeric_fact(fact)
        if value is None:
            continue
        rate_pct = value * 100 if abs(value) <= 1 else value
        rates.append({
            "debt_type": debt_type,
            "currency": None,
            "rate_pct": rate_pct,
            "status": "reported",
            "evidence": _fact_evidence(fact, source_id, evidence_file),
        })
    return {
        "source_documents": [{"source_id": source_id, "source_file": source_file}],
        "maturity_profile": rows,
        "currency_profile": _extract_currency_profile(
            facts, source_id=source_id, source_file=evidence_file,
        ),
        "weighted_average_rates": rates,
    }


def _extract_currency_profile(
    facts: tuple[SecFact, ...], *, source_id: str, source_file: str,
) -> list[dict[str, Any]]:
    by_instrument: dict[str, list[SecFact]] = {}
    for fact in facts:
        if fact.concept != "DebtInstrumentFaceAmount" or fact.is_nil or not fact.unit:
            continue
        members = [
            member for axis, member in fact.dimensions
            if axis.endswith("DebtInstrumentAxis")
        ]
        if len(members) == 1:
            by_instrument.setdefault(members[0], []).append(fact)
    selected: list[SecFact] = []
    for instrument_facts in by_instrument.values():
        values = {(fact.unit, _numeric_fact(fact)) for fact in instrument_facts}
        if len(values) == 1:
            selected.append(sorted(instrument_facts, key=lambda fact: fact.context_id)[0])
    by_currency: dict[str, list[SecFact]] = {}
    for fact in selected:
        code = fact.unit.upper()
        if len(code) == 3 and code.isalpha():
            by_currency.setdefault(code, []).append(fact)
    rows: list[dict[str, Any]] = []
    for code in sorted(by_currency):
        currency_facts = by_currency[code]
        total = sum(_numeric_fact(fact) or 0 for fact in currency_facts)
        evidence = _fact_evidence(currency_facts[0], source_id, source_file)
        evidence["quoted_text"] = (
            f"Aggregate of {len(currency_facts)} SEC Inline XBRL DebtInstrumentFaceAmount facts"
        )
        rows.append({
            "value": total / 1_000_000,
            "raw_quoted_value": str(total),
            "currency": code,
            "debt_currency": code,
            "scale": "million",
            "status": "reported",
            "evidence": evidence,
            "liability_scope": "Debt instruments with disclosed face amount",
        })
    return rows


def _empty_note_details() -> dict[str, Any]:
    return {
        "source_documents": [], "maturity_profile": [],
        "currency_profile": [], "weighted_average_rates": [],
    }


def _note_fact(
    facts: tuple[SecFact, ...], concept: str, period_end: date, *, unit: str = "usd",
) -> SecFact | None:
    candidates = [
        fact for fact in facts
        if fact.concept == concept and fact.end_date == period_end
        and not fact.is_nil and fact.unit == unit
    ]
    if not candidates:
        return None
    dimensionless = [fact for fact in candidates if not fact.dimensions]
    candidates = dimensionless or candidates
    values = {str(_numeric_fact(fact)) for fact in candidates}
    if len(values) != 1:
        return None
    return sorted(candidates, key=lambda fact: (len(fact.dimensions), fact.context_id))[0]


def _numeric_fact(fact: SecFact) -> float | None:
    try:
        return float(fact.value)
    except (TypeError, ValueError):
        return None


def _note_amount(
    fact: SecFact, *, source_id: str, source_file: str,
    liability_scope: str, maturity_bucket: str,
) -> dict[str, Any]:
    value = _numeric_fact(fact)
    return {
        "value": value / 1_000_000 if value is not None else None,
        "raw_quoted_value": fact.value,
        "currency": "USD",
        "scale": "million",
        "status": "reported",
        "evidence": _fact_evidence(fact, source_id, source_file),
        "liability_scope": liability_scope,
        "maturity_bucket": maturity_bucket,
    }


def _fact_evidence(
    fact: SecFact, source_id: str, source_file: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_file": source_file,
        "page": None,
        "quoted_text": f"SEC Inline XBRL fact {fact.qualified_name}#{fact.context_id}",
    }


def _merge_source_documents(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for group in groups:
        for item in group:
            by_id[item["source_id"]] = item
    return [by_id[key] for key in sorted(by_id)]


def _extract_item_1a(primary_document: Path) -> str | None:
    text = " ".join(html.fromstring(primary_document.read_bytes()).text_content().split())
    starts = list(
        re.finditer(
            r"item\s*1a[^A-Za-z0-9]{0,12}risk\s*factors",
            text,
            flags=re.IGNORECASE,
        )
    )
    candidates: list[tuple[int, str]] = []
    opening_signals = (
        "the risks described below",
        "the following risks",
        "our business is subject",
        "you should carefully",
        "carefully consider",
        "no material change in the risk factors",
        "no material changes in the risk factors",
    )
    for match in starts:
        tail = text[match.end():]
        end = re.search(
            r"item\s*(?:1b|1c|2)[^A-Za-z0-9]{1,12}",
            tail,
            flags=re.IGNORECASE,
        )
        candidate = tail[: end.start() if end else 120_000].strip()
        if 200 <= len(candidate) <= 160_000:
            opening = candidate[:700].lower()
            score = sum(10 for signal in opening_signals if signal in opening)
            category_hits = sum(
                1
                for _, _, _, keywords, _ in _RISK_CATEGORIES
                for keyword in keywords
                if keyword in opening
            )
            context_hits = sum(term in opening for term in _RISK_CONTEXT_TERMS)
            score += (2 * category_hits) + context_hits
            if score >= 4:
                candidates.append((score, candidate))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], len(item[1])))[1]


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if 60 <= len(sentence.strip()) <= 700
    ]


_RISK_CONTEXT_TERMS = (
    "risk", "adverse", "disrupt", "could", "may", "failure", "loss",
    "impact", "affect", "increase", "cost", "threat", "breach", "harm",
    "material", "exposure", "penalt", "damage", "consequence",
)


def _select_risk_evidence(
    sentences: list[str], keywords: tuple[str, ...], used_sentences: set[str],
) -> str | None:
    candidates = []
    for position, sentence in enumerate(sentences):
        normalized = sentence.lower()
        matched = [keyword for keyword in keywords if keyword in normalized]
        if not matched or sentence in used_sentences:
            continue
        context_count = sum(term in normalized for term in _RISK_CONTEXT_TERMS)
        local_context_count = 0
        for keyword in matched:
            keyword_position = normalized.find(keyword)
            window = normalized[
                max(0, keyword_position - 180): keyword_position + len(keyword) + 180
            ]
            local_context_count = max(
                local_context_count,
                sum(term in window for term in _RISK_CONTEXT_TERMS),
            )
        candidates.append(
            (local_context_count, context_count, len(matched), -len(sentence), -position, sentence)
        )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[:5])[5]


def _keyword_centered_excerpt(
    text: str, keywords: tuple[str, ...], max_words: int,
) -> str:
    cleaned = re.sub(r"\d+Table of Contents.*$", "", text, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"(?<=[.!?])(?=[A-Z])", " ", cleaned)
    cleaned = re.sub(r"(?<=[.!?])\d+(?=[A-Z])", " ", cleaned)
    cleaned = re.sub(r"(?<=[a-z])\d+(?=[A-Z])", " ", cleaned)
    cleaned = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", cleaned)
    normalized = cleaned.lower()
    positions = [normalized.find(keyword) for keyword in keywords if keyword in normalized]
    match_position = min(positions) if positions else 0
    words = list(re.finditer(r"\S+", cleaned))
    if not words:
        return ""
    match_word = next(
        (index for index, word in enumerate(words) if word.start() <= match_position < word.end()),
        0,
    )
    start = max(0, match_word - 8)
    end = min(len(words), start + max_words)
    start = max(0, end - max_words)
    excerpt = " ".join(word.group(0) for word in words[start:end])
    if start > 0:
        excerpt = "…" + excerpt
    if end < len(words):
        excerpt += "…"
    return excerpt


def _excerpt(text: str, max_words: int) -> str:
    words = text.split()
    excerpt = " ".join(words[:max_words])
    return excerpt + ("…" if len(words) > max_words else "")


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _upsert_text_source(
    workspace: Path, ticker: str, filing: FilingRef, source_id: str,
    relative_source: str, source_path: Path,
) -> None:
    manifest_path = workspace / "data" / "source-manifests" / f"{ticker}.json"
    manifest = read_json(manifest_path)
    source = {
        "source_id": source_id,
        "path": relative_source,
        "source_type": "sec_filing_text",
        "language": "en",
        "publication_date": filing.filing_date.isoformat(),
        "periods_covered": [],
        "currency": None,
        "scale": None,
        "consolidation": "consolidated",
        "audit_status": "audited" if filing.form == "10-K" else "unaudited",
        "accounting_basis": "US_GAAP",
        "is_primary": True,
        "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "notes": f"SEC {filing.form} Item 1A risk-factor text snapshot; accession {filing.accession}.",
    }
    manifest["sources"] = [item for item in manifest["sources"] if item.get("source_id") != source_id] + [source]
    manifest["sources"].sort(key=lambda item: (item.get("publication_date") or "", item["source_id"]))
    write_json_atomic(manifest_path, manifest)


def _amount_observation(metric: dict[str, Any] | None, direct: dict[str, Any]) -> dict[str, Any]:
    if metric is None or metric.get("value") is None:
        return _missing_amount()
    provenance = metric["provenance"]
    value = metric["value"]
    return {
        "value": value,
        "raw_quoted_value": str(value),
        "currency": direct["currency"],
        "scale": direct["scale"],
        "status": "reported",
        "evidence": {
            "source_id": provenance["source_id"],
            "source_file": provenance["source_file"],
            "page": None,
            "quoted_text": f"SEC Inline XBRL fact {provenance.get('cell_or_range')}",
        },
    }


def _missing_amount() -> dict[str, Any]:
    return {
        "value": None, "raw_quoted_value": None, "currency": None,
        "scale": None, "status": "not_disclosed", "evidence": None,
    }


def _reported_value(observation: dict[str, Any]) -> float | None:
    value = observation.get("value")
    return float(value) if observation.get("status") == "reported" and value is not None else None


def _diagnostic(value: float | None, unit: str) -> dict[str, Any]:
    return {"status": "available" if value is not None else "unavailable", "value": value, "unit": unit}


def _pressure(cash_ratio: float | None, near_share: float | None) -> tuple[str | None, list[str]]:
    reasons: list[str] = []
    if cash_ratio is not None and cash_ratio < 0.25:
        reasons.append("cash_covers_less_than_25pct_of_near_term_debt")
    if near_share is not None and near_share >= 0.40:
        reasons.append("at_least_40pct_of_debt_is_near_term")
    if reasons:
        return "high", reasons
    if cash_ratio is None or near_share is None:
        return None, ["insufficient_xbrl_debt_components"]
    if cash_ratio < 0.75 or near_share >= 0.25:
        return "medium", ["moderate_near_term_debt_pressure"]
    return "low", ["cash_and_maturity_indicators_are_comfortable"]


def _unavailable_risk_artifact(ticker: str, period_id: str, as_of: date) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "ticker": ticker,
        "period": period_id,
        "as_of": as_of.isoformat(),
        "scope_note": "SEC filinginde ayrıştırılabilir Item 1A risk bölümü bulunamadı.",
        "analysis_status": "unavailable",
        "unavailable_reason_code": "risk_extraction_failed",
        "validation_findings": [],
        "risks": [],
    }
