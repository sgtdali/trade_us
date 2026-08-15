Ekonomik olarak büyük ölçüde haklısın: hedge, short ve kaldıraç yoksa risk yalnızca **neyi tuttuğun, ne kadar tuttuğun, toplam ne kadar yatırımda olduğun ve ne zaman azalttığın** üzerinden yönetilir.

Fakat bundan “ayrı risk katmanına gerek yok” sonucu çıkmaz. Risk araçları azdır; ölçülmesi gereken riskler az değildir. Doğru çözüm ayrı bir LLM/skill değil, portföy çekirdeğinin içinde deterministik bir `risk_engine`dır.

```text
pozisyonlar + nakit + piyasa + tez-driver bilgisi
→ portfolio_risk_snapshot
→ limit / assumption / drawdown kontrolleri
→ risk_breach veya review_required
→ portfolio_proposal
```

`portfolio-risk-management` yalnız sıra dışı downside, event-gap veya driver çakışmasını yorumlayan koşullu support olabilir; devamlı çalışan risk motorunun sahibi değildir.

## 1. Faktör modeli olmadan ortak sürücüler

`intended_alpha` tek başına yeterli değildir. Yalnız neyi kazanmak istediğimizi söyler; beraberinde taşıdığımız ortak riski söylemez.

V0 için tam faktör modeli yerine küçük, kontrollü bir **causal driver registry** öneririm:

```text
ai_capex
long_duration_rates
usd_strength
consumer_spending
cloud_optimization
china_export_controls
oil_price
power_demand
credit_cycle
regulatory_pricing
```

Bu liste baştan yüzlerce etiketle kurulmaz; yalnız gerçek portföyde görülen 8–15 maddi sürücü eklenir.

Her pozisyon için:

- `primary_driver_ids`
- `secondary_driver_ids`
- `known_confounding_driver_ids`
- `direction`: benefits / harmed / mixed
- `materiality`: primary / secondary
- `transmission_path`
- `as_of`
- `review_due_at`
- `confidence`
- `adjudicated_by`

LLM etiket önerebilir; kanonik eşlemeyi insan kabul eder. Yeni driver kimliği LLM tarafından sessizce icat edilemez.

Risk motoru ilk aşamada sahte factor beta hesaplamaz. Şunları gösterir:

- Aynı primary driver’a bağlı toplam portföy ağırlığı.
- Bu driver’a bağlı pozisyon sayısı.
- Tek bir olumsuz driver senaryosundaki toplam bp NAV kaybı.
- Driver’ın sektörler arasında ne kadar yayıldığı.
- En büyük üç ortak driver yoğunlaşması.

Sektör limitleri hard kalabilir; driver yoğunlaşması V0’da soft review threshold olmalıdır. Taksonomi yeterince sınanmadan “AI capex en fazla %25” gibi hard limit koymak erken olur.

Ek olarak 60/120 günlük rolling korelasyon basit bir anomali göstergesi olarak hesaplanabilir. Ancak korelasyon:

- Causal driver’ın yerine geçmez.
- Hard limit üretmez.
- Rejim değişiminde güvenilir sayılmaz.
- Yalnız “farklı sandığımız isimler birlikte hareket etmeye başladı” uyarısı üretir.

Yani iki sinyal birlikte kullanılır: driver etiketi nedensel hipotez, korelasyon ampirik alarmdır.

## 2. Drawdown’a tepki

Üçüncü seçeneği savunuyorum: **drawdown otomatik satış değil, zorunlu yeniden inceleme tetikleyicisidir.**

Drawdown eşikleri capital policy’de bulunur; hesaplama ve dispatch risk monitoring motorunun işidir. Drawdown ham NAV’dan değil, dış nakit akışlarından arındırılmış TWR wealth index’inden hesaplanmalıdır.

V0 için kalibrasyon çıpası:

