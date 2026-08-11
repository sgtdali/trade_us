"""Item 2.02 (sonuc aciklamasi) 8-K'larini ve eklerini indirir.

NEDEN AYRI BIR KATMAN. Aciklama gunu ceyregin toplam oynakliginin %12,6'sini
tasiyor -- 63 seansin biri icin 8 kat yogunlasma -- ama EPS surprizi o gunun
hareketinin ancak ~%4'unu acikliyor. Kalani ayni belgede ayni anda yayinlanan
seyler: gelir, marjlar, segment detayi, yonetim yorumu ve gelecek donem
yonlendirmesi. Bu betik o belgeyi toplar.

Degerleme hattina DOKUNMAZ. `discovery.list_filings` formlari parametreyle
aliyor ama `items` sutununu tasimiyor ve Item 2.02 filtresi icin o gerekiyor;
paylasilan cekirdegi kesif amacli bir veri katmani icin degistirmek yerine
submissions okumasi burada tekrarlanir.

Nokta-zaman: her kayit `filing_date` ile saklanir, hicbir sey filtrelenmeden
atilmaz. Bir kesim tarihine gore daraltmak TUKETICININ isidir; burada
kaydedilen sey "SEC'te bu belge su tarihte vardi" olgusudur.

Yeniden calistirilabilir: indirilmis bildirimler atlanir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from adapter.discovery import resolve_cik  # noqa: E402
from adapter.sec_client import SecClient  # noqa: E402

TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
EARNINGS_ITEM = "2.02"
# Aciklamalar ARASINDA gelen bildirimler. Kalintiyi -- yani sirketin kendi
# gecmisinden cikarilamayan kismi -- uretecek haber tam olarak buradadir:
# 7.01 duzenlenmis bilgi (konferans sunumlari, on aciklamalar), 8.01 diger
# olaylar, 2.05/2.06 yeniden yapilanma ve deger dususu, 1.01/1.02 onemli
# sozlesmeler, 5.02 yonetim degisikligi.
INTERIM_ITEMS = ("7.01", "8.01", "2.05", "2.06", "1.01", "1.02", "5.02")


def submission_pages(client: SecClient, cik: str) -> list[dict]:
    """recent + spill sayfalari. 'recent' kabaca bin kayitla sinirli ve 8-K
    trafigi yogun oldugu icin eski ceyrekler o sinirin arkasina dusuyor --
    discovery.py'de ayni tuzak CHD'de yakalanmisti."""
    payload = client.get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
    pages = []
    recent = payload.get("filings", {}).get("recent")
    if isinstance(recent, dict) and recent.get("accessionNumber"):
        pages.append(recent)
    for entry in payload.get("filings", {}).get("files", []) or []:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not name:
            continue
        page = client.get_json(f"https://data.sec.gov/submissions/{name}")
        if isinstance(page, dict) and page.get("accessionNumber"):
            pages.append(page)
    return pages


def earnings_filings(pages: list[dict], *, since: str,
                     want_interim: bool = False) -> list[dict]:
    out = []
    for page in pages:
        items_col = page.get("items") or [""] * len(page["accessionNumber"])
        for index, accession in enumerate(page["accessionNumber"]):
            if page["form"][index] != "8-K":
                continue
            filing_date = page["filingDate"][index]
            if filing_date < since:
                continue
            items = items_col[index] or ""
            if EARNINGS_ITEM in items:
                kind = "earnings"
            elif want_interim and any(code in items for code in INTERIM_ITEMS):
                kind = "interim"
            else:
                continue
            out.append({
                "kind": kind,
                "accession": accession,
                "filing_date": filing_date,
                "report_date": page["reportDate"][index] or None,
                "items": items,
                "primary_document": page["primaryDocument"][index],
            })
    out.sort(key=lambda row: (row["filing_date"], row["accession"]))
    return out


def fetch_filing(client: SecClient, *, cik: str, row: dict, dest: Path) -> dict:
    """Bildirim birimi bir butun olarak inilir: ana belge tek basina yeterli
    degil, yonlendirme neredeyse her zaman EX-99 basin bulteninde."""
    naked = row["accession"].replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{naked}"
    index = json.loads(client.get_bytes(f"{base}/index.json").decode("utf-8"))
    dest.mkdir(parents=True, exist_ok=True)
    saved = []
    for item in index.get("directory", {}).get("item", []):
        name = item.get("name", "")
        low = name.lower()
        if not low.endswith((".htm", ".html")):
            continue
        # {accession}.txt tam bildirimin kendisidir ve butun ekleri tekrar
        # icerir; 60 sirket x 24 bildirimde bosuna ~1,4 GB eder. index.html ve
        # index-headers gezinme sayfalari, icerik tasimazlar.
        if low.endswith("-index.html") or low.endswith("-index.htm") \
           or "index-headers" in low:
            continue
        blob = client.get_bytes(f"{base}/{name}")
        (dest / name).write_bytes(blob)
        saved.append({"name": name, "bytes": len(blob),
                      "sha256": hashlib.sha256(blob).hexdigest()})
    record = dict(row)
    record.update({"cik": cik, "files": saved,
                   "retrieved_at": datetime.now(timezone.utc).isoformat()})
    (dest / "filing.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-root", default=None, help="evreni buradan okur")
    ap.add_argument("--universe", default=None,
                    help="config/universes/*.json -- CIK'ler dosyada, SEC'e "
                         "ticker cozumu icin ayrica gidilmez")
    ap.add_argument("--min-free-gb", type=float, default=3.0,
                    help="bu esigin altina inince temiz durur")
    ap.add_argument("--out", default=str(REPO / "guidance"))
    ap.add_argument("--since", default="2021-01-01")
    ap.add_argument("--log", required=True)
    ap.add_argument("--interim", action="store_true",
                    help="Item 2.02 disindaki ceyrek arasi bildirimleri de cek")
    args = ap.parse_args()

    user_agent = os.environ.get("SEC_USER_AGENT")
    if not user_agent:
        print("SEC_USER_AGENT gerekli", flush=True)
        return 2

    client = SecClient(user_agent=user_agent)
    known_cik: dict[str, str] = {}
    if args.universe:
        payload = json.loads(Path(args.universe).read_text(encoding="utf-8"))
        known_cik = {m["ticker"]: m["cik"] for m in payload["members"]}
        universe = sorted(known_cik)
    elif args.run_root:
        universe = sorted(json.loads(
            (Path(args.run_root) / "run-config.json").read_text())["universe"])
    else:
        print("--universe ya da --run-root gerekli", flush=True)
        return 2
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    log_path = Path(args.log)
    ticker_payload = client.get_json(TICKER_URL)

    class _Static:
        def get_json(self, url):
            if url != TICKER_URL:
                raise KeyError(url)
            return ticker_payload

    totals = {"sirket": 0, "bildirim": 0, "indirilen": 0, "atlanan": 0, "hata": 0}
    for ticker in universe:
        free_gb = shutil.disk_usage(out_root.anchor).free / (1024 ** 3)
        if free_gb < args.min_free_gb:
            # Gozetimsiz kosuda diski doldurmak makineyi etkiler; eksik kapsama
            # bildirilebilir bir sonuctur, dolu disk degildir.
            print(f"DURDU: bos disk {free_gb:.1f} GB < {args.min_free_gb} GB",
                  flush=True)
            break
        totals["sirket"] += 1
        try:
            cik = known_cik.get(ticker) or resolve_cik(_Static(), ticker)
            rows = earnings_filings(submission_pages(client, cik), since=args.since,
                                    want_interim=args.interim)
        except Exception as exc:  # noqa: BLE001 - tek sirket kosuyu durdurmamali
            totals["hata"] += 1
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{ticker} KESIF HATASI\n{traceback.format_exc()}\n")
            print(f"{ticker}: kesif hatasi {str(exc)[:120]}", flush=True)
            continue
        got = skipped = 0
        for row in rows:
            dest = out_root / ticker / row["accession"]
            if (dest / "filing.json").is_file():
                skipped += 1
                continue
            try:
                fetch_filing(client, cik=cik, row=row, dest=dest)
                got += 1
            except Exception:  # noqa: BLE001
                totals["hata"] += 1
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(f"{ticker} {row['accession']}\n{traceback.format_exc()}\n")
            time.sleep(0.25)   # rejim kosusu ayni anda SEC vuruyor; toplam hiz sinirin altinda kalsin
        totals["bildirim"] += len(rows)
        totals["indirilen"] += got
        totals["atlanan"] += skipped
        print(f"[{totals['sirket']}/{len(universe)}] {ticker}: {len(rows)} Item 2.02 "
              f"({got} indirildi, {skipped} zaten vardi)", flush=True)

    print(f"\nbitti: {totals}", flush=True)
    (out_root / "ingest-summary.json").write_text(
        json.dumps({**totals, "since": args.since,
                    "completed_at": datetime.now(timezone.utc).isoformat()}, indent=1),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
