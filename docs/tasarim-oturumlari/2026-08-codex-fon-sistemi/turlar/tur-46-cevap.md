Üst düzey hükmüm şu: tek bir şemadan diğerlerini otomatik üretmeye çalışmayalım. Aynı domain semantiğini paylaşan fakat farklı sorumlulukları olan dört temsil bulunsun.

## 1. Temsiller ve otorite

| Katman | Rolü | Otorite mi? | Şema gerekir mi? |
|---|---|---|---|
| Kanonik olaylar + hash’li artefaktlar | Gerçekte ne oldu ve hangi belgeye dayanıyordu? | **Evet** | Evet, her olay türü için |
| SQLite depolama | Atomiklik, sıra, uniqueness, indeks ve transaction | Hayır; kanonik gerçekliği saklar | Evet, DDL/migration olarak |
| Kalıcı projection/snapshot | Pozisyon, NAV, risk, proposal gibi karar girdileri | Hayır; yeniden üretilebilir | **Evet** |
| Geçici kod içi nesneler | Tek process içindeki ara hesaplar | Hayır | Kod tipi yeterli |

Önemli düzeltme: **Olay şeması otorite değildir; kabul edilmiş olay örnekleri ve referans verdikleri değişmez artefaktlar otoritedir.** Şema yalnızca deftere neyin kabul edilebileceğini belirler.

Projection’ın türetilmiş olması şemasız olabileceği anlamına gelmez. Şunlardan herhangi biri doğruysa projection’a JSON Schema gerekir:

- Dosyaya veya veritabanına kaydediliyorsa
- Hash’lenip proposal’a bağlanıyorsa
- Başka motorun girdisiyse
- İnsan karar ekranında gösteriliyorsa
- Geçmiş kararın ne gördüğünü kanıtlıyorsa

Dolayısıyla `position_snapshot`, `nav_snapshot`, `portfolio_risk_snapshot`, `portfolio_proposal` ve `reconciliation_report` şemalı olmalıdır. Her biri `projector_version`, `built_from`, `as_of` ve `input_manifest_hash` taşımalıdır.

JSON Schema’dan SQLite DDL otomatik üretmem. JSON Schema domain/write sözleşmesini; DDL atomiklik, unique constraint, foreign key ve indeksleri temsil eder. Aralarındaki uyum test edilir.

## 2. Para, oran ve adet

Repo zaten doğru yöne gitmiş: `decimalString` geleneği korunmalı.

### Kanonik tipler

```text
Money:
  amount: decimal string
  currency: ISO 4217

Quantity:
  amount: non-negative decimal string
  unit: shares
  security_id

Price:
  amount: decimal string
  currency
  quantity_unit: share

FxRate:
  value: positive decimal string
  base_currency
  quote_currency
  convention: quote_per_base

Weight:
  fraction: decimal string, 0..1
```

Örnekler:

```json
{"amount": "123.45", "currency": "USD"}
{"amount": "0.125", "unit": "shares"}
{"fraction": "0.075"}
```

Kurallar:

- Domain katmanında `float` yasaktır.
- JSON ve SQLite’ta exact decimal değerler `TEXT` olarak saklanır.
- Hesaplama Python `Decimal` ile yapılır.
- SQL içinde TEXT decimal üzerinde `+`, `/` gibi işlemler yapılmaz.
- Kaynak hassasiyeti korunur; yalnız sunum sırasında yuvarlanır.
- Her yuvarlama noktasının ayrı kuralı vardır: broker quantity increment, currency settlement, ekran gösterimi gibi.

