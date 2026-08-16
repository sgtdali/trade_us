Doğru ayrım şu: **tez takibi insanın hatırladığı bir takvim değil, yeni kanıt geldikçe çalışan küçük bir kontrol döngüsü olmalıdır.** İnsan tezi yorumlar ve durum değişimini kabul eder; hangi metriğe ne zaman bakılacağını sistem hatırlar.

## 1. Bu ölçekte tez izleme ne yapmalı?

Sekiz tez için önerdiğim döngü:

```text
Yeni filing / earnings kanıtı / review tarihi
                    ↓
       Normalize finansallar güncellenir
                    ↓
     Mekanik kurallar değerlendirilir
                    ↓
 ┌──────────────────┴──────────────────┐
 │                                     │
Sapma yok                         Sapma / nitel review
 │                                     │
Kısa kontrol kaydı               thesis = review_required
                                       ↓
                              Sabit review recipe
                           deep-dive → thesis-tracker
                                       ↓
                             Provisional assessment
                                       ↓
                              İnsan adjudication
                                       ↓
                      Yeni assessment + tez durumu
```

Finansal kurallar haftalık çalışmaz; **yeni ilgili veri geldiğinde** çalışır. Günlük `research-cycle`, aynı financial rule’u her gün yeniden değerlendirmez.

Tipik sekiz tezde toplam 16–32 koşul olabilir. Bunların muhtemelen:

- 8–16’sı mekanik
- 8–16’sı nitel

olur. Ancak başlangıç için tez başına **1–2 mekanik ve 1–2 nitel koşul** yeterlidir.

Repo gerçekten avantaj sağlıyor:

- `revenue_growth`
- `gross_margin`
- `free_cash_flow_margin`
- `operating_margin`
- `roic`

gibi metrikler katalogda bulunuyor. [metric-catalog.json](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/config/pipeline/metric-catalog.json:2058) Finansal seri sözleşmesi dönem, birim ve provenance taşıyor. [financial-series.schema.json](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/schemas/financial-series.schema.json:1) Normalizasyon da yayın tarihi ve accession tabanlı kaynak sürümünü saklıyor. [normalize.py](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/src/adapter/normalize.py:211)

Fakat eşleme bedava değildir. Şu ifade eksiktir:

> “Gelir büyümesi %15’in altına inerse.”

Şunların seçilmesi gerekir:

- Çeyreklik mi, TTM mi?
- Yıllık karşılaştırma mı?
- Raporlanan gelir mi, organik büyüme mi?
- Devam eden faaliyetler mi?
- Hangi birim ve şirket kapsamı?

Genel GAAP metriklerinin bağlanması kural başına yaklaşık 10–30 dakikalık doğrulama işidir. Segment, non-GAAP veya şirket-özel KPI’lar saatler sürebilir. **Katalogda güvenilir karşılığı olmayan koşul mekanik yapılmaya zorlanmamalı; nitel kalmalıdır.**

## 2. En küçük monitoring sözleşmesi

Tezin içinde sürümlü küçük bir alt belge yeterlidir:

```text
monitoring_contract
  version
  effective_from

  mechanical_rules[]
    rule_id
    metric_id
    period_basis
    test_type
    operator
    threshold
    optional_baseline

  qualitative_checks[]
    check_id
    question
    review_on
    review_due
```

Kapalı sözlükler dar tutulur:

### `period_basis`

- `latest_quarter_yoy`
- `latest_quarter_qoq`
- `ttm`
- `latest_fy`
- `change_from_baseline`

### `test_type`

- `absolute_value`
- `percentage_change`
- `basis_point_change`

### Mekanik kontrol sonucu

- `not_breached`
- `breached`
- `unavailable`

`not_breached`, “tez sağlıklı” anlamına gelmez; yalnız ilgili kuralın ihlal edilmediğini söyler.

Şunlar sözleşmede tekrarlanmaz:

- Unit: metric katalogdan gelir.
- Source contract: metric katalogdan gelir.
- Cadence: financial rule yeni filing’de çalışır.
- `known_at`: değerlendirme kaydı kullanılan accession ve publication date’i taşır.
- Missing-data policy: V0’da sabittir; veri yoksa tahmin yapılmaz.
- Revision policy: Aynı dönemin yeni accession/restatement’i gelirse otomatik olarak yeniden inceleme gerekir.
- Tolerance: Yalnız gerçek ihtiyaç görülen kuralda opsiyonel eklenir.

Tez başına önerim:

- Normal durum: 3 kural
- Makul aralık: 2–4
- Sert tavan: 5

Bir koşul ihlal edildiğinde pozisyonu yeniden değerlendirmeyeceksek monitoring kuralı olmamalıdır.

Monitoring kuralları değiştirilebilir; fakat eski sürüm silinmez. Eşik gevşetme, yeni version ve gerekçe gerektirir.

## 3. Nitel koşullar

Deep-dive’ın nitel koşullara kendiliğinden bakacağı varsayılmamalıdır. Aktif nitel sorular pack’e açıkça enjekte edilir:

