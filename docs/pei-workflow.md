# Public Equity Investing eklentisini sistematik calistirma

Kaynak: eklentinin kendi `SKILL.md` dosyalari okunarak cikarildi
(`~/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31`).
Tahmin yok; her madde bir dosyaya dayaniyor.

---

## 1. Okumadan cikan dort yapisal gercek

### 1a. Sonuc sozlugu ZATEN VAR -- ama skill basina, ve hepsinde degil

| skill | kapali sozluk |
|---|---|
| `idea-generation` | `A - immediate research candidate` / `B - watchlist / needs trigger` / `C - screen flag only` / `Reject` |
| `earnings-preview` | `add` / `press` / `hold` / `trim` / `exit` / `hedge` / `watchlist` / `wait for proof` |
| `long-short-pitch` | `actionable candidate` / `watchlist` / `pass for now` / `red-team only` |
| `thesis-tracker` | **uc ayri eksen**, asagida |
| `company-tearsheet` | **YOK -- kasitli** |

`company-tearsheet` acikca yaziyor: *"Do not turn a tearsheet into a
recommendation; route investment decisions to initiating coverage,
memo-builder, long-short-pitch, or thesis-tracker."* Cikti sozlesmesinin son
maddesi sadece *"Recommended next step or downstream handoff."*

