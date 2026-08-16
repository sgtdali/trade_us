Ana kararım şu: üç kimliği mantıksal olarak ilk günden koruyalım; fakat bunları üç ayrı kullanıcı iş akışına ve onlarca şema dosyasına dönüştürmeyelim. Muhasebe olayları ekonomik gerçekleri, uzlaştırma olayları ise gerçeğin broker ile uyuşup uyuşmadığını anlatsın.

## 1. Issuer / security / listing

Bu ayrım gerçekten işe yarıyor:

| Vaka | Kimlik sonucu |
|---|---|
| Yalnız ticker değişimi | Aynı `issuer_id`, `security_id`, `listing_id`; sembol geçmişine yeni dönem eklenir |
| Borsa değişimi veya yeniden kotasyon | Aynı security, yeni `listing_id` |
| GOOG / GOOGL gibi sınıflar | Aynı issuer, farklı security ve listing |
| Spin-off | Yeni issuer, security ve listing; eski pozisyondan kurumsal işlemle doğar |
| Merger | Eski security sona erer; nakit ve/veya yeni security alınır |
| ADR | Ekonomik olarak bağlı olsa da ayrı security ve listing’dir |
| Delisting | Security kaybolmaz; listing kapanır |

CIK, `issuer_id` yerine geçmemeli; issuer’a bağlanan haricî kimliklerden biri olmalı.

V0’da önerim:

- JSON tarafında tek `instrument-master` şeması; içinde `issuer`, `security`, `listing` tanımları.
- SQLite tarafında küçük `issuers`, `securities`, `listings`, `listing_symbols` tabloları.
- Olaylar ekonomik araca `security_id` ile, piyasa verisi `listing_id` ile, şirket araştırması `issuer_id` ile bağlanır.

Yani üç ayrı kavram evet; üç ayrı kullanıcı yüzeyi hayır. Bunları şimdi tek kimliğe sıkıştırmak, ileride bütün olayları, lotları ve performans tarihini yeniden eşleme göçü doğurur. Ayrı kimlikleri tek master belgesinde taşımak ise ileride fiziksel ayrıştırmayı ucuz bırakır.

## 2. Açılış bakiyesi

Sentetik opening fill kullanılmamalı. Olmamış bir işlemi uydurarak sahte işlem tarihi, nakit çıkışı, elde tutma süresi ve karar attribution’ı üretir.

Doğru olay:

`opening_account_state_asserted`

Asgari payload:

- `account_id`
- `as_of`
- `source_artifact_ref` ve hash
- `cash_balances[]`
- `positions[]`
  - `security_id`
  - `quantity`
  - `cost_basis_status`
  - varsa `total_cost_basis`
  - `cost_basis_currency`
  - varsa broker lotları
  - varsa broker’ın bildirdiği piyasa değeri
- `assertion_method`
- `import_batch_id`

`cost_basis_status` şu sözlükte olmalı:

- `lot_level_known`
- `aggregate_only`
- `partial`
- `unknown`

Maliyet bilinmiyorsa sıfır yazılmaz. Sonuçları:

- Adet ve piyasa değeri bilinir.
- Açılış tarihinden sonraki TWR hesaplanabilir.
- Maliyet bilinmeden unrealized P&L hesaplanamaz.
- Satılan lotun maliyeti bilinmiyorsa realized P&L de `unknown` veya `partial` kalır.
- Aggregate maliyet biliniyor ama lotlar bilinmiyorsa toplam unrealized P&L hesaplanabilir; kısmi satış attribution’ı güvenilir değildir.

Maliyet sonradan bulunursa geçmiş olay değiştirilmez; `opening_cost_basis_supplied` olayı açılış iddiasına referans verir. Böylece “o tarihte ne biliyorduk?” izi de korunur.

## 3. V0 muhasebe olayları

Kullanıcının dokuz tipi doğru yönde, fakat üç düzeltme gerekiyor:

- `cash_flow_recorded` yalnız dış sermaye giriş/çıkışı olmalı; temettü ve ücretle karışmamalı.
- Uzlaştırma ekonomik hareket değildir; ayrı aile olmalı.
- Temettü hak edişi ile nakit tahsilatı ayrılmalı.

Önerdiğim çekirdek aile:

| Olay | Temel payload |
|---|---|
| `opening_account_state_asserted` | Hesap, as-of, nakitler, pozisyonlar, maliyet durumu, kaynak ekstre |
| `opening_cost_basis_supplied` | Açılış olayına referans, yeni lot/basis bilgisi, kaynak |
| `fill_recorded` | Hesap, security/listing, yön, adet, fiyat, brüt tutar, ücretler, trade/settlement date, broker fill kimliği |
| `external_cash_flow_recorded` | Katkı/çekim, para, efektif tarih, kaynak |
| `internal_cash_transfer_recorded` | Kaynak/hedef hesap, para, tarihler; TWR dış akışı sayılmaz |
| `fx_conversion_recorded` | Satılan para, alınan para, kur yöntemi, ücret, tarih |
| `dividend_entitlement_recorded` | Security, hak kazanan adet, ex-date, brüt hisse başı/tutar, ödeme tarihi |
| `dividend_settlement_recorded` | Entitlement ref, brüt, stopaj bileşenleri, ücret, net nakit, ödeme tarihi |
| `interest_recorded` | Tutar, para birimi, dönem, ödeme tarihi |
| `fee_recorded` | Ücret kategorisi, tutar, ilişkili işlem/hesap |
| `tax_withholding_recorded` | Vergi türü/yargı alanı, tutar, ilişkili gelir olayı; broker ayrı satır verirse |
| `corporate_action_recorded` | Action type, security bağlantıları, oran, adet/basis/nakit etkisi, effective date |
| `broker_account_snapshot_recorded` | Broker’ın belirli as-of’taki pozisyon, nakit ve varsa basis iddiası |
| `reconciliation_completed` | Snapshot ref, projector high-water mark, adet/nakit/basis boyutlarının ayrı sonuçları |

