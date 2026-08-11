"""Item 2.02 8-K'larini NotebookLM'e yukler ve yonlendirmeyi cikarir.

On kayit: docs/us-guidance-extraction-preregistration.md (Ek 1)

Neden CLI, neden MCP degil: 1.420 yuklemeyi konusma icinde tek tek cagirmak
pratik degil. `nlm` CLI ayni sunucuyu kullanir ve paralel surecler acilabilir.

Defter kimlikleri KALICI olarak `us/guidance/notebooks.json`'a yazilir ve her
adimda once oradan okunur -- aksi halde bir sonraki oturum ayni 1.420 belgeyi
yeniden yukler (AGENTS.md'deki kural, ayni gerekce).

Her adim yeniden calistirilabilir: var olan defter yeniden acilmaz, yuklenmis
kaynak yeniden yuklenmez.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GUIDANCE = REPO / "us" / "guidance"
LEDGER = GUIDANCE / "notebooks.json"

PROMPT = """Go through EVERY source document in this notebook, one at a time, \
and report the company's NEWLY ISSUED FULL-YEAR adjusted diluted EPS guidance.

Rules:
- FULL YEAR only. Ignore guidance given for a single quarter.
- ADJUSTED (non-GAAP) only. Ignore GAAP / reported EPS guidance.
- If the sentence is a revision reading "raises guidance FROM $x to $y TO $a to $b", \
the answer is the NEW range $a to $b, never the old one.
- If a document gives no full-year adjusted diluted EPS guidance, say NONE.

Output one line per document, this exact format, nothing else, no commentary:

YYYY-MM-DD | LOW | HIGH | LABEL

There are {count} documents. Produce {count} lines, sorted by date ascending. \
Do not skip any document."""

# Yonlendirme DUZELTILMIS bazda veriliyor, SEC artifactlarimiz GAAP. Kosu hizi
# farkini (yil-basindan-bugune gerceklesen vs yonlendirmenin ima ettigi yol)
# hesaplayabilmek icin duzeltilmis GERCEKLESEN kar da ayni bultenlerden
# cikarilir.
ACTUALS_PROMPT = """Go through EVERY source document in this notebook, one at a time, and report the ADJUSTED (non-GAAP) diluted EPS the company ACTUALLY REPORTED for the quarter this release covers.

Rules:
- REPORTED RESULT for the quarter, not guidance, not an outlook, not a forecast.
- ADJUSTED (non-GAAP) only. If only GAAP is given, say NONE.
- The quarter just ended, not year-to-date and not the full year.
- A single number, not a range.

Output one line per document, this exact format, nothing else, no commentary:

YYYY-MM-DD | EPS | PERIOD_LABEL