**ORCL oturumunda olan sey buydu:** tearsheet'e ait olmayan bir etiket
(`wait for proof`, ki o `earnings-preview`'in sozlugu) tearsheet'e sizdi;
sorulunca model "kapali liste yok" dedi ve **yerinde 6 kategori uydurdu**,
sonra ayni sirketi yeni sozlukle yeniden sinifladi. Kanit degismedi, kelime
degisti.

**Kural: bir skill'den, sahibi olmadigi bir hukum istenmez.**

### 1b. thesis-tracker'in uc ekseni -- kaydin omurgasi burasi

```
company thesis : strengthening | intact | watch | impaired | broken |
                 changed | untested | retired
security       : ready | conditional | re-underwrite | not decision-grade
position       : add | press | hold | trim | exit | hedge |
                 wait for proof | re-underwrite
```

Uc eksen ayri tutuluyor, cunku *"better fundamentals can coexist with worse
forward risk/reward"*. Ve tracker **append-only**: *"never delete, collapse,
or rewrite prior thesis data"*. Ayrica her esigin kokeni etiketlenmek zorunda:
`Inherited threshold` / `Draft threshold for PM confirmation` /
`Approved monitoring rule`.

Yani aradigimiz kayit katmani zaten tasarlanmis. Yeniden icat etmeyecegiz.

### 1c. Veri arayuzu YAYINLANMIS

`earnings-preview/references/SCHEMAS.md` tam kolon adlariyla CSV sozlesmesi
veriyor. Bizim urettiklerimizle ortusmesi neredeyse birebir:

| eklentinin istedigi | bizde karsiligi |
|---|---|
| `reported_financials.csv` | SEC XBRL kanonik metrikler |
| `consensus_estimates.csv` | `data/consensus/snapshot-*.json` |
| `guidance_history.csv` | `us/guidance/_answers/` |
| `price_returns.csv` | fiyat defteri |
| `company_master.csv`, `fiscal_period_index.csv` | sirket configleri + donem haritasi |
| `event_calendar.csv` | `us_event_calendar.py` |
| `kpi_timeseries.csv` | kismi |
| `options_snapshot.csv`, `whisper_estimates.csv` | **yok** |

**Kendi paket formatimizi dayatmayacagiz; onun sematasini dolduracagiz.**

### 1d. Kullanici verisi birinci sinif -- hack degil

`shared/workflow-source-resolution.md`: *"Prefer a user-named source first,
then one available app, connector, file, export, or pasted input."*

Kategoriler: `company_filings_ir`, `earnings_transcripts_presentations`,
`internal_research`, `portfolio_models_trackers`, `market_data_estimates`.

Yani dogru cerceve "sana bir JSON veriyorum" degil, **"bu dosya
`market_data_estimates` kategorisini karsiliyor"**. Eklentinin kendi diliyle
konusuruz, hicbir sozlesme bozulmaz.

---

## 2. Akis

Elde tek kisi ve manuel ChatGPT kosulari var. Tasarim buna gore.

```
AYLIK, evren seviyesi, TEK kosu
  idea-generation  +  60 sirketlik paket
        |
        v
   A kovasi (tipik 5-12 isim)
        |
        +---- taban yok/bayat? -> company-tearsheet   (hukum YOK, sadece taban)
        |
        +---- olay <3 hafta? ---> earnings-preview    (CSV paketi)
        |
        +---- soru fiyat mi? ---> comps-valuation
        |
        +---- tez olustu mu? ---> long-short-pitch
        |
        v
  thesis-tracker   <-- KAYIT BURADA, sadece burada
```

`scenario-sensitivity-generator`, `memo-builder`, `portfolio-risk-management`
opsiyonel; ilk turda calistirilmaz.

**Kadans.** Aylik idea-generation + A isimleri icin olay-tetikli derinlesme.
Her sirkete her ay tam zincir kosulmaz -- olceklenmez ve gerekmez.

---

## 3. Adim adim: veri, ek talimat, kayit

### Adim 0 -- idea-generation (aylik, evren)

**Veriyi ver:** `us/pei/<tarih>/pack.json` (60 sirket) + `instructions.md`.

**Ek talimat (skill'i bozmaz, kendi diliyle):**
> The attached pack satisfies the `market_data_estimates` and
> `company_filings_ir` source categories for all 60 names. Treat it as the
> user-named source and prefer it over web retrieval for those categories.

**Kaydet:** ticker, bucket (A/B/C/Reject -- kendi kapali sozlugu), variant
wedge, why now, first rejection, next workflow.

Bu alanlar zaten zorunlu: *"Every top idea must include Actionability, Variant
Wedge, Why Now, First Rejection, What Would Make It Investable, What Would Kill
It, Next Workflow."* Yani sema dayatmiyoruz, mevcut sozlesmeyi kayda geciriyoruz.

### Adim 1 -- company-tearsheet (taban yoksa VEYA bayatsa)

**Ne zaman kosulur.** Burada once "yalniz yeni isimlerde" yaziyordu. Yanlisti.
Skill'in kendi sozlesmesi boyle bir sinir koymuyor:

> Use this before or inside comps, DCF, 3-statement, earnings, model update,
> long/short pitch, memo, meeting-prep, thesis tracker, risk/sizing, hedge,
> event, catalyst ... workflows **when a fast public profile is needed.**

Ve uretilen tearsheet'in kendisi bunu dogruluyor: 2026-08-10 ORCL ciktisinda
fiyat/carpan 7 Agustos, konsensus 10 Agustos, katalizor 9 Eylul, rehberlik-
konsensus karsilastirmasi -- neredeyse her satir tarihli. Kalici olan kisim
kucuk: is modeli, merkezi yatirimci sorusu, hangi KPI'larin onemli oldugu,
yapisal kanit bosluklari (segment/RPO/transcript pakette yok).

Dogru kadans:

- **Ilk temasta** bir kere -- taban hic yok.
- **Her bilanco baskisindan sonra**, o ismi tutuyorsan -- yeni mali donem
  tabani gecersiz kilar.
- **Asagi akista bir skill'e girmeden once** (comps, pitch), taban bayatsa.

Yani "yeni isim mi" degil, "**elimde guncel bir taban var mi**".

**Veriyi ver:** o sirketin paket kaydi -- 60'lik paketin tamami DEGIL.

**Ek talimat:**
> Do not classify this name. The tearsheet's output contract ends at
> `Recommended next step`. Any add/trim/watch/wait-for-proof judgment belongs
> to a later skill.

Bu, ORCL'de olanin tekrarini engelleyen tek satir.

**Kaydet:** sadece `next_route` + `data_gaps`. Hukum yok.

### Adim 2 -- earnings-preview (olay <3 hafta)

**Veriyi ver:** SCHEMAS.md formatinda CSV seti. Uretemediklerimiz
(`options_snapshot`, `whisper_estimates`) **bos header ile** verilir --
sema "may be empty with headers" diyor ve skill zaten
*"render a precise limitation rather than a placeholder"* istiyor.

**Ek talimat:** yok. Skill zaten freeze-time, GAAP/non-GAAP ayrimi ve
EPS-quality landmine taramasi zorunlu tutuyor.

**Kaydet:** expectation bar (metrik + esik), 3-6 stock-moving KPI,
position action (kendi sozlugunden), call-question falsifier'lari.

### Adim 3 -- comps-valuation (soru fiyatsa)

**Veriyi ver:** hedef + emsal grubu carpanlari, ayni tanimla. Emsal gruplari
`us/config/valuation/comparison/peer-universes/`.

**Ek talimat -- bizim olctugumuz seyi soyleriz:**
> Peer-median convergence is not evidence on its own. In this universe,
> ranking a multiple inside its sector peer group carried no measurable
> forward-return information over 31 cross-sections
> (`docs/us-peer-relative-multiple-result.md`). If your upside rests on
> convergence to a peer multiple, say so explicitly and state what independent
> evidence supports that multiple.

Skill zaten *"whether upside is driven by fundamentals, multiple expansion,
mix, capital return, sentiment, or event probability"* ayrimini istiyor; biz
sadece bir olcum sonucunu ekliyoruz.

**Kaydet:** implied expectation (fiyatin ima ettigi EPS/buyume), upside'in
kaynak dagilimi, hangi carpanin varsayildigi.

### Adim 4 -- long-short-pitch (tez olustuysa)

**Veriyi ver:** onceki adimlarin ciktilari. Yeni ham veri yok.

**Kaydet:** actionability (kapali sozluk), variant perception, what must be
true, kill criteria, catalyst + tarih.

### Adim 5 -- thesis-tracker (KAYIT)

**Veriyi ver:** mevcut tracker + o turun yeni kaniti.

**Ek talimat:**
> Every threshold must carry a number and a date. Label each as
> `Draft threshold for PM confirmation` unless it was inherited from a prior
> tracker row.

**Kaydet:** uc eksen (company / security / position) + pillar durumlari +
kanit satiri + changelog.

---

## 4. Kaliba sokmadan kayit tutma

Replay denemesi tam bunda patladi: bir gerekce **17 kez** tekrarlandi, butun
A adaylari tek workflow'a itildi. Ders: **sema ne kadar sikilasirsa duzyazi o
kadar kaliplasiyor.**

Cozum: **alanlari kisitla, duzyaziyi degil.**

Kapali olan sadece uc sey:

1. **hukum** -- ilgili skill'in kendi sozlugunden, serbest metin degil
2. **esik** -- sayi ve tarih tasimak zorunda
3. **olay** -- tarih

Geri kalan (tez, variant wedge, first rejection, gerekce) **tamamen serbest.**

Ve kalip kontrolu mekanik yapilir, talimatla degil: **iki sirket ayni gerekce
metnini paylasiyorsa o kosu reddedilir.** Eklentinin kendisi de bunu istiyor --
*"Two companies reaching the same conclusion must still differ in their
company-specific evidence and first rejection"* ve *"Avoid vague 'monitor'
language unless paired with exact metric, threshold, source, date, and
action."*

Yani kalip yasagi bizim icadimiz degil; sadece **denetlenebilir** hale
getiriyoruz.

---

## 5. Kayit semasi

Sirket basina, kosu basina tek satir. Yedi alan, yalniz biri kapali sozluk.

```json
{
  "ticker": "ORCL",
  "run_date": "2026-08-09",
  "skill": "idea-generation",
  "verdict": "A",
  "verdict_vocabulary": "idea-generation",
  "thesis": "<serbest, tek cumle>",
  "falsifier": {"metric": "...", "threshold": 1.72, "direction": "below",
                "by_date": "2026-09-15", "origin": "draft"},
  "next_event": {"name": "Q1 FY2027", "date": "2026-09-15",
                 "date_confirmed": false},
  "data_gaps": ["options implied move", "short interest"],
  "used_our_pack": true
}
```

`verdict_vocabulary` alani sart: ayni etiket farkli skill'lerde farkli sey
demek. `wait for proof` earnings-preview'de pozisyon aksiyonu, tearsheet'te
hicbir sey.

---

## 6. Once yapilacak uc sey

1. **Tek sirketlik paket cikaricisi.** Bugun 60'lik paket var; tearsheet ve
   preview tek isim istiyor. `us_pei_pack.py --only TICKER`.
2. **SCHEMAS.md CSV cikaricisi** earnings-preview icin. Uretemediklerimiz bos
   header.
3. **Kayit dosyasi + kalip denetleyicisi.** Yedi alan, ve ayni gerekce iki
   sirkette geciyorsa uyari.

Sirasi onemli: 1 olmadan tearsheet'e dogru veri veremiyoruz, ki ORCL
kosusunda olan da buydu -- paket verilmedi cunku 60 sirketlikti.
