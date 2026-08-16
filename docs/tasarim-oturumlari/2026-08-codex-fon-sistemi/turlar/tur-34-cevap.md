Capital policy v0 bir anlatı belgesi değil, **sermaye kararlarının çalıştırılabilir anayasası** olmalı. Bugünkü pozisyonlar, fiyatlar, tezler ve nakit miktarı policy’ye yazılmaz; bunlar portföy state’idir. Policy yalnız bu state üzerinde hangi kararların meşru olduğunu tanımlar.

Ayrıca `null` bir politika değildir. Her alan ya gerçek bir değer ya da `not_applicable`, `unbounded_by_policy`, `disabled` gibi açık bir hüküm taşımalıdır.

## 1. Asgari alan kümesi

| Bölüm | Asgari alanlar | Neden gerekli? | Yoksa sistem neyi veremez? |
|---|---|---|---|
| Kimlik ve yürürlük | `policy_id`, `version`, `effective_from`, `status`, `owner` | Her sermaye kararını yürürlükteki kurala bağlar | Bir kararın hangi kurallarla alındığı ve replay sonucu bilinemez |
| Amaç ve ufuk | `objective: absolute_return`, `underwriting_horizon`, `capital_review_cadence`, `change_required:false` | Benchmark’sız stratejinin zaman mantığını tanımlar | Aylık bakışın neden aylık işlem olmadığını açıklayamaz |
| Uygun yatırım | `long_only`, `common_stock_only`, `us_listed`, `leverage:false`, `shorting:false`, `options:false` | Sermayenin hangi araçlara gidebileceğini bağlayıcı yapar | Bir önerinin mandate’e uygunluğunu doğrulayamaz |
| Nakit politikası | `full_investment_required`, `operational_cash_floor`, `cash_target`, `cash_ceiling` | Dağıtılabilir sermayeyi ve fikirsizlik hâlini tanımlar | “Bu nakit kullanılmalı mı?” sorusunu cevaplayamaz |
| Portföy kapasitesi | `max_active_positions`, minimum sayının hard/soft niteliği, izleme bütçesi | Çeşitlendirmeyi tek operatör kapasitesine bağlar | Yeni pozisyonun operasyonel olarak kabul edilip edilemeyeceğini bilemez |
| Yoğunlaşma sınırları | `max_issuer_weight`, `max_sector_weight`, related-issuer toplama kuralı | İyi tezlerin aynı riski yığmasını engeller | Portföy-fit ve limit ihlali hesabı yapamaz |
| Boyutlandırma | `base_weight_formula`, readiness sınıfları/multiplier’ları, `min_economic_weight`, `max_position_weight` | Tezi deterministik hedef ağırlığa çevirir | “Ne kadar?” sorusunu veremez |
| Kayıp/risk bütçesi | Pozisyon başına `scenario_loss_budget_bps_nav`, portföy `stress_loss_review_threshold`, downside girdisi zorunluluğu | Ağırlığı fiyat oynaklığından değil tolere edilen kayıptan sınırlar | Matematiksel olarak savunulabilir üst pozisyon büyüklüğü üretilemez |
| İşlem politikası | Review kadansı, no-trade bandı, minimum ekonomik işlem, zorunlu işlem istisnaları | İnceleme ile işlem yapmayı ayırır | Hangi hedef farkının işlem doğuracağını bilemez |
| Ölçüm referansı | `base_currency`, resmi NAV zamanı, fiyat/FX kaynağı, performans yöntemi referansı | Ağırlık, risk bütçesi ve performansın ortak paydasını kurar | Yüzde NAV, P&L ve performans tutarlı hesaplanamaz |
| Değişiklik/override | Onay yetkisi, cooling-off, acil override süresi, geriye yürümeme kuralı | Piyasa baskısı altında politika gevşetmeyi görünür kılar | Limit değişikliği ile gerçek karar arasındaki fark kaybolur |

Capital policy’nin içinde olmaması gerekenler: güncel NAV, güncel nakit, pozisyonlar, lotlar, fiyatlar, aktif tezler ve broker fills. Bunlar policy’nin girdisidir.

## 2. Boyutlandırma: taban + tavanlı readiness eğimi

Senin önerdiğin yöntem doğru, fakat buna `conviction` değil **underwriting readiness** demeyi tercih ederim. Pitch’in “high confidence” demesi doğrudan daha büyük pozisyon yaratmamalı.