| TWR drawdown | Otomatik sonuç | Sermaye sonucu |
|---|---|---|
| −10% | `drawdown_warning` | Tam portföy risk özeti; otomatik işlem yok |
| −15% | `drawdown_review_required` | Yeni add/initiate dondurulur; maddi kayıp sürücüleri yeniden incelenir |
| −20% | `full_reunderwrite_required` | Her fonlanmış tez yeniden adjudicate edilir; yeni risk, inceleme bitene kadar açılamaz |
| Daha ağır policy eşiği | `capital_preservation_review` | İnsan yeni cash/exposure hedefi belirler; yine mekanik toplu satış yok |

Bu sayılar evrensel gerçek değil, başlangıç çıpasıdır; kullanıcının drawdown toleransı bunları belirlemelidir.

İnceleme şunları ayırmalı:

- Piyasa-geneli multiple daralması.
- Aynı driver’a bağlı toplu kayıp.
- Tezlerin gerçekten bozulması.
- Downside senaryolarının yanlış kalibrasyonu.
- Pozisyonların policy’den büyük olması.
- Veri, fiyat veya reconciliation sorunu.

Drawdown nedeniyle risk azaltmak mümkündür; fakat sonuç review’dan çıkar. Fiyat düşüşü kendi başına “nakde geç” komutu değildir. Yeni risk dondurmak, dipte bütün kitabı satmaktan daha güvenli ara tepkidir.

Dondurma da fiyat toparlandı diye kalkmaz; zorunlu inceleme tamamlanınca kalkar.

## 3. Tek-isim gap riski

`max_position_weight` gereklidir ama tek başına yeterli açıklama değildir. İki ayrı koruma gerekir:

1. **Mutlak tek-isim tavanı:** Downside modeli yanlış olsa bile pozisyonun NAV içindeki en büyük payını sınırlar.
2. **Gap/tail kapasitesi:** Pozisyonun makul bir ani düşüş senaryosunda yaratacağı NAV kaybını sınırlar.

```text
gap_loss_bps_nav =
    position_weight × assumed_gap_return × 10,000

gap_capacity_weight =
    allowed_gap_loss_bps / absolute_assumed_gap_return
```

Hedef kapasite:

```text
policy_compliant_max_weight = min(
    readiness_capacity,
    thesis_downside_capacity,
    gap_capacity,
    max_position_weight,
    issuer_capacity,
    sector_capacity,
    cash_capacity
)
```

Gap risk sınıfları sade tutulabilir:

| Sınıf | Örnek yapı | Yaklaşım |
|---|---|---|
| `ordinary` | Çeşitlendirilmiş, likit büyük şirket | Standart gap varsayımı |
| `elevated` | Tek ürün/müşteri, düzenleyici veya bilanço riski | Daha ağır gap varsayımı |
| `binary` | FDA, dava, solvency veya tek olay sonucu | Çok küçük pozisyon veya sahip olmama |

`max_position_weight`, sıfıra gidişte mutlak kaybı sınırlar. Gap kapasitesi ise daha gerçekçi −30/−40% olayında risk bütçesinin ne kadar kullanıldığını gösterir. İkisi birbirinin alternatifi değildir.

## 4. Likidite ve geçici varsayımlar

“Likidite uygulanmıyor” kalıcı policy hükmü olarak yanlıştır. Doğru ifade:

> Likidite kısıtı mevcut NAV ve hedef büyüklüklerde bağlayıcı değildir.

Bu hüküm ölçülebilir bir varsayım olmalıdır:

```text
policy_assumption:
  assumption_id
  assumption_type
  predicate
  observed_value
  source
  observed_at
  review_due_at
  reevaluate_on
  failure_action
  status
```

Likidite için predicate örneği:

```text
normal_exit_days <= policy.max_normal_exit_days
and
stress_exit_days <= policy.max_stress_exit_days
and
position_percent_adv <= policy.max_participation
```