Buna lot karar ailesinde iki olay eklenir:

- `lot_disposition_instructed`
- `lot_disposition_confirmed`

`corporate_action_recorded`, serbest bir yama kanalı olmamalı; `action_type` alanına göre `split`, `reverse_split`, `spinoff`, `merger`, `return_of_capital`, `symbol_change`, `cash_in_lieu` gibi ayrık `oneOf` payload’ları bulunmalı.

Temettü konusunda önerim iki ekonomik olaydır. Ex-date’te alacak doğar, ödeme tarihinde nakit gelir. Tek settlement olayı kullanılırsa ex-date ile pay-date arasında NAV sahte düşüş gösterebilir. Settlement içinde:

```text
net = gross - withholding - fees
```

eşitliği contract validator tarafından doğrulanmalı. Stopaj broker’da ayrı hareket olarak gelmişse ayrıca `tax_withholding_recorded` yazılır; hem settlement bileşeni hem ayrı olay olarak iki kez sayılması yasaktır.

Bu, Türk vergi hesabının nasıl yapılacağına ilişkin bir hüküm değil; yalnız brüt gelir, kesinti ve net nakdin birbirinden kaybolmamasıdır.

## 4. Pozisyon ve lot projection’ı

Pozisyon projection’ında en az şunlar bulunmalı:

- `account_id`, `security_id`
- `projection_as_of`
- `input_event_high_water_mark`
- `input_manifest_hash`
- `projector_version`
- `total_quantity`
- `settled_quantity`
- `pending_buy_quantity`, `pending_sell_quantity`
- `position_currency`
- `cost_basis_status`
- varsa `total_cost_basis`, yalnız gösterim için `average_cost`
- `open_lots[]`
- `position_state`
- `reconciliation_status`
- `last_reconciled_at`
- bekleyen settlement/kurumsal işlem bayrakları

`position_state`:

- `open`
- `projected_flat`
- `confirmed_flat`
- `unknown`
- `disputed`

Fill’lerden sıfır türemesi yalnız `projected_flat` üretir. `confirmed_flat`, broker snapshot’ıyla adet sıfır uzlaştırıldığında kullanılabilir.

Lotların kendisi projection’dır. Alış fill’i, açılış iddiası veya kurumsal işlem lot yaratır/dönüştürür. Lot kaydı:

- `lot_id`
- `origin_event_id`
- `lot_kind`
- `acquired_on`
- `original_quantity`
- `open_quantity`
- `unit_cost_basis`
- `total_cost_basis`
- `currency`
- `basis_status`
- adjustment/source referansları

Ancak satışta hangi lotun kapatılacağı bir karardır; projection’a gömülemez. Bu nedenle:

- `lot_disposition_instructed`: satış fill/order ref, yöntem, seçilen lotlar ve adetler.
- `lot_disposition_confirmed`: broker’ın gerçekten uyguladığı lot eşlemesi ve kanıtı.

Eşleme yoksa adet azalabilir ama realized P&L `pending_lot_allocation` veya `unknown` kalır. Sistem sessizce FIFO varsaymamalı. ABD broker kayıtlarında belirli lot seçimi ile FIFO’nun maliyet tabanını farklılaştırması ve specific identification için broker teyidinin önemi [IRS Publication 550](https://www.irs.gov/publications/p550) tarafından da açıkça ayrılıyor; bu yalnız veri modelinin neden seçimi kaydetmesi gerektiğini destekler.

## 5. Şema dizini

Yeni fon şemalarını `schemas/fund/` altında toplamak doğru olur. Mevcut düz dosyaları taşımam; yalnız yeni alt sistemi ayrıştırırım.

İlk aile dosyaları yaklaşık şöyle olabilir:

```text
schemas/fund/
  common.schema.json
  identity.schema.json
  event-envelope.schema.json
  accounting-events.schema.json
  corporate-action-events.schema.json
  reconciliation-events.schema.json
  position-projection.schema.json
  lot-projection.schema.json
```

Her olay tipi için ayrı dosya açmaya gerek yok; aynı aile içindeki ayrık payload’lar `$defs` ve `oneOf` ile gruplanabilir.

Kod incelemesine göre mevcut şema yükleyicileri açık allowlist kullanıyor ve yolu `schemas` köküne ekliyor. Allowlist değerinin `fund/accounting-events.schema.json` olması teknik olarak yeterli; eski loader’ları veya mevcut şemaları taşımak gerekmiyor. Fon için valuation katmanındaki gibi ağ erişimine kapalı, bütün `$ref`leri önceden yükleyen ayrı bir registry kurulmalı.

Özet hüküm: üç kimliği şimdi koru, opening fill uydurma, uzlaştırmayı ekonomik olay sayma, lotu projection ama lot seçimini olay yap ve yeni fon şemalarını tek tek düz klasöre saçma.