```text
- Hyperscaler capex siparişe dönüşüyor mu?
- Pricing power zayıflıyor mu?
- Competitive moat üzerinde yeni kanıt var mı?
```

Her nitel koşul şu tetikleyicilerden birini veya birkaçını taşır:

- `new_periodic_filing`
- `earnings_release`
- `material_8k`
- `review_due`

Doğru politika:

- Yeni filing/earnings gelirse deep-dive bu soruları cevaplar.
- Yeni kanıt gelmese bile `review_due` dolunca tracker otomatik çalışır.
- Sessiz haftalarda insanın önüne liste düşmez.
- Her nitel koşul `last_reviewed_at` ve `review_due` taşır.

Böylece “mekanik sapma yok” ile “nitel koşullar kontrol edildi” birbirine karıştırılmaz.

## 4. Thesis ve assessment ayrıdır

Evet, doğru model şudur:

> **Thesis kalıcı lifecycle nesnesidir; assessment o tezin belirli tarihteki fotoğrafıdır.**

### Minimal `thesis`

- `thesis_id`
- `security_id`
- `opened_at`
- `thesis_statement`
- `status`
- `current_assessment_id`
- Sürümlü küçük `monitoring_contract`
- `closed_at` ve `close_reason` — gerekiyorsa

### Status

- `active`
- `review_required`
- `broken`
- `closed`

Actual exposure thesis’in alanı değildir; `account_event` projection’ından gelir. Dolayısıyla üç gerçek ayrı kalır:

1. Tezin governance durumu
2. Gerçek pozisyon/exposure
3. Tarihli assessment geçmişi

Bir tez hayatı boyunca çok sayıda assessment alır:

```text
THS-NVDA-01
  ├── ASM-001  açılış
  ├── ASM-002  Q2 earnings sonrası
  ├── ASM-003  review_due
  └── ASM-004  Q3 filing sonrası
```

Makine tezi otomatik `broken` veya `closed` yapamaz. Mekanik breach yalnız `review_required` üretir. Tracker bir durum değişikliği önerir; insan adjudication’ı `active`, `broken` veya `closed` sonucunu kabul eder.

Bu nedenle nesne sayısı dörtten beşe çıkar:

1. `capital_policy`
2. `thesis`
3. `assessment_record`
4. `decision_record`
5. `account_event`

Monitoring contract ayrı bir üst düzey nesne değil, thesis’in sürümlü alt belgesidir.

## 5. Mekanik sapmadan sonra ne olur?

Temel hükmünde sana katılıyorum: **Sapma önce insana değil, otomatik olarak tracker recipe’sine gitmelidir.**

Ancak her breached rule ayrı LLM çağrısı üretmez.

### Gürültü kontrolü

1. Kural yalnız yeni evidence/accession geldiğinde değerlendirilir.
2. Aynı evidence için yalnız bir kez çalışır.
3. Aynı tezdeki bütün breach’ler tek work item’da birleştirilir.
4. Filing için zaten deep-dive çalışıyorsa ayrı tracker çağrısı açılmaz; breach’ler aynı recipe’ye eklenir.
5. Dedup anahtarı:

```text
thesis_id + monitoring_contract_version + evidence_accession
```

6. Yeni evidence veya contract version gelmeden tekrar çalışmaz.
7. `unavailable` tek başına yeni LLM çağrısı üretmez; mevcut filing review’ına veri boşluğu olarak eklenir.

### Sabit recipe’ler

```text
Yeni filing + açık tez
    → deep-dive
    → thesis-tracker
    → adjudication inbox

Review_due + yeni filing yok
    → thesis-tracker
    → adjudication inbox

Bağımsız mekanik breach
    → thesis-tracker
    → adjudication inbox
```

Tracker şunları görür:

- Mevcut thesis
- Son kabul edilmiş assessment
- Aktif monitoring kuralları
- Yeni evidence
- Breached/unavailable rule sonuçları
- Vadesi gelmiş nitel sorular

Şunları görmez:

- Pozisyon ağırlığı
- Maliyet
- P&L
- İşlem sonucu

Çıktısı yalnız provisional assessment’tır. İnsan kabul ettikten sonra yeni assessment aktif olur; ancak bundan sonra `trade-preview` sermaye etkisini gösterir.

Sekiz tez için bu model haftalık sekiz LLM çağrısı üretmez. Esas ritim filing ve earnings’tir: yılda yaklaşık 2–4 anlamlı review/tez, yani kabaca **16–32 otomatik review recipe’si/yıl**. Bu ölçek otomasyonun maliyetini haklı çıkarır, fakat genel monitoring platformu gerektirmez.

Son hüküm:

> **Sistem yalnız review tarihini hatırlamamalı; yeni kanıtı gözlemlemeli, az sayıdaki mekanik kuralı çalıştırmalı, nitel soruları doğru skill’e vermeli ve yorumlanmış sonucu insanın önüne getirmelidir. İnsan tezi takip etmez; sistem takip eder, insan hüküm verir.**