Temel formül:

```text
base_weight = deployable_capital_fraction / max_active_positions

readiness_weight = base_weight × readiness_multiplier

target_weight = min(
    readiness_weight,
    loss_budget_capacity,
    issuer_capacity,
    sector_capacity,
    cash_capacity,
    liquidity_capacity,
    max_position_weight
)
```

Nitel eğim yalnız aşağıdaki typed kanıtlardan türetilmeli:

- Tez kabul edilmiş ve `active`.
- Valuation anchor destekli ve güncel.
- Downside/thesis-break senaryosu tanımlı.
- İzleme sözleşmesi onaylı.
- Maddi veri boşluğu yok.
- Portföy çakışması ve yoğunlaşma kontrol edilmiş.
- Pozisyon/broker state’i biliniyor.

V0 için sade merdiven:

| Sınıf | Anlam | Örnek multiplier |
|---|---|---:|
| `watchlist` | Sermaye için hazır değil | `0.0×` |
| `starter` | Tez var; bazı belirsizlikler öğrenme pozisyonunu gerektiriyor | `0.5×` |
| `core` | Kanıt, downside, valuation ve izleme yeterli | `1.0×` |
| `exceptional` | Bütün koşullar güçlü ve açık insan onayı var | En fazla `1.25×` |

Son satırın V0’da hiç kullanılmaması da makul. Asıl ilke: readiness multiplier hiçbir hard risk limitini genişletemez.

Saf equal-weight’ten daha iyi çünkü araştırma olgunluğunu kullanıyor; saf conviction’dan daha iyi çünkü LLM sıfatını sermaye miktarına çevirmiyor; saf volatilite boyutlandırmasından daha iyi çünkü gap ve tez-kırılma riskini volatiliteyle karıştırmıyor.

## 3. Nakit: birinci sınıf state, artık sermaye

Mandate sabit nakit hedefinden çok **fikir varsa yatırım, yoksa bekleme** yaklaşımını ima ediyor:

- Pozisyon sayısını ekran belirliyor.
- Benchmark yok.
- Full-investment zorunluluğu yok.
- Aylık incelemede `change_required:false`.

Bu nedenle V0 için önerim:

```text
full_investment_required: false
cash_target: null / not_applicable
cash_ceiling: unbounded_by_policy
operational_cash_floor: kullanıcı tarafından belirlenmiş pozitif tutar/oran
```

Bu bir çelişki değildir. Nakit muhasebe ve risk açısından birinci sınıf pozisyondur; hedef tahsis açısından ise **kalan ve meşru bir seçenek**tir.

Yüksek nakit uyarı üretebilir ama otomatik yatırım zorunluluğu doğurmamalı. Beş uygun isim varsa ağırlıkları beşe bölüp %100’e normalize etmek yanlış olur; boş kapasite nakitte kalmalıdır.

## 4. Pozisyon sayısı: hard üst sınır, zorunlu alt sınır yok

Hard minimum pozisyon sayısı düşük kaliteli isim satın almaya zorlayabilir. Çeşitlendirme, minimum isim sayısından çok şu iki mekanizmayla sağlanmalı:

- Tek-isim ve sektör tavanları.
- Kalan sermayenin nakitte kalabilmesi.

Üst sınır ise gerçek ve operasyonel olmalı:

```text
weekly_capacity =
    fixed_portfolio_work
  + active_positions × quiet_week_minutes
  + event_reviews × incremental_event_minutes
```

`max_active_positions`, yoğun haftada toplamın 6–9 saati aşmayacağı sayı olmalıdır. İlk kalibrasyon için **10 aktif pozisyonluk hard cap** savunulabilir; iki gerçek earnings döngüsünden sonra ölçülerek değiştirilir.

Böylece:

- Yalnız üç isim barı geçerse üçü %33 olmaz; tavanlar uygulanır, kalan nakit olur.
- On birinci iyi isim çıkarsa otomatik eklenmez; mevcut on isimden biriyle fırsat maliyeti karşılaştırılır.
- Watchlist ve fonlanmamış tezler ayrı kapasite taşır; `max_active_positions` yalnız gerçek pozisyonları sayar, fakat toplam izleme yükü ayrıca sınırlanır.

İleride “soft diversification warning” eklenebilir; V0’da hard minimum gereksizdir.

