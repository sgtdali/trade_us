# PEI workflow orchestrator tasarimi

Durum: Onaylanmis tasarim  
Tarih: 2026-08-12

## 1. Amac

PEI arastirma akisini sohbet hafizasindan bagimsiz hale getirmek. Baska bir
Codex oturumu yalnizca repoyu okuyarak su sorulari cevaplayabilmelidir:

- Hangi idea-generation kosulari yapildi?
- Her sirket neden mevcut asamada?
- Siradaki is nedir, neden ve nasil calistirilir?
- Bir aday neyi bekliyor?
- Beklenen kosul olustu mu ve ne zaman yeniden kontrol edilecek?
- Bir sirket ne zaman arastirma adayindan onayli teze gecti?

Serbest ChatGPT yorumu standartlastirilmaz. Standart olan, yorumdan sonra
uretilen workflow olaylarinin anatomisi, kaynaklari ve durum gecisleridir.

## 2. Anlayis ozeti

- Her kosu kimlikli, tarihli ve kaynak hash'leriyle kalici olmali.
- Ham model cevabi degistirilmeden korunmali.
- Idea screen ile thesis tracker arasinda ayri bir arastirma kuyrugu olmali.
- Workflow durumu sohbetten degil append-only olaylardan turetilmeli.
- Modelin `next workflow` onerisi yalniz desteklenen kataloga eslesirse
  yurutulebilir olmali.
- B adaylari izlenebilir tetikleyici veya tarihli manuel inceleme olmadan
  beklemeye alinamamali.
- Yeni bir oturum tek komutla guncel durumu ve siradaki kesin isi gorebilmeli.

## 3. Varsayimlar ve kapsam disi

Varsayimlar:

- Tek kullanici, yerel repo ve yaklasik 87 sirketlik canli evren.
- Aylik idea-generation, haftalik kontrol ve olay-tetikli inceleme.
- Sistem kullanici komutuyla calisir; surekli arka plan servisi yoktur.
- Mevcut pack ureticisi sayisal kaynak katmani olmaya devam eder.
- Semantik cikarma idea-generation ekrani icin `agy` (Gemini CLI, sema-zorlamali
  `--json-schema`) ile otomatik yapilir (bkz. 2026-08-13 karar gunlugu);
  diger workflow sonuclari (tearsheet/pitch/comps) icin hala Codex elle yapar.
  Ikisinde de repo araci kendi basina API anahtari tutmaz, yalniz yerel CLI
  cagirir.
- Gecersiz veya belirsiz durumlarda sistem fail-closed davranir.

Kapsam disi:

- UI, Excel, veritabani veya daemon.
- Otomatik alim-satim veya portfoy emri.
- Ham model metnini tek tip rapor kalibina zorlama.
- Desteklenmeyen workflow'lari serbest metinden tahmin ederek calistirma.

## 4. Mimari

### 4.1 Degismez kosu artefaktlari

Gercek uygulanan yol (bkz. [repo-map.md](repo-map.md)):

```text
data/pei-workflow/runs/<run_id>/work/<work_item_id>/<tarih>/<ticker>/<adim>/
  pack.json
  instructions.md
  result.md
  manifest.json
```

`pei/<tarih>/<ticker>/<adim>/` eski, elle kosulan donemin (2026-08-12'ye
kadar) klasor sekli; dondu, yeni yazma yok. Ikisi de git'e tracked.

Bu dosyalar bir kosunun kanitidir. Bir yorum daha sonra hatali bulunursa
`result.md` degistirilmez; duzeltme yeni bir workflow olayi olarak eklenir.

### 4.2 Append-only olay gunlugu

```text
data/pei-workflow/events.jsonl
```

Her satir tek, semaya uygun bir olaydir. Olay gunlugu otoritatiftir. Guncel
arastirma kuyrugu bu gunlukten tekrar uretilebilir; ayri bir cache varsa
otoritatif sayilmaz.

Baslangic olay sozlugu:

```text
idea_run_started
screen_run_recorded
candidate_screened
workflow_requested
workflow_prepared
workflow_completed
waiting_for_trigger
trigger_satisfied
manual_review_required
candidate_deprioritized
source_interpretation_corrected
thesis_opened
```

### 4.3 Workflow katalogu

```text
config/pei-workflows.json
```

Baslangicta desteklenen workflow kimlikleri:

```text
tearsheet
earnings_preview
earnings_deep_dive
comps
pitch
thesis_tracker
```

