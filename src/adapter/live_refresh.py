"""Canli veri tazeleme: paket uretildigi gunun verisini tasisin.

Tasarim ilkesi -- KATMANLAR AYNI HIZDA DEGISMEZ:

  fiyat        her seans degisir   -> her kosuda tazelenir  (~40 sn)
  SEC kesfi    her gun degisebilir -> her kosuda tazelenir  (~2 dk)
  finansal     ancak YENI BILANCO gelince degisir -> yalniz o sirketler
               yeniden islenir (~30 sn/sirket)
  konsensus    her gun degisir     -> her kosuda tazelenir  (~40 sn)
  olay takvimi her gun degisebilir -> her kosuda tazelenir  (~40 sn)

Butun 60 sirketi her gun yeniden islemek 30 dakika surer ve neredeyse her
gun ayni sonucu uretir; bilanco takvimi buna izin vermez. Bu yuzden tetik
takvim degil, DOSYALAMADIR: bir sirketin SEC'deki en yeni 10-Q/10-K'si
elimizdekinden yeniyse o sirket yeniden islenir, digerleri atlanir.

Config kopyalanmaz -- canli kok config icin dogrudan repo kokune bakar
(bkz. point_in_time.initialize_run_root, workflow.run_company_workflow'un
config_root parametresi). Yalniz kendi urettigi veri (data/, raw/, cache/,
raw-cache/, reports/) kok altinda yasar; ayrica bir "workspace/" katmani
yok, hepsi dogrudan run root'un altinda.
"""
from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .point_in_time import (
    SEC_TICKER_URL, MonthPlan, _StaticJsonClient, _file_hash, _price_rows,
    freeze_price_ledger, freeze_sec_discovery_ledger,
    historical_market_observation, historical_technical_input,
    initialize_run_root, load_cohorts, materialize_month_cutoff, read_json,
    verify_price_ledger, verify_sec_discovery_ledger, write_json_atomic,
)
from .discovery import resolve_cik
from .errors import UsPipelineError
from .sec_client import SecClient
from engine.valuation.ingestion.eod.models import EndOfDayFetchRequest
from engine.valuation.ingestion.eod.providers.yfinance_provider import YFinanceProvider

# Canli veri koku live/current.
#
# DIKKAT: kok klasorune "data" ADI VERILEMEZ. Degerleme referanslarini
# yazan _valuation_inputs_relative_path_of yolu parcalara ayirip ILK
# "data" segmentinden itibaren aliyor; kok klasorun adi "data" olursa
# referans "data/data/..." diye yaziliyor ve dogrulama
# ArtifactReferenceError ile patliyor. 2026-08-10'da tam bu yasandi.
RUN_ID = "current"
LIVE_PARENT = "live"
START_DATE = "2024-01-01"          # 400 gunluk teknik geriye bakis icin yeterli
END_DATE = "2030-12-31"            # sabit: her gun yeni kok yaratmamak icin
FORMS = ("10-K", "10-Q")