SQLite `NUMERIC` affinity metinsel sayıları INTEGER veya REAL’a çevirebilir ve REAL dönüşümünde yaklaşık 15–16 anlamlı basamakla sınırlıdır; bu nedenle exact decimal alanlarını `TEXT` tutmak gerekir. [SQLite resmî tür dokümantasyonu](https://www.sqlite.org/datatype3.html)

Minor-unit integer’ı kanonik tip yapmam. Cent; FX, fractional share, bölünme oranı, fractional-cent ücret ve faiz için yetersizdir. Broker gerçekten minor unit veriyorsa türetilmiş reconciliation alanı olabilir.

Policy tarafından yazılan oranlar ise anlamı bp ise integer tutulabilir:

```text
loss_budget_bp: 100
max_position_bp: 1250
no_trade_absolute_bp: 100
```

Hesaplanmış ağırlıklar bp’ye yuvarlanmaz; decimal fraction olarak korunur.

Kesirli hisse baştan desteklenmelidir. `Quantity.amount` decimal string olur; izin verilen adım `broker_instrument_capability.quantity_increment` alanından gelir. Global “en fazla dört ondalık” kuralı konmamalıdır.

## 3. Zaman modeli

Üç temel zaman tipi gerekir:

### `UtcInstant`

Gerçek bir an:

- `occurred_at`
- `recorded_at`
- `known_at`
- `approved_at`
- `submitted_at`
- `filled_at`
- `valuation_at`

Kanonik UTC, `Z` son ekli RFC 3339 biçimi kullanılır. Yeni fund şemalarında repo’nun mevcut `utcInstant` yaklaşımı korunur.

### `LocalDate`

Saat anlamı taşımayan ekonomik/takvim tarihi:

- `period_end`
- `trade_date`
- `settlement_date`
- `effective_date`
- `ex_date`
- `pay_date`
- `review_date`

Bunları gece yarısı UTC timestamp’ine çevirmek yasaktır.

### `MarketSessionDate`

```json
{
  "session_date": "2026-08-17",
  "market_calendar_id": "XNYS",
  "venue_id": "XNYS"
}
```

Trade date, kullanıcının İstanbul tarihinden veya UTC tarihten türetilmez; broker/venue takvimine aittir.

“Bugün” kanonik veri alanı değildir. Scheduler bir `evaluation_instant` alır ve bundan ayrı ayrı şunları türetir:

- `operator_date` — `Europe/Istanbul`
- `market_session_date` — ilgili borsa takvimi
- Gerekirse `broker_business_date`

`America/New_York` gibi IANA timezone kullanılmalı; sabit `UTC-5` kullanılmamalıdır.

JSON Schema’daki `format: date-time` varsayılan olarak yalnız annotation olabilir; validator’ın gerçekten reddetmesi garanti değildir. Bu nedenle mevcut repodaki gibi pattern + runtime parser birlikte kullanılmalıdır. [JSON Schema resmî açıklaması](https://json-schema.org/understanding-json-schema/reference/type)

## 4. Kimlikler

Kanonik iç kimliklerde **UUIDv7** kullanırdım:

- `event_id`
- `issuer_id`
- `security_id`
- `listing_id`
- `account_id`
- `thesis_id`
- `proposal_id`
- `attempt_id`
- `lot_id`
- `policy_id`
- `authority_grant_id`

UUIDv7 standartlaştırılmış, zamanla kabaca sıralanabilir ve çakışma güvenliği sağlar. Ancak olay sırası UUID’den türetilmez; sıra SQLite’ın `global_position` ve `stream_position` alanlarıyla belirlenir. [RFC 9562](https://www.rfc-editor.org/rfc/rfc9562.html)

`PROP-2026-0042` gibi değerler yalnız `display_ref` olabilir; foreign key, idempotency veya event identity olarak kullanılmaz.

Security kimliği üçe ayrılmalıdır:

```text
issuer_id   -> şirket / SEC registrant
security_id -> ekonomik/legal menkul kıymet veya pay sınıfı
listing_id  -> belirli borsadaki listeleme ve ticker
```

Dış kimlikler mapping tablosunda yaşar:

- CIK: çoğunlukla issuer kimliği
- Ticker: listing alias; değişebilir
- FIGI/ISIN/CUSIP: varsa security/listing mapping
- Broker instrument ID: broker’a özgü mapping

Hiçbiri kendi başına iç `security_id` olmaz.

Fill idempotency anahtarı da `event_id` değildir. Öncelik:

1. Broker transaction/fill ID
2. Broker account + statement ID + row ID
3. Kontrollü import fingerprint

## 5. Sürümleme

Dosya adı, `$id` ve veri örneği birlikte sürüm taşımalıdır.

Örnek:

```text
schemas/fund/events/fill-recorded-1.0.0.schema.json
```

```json
{
  "$id": "https://trade-us.local/schemas/fund/events/fill-recorded/1.0.0"
}
```

Olay örneği:

```json
{
  "schema_ref": {
    "schema_id": "fund.events.fill_recorded",
    "schema_version": "1.0.0"
  }
}
```

Kurallar:

- Yayınlanmış schema dosyası sonradan değiştirilmez.
- Her olay, kendisini doğrulayan tam şema sürümünü taşır.
- Eski olaylar yeniden yazılmaz.
- Projector eski sürümleri adapter/upcaster ile güncel iç modele çevirir.
- SQLite storage sürümü ayrı migration tablosunda tutulur; olaylara yazılmaz.
- Projection ayrıca `projection_schema_version` ve `projector_version` taşır.
- Policy’nin `policy_version`ı, JSON Schema sürümünden farklıdır.
- Engine sürümü de şema sürümü değildir.

Tek `schema_version` alanını bütün bu anlamlar için kullanmak yasaktır.

Referans zinciri şöyledir:

```text
event -> exact event schema
projection -> projection schema + projector version + event high-water mark
proposal -> exact policy + risk snapshot + input manifest + engine version
```

## 6. Dosya sayısı ve yazım sırası

Minimum fon omurgası yaklaşık **24–30 yeni şema**, tam hedef sistem **30–40 şema** eder. Her event type için tamamen ayrı dosya açılırsa sayı 50’yi geçer; bunun yerine açık discriminator taşıyan event-family dosyaları kullanılabilir. Fakat hiçbir aile genel amaçlı `payload patch` kanalına dönüşmemelidir.

Önerilen gruplar:

- 5 ortak primitive/ref şeması
- 3–4 identity/reference şeması
- 7–9 event-family şeması
- 5–6 policy/governance dokümanı
- 7–10 projection/snapshot şeması

İlk açılacak dosya:

```text
schemas/fund/common/core-types-1.0.0.schema.json
```

Burada yalnız atomik tanımlar bulunur:

- UUIDv7
- schema reference
- SHA-256 digest
- decimal string
- currency code
- basis points
- UTC instant
- local date
- market session reference

Sonraki sıra:

1. `core-types`
2. `identity-reference` — issuer/security/listing/account
3. `event-envelope`
4. `capital-policy`
5. `policy-validation-spec/report`
6. Accounting event ailesi — opening balance, cash flow, fill, fee, dividend
7. Corporate-action event ailesi
8. Position/cash/lot snapshot
9. Market valuation ve NAV snapshot
10. Reconciliation report
11. Risk snapshot
12. Portfolio proposal ve decision
13. Operating authority
14. Execution intent/fill lifecycle
15. Performance/attribution

Mevcut `valuation-common.schema.json` geriye dönük uyumluluk için değiştirilmemelidir. Yeni fund şemaları valuation’a özgü namespace’e bağlanmak yerine yeni `fund/common` primitive’lerini kullanmalı; eski şemalar zamanla, yalnız ihtiyaç oldukça adapte edilmelidir.

En temel karar özeti:

> Kanonik olaylar gerçeği, SQLite güvenli saklamayı, şemalı projection’lar karar arayüzünü temsil eder; para decimal string, zaman anlamına göre date/instant/session, iç kimlik UUIDv7, dış kimlikler mapping ve bütün kalıcı sözleşmeler exact schema version taşır.