Her katalog kaydi sunlari tanimlar:

- gerekli onceki asamalar;
- gerekli kaynak artefaktlari;
- pack uretim komutu;
- tamamlanma kosulu;
- izin verilen sonraki rotalar;
- sonuc sahibinin kapali hukum sozlugu, varsa.

Katalogda olmayan bir model onerisi calistirilmaz. Olay
`manual_review_required` olur.

### 4.4 Tek CLI

```text
scripts/us_pei_workflow.py
```

Komut yuzeyi:

```bash
python scripts/us_pei_workflow.py start-idea --tickers AAPL,...
python scripts/us_pei_workflow.py attach-result --run-id <ID> --file <PATH>
python scripts/us_pei_workflow.py validate --draft <PATH>
python scripts/us_pei_workflow.py approve --draft <PATH>
python scripts/us_pei_workflow.py status
python scripts/us_pei_workflow.py next
python scripts/us_pei_workflow.py prepare <WORK_ITEM_ID>
python scripts/us_pei_workflow.py check-triggers --refresh
```

## 5. Olay sozlesmesi

Butun olaylar su ortak alanlari tasir:

```json
{
  "schema_version": 1,
  "event_id": "EVT-20260812-...",
  "event_type": "candidate_screened",
  "recorded_at": "2026-08-12T16:00:00+03:00",
  "run_id": "IDEA-20260812-shortlist",
  "ticker": "META",
  "source_artifacts": [
    {"path": "pei/.../result.md", "sha256": "...", "role": "result"}
  ],
  "payload": {}
}
```

`event_id`, `run_id` ve sonuc hash'leri idempotency kontrolune tabidir.

Idea-generation aday payload'i:

```json
{
  "bucket": "B",
  "setup": "serbest metin",
  "variant_wedge": "serbest metin",
  "first_rejection": "serbest metin",
  "suggested_workflow": "scenario-sensitivity-generator",
  "mapped_workflow": null,
  "route_status": "unsupported"
}
```

Modelin serbest onerisi ile sistemin yurutulebilir rotasi ayri alanlardir.

## 6. Turetilmis aday durumu

Durumlar:

```text
screened
ready
in_progress
waiting
blocked
completed
deprioritized
thesis_opened
```

Varsayilan bucket politikasi:

- `A`: Desteklenen rota varsa `ready`; yoksa `manual_review_required`.
- `B`: Makinece izlenebilir tetikleyici veya tarihli manuel inceleme gerekir.
- `C`: Sonraki idea-generation kosusuna kadar `deprioritized`; acik veri sorunu
  varsa `blocked`.
- `Reject`: Yeni bir screen olayi degistirene kadar kapali.

Yeni idea-generation kosusu eski sonucu silmez. Adayin guncel bucket'i en son
onayli screen olayindan, gecmisi ise onceki olaylardan okunur.

## 7. Tetikleyici modeli

Desteklenen tetikleyici tipleri:

```text
date_due
event_window
new_filing
metric_condition
```

Ornek:

```json
{
  "trigger_id": "META-20260812-CAPEX-REVIEW",
  "type": "metric_condition",
  "metric_path": "/companies/META/...",
  "operator": ">=",
  "value": 10,
  "unit": "pct",
  "check_cadence": "weekly",
  "next_check_date": "2026-08-19",
  "on_match": "request_workflow",
  "workflow": "comps",
  "source_artifact": "pei/.../result.md"
}
```

Her tetikleyici sunlari tasimak zorundadir:

- izlenecek metrik, olay veya tarih;
- operator ve deger, uygulanabiliyorsa;
- kontrol sikligi ve sonraki kontrol tarihi;
- eslesme halinde aksiyon;
- kaynak;
- tarih durumu: `confirmed`, `estimated` veya `analyst_deadline`.

Model kesin bir esik vermediyse sistem esik uydurmaz. Aday, belirli bir
`next_review_date` tasiyan `manual_review_required` olayina gider.

## 8. Operasyon akisi

### 8.1 Idea kosusu

`start-idea` yeni `run_id` olusturur, guncel idea pack'ini uretir ve
`idea_run_started` yazar. Durum `waiting_for_result` olur.

`attach-result` ham cevabi kosu klasorune alir ve hash'ler. Codex, sonuc ile
olay semasindan bir taslak cikarir. `validate` sema, kaynak, hash, gecis ve
tetikleyici kontrollerini yapar. `approve` onayli olaylari atomik olarak
gunluge ekler.

