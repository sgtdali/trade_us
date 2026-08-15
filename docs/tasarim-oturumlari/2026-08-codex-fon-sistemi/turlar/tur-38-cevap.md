Bu köprünün temel ilkesi üç ayrı gerçeği birbirine karıştırmamaktır:

1. **Karar niyeti:** Onaylanan hedef ağırlık ve risk sınırı.
2. **İnsan icrası:** Broker’a gerçekte ne girildiği.
3. **Broker gerçeği:** Gerçekte neyin, kaç adet ve hangi fiyattan gerçekleştiği.

İnsan farklı davranınca karar geçmişi yeniden yazılmaz; broker gerçeği de policy’ye uymuyor diye reddedilmez.

## 1. Proposal zaman aşımı ve fiyat değişimi

Doğru yaklaşım **(a) + (c)**:

- İnsan hedef ağırlığı/bandı onaylar.
- Adet, en güncel NAV, nakit, pozisyon ve fiyatla icra anında yeniden hesaplanır.
- Ancak yeni hesap onaylanan geçerlilik sınırlarını aşıyorsa yeniden onay gerekir.

Dolayısıyla proposal yalnız `valid_until` değil bir `validity_contract` taşımalıdır:

```text
valid_until
reference_price
approved_price_band
approved_weight_band
max_cash_impact
max_downside_loss_bps
required_policy_version
required_portfolio_snapshot_state
invalidation_events
```

İcra anındaki adet:

```text
execution_quantity =
    floor(
        (target_weight × current_nav - current_position_value)
        / current_price
    )
```

Kesirli hisse kullanılmıyorsa rounding farkı nakitte kalır.

Fiyat toleransı karar türüne göre değişmelidir:

| Karar | Fiyat değişiminin etkisi |
|---|---|
| Initiate/add/replace | Valuation ve reward/downside değiştiği için dar tolerans |
| Ağırlık drift’i nedeniyle trim | Adet yeniden hesaplanır; ağırlık bandı esas |
| `broken/closed` nedeniyle exit | Fiyat değişimi çıkış gerekçesini ortadan kaldırmaz |
| Hard risk remediation | Risk azaltma amacı sürer; yalnız adet/nakit yeniden hesaplanır |

V0 için initiate/add kararlarında **%2–3 fiyat hareketi** yeniden onay çıpası olabilir. Daha doğrusu fiyat bandı şu üçünün kesişimi olmalıdır:

- Policy’deki yüzde toleransı.
- Valuation anchor’ın hâlâ geçerli olduğu fiyat aralığı.
- Onaylanan downside kayıp bütçesini aşmayan aralık.

Cuma üretilip cumartesi onaylanan proposal pazartesi açılışında bu testten geçer. %3 hareket policy toleransını aşıyorsa ticket yenilenmez; proposal `reapproval_required` olur.

`valid_until` için başlangıç yaklaşımı: discretionary alım/replace kararı, onaydan sonraki ilk işlem seansının sonuna kadar geçerli; çok günlük icrada kalan adet her seans yeniden doğrulanır.

## 2. İnsan farklı bir şey yaparsa

### 100 yerine 60 aldı

Gerçek fills kaydedilir. Plan:

```text
execution_status: partially_executed
approved_quantity_at_submission: 100
filled_quantity: 60
remaining_quantity: 40
target_gap: ...
```

Kalan niyet proposal geçerliyse açık kalabilir. İnsan bilinçli olarak durduysa `execution_deviation` ve gerekçe gerekir.

### Hiç almadı

Proposal portföyü değiştirmiş sayılmaz:

```text
execution_status: expired_unexecuted | declined_at_execution
```

Neden sınıflandırılır: fiyat bandı aşıldı, nakit yoktu, insan vazgeçti, broker sorunu, unutuldu. Unutulmuş onaylı işlem operatör kuyruğuna düşmelidir.

### Listede olmayan bir şey aldı

Gerçek fill değişmez biçimde kaydedilir:

```text
unplanned_fill_observed
post_trade_exception_review_required
```

Pozisyon şu durumda olur:

```text
position_state: open
policy_state: unadjudicated
thesis_link: missing
readiness: unknown
loss_budget: not_assessed
```

Sistem gerçeği reddetmez ama normal pozisyon gibi kabul de etmez:

- Yeni risk eklemek bloklanır.
- Policy uygunluğu hesaplanır.
- Uygun araç değilse hard breach oluşur.
- İnsan “elde tutup sonradan araştırma yap”, “mevcut teze bağla” veya “çıkış proposal’ı üret” kararlarından birini verir.
- Sonradan tez bağlanırsa `linked_post_execution:true` kalır; geçmişe onay uydurulmaz.

Bu ayrım çok önemli:

> Broker pozisyonun varlığında otoritedir; sistem pozisyonun meşruiyetinde otoritedir.

## 3. Kısmi ve çok parçalı gerçekleşme

Her fill ayrı kanonik kayıt olmalıdır:

- Broker işlem/fill kimliği varsa o.
- Yoksa import batch kimliği, satır sırası ve ham satır hash’i.
- Zaman.
- Security.
- Side.
- Adet.
- Fiyat.
- Para birimi.
- Komisyon/ücret.
- Settlement tarihi.
- Kaynak.

Toplulaştırma yalnız projection’dır:

```text
requested_quantity
filled_quantity
remaining_quantity
fill_vwap
total_fees
first_fill_at
last_fill_at
```

Durum makinesi:

```text
staged
→ submitted
→ partially_filled
→ filled
  | cancelled
  | expired
  | partially_filled_cancelled
```

Kısmen dolup iptal edilmek “başarısız fill” değildir; terminal bir **execution outcome**dur. Fakat hedefe ulaşılamadığı için ayrıca:

