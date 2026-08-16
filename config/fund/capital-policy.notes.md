# capital-policy.json — neden bu değerler

JSON yorum taşımadığı için gerekçeler burada. Bir değeri değiştirirseniz buraya
da bir satır yazın — üç ay sonra "bu sayı neden 100?" sorusunun cevabı burada
olmalı.

Sürüm: **0.1.0**, yürürlük **2026-08-16**.

## Kullanıcının verdiği kararlar (2026-08-16)

| Alan | Değer | Gerekçe |
|---|---|---|
| `measurement.base_currency` | `USD` | Bütün pozisyonlar ABD listeli ve fiyatlar zaten USD. Kanonik NAV'ı TL yapmak, portföy performansına kur hareketini karıştırır: −%15 drawdown basamağı hisseler yüzünden değil kur yüzünden tetiklenebilirdi. TL istenirse yalnız bağlam serisi olarak gösterilir, policy limitleri USD üzerinden bağlar. **Provisional değil** — bilinçli seçim. |
| `risk.position_loss_budget_bps_nav` | `100` (=%1 NAV) | Tasarımın çıpası. Bir pozisyonun kötü senaryosu gerçekleşirse NAV'ın en fazla %1'ini götürsün. −%30 downside'lı tipik bir isimde bu ≈ %3,3 ağırlık demek. 5-10 pozisyonluk kitapta çoğu zaman **bağlayıcı kısıt bu olacak** — yani boyutu iştah değil downside belirleyecek. Provisional: gerçek gözlemle kalibre edilecek. |
| `concentration.max_security_weight_bps` | `1000` (=%10) | Tek şirket hakkında tamamen yanılma ihtimaline karşı mutlak duvar. `max_active_positions: 10` ile eşit ağırlık tavanına denk. Kayıp bütçesi çoğu durumda daha erken bağladığı için bu limit yalnız çok düşük downside'lı isimlerde devreye girer. Provisional. |
| `objective.capital_horizon` | `over_3y` | Öngörülebilir çekim ihtiyacı yok. |
| `objective.liquidity_need_mode` | `none` | Aynı cevaptan. Nakit yalnız operasyonel taban kadar tutulur; ufuk uyumsuzluğu kısıtı yok. |

## Ajanın doldurduğu, kullanıcı onayı beklemeyen değerler

Tasarım Bölüm 3'teki başlangıç değerleri birebir alındı. Aşağıdakiler yalnız
ek açıklama gerektirenler.

| Alan | Değer | Gerekçe |
|---|---|---|
| `concentration.max_issuer_weight_bps` | `1000` (=%10) | Kullanıcıya ayrıca sorulmadı; security tavanına eşitlendi. Anlamı: bir şirketin iki hisse sınıfı (GOOG + GOOGL gibi) **birlikte** %10'u aşamaz. Security tavanından yüksek olması ancak çift sınıflı bir isimde bilinçli olarak daha fazla risk almak istenirse anlamlı olur. Provisional. |
| `sizing.readiness_multipliers` | `0 / 0,5 / 1 / disabled` | `watchlist: 0` yapısal — izleme listesi sermaye almaz. `exceptional` kapalı: core'un üstünde bir kademe açmak, "çok emindim" demenin pozisyonu büyütmesine izin vermek olurdu; readiness zaten conviction değil. `starter`/`core` provisional. |
| `risk.drawdown_response_ladder` | −%10 / −%15 / −%20 | Sırasıyla uyar, ekleme dondur, tam yeniden inceleme. Hiçbir basamak satış üretmez. Provisional — asıl soru basamakların yeri değil, doğru zamanda tetiklenip tetiklenmedikleri. |
| `trading.no_trade_band` | `max(100 bp, hedefin %20'si)` | Aylık karar ritmi ile 3-18 aylık ufuk arasındaki gerilimi çözer: ağırlık sürüklenmesi tek başına işlem sebebi değil. Provisional. |
| `cash.operational_floor_bps_nav` | `200` (=%2) | Ücret, temettü stopajı ve küsurat için operasyonel taban. `target: disabled` çünkü nakit hedeflenmiyor, artakalıyor. |
| `capacity.max_active_positions` | `10` | Ölçek varsayımının üst ucu. `base_weight = deployable / 10` hesabının paydası budur — değiştirmek bütün boyutlandırmayı kaydırır. Provisional. |
| `governance.loosening_cooling_off_days` | `7` | Sıkılaştırma hemen, gevşetme bir hafta bekler. Mevcut bir ihlali yok etmek için limit gevşetilemez (tasarım değişmez #12). |

## Provisional ne demek

`provisional_fields` içindeki her JSON Pointer, "bu sayı optimal olduğu için
değil, kalibre edilebilir bir çıpa olduğu için seçildi" demektir. Uygulama
planındaki **S2 kalibrasyon defteri** her biri için gerçek gözlem biriktirir:
kaç kez bağlayıcı oldu, kaç yanlış alarm üretti, kullanıcı kaç kez override
etti. Üç ayda bir (`governance.scheduled_review_cadence`) gözden geçirilir.

Listede **olmayan** alanlar mandate veya değişmez kaynaklıdır: `long_only`,
`shorting`/`leverage`/`derivatives: disabled`, `automatic_liquidation:
disabled`, `manual_execution_required: true`, `missing_input_behavior:
fail_closed`, `retroactive_changes: disabled`. Bunlar kalibrasyon konusu değil;
değişmeleri sistemin ne olduğunun değişmesi demek.

## Henüz doldurulmadı

`config/fund/fund-definition.json` (F0.1) — hangi broker hesabı ve hangi nakit
bu portföye dahil, açılış tarihi ne. Uydurulmadı: açılış kitabı girilirken
(uygulama planı F1.11) gerçek değerlerle yazılacak. O ana kadar hiçbir şeyi
bloklamıyor.
