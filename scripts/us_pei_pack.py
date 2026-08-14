"""ChatGPT Public Equity Investing icin deterministik veri paketi uretir.

Amac: eklentinin sayilari web'den toplamasini gereksiz kilmak.

Eklentinin ucretli connector'larindan (FactSet / LSEG / S&P / Daloopa /
Quartr) bize lazim olan kismin cogunu zaten uretiyoruz:

  konsensus, forward tahmin, revizyon   <- data/consensus/snapshot-*.json
  finansallar, marjlar, buyume, kalite  <- SEC XBRL, tutarli tanimla
  degerleme carpanlari                  <- degerleme motoru
  fiyat / piyasa degeri                 <- fiyat defteri
  guidance, 8-K alintilari              <- us/guidance

Uretemedigimiz: earnings call transcript, uzman gorusmeleri, ozel sirket /
M&A verisi. Bunlar nitel ve eklentinin web'den bulmasi beklenir.

Kural: SAYI bizden, ANLATI web'den, CELISKI acikca.

Iki mod:
  (evrensel)      60 sirket   -> idea-generation
  --only TICKER   tek sirket  -> tearsheet / preview / comps / pitch

Adim talimatlari docs/pei-workflow.md'den gelir; ORADA gerekcesi var.
En onemlisi tearsheet'inki: o skill'in kapali sonuc sozlugu YOKTUR ve
kendi dosyasi "do not turn a tearsheet into a recommendation" der. Bu satir
olmadan model baska bir skill'in etiketini oduncu aliyor (ORCL'de oldu).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from adapter import live_refresh  # noqa: E402
from adapter.live_pack import build_pack_from_artifacts  # noqa: E402

# Kaynak CANLI koktur, donmus backtest kokleri degil. Onceden ic-2024-v1
# idi ve --no-refresh verildiginde paket sessizce olcum kanitindan
# kuruluyordu: aylar once dondurulmus fiyat ve finansallarla. Bu akis
# backtest'lerden bagimsiz olmali.
SOURCE_RUN = REPO / live_refresh.LIVE_PARENT / live_refresh.RUN_ID
GUIDANCE = REPO / "guidance"
CONSENSUS_DIR = REPO / "data" / "consensus"
PEERS = REPO / "config" / "valuation" / "comparison" / "peer-universes"
COMPANY_PEERS = REPO / "config" / "valuation" / "comparison" / "company-peer-frameworks"
LIVE_UNIVERSE = REPO / "config" / "universes" / "us-live.json"
OUT_ROOT = REPO / "pei"

CARRY = ("earnings_estimate", "revenue_estimate", "eps_trend",
         "eps_revisions", "price_targets")

TEARSHEET_FINANCIAL_METRICS = (
    "revenue_total",
    "gross_profit",
    "operating_profit",
    "net_profit_attributable_parent",
    "eps_diluted_usc",
    "cash_and_equivalents",
    "financial_investments_current",
    "total_assets",
    "borrowings_long_term_current_portion",
    "borrowings_long_term",
    "total_liabilities",
    "total_equity",
    "cf_net_operating_activities",
    "cf_capex_ppe_intangible",
    "cf_dividends_paid",
    "cf_share_repurchases",
)

TEARSHEET_EXTERNAL_GAPS = (
    ("business_mix", "product, segment and geographic mix is not normalized in workspace artifacts"),
    ("free_float", "no point-in-time free-float source in the workspace"),
    ("index_membership_and_weight", "no point-in-time index constituent weight source in the workspace"),
    ("top_holders_and_ownership_concentration", "no point-in-time ownership source in the workspace"),
    ("passive_and_etf_ownership", "no point-in-time passive ownership source in the workspace"),
    ("short_interest_and_borrow", "no point-in-time short-interest or borrow source in the workspace"),
    ("factor_exposure", "no point-in-time factor model in the workspace"),
    ("governance_detail", "no normalized board and governance dataset in the workspace"),
    ("earnings_call_commentary", "earnings-call transcripts are not stored in the workspace"),
)

# Hangi adim hangi blogu gorur. Kaynak: skill dosyalarindaki "Relevant
# Dependency Categories" ve "Resolve only the catalogued source categories
# needed for the current <workflow>".
#
# Olculdu (ORCL tearsheet, 2026-08-09): sector_peers paketin %36'siydi ve
# ciktida yalnizca "bu emsal grubu heterojen" denip reddedilmek icin
# kullanildi. Emsal degerlemesi comps-valuation'in isi, tearsheet'in degil.
STEP_BLOCKS = {
    "tearsheet": {"sector_peers": False, "deterministic_signals": False,
                  "own_valuation_history": True,
                  "next_events": True, "roic": True, "special_situations": True,
                 "quarterly_series": False, "pre_print_consensus": False, "net_debt": True},
    "comps": {"sector_peers": True, "deterministic_signals": False,
              "own_valuation_history": True,
              "next_events": False, "roic": True, "special_situations": True,
             "quarterly_series": False, "pre_print_consensus": False, "net_debt": True},
    "preview": {"sector_peers": False, "deterministic_signals": True,
                "own_valuation_history": False,
                "next_events": True, "roic": False, "special_situations": True,
               "quarterly_series": False, "pre_print_consensus": False, "net_debt": True},
    "deepdive": {"sector_peers": False, "deterministic_signals": True,
                 "own_valuation_history": False,
                 "next_events": True, "roic": True, "special_situations": True,
                 "quarterly_series": True, "pre_print_consensus": True, "net_debt": True},
    "pitch": {"sector_peers": True, "deterministic_signals": True,
              "own_valuation_history": True,
              "next_events": True, "roic": True, "special_situations": True,
             "quarterly_series": False, "pre_print_consensus": False, "net_debt": True},
    "idea": {"sector_peers": False, "deterministic_signals": True,
             "own_valuation_history": True,
             "next_events": True, "roic": True, "special_situations": True,
            "quarterly_series": False, "pre_print_consensus": False, "net_debt": True},
    # pitch ile ayni -- sector_peers disinda. scenario-sensitivity-generator
    # sirketin KENDI rakamlarinin araligini hesapliyor, emsal karsilastirmasi
    # yapmiyor (referances/*.md hicbir tabloda peer verisi istemiyor).
    "scenario": {"sector_peers": False, "deterministic_signals": True,
                 "own_valuation_history": True,
                 "next_events": True, "roic": True, "special_situations": True,
                "quarterly_series": False, "pre_print_consensus": False, "net_debt": True},
    # pitch ile ayni genislik: initiating-coverage tam bir baslangic raporu
    # icin butun deterministik katmanlari istiyor. Segment/urun duzeyinde
    # cok yillik model ve klinik/anlasma detayi kasten YOK -- bu skill onu
    # web aramasiyla kendi kuruyor (bkz. ABBV test koşusu); pack yalnizca
    # fiyat/degerleme/konsensus/ozel durum icin "source of truth" katmani.
    "initiation": {"sector_peers": True, "deterministic_signals": True,
                   "own_valuation_history": True,
                   "next_events": True, "roic": True, "special_situations": True,
                  "quarterly_series": False, "pre_print_consensus": False, "net_debt": True},
}


def latest_complete_month(run_root: Path) -> str:
    """En az bir sirketi basariyla uretilmis en yeni canli kesit.

    Tek bir sirketin SEC/XBRL boslugu diger sirketlerin paketini bloke etmez.
    Kapsam eksigi ``coverage.json`` ve pack'in ``universe_coverage`` alaninda
    acikca tasinir; henuz hic sirket uretilmemis bir kesit kullanilmaz.
    """
    months = []
    for folder in (run_root / "months").iterdir():
        marker = folder / "cutoff.json"
        coverage_path = folder / "coverage.json"
        if not marker.is_file() or not coverage_path.is_file():
            continue
        cutoff_payload = json.loads(marker.read_text(encoding="utf-8"))
        cutoff = cutoff_payload["cutoff_date"]
        precedence = cutoff_payload.get("cutoff_instant") or cutoff
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        if int(coverage.get("covered") or 0) > 0:
            months.append((precedence, folder.name))
    if not months:
        raise SystemExit(f"{run_root}: kullanilabilir canli kesit yok")
    # Siralama KLASOR ADIYLA degil KESIN CUTOFF ANIYLA yapilir. Kokte iki
    # adlandirma yan yana yasiyor: eskiden ay adiyla ("2026-08", kesimi
    # 31 Temmuz), simdi kesim adiyla ("2026-08-07"). Lexik sirada
    # "2026-08-07" > "2026-08" oldugu icin bugun dogru olan seciliyor ama
    # bu tesaduf: eski semadan kalma bir "2026-09" hepsini yenerdi.
    return max(months)[1]


def resolve_live_month(run_root: Path, requested: str | None) -> str:
    """Live pack her zaman eldeki en yeni kullanilabilir kesitten kurulur."""
    latest = latest_complete_month(run_root)
    if requested is not None and requested != latest:
        raise SystemExit(
            f"live pack eski kesitten uretilmez: istenen {requested}, "
            f"en son canli kesit {latest}. Backtest/replay aracini kullanin."
        )
    return latest


def set_live_decision_date(pack: dict, built_on: str) -> None:
    """Canli pack karar tarihini kosu gunune bagla.

    Kaynak finansal artifact'in tarihi ``cutoff_instant`` ve ``execution_date``
    alanlarinda korunur. ``decision_date`` ise tarihsel artifact'ten miras
    alinmaz; bu pack'in hangi gun karar icin uretildigini anlatir.
    """
    pack["decision_date"] = built_on


def align_subset_coverage(pack: dict, keep_set: set[str]) -> None:
    """Alt kumeye daraltilmis pack'in coverage metadatasini hizala."""
    coverage = pack.get("universe_coverage")
    if not isinstance(coverage, dict):
        return
    source_included = coverage.get("included_count")
    if isinstance(source_included, int):
        coverage["source_included_count"] = source_included
    coverage["included_count"] = len(pack.get("companies") or [])
    missing = coverage.get("missing_financial_artifacts")
    if isinstance(missing, list):
        coverage["missing_financial_artifacts"] = [
            ticker for ticker in missing if ticker in keep_set
        ]


