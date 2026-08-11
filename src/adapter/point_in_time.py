"""Point-in-time run-root, price-ledger and SEC-discovery-ledger primitives.

Extracted from fundamentaltrading's backtest.py: the live/PEI refresh flow
reuses the same "freeze a point-in-time view" machinery that the walk-forward
backtest used, applied to a single current cutoff instead of a monthly
sequence. Only the functions the live flow actually calls are here; the
walk-forward simulation itself (portfolio decisions, execution, monthly
performance) was left behind.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from engine.io import read_json, write_json_atomic
from engine.technical.models import DailyBar
from engine.valuation.ingestion.eod.models import EndOfDayFetchRequest
from engine.valuation.ingestion.eod.providers.yfinance_provider import YFinanceProvider

from .errors import UsPipelineError
from .discovery import resolve_cik
from .sec_client import SecClient

POSITION_WEIGHT = Decimal("0.10")
MAX_POSITIONS = 10
MAX_PER_COHORT = 3
TRANSACTION_COST_RATE = Decimal("0.001")
SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"


@dataclass(frozen=True)
class MonthPlan:
    month: str
    decision_date: str
    cutoff_date: str
    cutoff_instant: str
    execution_date: str

    def as_dict(self) -> dict[str, str]:
        return {
            "month": self.month,
            "decision_date": self.decision_date,
            "cutoff_date": self.cutoff_date,
            "cutoff_instant": self.cutoff_instant,
            "execution_date": self.execution_date,
        }


def initialize_backtest(
    *, repo_root: Path, run_id: str, start_date: str, end_date: str,
    parent: Path | None = None,
) -> Path:
    """`parent` verilmezse kok us/backtests altinda kurulur.

    Canli veri koku bir backtest DEGIL; kendi yerine kurulabilsin diye
    parametre eklendi. Fonksiyon adi tarihsel; iceriginde artik backtest'e
    ozel bir varsayim yok."""
    if not run_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in run_id):
        raise UsPipelineError("run_id may contain only letters, numbers, dash and underscore")
    base = parent.resolve() if parent else (repo_root.resolve() / "backtests")
    root = base / run_id
    if root.exists():
        config = read_json(root / "run-config.json")
        if config["start_date"] != start_date or config["end_date"] != end_date:
            raise UsPipelineError("existing backtest run has different date boundaries")
        _activate_frozen_peer_universe(
            root / "workspace" / "config",
            effective_from=(date.fromisoformat(start_date) - timedelta(days=1)).isoformat(),
        )
        return root

    source_config = repo_root.resolve() / "config"
    root.mkdir(parents=True)
    _copytree(source_config, root / "workspace" / "config")
    _activate_frozen_peer_universe(
        root / "workspace" / "config",
        effective_from=(date.fromisoformat(start_date) - timedelta(days=1)).isoformat(),
    )
    cohorts = load_cohorts(source_config)
    tickers = sorted(cohorts)
    if len(tickers) < MAX_POSITIONS:
        raise UsPipelineError(
            f"universe has {len(tickers)} companies, fewer than the {MAX_POSITIONS} positions"
        )
    if MAX_PER_COHORT * len(set(cohorts.values())) < MAX_POSITIONS:
        raise UsPipelineError(
            f"{len(set(cohorts.values()))} cohorts at most {MAX_PER_COHORT} each cannot fill "
            f"{MAX_POSITIONS} positions"
        )
    config = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "start_date": date.fromisoformat(start_date).isoformat(),
        "end_date": date.fromisoformat(end_date).isoformat(),
        "universe": tickers,
        "cohorts": cohorts,
        "position_weight": str(POSITION_WEIGHT),
        "max_positions": MAX_POSITIONS,
        "max_per_cohort": MAX_PER_COHORT,
        "transaction_cost_rate": str(TRANSACTION_COST_RATE),
        "created_at": _utc_now(),
        "source_config_sha256": _tree_hash(source_config),
    }
    write_json_atomic(root / "run-config.json", config)
    return root


def peer_universe_paths(config_root: Path) -> list[Path]:
    """Tanimli butun emsal evrenleri. Tek bir dosyaya sabitlenmis degildir:
    emsal karsilastirmasi sektor-gorelidir ve her sektorun kendi evreni vardir."""
    root = config_root / "valuation" / "comparison" / "peer-universes"
    return sorted(root.glob("*.json")) if root.is_dir() else []


def load_cohorts(config_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in peer_universe_paths(config_root):
        universe = read_json(path)
        for member in universe.get("members", []):
            refs = member.get("classification_refs", [])
            models = [item.split(":", 1)[1] for item in refs if item.startswith("MODEL:")]
            if len(models) != 1:
                raise UsPipelineError(f"{member.get('ticker')}: exactly one MODEL cohort is required")
            ticker = str(member["ticker"]).upper()
            if ticker in result:
                raise UsPipelineError(f"duplicate peer-universe ticker: {ticker}")
            result[ticker] = models[0]
    return result


def _activate_frozen_peer_universe(config_root: Path, *, effective_from: str) -> None:
    for path in peer_universe_paths(config_root):
        universe = read_json(path)
        universe["effective_from"] = effective_from
        for member in universe.get("members", []):
            member["effective_from"] = effective_from
        write_json_atomic(path, universe)


def freeze_price_ledger(*, run_root: Path) -> Path:
    config = read_json(run_root / "run-config.json")
    ledger_dir = run_root / "ledger" / "prices"
    manifest_path = run_root / "ledger" / "price-ledger.json"
    if manifest_path.exists():
        verify_price_ledger(run_root)
        return manifest_path
    start = date.fromisoformat(config["start_date"]) - timedelta(days=450)
    end = date.fromisoformat(config["end_date"]) + timedelta(days=45)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    frozen_at = _utc_now()
    hashes: dict[str, str] = {}
    provider = YFinanceProvider()
    for ticker in config["universe"]:
        request = EndOfDayFetchRequest(
            internal_ticker=ticker, provider_symbol=ticker,
            start_date_inclusive=start.isoformat(), end_date_exclusive=end.isoformat(),
            repair=True,
        )
        series = provider.fetch((request,))[0]
        if series.status != "ok" or not series.rows:
            raise UsPipelineError(f"price ledger fetch failed for {ticker}: {series.error_reason}")
        payload = {
            "schema_version": "1.0.0", "ticker": ticker, "provider": "yfinance",
            "frozen_at": frozen_at, "rows": [row.to_dict() for row in series.rows],
            "warnings": list(series.warnings),
        }
        path = ledger_dir / f"{ticker}.json"
        write_json_atomic(path, payload)
        hashes[ticker] = _file_hash(path)
    manifest = {
        "schema_version": "1.0.0", "frozen_at": frozen_at,
        "purpose_separation": {
            "decision": "raw close only; adjusted values and future performance are forbidden",
            "performance": "adjusted-open total-return calculation; never exposed to report or LLM",
        },
        "ticker_sha256": hashes,
    }
    write_json_atomic(manifest_path, manifest)
    return manifest_path


def verify_price_ledger(run_root: Path) -> None:
    manifest = read_json(run_root / "ledger" / "price-ledger.json")
    expected = manifest.get("ticker_sha256", {})
    if set(expected) != set(read_json(run_root / "run-config.json")["universe"]):
        raise UsPipelineError("price ledger universe does not match the frozen run universe")
    for ticker, digest in expected.items():
        path = run_root / "ledger" / "prices" / f"{ticker}.json"
        if not path.is_file() or _file_hash(path) != digest:
            raise UsPipelineError(f"price ledger hash mismatch for {ticker}")


def freeze_sec_discovery_ledger(*, run_root: Path, client: SecClient) -> Path:
    target = run_root / "ledger" / "sec-discovery.json"
    payload_root = run_root / "ledger" / "sec-discovery-payloads"
    if target.exists():
        verify_sec_discovery_ledger(run_root)
        return target
    config = read_json(run_root / "run-config.json")
    ticker_payload = client.get_json(SEC_TICKER_URL)
    payload_root.mkdir(parents=True, exist_ok=True)
    ticker_path = payload_root / "company_tickers.json"
    write_json_atomic(ticker_path, ticker_payload)
    records = {}
    for ticker in config["universe"]:
        cik = resolve_cik(_StaticJsonClient({SEC_TICKER_URL: ticker_payload}), ticker)
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        submissions = client.get_json(url)
        path = payload_root / f"CIK{cik}.json"
        write_json_atomic(path, submissions)
        records[ticker] = {
            "cik": cik, "url": url, "relative_path": path.relative_to(run_root).as_posix(),
            "sha256": _file_hash(path),
        }
        # The submissions endpoint spills filings older than its ~1000-entry
        # cap into filings.files[]. Those pages must be frozen too, otherwise
        # a point-in-time run silently sees only a frequent filer's recent
        # history and cannot resolve its older annual reports.
        for entry in submissions.get("filings", {}).get("files", []) or []:
            name = entry.get("name") if isinstance(entry, dict) else None
            if not name:
                continue
            page_url = f"https://data.sec.gov/submissions/{name}"
            page_path = payload_root / name
            write_json_atomic(page_path, client.get_json(page_url))
            records[f"{ticker}:{name}"] = {
                "cik": cik, "url": page_url,
                "relative_path": page_path.relative_to(run_root).as_posix(),
                "sha256": _file_hash(page_path),
            }
    manifest = {
        "schema_version": "1.0.0", "frozen_at": _utc_now(),
        "company_tickers": {
            "url": SEC_TICKER_URL,
            "relative_path": ticker_path.relative_to(run_root).as_posix(),
            "sha256": _file_hash(ticker_path),
        },
        "submissions": records,
    }
    write_json_atomic(target, manifest)
    return target


def verify_sec_discovery_ledger(run_root: Path) -> None:
    manifest = read_json(run_root / "ledger" / "sec-discovery.json")
    entries = [manifest["company_tickers"], *manifest["submissions"].values()]
    for entry in entries:
        path = run_root / entry["relative_path"]
        if not path.is_file() or _file_hash(path) != entry["sha256"]:
            raise UsPipelineError(f"SEC discovery ledger hash mismatch: {path}")


class _StaticJsonClient:
    def __init__(self, payloads: dict[str, dict[str, Any]]) -> None:
        self.payloads = payloads

    def get_json(self, url: str) -> dict[str, Any]:
        return self.payloads[url]


def build_month_plans(*, run_root: Path, calendar_ticker: str = "WMT") -> list[MonthPlan]:
    verify_price_ledger(run_root)
    config = read_json(run_root / "run-config.json")
    rows = _price_rows(run_root, calendar_ticker)
    sessions = sorted(row["trade_date"] for row in rows)
    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"])
    grouped: dict[str, list[str]] = {}
    for session in sessions:
        if start <= date.fromisoformat(session) <= end:
            grouped.setdefault(session[:7], []).append(session)
    plans = []
    for month, month_sessions in sorted(grouped.items()):
        decision = month_sessions[0]
        decision_index = sessions.index(decision)
        if decision_index + 1 >= len(sessions) and month == max(grouped):
            continue
        if decision_index == 0 or decision_index + 1 >= len(sessions):
            raise UsPipelineError(f"calendar has no cutoff/execution session for {month}")
        cutoff = sessions[decision_index - 1]
        execution = sessions[decision_index + 1]
        plans.append(MonthPlan(
            month=month, decision_date=decision, cutoff_date=cutoff,
            cutoff_instant=f"{cutoff}T23:59:59Z", execution_date=execution,
        ))
    if not plans:
        raise UsPipelineError("no monthly backtest plans were generated")
    return plans


def materialize_month_cutoff(*, run_root: Path, plan: MonthPlan) -> Path:
    month_root = run_root / "months" / plan.month
    target = month_root / "cutoff.json"
    manifest_hash = _file_hash(run_root / "ledger" / "price-ledger.json")
    payload = {**plan.as_dict(), "price_ledger_manifest_sha256": manifest_hash}
    if target.exists():
        if read_json(target) != payload:
            raise UsPipelineError(f"immutable cutoff artifact differs for {plan.month}")
        return target
    month_root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(target, payload)
    return target


def historical_market_observation(
    *, run_root: Path, ticker: str, plan: MonthPlan,
) -> dict[str, str]:
    verify_price_ledger(run_root)
    manifest = read_json(run_root / "ledger" / "price-ledger.json")
    row = _row_on(run_root, ticker, plan.cutoff_date)
    close = _available(row, "close", ticker)
    # Kurumsal islemler ayni donmus defterden, bakis penceresiyle birlikte
    # tasinir. Piyasa katmani bunlari filing'in kapak tarihine gore suzer:
    # pay adedi o tarihin rakamidir ve araya giren bir islem onu gecersiz kilar.
    lookback = (date.fromisoformat(plan.cutoff_date) - timedelta(days=400)).isoformat()
    actions = [
        {"effective_date": item["trade_date"], "factor": item["stock_split"]["value"]}
        for item in _price_rows(run_root, ticker)
        if lookback <= item["trade_date"] <= plan.cutoff_date
        and _is_corporate_action(item)
    ]
    return {
        "ticker": ticker, "trade_date": plan.cutoff_date, "close": close,
        "available_at": f"{plan.cutoff_date}T20:00:00Z",
        "ledger_frozen_at": manifest["frozen_at"],
        "ledger_sha256": manifest["ticker_sha256"][ticker],
        "source_record_ref": f"backtest-ledger:yfinance:{ticker}:{plan.cutoff_date}:raw-close",
        "corporate_actions": actions,
        "corporate_actions_from": lookback,
    }


def _is_corporate_action(row: dict[str, Any]) -> bool:
    """Bu satirda gercekten bir kurumsal islem var mi.

    Besleme, islem olmayan gunleri 1 ile degil SIFIR ile isaretliyor. Yalniz
    1'i elemek her seansi bir bolunme sanmaya yol acar."""
    field = row.get("stock_split") or {}
    if field.get("status") != "available":
        return False
    try:
        factor = Decimal(str(field.get("value")))
    except (InvalidOperation, TypeError):
        return False
    return factor not in (Decimal(0), Decimal(1))