### 8.2 Siradaki is

`next`, olaylardan guncel kuyrugu turetir ve her is icin sunlari verir:

- siralama;
- ticker ve workflow kimligi;
- neden simdi;
- kaynak screen/run;
- kesin `prepare` komutu;
- varsa blocker veya beklenen tetikleyici.

`prepare`, katalogdaki komutu calistirir ve `workflow_prepared` olayi yazar.
Sohbet gecmisinden onceki calismayi bulmaya calismaz.

### 8.3 Sonuc tamamlama

Her workflow sonucu tekrar `attach-result`, taslak, `validate` ve `approve`
adimlarindan gecer. Sonuc sahibine gore kayit degisir:

- tearsheet: veri bosluklari ve onerilen rota; hukum yok;
- earnings preview/deep dive: beklenti/tetikleyici ve izinli aksiyon;
- comps: degerleme varsayimlari ve karar engelleri;
- pitch: pitch hukmu, tez ve kill/entry kurallari;
- thesis tracker: onayli tezin append-only izleme kaydi.

### 8.4 Kadans

```bash
# Haftalik veya ihtiyac halinde
python scripts/us_pei_workflow.py check-triggers --refresh

# Aylik
python scripts/us_pei_workflow.py start-idea --tickers ...

# Her zaman
python scripts/us_pei_workflow.py status
python scripts/us_pei_workflow.py next
```

Arka plan servisi olmadigi icin tetikleyiciler yalniz komut calistirildiginda
degerlendirilir. `status` son kontrol zamanini acikca gostermelidir.

## 9. Dogrulama ve hata davranisi

- Her olay JSON Schema'dan gecmelidir.
- Kaynak yolu repo icinde bulunmali ve SHA-256 eslesmelidir.
- Ayni olay, `run_id` veya sonuc hash'i kurala aykiri bicimde tekrarlanamaz.
- Durum gecisi katalogda izinli olmalidir.
- B adayi tetikleyicisiz veya tarihli manuel incelemesiz kalamaz.
- Bulunamayan `metric_path` tetiklenmis sayilmaz.
- Tahmini tarih dogrulanmis gibi kullanilmaz.
- Katalogda olmayan workflow fail-closed durur.
- Ham model cevabi otomatik yatirim karari sayilmaz.
- Append atomik yapilir; yarim yazma olay gunlugunu bozamaz.

## 10. Mevcut verinin tasinmasi

- 2026-08-12 shortlist idea kosusu `legacy_import` baglamiyla kaydedilir.
- Ham result degistirilmez; A/B/C aday olaylari ayri taslakta cikarilir.
- Orchestrator disinda uretilmis NVDA preview pack'i hash kontrolunden sonra
  ilgili work item'a baglanir.
- AAPL ve VZ'nin mevcut thesis tracker satirlari korunur ve arastirma
  kuyruguna `thesis_opened` olaylariyla baglanir.
- CRM'nin yeni bir donemsel filing varmis gibi yorumlanmasi ham metinden
  silinmez; `source_interpretation_corrected` olayi eklenir.
- GOOGL icin katalogda olmayan normalizasyon onerisi, uygun workflow
  tanimlanana kadar `manual_review_required` kalir.

## 11. Test ve kalite hedefleri

- 87 sirket icin `status` ve `next` birkac saniyenin altinda tamamlanmali.
- Ayni olay gunlugu her kosuda ayni guncel durumu uretmeli.
- Ayni cevap ikinci kez eklenmemeli.
- Yarım append ve bozuk son satir guvenli bicimde ele alinmali.
- `date_due`, `event_window`, `new_filing` ve `metric_condition` ayri test
  edilmelidir.
- Bilinmeyen workflow ve gecersiz durum gecisi reddedilmelidir.
- Kaynak hash'i degisen sonuc onaysiz kalmalidir.
- Tetiklenmemis bir B adayi `ready` gorunmemelidir.

## 12. Karar gunlugu

1. **Olay gunlugu secildi.** Tek guncel JSON daha basitti fakat gecmisi ezerdi;
   dosya varligindan durum cikarma ise neden ve tetikleyiciyi tasiyamazdi.
2. **Olay gunlugu append-only olacak.** Gecmis yeniden yazilmayacak ve duzeltme
   yeni olayla yapilacak.
3. **Pre-thesis kuyrugu thesis tracker'dan ayrildi.** Idea bucket'i sirket tezi
   veya pozisyon karari degildir.
