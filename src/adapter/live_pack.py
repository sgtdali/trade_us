"""Paketi ARTIFACT'lerden kur, markdown raporu ayristirmadan.

Neden: paket bugune kadar degerleme raporunu regex'le ayristiriyordu --
carpanlari bir tablodan, fiyati bir bolumden, sinyalleri bir listeden. Rapor
bir SUNUM katmani; sayilar zaten altta duruyor. Ayristirmak iki sey getiriyordu:

  1. Rapor uretimi zorunlu hale geliyordu. Canli akista raporu kimse okumuyor
     (ChatGPT pack.json aliyor) ama uretilmeden paket kurulamiyordu.
  2. Bolum basliklarina bagli regex kirilgan.

Bu modul ayni paketi dogrudan artifact'lerden kurar:

  valuation-results/<t>/<as_of>/ctx-*/current.json  -> carpanlar
  valuation-inputs/<t>/<as_of>/ctx-*.json           -> fiyat, piyasa degeri
  financial/<t>/<donem>{,-derived-ratios}.json      -> donem, fundamentals
  signals/<t>/<donem>.json                          -> deterministik sinyaller

Piotroski KALDIRILDI: hicbir artifact'te yok, yalniz rapor uretilirken
hesaplaniyordu ve eklentinin 570 dosyasinin hicbirinde gecmiyor -- ne
piotroski, ne altman, ne beneish. Kalite boyutunun istedigi her sey (marjlar,
nakit donusumu, bilanco, ROIC) zaten ayri ayri pakette.
"""
from __future__ import annotations

import glob
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from .evidence import (
    _latest_release_evidence, _market_stats, _read_json,
)
from .point_in_time import MonthPlan

# method_id -> gorunur ad. Sunum katalogu (config/valuation/reporting/
# labels.json) Turkce ve ABD rapor yolu ondan cevirmiyor; tek kaynak burasi
# olsun ki paket ile carpan gecmisi ayni adi kullansin.
METHOD_LABELS = {
    "val.method.pe.reported_parent": "Price / Earnings",
    "val.method.earnings_yield.reported_parent": "Earnings Yield",
    "val.method.price_to_book.parent_equity": "Price / Book Value",
    "val.method.fcf_yield.standard_equity":
        "Parent-Attributed Free Cash Flow Yield (Proxy)",
    "val.method.ev_to_ebit.core":
        "Lease-Exclusive Enterprise Value / Reported Operating Income",
    "val.method.ev_to_ebitda.canonical":
        "Enterprise Value / Issuer-Reported EBITDA",
}
# Artifact getiriyi ORAN tutuyor (0,0286), rapor YUZDE gosteriyordu (2,86).
# A/B karsilastirmasi bunu yakaladi. Paket rapor sozlesmesini korur, cunku
# talimattaki yeniden olcekleme kurali ve carpan gecmisi ona gore yazildi.
YIELD_METHODS = {"val.method.earnings_yield.reported_parent",
                 "val.method.fcf_yield.standard_equity"}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _describe_period(payload: dict) -> str:
    """Donemi INSAN OKUR bicimde tarif et.

    Ham etiket "2026-Q3" bir ceyrek gibi okunur; oysa ABD dosyalamalarinda o
    KUMULATIF olabilir (AAPL'de 39 hafta). Kapsam suresini soylemek, yillik
    buyumeyi bir ceyrek sanmayi engelleyen tek sey.
    """
    label = payload.get("period") or "?"
    start, end = payload.get("period_start"), payload.get("period_end")
    if not (start and end):
        return label
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    weeks = round(days / 7)
    if payload.get("period_type") == "annual":
        return f"{label} — fiscal year of {weeks} weeks ended {end}"
    kind = "cumulative year-to-date" if days > 100 else "discrete quarter"
    return f"{label} — {weeks} weeks ended {end} ({kind})"


def _latest_financial(workspace: Path, ticker: str, horizon: str):
    """Ufka kadar yayinlanmis, donem sonu en yeni rapor ve turetilmis oranlari."""
    folder = workspace / "data" / "financial" / ticker
    if not folder.is_dir():
        return None, None
    best = None
    for path in folder.glob("*.json"):
        if path.name.endswith("-derived-ratios.json"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        published = payload.get("publication_date")
        if published and published > horizon:
            continue
        key = payload.get("period_end") or ""
        if best is None or key > best[0]:
            best = (key, payload, path)
    if best is None:
        return None, None
    _end, payload, path = best
    derived_path = path.with_name(path.stem + "-derived-ratios.json")
    derived = None
    if derived_path.is_file():
        try:
            derived = json.loads(derived_path.read_text(encoding="utf-8"))
        except Exception:
            derived = None
    return payload, derived


def _fundamentals(derived: dict | None) -> dict[str, float]:
    """Turetilmis oran dosyasindaki sayisal kalemler."""
    out: dict[str, float] = {}
    if not derived:
        return out
    for group in derived.values():
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, dict):
                continue
            value = _number(item.get("value"))
            if value is not None and item.get("metric_id"):
                out[item["metric_id"]] = value
    return out


