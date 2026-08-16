Performans katmanı yalnız raporlama değildir; policy ve karar mekanizmasının doğruluk testi olmalıdır. Ancak üç gerçeği ayırmalı:

1. Para ne yaptı?
2. Tezde öngörülen dünya gerçekleşti mi?
3. Verilen karar, o anda mevcut bilgiyle kaliteli miydi?

Bunları tek “başarı” puanında birleştirmek yeniden sahte kesinlik üretir.

## 1. Getiri ölçüsü: TWR ve MWR birlikte

İkisi de gereklidir; farklı soruları cevaplar.

| Ölçü | Cevapladığı soru | Kullanımı |
|---|---|---|
| TWR | Dış nakit giriş/çıkışlarının zamanlamasından bağımsız olarak strateji nasıl performans gösterdi? | Birincil strateji/karar performansı |
| MWR/XIRR | Kullanıcının yatırdığı gerçek paranın zamanlamasıyla cebindeki sermaye ne yaptı? | Sahip deneyimi ve sermaye zamanlaması |
| P&L | Hangi dönemde kaç dolar kazanıldı/kaybedildi? | Muhasebe ve attribution |
| NAV/drawdown | Sermaye hangi yolu izledi, tepeden ne kadar düştü? | Risk ve path değerlendirmesi |

TWR, dış nakit akışı günlerinde alt dönemlere bölünüp zincirlenmeli. MWR, tarihli yatırma/çekme akışları ve bitiş NAV’ıyla XIRR olarak hesaplanmalı. Alım/satım ve temettü portföy içi hareketlerdir; dış nakit akışı değildir.

Benchmark yasağı ile referans serisi yasağı aynı şey değildir:

- **Benchmark:** Portföyün aktif ağırlık, tracking error ve göreli risk kararlarını belirleyen bağlayıcı karşılaştırma.
- **Hurdle:** Sermayenin aşması beklenen minimum sonuç; örneğin USD nakit getirisi veya açıkça seçilmiş mutlak getiri hedefi.
- **Context series:** S&P 500 veya enflasyon gibi yalnız “aynı dönemde dış dünya ne yaptı?” sorusunu cevaplayan seri.

Mandate benchmark varsaymayı yasaklıyor; bu, geniş endeksi bağlamsal olarak göstermeyi yasaklamaz. Ancak sistem `active_return`, `alpha` veya “endeksi yendi” dilini kullanmamalı.

V0 için:

- Birincil ölçü: TWR, drawdown ve policy ihlalleri.
- Sahip ölçüsü: MWR/XIRR.
- Başarı çıpası: kullanıcının açıkça seçtiği mutlak hurdle + drawdown bütçesi.
- Geniş endeks ve nakit getirisi: ancak `context_reference`, sermaye kararının girdisi değil.

Hurdle tanımlanmadan sistem “iyi/kötü” diyemez; yalnız “pozitif/negatif ve şu riske karşı şu getiri” diyebilir.

## 2. Attribution eksenleri

### Pozisyon attribution’ı

Her gün için:

- Başlangıç ağırlığı.
- Fiyat getirisi.
- Temettü katkısı.
- FX katkısı.
- Ücret/işlem maliyeti.
- Toplam bp NAV katkısı.

Nakit de ayrı katkı satırı olmalıdır. Böylece “hisseler kazandırdı ama fazla nakit drag yarattı” görünür olur.

### Tez attribution’ı

Her sermaye tahsisi bir `thesis_id` taşımalı. Fill’in vergi lotuna değil, onu doğuran karar/tez ilişkisine bağlanması yeterlidir.

Tez attribution’ı:

- Fonlanma tarihi ve tahsis edilen sermaye.
- Tez altında geçen ağırlıklı günler.
- Gerçekleşmiş/gerçekleşmemiş P&L.
- Temettü ve maliyetler.
- Azami drawdown.
- Tez kapanırken kalan exposure.
- Tez outcome sınıfı.

Bir tez kapanıp pozisyon wind-down’da kalırsa attribution eski teze bağlı devam eder. Yeni tez altında tutma kararı verilirse açık bir yeniden tahsis kararı gerekir; geçmiş sessizce yeni teze taşınmaz.

### Karar attribution’ı

Her onaylı sermaye kararında bir `decision_evaluation_contract` dondurulmalı:

- Kararın türü: initiate/add/trim/exit/replace/hold.
- Gerçekleşen hedef ve sermaye farkı.
- Statüko karşı-olgusu.
- Varsa seçilmiş alternatif.
- Değerlendirme ufku.
- Beklenen gözlemler/falsifier’lar.
- Kullanılacak fiyat, maliyet ve performans yöntemi.
- Kararın hangi olayla sona ereceği veya yeniden değerlendirileceği.

