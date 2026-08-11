"""Item 2.02 8-K'larindan EPS yonlendirmesini cikarir.

Cumle seviyesinde calisir: bir cumle hem YONLENDIRME fiili (expect/guidance/
outlook/anticipate/forecast/see) hem de EPS terimi tasiyorsa, icindeki dolar
degerleri aday olur. Aralik varsa aralik, tek deger varsa nokta tahmini.

Kasitli olarak muhafazakar: emin olunmayan cikarilmaz. Kapsama orani sonucun
bir parcasidir, doldurulacak bir eksik degil."""
import pathlib, re, html, json, statistics, collections

R = pathlib.Path("us/guidance")
MONEY = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)")
RANGE = re.compile(r"\$\s?(\d+\.\d{2})\s*(?:to|-|–|—|and)\s*\$?\s?(\d+\.\d{2})")
EPS = re.compile(r"(?i)\b(eps|earnings per share|earnings per diluted share|"
                 r"income per share|per diluted share)\b")
FWD = re.compile(r"(?i)\b(guidance|outlook|expects?|expecting|anticipates?|"
                 r"forecasts?|projects?|sees|targeting|raises?|lowers?|reaffirms?)\b")
# Gecmise donuk cumleleri disla: "EPS was $1.20" / "compared to $1.10"
PAST = re.compile(r"(?i)\b(was|were|compared (?:to|with)|versus|prior year|"
                  r"last year|reported (?:eps|earnings)|in the quarter ended)\b")

def text(p):
    s = p.read_text(encoding="utf-8", errors="ignore")
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s)))

def sentences(t):
    return re.split(r"(?<=[.;])\s+(?=[A-Z(])", t)

def extract(filing_dir):
    best = None
    for p in sorted(filing_dir.glob("*.htm*")):
        for s in sentences(text(p)):
            if len(s) > 700 or not EPS.search(s) or not FWD.search(s):
                continue
            if PAST.search(s):
                continue
            # Revizyonlar "from ESKI to ESKI to YENI to YENI" kalibiyla
            # yazilir; ILK eslesme her zaman bir onceki ceyregin
            # yonlendirmesidir. Sondan alinir -- aksi halde bayat bilgi
            # sinyal sanilir.
            found = [(float(a), float(b)) for a, b in RANGE.findall(s)
                     if float(b) >= float(a) and float(b) < 100]
            if found:
                lo, hi = found[-1]
                if True:
                    cand = {"low": lo, "high": hi, "point": (lo+hi)/2,
                            "kind": "range", "revision": len(found) > 1,
                            "sentence": s[:300]}
                    if best is None or best["kind"] != "range":
                        best = cand
                    continue
            if best is None:
                vals = [float(v.replace(",", "")) for v in MONEY.findall(s)]
                vals = [v for v in vals if 0.05 <= v < 100]
                if len(vals) == 1:
                    best = {"low": vals[0], "high": vals[0], "point": vals[0],
                            "kind": "point", "sentence": s[:300]}
    return best

rows = []
for f in sorted(R.glob("*/*/filing.json")):
    meta = json.loads(f.read_text())
    g = extract(f.parent)
    rows.append({"ticker": f.parent.parent.name, "filing_date": meta["filing_date"],
                 "accession": meta["accession"], "guidance": g})
out = pathlib.Path(__file__).parent / "guidance-ledger.json"
out.write_text(json.dumps(rows, indent=1), encoding="utf-8")

got = [r for r in rows if r["guidance"]]
kinds = collections.Counter(r["guidance"]["kind"] for r in got)
per = collections.Counter(r["ticker"] for r in got)
print(f"bildirim          : {len(rows)}")
print(f"yonlendirme cikti : {len(got)}  (%{len(got)/len(rows)*100:.1f})")
print(f"  aralik / nokta  : {kinds['range']} / {kinds['point']}")
print(f"hic cikmayan sirket: {60-len(per)}")
print(f"sirket basina medyan: {statistics.median(per.values()):.0f}/~24")
print("\nornekler:")
for r in got[:4]:
    g = r["guidance"]
    print(f"  {r['ticker']:5} {r['filing_date']}  {g['low']}-{g['high']} ({g['kind']})")
    print(f"        \"{g['sentence'][:150]}...\"")