There are {count} documents. Produce {count} lines, sorted by date ascending. Do not skip any document."""


def load_ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.is_file() else {}


def save_ledger(ledger: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=1, sort_keys=True), encoding="utf-8")


def nlm(args: list[str], *, timeout: float = 900) -> tuple[int, str]:
    """Zaman asimi bir SONUCTUR, bir cokme degil. Ilk yazimda
    TimeoutExpired'i yakalamayinca tek bir yavas sorgu butun havuzu goturdu ve
    kalan 32 sirket hic denenmedi."""
    try:
        proc = subprocess.run(["nlm", *args], capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return 124, f"zaman asimi ({timeout:.0f}s)"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def plain_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    return re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def stage_text(ticker: str, work: Path) -> list[Path]:
    """Bildirimleri duz metne cevir. HTML desteklenmiyor; ekler ana belgeyle
    birlestirilir cunku yonlendirme genelde EX-99 basin bulteninde."""
    out = work / ticker
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for filing in sorted((GUIDANCE / ticker).glob("*/filing.json")):
        meta = json.loads(filing.read_text(encoding="utf-8"))
        target = out / f"{ticker}_{meta['filing_date']}.txt"
        if not target.is_file():
            body = "\n\n".join(plain_text(p) for p in sorted(filing.parent.glob("*.htm*")))
            target.write_text(
                f"{ticker} Form 8-K Item 2.02, filed {meta['filing_date']}\n\n{body}",
                encoding="utf-8")
        made.append(target)
    return made


def ensure_notebook(ticker: str, ledger: dict) -> str | None:
    if ticker in ledger and ledger[ticker].get("notebook_id"):
        return ledger[ticker]["notebook_id"]
    code, out = nlm(["notebook", "create", f"{ticker} - earnings 8-K guidance", "--json"])
    if code != 0:
        print(f"{ticker}: defter acilamadi -- {out[:160]}", flush=True)
        return None
    try:
        payload = json.loads(out)
        # CLI notebook_id'yi UST seviyede dondurur, MCP ise
        # notebook.id icinde; ikisi de kabul edilir.
        notebook_id = payload.get("notebook_id") or payload["notebook"]["id"]
    except Exception:
        found = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", out)
        if not found:
            print(f"{ticker}: defter kimligi okunamadi -- {out[:160]}", flush=True)
            return None
        notebook_id = found.group(0)
    ledger.setdefault(ticker, {})["notebook_id"] = notebook_id
    return notebook_id


def uploaded_titles(notebook_id: str) -> set[str]:
    code, out = nlm(["source", "list", notebook_id, "--json"])
    if code != 0:
        return set()
    try:
        payload = json.loads(out)
    except Exception:
        return set()
    rows = payload if isinstance(payload, list) else payload.get("sources", [])
    return {str(r.get("title", "")) for r in rows if isinstance(r, dict)}


def do_company(ticker: str, work: Path, ledger: dict) -> dict:
    files = stage_text(ticker, work)
    notebook_id = ensure_notebook(ticker, ledger)
    if not notebook_id:
        return {"ticker": ticker, "state": "no_notebook"}
    have = uploaded_titles(notebook_id)
    added = failed = 0
    for path in files:
        if path.name in have:
            continue
        code, out = nlm(["source", "add", notebook_id, "-f", str(path), "--wait", "--json"])
        if code == 0:
            added += 1
        else:
            failed += 1
            print(f"  {ticker} {path.name}: {out[:120]}", flush=True)
        time.sleep(0.3)
    record = ledger.setdefault(ticker, {})
    record.update({"notebook_id": notebook_id, "sources": len(files),
                   "added_last_run": added, "failed": failed})
    print(f"{ticker}: {len(files)} belge  (+{added} yuklendi, {len(have)} zaten vardi, "
          f"{failed} hata)", flush=True)
    return {"ticker": ticker, "state": "ok", "files": len(files)}


def do_query(ticker: str, ledger: dict, out_dir: Path, kind: str = "guidance") -> None:
    record = ledger.get(ticker) or {}
    notebook_id = record.get("notebook_id")
    if not notebook_id:
        return
    target = out_dir / f"{ticker}.txt"
    if target.is_file() and target.stat().st_size > 20:
        return
    count = record.get("sources") or len(list((GUIDANCE / ticker).glob("*/filing.json")))
    template = PROMPT if kind == "guidance" else ACTUALS_PROMPT
    code, out = nlm(["notebook", "query", notebook_id, template.format(count=count),
                     "--json", "--timeout", "420"], timeout=900)
    if code != 0:
        print(f"{ticker}: sorgu hatasi {out[:160]}", flush=True)
        return
    try:
        answer = json.loads(out).get("answer", "")
    except Exception:
        answer = out
    target.write_text(answer, encoding="utf-8")
    lines = [ln for ln in answer.splitlines() if "|" in ln]
    print(f"{ticker}: {len(lines)}/{count} satir", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("upload", "query", "both"), default="both")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--work", default=None, help="duz metin calisma klasoru")
    ap.add_argument("--answers", default=None)
    ap.add_argument("--only", default=None, help="virgulle ayrilmis ticker listesi")
    ap.add_argument("--kind", choices=("guidance", "actuals"), default="guidance")
    args = ap.parse_args()

    work = Path(args.work) if args.work else GUIDANCE / "_text"
    default_answers = "_answers" if args.kind == "guidance" else "_actuals"
    answers = Path(args.answers) if args.answers else GUIDANCE / default_answers
    work.mkdir(parents=True, exist_ok=True)
    answers.mkdir(parents=True, exist_ok=True)

    tickers = sorted(d.name for d in GUIDANCE.iterdir()
                     if d.is_dir() and not d.name.startswith("_"))
    if args.only:
        wanted = {t.strip().upper() for t in args.only.split(",")}
        tickers = [t for t in tickers if t in wanted]
    print(f"sirket: {len(tickers)}   worker: {args.workers}", flush=True)

    ledger = load_ledger()
    if args.stage in ("upload", "both"):
        # Defterler ONCE seri acilir: paralel acilis ayni ticker icin iki defter
        # yaratabilir ve ledger'in tek dogru kaynagi olma ozelligi bozulur.
        for ticker in tickers:
            ensure_notebook(ticker, ledger)
        save_ledger(ledger)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(lambda t: do_company(t, work, ledger), tickers))
        save_ledger(ledger)

    if args.stage in ("query", "both"):
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(lambda t: do_query(t, ledger, answers, args.kind), tickers))

    save_ledger(ledger)
    print(f"\nledger: {LEDGER}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