Replacement için temel ölçü:

```text
decision_value_add =
    actual_new_allocation_return
  - counterfactual_retained_allocation_return
  - incremental_costs
```

Aynı anda çok sayıda işlem yapıldıysa sahte tek-isim nedenselliği kurulmaz; bütün işlem paketi `decision_bundle` olarak statükoya karşı değerlendirilir, pozisyon katkıları yalnız alt kırılım olur.

## 3. İyi karar ile iyi sonuç ayrımı

Üç ayrı değerlendirme tutulmalı:

### Ex-ante süreç kalitesi

Karar anında şunlar mevcut muydu?

- Güncel ve kaynaklı veri.
- Kabul edilmiş tez ve valuation anchor.
- Downside senaryosu.
- Monitoring contract.
- Policy/limit kontrolü.
- Statüko ve gerçek alternatif.
- Binding constraint.
- Gerekçeli insan onayı.
- Gizlenmemiş eksiklik ve override.

Bu değerlendirme karar anındaki bilgilerle yapılır; sonuç görüldükten sonra yeniden yazılmaz.

### Tez/öngörü sonucu

Önceden yazılmış beklentiler gerçekleşti mi?

- KPI ve finansal beklentiler.
- Catalyst sonucu ve zamanlaması.
- Falsifier/kill koşulları.
- Yönetim davranışı veya rekabet varsayımı.
- Valuation/multiple varsayımı.
- Öngörülmeyen dış etkenler.

Sonuç sözlüğü örneğin:

```text
supported
partially_supported
falsified
unresolved
not_testable_due_to_missing_evidence
```

### Finansal sonuç

- TWR/P&L katkısı.
- Drawdown ve zaman altında kalma.
- Hurdle’a ve önceden seçilmiş counterfactual’a göre sonuç.
- Kullanılan risk bütçesine göre getiri/kayıp.

Bunlardan şu matris çıkar:

| Süreç | Finansal sonuç | Yorum |
|---|---|---|
| İyi | İyi | Amaçlanan başarı; yine de şans payı sıfır değildir |
| İyi | Kötü | Makul karar, olumsuz gerçekleşme; downside kalibrasyonu incelenir |
| Kötü | İyi | Şanslı kötü karar; yöntem ödüllendirilmez |
| Kötü | Kötü | Kaçınılabilir hata veya politika kusuru |

Falsifier, monitoring contract ve preview snapshot çok değerlidir ama tek başına yeterli değildir. Bunlar çoğunlukla “ne tezi öldürür?” sorusunu cevaplar. Ayrıca önceden yazılmış bir `claim_set` gerekir:

- Beklenen şirket sonucu.
- Beklenen dönem.
- Kabul edilebilir aralık.
- Bu sonucun yatırım görüşündeki önemi.
- Fiyat sonucuna bağlanan varsayım.

“Şirket beklendiği gibi yürüdü ama multiple daraldı” ile “şirket tezi bozuldu ama piyasa yükseldi” ancak böyle ayrılır. Nihai causal sınıflandırma insan adjudication’ı ister.

## 4. Counterfactual: ölçülmeli, fakat yalnız önceden dondurulmuşsa

Katılıyorum. Fiyatları izlemek ucuzdur; dürüst counterfactual kurmak pahalıdır.

Kurallar:

- Counterfactual karar anında oluşturulur; sonradan kazanan isim seçilmez.
- Yalnız gerçek karar alternatifleri izlenir: statüko ve proposal’daki en fazla bir-iki alternatif.
- Her Reject/C bucket ismi için sonsuz shadow book kurulmaz.
- Ağırlık, nakit, temettü, FX, corporate action ve maliyetler gerçek portföyle aynı yöntemle hesaplanır.
- Ufuk önceden belirlenir: sabit 1/3/6/12 ay veya kararın kendi catalyst/tez ufku.
- Satılmış pozisyon, “kaçırılan kazanç” diye değil replacement kararının statüko kolu olarak izlenir.
- Counterfactual sonuçları gerçek NAV’a karışmaz.

Sunum dili:

- Yanlış: “ADBE’yi satsaydın şu kadar kaçırdın.”
- Doğru: “Replacement kuralıyla verilen sekiz kararın beşinde challenger, önceden tanımlı ufukta incumbent’tan daha yüksek net katkı üretti; toplam incremental katkı −42 bp NAV.”

Counterfactual yalnız kural kalitesini sınar. Alternatif yolun o anda gerçekten uygulanabilir olduğunu kanıtlamaz; likidite, insan davranışı ve sonraki bilgi akışı hâlâ varsayımsaldır.

## 5. Küçük örneklemde anlamlı ölçüm

