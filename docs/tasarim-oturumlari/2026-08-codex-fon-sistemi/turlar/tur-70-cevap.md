## 1. Bir yıl sonra ne bozulur?

Bunların tamamı gerçek bozulma yollarıdır; en olası sıralama şöyledir:

| Bozulma | Olasılık | Sistem nasıl fark eder? |
|---|---:|---|
| Metrik/XBRL eşlemesi kayar | Yüksek | Beklenen filing geldikten sonra metriğin üretilememesi, birim/dönem değişimi, kaynak accession değişimi |
| Plugin/skill çıktısı contract’tan sapar | Yüksek | Sürüm sabitleme, şema doğrulama, contract testleri |
| Dispatch kuralı hiç veya aşırı ateşler | Orta-yüksek | Kural bazında son ateşleme, beklenen/gerçek sayı ve job üretim istatistiği |
| Fiyat/veri kaynağının semantiği değişir | Orta | Kaynak kimliği, timestamp, kapsam ve uç değer kontrolleri |
| Tez sözleşmesi ekonomik olarak bayatlar | Kesin | Teknik validation yakalayamaz; periyodik insan incelemesi gerekir |

En kritik ek mekanizma bir **izleme canlılığı denetimi** olmalıdır. Her aktif tez için sistem şunları göstermelidir:

```text
son ilgili filing
son başarılı monitoring check
son unavailable sonucu
arka arkaya unavailable sayısı
son insan değerlendirmesi
bir sonraki beklenen kanıt veya review_due
monitoring_coverage: healthy | degraded | blind
```

Kurallar:

- İlgili filing geldiği hâlde bir mekanik kural değerlendirilemediyse `degraded`.
- Aynı kural iki ilgili kanıt döneminde üst üste `unavailable` kaldıysa `blind`.
- `blind` tez Q0’a düşer; yeni risk artırımı bloklanır.
- `unavailable`, asla başarılı kontrol veya “sapma yok” sayılmaz.
- Aylık review, yalnızca tez sonucunu değil **izleme kapsamını** da kontrol eder.

Dispatch için de küçük bir sağlık raporu gerekir:

```text
rule_id | enabled | last_observed | last_dispatched | jobs_30d | failures_30d
```

Sistem her şeyi kendi kendine düzeltemez; fakat sessiz bozulmayı görünür ve bloke edici hâle getirebilir. Plugin sürümü otomatik yükseltilmemeli; yeni sürüm önce contract fixture’larından geçmelidir.

## 2. İnsan pasifleşir mi?

**Evet. Otomasyonun en ciddi bedeli budur.** Hazır hükmü kabul etmek, bağımsız hüküm üretmekten bilişsel olarak çok daha kolaydır.

Tamamen çözülemez; azaltılabilir:

1. **İki aşamalı ekran korunur.** İlk aşamada sermaye etkisi, mevcut ağırlık ve P&L gösterilmez.

2. **Tek tıkla kabul yoktur.** Kullanıcı en az şu üç soruya kapalı cevap verir:

   - Kritik kaynakları kontrol ettim mi?
   - Bu pozisyona sahip olmasaydım aynı downside’ı kabul eder miydim?
   - Önceki assessment’a göre değişimin ana nedeni nedir?

3. **Maddi değişiklikte gerekçe zorunludur.** Readiness değişimi veya downside’da örneğin 500 bp üzeri değişim, kısa bir insan gerekçesi ister.

4. **Periyodik kör kontrol yapılır.** Her çeyrekte en az bir tez `independent_then_reconcile` modunda, önceki assessment ve model önerisi gösterilmeden değerlendirilir.

5. **Törensel kabul ölçülür.** Şunlar kalite sinyalidir:

   - Art arda değiştirmeden kabul oranı
   - Çok kısa adjudication sayısı
   - Kaynak açılmadan verilen kabuller
   - Her route için reject/human-authored oranı
   - Sonradan geri alınan kabuller

Bunlar otomatik olarak “kullanıcı düşünmedi” hükmü vermez. Ancak örneğin son 10 maddi review’un 10’u da kısa sürede ve değişikliksiz kabul edilmişse sistem `adjudication_quality_warning` göstermelidir.