def latest_consensus() -> tuple[dict, str, Path]:
    files = sorted(CONSENSUS_DIR.glob("snapshot-*.json"))
    if not files:
        raise SystemExit("konsensus snapshot yok -- once us_consensus_snapshot.py")
    path = files[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["companies"], payload["snapshot_date"], path


def sector_of() -> dict[str, str]:
    out = {}
    for path in PEERS.glob("*.json"):
        for member in json.loads(path.read_text(encoding="utf-8"))["members"]:
            out[member["ticker"]] = path.stem
    return out


def attach_consensus(pack: dict, companies: dict, as_of: str) -> tuple[int, list[str]]:
    hit, missing = 0, []
    for entry in pack["companies"]:
        record = companies.get(entry["ticker"])
        if not record:
            entry["consensus_estimates"] = {
                "status": "unavailable",
                "reason": "ticker not in consensus snapshot",
            }
            missing.append(entry["ticker"])
            continue
        entry["consensus_estimates"] = {
            "status": "available",
            "as_of": as_of,
            "source": "yfinance / Yahoo Finance analyst estimates",
            **{k: record[k] for k in CARRY if k in record},
        }
        hit += 1
    return hit, missing


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _tearsheet_identity(run_root: Path, ticker: str) -> dict:
    config = _load_json(REPO / "config" / "companies" / f"{ticker}.json")
    discovery = _load_json(
        run_root / "ledger" / "sec-discovery-payloads" /
        f"CIK{str((config.get('sources') or {}).get('cik') or '').zfill(10)}.json"
    )
    if not discovery:
        index = _load_json(run_root / "ledger" / "sec-discovery.json")
        record = ((index.get("submissions") or {}).get(ticker) or {})
        relative = record.get("relative_path")
        if relative:
            discovery = _load_json(run_root / relative)

    classification = config.get("classification") or {}
    address = (discovery.get("addresses") or {}).get("business") or {}
    headquarters = {
        key: address.get(key)
        for key in ("city", "stateOrCountry", "country", "zipCode")
        if address.get(key) is not None
    }
    return {
        "legal_name": discovery.get("name") or config.get("company_name"),
        "ticker": ticker,
        "exchange": config.get("exchange") or next(iter(discovery.get("exchanges") or []), None),
        "cik": str(discovery.get("cik") or "").zfill(10) or None,
        "sic": discovery.get("sic"),
        "sic_description": discovery.get("sicDescription"),
        "fiscal_year_end": discovery.get("fiscalYearEnd"),
        "headquarters": headquarters or None,
        "sector": classification.get("official_sector"),
        "industry": classification.get("official_industry"),
        "subindustry": classification.get("official_subindustry"),
        "actual_activity": classification.get("actual_activity"),
        "classification_as_of": classification.get("classification_date"),
        "sources": {
            "identity": (config.get("sources") or {}).get("identity_source"),
            "classification": (config.get("sources") or {}).get("classification_source"),
            "sec_submissions": (
                f"sec-submissions-{str(discovery.get('cik')).zfill(10)}"
                if discovery.get("cik") is not None else None
            ),
        },
    }


def _metric_evidence(item: dict) -> dict:
    provenance = item.get("provenance") or {}
    direct = item.get("data_type") == "direct"
    return {
        "metric_id": item.get("metric_id"),
        "name": item.get("name"),
        "value": item.get("value"),
        "unit": item.get("unit"),
        "period": item.get("period"),
        "comparison_value": item.get("comparison_value"),
        "comparison_period": item.get("comparison_period"),
        "status": item.get("status"),
        "source": provenance.get("source_id"),
        "source_location": {
            key: provenance.get(key)
            for key in ("source_file", "sheet", "cell_or_range", "page")
            if provenance.get(key) is not None
        } or None,
        "evidence": "fact_source_reported" if direct else "derived_calculation",
        "confidence": "high" if direct and provenance.get("source_id") else "medium",
        "calculation": provenance.get("formula"),
        "notes": provenance.get("notes"),
    }


def _tearsheet_reported_financials(run_root: Path, ticker: str, period: str) -> dict:
    payload = _load_json(run_root / "data" / "financial" / ticker / f"{period}.json")
    metrics_by_id = {
        item.get("metric_id"): item
        for section in ("income_statement", "balance_sheet", "cash_flow_statement")
        for item in (payload.get(section) or [])
        if isinstance(item, dict) and item.get("metric_id")
    }
    metrics = [
        _metric_evidence(metrics_by_id[metric_id])
        for metric_id in TEARSHEET_FINANCIAL_METRICS
        if metric_id in metrics_by_id
    ]
    return {
        "period": payload.get("period") or period,
        "period_start": payload.get("period_start"),
        "period_end": payload.get("period_end"),
        "period_type": payload.get("period_type"),
        "currency": payload.get("currency"),
        "scale": payload.get("scale"),
        "accounting_basis": payload.get("accounting_basis"),
        "audit_status": payload.get("audit_status"),
        "publication_date": payload.get("publication_date"),
        "source_revision": payload.get("source_revision"),
        "metrics": metrics,
    }


def _tearsheet_risks(run_root: Path, ticker: str, period: str) -> dict:
    payload = _load_json(run_root / "data" / "risks" / ticker / f"{period}.json")
    risks = []
    for item in payload.get("risks") or []:
        if not isinstance(item, dict):
            continue
        risks.append({
            key: item.get(key)
            for key in ("risk_id", "category", "title", "description", "direction",
                        "severity", "severity_rationale", "time_horizon", "evidence",
                        "mitigants", "quantified_effect", "notes")
        })
    return {
        "status": payload.get("analysis_status") or "unavailable",
        "as_of": payload.get("as_of"),
        "scope_note": payload.get("scope_note"),
        "risks": risks,
    }


def _tearsheet_sources(run_root: Path, entry: dict, identity: dict,
                       financials: dict, risks: dict) -> list[dict]:
    ticker = entry["ticker"]
    manifest = _load_json(run_root / "data" / "source-manifests" / f"{ticker}.json")
    used_ids = {
        metric.get("source")
        for metric in financials.get("metrics") or []
        if metric.get("source")
    }
    for risk in risks.get("risks") or []:
        for evidence in risk.get("evidence") or []:
            if evidence.get("source_id"):
                used_ids.add(evidence["source_id"])
    release = entry.get("latest_earnings_release") or {}
    if release.get("source_id"):
        used_ids.add(release["source_id"])

    sources = []
    for item in manifest.get("sources") or []:
        if item.get("source_id") not in used_ids:
            continue
        sources.append({
            "source_id": item.get("source_id"),
            "source_name": item.get("path"),
            "source_type": item.get("source_type"),
            "provider_or_owner": "SEC",
            "as_of_date": item.get("publication_date"),
            "period_covered": item.get("periods_covered"),
            "source_location": item.get("path"),
            "freshness_status": "current",
            "sha256": item.get("sha256"),
            "notes": item.get("notes"),
        })

    synthetic = [
        {
            "source_id": f"company-config-{ticker}",
            "source_name": f"config/companies/{ticker}.json",
            "source_type": "workspace_config",
            "provider_or_owner": "trade_us",
            "as_of_date": identity.get("classification_as_of"),
            "source_location": f"config/companies/{ticker}.json",
            "freshness_status": "current",
        },
        {
            "source_id": identity.get("sources", {}).get("sec_submissions"),
            "source_name": "SEC company submissions payload",
            "source_type": "sec_submissions",
            "provider_or_owner": "SEC",
            "as_of_date": identity.get("classification_as_of"),
            "source_location": (
                "live/current/ledger/sec-discovery-payloads/"
                f"CIK{identity.get('cik')}.json"
            ),
            "freshness_status": "current",
        },
        {
            "source_id": f"market-pack-{ticker}",
            "source_name": "point-in-time market and valuation artifacts",
            "source_type": "workspace_market_artifacts",
            "provider_or_owner": "trade_us pipeline",
            "as_of_date": (
                entry.get("market_data_as_of")
                or entry.get("price_reconciliation", {}).get("multiples_price_as_of")
            ),
            "source_location": f"live/current/data/market/{ticker}",
            "freshness_status": "current",
        },
    ]
    if release.get("status") == "available":
        synthetic.append({
            "source_id": release.get("source_id"),
            "source_name": f"SEC earnings release {release.get('accession')}",
            "source_type": "sec_earnings_release",
            "provider_or_owner": "SEC / issuer",
            "as_of_date": release.get("filing_date"),
            "source_location": f"guidance/{ticker}/{release.get('accession')}",
            "freshness_status": "current",
            "sha256": release.get("text_sha256"),
        })
    consensus = entry.get("consensus_estimates") or {}
    if consensus.get("status") == "available":
        synthetic.append({
            "source_id": f"consensus-{ticker}",
            "source_name": consensus.get("source"),
            "source_type": "provider_snapshot",
            "provider_or_owner": consensus.get("source"),
            "as_of_date": consensus.get("as_of"),
            "source_location": f"data/consensus/snapshot-{consensus.get('as_of')}.json",
            "freshness_status": "current",
        })
    return [item for item in sources + synthetic if item.get("source_id")]


def _tearsheet_evidence_gaps(entry: dict, identity: dict,
                             financials: dict, risks: dict) -> list[dict]:
    gaps = [
        {"field": field, "status": "missing_required_source", "reason": reason}
        for field, reason in TEARSHEET_EXTERNAL_GAPS
    ]
    checks = (
        ("legal_name", identity.get("legal_name"), "company identity is unavailable"),
        ("exchange", identity.get("exchange"), "listing venue is unavailable"),
        ("reported_financials", financials.get("metrics"), "latest reported financial metrics are unavailable"),
        ("risk_factors", risks.get("risks"), "normalized SEC risk factors are unavailable"),
        ("consensus", (entry.get("consensus_estimates") or {}).get("status") == "available",
         "current consensus snapshot is unavailable"),
    )
    for field, present, reason in checks:
        if not present:
            gaps.append({"field": field, "status": "missing_required_source", "reason": reason})
    return gaps


def attach_tearsheet_context(pack: dict, run_root: Path) -> None:
    """Pack'teki mevcut repo artefaktlarini tearsheet icin kanitli hale getir."""
    for entry in pack.get("companies") or []:
        ticker = entry["ticker"]
        period = entry.get("period_label")
        identity = _tearsheet_identity(run_root, ticker)
        financials = _tearsheet_reported_financials(run_root, ticker, period)
        risks = _tearsheet_risks(run_root, ticker, period)
        release = entry.get("latest_earnings_release") or {}
        entry["identity"] = identity
        entry["business_profile"] = {
            "status": "partial",
            "company_name": identity.get("legal_name"),
            "sector": identity.get("sector"),
            "industry": identity.get("industry"),
            "actual_activity": identity.get("actual_activity"),
            "latest_issuer_reported_context": {
                "as_of": release.get("filing_date"),
                "source": release.get("source_id"),
                "evidence": "issuer_management_claim",
                "confidence": "high" if release.get("status") == "available" else "low",
                "excerpts": release.get("excerpts") or [],
            },
            "limitation": (
                "Normalized product, segment and geographic mix is not available; "
                "the external research layer may complete it."
            ),
        }
        entry["reported_financials"] = financials
        metric_map = {
            item["metric_id"]: item
            for item in financials.get("metrics") or []
        }
        entry["capital_allocation"] = {
            "period": financials.get("period"),
            "dividends_paid": metric_map.get("cf_dividends_paid"),
            "share_repurchases": metric_map.get("cf_share_repurchases"),
        }
        entry["risk_factors"] = risks
        entry["sources"] = _tearsheet_sources(run_root, entry, identity, financials, risks)
        entry["evidence_gaps"] = _tearsheet_evidence_gaps(entry, identity, financials, risks)


def attach_events(pack: dict) -> tuple[int, str | None]:
    """Ileri bilanco/temettu tarihi -- katalist boyutunun zamanlama kismi."""
    files = sorted((REPO / "data" / "events").glob("snapshot-*.json"))
    if not files:
        return 0, None
    payload = json.loads(files[-1].read_text(encoding="utf-8"))
    as_of, companies = payload["snapshot_date"], payload["companies"]
    hit = 0
    for entry in pack["companies"]:
        record = companies.get(entry["ticker"]) or {}
        day = record.get("next_earnings_date")
        if not day or record.get("is_past"):
            entry["next_events"] = {
                "status": "unavailable",
                "reason": ("reported date is in the past; the next one is not "
                           "published yet" if record.get("is_past")
                           else "no forward date available"),
            }
            continue
        entry["next_events"] = {
            "status": "available",
            "as_of": as_of,
            "source": payload["source"],
            "next_earnings_date": day,
            "date_confirmed": False,
            "confirmation_note": ("Yahoo does not distinguish a company-announced "
                                  "date from an estimate. Treat as estimated "
                                  "until the IR page confirms it."),
            "dividend_date": record.get("dividend_date"),
            "ex_dividend_date": record.get("ex_dividend_date"),
        }
        hit += 1
    return hit, as_of


def attach_valuation_history(pack: dict, horizon: str) -> tuple[int, str | None]:
    """Sirketin KENDI carpan araligi -- "gecmisine gore ucuz mu"."""
    path = REPO / "data" / "valuation-history" / "history.json"
    if not path.is_file():
        return 0, None
    payload = json.loads(path.read_text(encoding="utf-8"))
    companies = payload["companies"]
    hit, newest = 0, None
    for entry in pack["companies"]:
        history = companies.get(entry["ticker"])
        if not history:
            continue
        block = {}
        for label, stats in history.items():
            # Seri KESIM TARIHINE kesilir. Onceden hesaplanmis yuzdelikler
            # butun araligi kapsar ve gecmis bir pakete oldugu gibi konursa
            # gelecek sizar (2025-01 denemesinde 19 ay sizmisti).
            points = [(d, v) for d, v in stats.get("series", []) if d <= horizon]
            if len(points) < 8:
                continue
            values = sorted(v for _d, v in points)
            n = len(values)

            def at(fraction: float, _v=values, _n=n) -> float:
                return round(_v[min(_n - 1, max(0, int(round(fraction * (_n - 1)))))], 4)

            stats = {**stats, "observations": n,
                     "first_as_of": points[0][0], "last_as_of": points[-1][0],
                     "last_value": round(points[-1][1], 4),
                     "min": at(0), "p25": at(0.25), "median": at(0.5),
                     "p75": at(0.75), "max": at(1.0), "n": n}
            stats.pop("series", None)
            # Konum, serinin KENDI son noktasindan hesaplanir. Paketin
            # `valuation` blogu ayri bir hesaplama ve birimi farkli olabilir
            # (kazanc getirisi orada yuzde, burada oran) -- iki kaynagi
            # karsilastirmak sessiz bir hata uretiyordu.
            now = stats.get("last_value")
            where = None
            if isinstance(now, (int, float)):
                if now <= stats["p25"]:
                    where = "at or below its own 25th percentile"
                elif now <= stats["median"]:
                    where = "between its 25th percentile and median"
                elif now <= stats["p75"]:
                    where = "between its median and 75th percentile"
                else:
                    where = "at or above its own 75th percentile"
            block[label] = {**stats, "latest_sits": where}
        if block:
            latest = max(s["last_as_of"] for s in block.values())
            entry["own_valuation_history"] = {
                "status": "available",
                "span": [min(s["first_as_of"] for s in block.values()), latest],
                "cross_sections": payload["cross_sections"],
                "note": payload["note"],
                "unit_warning": (
                    "This block is internally consistent and self-contained. Its "
                    "values come from the point-in-time valuation engine and may "
                    "use a different unit or basis from the `valuation` block "
                    "above (earnings yield is a percentage there and a fraction "
                    "here). Compare inside this block only; never place a number "
                    "from `valuation` onto this scale."),
                "methods": block,
            }
            hit += 1
            newest = latest if newest is None else max(newest, latest)
    return hit, newest


def refresh_prices(pack: dict) -> tuple[int, str | None]:
    """Fiyat ve piyasa istatistiklerini son tamamlanmis seansa cek.

    Fiyat, donmus aylik kosunun defterinden geliyordu ve gunlerce bayat
    kalabiliyor (2026-08-09'da 5 gun; o arada piyasa ortalama %3, ORCL %13
    hareket etmisti). Uyari yazmak yerine sayiyi tazelemek dogrusu.

    Yeniden olcekleme TAM, tahmin degil: birkac gunde kazanc, ozkaynak ve
    nakit akisi degismez, yalniz fiyat degisir. Dogrulandi (ORCL): F/K'dan
    ima edilen EPS geri cikarilip yeni fiyatla dogrudan hesaplandiginda
    olcekleme ile farki 0,000000.

    ISTISNA: girisim degeri tabanli carpanlar (FD/FVOK, FD/FAVOK) boyle
    olceklenmez -- FD = piyasa degeri + net borc ve borc fiyatla degismez.
    Onlar kesim fiyatinda BIRAKILIR ve oyle isaretlenir.
    """
    import yfinance as yf

    symbols = [c["ticker"] for c in pack["companies"]]
    quotes: dict[str, float] = {}
    current_market: dict[str, dict] = {}
    try:
        # threads=False: yfinance'in threaded indiricisi curl_cffi'yi
        # esas alan native HTTP istemcisini paralel cagirir; Windows'ta bu
        # curl_cffi native cagrilari arasinda araliksiz segfault'a yol
        # aciyordu (PYTHONFAULTHANDLER ile yfinance/multi.py -> curl_cffi
        # icinde SIGSEGV olarak dogrulandi). Seri indirme daha yavas ama
        # kararli.
        data = yf.download(symbols, period="18mo", progress=False,
                           auto_adjust=False, threads=False)["Close"]
        volume_data = yf.download(symbols, period="18mo", progress=False,
                                  auto_adjust=False, threads=False)["Volume"]
        for symbol in symbols:
            close_column = data[symbol] if len(symbols) > 1 else data
            volume_column = volume_data[symbol] if len(symbols) > 1 else volume_data
            frame = close_column.to_frame("close").join(
                volume_column.to_frame("volume"), how="left"
            ).dropna(subset=["close"])
            if not len(frame):
                continue
            quotes[symbol] = float(frame["close"].iloc[-1])
            closes = [float(value) for value in frame["close"]]

            def trailing_return(sessions: int) -> float | None:
                if len(closes) <= sessions or closes[-sessions - 1] == 0:
                    return None
                return round((closes[-1] / closes[-sessions - 1] - 1) * 100, 2)

            daily_returns = [
                closes[index] / closes[index - 1] - 1
                for index in range(1, len(closes))
                if closes[index - 1] != 0
            ]
            recent_returns = daily_returns[-252:]
            volatility = (
                round(statistics.stdev(recent_returns) * (252 ** 0.5) * 100, 2)
                if len(recent_returns) >= 2 else None
            )
            window = closes[-253:]
            peak = window[0]
            max_drawdown = 0.0
            for value in window:
                peak = max(peak, value)
                max_drawdown = min(max_drawdown, value / peak - 1)
            recent = frame.tail(20).dropna(subset=["volume"])
            adv = (
                round(float((recent["close"] * recent["volume"]).mean()) / 1_000_000, 2)
                if len(recent) else None
            )
            current_market[symbol] = {
                "return_1m_pct": trailing_return(21),
                "return_3m_pct": trailing_return(63),
                "return_6m_pct": trailing_return(126),
                "return_12m_pct": trailing_return(252),
                "annualized_volatility_pct": volatility,
                "max_drawdown_12m_pct": round(max_drawdown * 100, 2),
                "avg_dollar_volume_20d_usd_m": adv,
            }
        as_of = str(data.dropna(how="all").index[-1].date())
    except Exception as exc:
        for entry in pack["companies"]:
            entry["price_refresh"] = {"status": "unavailable", "reason": str(exc)[:120]}
        return 0, None

    hit = 0
    for entry in pack["companies"]:
        now = quotes.get(entry["ticker"])
        anchor = entry.get("closing_price_usd")
        if not now or not anchor:
            entry["price_refresh"] = {"status": "unavailable"}
            continue
        ratio = now / anchor
        cutoff_market = dict(entry.get("market") or {})
        refreshed_market = current_market.get(entry["ticker"])
        if refreshed_market:
            entry["market_statistics_at_cutoff"] = cutoff_market
            entry["market_statistics_at_cutoff_as_of"] = pack["execution_date"]
            entry["market"] = refreshed_market
            entry["market_statistics_as_of"] = as_of
            entry["market_statistics_refresh_status"] = "available"
        else:
            entry["market_statistics_as_of"] = pack["execution_date"]
            entry["market_statistics_refresh_status"] = "unavailable"
        rescaled, left = {}, []
        for label, value in (entry.get("valuation") or {}).items():
            if not isinstance(value, (int, float)):
                continue
            if "Enterprise Value" in label:
                left.append(label)          # FD tabanli -- olceklenmez
                continue
            rescaled[label] = round(value / ratio if "Yield" in label
                                    else value * ratio, 4)
        entry["price_refresh"] = {
            "status": "available",
            "price_now": round(now, 4),
            "price_as_of": as_of,
            "price_at_cutoff": anchor,
            "cutoff_price_as_of": pack["execution_date"],
            "change_pct": round((ratio - 1) * 100, 2),
            "market_cap_now_usd_m": (round(entry["market_cap_usd_m"] * ratio, 1)
                                     if entry.get("market_cap_usd_m") else None),
            "valuation_at_price_now": rescaled,
            "not_rescaled": left,
            "not_rescaled_reason": ("enterprise-value multiples do not scale with "
                                    "price alone: EV = market cap + net debt, and "
                                    "debt did not move. These stay at the cutoff "
                                    "price."),
            "method": "exact: only price changed, so a price multiple scales by "
                      "the price ratio and a yield by its inverse",
        }
        hit += 1
    return hit, as_of


# SEC 8-K madde kodlari. workflow.md Bolum 2 "recent IPO, spin-off, merger,
# divestiture, restatement, fiscal-year change" bayraklanmasini istiyor.
#
# NEDEN ONEMLI: HON Haziran 2026'da Aerospace'i ayirdi, ama paket 2026-Q2
# gelirini (18.862) bir onceki yilin 18.247'siyle yan yana koyuyordu ve
# hicbir sey bunlarin ayni isletme OLMADIGINI soylemiyordu. `restatement`
# alani "original" diyor -- spin'i yakalamiyor.
HIGH_SIGNAL = {
    "2.01": "completed acquisition or disposition of assets",
    "4.02": "previously issued financials should no longer be relied upon",
    "2.06": "material impairment",
}
# 5.03 hem mali yil degisikligi hem esas sozlesme degisikligi demek ve evrende
# 19 sirkette gorunuyor; tek basina sinyal degil, baglam.
CONTEXT_SIGNAL = {
    "5.03": "amended articles/bylaws, or a change of fiscal year",
    "2.05": "costs associated with exit or disposal",
}

# ISLEM FILING GECMISI: birlesme/devralma ile iliskili form gorulmus.
#
# 2.01 yalniz TAMAMLANMIS islemi yakaliyor. NSC'nin 85 milyar dolarlik
# bekleyen birlesmesi bu yuzden pakette hic gorunmedi ve tarama onu ceyreklik
# kar dususu yuzunden reddetti -- devralma altindaki bir sirket icin o rakam
# neredeyse ilgisiz.
#
# Ilk akla gelen cozum 8-K madde 1.01 ("esasli sozlesmeye giris") idi. OLCULDU
# ve elendi: 60 sirketin 39'unda goruluyor, cunku her rutin kredi sozlesmesi ve
# tahvil ihraci da 1.01. 8.01 daha kotu, 56/60. Ikisi de 5.03'un dustugu tuzak.
#
# Ayirt eden sey madde kodu degil FORM TIPI. Bir islem duyuruldugunda taraflar
# 425 (birlesme iletisimi), S-4 (islemde ihrac edilecek pay kaydi) ve DEFM14A
# (birlesme vekaleti) dosyalamak ZORUNDA; bunlarin baska kullanimi yok.
# Olculdu, ayni 24 aylik pencere: 8/60 sirket. DEFA14A bilerek DISARIDA --
# olagan genel kurul materyali, 57/60'ta goruluyor ve sinyali yok ediyor.
TRANSACTION_FILING_FORMS = ("425", "S-4", "DEFM14A", "PREM14A", "SC 13E3")


def _mark_broken_comparisons(entry: dict, high: list[dict], cutoff: date) -> None:
    """Yapisal olay yillik karsilastirmayi kirdiysa BUNU ORADA soyle.

    HON'da bayrak zaten vardi -- 2026-06-29 tarihli 8-K madde 2.01, Aerospace
    ayrilmasi. Ama paket onu ayri bir blokta bildirip fundamentals icinde net
    kar buyumesini +%113,5 ve OCF buyumesini -%67,3 diye sundu. Bu sayilar
    ayrilma SONRASI donemi ayrilma ONCESI tabana olcuyor: aritmetik dogru,
    ekonomik olarak anlamsiz. Tarama sayilara inandi, bayraga degil, ve HON'u
    "nakit kalitesi bozuk" diyerek reddetti.

    Ders: uyariyi olcunun yaninda degil, olcunun ICINDE tasi. Tek donem
    oranlari (marj, cari oran, borc/ozkaynak) etkilenmez -- onlar iki donemi
    karsilastirmiyor; yalniz *_growth alanlari kirilir.
    """
    window_start = cutoff.replace(year=cutoff.year - 1).isoformat()
    inside = [h for h in high if h["date"] >= window_start]
    if not inside:
        return
    affected = sorted(k for k in entry.get("fundamentals", {}) if k.endswith("_growth"))
    if not affected:
        return
    entry["fundamentals_comparability"] = {
        "status": "year-over-year growth is not like-for-like",
        "affected_fields": affected,
        "events": inside,
        "note": (
            "A structural event is dated inside the twelve months these growth "
            "rates span, so the current period and the prior-year figure it is "
            "measured against do not cover the same set of businesses. Neither "
            "period was restated in this pack. Single-period ratios in "
            "`fundamentals` -- margins, current ratio, leverage -- compare "
            "nothing and are unaffected."),
        "not_in_this_pack": (
            "Restated or continuing-operations figures that would make the two "
            "periods comparable."),
    }


def flag_special_situations(pack: dict, source_run: Path,
                            months: int = 24) -> tuple[int, list[str]]:
    """Spin, satin alma, elden cikarma, duzeltme, mali yil degisikligi."""
    ledger_path = source_run / "ledger" / "sec-discovery.json"
    if not ledger_path.is_file():
        return 0, []
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    cutoff = date.fromisoformat(pack["cutoff_instant"][:10])
    since = (cutoff.replace(year=cutoff.year - (months // 12))).isoformat()

    hit, names = 0, []
    for entry in pack["companies"]:
        submission = ledger.get("submissions", {}).get(entry["ticker"])
        if not submission:
            continue
        recent = (json.loads((source_run / submission["relative_path"])
                             .read_text(encoding="utf-8"))
                  .get("filings", {}).get("recent", {}))
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        codes = recent.get("items", [""] * len(forms))
        high, context, amended, deal = [], [], [], []
        for form, day, code in zip(forms, dates, codes):
            if not (since <= day <= cutoff.isoformat()):
                continue
            if form.startswith(("10-Q/A", "10-K/A")):
                amended.append({"date": day, "form": form})
            if form.startswith(TRANSACTION_FILING_FORMS):
                deal.append({"date": day, "form": form})
            for part in (code or "").split(","):
                part = part.strip()
                if part in HIGH_SIGNAL:
                    high.append({"date": day, "item": part,
                                 "meaning": HIGH_SIGNAL[part]})
                elif part in CONTEXT_SIGNAL:
                    context.append({"date": day, "item": part,
                                    "meaning": CONTEXT_SIGNAL[part]})
        if deal:
            forms = sorted({d["form"] for d in deal})
            # Rol, dosyalanan form tipinden cikar ve bir yorum degil bir olgudur:
            # birlesme vekaleti KENDI ortaklarindan onay ister, S-4 ise islemde
            # IHRAC EDILECEK payi kaydeder. NSC'de DEFM14A var S-4 yok, UNP'de
            # tersi -- ayni islemin iki tarafi. Yalniz 425 varsa rol bilinmiyor
            # ve bilinmiyor denir.
            proxy = any(f.startswith(("DEFM14A", "PREM14A")) for f in forms)
            registered = any(f.startswith("S-4") for f in forms)
            if proxy and not registered:
                role, basis = "filed to solicit its own shareholders", "filed a merger proxy (DEFM14A/PREM14A) and no S-4"
            elif registered and not proxy:
                role, basis = "filed to register securities for a transaction", "filed an S-4 and no merger proxy"
            else:
                role, basis = "not determinable from form mix", "filed neither form, or both"
            entry["transaction_filing_history"] = {
                "status": "transaction-related filing history; current status not determined",
                "current_transaction_status": "not determined from filing-form history",
                "verification_required": True,
                "filing_count": len(deal),
                "first_filing": min(d["date"] for d in deal),
                "latest_filing": max(d["date"] for d in deal),
                "forms": forms,
                "filing_role_indicator": role,
                "filing_role_basis": basis,
                "not_established_by_pack": (
                    "Whether a transaction remains pending, completed, terminated "
                    "or superseded; deal terms, consideration, counterparty, closing "
                    "timetable and regulatory status. Filing-form history alone does "
                    "not establish current transaction status."),
            }
        if not (high or amended):
            if context:
                entry["special_situations"] = {"status": "context only",
                                               "context": context}
            continue
        entry["special_situations"] = {
            "status": "structural event in the last two years",
            "high_signal": high,
            "amended_periodic_filings": amended,
            "context": context,
            "why_it_matters": (
                "A completed acquisition or disposition changes what the company "
                "is. Year-over-year comparisons in this pack place the current "
                "period beside the prior-year figure without restating either, "
                "so across such an event the two are not the same business. An "
                "amended 10-Q or 10-K means a previously filed period was "
                "revised."),
            "scope": ("Any growth rate or multiple built across the event date "
                      "spans the change, so the movement it shows is not "
                      "wholly organic."),
        }
        _mark_broken_comparisons(entry, high, cutoff)
        hit += 1
        names.append(entry["ticker"])
    return hit, names


EARNINGS_QUALITY_GAP_THRESHOLD_PCT = 25.0


def flag_earnings_quality(pack: dict, horizon: str) -> tuple[int, list[str]]:
    """Net kar ile faaliyet kari arasindaki buyuk sapmayi bayrakla.

    GOOGL 2026-Q2'de faaliyet kari $80.5B, net kar $174.8B -- fark
    muhtemelen faaliyet-disi bir kalemden (ör. halka acik hisse
    yatirimlarinin gerceklesmemis deger artisi) geliyor ve P/E'yi
    carpitiyor. idea-generation skill'i bunu kendi basina dogru teshis
    etti ("17.2x P/E is contaminated by exceptional other income") ve
    kataloğumuzda olmayan bir "financials-normalizer" adimi istedi --
    asil eksik olan ayri bir workflow degil, bu sapmayi gosteren bir
    pack alaniydi.

    `entry["reported_financials"]` yalniz tearsheet adiminda ve tek
    sirket icin doluyor (attach_tearsheet_context), o yuzden buradan
    okunamaz -- attach_roic gibi ham filing dosyalarindan hesaplanir ki
    her `--for` adiminda ve butun evrende calissin.
    """
    source = pack.get("_financial_root")
    if source is None:
        return 0, []
    root = Path(source)
    hit, names = 0, []
    for entry in pack["companies"]:
        folder = root / entry["ticker"]
        files = sorted(p for p in folder.glob("*.json")
                       if "derived" not in p.name) if folder.is_dir() else []
        income = None
        for path in sorted(files, reverse=True):
            try:
                candidate = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            published = candidate.get("publication_date")
            if published and published > horizon:
                continue
            inc = {i["metric_id"]: i.get("value")
                   for i in candidate.get("income_statement", [])}
            if isinstance(inc.get("operating_profit"), (int, float)) and (
                isinstance(inc.get("net_profit_for_period"), (int, float))
                or isinstance(inc.get("net_profit_attributable_parent"), (int, float))
            ):
                income = inc
                break
        if income is None:
            continue
        operating = income["operating_profit"]
        net = income.get("net_profit_for_period", income.get("net_profit_attributable_parent"))
        if operating == 0:
            continue
        gap_pct = round((net - operating) / abs(operating) * 100, 1)
        if abs(gap_pct) < EARNINGS_QUALITY_GAP_THRESHOLD_PCT:
            continue
        direction = "higher" if gap_pct > 0 else "lower"
        entry["earnings_quality_flags"] = [{
            "flag": "net_income_diverges_from_operating_income",
            "operating_profit_musd": operating,
            "net_profit_musd": net,
            "gap_pct": gap_pct,
            "note": (
                f"Net income is {abs(gap_pct):.0f}% {direction} than operating "
                "income for this period. This is typically driven by "
                "non-operating items (investment gains/losses, other "
                "income/expense, tax items) rather than the core business. "
                "P/E and other net-income-based multiples may be misleading "
                "here; consider EV/EBIT or an operating-income-based multiple "
                "instead, or adjust net income for the flagged gap before "
                "comparing to peers."
            ),
        }]
        hit += 1
        names.append(entry["ticker"])
    return hit, names


def attach_roic(pack: dict, horizon: str) -> tuple[int, int]:
    """ROIC -- kalite boyutu adiyla istiyor, elimizde yoktu.

    NOPAT / yatirilmis sermaye. Girdiler bilancoda var ama TOPLAM BORC
    kalemi yok, o yuzden yatirilmis sermaye standart sadelestirmeyle
    kurulur: toplam varlik - kisa vadeli yukumluluk.

    Iki koruma: payda varliklarin %10'undan kucukse hesaplanmaz (sifira
    yakin payda carpani patlatir, metodoloji 0e), ve ceyreklik veri
    KUMULATIF oldugu icin NOPAT yillandirilir.
    """
    source = pack.get("_financial_root")
    if source is None:
        return 0, 0
    root = Path(source)
    ok = skipped = 0
    for entry in pack["companies"]:
        folder = root / entry["ticker"]
        files = sorted(p for p in folder.glob("*.json")
                       if "derived" not in p.name) if folder.is_dir() else []
        if not files:
            continue
        # UFKA UYAN ve alanlari TAM olan, donem sonu en yeni rapor.
        # Yayin tarihine gore secmek ekonomik olarak en yeni donemi degil en
        # son yayinlanani seciyordu ve 60 sirketin 52'sinde eksik alana
        # dusuyordu; ufuk suzgeci ise gecmis pakette gelecek donemi engeller.
        eligible = []
        for path in files:
            try:
                candidate = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            published = candidate.get("publication_date")
            if published and published > horizon:
                continue
            eligible.append((candidate.get("period_end") or "", candidate))
        payload = income = balance = None
        for _end, candidate in sorted(eligible, key=lambda row: row[0], reverse=True):
            inc = {i["metric_id"]: i.get("value")
                   for i in candidate.get("income_statement", [])}
            bal = {i["metric_id"]: i.get("value")
                   for i in candidate.get("balance_sheet", [])}
            needed = (inc.get("operating_profit"), inc.get("tax_expense_total"),
                      bal.get("total_assets"), bal.get("total_current_liabilities"))
            if all(isinstance(v, (int, float)) for v in needed):
                payload, income, balance = candidate, inc, bal
                break
        if payload is None:
            entry["roic"] = {"status": "not computed",
                             "reason": "no filing at or before the horizon carries "
                                       "operating profit, tax, total assets and "
                                       "current liabilities together"}
            skipped += 1
            continue
        ebit = income.get("operating_profit")
        tax = income.get("tax_expense_total")
        assets = balance.get("total_assets")
        current = balance.get("total_current_liabilities")
        invested = assets - current
        if invested <= 0 or invested < 0.10 * assets:
            entry["roic"] = {"status": "not computed",
                             "reason": "invested capital is too small a share of "
                                       "assets for the ratio to mean anything"}
            skipped += 1
            continue
        pretax = ebit + (income.get("financial_expense") or 0)
        rate = abs(tax) / pretax if pretax and pretax > 0 else None
        if rate is None or not (0 <= rate < 0.6):
            entry["roic"] = {"status": "not computed",
                             "reason": "effective tax rate outside a usable range"}
            skipped += 1
            continue
        try:
            start = date.fromisoformat(payload["period_start"])
            end = date.fromisoformat(payload["period_end"])
            days = max(1, (end - start).days)
        except Exception:
            days = 365
        nopat = ebit * (1 - rate) * (365.0 / days)
        entry["roic"] = {
            "status": "derived",
            "value_pct": round(100 * nopat / invested, 2),
            "period": payload.get("period"),
            "annualized_from_days": days,
            "invested_capital_musd": round(invested, 1),
            "definition": ("NOPAT / invested capital, where NOPAT is operating "
                           "profit after the effective tax rate, annualized from "
                           "the period length, and invested capital is total "
                           "assets less current liabilities"),
            "caveat": ("Derived here, not reported by the company. No total-debt "
                       "line exists in our statements, so invested capital uses "
                       "the assets-less-current-liabilities simplification and "
                       "will differ from a provider's ROIC."),
        }
        ok += 1
    return ok, skipped


def older_statement_with_debt(folder: Path, horizon: str):
    """Borcu tasiyan EN YENI donem. Bazi sirketler borcu yalniz yillik
    raporda etiketliyor; en yeni ceyrekte olmamasi borcu olmadigi anlamina
    gelmez."""
    if not folder.is_dir():
        return None
    best = None
    for path in folder.glob("*.json"):
        if "derived" in path.name:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        published = payload.get("publication_date")
        if published and published > horizon:
            continue
        keys = {i["metric_id"] for i in payload.get("balance_sheet", [])}
        if not (set(DEBT_LINES) & keys):
            continue
        end = payload.get("period_end") or ""
        if best is None or end > best[0]:
            best = (end, payload)
    return best[1] if best else None


DEBT_LINES = ("borrowings_short_term", "borrowings_long_term_current_portion",
              "borrowings_long_term", "borrowings_current_total",
              "borrowings_total")
CASH_LINES = ("cash_and_equivalents", "financial_investments_current")


def latest_statement(folder: Path, horizon: str):
    """Ufka kadar yayinlanmis, donem sonu en yeni rapor."""
    if not folder.is_dir():
        return None
    best = None
    for path in folder.glob("*.json"):
        if "derived" in path.name:
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
            best = (key, payload)
    return best[1] if best else None


def attach_net_debt(pack: dict, source_run: Path, horizon: str) -> tuple[int, list[str]]:
    """Net borc ve girisim degeri.

    Kaldirac bu pakette hic ifade edilemiyordu ve FD tabanli carpanlarin
    null gelmesinin sebebi buydu. ORCL'in butun tartismasi 129,5 milyar
    borc ve negatif serbest nakit akisi; onu tasiyamayan bir paket o
    sirketin hikayesini tasiyamaz.

    Kiralar AYRI tutulur: degerleme motoru "Lease-Exclusive Enterprise
    Value" diyor, yani kendi sozlesmesinde kiralari disarida birakiyor.
    Ikisini toplayip tek sayi vermek o sozlesmeyi sessizce bozardi.
    """
    root = source_run / "data" / "financial"
    ok, missing = 0, []
    for entry in pack["companies"]:
        payload = latest_statement(root / entry["ticker"], horizon)
        if payload is None:
            missing.append(entry["ticker"])
            continue
        balance = {i["metric_id"]: i.get("value")
                   for i in payload.get("balance_sheet", [])}
        debt = {k: balance[k] for k in DEBT_LINES
                if isinstance(balance.get(k), (int, float))}
        debt_as_of = payload.get("period_end")
        if not debt:
            # Bazi sirketler borcu yalniz YILLIK raporda etiketliyor (CAT,
            # MNST). En yeni donemde yoksa, borcu tasiyan en yeni donemi ara
            # -- bilanco kalemi nokta-zamanlidir, eski bir tarihten alinmasi
            # yaklasiktir ve OYLE ETIKETLENIR.
            fallback = older_statement_with_debt(root / entry["ticker"], horizon)
            if fallback:
                balance = {i["metric_id"]: i.get("value")
                           for i in fallback.get("balance_sheet", [])}
                debt = {k: balance[k] for k in DEBT_LINES
                        if isinstance(balance.get(k), (int, float))}
                debt_as_of = fallback.get("period_end")
        if not debt:
            # Katalog bosluğu ile "sirketin borcu yok"u ayirmak gerekiyor.
            # FIZZ hicbir donemde borc etiketlemiyor cunku borcu YOK; ORCL
            # ise etiketliyor ama baska bir kavramla. Ikisine ayni seyi demek
            # birini gizler.
            entry["net_debt"] = {
                "status": "not computed",
                "reason": ("no borrowings line appears in any filing at or "
                           "before the horizon. Either the company carries no "
                           "debt, or its filing uses an XBRL concept the "
                           "catalog does not map. This block cannot tell the "
                           "two apart."),
                "concepts_looked_for": list(DEBT_LINES) + ["borrowings_total"],
                "consequence": ("leverage and enterprise value are not stated "
                                "here; do not infer them from other fields"),
            }
            missing.append(entry["ticker"])
            continue
        cash = {k: balance[k] for k in CASH_LINES
                if isinstance(balance.get(k), (int, float))}
        # TOPLAM nitelikli kalemler bilesenlerle TOPLANMAZ, TERCIH EDILIR.
        # Olculdu: DebtCurrent cari borcun toplamidir ve uzun vadelinin cari
        # kismini icerir; bilesen sanip eklendiginde NVDA'da 1.000, PFE'de
        # 2.605 iki kez sayildi. Ayni sekilde ORCL'in
        # DebtLongtermAndShorttermCombinedAmount'i butun borcu kapsar.
        #
        # Tercih sirasi: butun borcun toplami > (cari toplam + uzun vadeli)
        #              > bilesenlerin toplami
        whole = balance.get("borrowings_total")
        current_total = balance.get("borrowings_current_total")
        long_term = balance.get("borrowings_long_term")
        if isinstance(whole, (int, float)):
            total_debt = whole
            basis = "reported as a single all-debt line"
            debt = {"borrowings_total": whole, **debt}
        elif isinstance(current_total, (int, float)):
            total_debt = current_total + (long_term if isinstance(long_term, (int, float)) else 0)
            basis = ("reported total current debt plus long-term debt"
                     if isinstance(long_term, (int, float))
                     else "reported total current debt only; no long-term line found")
            debt = {"borrowings_current_total": current_total,
                    **({"borrowings_long_term": long_term}
                       if isinstance(long_term, (int, float)) else {})}
        else:
            total_debt = sum(debt.values())
            basis = "sum of the reported components"
        # Bir tarafi eksik olan toplam, TAM borc degildir ve oyle sunulmamali.
        one_sided = (not isinstance(whole, (int, float))
                     and (isinstance(long_term, (int, float))
                          is not (isinstance(current_total, (int, float))
                                  or "borrowings_short_term" in debt
                                  or "borrowings_long_term_current_portion" in debt)))
        total_cash = sum(cash.values())
        leases = sum(balance[k] for k in ("lease_liabilities_short_term",
                                          "lease_liabilities_long_term")
                     if isinstance(balance.get(k), (int, float)))
        market_cap = entry.get("market_cap_usd_m")
        refreshed = (entry.get("price_refresh") or {}).get("market_cap_now_usd_m")
        block = {
            "status": "derived",
            "period": payload.get("period"),
            "as_of": payload.get("period_end"),
            "unit": "million USD",
            "debt_as_of": debt_as_of,
            "debt_is_from_an_older_period": debt_as_of != payload.get("period_end"),
            "total_debt": round(total_debt, 1),
            "total_debt_basis": basis,
            "may_be_only_part_of_the_debt": one_sided,
            "debt_components": {k: round(v, 1) for k, v in debt.items()},
            "cash_and_investments": round(total_cash, 1),
            "cash_components": {k: round(v, 1) for k, v in cash.items()},
            "net_debt": round(total_debt - total_cash, 1),
            "lease_liabilities": round(leases, 1) if leases else None,
            "lease_note": ("Leases are kept out of net debt because the valuation "
                           "engine's enterprise value is lease-exclusive. Add them "
                           "only if you say you are doing so."),
        }
        base = refreshed or market_cap
        if isinstance(base, (int, float)):
            block["enterprise_value"] = round(base + block["net_debt"], 1)
            block["enterprise_value_basis"] = ("market cap at the refreshed price"
                                               if refreshed else "market cap at cutoff")
        entry["net_debt"] = block
        ok += 1
    return ok, missing


def finalize_current_valuation(pack: dict) -> tuple[int, list[str]]:
    """Guncel fiyati pack'in kanonik piyasa ve degerleme gorunumu yap.

    Ozsermaye carpanlari ``refresh_prices`` tarafindan fiyat oranıyla tam
    olarak guncellenir. Girisim-degeri carpanlari ise ancak net borc
    eklendikten sonra tam hesaplanabilir: yeni EV / eski EV orani kullanilir.
    Eski kesit ``*_at_cutoff`` alanlarinda korunur.
    """
    updated, incomplete = 0, []
    for entry in pack.get("companies") or []:
        refresh = entry.get("price_refresh") or {}
        if refresh.get("status") != "available":
            incomplete.append(entry.get("ticker"))
            continue

        valuation_at_cutoff = dict(entry.get("valuation") or {})
        current = dict(refresh.get("valuation_at_price_now") or {})
        debt = entry.get("net_debt") or {}
        net_debt = debt.get("net_debt")
        cap_at_cutoff = entry.get("market_cap_usd_m")
        cap_now = refresh.get("market_cap_now_usd_m")
        can_refresh_ev = (
            isinstance(net_debt, (int, float))
            and isinstance(cap_at_cutoff, (int, float))
            and isinstance(cap_now, (int, float))
            and not debt.get("may_be_only_part_of_the_debt")
        )
        still_stale = []
        for label, value in valuation_at_cutoff.items():
            if label in current:
                continue
            if not isinstance(value, (int, float)):
                current[label] = None
                continue
            if "Enterprise Value" not in label:
                continue
            if not can_refresh_ev:
                still_stale.append(label)
                current[label] = None
                continue
            ev_at_cutoff = cap_at_cutoff + net_debt
            ev_now = cap_now + net_debt
            if ev_at_cutoff <= 0:
                still_stale.append(label)
                current[label] = None
                continue
            current[label] = round(value * ev_now / ev_at_cutoff, 4)

        entry["market_at_cutoff"] = {
            "price_usd": entry.get("closing_price_usd"),
            "market_cap_usd_m": cap_at_cutoff,
            "as_of": refresh.get("cutoff_price_as_of"),
        }
        entry["valuation_at_cutoff"] = valuation_at_cutoff
        entry["valuation_at_cutoff_as_of"] = refresh.get("cutoff_price_as_of")
        entry["closing_price_usd"] = refresh.get("price_now")
        entry["market_cap_usd_m"] = cap_now
        entry["market_data_as_of"] = refresh.get("price_as_of")
        entry["valuation"] = current
        entry["valuation_as_of"] = refresh.get("price_as_of")
        refresh["valuation_at_price_now"] = current
        refresh["not_rescaled"] = still_stale
        refresh["not_rescaled_reason"] = (
            "Only methods lacking a complete net-debt bridge remain at the cutoff."
            if still_stale else None
        )
        refresh["method"] = (
            "Price-based multiples use the exact price ratio; enterprise-value "
            "multiples use exact current EV = refreshed market cap + filing-based net debt."
        )
        history = entry.get("own_valuation_history") or {}
        history["history_through"] = (
            max(history.get("span") or [None]) if history.get("span") else None
        )
        history["current_valuation_as_of"] = entry["valuation_as_of"]
        for label, stats in (history.get("methods") or {}).items():
            current_display = current.get(label)
            if not isinstance(current_display, (int, float)):
                stats["current_value"] = None
                stats["current_sits"] = None
                continue
            current_comparable = (
                current_display / 100 if "Yield" in label else current_display
            )
            if current_comparable <= stats["p25"]:
                where = "at or below its own 25th percentile"
            elif current_comparable <= stats["median"]:
                where = "between its 25th percentile and median"
            elif current_comparable <= stats["p75"]:
                where = "between its median and 75th percentile"
            else:
                where = "at or above its own 75th percentile"
            stats["historical_last_value"] = stats.pop("last_value", None)
            stats["historical_last_sits"] = stats.pop("latest_sits", None)
            stats["current_value"] = round(current_comparable, 6)
            stats["current_display_value"] = current_display
            stats["current_as_of"] = entry["valuation_as_of"]
            stats["current_sits"] = where
        if history:
            history["note"] = (
                "Historical distribution ends at history_through. current_value is "
                "the live valuation placed against that unchanged historical distribution."
            )
            history["unit_warning"] = (
                "Historical yields use fractions; current_display_value keeps the "
                "reader-facing percentage while current_value is converted to the "
                "historical fraction scale before current_sits is calculated."
            )
        updated += 1
    return updated, [ticker for ticker in incomplete if ticker]


DISCRETE_METRICS = {
    "revenue_total": "revenue",
    "operating_profit": "operating_income",
    "net_profit_attributable_parent": "net_income",
    "eps_diluted_usc": "eps_diluted",
}


def attach_quarterly_series(pack: dict, source_run: Path,
                            horizon: str) -> tuple[int, int]:
    """AYRIK ceyreklik seri -- deep-dive'in "growth trajectory" istegi.

    Verimiz kumulatif (YTD): 2026-Q3 dokuz ayi kapsar. Oyle verilirse ceyrek
    sanilir ve buyume yanlis okunur. Farklandirilir:
        Q1 = Q1ytd,  Q2 = Q2ytd - Q1ytd,  Q3 = Q3ytd - Q2ytd,  Q4 = FY - Q3ytd
    Onceki YTD yoksa o ceyrek ATLANIR -- kumulatif rakami ceyrek diye
    yazmak sessiz bir hata olurdu.
    """
    # Canli kok tek kesim icin kuruldu ve sirket basina ~5 donem tasiyor;
    # ceyreklik seri icin yetmez. Donmus kosu kokleri yillarca birikmis
    # donemleri tasiyor. Ikisi birlestirilir, cakisan donemde CANLI kazanir.
    roots = [source_run] + [REPO / "backtests" / name
                            for name in ("ic-2024-v1", "ic-2021-v1")
                            if (REPO / "backtests" / name) != source_run]
    ok = skipped = 0
    for entry in pack["companies"]:
        periods: dict[str, dict] = {}
        for index, root in enumerate(reversed(roots)):
            folder = root / "data" / "financial" / entry["ticker"]
            if not folder.is_dir():
                continue
            for path in folder.glob("*.json"):
                if "derived" in path.name:
                    continue
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                published = payload.get("publication_date")
                if published and published > horizon:
                    continue
                periods[path.stem] = payload      # sonraki kok oncekini ezer
        if not periods:
            skipped += 1
            continue

        def flows(payload: dict) -> dict[str, float]:
            out = {}
            for item in payload.get("income_statement") or []:
                target = DISCRETE_METRICS.get(item.get("metric_id"))
                if target and isinstance(item.get("value"), (int, float)):
                    out[target] = float(item["value"])
            return out

        rows = []
        for year in sorted({k.split("-")[0] for k in periods}):
            ytd = {q: periods[f"{year}-Q{q}"] for q in (1, 2, 3)
                   if f"{year}-Q{q}" in periods}
            annual = periods.get(f"{year}-FY")
            for q in (1, 2, 3):
                if q not in ytd:
                    continue
                values = flows(ytd[q])
                if q == 1:
                    discrete, start = values, ytd[q]["period_start"]
                elif q - 1 in ytd:
                    prior = flows(ytd[q - 1])
                    discrete = {k: v - prior.get(k, 0.0) for k, v in values.items()
                                if k in prior}
                    start = ytd[q - 1]["period_end"]
                else:
                    continue
                rows.append({"period": f"FY{year}Q{q}", "start": start,
                             "end": ytd[q]["period_end"],
                             "derived": q > 1, **{k: round(v, 4)
                                                  for k, v in discrete.items()}})
            if annual and 3 in ytd:
                third = flows(ytd[3])
                values = flows(annual)
                discrete = {k: v - third.get(k, 0.0) for k, v in values.items()
                            if k in third}
                if discrete:
                    rows.append({"period": f"FY{year}Q4",
                                 "start": ytd[3]["period_end"],
                                 "end": annual["period_end"], "derived": True,
                                 **{k: round(v, 4) for k, v in discrete.items()}})
        if len(rows) < 4:
            skipped += 1
            continue
        rows.sort(key=lambda r: r["end"])
        entry["quarterly_series"] = {
            "status": "available",
            "method": ("discrete quarters differenced from cumulative filings; "
                       "Q4 is the annual less the nine-month figure"),
            "caveat": ("`derived: true` means the row is a difference, not a "
                       "figure the company filed on its own. Quarters whose "
                       "prior cumulative period is missing are omitted rather "
                       "than filled with a cumulative number."),
            "quarters": rows[-12:],
        }
        ok += 1
    return ok, skipped


def attach_prior_consensus(pack: dict, horizon: str) -> tuple[int, str | None]:
    """Rapor ONCESI konsensus -- surpriz ancak boyle hesaplanir.

    Bir ceyregin surprizi, o ceyrek aciklanmadan ONCEKI konsensuse gore
    olculur. Bugunun konsensusu artik BIR SONRAKI ceyrege aittir. Yani
    surpriz, ancak baskidan once alinmis bir snapshot varsa hesaplanabilir.
    Haftalik snapshot tam bunun icin birikiyor; ilk kayit 2026-08-07.
    """
    files = sorted(CONSENSUS_DIR.glob("snapshot-*.json"))
    hit, used = 0, None
    for entry in pack["companies"]:
        release = (entry.get("latest_earnings_release") or {}).get("filing_date")
        if not release:
            continue
        # Baskidan onceki EN YAKIN snapshot.
        before = [p for p in files if p.stem.replace("snapshot-", "") < release]
        if not before:
            entry["pre_print_consensus"] = {
                "status": "unavailable",
                "reason": (f"no consensus snapshot predates the {release} release; "
                           f"the earliest we hold is "
                           f"{files[0].stem.replace('snapshot-', '') if files else 'none'}"),
                "consequence": "surprise against consensus cannot be computed for "
                               "this print, and must not be estimated",
            }
            continue
        path = before[-1]
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = payload["companies"].get(entry["ticker"])
        if not record:
            continue
        entry["pre_print_consensus"] = {
            "status": "available",
            "as_of": payload["snapshot_date"],
            "release_date": release,
            "earnings_estimate": (record.get("earnings_estimate") or {}).get("0q"),
            "revenue_estimate": (record.get("revenue_estimate") or {}).get("0q"),
        }
        hit += 1
        used = payload["snapshot_date"]
    return hit, used


def flag_superseded(pack: dict, source_run: Path) -> tuple[int, list[str]]:
    """Piyasa bizden YENI rakam biliyor mu?

    Finansallarimiz 10-Q/10-K'nin XBRL'inden gelir. Sirketler kazanci once
    8-K ile aciklar, 10-Q gunler ya da haftalar sonra dosyalanir. O aralikta
    piyasa yeni ceyregi bilir, bizim paket hâlâ oncekini tasir.

    Olculdu (2026-08-07 kesimi): KDP ve PH 6 Agustos'ta kazanc acikladi ama
    en son periyodik dosyalamalari sirasiyla 105 ve 97 gun oncesine ait.
    Kesim tarihini kovalamak bunu cozmez -- eksik olan sey XBRL'in kendisi.

    Bu yuzden karsilastirma kesimle degil, FINANSALIMIZIN GELDIGI periyodik
    dosyalama ile 8-K kazanc bulteni arasindadir.
    """
    ledger_path = source_run / "ledger" / "sec-discovery.json"
    if not ledger_path.is_file():
        return 0, []
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    text_root = REPO / "guidance" / "_text"
    hit, names = 0, []
    for entry in pack["companies"]:
        ticker = entry["ticker"]
        submission = ledger.get("submissions", {}).get(ticker)
        if not submission:
            continue
        recent = (json.loads((source_run / submission["relative_path"])
                             .read_text(encoding="utf-8"))
                  .get("filings", {}).get("recent", {}))
        forms, dates = recent.get("form", []), recent.get("filingDate", [])
        items = recent.get("items", [""] * len(forms))
        periodic = [d for f, d in zip(forms, dates) if f in ("10-K", "10-Q")]
        # Sadece Item 2.02 (Results of Operations and Financial Condition)
        # tasiyan 8-K'ler kazanc bulteni sayilir. Baska bir 8-K (yonetici
        # degisikligi, M&A, borc ihraci vb.) "daha yeni ceyrek acildi"
        # anlamina gelmez -- olculdu: CRM'in 2026-08-05 8-K'si Item 5.02
        # (yonetici atamasi/ayrilisi), kazanc degildi ama filtre olmadan
        # yanlislikla "announced_but_not_filed" olarak isaretlendi.
        eight_k = [d for f, d, it in zip(forms, dates, items)
                   if f == "8-K" and "2.02" in (it or "").split(",")]
        if not periodic or not eight_k:
            continue
        last_periodic, last_8k = max(periodic), max(eight_k)
        if last_8k <= last_periodic:
            continue
        gap = (date.fromisoformat(last_8k) - date.fromisoformat(last_periodic)).days
        # Kisa gecikme normal: kazanc 8-K'si 10-Q ile ayni hafta gelir. Uzun
        # gecikme, aciklanmis ama henuz dosyalanmamis bir ceyrek demektir.
        if gap < 45:
            continue
        held_text = None
        folder = text_root / ticker
        if folder.is_dir():
            for path in sorted(folder.glob("*.txt")):
                found = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
                if found and found.group(1) >= last_8k:
                    held_text = path.relative_to(REPO).as_posix()
        entry["announced_but_not_filed"] = {
            "status": "the market has a newer quarter than this pack",
            "our_financials_from_filing": last_periodic,
            "latest_8k": last_8k,
            "gap_days": gap,
            "pack_period": entry.get("latest_reported_period"),
            "release_text_we_hold": held_text,
            "why": ("Our statements come from 10-Q/10-K XBRL. This company "
                    "announced results in an 8-K that has no matching periodic "
                    "filing yet, so the newer quarter is not in the pack and no "
                    "later cutoff would bring it in."),
            "what_to_do": ("Treat the pack's figures as the last filed quarter, "
                           "not the last reported one. Source the release for "
                           "the newer numbers and label them as such; do not "
                           "place them inside ratios built from the older "
                           "statements."),
        }
        hit += 1
        names.append(ticker)
    return hit, names


def flag_price_drift(pack: dict, consensus_as_of: str) -> tuple[int, float]:
    """Iki fiyat var ve tarihleri farkli -- carpanlar hangisinden hesaplandi.

    Fark sessiz kalirsa eklenti ikisini karistirir ve ayni sirket icin iki
    farkli F/K uretir (ORCL'de %13 idi).
    """
    drifted, worst = 0, 0.0
    for entry in pack["companies"]:
        anchor = entry.get("closing_price_usd")
        live = (entry.get("consensus_estimates", {}).get("price_targets") or {}).get("current")
        if not anchor or not live:
            continue
        gap = (live / anchor - 1) * 100
        entry["price_reconciliation"] = {
            "multiples_computed_from": anchor,
            "multiples_price_as_of": pack["execution_date"],
            "consensus_block_price": round(live, 2),
            "consensus_price_as_of": consensus_as_of,
            "gap_pct": round(gap, 2),
            "note": ("Every multiple in `valuation` uses multiples_computed_from. "
                     "If you quote a multiple, quote that price and that date. "
                     "Do not recompute multiples against the consensus-block price "
                     "yourself -- see `price_refresh.valuation_at_price_now` for the "
                     "already-rescaled figures."),
        }
        if abs(gap) >= 5:
            drifted += 1
        worst = max(worst, abs(gap))
    return drifted, worst


PEER_FUNDAMENTAL_METRICS = (
    "revenue_growth",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "operating_cash_flow_margin",
    "free_cash_flow_margin",
    "ocf_to_net_profit",
)


def _growth_pct(record: dict, period: str) -> float | None:
    value = (record.get(period) or {}).get("growth")
    return round(value * 100, 2) if isinstance(value, (int, float)) else None


def _peer_consensus_summary(entry: dict) -> dict:
    consensus = entry.get("consensus_estimates") or {}
    if consensus.get("status") != "available":
        return {"status": "unavailable"}
    revenue = consensus.get("revenue_estimate") or {}
    earnings = consensus.get("earnings_estimate") or {}
    revisions = consensus.get("eps_revisions") or {}
    current_year_revisions = revisions.get("0y") or {}
    up = current_year_revisions.get("upLast30days")
    down = current_year_revisions.get("downLast30days")
    return {
        "status": "available",
        "as_of": consensus.get("as_of"),
        "revenue_growth_current_year_pct": _growth_pct(revenue, "0y"),
        "revenue_growth_next_year_pct": _growth_pct(revenue, "+1y"),
        "eps_growth_current_year_pct": _growth_pct(earnings, "0y"),
        "eps_growth_next_year_pct": _growth_pct(earnings, "+1y"),
        "current_year_eps_analyst_count": (earnings.get("0y") or {}).get("numberOfAnalysts"),
        "current_year_eps_revision_net_30d": (
            up - down if isinstance(up, (int, float)) and isinstance(down, (int, float))
            else None
        ),
    }


def _peer_snapshot(entry: dict) -> dict:
    fundamentals = entry.get("fundamentals") or {}
    return {
        "ticker": entry["ticker"],
        "as_of": {
            "financial_period_end": entry.get("latest_period_end"),
            "financial_publication_date": entry.get("financial_publication_date"),
            "market": entry.get("market_data_as_of"),
            "valuation": entry.get("valuation_as_of"),
            "consensus": (entry.get("consensus_estimates") or {}).get("as_of"),
        },
        "closing_price_usd": entry.get("closing_price_usd"),
        "market_cap_usd_m": entry.get("market_cap_usd_m"),
        "valuation": entry.get("valuation") or {},
        "fundamentals": {
            metric: fundamentals.get(metric)
            for metric in PEER_FUNDAMENTAL_METRICS
            if isinstance(fundamentals.get(metric), (int, float))
        },
        "fundamentals_comparability": entry.get("fundamentals_comparability"),
        "roic": entry.get("roic") or {"status": "unavailable"},
        "consensus": _peer_consensus_summary(entry),
    }


def _peer_medians(members: list[dict]) -> dict:
    sections: dict[str, dict[str, list[float]]] = {
        "valuation": {}, "fundamentals": {}, "consensus": {}, "quality": {}
    }
    for member in members:
        for section in ("valuation", "fundamentals", "consensus"):
            for key, value in (member.get(section) or {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    sections[section].setdefault(key, []).append(value)
        roic = (member.get("roic") or {}).get("value_pct")
        if isinstance(roic, (int, float)):
            sections["quality"].setdefault("roic_pct", []).append(roic)
    return {
        section: {
            key: round(statistics.median(values), 2)
            for key, values in rows.items() if values
        }
        for section, rows in sections.items()
    }


def _company_peer_framework(pack: dict, ticker: str, path: Path) -> dict:
    framework = json.loads(path.read_text(encoding="utf-8"))
    if framework.get("subject_ticker") != ticker:
        return {"status": "unavailable", "reason": "peer framework subject mismatch"}
    index = {entry["ticker"]: entry for entry in pack["companies"]}
    groups, all_member_tickers, missing = [], set(), []
    for authored in framework.get("groups") or []:
        members = []
        absent = []
        for member_ticker in authored.get("members") or []:
            entry = index.get(member_ticker)
            if entry is None:
                absent.append(member_ticker)
                missing.append(member_ticker)
                continue
            snapshot = _peer_snapshot(entry)
            members.append(snapshot)
            all_member_tickers.add(member_ticker)
        groups.append({
            "group_id": authored.get("group_id"),
            "label": authored.get("label"),
            "purpose": authored.get("purpose"),
            "member_count": len(members),
            "missing_members": absent,
            "medians": _peer_medians(members),
            "members": members,
        })
    return {
        "status": "partial" if missing else "available",
        "framework_type": "company_specific_multi_lens",
        "framework_id": framework.get("artifact_id"),
        "framework_version": framework.get("framework_version"),
        "framework_source": str(path.relative_to(REPO)).replace("\\", "/"),
        "effective_from": framework.get("effective_from"),
        "methodology": framework.get("methodology"),
        "single_combined_peer_median": False,
        "peer_count": len(all_member_tickers),
        "missing_numeric_peers": sorted(set(missing)),
        "groups": groups,
        "operational_references": framework.get("operational_references") or [],
        "median_caveat": (
            "Each median belongs only to its stated economic lens. Do not combine "
            "the groups into one median and do not treat convergence as evidence "
            "without an independent operating or fundamental justification."
        ),
    }


def peer_block(pack: dict, ticker: str, sectors: dict[str, str]) -> dict:
    """Genel altyapi; varsa hedefe ozel, yoksa sektor tabanli peer blogu."""
    framework_path = COMPANY_PEERS / f"{ticker}.json"
    if framework_path.is_file():
        return _company_peer_framework(pack, ticker, framework_path)

    group = sectors.get(ticker)
    if not group:
        return {"status": "unavailable", "reason": "no peer group mapped"}
    members = [
        _peer_snapshot(entry)
        for entry in pack["companies"]
        if entry["ticker"] != ticker and sectors.get(entry["ticker"]) == group
    ]
    return {
        "status": "available",
        "framework_type": "sector_fallback",
        "peer_group": group,
        "peer_group_source": "config/valuation/comparison/peer-universes",
        "peer_count": len(members),
        "medians": _peer_medians(members),
        "median_caveat": (
            "This is a broad sector fallback, not a claim that every member is "
            "an operating peer. Convergence to its median is not evidence on its own."
        ),
        "members": members,
    }


def mandate_block() -> str:
    """Mandat VERI degil KARAR. Yazilmazsa skill kendi varsayimini uretir."""
    path = REPO / "config" / "mandate.json"
    if not path.is_file():
        return ""
    m = json.loads(path.read_text(encoding="utf-8"))
    h = m["horizon"]
    lines = [
        "## Mandate -- do not infer this, it is given",
        "",
        f"- **{m['mandate'].replace('_', ' ')}**, {m['instruments']}.",
        f"- Universe: {m['geography']}. {m['sectors']}.",
        f"- Review {h['review_cadence']}, rebalance {h['rebalance_cadence']}. "
        f"{h['note']}",
    ]
    if m.get("position_count") is None:
        lines.append(f"- Position count is not fixed. {m['position_count_note']}")
    else:
        lines.append(f"- Target {m['position_count']} positions.")
    if not m["liquidity_floor"]["applies"]:
        lines.append(f"- No liquidity floor. {m['liquidity_floor']['reason']}")
    if m.get("benchmark") is None:
        lines.append(f"- {m['benchmark_note']}")
    lines += ["", f"**Known tension, stated so you do not have to discover it:** "
                  f"{m['known_tension']}", ""]
    return "\n".join(lines)


HEADER = """# Deterministic data pack -- read this before anything else

**This pack was built for `{step}`.** `pack.json` says the same in
`intended_step`. If the two disagree, the pack is authoritative and the pack and
these instructions came from different runs -- stop and say so rather than
picking one.

Attached: `pack.json`. {scope} It was prepared by my own pipeline from SEC XBRL
filings, a frozen price ledger and a dated analyst consensus snapshot.

It satisfies the `market_data_estimates` and `company_filings_ir` source
categories. Treat it as the user-named source and prefer it over web retrieval
for those categories.

## Deliverable surface

Markdown only -- no HTML report, dashboard, or screenshot pass.

## Source-of-truth rule

The numeric fields in `pack.json` are the **primary numeric source of truth**.

- Do **not** re-derive revenue, margins, growth, cash flow, multiples, market
  cap, consensus estimates, revisions or price targets from
  the web. They are already here, computed the same way for every company, so
  cross-company comparison is valid.
- Do **not** fill a missing value by estimating it. `unavailable` means
  unavailable and stays that way in your output.
- If something you find on the web contradicts a number in the pack, **say so
  explicitly** and name both values. Do not silently replace mine with theirs.

## Public sources, if you have them

If you have web search, it is worth using for what the pack does not contain:
news, events, management commentary, earnings call content, what the market is
currently debating, and sector or macro context. That layer is the one I cannot
produce.

## As-of dates -- these differ and it matters

| layer | as of |
|---|---|
| this pack was built on | {built_on} |
| financial statement period end | {financial_period_end} |
| financial filing publication | {financial_publication_date} |
| data eligibility cutoff | {cutoff} |
| latest market price and canonical valuation | {price_as_of} |
| trailing returns / volatility / ADV | {market_statistics_as_of} |
| analyst consensus | {consensus_as_of} |

Quote the correct as-of when you cite a number. Anything after these dates
belongs to the web layer, not to the pack.

`valuation` is the canonical current valuation priced as of {price_as_of}.
`valuation_at_cutoff` preserves the original {execution} valuation snapshot.
{drift_line} Price-based multiples are updated by the exact price ratio.
Enterprise-value multiples are recomputed from refreshed market cap plus
filing-based net debt; any method that cannot be refreshed remains explicitly
listed in `price_refresh.not_rescaled` rather than silently mixed with current data.

## Names that reported after the cutoff -- read this before ranking

{stale_line}

Affected companies carry `announced_but_not_filed` (filing dates, data age) --
some are a full quarter behind. This does not rescale away: source the newer
print and label it web-sourced, or say plainly the pack predates it. Do not
fold a newer headline number into a ratio built from older statements, and do
not rank a stale company against a current one without saying so.

## Corporate events -- three blocks, and what they are

Facts from the SEC filing index; what they mean for a company is yours to judge.

`special_situations` -- a completed acquisition, disposition, spin,
restatement, or amended 10-Q/10-K in the last two years (dates, 8-K item
numbers).

`fundamentals_comparability` -- present when such an event falls inside the
twelve months a company's growth rates span. Names the affected `*_growth`
fields: they compare periods covering different businesses, neither restated.
Single-period ratios are unaffected.

`transaction_filing_history` -- a 425, S-4 or merger proxy was found in the
filing window. Carries form mix, count, dates and a form-based role indicator
(merger proxy = soliciting its own shareholders; S-4 = registering securities;
425 alone = role unknown). **This does not establish that a transaction is
currently pending, completed or terminated. Deal terms, consideration,
counterparty, timetable, regulatory status and outcome are not in the pack.**

## What is deliberately NOT in the pack

Earnings call transcripts, expert-network work, options and implied-move data,
short interest and positioning, private-company transactions, and the terms of
any M&A deal. I have no source for these. Fill them from public sources if you
can and mark them as such; where you cannot, state the limitation and carry on.

{mandate}
## Task

{task}
"""

TASKS = {
    "idea": """Use idea-generation across all {n} companies in one screen.

End with a single table covering all {n} tickers, one row each:

| Ticker | Bucket | Setup | Variant wedge | First rejection | Next workflow |

Two companies reaching the same conclusion must still differ in their
company-specific evidence and first rejection. Repeated boilerplate rationale
is a failed run.""",

    "tearsheet": """Use company-tearsheet for {ticker}.""",

    "preview": """Use earnings-preview for {ticker}.

I have no options or implied-move data and no positioning or short-interest
data. Do not construct an implied-move bar from an expiry that does not isolate
the event; say the input is missing instead.""",

    "deepdive": """Use earnings-deep-dive for {ticker}.

`quarterly_series` holds discrete quarters differenced from the cumulative
filings, so a growth trajectory can be read without mistaking a nine-month
figure for a quarter. Rows marked `derived` are differences, not filed numbers.

`pre_print_consensus` holds the consensus as it stood before the release, where
a snapshot predates it. Where it does not, surprise against consensus cannot be
computed for that print and must not be estimated -- say so instead.

I have no earnings-call transcript. Mark the Q&A and debate-map sections
`transcript not provided` and name the missing artifact rather than rendering an
empty table.""",

    "comps": """Use comps-valuation for {ticker}.

`sector_peers` uses a company-specific multi-lens framework where one is
authored; otherwise it clearly identifies a broad sector fallback. Each peer
contains valuation, selected fundamentals, ROIC, consensus growth/revisions
and layer-specific as-of dates.

For a multi-lens framework use only each group's own median. Never combine the
groups into one median. Read `purpose`, `operational_references` and
`median_caveat` before drawing a conclusion.""",

    "pitch": """Use long-short-pitch for {ticker}.

Build on the earlier result artifacts supplied with this pack. Do not assume
that this chat contains any prior work. If a required prior artifact was not
supplied, name the missing artifact instead of reconstructing it from memory.
The pack is here for the current numbers; no new raw data is needed.

Every threshold must carry a number and a date. A threshold without one is not
a threshold.""",

    "scenario": """Use scenario-sensitivity-generator for {ticker}.

This pack does not contain sector_peers -- this workflow works from the
company's own numbers (EBITDA-based EV multiple, net debt with components,
FCF, forward EPS consensus range), not a peer comparison. Focus on
`valuation_sensitivity` and `eps_revision_sensitivity`; only use
`equity_liquidity_downside` or `kpi_driver_sensitivity` if you explicitly flag
that revolver/covenant data and segment-level KPIs are not in this pack rather
than estimating them.

State the driver that breaks first, whether upside depends on multiple
expansion or estimate revisions, and the explicit PM action rule (add / press
/ hold / trim / exit / hedge / wait for proof) tied to a numeric threshold and
date. Do not present a probability-weighted value without labeling its source
posture (model-validated, source-derived, or illustrative).""",

    "initiation": """Use initiating-coverage for {ticker}.

This pack gives you the deterministic source-of-truth layer only: current
price and valuation, consensus, net debt, ROIC, special situations and
earnings-quality flags. It deliberately does NOT contain segment- or
product-level revenue, multi-year forecast drivers, deal terms, or clinical/
regulatory detail -- build that yourself from web search per your own
Non-Negotiables (label facts, company claims, model-derived values and
assumptions distinctly; state what remains missing rather than fabricating
it).

Do not treat this pack's single-period multiples as sufficient valuation
support on their own if the Capital-Intensive And Financed Growth Gate
applies to {ticker} -- build the pro forma capitalization / EV bridge and
after-financing return evidence the gate requires before a positive
underwriting conclusion or target price.""",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="tek sirket (ticker)")
    # Iki asamali eleme icin. Once her sektor ayri kosulur (--sector), sonra
    # A kovasindan cikanlar tek havuzda yeniden kosulur (--tickers).
    #
    # Bolmenin bir bedeli var ve bilerek odenir: her kosu kendi havuzuna gore
    # A uretir, yani sektor kovalari BIRBIRIYLE KIYASLANABILIR DEGILDIR.
    # 2026-08-10'da 60'lik tek kosuda 24 tuketim sirketinden yalniz 1'i A
    # cikti; ayni 24'u tek basina kosarsan daha fazla cikar, sirketler
    # degismeden. Ikinci asama tam bunu duzeltir: hepsi tek havuzda yeniden
    # karsilasir.
    ap.add_argument("--sector", default=None,
                    help="tek sektor ailesi (consumer_staples, health_care, "
                         "industrials, technology)")
    ap.add_argument("--tickers", default=None,
                    help="virgulle ayrilmis liste; onceki elemeden gecenler")
    ap.add_argument("--for", dest="step", default=None,
                    choices=sorted(TASKS), help="hangi adim icin talimat")
    ap.add_argument(
        "--month", default=None,
        help=("yalniz en son canli kesit kabul edilir; eski ay verilirse "
              "live pack uretimi durur"),
    )
    ap.add_argument("--out", default=str(OUT_ROOT))
    # Varsayilan: her sey tazelenir. Paket, uretildigi gunun verisini tasir.
    ap.add_argument("--no-refresh", action="store_true",
                    help="tazeleme yapma, elde ne varsa onu kullan")
    ap.add_argument("--force-refresh", action="store_true",
                    help="bilanco degismemis olsa da butun sirketleri yeniden isle")
    args = ap.parse_args()

    ticker = args.only.strip().upper() if args.only else None
    step = args.step or ("tearsheet" if ticker else "idea")
    if step != "idea" and not ticker:
        raise SystemExit(f"--for {step} tek sirket ister; --only TICKER ekleyin")
    if step == "idea" and ticker:
        raise SystemExit("--for idea butun evreni ister; --only kaldirin")
    if args.sector and args.tickers:
        raise SystemExit("--sector ve --tickers birlikte verilmez")
    if (args.sector or args.tickers) and step != "idea":
        raise SystemExit("--sector ve --tickers yalniz --for idea ile calisir")
    wanted = ([t.strip().upper() for t in args.tickers.split(",") if t.strip()]
              if args.tickers else None)

    source_run, month = SOURCE_RUN, args.month
    if not args.no_refresh:
        # Tek komut = guncel paket. Fiyat ve SEC her kosuda tazelenir;
        # finansal yalniz yeni bilanco gelen sirketlerde yeniden islenir.
        print("=== tazeleme ===", flush=True)
        for helper in ("us_consensus_snapshot.py", "us_events_snapshot.py"):
            started = time.time()
            proc = subprocess.run(
                [sys.executable, str(REPO / "scripts" / helper),
                 "--universe", str(LIVE_UNIVERSE)],
                capture_output=True, text=True)
            tail = (proc.stdout or "").strip().splitlines()
            print(f"{helper:28} ({time.time()-started:.0f} sn) "
                  f"{tail[-1] if tail else 'cikti yok'}", flush=True)
        outcome = live_refresh.refresh(repo_root=REPO, force=args.force_refresh)
        source_run, month = outcome["run_root"], outcome["month"]
        if outcome["skipped"]:
            print(f"  ATLANAN: {', '.join(outcome['skipped'])}", flush=True)
        print("=== tazeleme bitti ===\n", flush=True)
    month = resolve_live_month(source_run, month)
    print(f"kaynak: {source_run.name}/{month}   adim: {step}"
          + (f"   sirket: {ticker}" if ticker else ""))

    # Rapor AYRISTIRILMIYOR: paket dogrudan artifact'lerden kuruluyor.
    pack = build_pack_from_artifacts(run_root=source_run, month=month,
                                     guidance_root=GUIDANCE)
    pack["mode"] = "live"
    pack["known_limitations"] = [
        item for item in pack.get("known_limitations", [])
        if item != "all knowledge and claims must be bounded by cutoff_instant"
    ]
    pack["known_limitations"].append(
        "each live layer carries its own as-of date; do not apply the financial "
        "artifact cutoff to refreshed market, consensus or event data"
    )
    # SEC artefaktlari icin son canli kesim. Bu script tarihsel replay yapmaz;
    # asagidaki butun canli katmanlar kosu anindaki en yeni veriye cekilir.
    horizon = pack["cutoff_instant"][:10]
    # Paketin URETILDIGI gun; kesim (son seans) ondan farklidir.
    built_on = date.today().isoformat()
    set_live_decision_date(pack, built_on)
    companies, consensus_as_of, consensus_path = latest_consensus()
    hit, missing = attach_consensus(pack, companies, consensus_as_of)
    events_n, events_as_of = attach_events(pack)
    history_n, history_last = attach_valuation_history(pack, horizon)
    pack["_financial_root"] = str(source_run / "data" / "financial")
    special_n, special_names = flag_special_situations(pack, source_run)
    roic_n, roic_skipped = attach_roic(pack, horizon)
    eq_n, eq_names = flag_earnings_quality(pack, horizon)
    pack.pop("_financial_root", None)
    series_n, series_skipped = attach_quarterly_series(pack, source_run, horizon)
    prior_n, prior_as_of = attach_prior_consensus(pack, horizon)
    stale_n, stale_names = flag_superseded(pack, source_run)
    priced_n, price_as_of = refresh_prices(pack)
    debt_n, debt_missing = attach_net_debt(pack, source_run, horizon)
    drifted, worst = flag_price_drift(pack, consensus_as_of)
    current_valuation_n, current_valuation_missing = finalize_current_valuation(pack)
    universe_count = pack["universe_count"]

    # Alt kume DARALTMASI butun bloklar eklendikten SONRA yapilir: emsal
    # gozlemleri, carpan gecmisi ve ozel durum defteri tam evreni gorerek
    # hesaplanir, sonra liste kirpilir.
    subset_label = None
    if args.sector or wanted:
        family = sector_of()
        if args.sector:
            # Tire mi alt cizgi mi: emsal evreni DOSYA ADI "health-care",
            # icindeki sector_family alani "health_care". Ikisi de kabul
            # edilir; kullanicinin hangisinin nerede gectigini bilmesi
            # gerekmez.
            def norm(s: str) -> str:
                return s.replace("-", "_").lower()
            keep_set = {t for t, f in family.items() if norm(f) == norm(args.sector)}
            if not keep_set:
                raise SystemExit(
                    f"'{args.sector}' bilinmiyor. Mevcut: "
                    f"{', '.join(sorted(set(family.values())))}")
            subset_label = norm(args.sector)
            subset_kind = "sector"
        else:
            known = {c["ticker"] for c in pack["companies"]}
            unknown = [t for t in wanted if t not in known]
            if unknown:
                raise SystemExit(f"evrende olmayan ticker: {', '.join(unknown)}")
            keep_set = set(wanted)
            subset_label = "shortlist"
            subset_kind = "shortlist"
        pack["companies"] = [c for c in pack["companies"] if c["ticker"] in keep_set]
        pack["universe_count"] = len(pack["companies"])
        universe_count = pack["universe_count"]
        align_subset_coverage(pack, keep_set)

        # Ozet sayilar daraltmadan ONCE hesaplanmisti; oldugu gibi birakmak
        # "net borc 58/12" gibi bir satir ve teknoloji paketinde FIZZ/MNST
        # gibi uye olmayan eksikler yazdiriyordu. Daraltilmis listeden
        # yeniden sayilir.
        here = pack["companies"]
        def _have(key, inner="status", good=("available", "derived")):
            return sum(1 for c in here
                       if isinstance(c.get(key), dict)
                       and c[key].get(inner) in good)
        roic_n = _have("roic")
        roic_skipped = universe_count - roic_n
        debt_n = sum(1 for c in here if (c.get("net_debt") or {}).get("net_debt") is not None)
        debt_missing = [c["ticker"] for c in here
                        if (c.get("net_debt") or {}).get("net_debt") is None]
        special_names = [c["ticker"] for c in here if c.get("special_situations")
                         and c["special_situations"].get("status", "").startswith("structural")]
        special_n = len(special_names)
        events_n = _have("next_events")
        history_n = _have("own_valuation_history")
        current_valuation_n = sum(
            1 for c in here if c.get("valuation_as_of") is not None
        )
        current_valuation_missing = [
            c["ticker"] for c in here if c.get("valuation_as_of") is None
        ]
        priced_n = sum(
            1 for c in here
            if (c.get("price_refresh") or {}).get("status") == "available"
        )
        stale_names = [c["ticker"] for c in here if c.get("announced_but_not_filed")]
        stale_n = len(stale_names)
        eq_names = [c["ticker"] for c in here if c.get("earnings_quality_flags")]
        eq_n = len(eq_names)
        pack["subset"] = {
            "kind": subset_kind,
            "name": subset_label,
            "members": sorted(keep_set),
            "drawn_from": f"{len(known) if wanted else 60} company universe",
            "note": (
                "This pack is one sector family out of four. Buckets assigned "
                "here rank companies against this pool, not against the whole "
                "universe."
                if subset_kind == "sector" else
                "These companies were carried forward from a prior sector-level "
                "screen; the names that did not survive it are not here. They "
                "now sit in one pool for the first time."),
        }

    blocks = STEP_BLOCKS[step]
    dropped = [name for name, keep in blocks.items() if not keep]

    if ticker:
        target = [c for c in pack["companies"] if c["ticker"] == ticker]
        if not target:
            raise SystemExit(f"{ticker} evrende yok ({universe_count} sirket)")
        entry = target[0]
        # Emsal blogu, liste tek sirkete indirilmeden ONCE hesaplanir --
        # sonra hesaplanirsa gezinecek emsal kalmaz.
        peers = peer_block(pack, ticker, sector_of()) if blocks["sector_peers"] else None
        pack["companies"] = target
        pack["universe_count"] = 1
        universe_count = 1
        if peers is not None:
            pack["sector_peers"] = peers
        # Ozet sayilar (roic_n, debt_n, special_n, eq_n, events_n, history_n,
        # current_valuation_n, priced_n...) tek sirkete daraltmadan ONCE,
        # butun evren uzerinde hesaplanmisti -- align_subset_coverage yalniz
        # --tickers/--sector yolunda calisiyor, --only tek sirket yolunda
        # calismiyordu. Ayni "82/1" turu yaniltici satiri onlemek icin tek
        # sirketten yeniden sayilir (align_subset_coverage'daki _have ile
        # ayni mantik).
        def _have_one(key, inner="status", good=("available", "derived")):
            value = entry.get(key)
            return 1 if isinstance(value, dict) and value.get(inner) in good else 0
        roic_n = _have_one("roic")
        roic_skipped = 1 - roic_n
        debt_n = 1 if (entry.get("net_debt") or {}).get("net_debt") is not None else 0
        debt_missing = [] if debt_n else [ticker]
        special_n = 1 if (entry.get("special_situations") or {}).get("status", "").startswith("structural") else 0
        special_names = [ticker] if special_n else []
        events_n = _have_one("next_events")
        history_n = _have_one("own_valuation_history")
        current_valuation_n = 1 if entry.get("valuation_as_of") is not None else 0
        current_valuation_missing = [] if current_valuation_n else [ticker]
        priced_n = 1 if (entry.get("price_refresh") or {}).get("status") == "available" else 0
        eq_n = 1 if entry.get("earnings_quality_flags") else 0
        eq_names = [ticker] if eq_n else []
        if step == "tearsheet":
            attach_tearsheet_context(pack, source_run)
        gap = (entry.get("price_reconciliation") or {}).get("gap_pct")
        drift_line = (f"For {ticker} the two prices differ by {gap:+.1f}%."
                      if gap is not None else
                      "No second price is available for this name.")
        scope = (f"It contains one company, {ticker}, plus its sector peer group."
                 if peers is not None else
                 f"It contains one company, {ticker}.")
        hit_n = 1 if entry["consensus_estimates"]["status"] == "available" else 0
        guidance_n = int(entry["latest_earnings_release"]
                         .get("guidance", {}).get("status") == "available")
        count = 1
    else:
        drift_line = (f"{drifted} of {universe_count} names differ by 5% or more, "
                      f"the widest by {worst:.0f}%.")
        if subset_label == "shortlist":
            scope = (f"It contains {universe_count} US large-cap companies "
                     f"carried forward from a sector-level screen. The names "
                     f"that screen did not carry forward are not in this pack, "
                     f"so this is the first time these companies are being "
                     f"compared with each other.")
        elif subset_label:
            scope = (f"It contains {universe_count} US large-cap companies, "
                     f"the whole of the {subset_label} family and nothing else. "
                     f"Three other sector families are being run separately, so "
                     f"a bucket assigned here ranks a company against this pool "
                     f"rather than against the full universe.")
        else:
            scope = f"It contains {universe_count} US large-cap companies."
    if ticker:
        stale_line = (
            f"**{ticker} filed after the cutoff** "
            f"({', '.join(entry['announced_but_not_filed']['filing_dates_after_cutoff'])})."
            if "announced_but_not_filed" in entry
            else f"{ticker} has not filed since the cutoff, so its financials here "
                 f"are the latest ones.")
    else:
        stale_line = (
            f"**{stale_n} of {universe_count} names filed after {pack['cutoff_instant'][:10]}:** "
            f"{', '.join(stale_names)}." if stale_n
            else "No company filed after the cutoff.")
        # `hit` daraltmadan once sayildi; alt kumede kendi listesinden sayilir.
        hit_n = sum(1 for c in pack["companies"]
                    if c["consensus_estimates"].get("status") == "available")
        guidance_n = sum(
            1 for c in pack["companies"]
            if c["latest_earnings_release"].get("guidance", {}).get("status")
            == "available")
        count = universe_count
        missing = [c["ticker"] for c in pack["companies"]
                   if c["consensus_estimates"].get("status") != "available"]

    if ticker:
        financial_period_end = entry.get("latest_period_end") or "unavailable"
        financial_publication_date = (
            entry.get("financial_publication_date") or "unavailable"
        )
        market_statistics_as_of = (
            entry.get("market_statistics_as_of") or "unavailable"
        )
    else:
        financial_period_end = "varies by company; see latest_period_end"
        financial_publication_date = "varies by company; see financial_publication_date"
        market_statistics_as_of = "varies by company; see market_statistics_as_of"
    current_market_as_of = price_as_of or pack["execution_date"]

    pack["pack_purpose"] = (
        "Deterministic numeric input for the ChatGPT Public Equity Investing "
        "plugin. Numbers here replace the plugin's paid data connectors; the "
        "plugin should use the web only for narrative and for fields marked "
        "unavailable."
    )
    pack["consensus_as_of"] = consensus_as_of
    pack["intended_step"] = step
    pack["built_on"] = built_on
    pack["last_market_session"] = current_market_as_of
    pack["market_data_as_of"] = current_market_as_of
    pack["financial_data_cutoff"] = pack["cutoff_instant"]

    # Adima ait olmayan bloklari SIL. Fazladan veri masum degil: okunmayi
    # bekleyen her blok dikkati boler, ve skill zaten yalniz kendi kaynak
    # kategorilerini cozmesini soyluyor.
    # Bir blok birden fazla alan yaziyorsa hepsi birlikte gider; yoksa blok
    # kapatildiginda yetim bir uyari alani geride kalir.
    COMPANIONS = {"special_situations": ("transaction_filing_history",
                                         "fundamentals_comparability")}
    for name, keep in blocks.items():
        if keep or name == "sector_peers":
            continue
        for company in pack["companies"]:
            company.pop(name, None)
            for extra in COMPANIONS.get(name, ()):
                company.pop(extra, None)
    if dropped:
        pack["blocks_omitted_for_step"] = {
            "omitted": dropped,
            "reason": (f"Not part of the {step} step's source categories. "
                       f"Ask for a pack built for the owning step instead of "
                       f"working around the gap."),
        }

    # Klasor URETIM gunune gore adlandirilir, kesime gore degil. Kesim son
    # seanstir ve hafta sonu boyunca degismez; iki gun ust uste uretilen paket
    # ayni klasore yazip birbirini ezerdi ve kayit kaybolurdu. Kesim tarihi
    # manifest'te ve paketin kendi icinde zaten duruyor.
    #
    # Adim basina da AYRI klasor: once hepsi <TICKER>/ altina yaziyordu, ikinci
    # bir adim oncekinin instructions.md'sini eziyordu ve model tearsheet
    # paketiyle pitch talimatini yan yana gordu (2026-08-10).
    out = Path(args.out) / built_on / (ticker or subset_label or "universe") / step
    out.mkdir(parents=True, exist_ok=True)

    encoded = (json.dumps(pack, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (out / "pack.json").write_bytes(encoded)

    task = TASKS[step].format(n=universe_count, ticker=ticker or "")
    (out / "instructions.md").write_text(
        HEADER.format(scope=scope, cutoff=pack["cutoff_instant"],
                      execution=pack["execution_date"],
                      financial_period_end=financial_period_end,
                      financial_publication_date=financial_publication_date,
                      price_as_of=current_market_as_of,
                      market_statistics_as_of=market_statistics_as_of,
                      consensus_as_of=consensus_as_of,
                      drift_line=drift_line, task=task, step=step,
                      mandate=mandate_block(), stale_line=stale_line,
                      built_on=built_on),
        encoding="utf-8")

    (out / "manifest.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "built_on": built_on,
        "last_market_session": current_market_as_of,
        "intended_step": step,
        "ticker": ticker,
        "source_month": month,
        "source_run_root": SOURCE_RUN.relative_to(REPO).as_posix(),
        "financial_period_end": (entry.get("latest_period_end") if ticker else None),
        "financial_publication_date": (
            entry.get("financial_publication_date") if ticker else None
        ),
        "financial_data_cutoff": pack["cutoff_instant"],
        "financials_as_of": (entry.get("latest_period_end") if ticker else None),
        "prices_as_of": current_market_as_of,
        "valuation_as_of": current_market_as_of,
        "market_statistics_as_of": (
            entry.get("market_statistics_as_of") if ticker else None
        ),
        "consensus_as_of": consensus_as_of,
        "consensus_file": consensus_path.relative_to(REPO).as_posix(),
        "companies_in_pack": count,
        "consensus_coverage": f"{hit_n}/{count}",
        "consensus_missing": missing if not ticker else [],
        "guidance_coverage": f"{guidance_n}/{count}",
        "price_drift_ge_5pct": f"{drifted}/{universe_count}",
        "price_drift_worst_pct": round(worst, 2),
        "pack_sha256": hashlib.sha256(encoded).hexdigest(),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    try:
        shown = out.relative_to(REPO)
    except ValueError:
        shown = out          # repo disina yazilabilir (gecmis denemeleri)
    print(f"\nyazildi: {shown}")
    print(f"  pack.json        {len(encoded)/1024:,.0f} KB   ({count} sirket)")
    print(f"  instructions.md  ChatGPT'ye mesaj olarak yapistirilir")
    print("\nkapsam:")
    print(f"  konsensus  {hit_n}/{count}"
          + (f"   eksik: {', '.join(missing)}" if not ticker and missing else ""))
    print(f"  guidance   {guidance_n}/{count}")
    print(f"  ROIC       {roic_n}/{universe_count}"
          + (f"   ({roic_skipped} hesaplanamadi)" if roic_skipped else ""))
    if blocks.get("quarterly_series"):
        print(f"  ceyreklik seri {series_n}/{universe_count}"
              + (f"   ({series_skipped} yetersiz)" if series_skipped else ""))
        print(f"  baski oncesi konsensus {prior_n}/{universe_count}"
              + (f"   (as-of {prior_as_of})" if prior_as_of else "   -- henuz yok"))
    if blocks.get("net_debt", True):
        print(f"  net borc   {debt_n}/{universe_count}"
              + (f"   cikarilamayan: {', '.join(debt_missing)}" if debt_missing else ""))
    print(f"  ozel durum {special_n}/{universe_count}"
          + (f"   {', '.join(special_names)}" if special_names else ""))
    if eq_names:
        print(f"  kazanc kalitesi bayragi {eq_n}/{universe_count}   {', '.join(eq_names)}")
    deal_names = [c["ticker"] for c in pack["companies"]
                  if c.get("transaction_filing_history")]
    broken = [c["ticker"] for c in pack["companies"] if c.get("fundamentals_comparability")]
    if deal_names:
        print(f"  islem filing gecmisi {len(deal_names)}/{universe_count}   "
              f"{', '.join(deal_names)}   (guncel durum dogrulanmadi)")
    if broken:
        print(f"  kirik buyume   {len(broken)}/{universe_count}   {', '.join(broken)}"
              "   (yillik karsilastirma yapisal olayi asiyor)")
    if blocks["next_events"]:
        print(f"  olay       {events_n}/{universe_count}   (as-of {events_as_of})")
    if blocks["own_valuation_history"]:
        print(f"  carpan gecmisi {history_n}/{universe_count}   (son {history_last})")
    print(f"  guncel degerleme {current_valuation_n}/{universe_count}"
          + (f"   eksik: {', '.join(current_valuation_missing)}"
             if current_valuation_missing else ""))
    if ticker and "sector_peers" in pack:
        framework = pack["sector_peers"].get("framework_type")
        group = pack["sector_peers"].get("peer_group")
        print(f"  emsal      {pack['sector_peers'].get('peer_count', 0)} sirket "
              f"({framework or group})")
    if dropped:
        print(f"  cikarilan  {', '.join(dropped)}   (bu adima ait degil)")
    if ticker:
        own = "announced_but_not_filed" in pack["companies"][0]
        print(f"\nACIKLADI AMA DOSYALAMADI MI: {'EVET' if own else 'hayir'}"
              + (f"   {', '.join([pack['companies'][0]['announced_but_not_filed']['latest_8k']])}"
                 if own else ""))
    else:
        print(f"\nACIKLADI AMA DOSYALAMADI: {stale_n}/{universe_count}"
              + (f"\n  {', '.join(stale_names)}" if stale_names else ""))
    print(f"\nuretim gunu {built_on}   son piyasa seansi {current_market_as_of}")
    print("as-of:")
    if ticker:
        own_stale = "announced_but_not_filed" in pack["companies"][0]
        note = "   ACIKLADI AMA DOSYALAMADI" if own_stale else "   guncel"
    else:
        note = f"   ({stale_n} sirket acikladi ama dosyalamadi)" if stale_n else "   guncel"
    if ticker:
        print(f"  finansal donem sonu  {financial_period_end}{note}")
        print(f"  finansal yayin       {financial_publication_date}")
    else:
        print(f"  finansal veri kesimi {pack['cutoff_instant'][:10]}{note}")
    print(f"  fiyat/degerleme      {current_market_as_of}"
          + (f"   ({priced_n}/{universe_count} tazelendi)" if priced_n else " TAZELENEMEDI"))
    if ticker:
        print(f"  piyasa istatistikleri {market_statistics_as_of}")
    print(f"  konsensus  {consensus_as_of}")
    print(f"  olay       {events_as_of}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
