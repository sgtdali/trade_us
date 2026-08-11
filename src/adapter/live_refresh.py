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
import os
import shutil
import subprocess
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

from .point_in_time import (
    MonthPlan, _price_rows, freeze_price_ledger, freeze_sec_discovery_ledger,
    historical_market_observation, historical_technical_input,
    initialize_run_root, materialize_month_cutoff, read_json,
)
from .sec_client import SecClient

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
            run_company_workflow(
                client=client, workspace=run_root, config_root=repo_root, ticker=ticker,
                as_of=date.fromisoformat(plan.cutoff_date),
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
            as_of_date=plan.cutoff_date, generated_at=plan.cutoff_instant,
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
    universe = read_json(run_root / "run-config.json")["universe"]
    results = run_root / "data" / "valuation-results"
    covered = [t for t in universe if (results / t / plan.cutoff_date).is_dir()]
    month_root = run_root / "months" / plan.month
    month_root.mkdir(parents=True, exist_ok=True)
    (month_root / "coverage.json").write_text(
        json.dumps({"month": plan.month, "universe": len(universe),
                    "covered": len(covered),
                    "missing": [t for t in universe if t not in covered],
                    "skipped": failed},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    return {"month": plan.month, "processed": done, "skipped": failed,
            "status": "generated"}


def refresh(*, repo_root: Path, log: Callable[[str], None] = print,
            force: bool = False) -> dict[str, Any]:
    """Canli kokte fiyat, SEC ve finansallari bugune getirir."""
    agent = sec_user_agent(repo_root)
    log(f"SEC kimligi: {agent}")

    root = initialize_run_root(repo_root=repo_root, run_id=RUN_ID,
                               start_date=START_DATE, end_date=END_DATE,
                               parent=repo_root / LIVE_PARENT)

    universe = read_json(root / "run-config.json")["universe"]

    started = time.time()
    freeze_price_ledger(run_root=root)
    sessions = sorted(row["trade_date"] for row in _price_rows(root, "WMT"))
    cutoff = sessions[-1]
    log(f"fiyat defteri  -> {cutoff}   ({time.time()-started:.0f} sn)")

    client = SecClient(user_agent=agent)
    started = time.time()
    freeze_sec_discovery_ledger(run_root=root, client=client)
    log(f"SEC kesfi      -> tamam    ({time.time()-started:.0f} sn)")

    filed = latest_filing_dates(root, universe)
    held = held_publication_dates(root, universe)
    # Tetik takvim degil DOSYALAMA: SEC'deki en yeni rapor elimizdekinden
    # yeniyse (ya da hic islenmemisse) o sirket yeniden islenir.
    todo = [t for t in universe
            if force or t not in held or filed.get(t, "") > held[t]]

    # Ay klasoru kesim tarihiyle adlandirilir: paket ureticisi
    # months/<ad>/{cutoff,coverage}.json + reports + metric-dictionaries bekler,
    # ve her kesim kendi klasorunde kalir, eskisi silinmez.
    month = cutoff
    plan = MonthPlan(month=month, decision_date=cutoff, cutoff_date=cutoff,
                     cutoff_instant=f"{cutoff}T23:59:59Z", execution_date=cutoff)

    fresh = [t for t in todo if t in held]
    log(f"finansal: {len(todo)}/{len(universe)} sirket islenecek"
        + (f"   yeni bilanco: {', '.join(fresh)}" if fresh else ""))

    if force and todo:
        # run_company_workflow bir sirketin daha onceki ciktisi varsa erken
        # donuyor. Katalog degistiginde (yeni bir XBRL kavrami eklendiginde)
        # yeniden cikarim ancak bu izler silinirse gerceklesir.
        for ticker in todo:
            for relative in (
                Path("reports") / "valuation" / ticker / f"{cutoff}-valuation-analysis.md",
                Path("data") / "valuation-results" / ticker / cutoff,
                Path("data") / "valuation-inputs" / ticker / cutoff,
                Path("data") / "market-inputs" / ticker / cutoff,
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
    log(f"finansal+degerleme -> {month}   ({time.time()-started:.0f} sn, "
        f"{len(outcome['processed'])} sirket)")

    return {
        "run_root": root,
        "month": month,
        "cutoff_date": cutoff,
        "universe": universe,
        "reprocessed": todo,
        "skipped": outcome.get("skipped", {}),
        "status": outcome.get("status", "built"),
    }
