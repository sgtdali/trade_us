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
OUT_ROOT = REPO / "pei"

CARRY = ("earnings_estimate", "revenue_estimate", "eps_trend",
         "eps_revisions", "price_targets")

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
}


def latest_complete_month(run_root: Path) -> str:
    """Butun evrenin degerlemesi cikmis en yeni ay.

    Olcu RAPOR DEGIL degerleme sonucudur: canli akis artik rapor uretmiyor
    (paket dogrudan artifact'lerden kuruluyor) ve rapor sayan eski kural bu
    kokte hicbir ayi tam gormezdi. Donmus backtest kokleri raporlarini
    uretmeye devam ediyor ama onlarin da degerleme sonuclari yerinde.
    """
    universe = json.loads((run_root / "run-config.json").read_text())["universe"]
    months = []
    for folder in (run_root / "months").iterdir():
        marker = folder / "cutoff.json"
        if not marker.is_file():
            continue
        cutoff = json.loads(marker.read_text(encoding="utf-8"))["cutoff_date"]
        if live_refresh.month_is_complete(run_root=run_root, cutoff=cutoff,
                                          universe=universe):
            months.append((cutoff, folder.name))
    if not months:
        raise SystemExit(f"{run_root}: tam ay yok")
    # Siralama KLASOR ADIYLA degil KESIM TARIHIYLE yapilir. Kokte iki
    # adlandirma yan yana yasiyor: eskiden ay adiyla ("2026-08", kesimi
    # 31 Temmuz), simdi kesim adiyla ("2026-08-07"). Lexik sirada
    # "2026-08-07" > "2026-08" oldugu icin bugun dogru olan seciliyor ama
    # bu tesaduf: eski semadan kalma bir "2026-09" hepsini yenerdi.
    return max(months)[1]


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
    """Fiyati BUGUNE cek ve fiyat-tabanli carpanlari yeniden olcekle.

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
    try:
        data = yf.download(symbols, period="5d", progress=False,
                           auto_adjust=False, threads=True)["Close"]
        for symbol in symbols:
            column = data[symbol] if len(symbols) > 1 else data
            series = column.dropna()
            if len(series):
                quotes[symbol] = float(series.iloc[-1])
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

# BEKLEYEN islem: duyurulmus ama tamamlanmamis birlesme/devralma.
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
PENDING_DEAL_FORMS = ("425", "S-4", "DEFM14A", "PREM14A", "SC 13E3")


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
            if form.startswith(PENDING_DEAL_FORMS):
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
                role, basis = "solicited its own shareholders", "filed a merger proxy (DEFM14A/PREM14A) and no S-4"
            elif registered and not proxy:
                role, basis = "registered shares to be issued", "filed an S-4 and no merger proxy"
            else:
                role, basis = "not determinable from form mix", "filed neither form, or both"
            entry["pending_transaction"] = {
                "status": "announced; no completion filing in this window",
                "filing_count": len(deal),
                "first_filing": min(d["date"] for d in deal),
                "latest_filing": max(d["date"] for d in deal),
                "forms": forms,
                "role_in_transaction": role,
                "role_basis": basis,
                "not_in_this_pack": (
                    "Deal terms, consideration, the counterparty, the closing "
                    "timetable and the regulatory status. The pack carries only "
                    "which forms were filed, how many and when."),
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
        periodic = [d for f, d in zip(forms, dates) if f in ("10-K", "10-Q")]
        eight_k = [d for f, d in zip(forms, dates) if f == "8-K"]
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
                     "Do not recompute multiples against the consensus-block price."),
        }
        if abs(gap) >= 5:
            drifted += 1
        worst = max(worst, abs(gap))
    return drifted, worst


def peer_block(pack: dict, ticker: str, sectors: dict[str, str]) -> dict:
    """Hedefin kendi sektor emsalleri: ayni tanimla hesaplanmis carpanlar.

    Medyan da verilir ama uyarisiyla: emsal medyanina yakinsamanin bu evrende
    olculebilir bir ileri getiri bilgisi tasimadigi olculdu
    (docs/us-peer-relative-multiple-result.md).
    """
    group = sectors.get(ticker)
    if not group:
        return {"status": "unavailable", "reason": "no peer group mapped"}
    members, rows = [], {}
    for entry in pack["companies"]:
        if entry["ticker"] == ticker or sectors.get(entry["ticker"]) != group:
            continue
        members.append({
            "ticker": entry["ticker"],
            "closing_price_usd": entry.get("closing_price_usd"),
            "market_cap_usd_m": entry.get("market_cap_usd_m"),
            "valuation": entry.get("valuation"),
        })
        for key, value in (entry.get("valuation") or {}).items():
            if isinstance(value, (int, float)):
                rows.setdefault(key, []).append(value)
    medians = {k: round(statistics.median(v), 2) for k, v in rows.items() if v}
    return {
        "status": "available",
        "peer_group": group,
        "peer_group_source": "config/valuation/comparison/peer-universes",
        "peer_count": len(members),
        "medians": medians,
        "median_caveat": (
            "Convergence to a peer median is not evidence on its own. Ranking a "
            "multiple inside its sector peer group carried no measurable "
            "forward-return information across 31 cross-sections of this same "
            "universe (mean IC -0.013, 95% upper bound +0.037). If an upside "
            "case rests on peer convergence, say so explicitly and state what "
            "independent evidence supports the target multiple."
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

## Deliverable surface -- Markdown, not HTML

I am requesting Markdown as the presentation surface. Treat that as the
deliverable-intake answer and do not ask again.

No standalone HTML report, no dashboard, no `public_equity_investing_dashboard`
payload, no rendered artifact, and no headless-browser screenshot pass. Those
steps do not apply here and skipping them is not a reduction in scope.

Keep the full analytical depth the workflow calls for -- the same sections, the
same tables, the same evidence discipline -- just written as Markdown. Tables as
Markdown tables. If a chart would have carried the point, say it in a table or a
sentence instead.

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

To be clear about what is being asked: ordinary web search only. Nothing here
needs a browser to be driven, a page to be clicked through, or any
computer-control tool.

**If you have no web access, that is fine and not a reason to stop.** The pack
is self-contained. Do the analysis from it, and list what you would have checked
online as an open item.

## As-of dates -- these differ and it matters

| layer | as of |
|---|---|
| this pack was built on | {built_on} |
| financial statements | {cutoff} |
| prices / market cap, and every multiple | {execution} |
| analyst consensus | {consensus_as_of} |

Quote the correct as-of when you cite a number. Anything after these dates
belongs to the web layer, not to the pack.

**Two prices, and they disagree.** Every multiple in `valuation` comes from the
price on {execution}; the consensus block carries its own later price from
{consensus_as_of}. `price_reconciliation` shows both and the gap. {drift_line}

Quote the {execution} price beside any multiple you cite, and never mix the two
prices inside one comparison.

**Updating a multiple to the later price is exact, not an estimate.** Earnings,
book value and cash flow do not move in a few days; only the price does. So for
any price-based multiple:

    multiple_at_later_price = multiple x (consensus_block_price / multiples_computed_from)

and for a yield, divide instead of multiply. Both prices sit in
`price_reconciliation`. Do this when the later price matters to a conclusion,
show the arithmetic, and label the result with the later date. What you must not
do is rebuild a multiple from your own earnings figure.

The gap is not a defect in the numbers. The financials-to-price gap is
point-in-time discipline: decide on what was known at the cutoff, transact at
the next open. The price-to-consensus gap is a data lag on our side, and the
rescale above closes it.

## Names that reported after the cutoff -- read this before ranking

{stale_line}

For those names the financials here are not the latest ones. Some are a full
quarter behind: the pack holds Q1 while the company has already printed Q2.
Each affected company carries `announced_but_not_filed` with the filing dates
and the age of what we hold.

This one does not rescale away. Either source the newer print and label it as
web-sourced, or say plainly that the pack predates it. What you must not do is
drop a newer headline number into a ratio built from the older statements, or
rank a stale company against a current one without saying so.

## Corporate events -- three blocks, and what they are

These record facts from the SEC filing index. What they mean for a company is
yours to judge; I am not routing anything.

`special_situations` -- a completed acquisition, disposition or spin, a
restatement, or an amended 10-Q/10-K in the last two years, with dates and
8-K item numbers.

`fundamentals_comparability` -- present when such an event is dated inside the
twelve months a company's growth rates span. It names the affected `*_growth`
fields. Those fields put the current period beside a prior-year figure that
does not cover the same set of businesses, and neither period was restated
here. Single-period ratios compare nothing and are unaffected.

`pending_transaction` -- the company filed 425, S-4 or a merger proxy in the
window, and no completion filing appears. It carries the form mix, the count,
the dates, and which side of a transaction the forms place the company on: a
merger proxy solicits its own shareholders, an S-4 registers shares it would
issue, and 425 alone leaves the role unknown, which the block says. **Deal
terms, consideration, counterparty, timetable and regulatory status are not in
the pack.** Neither is the outcome; the filing count is a count.

## What is deliberately NOT in the pack

Earnings call transcripts, expert-network work, options and implied-move data,
short interest and positioning, private-company transactions, and the terms of
any M&A deal. I have no source for these. Fill them from public sources if you
can and mark them as such; where you cannot, state the limitation and carry on.

{mandate}## Task

{task}
"""