Amaç insanı form doldurmaya zorlamak değil; sistemin “insan değerlendirdi” iddiasını gerçek davranışla desteklemektir.

## 3. Yanlış alarm bütçesi

8 tez × yılda 2–4 filing × tez başına 1–2 mekanik kural yaklaşık **16–64 kural değerlendirmesi** demektir. Bunların kaçının breach olacağını dürüstçe önceden bilemeyiz.

Başlangıç için makul operasyon hedefi:

- Yılda toplam **4–8 anlamlı `review_required`**
- Tez başına ortalama yılda **0–2**
- **12’den fazla** toplam alarm veya bir çeyrekte tezlerin üçte birinden fazlasının alarm vermesi: kalibrasyon incelemesi
- Alarmların yarısından fazlası iki dönem boyunca “doğru hesaplanmış ama karar açısından önemsiz” çıkarsa: kural faydasızdır

Burada “yanlış alarm” ikiye ayrılmalıdır:

- `measurement_error`: veri/eşleme yanlış; kural tamir edilir.
- `decision_irrelevant_breach`: eşik gerçekten aşılmış ama sermaye hükmünü değiştirecek kadar anlamlı değil; eşik veya kural tasarımı gözden geçirilir.

Eşikler alarm sayısını azaltmak için optimize edilmemeli; tezin önceden yazılmış falsifier’ından türemelidir. Gürültüyü azaltmak için:

- Tek dönemlik küçük sapmalarda tolerans/histerezis
- Gerekliyse art arda iki dönem doğrulaması
- Baseline’a göre anlamlı değişim
- Aynı kanıt için kesin dedup
- Birbirinin kopyası kuralların birleştirilmesi

İlk yıl bir **kalibrasyon dönemi** olmalıdır, fakat “sonuç hoşuma gitmedi, eşiği değiştirdim” dönemi değildir. Her değişiklik gerekçeli yeni contract sürümüdür; eski sonuçlar eski kuralla korunur.

## 4. Otomatikleştirilmeyen kalan sınır

| Konu | Hüküm | Gerekçe |
|---|---|---|
| Discovery/yeni aday üretimi | **Ertelenmemeli, fakat izleme dikey diliminden sonra eklenmeli** | Kullanıcının araştırma operasyonunu otomatikleştirme hedefinin parçasıdır; periyodik `idea-generation` sabit dispatch kuralıyla ilk kullanılabilir sürüme girmelidir. |
| Çok seçenekli `portfolio_proposal` | Ertelenebilir | Sekiz pozisyonda çoklu optimize portföyler yapay kesinlik üretir; ancak tek işlem için deterministik `trade-preview` ertelenmemelidir. |
| Attribution | Ertelenebilir | Hesaplanabilir katkı için yeterli karar ve tutma dönemi birikmeden yüzeyin çoğu boş kalır. |
| Counterfactual | Ertelenebilir | Yalnız karar anında dondurulmuş alternatiflerle anlamlıdır; önce gerçek decision record’ları birikmelidir. |
| A0–A4 merdiveni | Tam hâli ertelenebilir | Başlangıçta `shadow` ve `live_manual_execution` ayrımı yeterlidir; daha ince yetki kademeleri gerçek ihtiyaç doğarsa eklenir. |
| `capital_input_manifest` | Yapılmamalı | Küçük sistemde kabul edilmiş assessment ile decision record aynı kanıt zincirini daha sade biçimde taşır. |
| Genel capability router/episode/support bütçesi | Yapılmamalı | Sabit dispatch tablosu ve kapalı recipe’ler sekiz tez için yeterlidir. |
| Tezin otomatik `broken/closed` yapılması | Yapılmamalı | Otomasyon kanıt toplar ve `review_required` üretir; lifecycle hükmü insana aittir. |

Düzeltmem gereken tek nokta discovery’dir: bunu belirsiz bir geleceğe bırakmak, kullanıcının otomatik araştırma operasyonu talebiyle çelişirdi. Doğru sıralama şudur:

**Önce mevcut kitabı kendi kendine izleyen sistem → ardından aynı sabit dispatch mekanizmasıyla düşük frekanslı otomatik discovery.**

Bu, kapsam dışına çıkarma değil, hata ayıklanabilir bir uygulama sırasıdır.