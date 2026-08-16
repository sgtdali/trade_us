## 1. Gölge koşu nedir?

Gölge koşu, sistemin gerçek portföy verisiyle gerçek zamanlı proposal üretmesi fakat bu proposal’ın hiçbir sermaye yetkisi taşımamasıdır. İnsan mevcut karar sürecini bağımsız yürütür.

Doğru sıra iki ayrı aşamadır:

1. **Kör paralel koşu:** Sistem proposal’ını dondurur ve mühürler; kullanıcı kendi karar niyetini kaydetmeden sistem çıktısını görmez. Bu, karar farkını ölçer.
2. **Kâğıt icra:** Kullanıcı sistem proposal’ını görüp simülasyonda onaylar; adet, fiyat toleransı, kısmi fill, expiry ve reconciliation çalıştırılır fakat broker emri verilmez. Bu, uygulanabilirliği ölçer.

Küçük tutarlı gerçek işlem ikinci aşama değildir; artık sınırlı canlı pilottur. Önce kör gölge, sonra kâğıt icra, sonra sınırlı canlı yetki gelmelidir.

İnsanın ve sistemin kararları farklı `as_of` veya kanıt setlerine dayanıyorsa karşılaştırılmamalıdır. Gölge karşılaştırmasının anahtarı “aynı hafta” değil, mümkün olduğunca aynı karar snapshot’ıdır.

## 2. Gölge koşuda ne kaydedilir?

Aynı kanonik event store’da tutulmalıdır; fakat accounting projection’a girmemelidir.

Gerekli gerçekler:

- `shadow_proposal_created`
- `independent_human_decision_recorded`
- `shadow_proposal_revealed`
- `shadow_decision_compared`
- Gerekirse `shadow_execution_simulated`
- `shadow_outcome_observed`

Her shadow proposal şunları taşır:

- `authority_mode: shadow`
- Policy, engine ve input-manifest hash’leri
- Üretildiği ve açığa çıkarıldığı zaman
- Hedef/band/trade önerisi
- Binding constraint’ler
- `capital_effect: none`

Üç sert kural gerekir:

- Shadow proposal kanonik pozisyonu, nakdi veya NAV’ı değiştiremez.
- Shadow counterfactual portföy ayrı bir simulation projection’dır; resmî NAV değildir.
- Shadow proposal sonradan “canlıya yükseltilemez”; canlı karar gerekiyorsa güncel snapshot’tan yeni proposal üretilir.

İnsan farklı davrandığında bu `execution_deviation` değildir. O terim yalnız yetkili ve onaylanmış canlı proposal’dan sapmayı ifade eder.

## 3. Yetki merdiveni

| Seviye | Sistem ne yapar? | İnsan ne yapar? | İlerleme kapısı |
|---|---|---|---|
| A0 — Kayıt | Broker gerçeği, NAV ve risk görünümü üretir; sermaye önermez. | Normal kararlarını verir ve işlemleri girer. | Açılış kitabı ve bir statement dönemi pozisyon/nakit bazında uzlaştırılmıştır. |
| A1 — Kör gölge | Gerçek snapshot’tan mühürlü proposal üretir; karar öncesinde göstermez. | Bağımsız karar niyetini ve gerekçesini kaydeder. | İki aylık döngü + bir event-driven vaka; bütün farklar sınıflandırılmış, hard failure yoktur. |
| A2 — Kâğıt icra | Proposal’ı gösterir; order/fill/expiry/reconciliation’ı simüle eder. | Proposal’ı kabul/reddeder ama broker’da uygulamaz. | Fiyat geçersizleşmesi, kısmi fill, iptal ve reconciliation uçtan uca çalışmıştır. |
| A3 — Sınırlı canlı | Policy içindeki proposal’lar insan onayına açılır; kapsam pilot tavanıyla sınırlıdır. | Onaylar ve broker’da elle uygular. | En az bir tam statement kapanışı ve iki uzlaştırılmış canlı karar döngüsü; açıklanamayan fark yoktur. |
| A4 — Normal canlı | Policy’nin tamamı içinde proposal ve trade intent üretir. | Her sermaye kararını onaylar, broker’da elle icra eder. | Sürekli işletim seviyesidir; otomatik emir yetkisi hiçbir zaman doğmaz. |

A3’teki pilot kapsamı ayrıca tanımlanmalıdır: izin verilen aksiyonlar, azami yeni exposure, starter sınırı, geçerlilik süresi ve yasak aksiyonlar.

`authority_level`, capital policy alanı olmamalıdır. Ayrı bir `operating_authority` nesnesidir; çünkü:

- Aynı policy gölgede veya canlıda kullanılabilir.
- Operasyonel arıza nedeniyle authority düşürülebilirken ekonomik policy değişmeyebilir.
- Policy değişikliği authority artışı anlamına gelmemelidir.

Bir `authority_grant` şu referansları taşımalıdır:

- Fon ve policy sürümü
- Validation report
- Yetki seviyesi ve kapsamı
- Capital/action limitleri
- Başlangıç, expiry ve revocation
- İnsan onayı

Yetki yükseltmesi insan olayıdır; düşürme veya askıya alma güvenlik nedeniyle hemen yapılabilir.

## 4. Gölge koşu ne zaman başarısızdır?

İnsan ile sistemin farklı karar vermesi tek başına başarısızlık değildir. Fark önce sınıflandırılmalıdır:

| Fark türü | Anlamı |
|---|---|
| Input farkı | Farklı veri, zaman veya kanıt görülmüştür; kararlar karşılaştırılamaz. |
| Policy boşluğu | İnsan, policy’de temsil edilmeyen meşru bir kısıtı kullanmıştır. |
| Motor kusuru | Sistem kendi policy’sini yanlış uygulamıştır. |
| İnsan policy sapması | İnsan kabul edilmiş policy dışında davranmıştır. |
| Yargı farkı | Aynı gerçekler içinde iki savunulabilir sermaye değerlendirmesi vardır. |
| Operasyon farkı | Vergi, broker, nakit ihtiyacı veya icra kısıtı sisteme taşınmamıştır. |
| Kayıt yetersizliği | İnsan gerekçesi bulunmadığı için fark açıklanamamaktadır. |

Gölge koşu şu durumlarda başarısızdır:

- Motor kusuru veya hard-limit ihlali oluşursa
- Proposal başka snapshot’a dayanıyormuş gibi görünürse
- Sistem önerisi açıklanamaz veya uygulanamazsa
- Aynı policy boşluğu/override tekrar eder ve çözülmezse
- Gerekli data sürekli eksik veya bayatsa
- Proposal’lar no-trade amacına rağmen sürekli churn üretirse
- P0/P1 görevleri kapanmazsa
- Operasyon yükü haftalık kapasiteyi aşarsa
- Kör koşu fiilen kör değilse ve insan kararları sistem tarafından anchor ediliyorsa

İnsan sürekli policy dışı davranıyorsa “motor başarısız” denemez. İki ihtimal vardır: kullanıcı aslında yazılı policy’ye inanmıyordur veya policy gerçek tercihlerini temsil etmiyordur. Her iki durumda da canlı yetkiye geçilmemelidir.

Bu ayrım bütünüyle objektif olamaz; tek operatör hem kullanıcı hem validator’dır. Fakat kararları önceden dondurmak, fark sözlüğünü önceden tanımlamak ve sonucu görmeden sınıflandırmak kendini kandırma alanını daraltır. Agreement rate başarı metriği değildir; insan ve sistem aynı anda aynı yanlışı da yapabilir.

## 5. Bu aparat orantılı mı?

Evet, fakat yalnız dar tutulursa.

Tek kişilik sistem için asgari paket şudur:

- 10–15 kritik property
- 6–8 golden fixture
- Birkaç sabit tarihsel şok yolu
- İki aylık kör gölge döngüsü
- Bir kâğıt-icra senaryosu
- Sürümlü validation report

Kurumsal ölçekte bağımsız validation ekibi, geniş istatistiksel backtest altyapısı veya model governance portalı gereksizdir. Resmî model-risk rehberinin kendisi de doğrulama yükünün modelin etkisi, kullanım alanı ve kurumun ölçeğiyle orantılı olması gerektiğini söyler; bu sistem için ilke alınabilir ama kurumsal süreç birebir kopyalanmamalıdır. [Federal Reserve SR 11-7](https://www.federalreserve.gov/boarddocs/srletters/2011/sr1107a1.pdf)

“Test yazmadan da olur” itirazına cevabım:

> Para bağlamayan bir prototip test edilmeden çalışabilir; sermaye miktarı öneren bir motor çalışamaz.

Çünkü bu motorun en tehlikeli hataları çökme üretmez. Tutarlı, açıklanabilir ve yanlış ağırlıklar üretir. Bir loss-budget işaret hatası, split uyumsuzluğu, bayat snapshot veya policy-version karışıklığı haftalarca fark edilmeden bütün kitaba yayılabilir.

1,5–2,5 haftalık doğrulama maliyetinin karşılığı “sistemin para kazandırdığına güven” değildir. Daha dar ama gerçek bir güvendir:

- Policy’nin kodda gerçekten uygulandığını bilmek
- Bilinen uç durumları gerçek parayla keşfetmemek
- Sonraki değişikliklerin eski güvenlik kurallarını bozmadığını görmek
- Kullanıcının policy ile gerçek tercihleri arasındaki farkı sermaye bağlamadan ortaya çıkarmak

Kısacası: doğrulama aparatı getiriyi kanıtlamaz; yanlış çalışan makineye yetki vermeyi engeller. Bu sistemde hak ettiği rol tam olarak budur.