Normal ve stres hesabı ayrı yapılmalı:

- Normal çıkış: tanımlı ADV katılım oranı.
- Stres çıkış: daha düşük ADV katılımı ve olumsuz fiyat sonrası pozisyon değeri.
- 30 ve 90 günlük dollar ADV.
- Güncel ve proposed pozisyonun ayrı hesabı.

Varsayım şu olaylarda yeniden hesaplanır:

- NAV veya dış sermaye akışı maddi değişti.
- Hedef pozisyon ağırlığı değişti.
- Fiyat veya ADV maddi değişti.
- Yeni security investable set’e girdi.
- Aylık review geldi.

Predicate bozulursa capital policy değişmez; yalnız daha önce bağlayıcı olmayan likidite kısıtı artık proposal’da binding olur. Gerekirse yeni alımı bloklar.

Genel mekanizma doğru, fakat serbest metinli bir `assumption_valid_while` DSL’i kurmazdım. V0’da typed varsayım aileleri yeterlidir:

- `liquidity_non_binding`
- `transaction_cost_immaterial`
- `fx_exposure_immaterial`
- `price_source_sufficient`
- `single_broker_snapshot_sufficient`

Her biri ölçülebilir predicate ve failure action taşır.

## 5. Stop loss

Önce önemli düzeltme:

> **Kayıp bütçesi stop değildir. Kayıp bütçesi pozisyon açılmadan önce uygulanan boyutlandırma sınırıdır.**

Üç farklı kavram vardır:

| Kavram | Ne yapar? | V1 hükmü |
|---|---|---|
| Fiyat stop’u | Fiyat belirli seviyeyi geçince satışı tetikler | Otomatik satış için kullanılmaz |
| Tez stop’u | Önceden tanımlanmış şirket/iş varsayımı bozulunca hedefi yeniden değerlendirir | Esas fundamental exit mekanizması |
| Risk-review fiyatı | Büyük/olağandışı fiyat hareketinde zorunlu inceleme başlatır | Kullanılır |

Temel sorun: fiyat stop’u gap riskini koruyamaz. Hisse −35% açılırsa −15% stop seviyesinde işlem yapılamaz. Üstelik 3–18 aylık temel analiz ufkunda piyasa volatilitesini tez bozulmasıyla karıştırabilir.

Fiyatın yine de dört meşru rolü vardır:

- Beklenmeyen büyük hareket için `price_move_review_required`.
- Valuation anchor’ın güncellenmesi.
- Pozisyon ağırlığının policy limitine sürüklenmesi.
- Piyasanın yeni bilgi taşıdığı ihtimaliyle tez re-underwrite’ı.

Önerilen kural:

```text
price threshold crossed
→ automatic sell değil
→ adds_frozen + evidence_check + reunderwrite_required
```

İstisna fiyat değil, başka bir hard gerçektir: delisting, fraud kanıtı, solvency olayı, tez `broken/closed` veya policy ihlali hedef ağırlığı sıfıra indirebilir. Fiyat yalnız bu incelemeyi uyandırır.

## Sonuç

Risk yönetimi bu sistemde bir hedge üretme işi değildir:

```text
risk ölçümü
→ ağırlık/nakit/sahip olmama sınırı
→ zorunlu review
→ insan onaylı target değişikliği
```

İlk risk katmanının asgari nesneleri şunlardır:

- `portfolio_risk_snapshot`
- `position_gap_risk`
- `risk_driver_registry`
- `position_driver_exposure`
- `policy_assumption`
- `drawdown_episode`
- `risk_breach`

Net ilke:

> **Long-only fonda risk motorunun görevi zararı fiyat stop’uyla kovalamak değil, sermayeyi hata gerçekleşmeden önce sınırlamak ve gerçekleşen fiyat hareketinin tez mi, ortak driver mı, yoksa gürültü mü olduğunu zorunlu olarak yeniden sordurmaktır.**