4. **Serbest analiz korunacak.** Model metni standartlastirilmayacak; yalniz
   workflow olaylari kontrollu olacak.
5. **Workflow katalogu kapali olacak.** Model onerisi katalogda yoksa sistem
   onu uydurmayacak.
6. **B adaylarinda izlenebilirlik zorunlu.** Tetikleyici yoksa tarihli manuel
   inceleme gerekir.
7. **Arka plan servisi olmayacak.** Kontroller kullanici komutuyla yapilacak ve
   son kontrol zamani gorunecek.
8. **Tek CLI kullanilacak.** Durum, siradaki is, sonuc baglama ve tetikleyici
   kontrolu ayni giris noktasindan yonetilecek.
9. **Mevcut artefaktlar korunacak.** Legacy kosular silinmeden yeni olay
   gunlugune baglanacak.
10. **(2026-08-13) Idea-generation taslak cikarma agy'ye tasindi.** Onceki
    regex/tablo ayristirici (`parse_screen_table`) yalniz ChatGPT'nin belirli
    bir markdown tablosu uretmesi halinde calisiyordu; serbest metin
    cevaplarda sessizce yanlis/eksik taslak uretme riski tasiyordu (bkz.
    [repo-map.md](repo-map.md) bulgusu). Yerine `agy --json-schema` ile
    semaya zorlanmis gercek bir LLM cikarimi konuldu
    (`extract_candidates_via_agy`, `src/adapter/pei_workflow.py`); sonuc
    `structured_output` alanindan okunur (`response` alani agy'nin kendi
    onarim denemelerini icerebilir, guvenilmez). Workflow eslemesi
    (`suggested_workflow` -> `mapped_workflow`) hala deterministik kodda,
    LLM'e birakilmadi. 24.000 karakter ustu sonuclar komut satiri sinirina
    takilir ve acik hatayla durur (sessiz bozulma yerine fail-closed).

## 13. Uygulama sirasi

1. Olay ve workflow katalog semalari.
2. Append-only store, projection ve dogrulama cekirdegi.
3. `status` ve `next` salt-okunur komutlari.
4. `start-idea`, `attach-result`, `validate` ve `approve`.
5. `prepare` ile mevcut pack ureticisinin baglanmasi.
6. Tetikleyici degerlendirme.
7. Legacy 2026-08-12 tasimasi.
8. Hedefli testler ve kanonik dokumantasyon guncellemesi.

## 14. Uygulanan komutlar

Tasarim 2026-08-12 tarihinde uygulanmistir. Yeni bir oturum once su iki
komutu calistirir:

```bash
python scripts/us_pei_workflow.py status
python scripts/us_pei_workflow.py next
```

Yeni aylik kosu:

```bash
python scripts/us_pei_workflow.py start-idea --tickers AAPL,MSFT,...
```

ChatGPT sonucu alindiktan sonra:

```bash
python scripts/us_pei_workflow.py attach-result --run-id <RUN_ID> --file <PATH>
```

Idea sonucu icin Codex, `candidate_screened` olaylarini
`schemas/pei-workflow-event.schema.json` biciminde bir draft'a cikarir. Ornek
olarak 2026-08-12 legacy kosusu su dosyada bulunur:

```text
pei/2026-08-12/shortlist/idea/record/screen-draft.json
```

Taslak kalici durumu degistirmeden once:

```bash
python scripts/us_pei_workflow.py validate --draft <DRAFT>
python scripts/us_pei_workflow.py approve --draft <DRAFT>
```

`next` ciktisindaki kesin komut daha sonra calistirilir. Hazirlanan workflow
sonucu, kendi work item kimligiyle baglanir:

```bash
python scripts/us_pei_workflow.py prepare <WORK_ITEM_ID>
python scripts/us_pei_workflow.py attach-result --run-id <RUN_ID> \
  --work-item <WORK_ITEM_ID> --file <PATH>
```

Haftalik kontrol:

```bash
python scripts/us_pei_workflow.py check-triggers --refresh
```

`--refresh`, yalniz veri gerektiren bekleyen tetikleyiciler varsa guncel bir
kontrol pack'i uretir. Tarih tetikleyicileri dis veri yenilemeden kontrol
edilir. Tetikleyici olusturulamayan adaylar otomatik ilerlemez; tarihli manuel
inceleme zamani geldiginde `blocked` olur ve nedeni `status` ciktisinda
gorunur.