Yıllık 10–20 karar düzeyinde hit rate veya ortalama getiri istatistiksel hüküm vermez. Yine de veri değersiz değildir; yalnız doğru epistemik etiketle sunulmalıdır.

### Birinci öncelik: bütünlük ve süreç

- Policy’ye aykırı proposal sayısı.
- Kayıp bütçesi ihlalleri.
- Süresi geçen reconciliation.
- `position_unknown` geçirilen gün.
- Gecikmiş tez incelemeleri.
- İzleme sözleşmesiz fonlanmış pozisyon.
- No-trade bandı içindeyken yapılan işlemler.
- Override sayısı, süresi ve gerekçesi.
- Bayat veriyle alınan kararlar.
- Önceden tanımlanmamış counterfactual oranı.
- Turnover ve gereksiz işlem maliyeti.

Bunlar küçük örneklemde de kesindir: kural ya uygulanmıştır ya uygulanmamıştır.

### İkinci öncelik: sermaye yolu

- TWR ve MWR.
- Max drawdown.
- Time under water.
- Volatilite; küçük örneklem uyarısıyla.
- Nakit ağırlığı.
- Pozisyon/tez katkısı.
- Stress budget kullanımı.
- Turnover ve maliyetler.

### Üçüncü öncelik: karar kalibrasyonu

- Starter/core sayısı ve sonuç dağılımları.
- Tez `supported/falsified/unresolved` sayıları.
- Replacement incremental katkısı.
- Position sizing’in ex-ante risk bütçesine göre sonucu.
- Median ve dağılım; yalnız ortalama değil.
- Her metriğin yanında açık `n`.
- Güven aralığı veya en azından “insufficient sample” etiketi.

Bunları tek ağırlıklı puana dönüştürmezdim. Öncelik hiyerarşisi:

1. Muhasebe ve policy bütünlüğü bir geçiş kapısıdır.
2. Süreç uyumu erken dönemde ana öğrenme kaynağıdır.
3. Finansal sonuç zorunlu olarak raporlanır ama küçük örneklemde policy’yi tek başına değiştiremez.

Bir tek büyük kayıp istatistiksel kanıt olmayabilir; yine de risk bütçesini aşmışsa governance olayıdır.

## 6. Geri besleme

Performans katmanı policy’yi otomatik değiştirmemeli. Ürettiği şey:

```text
calibration_signal
policy_review_signal
process_breach
data_quality_issue
```

olmalıdır.

| Bulgudan doğan şey | Tepki |
|---|---|
| Muhasebe/reconciliation hatası | Hemen düzeltme; sermaye kararı bloklanabilir |
| Policy veya süreç ihlali | Hemen governance incelemesi |
| Tek kötü finansal sonuç | Karar postmortem’i; otomatik policy değişikliği yok |
| Birkaç benzer calibration sinyali | Üç aylık policy incelemesine hipotez |
| Yeterli ve karşılaştırılabilir cohort | Readiness/sizing/replacement kuralı değişiklik önerisi |
| Stratejinin temel amacında sorun | Daha uzun dönemli strateji incelemesi |

Örneğin core’ların starter’lardan kötü görünmesi tek başına readiness merdiveninin yanlış olduğunu göstermez. Önce şunlara bakılmalı:

- Aynı piyasa ve sektör dönemlerinde mi?
- Core’lar daha uzun tutulduğu için mi?
- Downside bütçesi ve ağırlık farkı hesaba katıldı mı?
- Tez outcome’u gerçekten daha mı kötüydü?
- Financial underperformance valuation/multiple kaynaklı mıydı?
- Örneklem kaç?

Replacement hurdle için de raw hit rate yerine:

- Net incremental bp NAV.
- Turnover ve maliyet sonrası sonuç.
- Downside/drawdown farkı.
- Statükodan vazgeçmenin risk katkısı.
- Önceden belirlenmiş ufukta sonuç.

raporlanmalı.

Policy değişikliği yine mevcut governance’tan geçer:

`calibration_hypothesis → cohort review → impact simulation → cooling-off → human approval → yeni policy version`

Risk sıkılaştırması hemen yapılabilir; sonuç kötü geldi diye risk gevşetmek bekleme süresini atlayamaz.

## Asgari yeni nesneler

Bu katmanın en küçük düzgün modeli altı nesne gerektirir:

- `external_cash_flow`
- `nav_snapshot`
- `performance_period`
- `attribution_record`
- `decision_evaluation_contract`
- `counterfactual_path`

Bunların üstünde üç aylık `performance_and_process_review` üretilir. Bu rapor policy’yi değiştirmez; yalnız değişiklik önerisine kanıt sağlar.

Net ilke:

> **P&L hakemdir ama öğretmen değildir; öğrenme, önceden dondurulmuş beklenti, süreç kaydı ve counterfactual ile birlikte gelir.**