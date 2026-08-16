Temel kesme ilkesi: **genelliği kes, doğruluğu kesme**. İlk dilimde geniş aile şemaları veya gelecekte kullanılabilecek enum’lar değil, açılış kitabını kayıpsız replay etmeye yetecek dar ve kapalı sözleşmeler yazılmalı.

## 1. İlk çalışan dilim için şema seti

### Şimdi tam yazılacak

Dar kapsamları içinde eksiksiz olmalılar:

| Dosya | V0 kapsamı |
|---|---|
| `common.schema.json` | UUIDv7, exact decimal, Money, Currency, UtcInstant, LocalDate, digest, artifact ref |
| `fund-definition.schema.json` | Fund/account kapsamı, base currency, opening as-of |
| `event-envelope.schema.json` | Kimlik, subject, actor, idempotency, zaman, correlation/causation, payload bağlantısı |
| `opening-accounting-event.schema.json` | Yalnız `opening_account_state_asserted`; nakit, pozisyon, cost-basis durumu, kaynak |
| `valuation-observation-bundle.schema.json` | Security fiyatı, currency, market date/as-of; gerekiyorsa FX |
| `fund-state-projections.schema.json` | Position ve cash projection’larının V0 biçimi |
| `nav-snapshot.schema.json` | NAV, bileşenler, eksik fiyat/FX durumu, provenance |
| `fund-ledger.sql` | Batch, event, stream, artifact ve projection checkpoint tabloları |

`opening-accounting-event` bütün muhasebe olaylarını şimdiden saymamalı. Yalnız gerçekten çalışan opening olayını tam tanımlamalı.

### Stub olarak yazılacak

Stub demek `additionalProperties: true` demek değildir. Dar, kapalı ve sürümlü olmalı; sonra yeni opsiyonel alanlarla veya yeni şema sürümüyle genişlemeli.

| Dosya | V0 alanları | Sonraya bırakılanlar |
|---|---|---|
| `instrument-master.schema.json` | issuer/security/listing ID, mevcut ticker, venue, currency, active status | Ticker geçmişi, ADR/underlying, merger/spin-off ilişkileri, haricî ID kataloğu |
| `artifact-manifest.schema.json` | ID, type, schema ref, digest, media type, byte size, immutable path | Tam lineage DAG, retention, replica kayıtları |
| `input-manifest.schema.json` | Doğrudan input ref/digest listesi ve producer sürümü | Closure manifest, ayrıntılı lineage relations |
| Projection metadata | Projection ID, as-of, high-water mark, projector version, input digest | Reconciliation ayrıntıları, data-quality taksonomisi |

Instrument master’daki üç kimlik şimdi korunmalı; yalnız etraflarındaki bütün kurumsal işlem modeli yazılmamalı.

### Bu dilimde hiç yazılmayacak

- Fill, temettü, ücret, vergi, faiz ve corporate-action şemaları
- Lot projection ve lot disposition
- Reconciliation motoru ve ayrıntılı reconciliation şemaları
- `capital-policy.schema.json`ın çalıştırılabilir validator’ı
- `policy_validation_spec`
- `operating_authority`
- `portfolio_risk_snapshot`
- `portfolio_proposal`
- Execution plan, ticket, broker order
- TWR/MWR ve attribution
- Driver registry, scenario setleri
- Araştırma/thesis entegrasyonu

Capital policy karar belgesi doldurulabilir ve draft olarak saklanabilir; fakat açılış/NAV dilimi onu yürütmediği için tam validator’ını şimdi yazmak gerekmez. Risk engine diliminden önce zorunlu hâle gelir.

Toplam: **7 tam şema + 3 küçük stub + 1 DDL**. Otuz şema değil.

## 2. Büyük şemaların küçük başlangıcı

Bunlar ilk açılış diliminde hiç yazılmamalı. Risk/proposal dilimine gelindiğinde V0 şu kadar olmalı.