TASKS = {
    "idea": """Use idea-generation across all {n} companies in one screen.

Classify every ticker into your own bucket vocabulary -- `A - immediate research
candidate`, `B - watchlist / needs trigger`, `C - screen flag only`, `Reject` --
as research priority, not as a buy recommendation.

For each A name give Actionability, Variant Wedge, Why Now, First Rejection,
What Would Make It Investable, What Would Kill It, and Next Workflow.

End with a single table covering all {n} tickers, one row each:

| Ticker | Bucket | Setup | Variant wedge | First rejection | Next workflow |

Two companies reaching the same conclusion must still differ in their
company-specific evidence and first rejection. Repeated boilerplate rationale
is a failed run.""",

    "tearsheet": """Use company-tearsheet for {ticker}.

**Do not classify this name.** The tearsheet output contract ends at
`Recommended next step or downstream handoff`. Any add / trim / hold /
watchlist / wait-for-proof judgment belongs to earnings-preview,
long-short-pitch or thesis-tracker, not here. If you feel the need for a verdict
label, name the skill that owns it instead and stop.

What I want: the factual investor read, the core earnings-driver question, four
or five decision-useful metrics with period and source, valuation context,
concise catalysts and risks, material evidence gaps, and the next analytical
route.""",

    "preview": """Use earnings-preview for {ticker}.

State the freeze time and the expectation bar first: consensus, company guide,
the last reported baseline, and the estimate-revision path. All of those are in
the pack.

Then the 3-6 KPIs that can actually move the stock, guidance credibility, and
the EPS-quality landmines -- tax rate, share count, equity-investment marks, FX,
asset sales, impairments, restructuring, and any mismatch between GAAP EPS,
adjusted EPS and the consensus basis.

I have no options or implied-move data and no positioning or short-interest
data. Do not construct an implied-move bar from an expiry that does not isolate
the event; say the input is missing instead.

Close with the position action from your own vocabulary and with call questions
that carry a listen-for and a falsifier.""",

    "deepdive": """Use earnings-deep-dive for {ticker}.

The print is out. Compare it against what was expected, then say what the
quarter changed.

`quarterly_series` holds discrete quarters differenced from the cumulative
filings, so a growth trajectory can be read without mistaking a nine-month
figure for a quarter. Rows marked `derived` are differences, not filed numbers.

`pre_print_consensus` holds the consensus as it stood before the release, where
a snapshot predates it. Where it does not, surprise against consensus cannot be
computed for that print and must not be estimated -- say so instead.

I have no earnings-call transcript. Mark the Q&A and debate-map sections
`transcript not provided` and name the missing artifact rather than rendering an
empty table.

Run the EPS quality screen: tax, share count, equity-investment marks, FX, asset
sales, impairments, restructuring, litigation, and anything else that would make
headline EPS misstate recurring performance.

Close with what changed in the thesis, what the next falsifier is, and the
position action from your own vocabulary.""",

    "comps": """Use comps-valuation for {ticker}.

`sector_peers` in the pack holds the peer group and their multiples, all
computed with one definition, plus the peer medians. Read `median_caveat`
before you use those medians.

Answer specifically: what does the current price imply, and is the upside driven
by fundamentals, multiple expansion, mix, capital return, sentiment or event
probability? If the case rests on convergence to a peer multiple, say so
plainly and state what independent evidence supports that multiple.

Peer selection is yours -- my grouping is a starting universe, not a
conclusion. Say which peers you exclude and why.""",

    "pitch": """Use long-short-pitch for {ticker}.

Build on the earlier work in this conversation. The pack is here for the
current numbers; no new raw data is needed.

Give Actionability from your own vocabulary, the variant perception, what is
priced in, why now, the catalyst path with dates, what must be true, kill
criteria, and the add / trim / exit rules.

Every threshold must carry a number and a date. A threshold without one is not
a threshold.""",
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
    ap.add_argument("--month", default=None, help="varsayilan: en son tam ay")
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
                 "--universe", str(REPO / "config" / "universes" / "us60.json")],
                capture_output=True, text=True)
            tail = (proc.stdout or "").strip().splitlines()
            print(f"{helper:28} ({time.time()-started:.0f} sn) "
                  f"{tail[-1] if tail else 'cikti yok'}", flush=True)
        outcome = live_refresh.refresh(repo_root=REPO, force=args.force_refresh)
        source_run, month = outcome["run_root"], outcome["month"]
        if outcome["skipped"]:
            print(f"  ATLANAN: {', '.join(outcome['skipped'])}", flush=True)
        print("=== tazeleme bitti ===\n", flush=True)
    if month is None:
        month = latest_complete_month(source_run)
    print(f"kaynak: {source_run.name}/{month}   adim: {step}"
          + (f"   sirket: {ticker}" if ticker else ""))

    # Rapor AYRISTIRILMIYOR: paket dogrudan artifact'lerden kuruluyor.
    pack = build_pack_from_artifacts(run_root=source_run, month=month,
                                     guidance_root=GUIDANCE)
    # Paketin bilgi ufku. Nokta-zamanli olmayan her katman buna gore
    # kesilir ya da hic eklenmez.
    horizon = pack["cutoff_instant"][:10]
    # Paketin URETILDIGI gun; kesim (son seans) ondan farklidir.
    built_on = date.today().isoformat()
    companies, consensus_as_of, consensus_path = latest_consensus()
    # GECMISE DONUK KULLANIM KORUMASI.
    # Konsensus, olay takvimi ve tazelenmis fiyat BUGUNUN verisidir ve hicbir
    # gecmis vintage'i yoktur. Gecmis bir aya bunlari eklemek 19 aylik gelecegi
    # pakete sizdirir -- ve sessizce. Once 2025-01 paketinde tam bunun oldugu
    # goruldu: consensus_estimates 60/60 doluydu, hepsi 2026-08-09 tarihliydi.
    is_historical = consensus_as_of > horizon and (
        date.fromisoformat(consensus_as_of) - date.fromisoformat(horizon)).days > 14
    if is_historical:
        for entry in pack["companies"]:
            entry["consensus_estimates"] = {
                "status": "unavailable",
                "reason": (f"no consensus vintage exists for {horizon}; the only "
                           f"snapshot we hold is {consensus_as_of} and attaching "
                           f"it would leak the future into a historical pack"),
            }
            entry["next_events"] = {
                "status": "unavailable",
                "reason": "forward event dates cannot be reconstructed historically",
            }
        pack["historical_mode"] = {
            "cutoff": horizon,
            "layers_withheld": ["consensus_estimates", "next_events",
                                "price_refresh"],
            "why": ("These layers have no point-in-time vintage. They are "
                    "captured live and only forward. A pack built for a past "
                    "date carries them as unavailable rather than carrying "
                    "today's values under a past date."),
        }
        hit, missing = 0, list(pack["companies"] and
                               [c["ticker"] for c in pack["companies"]])
    else:
        hit, missing = attach_consensus(pack, companies, consensus_as_of)
    events_n, events_as_of = (0, None) if is_historical else attach_events(pack)
    history_n, history_last = attach_valuation_history(pack, horizon)
    pack["_financial_root"] = str(source_run / "data" / "financial")
    special_n, special_names = flag_special_situations(pack, source_run)
    roic_n, roic_skipped = attach_roic(pack, horizon)
    pack.pop("_financial_root", None)
    series_n, series_skipped = attach_quarterly_series(pack, source_run, horizon)
    prior_n, prior_as_of = attach_prior_consensus(pack, horizon)
    stale_n, stale_names = flag_superseded(pack, source_run)
    # Gecmis paket bugunun fiyatini tasiyamaz.
    priced_n, price_as_of = (0, None) if is_historical else refresh_prices(pack)
    debt_n, debt_missing = attach_net_debt(pack, source_run, horizon)
    drifted, worst = flag_price_drift(pack, consensus_as_of)
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
        stale_names = [c["ticker"] for c in here if c.get("announced_but_not_filed")]
        stale_n = len(stale_names)
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
        if peers is not None:
            pack["sector_peers"] = peers
        gap = (entry.get("price_reconciliation") or {}).get("gap_pct")
        drift_line = (f"For {ticker} the two prices differ by {gap:+.1f}%."
                      if gap is not None else
                      "No second price is available for this name.")
        scope = f"It contains one company, {ticker}, plus its sector peer group."
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

    pack["pack_purpose"] = (
        "Deterministic numeric input for the ChatGPT Public Equity Investing "
        "plugin. Numbers here replace the plugin's paid data connectors; the "
        "plugin should use the web only for narrative and for fields marked "
        "unavailable."
    )
    pack["consensus_as_of"] = consensus_as_of
    pack["intended_step"] = step
    pack["built_on"] = built_on
    pack["last_market_session"] = pack["execution_date"]

    # Adima ait olmayan bloklari SIL. Fazladan veri masum degil: okunmayi
    # bekleyen her blok dikkati boler, ve skill zaten yalniz kendi kaynak
    # kategorilerini cozmesini soyluyor.
    # Bir blok birden fazla alan yaziyorsa hepsi birlikte gider; yoksa blok
    # kapatildiginda yetim bir uyari alani geride kalir.
    COMPANIONS = {"special_situations": ("pending_transaction",
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
                      consensus_as_of=consensus_as_of,
                      drift_line=drift_line, task=task, step=step,
                      mandate=mandate_block(), stale_line=stale_line,
                      built_on=built_on),
        encoding="utf-8")

    (out / "manifest.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "built_on": built_on,
        "last_market_session": pack["execution_date"],
        "intended_step": step,
        "ticker": ticker,
        "source_month": month,
        "source_run_root": SOURCE_RUN.relative_to(REPO).as_posix(),
        "financials_as_of": pack["cutoff_instant"],
        "prices_as_of": pack["execution_date"],
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
    deal_names = [c["ticker"] for c in pack["companies"] if c.get("pending_transaction")]
    broken = [c["ticker"] for c in pack["companies"] if c.get("fundamentals_comparability")]
    if deal_names:
        print(f"  bekleyen islem {len(deal_names)}/{universe_count}   {', '.join(deal_names)}")
    if broken:
        print(f"  kirik buyume   {len(broken)}/{universe_count}   {', '.join(broken)}"
              "   (yillik karsilastirma yapisal olayi asiyor)")
    if blocks["next_events"]:
        print(f"  olay       {events_n}/{universe_count}   (as-of {events_as_of})")
    if blocks["own_valuation_history"]:
        print(f"  carpan gecmisi {history_n}/{universe_count}   (son {history_last})")
    if ticker and "sector_peers" in pack:
        print(f"  emsal      {pack['sector_peers'].get('peer_count', 0)} sirket "
              f"({pack['sector_peers'].get('peer_group')})")
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
    print(f"\nuretim gunu {built_on}   son seans {pack['execution_date']}")
    print("as-of:")
    if ticker:
        own_stale = "announced_but_not_filed" in pack["companies"][0]
        note = "   ACIKLADI AMA DOSYALAMADI" if own_stale else "   guncel"
    else:
        note = f"   ({stale_n} sirket acikladi ama dosyalamadi)" if stale_n else "   guncel"
    print(f"  finansal   {pack['cutoff_instant'][:10]}{note}")
    print(f"  fiyat      {price_as_of or pack['execution_date']}"
          + (f"   ({priced_n}/{universe_count} tazelendi)" if priced_n else " TAZELENEMEDI"))
    print(f"  konsensus  {consensus_as_of}")
    print(f"  olay       {events_as_of}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
