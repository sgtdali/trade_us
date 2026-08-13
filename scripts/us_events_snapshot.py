"""Ileri olay takvimi anlik goruntusu (bilanco, temettu).

idea-generation'in 6. puanlama boyutu katalist: "timing, probability,
magnitude, path dependency, and whether priced" (workflow.md Bolum 4).
Paketimizde hicbiri yoktu; en azindan ZAMANLAMA buradan gelir.

Konsensus snapshot'iyla ayni desen: tarihli dosya, yeniden uretilemez.
Yarin bugunun "ilan edilmis bir sonraki bilanco tarihi" hicbir yerden
alinamaz -- sirket tarihi degistirse bile eski kayit oyle kalir.

DIKKAT: Yahoo bir tarihi "ilan edilmis" mi "tahmini" mi ayirt etmiyor.
Bu yuzden her satir `confirmed: null` ile yazilir ve pakette tahmini
kabul edilir. Sirketin IR sayfasindan teyit ayri bir istir.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "events"


def as_iso(value) -> str | None:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    return None


def collect(symbol: str) -> dict:
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    calendar = ticker.calendar or {}
    if not isinstance(calendar, dict):
        calendar = {}

    earnings = calendar.get("Earnings Date")
    if isinstance(earnings, (list, tuple)):
        upcoming = sorted(filter(None, (as_iso(d) for d in earnings)))
    else:
        upcoming = [d for d in [as_iso(earnings)] if d]

    # Yahoo bazen SON bilancoyu donduruyor (60 sirkette 1 kez goruldu).
    # Gecmis bir tarihi "sonraki" diye tasimak sessiz bir hata olurdu.
    first = upcoming[0] if upcoming else None
    return {
        "next_earnings_date": first,
        "is_past": (date.fromisoformat(first) < date.today()) if first else None,
        # Yahoo bir aralik verebiliyor; ikisini de tasi.
        "earnings_date_window": upcoming if len(upcoming) > 1 else None,
        "confirmed": None,
        "dividend_date": as_iso(calendar.get("Dividend Date")),
        "ex_dividend_date": as_iso(calendar.get("Ex-Dividend Date")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe",
                    default=str(REPO / "config" / "universes" / "us-live.json"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--sleep", type=float, default=0.6)
    args = ap.parse_args()

    today = date.today().isoformat()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"snapshot-{today}.json"
    existing = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
    rows: dict = existing.get("companies", {})

    members = json.loads(Path(args.universe).read_text(encoding="utf-8"))["members"]
    symbols = [m["ticker"] for m in members]
    print(f"sirket: {len(symbols)}   zaten alinmis: {len(rows)}", flush=True)

    got = failed = 0
    for index, symbol in enumerate(symbols, start=1):
        if symbol in rows:
            continue
        try:
            rows[symbol] = collect(symbol)
            got += 1
        except Exception as exc:
            rows[symbol] = {"error": str(exc)[:160]}
            failed += 1
        if index % 20 == 0:
            print(f"  [{index}/{len(symbols)}] alinan {got}, hata {failed}", flush=True)
        time.sleep(args.sleep)

    target.write_text(json.dumps({
        "snapshot_date": today,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": "yfinance / Yahoo Finance calendar",
        "note": ("Bu dosya YENIDEN URETILEMEZ. Yarin bugunun ilan edilmis "
                 "bir sonraki bilanco tarihi hicbir yerden alinamaz. "
                 "Yahoo ilan edilmis ile tahmini tarihi ayirt etmiyor; "
                 "confirmed daima null."),
        "companies": rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    dated = sum(1 for r in rows.values() if r.get("next_earnings_date"))
    print(f"\nbitti: {len(rows)} sirket -> {target.relative_to(REPO)}")
    print(f"  bilanco tarihi olan: {dated}/{len(rows)}")
    if rows:
        soon = sorted((r["next_earnings_date"], t) for t, r in rows.items()
                      if r.get("next_earnings_date"))
        print("  en yakin 5:", ", ".join(f"{t} {d}" for d, t in soon[:5]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