```text
implementation_status: target_not_reached
```

oluşur.

Kalan hedef no-trade toleransından büyükse yeni proposal/ticket gerekir. Eski ve süresi dolmuş order niyeti sessizce yeniden açılmaz.

Çok günlük icrada geçmiş fills geri alınmaz; yalnız kalan miktar, her yeni seans başında güncel NAV/fiyat/policy’ye göre yeniden hesaplanır.

## 4. Reconciliation’ın anlamı

`reconciled` tek boolean olmamalıdır:

| Boyut | Ne eşleşir? | Sermaye kararını bloklar mı? |
|---|---|---|
| Position | Security ve adet | Evet |
| Cash | Para birimi bazında settled/unsettled nakit | Evet |
| Transactions | Fill, ücret, temettü, nakit akışı | Performans kapanışını bloklar |
| Cost basis | Broker ile iç maliyet kaydı | Vergi/realized P&L’yi bloklayabilir |
| Corporate actions | Split, merger, spin-off, cash-in-lieu | Pozisyon/NAV’ı bloklar |

`portfolio_reconciled` ancak policy’nin zorunlu saydığı bütün boyutlar geçince söylenebilir; her boyut `as_of` taşır.

Önerilen ritim:

- **Her işlem günü sonunda:** fills + pozisyon + nakit hızlı uzlaştırma.
- **Haftalık:** işlem olmasa da pozisyon ve nakit snapshot’ı.
- **Aylık ekstre kapanışında:** fills, fees, dividends, interest, external flows, cost basis ve corporate actions tam uzlaştırma.

Sistem 100, broker 97 diyorsa sistem eski olayı değiştirmez:

```text
book_quantity: 100
broker_quantity: 97
reconciliation_status: discrepancy
new_risk_blocked: true
```

İnsan nedeni çözer:

- Eksik fill → yeni fill kaydı.
- Yanlış manuel giriş → düzeltici olay.
- Split/corporate action → ilgili olay.
- Broker hatası → belgelenmiş broker düzeltmesi.

Broker snapshot’ı gerçek exposure için esas gözlemdir; fakat uyuşmazlık çözülene kadar state `position_unknown/disputed` kalır. Yeni alım bloklanır. Risk azaltıcı işlem gerekiyorsa insan broker ekranındaki teyitli miktarla hareket eder.

## 5. Nakit, temettü ve ücretler

En ucuz ve güvenilir yol farktan olay tahmin etmek değil, broker activity/statement export’unu ayrıştırmaktır:

- Deposit/withdrawal.
- Dividend.
- Withholding tax.
- Interest.
- Commission/fee.
- Trade settlement.
- Cash-in-lieu.
- Corporate-action cash.

API gerekmiyor. CSV/OFX export varsa deterministik importer; yalnız PDF varsa yapılandırılmış import önizlemesi ve insan onayı kullanılabilir.

Net nakit farkı doğrudan `cash_adjustment` diye yazılmamalıdır. Kaynak bilinmiyorsa:

```text
unexplained_cash_difference
```

oluşur ve attribution tamamlanmaz.

Tolerans farkın silinip silinmeyeceğini değil, ciddiyetini belirler. Her fark kaydedilir.

V0 için başlangıç çıpası:

- Pozisyon adedi: sıfır tolerans.
- Bilgi amaçlı küçük nakit farkı: `≤ max(1 USD, 0.1 bp NAV)`.
- Uyarı: bunun üstü.
- Sermaye kararını bloklayan fark: `> max(10 USD, 1 bp NAV)`.

Büyük NAV’da aşırı tolerans oluşmaması için mutlak üst sınır ayrıca konabilir. Bilinen settlement veya faiz timing farkı “açıklanamayan” sayılmaz; açık bir timing kalemi olarak taşınır.

Cost basis için broker vergi otoritesidir. Sistem ekonomik performansı kendi fill/cash kayıtlarından hesaplayabilir; farklılık giderilene kadar vergiye ilişkin sonuç üretmez.

## 6. İnsan yükü

On pozisyon, düşük turnover ve düzgün bir statement importer varsayımıyla:

| Hafta | Tahmini icra + reconciliation yükü |
|---|---:|
| İşlemsiz normal hafta | 20–35 dakika |
| 1–3 işlemli hafta | 45–90 dakika |
| Aylık ekstre kapanışı | İlave 30–60 dakika |
| Uyuşmazlık/corporate action haftası | 1–2 saat ek yük |

Yıllık ortalama yaklaşık **0,5–1,5 saat/hafta**, yoğun haftada **1,5–2,5 saat** beklerdim. Her hafta düzenli iki saati aşıyorsa üç ihtimal vardır:

- Turnover policy’ye göre fazla yüksektir.
- Broker verisi gereksiz yere elle giriliyordur.
- Reconciliation yüzeyi exception-driven değildir.

Yükü en çok azaltacak tek şey:

> **Broker CSV/OFX/activity export’unu idempotent biçimde içeri alan, satırları typed fill/cash activity’ye dönüştüren ve insana yalnız uyuşmazlıkları gösteren bir importer.**

Tam broker API’sinden önce bu yapılmalı. İkinci kazanç, approved proposal’dan broker ekranına elle kopyalanabilecek kısa bir trade ticket üretmektir.

Asgari köprü nesneleri:

- `execution_plan`
- `trade_ticket`
- `broker_order_observation`
- `fill`
- `cash_activity`
- `reconciliation_snapshot`
- `reconciliation_discrepancy`
- `execution_deviation`

Net ilke:

> **Karar ağırlık ve risk sınırı olarak onaylanır; adet icra anında türetilir; broker gerçeği hiçbir zaman reddedilmez, fakat policy dışı gerçekler normalleştirilmeden önce açık bir istisna olarak yönetilir.**