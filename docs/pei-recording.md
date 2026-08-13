# PEI serbest analiz kayit sistemi

## Amac

Bir PEI skill'inin serbest Markdown cevabini kaliba zorlamadan saklamak ve bu
cevaptan izlenebilir, tarihli, insan onayli tez kayitlari uretmek.

Sistem model cevabinin tekrarlanabilir olmasini beklemez. Standart olan analiz
metni degil, analizden sonra uretilen kaydin anatomisi ve dogrulama surecidir.

## Akis

```text
pack.json
  -> serbest skill analizi
  -> result.md (degismez kaynak)
  -> Codex destekli semantik cikarma
  -> record/draft.json
  -> deterministik validate
  -> record/validation.json
  -> acik kullanici onayi
  -> data/thesis-tracker/{TICKER}/{thesis_id}.jsonl
```

Ilk surum LLM veya OpenAI API cagrisi yapmaz. Codex, kullanicinin verdigi
`result.md` cevabindan taslagi hazirlar. Repo araci yalniz sema, kaynak,
denklesme, gecis ve append kurallarinin otoritesidir.

## Kimlik ve gecmis

Tracker sirket basina tek dosya degildir. Ayni sirketin farkli zamanlarda veya
es zamanli birden fazla tezi olabilir.

```text
data/thesis-tracker/VZ/
  VZ-20260812-operational-stabilization.jsonl
  VZ-20270315-frontier-synergy.jsonl
```

- Ayni iddiayi test eden yeni kanit mevcut `thesis_id` dosyasina append edilir.
- Sahip olma gerekcesi degisirse yeni tez acilir.
- Yeni tez eskisinin yerini aliyorsa `supersedes_thesis_id` ile bag kurulur.
- Eski kayit silinmez veya yeniden yazilmaz.
- Ayni cevap hash'i veya ayni `record_id` ikinci kez kaydedilmez.

## Kayit sozlesmesi

Kucuk cekirdek kontrolludur:

- skill'e ait hukum,
- sirket tezi durumu,
- menkul kiymet tezi hazirligi,
- pozisyon aksiyonu ve pozisyon durumu,
- tez islemi (`open_new`, `append_existing`, `supersede_existing`),
- kural anatomisi, operatorler ve tarih bicimi.

Sirket-ozel icerik aciktir:

- tez ve variant perception duzyazisi,
- KPI/metrik adlari,
- aksiyon aciklamasi,
- katalizorler,
- yapilandirilamayan fakat saklanmasi gereken bulgular.

### Sema surumleri

- `schema_version: 1` ilk acilis kayitlarinin geriye uyumlu bicimidir.
- `schema_version: 2` yeni kayitlar icin izleme katmanini ekler.
- Onaylanmis v1 satirlari migrate edilmez, yeniden yazilmaz ve gecerliligini
  korur. Ilgili tezin bir sonraki gercek kanit guncellemesi v2 olabilir.

V2 dort yapilandirilmis koleksiyonu zorunlu kilar:

- `thesis_pillars`: sirket tezinin sinanabilir, sirket-ozel sutunlari;
- `evidence_ledger`: tarihli, kaynak alintili dogrulayici veya curutucu kanit;
- `kpi_observations`: belirli doneme ait KPI gozlemi ve sonraki test;
- `open_questions`: karar kalitesini sinirlayan acik arastirma sorulari.

Bir tez acilisinda en az bir pillar ve bir kanit satiri gerekir. Bir
`evidence_update` en az bir yeni kanit satiri tasir. Kanit ve KPI gozlem
kimlikleri ayni tez icinde tekrar kullanilamaz. Pillar, kural ve kanit
referanslari mevcut tez gecmisinde gercekten bulunmak zorundadir.

Esikler yalniz `rules` koleksiyonunda otoritatiftir. Pillar ve KPI kayitlari
esigi tekrar kopyalamaz; `linked_rule_ids` ile kurala baglanir. Boylece ayni
esigin iki farkli yerde zamanla ayrismasi engellenir.

Her kural en az bir kosul, test tarihi, aksiyon ve `result.md` icinde gercekten
bulunan kaynak alintisi tasir. Yeni model esikleri varsayilan olarak
`draft_for_pm_confirmation` ve `pending` durumundadir. Bir kaydin onaylanmasi,
icindeki taslak esiklerin portfoy kurali olarak onaylandigi anlamina gelmez.

## Dogrulama

`python scripts/us_pei_record.py validate --draft <draft.json>` sunlari kontrol
eder:

1. JSON Schema ve kapali durum sozlukleri.
2. Kaynak dosyalarin repo icinde olmasi ve SHA-256 butunlugu.
3. Her kural alintisinin `result.md` icinde bulunmasi.
4. Opsiyonel pack JSON Pointer kontrollerinin gercek degerlerle eslesmesi.
5. Butun esiklerin tarihli olmasi ve senaryo olasiliklarinin toplami.
6. Tez acma/ekleme/yerine gecme isleminin mevcut tracker durumu ile uyumu.
7. Mukkerrer `record_id` ve cevap hash'i.
8. V2 pillar/kural/kanit referanslari ile kanit ve KPI kimliklerinin tekilligi.
9. Birden fazla core pillar bozuldugunda toplam sirket tezi durumunun
   `impaired`/`broken` olmasi veya kaynakli bir override gerekcesi tasimasi.

Sonuc `valid`, `valid_with_review` veya `rejected` olur. `valid_with_review`
ancak kullanici acikca inceleme uyarilarini kabul ederse onaylanabilir.

## Onay

`approve` komutu taslagi yeniden dogrular. Basarili kayda ayri
`record_approval` metadatasi ekler ve ilgili tez JSONL dosyasina atomik olarak
append eder. Taslak degismez; onayli satir onun bir kopyasidir.

## Karar gunlugu

- Serbest analiz metni standartlastirilmayacak.
- Kayit cikarma analizden ayri bir Codex gecisi olacak.
- Dogrulama ve append islemi deterministik olacak.
- Tracker tarihli ve tez kimligi bazinda olacak.
- Sirket-ozel metrik adlari serbest kalacak.
- Onaysiz kayit kalici gecmise giremeyecek.
- Ilk surumde API otomasyonu olmayacak.
- Excel, dashboard veya arayuz kalici kayit katmaninin parcasi olmayacak.
- V2 izleme alanlari JSONL icinde tutulacak; gorunum ihtiyaci daha sonra ve
  kaynak kayittan bagimsiz olarak ele alinacak.
- Onaylanmis v1 kayitlari geriye donuk zenginlestirilmeyecek; ilk yeni gercek
  kanitla v2 append baslayacak.
