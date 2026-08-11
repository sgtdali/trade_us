"""Analist konsensusu, dagilimi ve 90 gunluk revizyon izi -- tarihli snapshot.

NEDEN BU DOSYA VAR. Konsensusun gecmis VINTAGE'i (30/60/90 gun once ne
soyleniyordu) ucretsiz saglayicilarda yok diye yazmistim; yanlisti.
`eps_trend` 90 gunluk izi veriyor. Uzun tarihsel panel hâlâ kurulamaz -- 90
gunden geriye gitmiyor -- ama iki sey mumkun:

  1. BUGUN her sirket icin 90 gunluk revizyon momentumu hesaplanabilir.
  2. BUGUNDEN ITIBAREN haftalik snapshot alinirsa gercek vintage paneli birikir.

Ikincisi ancak baslarsak birikir. Snapshot'lar repoya girer cunku yeniden
uretilemezler: yarin bugunun konsensusunu hicbir yerden alamayiz.

Her snapshot tarihiyle adlandirilir ve degistirilmez.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "consensus"


def frame_to_rows(frame) -> dict:
    """pandas DataFrame -> {period: {sutun: deger}}, NaN'lar atilir."""
    if frame is None or not hasattr(frame, "iterrows"):
        return {}
    out = {}
    for period, row in frame.iterrows():
        clean = {}
        for key, value in row.items():
            if value is None:
                continue
            try:
                if value != value:          # NaN
                    continue
            except Exception:
                pass
            clean[str(key)] = value.item() if hasattr(value, "item") else value
        if clean:
            out[str(period)] = clean
    return out


def collect(symbol: str) -> dict | None:
    import yfinance as yf
    ticker = yf.Ticker(symbol)
    payload: dict = {}
    for name, attr in (("earnings_estimate", "earnings_estimate"),
                       ("revenue_estimate", "revenue_estimate"),
                       ("eps_trend", "eps_trend"),
                       ("eps_revisions", "eps_revisions"),
                       ("growth_estimates", "growth_estimates")):
        try:
            payload[name] = frame_to_rows(getattr(ticker, attr))
        except Exception:
            payload[name] = {}
    try:
        payload["price_targets"] = getattr(ticker, "analyst_price_targets", None) or {}
    except Exception:
        payload["price_targets"] = {}
    if not payload.get("earnings_estimate") and not payload.get("eps_trend"):
        return None
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe",
                    default=str(REPO / "us" / "config" / "universes" / "sp500.json"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--sleep", type=float, default=0.6)
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    today = date.today().isoformat()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"snapshot-{today}.json"
    existing = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
    rows: dict = existing.get("companies", {})

    members = json.loads(Path(args.universe).read_text(encoding="utf-8"))["members"]
    symbols = [m["ticker"] for m in members]
    if args.only:
        wanted = {t.strip().upper() for t in args.only.split(",")}
        symbols = [s for s in symbols if s in wanted]

    print(f"sirket: {len(symbols)}   zaten alinmis: {len(rows)}", flush=True)
    got = failed = 0
    for index, symbol in enumerate(symbols, start=1):
        if symbol in rows:
            continue
        try:
            payload = collect(symbol)
        except Exception as exc:  # noqa: BLE001 - tek sirket kosuyu durdurmamali
            payload = None
            if index % 25 == 0:
                print(f"  {symbol}: {type(exc).__name__}", flush=True)
        if payload:
            rows[symbol] = payload
            got += 1
        else:
            failed += 1
        if index % 25 == 0:
            target.write_text(json.dumps(
                {"snapshot_date": today,
                 "captured_at": datetime.now(timezone.utc).isoformat(),
                 "source": "yfinance / Yahoo Finance analyst estimates",
                 "note": ("Bu dosya YENIDEN URETILEMEZ. Yarin bugunun konsensusu "
                          "hicbir yerden alinamaz; vintage paneli ancak boyle birikir."),
                 "companies": rows}, ensure_ascii=False), encoding="utf-8")
            print(f"  [{index}/{len(symbols)}] alinan {got}, bos {failed}", flush=True)
        time.sleep(args.sleep)

    target.write_text(json.dumps(
        {"snapshot_date": today,
         "captured_at": datetime.now(timezone.utc).isoformat(),
         "source": "yfinance / Yahoo Finance analyst estimates",
         "note": ("Bu dosya YENIDEN URETILEMEZ. Yarin bugunun konsensusu hicbir "
                  "yerden alinamaz; vintage paneli ancak boyle birikir."),
         "companies": rows}, ensure_ascii=False), encoding="utf-8")
    print(f"\nbitti: {len(rows)} sirket -> {target}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