def refresh_live_price_ledger(
    *, run_root: Path, provider: Any | None = None,
    through: date | None = None,
) -> Path:
    """Canli fiyat defterini yeni seanslarla ilerlet.

    Backtest'in ``freeze_price_ledger`` fonksiyonu bilerek immutable'dir.
    Canli kokte ise ayni davranis son seansi ilk kosu gununde birakiyordu.
    Mevcut satirlar korunur; saglayicidan gelen ayni tarihli satir son degerdir.
    Bir ticker yenilenemezse onun eski defteri korunur ve manifestte aciklanir.
    """
    manifest_path = run_root / "ledger" / "price-ledger.json"
    if not manifest_path.is_file():
        return freeze_price_ledger(run_root=run_root)

    verify_price_ledger(run_root)
    config = read_json(run_root / "run-config.json")
    ledger_dir = run_root / "ledger" / "prices"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    provider = provider or YFinanceProvider()
    through = through or date.today()
    end_exclusive = (through + timedelta(days=1)).isoformat()
    failures: dict[str, str] = {}
    hashes: dict[str, str] = {}

    states: dict[str, tuple[Path, dict[str, Any], list[dict[str, Any]]]] = {}
    requests: dict[str, EndOfDayFetchRequest] = {}
    for ticker in config["universe"]:
        path = ledger_dir / f"{ticker}.json"
        existing = read_json(path) if path.is_file() else {
            "schema_version": "1.0.0", "ticker": ticker,
            "provider": "yfinance", "rows": [], "warnings": [],
        }
        rows = existing.get("rows") or []
        start = (
            str(rows[-1]["trade_date"])
            if rows else
            (date.fromisoformat(config["start_date"]) - timedelta(days=450)).isoformat()
        )
        states[ticker] = (path, existing, rows)
        requests[ticker] = EndOfDayFetchRequest(
            internal_ticker=ticker, provider_symbol=ticker,
            start_date_inclusive=start, end_date_exclusive=end_exclusive,
            repair=True,
        )

    results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(requests) or 1)) as executor:
        futures = {
            executor.submit(provider.fetch, (request,)): ticker
            for ticker, request in requests.items()
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                results[ticker] = future.result()[0]
            except Exception as exc:
                failures[ticker] = f"{type(exc).__name__}: {exc}"

    for ticker in config["universe"]:
        path, existing, rows = states[ticker]
        series = results.get(ticker)
        if series is None:
            if path.is_file():
                hashes[ticker] = _file_hash(path)
            continue
        if series.status != "ok" or not series.rows:
            failures[ticker] = series.error_reason or "provider returned no rows"
            if path.is_file():
                hashes[ticker] = _file_hash(path)
            continue
        merged = {str(row["trade_date"]): row for row in rows}
        merged.update({row.trade_date: row.to_dict() for row in series.rows})
        payload = {
            **existing,
            "schema_version": "1.0.0",
            "ticker": ticker,
            "provider": "yfinance",
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "rows": [merged[key] for key in sorted(merged)],
            "warnings": sorted(set(existing.get("warnings") or []) | set(series.warnings)),
        }
        payload.setdefault("frozen_at", payload["refreshed_at"])
        write_json_atomic(path, payload)
        hashes[ticker] = _file_hash(path)

    manifest = read_json(manifest_path)
    manifest["ticker_sha256"] = hashes
    manifest["refreshed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["refresh_failures"] = failures
    write_json_atomic(manifest_path, manifest)
    verify_price_ledger(run_root)
    return manifest_path


def refresh_live_sec_discovery_ledger(
    *, run_root: Path, client: SecClient,
) -> Path:
    """Canli SEC submissions snapshot'ini tum mevcut ticker'lar icin yenile."""
    target = run_root / "ledger" / "sec-discovery.json"
    if not target.is_file():
        return freeze_sec_discovery_ledger(run_root=run_root, client=client)

    verify_sec_discovery_ledger(run_root)
    config = read_json(run_root / "run-config.json")
    manifest = read_json(target)
    payload_root = run_root / "ledger" / "sec-discovery-payloads"
    payload_root.mkdir(parents=True, exist_ok=True)
    ticker_payload = client.get_json(SEC_TICKER_URL)
    ticker_path = payload_root / "company_tickers.json"
    write_json_atomic(ticker_path, ticker_payload)
    manifest["company_tickers"] = {
        "url": SEC_TICKER_URL,
        "relative_path": ticker_path.relative_to(run_root).as_posix(),
        "sha256": _file_hash(ticker_path),
    }

    records = manifest.get("submissions") or {}
    resolver = _StaticJsonClient({SEC_TICKER_URL: ticker_payload})
    for ticker in config["universe"]:
        previous = records.get(ticker) or {}
        cik = previous.get("cik") or resolve_cik(resolver, ticker)
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        submissions = client.get_json(url)
        path = payload_root / f"CIK{cik}.json"
        write_json_atomic(path, submissions)
        records[ticker] = {
            "cik": cik, "url": url,
            "relative_path": path.relative_to(run_root).as_posix(),
            "sha256": _file_hash(path),
        }
        for entry in submissions.get("filings", {}).get("files", []) or []:
            name = entry.get("name") if isinstance(entry, dict) else None
            if not name:
                continue
            record_key = f"{ticker}:{name}"
            page_path = payload_root / name
            if not page_path.is_file():
                page_url = f"https://data.sec.gov/submissions/{name}"
                write_json_atomic(page_path, client.get_json(page_url))
            records[record_key] = {
                "cik": cik,
                "url": f"https://data.sec.gov/submissions/{name}",
                "relative_path": page_path.relative_to(run_root).as_posix(),
                "sha256": _file_hash(page_path),
            }

    manifest["submissions"] = records
    manifest["refreshed_at"] = datetime.now(timezone.utc).isoformat()
    write_json_atomic(target, manifest)
    verify_sec_discovery_ledger(run_root)
    return target


def sec_user_agent(repo_root: Path) -> str:
    """SEC kimligi. Ortamda yoksa git kimliginden kurulur."""
    existing = os.environ.get("SEC_USER_AGENT")
    if existing:
        return existing

    def git(field: str) -> str:
        return subprocess.run(["git", "config", f"user.{field}"], capture_output=True,
                              text=True, cwd=repo_root).stdout.strip()

    name, mail = git("name"), git("email")
    if not mail:
        raise RuntimeError(
            "SEC_USER_AGENT yok ve git user.email bos. SEC kimlik ister; "
            "ya ortam degiskenini tanimlayin ya git yapilandirmasini doldurun.")
    agent = f"{name} {mail}".strip()
    os.environ["SEC_USER_AGENT"] = agent
    return agent


def latest_filing_dates(run_root: Path, universe: list[str]) -> dict[str, str]:
    """Her sirketin SEC'deki en yeni 10-Q/10-K dosyalama tarihi."""
    ledger = read_json(run_root / "ledger" / "sec-discovery.json")
    out: dict[str, str] = {}
    for ticker in universe:
        entry = ledger.get("submissions", {}).get(ticker)
        if not entry:
            continue
        payload = read_json(run_root / entry["relative_path"])
        recent = payload.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        best = [d for f, d in zip(forms, dates) if f in FORMS]
        if best:
            out[ticker] = max(best)
    return out


def held_publication_dates(run_root: Path, universe: list[str]) -> dict[str, str]:
    """Elimizde islenmis en yeni finansalin yayin tarihi."""
    out: dict[str, str] = {}
    root = run_root / "data" / "financial"
    for ticker in universe:
        folder = root / ticker
        if not folder.is_dir():
            continue
        best = None
        for path in folder.glob("*.json"):
            if "derived" in path.name:
                continue
            try:
                published = json.loads(path.read_text(encoding="utf-8")).get("publication_date")
            except Exception:
                continue
            if published and (best is None or published > best):
                best = published
        if best:
            out[ticker] = best
    return out


def month_is_complete(*, run_root: Path, cutoff: str, universe: list[str]) -> bool:
    """Bu kesim icin butun evrenin degerlemesi cikmis mi?

    Olcu RAPOR DEGIL degerleme sonucudur. Eskiden markdown sayiliyordu;
    canli akis rapor uretmedigi icin o kural hicbir ayi tam gormezdi.
    """
    results = run_root / "data" / "valuation-results"
    return all((results / ticker / cutoff).is_dir() for ticker in universe)


def run_live_month(*, client: SecClient, run_root: Path, repo_root: Path, plan: MonthPlan,
                   tickers: list[str],
                   log: Callable[[str], None] = print) -> dict[str, Any]:
    """Bir kesimi RAPOR URETMEDEN isle.

    Canli akista rapor okuyan yok: paket dogrudan artifact'lerden kuruluyor
    (live_pack.py) ve yalniz months/<ay>/cutoff.json'a bakiyor. Rapor
    uretimi sureyi buyutuyordu ve bugun uc saat kaybettiren
    ArtifactReferenceError tam oradan geliyordu.
    """
    from .peers import generate_us_peer_comparisons
    from .workflow import run_company_workflow

    done, failed = [], {}
    for index, ticker in enumerate(tickers, start=1):
        started = time.time()
        try:
            financial_as_of = date.fromisoformat(plan.cutoff_instant[:10])
            run_company_workflow(
                client=client, workspace=run_root, config_root=repo_root, ticker=ticker,
                as_of=financial_as_of,
                cutoff_instant=plan.cutoff_instant,
                historical_market_observation=historical_market_observation(
                    run_root=run_root, ticker=ticker, plan=plan),
                historical_technical_input=historical_technical_input(
                    run_root=run_root, ticker=ticker, plan=plan),
                generate_report=False,
            )
            done.append(ticker)
        except Exception as exc:
            # Bir sirketin cozulemeyen girdisi digerlerini dusurmez; bosluk
            # sessizce degil adiyla bildirilir.
            failed[ticker] = str(exc)[:200]
            log(f"    {ticker} BASARISIZ: {str(exc)[:90]}")
        if index % 20 == 0:
            log(f"    [{index}/{len(tickers)}] {time.time()-started:.0f} sn/sirket",
                )
    if done:
        generate_us_peer_comparisons(
            workspace=run_root, config_root=repo_root, tickers=done,
            as_of_date=plan.cutoff_instant[:10], generated_at=plan.cutoff_instant,
            generate_report=False,
        )

    # Kapsama kaydi: bu kesimde kimin cikmadigini ekrana yazip unutmayiz.
    # Kurumsal islem araya girdiginde bir sirket icin piyasa degeri
    # kurulamaz ve o sirket-kesim bosta kalir; bu bir OLCUM boslugudur ve
    # sonradan "neden 58 sirket vardi" diye sorulacak tek yer burasi.
    #
    # Sayim BU KOSUNUN listesinden degil ARTIFACT'ten yapilir: gunluk
    # tazelemede `tickers` yalnizca yeni bilanco gelen birkac sirkettir ve
    # onu evren sanmak 60'lik kaydin uzerine "universe: 3" yazardi.
    write_live_coverage(run_root=run_root, plan=plan, skipped=failed)

    return {"month": plan.month, "processed": done, "skipped": failed,
            "status": "generated"}


def write_live_coverage(
    *, run_root: Path, plan: MonthPlan, skipped: dict[str, str] | None = None,
) -> Path:
    """Mevcut artefaktlardan canli kesit kapsam kaydini yeniden kur."""
    universe = read_json(run_root / "run-config.json")["universe"]
    financials = run_root / "data" / "financial"
    covered = [ticker for ticker in universe if (financials / ticker).is_dir()]
    path = run_root / "months" / plan.month / "coverage.json"
    write_json_atomic(path, {
        "month": plan.month,
        "universe": len(universe),
        "covered": len(covered),
        "missing": [ticker for ticker in universe if ticker not in covered],
        "skipped": skipped or {},
    })
    return path


def synchronize_live_universe(*, run_root: Path, repo_root: Path) -> dict[str, list[str]]:
    """Mevcut canli koku authored config ile ileri tasir.

    ``initialize_run_root`` mevcut bir koku bilerek yeniden yazmaz. Bu dogru
    backtest davranisidir, fakat hep-guncel canli kokte yeni bir sirketin
    config'e eklenip veri akisina hic girmemesiyle sonuclanir. Senkronizasyon
    yalniz ``live/current`` icin burada yapilir; uretilmis sirket verileri
    silinmez.
    """
    path = run_root / "run-config.json"
    config = read_json(path)
    desired_cohorts = load_cohorts(repo_root / "config")
    desired = sorted(desired_cohorts)
    current = list(config.get("universe") or [])
    added = sorted(set(desired) - set(current))
    removed = sorted(set(current) - set(desired))
    cohort_changed = config.get("cohorts") != desired_cohorts
    if added or removed or cohort_changed:
        config["universe"] = desired
        config["cohorts"] = desired_cohorts
        config["universe_source"] = "config/valuation/comparison/peer-universes"
        config["universe_synced_at"] = datetime.now(timezone.utc).isoformat()
        write_json_atomic(path, config)
    return {"added": added, "removed": removed}


def live_month_name(*, run_root: Path, cutoff: str) -> str:
    """Ayni kapanista degisen canli evren icin immutable kesiti surumle."""
    manifest = run_root / "ledger" / "price-ledger.json"
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    base = run_root / "months" / cutoff / "cutoff.json"
    if not base.is_file():
        return cutoff
    existing = read_json(base)
    if existing.get("price_ledger_manifest_sha256") == manifest_hash:
        return cutoff
    return f"{cutoff}-{manifest_hash[:8]}"


def refresh(*, repo_root: Path, log: Callable[[str], None] = print,
            force: bool = False) -> dict[str, Any]:
    """Canli kokte fiyat, SEC ve finansallari bugune getirir."""
    agent = sec_user_agent(repo_root)
    log(f"SEC kimligi: {agent}")

    root = initialize_run_root(repo_root=repo_root, run_id=RUN_ID,
                               start_date=START_DATE, end_date=END_DATE,
                               parent=repo_root / LIVE_PARENT)

    universe_change = synchronize_live_universe(run_root=root, repo_root=repo_root)
    if universe_change["added"]:
        log(f"evrene eklendi  -> {', '.join(universe_change['added'])}")
    if universe_change["removed"]:
        log(f"evrenden cikti  -> {', '.join(universe_change['removed'])}")

    universe = read_json(root / "run-config.json")["universe"]

    started = time.time()
    refresh_live_price_ledger(run_root=root)
    sessions = sorted(row["trade_date"] for row in _price_rows(root, "WMT"))
    market_session = sessions[-1]
    log(f"fiyat defteri  -> {market_session}   ({time.time()-started:.0f} sn)")

    client = SecClient(user_agent=agent)
    started = time.time()
    refresh_live_sec_discovery_ledger(run_root=root, client=client)
    log(f"SEC kesfi      -> tamam    ({time.time()-started:.0f} sn)")

    filed = latest_filing_dates(root, universe)
    held = held_publication_dates(root, universe)
    # Tetik takvim degil DOSYALAMA: SEC'deki en yeni rapor elimizdekinden
    # yeniyse (ya da hic islenmemisse) o sirket yeniden islenir.
    todo = [
        ticker for ticker in universe
        if (
            force
            or ticker not in held
            or filed.get(ticker, "") > held[ticker]
        )
    ]

    # Her canli snapshot kendi klasorunde kalir. Fiyat seansi ile bilgi cutoff'u
    # ayridir: piyasa kapaliyken yeni bir SEC filing yine de uygun olabilir.
    information_now = datetime.now(timezone.utc)
    information_date = information_now.date().isoformat()
    cutoff_instant = information_now.isoformat().replace("+00:00", "Z")
    snapshot_suffix = hashlib.sha256(cutoff_instant.encode("utf-8")).hexdigest()[:8]
    month = f"{information_date}-{snapshot_suffix}"
    plan = MonthPlan(
        month=month, decision_date=information_date,
        cutoff_date=market_session, cutoff_instant=cutoff_instant,
        execution_date=market_session,
    )

    fresh = [t for t in todo if t in held]
    log(f"finansal: {len(todo)}/{len(universe)} sirket islenecek"
        + (f"   yeni bilanco: {', '.join(fresh)}" if fresh else ""))

    if force and todo:
        # run_company_workflow bir sirketin daha onceki ciktisi varsa erken
        # donuyor. Katalog degistiginde (yeni bir XBRL kavrami eklendiginde)
        # yeniden cikarim ancak bu izler silinirse gerceklesir.
        for ticker in todo:
            for relative in (
                Path("reports") / "valuation" / ticker / f"{information_date}-valuation-analysis.md",
                Path("data") / "valuation-results" / ticker / information_date,
                Path("data") / "valuation-inputs" / ticker / information_date,
                Path("data") / "market-inputs" / ticker / information_date,
            ):
                target = root / relative
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                else:
                    target.unlink(missing_ok=True)
            # Temel analiz raporlari donem adiyla yazilir (2026-Q3-...), kesim
            # adiyla degil; hangi donemin yeniden islenecegi burada bilinmedigi
            # icin sirketin klasoru butunuyle kalkar. Artik hic uretilmiyorlar,
            # bu yalniz eski kosulardan kalanlari supurur.
            shutil.rmtree(root / "reports" / ticker, ignore_errors=True)
        log(f"zorlama: {len(todo)} sirketin onceki ciktisi silindi")

    started = time.time()
    materialize_month_cutoff(run_root=root, plan=plan)
    outcome = run_live_month(client=client, run_root=root, repo_root=repo_root, plan=plan,
                             tickers=todo, log=log) if todo else {
        "processed": [], "skipped": {}, "status": "existing"}
    if not todo:
        write_live_coverage(run_root=root, plan=plan)
    log(f"finansal+degerleme -> {month}   ({time.time()-started:.0f} sn, "
        f"{len(outcome['processed'])} sirket)")

    return {
        "run_root": root,
        "month": month,
        "cutoff_date": information_date,
        "market_session": market_session,
        "universe": universe,
        "reprocessed": todo,
        "skipped": outcome.get("skipped", {}),
        "status": outcome.get("status", "built"),
    }