## 5. İşlem eşiği: no-trade bandı + maliyet vetosu + durum override’ı

Katılıyorum: 3–18 aylık ufuk ile aylık inceleme arasındaki gerilimin doğru çözümü histerezistir. Fakat tek başına yüzde puan, işlem maliyeti veya tez değişimi yeterli değildir.

Her hedef ağırlığın bir no-trade bandı olmalı:

```text
band_half_width =
    max(
        absolute_weight_threshold,
        relative_threshold × target_weight
    )

trade_candidate =
    abs(current_weight - target_weight) > band_half_width
```

Bunun üstüne iki kural gelir:

- İşlem tutarı minimum ekonomik büyüklüğü ve maliyet vetosunu geçmeli.
- Tez/risk durumu bazı hâllerde bandı geçersiz kılmalı.

| Durum | Davranış |
|---|---|
| `active`, hedef değişmedi | Yalnız bandın dışındaysa işlem |
| `review_required` | Yeni alım dondurulur; otomatik satış gerekmez |
| `broken` veya `closed` | Hedef sıfıra iner; band uygulanmaz |
| Hard issuer/sector/cash ihlali | Düzeltici işlem önerisi zorunlu |
| Yeni starter | Hedef minimum ekonomik pozisyonu geçmiyorsa işlem yok |
| Sırf aylık tarih geldi | Varsayılan `no_change` |

İşlem maliyeti, sıvı ABD hisselerinde çoğu kez bağlayıcı olmayabilir; yine de spread/komisyon üzerinden veto olarak bulunmalı. Vergi etkisi tanımlanmamışsa sistem “vergi sonrası optimal” iddiasında bulunmamalı.

Özet kural:

> **Aylık ritim yeniden karar verme ritmidir, yeniden işlem yapma ritmi değildir.**

## 6. Capital policy değişiklik yönetimi

Capital policy’nin sahibi yalnız kullanıcıdır. Sistem değişiklik önerebilir ama kendisi etkinleştiremez.

Önerilen akış:

```text
capital_policy_change_proposed
→ current_book_impact_previewed
→ cooling_off
→ human_approved
→ capital_policy_activated
```

Kurallar:

- Her değişiklik yeni sürüm, gerekçe, diff ve `effective_from` taşır.
- Geriye yürüyemez; geçmiş kararlar o gün yürürlükte olan policy ile değerlendirilir.
- Mevcut portföye etkisi etkinleştirmeden önce gösterilir.
- Risk sıkılaştırması hemen etkinleşebilir.
- Risk gevşetmesi yalnız bir sonraki planlı policy incelemesinde ve bekleme süresinden sonra etkinleşir.
- Mevcut ihlali “yok etmek” için limit gevşetilemez; ihlal eski policy altında tarihsel olarak kalır.
- Acil istisna policy değişikliği değildir: gerekçeli, kapsamı dar ve süreli `policy_override` olur.
- Override sona erince kural kendiliğinden geri gelir.
- Her portfolio proposal kullanılan `capital_policy_version`ı taşır.

Sıklık olarak **üç aylık planlı policy incelemesi** öneririm. Aylık portföy incelemesinde policy yeniden tartışılmaz; yalnız uygulanır. Olağanüstü değişiklik mümkündür ama yukarıdaki governance’tan geçer.

## Sonuç

V0’ın karakteri şu olur:

- Benchmark’sız absolute-return.
- Full-investment zorunluluğu yok.
- Nakit meşru residual.
- Hard minimum pozisyon sayısı yok, başlangıçta 10 pozisyonluk operasyonel tavan.
- Taban ağırlık + evidence/readiness eğimi.
- Büyüklüğü conviction değil, en sıkı risk kısıtı belirler.
- Aylık review, varsayılan `no_change`.
- İşlem yalnız no-trade bandı, ekonomik eşik veya maddi tez/risk değişimiyle doğar.
- Policy kullanıcıya ait, sürümlü ve gevşetmeye karşı gecikmelidir.

Bir sonraki sayısal kararı belirleyen tek temel soru şudur: **Bir pozisyonun tanımlanmış downside senaryosunda portföy NAV’ından kaybetmesine izin verilecek azami tutar kaç baz puan olmalıdır?** Bu cevap, starter/core ağırlıklarından tek-isim tavanına kadar geri kalan sayıların çoğunu belirler.