"""Asama 1: kazanc bulteninden KPI ADAYI hasadi. LLM YOK.

Ilke: METIN NE DIYORSA ONU KAYDET, YORUMLAMA.
Bu asama bir sayinin ne oldugunu soylemez; yalniz nerede gectigini, hangi
cumlede gectigini ve alintinin kaynakta gercekten bulundugunu kanitlar.
Adlandirma asama 2'nin isi ve orada model SAYIYA DOKUNMAZ.

Iki mekanik dogrulama (ikisi de gecmezse satir `verified: false`):
  V1  sayi, alintida harfiyen geciyor
  V2  alinti, normalize edilmis kaynak metinde harfiyen geciyor

Normalizasyon yalniz metin acikca soylediginde yapilir: "$5.8 billion" ->
5800 (milyon USD). Olcek kelimesi yoksa `value_musd` bos birakilir --
"$1.45"i milyon saymak sessiz bir hata olurdu (EPS'dir).

Cikti: us/pei/kpi/<TICKER>/candidates.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEXT_ROOT = REPO / "guidance" / "_text"
OUT_ROOT = REPO / "pei" / "kpi"

SCALE = {"trillion": 1_000_000.0, "billion": 1_000.0, "million": 1.0}

# "$5.8 billion, up 93%" / "$1.45" / "$638 billion"
MONEY = re.compile(
    r"\$\s?(?P<value>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<scale>trillion|billion|million)?"
    r"(?P<move>\s*,?\s*(?:up|down|increased|decreased|grew|rose|fell)\s+"
    r"(?P<pct>\d+(?:\.\d+)?)\s*%)?",
    re.I)

# "NRR was 102%" / "margin of 44%" -- parasiz oranlar
PERCENT = re.compile(
    r"(?<![\d.$])(?P<value>\d{1,3}(?:\.\d+)?)\s*%", re.I)

# "from $553 billion to $638 billion" -- kopru, dogrulanabilir kimlik
BRIDGE = re.compile(
    r"from\s+\$\s?(?P<a>\d[\d,]*(?:\.\d+)?)\s*(?P<sa>trillion|billion|million)?"
    r"\s+to\s+\$\s?(?P<b>\d[\d,]*(?:\.\d+)?)\s*(?P<sb>trillion|billion|million)?",
    re.I)

PERIOD = re.compile(r"\b(Q[1-4]|FY\s?\d{2,4}|first|second|third|fourth)\b", re.I)


def plain(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def quote_around(text: str, start: int, end: int, before: int = 130,
                 after: int = 90) -> tuple[str, int, int]:
    left = max(0, start - before)
    right = min(len(text), end + after)
    return text[left:right], left, right


def harvest(text: str, source_id: str, limit: int) -> list[dict]:
    rows: list[dict] = []

    def add(kind: str, start: int, end: int, payload: dict) -> None:
        quote, left, right = quote_around(text, start, end)
        literal = text[start:end]
        payload.update({
            "kind": kind,
            "source_id": source_id,
            "matched_text": literal,
            "quote": quote,
            "char_start": start,
            "char_end": end,
            # V1 / V2 -- ikisi de mekanik, yoruma acik degil
            "v1_number_in_quote": literal in quote,
            "v2_quote_in_source": quote in text,
        })
        payload["verified"] = payload["v1_number_in_quote"] and payload["v2_quote_in_source"]
        window = text[max(0, start - 160):end]
        hits = PERIOD.findall(window)
        payload["period_hint"] = hits[-1].upper().replace(" ", "") if hits else None
        # Katman: asama 2'ye kac aday gidecegini bu belirler. Bulten basligi
        # "<etiket> $X billion, up Y%" kalibini kullanir ve dosya basina ~8
        # aday verir; ciplak yuzdeler cogunlukla dipnot gurultusudur.
        if kind == "bridge":
            payload["tier"] = "bridge"
        elif kind == "money" and payload.get("scale_word") and payload.get("move_pct") is not None:
            payload["tier"] = "headline"
        elif kind == "money" and payload.get("scale_word"):
            payload["tier"] = "money"
        else:
            payload["tier"] = "weak"
        rows.append(payload)

    for m in MONEY.finditer(text):
        if len(rows) >= limit:
            break
        scale = (m.group("scale") or "").lower()
        value = float(m.group("value").replace(",", ""))
        add("money", m.start(), m.end(), {
            "value_raw": m.group("value"),
            "scale_word": scale or None,
            # Olcek kelimesi yoksa NORMALIZE ETME -- yorum olurdu.
            "value_musd": round(value * SCALE[scale], 4) if scale else None,
            "move_pct": float(m.group("pct")) if m.group("pct") else None,
            "move_direction": (re.search(r"up|increased|grew|rose|down|decreased|fell",
                                         m.group("move"), re.I).group(0).lower()
                               if m.group("move") else None),
        })

    for m in PERCENT.finditer(text):
        if len(rows) >= limit:
            break
        # Para eslesmesinin icindeki yuzdeler zaten move_pct olarak alindi.
        if any(r["kind"] == "money" and r["char_start"] <= m.start() < r["char_end"]
               for r in rows):
            continue
        add("percent", m.start(), m.end(), {
            "value_raw": m.group("value"),
            "scale_word": "percent",
            "value_musd": None,
            "move_pct": None,
            "move_direction": None,
        })

    for m in BRIDGE.finditer(text):
        def norm(value: str, scale: str | None) -> float | None:
            scale = (scale or "").lower()
            return round(float(value.replace(",", "")) * SCALE[scale], 4) if scale else None

        add("bridge", m.start(), m.end(), {
            "value_raw": m.group("b"),
            "scale_word": (m.group("sb") or "").lower() or None,
            "value_musd": norm(m.group("b"), m.group("sb")),
            "bridge_from_musd": norm(m.group("a"), m.group("sa")),
            "move_pct": None,
            "move_direction": None,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe",
                    default=str(REPO / "config" / "universes" / "us60.json"))
    ap.add_argument("--only", default=None, help="tek ticker")
    ap.add_argument("--limit", type=int, default=400, help="dosya basina aday tavani")
    ap.add_argument("--head", type=int, default=14000,
                    help="dosyanin ilk N karakteri (baslik blogu); 0 = tamami")
    args = ap.parse_args()

    if args.only:
        tickers = [args.only.strip().upper()]
    else:
        members = json.loads(Path(args.universe).read_text(encoding="utf-8"))["members"]
        tickers = [m["ticker"] for m in members]

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    totals = {"files": 0, "candidates": 0, "verified": 0, "normalized": 0}
    tiers = {"headline": 0, "money": 0, "bridge": 0, "weak": 0}
    empty: list[str] = []
    per_file_headline: list[int] = []

    for ticker in tickers:
        folder = TEXT_ROOT / ticker
        if not folder.is_dir():
            empty.append(f"{ticker}: metin klasoru yok")
            continue
        rows: list[dict] = []
        for path in sorted(folder.glob("*.txt")):
            text = plain(path)
            if args.head:
                text = text[:args.head]
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            found = harvest(text, path.stem, args.limit)
            for row in found:
                row["ticker"] = ticker
                row["source_file"] = path.relative_to(REPO).as_posix()
                row["source_sha256"] = digest
            rows += found
            totals["files"] += 1
            per_file_headline.append(sum(1 for r in found if r["tier"] == "headline"))
        if not rows:
            empty.append(f"{ticker}: aday cikmadi")
            continue
        out = OUT_ROOT / ticker
        out.mkdir(parents=True, exist_ok=True)
        with (out / "candidates.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        totals["candidates"] += len(rows)
        totals["verified"] += sum(1 for r in rows if r["verified"])
        totals["normalized"] += sum(1 for r in rows if r.get("value_musd") is not None)
        for tier in tiers:
            tiers[tier] += sum(1 for r in rows if r["tier"] == tier)

    print(f"sirket {len(tickers)}   dosya {totals['files']}")
    print(f"aday   {totals['candidates']:,}")
    print(f"  dogrulanan (V1+V2)  {totals['verified']:,} "
          f"({100*totals['verified']/max(1,totals['candidates']):.1f}%)")
    print(f"  olcegi acik yazili  {totals['normalized']:,}")
    print("\nkatman:")
    print(f"  headline  {tiers['headline']:,}   <- asama 2 bunu tuketir")
    print(f"  money     {tiers['money']:,}")
    print(f"  bridge    {tiers['bridge']:,}   <- kopru ozdesligi dogrulanabilir")
    print(f"  weak      {tiers['weak']:,}   (cogunlukla dipnot gurultusu)")
    if per_file_headline:
        ordered = sorted(per_file_headline)
        mid = ordered[len(ordered) // 2]
        print(f"\ndosya basina headline: medyan {mid}, "
              f"min {ordered[0]}, maks {ordered[-1]}, "
              f"sifir olan {sum(1 for n in ordered if n == 0)} dosya")
    if empty:
        print(f"\nbos ({len(empty)}):")
        for line in empty[:10]:
            print("   ", line)
    print(f"\ncikti: {OUT_ROOT.relative_to(REPO)}/<TICKER>/candidates.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