def historical_technical_input(
    *, run_root: Path, ticker: str, plan: MonthPlan, lookback_days: int = 400,
) -> dict[str, Any]:
    verify_price_ledger(run_root)
    first_day = date.fromisoformat(plan.cutoff_date) - timedelta(days=lookback_days)
    rows = [
        row for row in _price_rows(run_root, ticker)
        if first_day.isoformat() <= row["trade_date"] <= plan.cutoff_date
    ]
    if not rows:
        raise UsPipelineError(f"{ticker}: no point-in-time technical history at {plan.cutoff_date}")
    factor = Decimal("1")
    adjusted: list[DailyBar] = []
    action_dates: set[str] = set()
    previous_ratio: Decimal | None = None
    for row in reversed(rows):
        raw_close = Decimal(_available(row, "close", ticker))
        raw_open = Decimal(_available(row, "open", ticker))
        raw_high = Decimal(_available(row, "high", ticker))
        raw_low = Decimal(_available(row, "low", ticker))
        volume = Decimal(_available(row, "volume", ticker))
        adjusted.append(DailyBar(
            trade_date=row["trade_date"], open=raw_open * factor,
            high=raw_high * factor, low=raw_low * factor, close=raw_close * factor,
            adjusted_close=raw_close * factor, volume=volume,
        ))
        dividend = Decimal(_available(row, "dividend", ticker))
        split = Decimal(_available(row, "stock_split", ticker))
        if dividend != 0 or split != 0:
            action_dates.add(row["trade_date"])
        if dividend != 0:
            if dividend >= raw_close:
                # A distribution at or above the share price cannot be a
                # dividend in the multiplicative sense; it marks a
                # reorganisation the provider's dividend field describes only
                # partially. The provider's adjusted close already reflects
                # the whole action, and dividing this row's adjusted/raw
                # ratio by the following row's isolates just this day's step.
                if previous_ratio is None:
                    raise UsPipelineError(
                        f"{ticker}: unmodellable distribution on {row['trade_date']} "
                        "is the most recent bar, so no provider ratio step exists"
                    )
                ratio = Decimal(_available(row, "adjusted_close", ticker)) / raw_close
                factor *= ratio / previous_ratio
            else:
                factor *= (raw_close - dividend) / raw_close
        if split != 0:
            if split <= 0:
                raise UsPipelineError(f"{ticker}: invalid split adjustment on {row['trade_date']}")
            factor /= split
        previous_ratio = Decimal(_available(row, "adjusted_close", ticker)) / raw_close
    adjusted.reverse()
    return {"daily_bars": adjusted, "corporate_action_dates": action_dates}


def _price_rows(run_root: Path, ticker: str) -> list[dict[str, Any]]:
    return read_json(run_root / "ledger" / "prices" / f"{ticker}.json")["rows"]


def _row_on(run_root: Path, ticker: str, trade_date: str) -> dict[str, Any]:
    rows = [row for row in _price_rows(run_root, ticker) if row["trade_date"] == trade_date]
    if len(rows) != 1:
        raise UsPipelineError(f"{ticker}: expected one price row on {trade_date}, found {len(rows)}")
    return rows[0]


def _available(row: dict[str, Any], field: str, ticker: str) -> str:
    value = row.get(field, {})
    if value.get("status") != "available" or value.get("value") is None:
        raise UsPipelineError(f"{ticker}: {field} is unavailable on {row.get('trade_date')}")
    return str(value["value"])


def _copytree(source: Path, target: Path) -> None:
    import shutil
    shutil.copytree(source, target)


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