### `portfolio_risk_snapshot` V0

Tutulacaklar:

```text
risk_snapshot_id
fund_id
as_of
policy_ref
position_snapshot_ref
nav_snapshot_ref
market_snapshot_ref
input_manifest_ref
producer
calculation_status
nav
cash_weight_bps_nav
deployable_capital
active_position_count
security_rows[]
limit_evaluations[]
proposal_gate
```

Security satırı:

```text
security_id
issuer_id
current_market_value
current_weight_bps_nav
policy_eligible
policy_compliant_max_weight_bps_nav
additional_capacity_bps_nav
constraint_evaluations[]
```

İlk constraint türleri yalnız:

```text
readiness_cap
downside_capacity
security_limit
issuer_limit
cash_capacity
```

İlk `binding_state` sözlüğü:

```text
binding
co_binding
non_binding
blocked
```

V0’dan çıkarılacaklar:

- `near_binding`
- `not_applicable` constraint satırları
- Causal-driver exposures
- Sector decomposition
- Currency exposures
- Scenario results
- Standalone downside sum
- Policy-assumption predicate sonuçları
- Liquidity capacity
- Ayrıntılı data-quality taksonomisi

Uygulanmayan constraint satırı hiç üretilmez. Böylece `not_applicable` satır yağmuru oluşmaz.

### `portfolio_proposal` V0

Tutulacaklar:

```text
proposal_id
fund_id
generated_at
decision_as_of
trigger
policy_ref
risk_snapshot_ref
input_manifest_ref
producer
proposal_outcome
options[]
validity_contract
decision_deadline
```

Options için:

- Tam olarak bir `status_quo`.
- Değişiklik varsa tam olarak bir `primary`.
- Alternatif yok.
- Her ikisi de bütün portföyü temsil eder.
- Target, exact zorunlu sayı değil band olabilir.
- İnsan kararı ayrı olaydır.

Option V0:

```text
option_id
role
position_targets[]
cash_target_band
resulting_cash_weight_bps_nav
turnover_bps_nav
hard_limit_results[]
reason_codes[]
```

Şimdilik çıkarılacaklar:

- Bir veya iki alternatif
- Replacement pair/counterfactual
- Scenario karşılaştırmaları
- Ayrıntılı maliyet tahmini
- Driver/sector etkisi
- Çok boyutlu portfolio-effects raporu
- İnsan-dili anlatı alanları

V0 karar state’leri:

```text
pending_review
approved
rejected
approval_revoked
expired
superseded
```

`deferred` yerine proposal pending bırakılabilir; validity süresi dolarsa expire olur. `reapproval_required` yerine değişen girdilerle yeni proposal üretilir. Bunlar ilk sürümde ciddi sadeleşme sağlar.

### Şimdi doğru konması gerekenler

Sonradan değiştirilmesi pahalı olanlar:

- UUID kimliklerinin anlamı
- Decimal/money/currency temsili
- Zaman alanlarının anlamı
- Artifact ile event ile projection ayrımı
- Exact policy/input/engine referansları
- Proposal’ın immutable olması
- İnsan kararının ayrı olay olması
- Option’ın tüm portföyü temsil etmesi
- Target’ın band olabilmesi
- Primary subject ve stream kimliği
- Event ve payload sürümleme
- Position state’lerinin anlamı
- Cost basis bilinmiyorsa sıfır yazılmaması

Sonradan ucuz eklenebilecekler:

- Yeni constraint türleri
- Yeni binding açıklamaları
- Yeni exposure breakdown’ları
- Alternatif option’lar
- Yeni scenario sonuçları
- Daha zengin reason code’lar
- Yeni projection alanları

Bir alan sonradan zorunlu olacaksa eski şema dosyası değiştirilmez. Yeni schema version çıkarılır; eski artefakt eski sürümle geçerli kalır.

## 3. Süre tahmini

### İlk çalışan dilimin şemaları

Üretim kalitesinde:

| İş | Süre |
|---|---:|
| İlk şema taslakları | 1–2 gün |
| `$ref` registry ve meta-schema doğrulaması | 1 gün |
| Pozitif/negatif fixture’lar | 1–2 gün |
| DDL ve constraint testleri | 1–2 gün |
| Anlam ve sınır düzeltmeleri | 1–2 gün |
| **Toplam** | **5–8 iş günü** |

Bu süre projector ve importer implementasyonunu içermez.

### Tanımladığımız bütün hedef set

Yaklaşık 25–30 production-quality şema için:

- AI ile ilk taslak: **3–5 gün**
- Domain incelemesi ve sadeleştirme: **6–10 gün**
- Fixture, negatif test, `$ref`, validator ve migration: **6–10 gün**
- Toplam: **15–25 odaklı iş günü**

Tek kişinin kısmi zamanıyla yaklaşık **4–6 takvim haftası**.

Claude/Codex şunları ciddi hızlandırır:

- JSON Schema boilerplate
- `if/then`, `oneOf`, `$defs` yazımı
- Örnek ve negatif fixture üretimi
- Tekrarlanan alanların faktörlenmesi
- Enum ve required uyum kontrolleri

Şunları hızlandıramaz veya güvenle tek başına çözemez:

- Alanın gerçekten gerekli olup olmadığı
- İki alanın aynı gerçeği mi taşıdığı
- Muhasebe semantiği
- Hangi yokluk durumunun `disabled` veya `unknown` olduğu
- Geriye uyumluluk kararı
- Broker verisinin gerçekte hangi ayrıntıyı sağlayacağı
- Bir fixture’ın ekonomik olarak doğru olup olmadığı

Şemayı yazmak hızlıdır; doğru şemaya karar vermek değildir.

## 4. Fazlalık denetimi

### Gerçek hatayı önleyenler — kalmalı

- Exact decimal + currency
- UUID ve issuer/security/listing ayrımı
- Event/payload schema version
- Primary subject
- Idempotency
- `occurred`/`recorded` ayrımı
- Correlation ve causation
- Artifact digest/provenance
- Cost-basis status
- `projected_flat`/`confirmed_flat`
- Global/stream position constraint’leri
- Proposal’ın immutable olması
- İnsan kararının ayrı olay olması
- Option’ın tam portföy olması
- Validity contract
- Fail-closed eksik fiyat/FX davranışı

Bunların her biri para, replay veya denetim hatası önler.

### İyi mimari hissi verip V0’da kesilecekler

- Altı değerli `binding_state` → dört değer
- On bir constraint türü → yalnız çalışan beş tür
- Geniş `related_refs.relation` taksonomisi → başlangıçta:

```text
affects
references
derived_from
```

- Tam causal-driver registry
- “Near binding” açıklama katmanı
- Çoklu alternatif proposal
- Tam validation-spec dili
- A0–A4 authority validator’ı
- Bütün accounting event family’sini peşinen yazmak
- Her projection için ayrı family/dosya
- Ayrıntılı lineage DAG
- Closure manifest’i kanonik yapmak
- Risk snapshot’ta kullanılmayan bütün breakdown’lar
- Proposal’da insan-okunur uzun gerekçe sözleşmesi

En sert hükmüm şu: **kullanılmayan enum değeri geleceğe hazırlık değil, test edilmemiş davranıştır.** Yeni değer gerçekten üretileceği turda şemaya eklenmelidir.

### Kesin V0 sınırı

İlk sürümün sorusu yalnız şu olmalı:

> “Broker kaynaklı bir açılış kitabını exact para/adetlerle bir kez kaydedip, tekrar çalıştırmada çoğaltmadan, fiyatlandırıp aynı pozisyon/nakit/NAV state’ini replay edebiliyor muyum?”

Bu soru geçmeden risk snapshot, proposal, authority veya validation spec yazmak yeniden erken kurumsallaşma olur.