def _valuation(workspace: Path, ticker: str, as_of: str) -> dict[str, float | None]:
    pattern = str(workspace / "data" / "valuation-results" / ticker / as_of
                  / "*" / "current.json")
    out: dict[str, float | None] = {}
    for path in glob.glob(pattern):
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        for result in payload.get("method_results", []):
            method_id = result.get("method_id")
            label = METHOD_LABELS.get(method_id)
            if not label:
                continue
            value = _number((result.get("canonical_value") or {}).get("value"))
            if value is not None and method_id in YIELD_METHODS:
                value = round(value * 100, 2)      # oran -> yuzde
            out[label] = round(value, 4) if value is not None else None
    return out


def _price_and_cap(workspace: Path, ticker: str,
                   as_of: str) -> tuple[float | None, float | None]:
    pattern = str(workspace / "data" / "valuation-inputs" / ticker / as_of / "*.json")
    for path in glob.glob(pattern):
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        price = _number(((payload.get("price_basis") or {})
                         .get("reporting_currency_price") or {}).get("value"))
        cap = _number(((payload.get("market_cap_basis") or {})
                       .get("reporting_currency_total_market_cap") or {}).get("value"))
        if price is not None or cap is not None:
            return price, (round(cap / 1e6, 1) if cap is not None else None)
    return None, None


def _signals(workspace: Path, ticker: str, period: str | None) -> dict[str, list[str]]:
    """positive/negative/diger -- rapordaki favorable/adverse ayrimi."""
    folder = workspace / "data" / "signals" / ticker
    if not folder.is_dir():
        return {"favorable": [], "adverse": [], "other": []}
    path = folder / f"{period}.json" if period else None
    if not (path and path.is_file()):
        files = sorted(folder.glob("*.json"))
        if not files:
            return {"favorable": [], "adverse": [], "other": []}
        path = files[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"favorable": [], "adverse": [], "other": []}
    out = {"favorable": [], "adverse": [], "other": []}
    for item in payload.get("signals", []):
        bucket = {"positive": "favorable", "negative": "adverse"}.get(
            item.get("value"), "other")
        out[bucket].append(item.get("signal_id"))
    return out


def build_pack_from_artifacts(*, run_root: Path, month: str,
                              guidance_root: Path | None = None) -> dict:
    config = _read_json(run_root / "run-config.json")
    cutoff = _read_json(run_root / "months" / month / "cutoff.json")
    workspace = run_root / "workspace"
    plan = MonthPlan(month=month, decision_date=cutoff["decision_date"],
                     cutoff_date=cutoff["cutoff_date"],
                     cutoff_instant=cutoff["cutoff_instant"],
                     execution_date=cutoff["execution_date"])
    horizon = cutoff["cutoff_date"]

    companies, missing = [], []
    for ticker in config["universe"]:
        payload, derived = _latest_financial(workspace, ticker, horizon)
        if payload is None:
            missing.append(ticker)
            continue
        price, cap = _price_and_cap(workspace, ticker, horizon)
        # Yas, DONEM SONUNDAN olculur; yayin tarihinden degil. A/B'de
        # AAPL icin 34 gun bekleniyordu, yayin tarihinden 0 cikmisti.
        period_end = payload.get("period_end")
        age = ((date.fromisoformat(horizon) - date.fromisoformat(period_end)).days
               if period_end else None)
        release = (_latest_release_evidence(guidance_root, ticker, horizon)
                   if guidance_root else
                   {"status": "unavailable", "reason": "guidance root not supplied"})
        source_ids = sorted({
            item["source_id"] for section in ("income_statement", "balance_sheet",
                                              "cash_flow_statement")
            for item in (payload.get(section) or [])
            if isinstance(item, dict) and item.get("source_id")
        })
        if release.get("source_id"):
            source_ids = sorted(set(source_ids) | {release["source_id"]})
        companies.append({
            "ticker": ticker,
            "cohort": config["cohorts"][ticker],
            "latest_reported_period": _describe_period(payload),
            "period_label": payload.get("period"),
            "latest_period_end": period_end,
            "financial_age_days": age,
            "closing_price_usd": round(price, 4) if price is not None else None,
            "market_cap_usd_m": cap,
            "market": _market_stats(run_root, ticker, plan),
            "fundamentals": _fundamentals(derived),
            "valuation": _valuation(workspace, ticker, horizon),
            "deterministic_signals": _signals(workspace, ticker, payload.get("period")),
            "latest_earnings_release": release,
            "source_ids": source_ids,
        })

    if missing:
        raise RuntimeError(f"{month}: finansali okunamayan sirket: {', '.join(missing)}")

    return {
        "schema_version": 2,
        "purpose": ("Deterministic point-in-time pack built directly from "
                    "workspace artifacts; no valuation report is parsed."),
        "month": month,
        "decision_date": plan.decision_date,
        "cutoff_instant": plan.cutoff_instant,
        "execution_date": plan.execution_date,
        "universe_count": len(companies),
        "known_limitations": [
            "fixed current universe creates survivorship and universe-selection bias",
            "historical consensus, transcripts, positioning and short-interest "
            "vintages are unavailable",
            "guidance is available only where a range was extracted and both "
            "endpoints appear in the selected release",
            "peer medians are supplied only for the comps step; do not invent them",
            "all knowledge and claims must be bounded by cutoff_instant",
        ],
        "companies": companies,
    }
