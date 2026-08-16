Ana hükmüm şu: Bugünkü CLI/JSON yüzeyiyle bu sistem tek kişi için sürdürülebilir değil. İstisna odaklı orkestrasyon ve gerçek bir karar yüzeyiyle, 87 isim ve 10–15 açık tez ölçeğinde çalışabilir. İnsan arayüzü burada kozmetik değil, güvenlik mimarisinin parçasıdır.

## 1. Tek giriş kuyruğu, çok sayıda kaynak kuyruğu

Operatörün sabah tek bir “Bugün” kuyruğu görmesi doğru. Fakat altta portföy, tez izleme, araştırma ve operasyon kuyrukları ayrı kalmalı. Hepsini tek bir sayısal puanla sıralamazdım; eski ama önemsiz bir dilimin canlı para riskinin önüne geçmesi tehlikeli olur.

Öncelik sırası leksikografik olmalı:

| Öncelik | İş türü |
|---|---|
| P0 | Pozisyon bilinmiyor, broker uzlaşmıyor, kurumsal işlem işlenmemiş, işlem kaydı eşleşmiyor |
| P1 | Fonlanmış tezde sapma, kırılmış tezle açık pozisyon, wind-down gecikmesi |
| P2 | Vadesi geçmiş nitel inceleme, bayat reconciliation, izleme verisi üretilememesi |
| P3 | Pitch/izleme sözleşmesi adjudication’ı, zinciri veya selection batch’i tıkayan karar |
| P4 | Açık tur, waived dilim, yeni keşif ve araştırma kapasitesi işleri |

Aynı sınıfta önce `due_at`, sonra yaş sıralaması kullanılabilir. Her kuyruk öğesi “neden şimdi?”, “bugün yapılmazsa ne olur?”, “kaç dakika sürer?” ve “hangi kanıta bakılmalı?” sorularını cevaplamalı.

Kuyruk öğeleri yeni bir otoritatif defter olmamalı; olaylardan ve vadelerden türetilen projection’lardır. Yalnız karar, erteleme veya waiver olay üretir.

Bir sınır da var: Sistem dış dünyadan broker verisi almıyorsa “girilmesi unutulmuş işlem”i bilemez. Ancak “reconciliation vadesi geçti” diyebilir. Unutulan işlemi gerçekten yakalamak için broker ekstresi veya içe aktarma gerekir.

## 2. Gerçek okuma arayüzü birinci sınıf gereksinimdir

JSON köprüsü iyi bir makine adaptörüdür, insan yüzeyi değildir. İlk sürümün tam teşekküllü bir web uygulaması olması gerekmez; yerel üretilen bir HTML kontrol paneli yeterli olabilir. Fakat kanıt ile eylem yan yana bulunmalıdır. İnsan HTML’de okuyup sonra event ID kopyalayarak üç CLI komutu çalıştırıyorsa kapı zamanla törensel hâle gelir.

Adjudication ekranı şunları göstermeli:

- İstenen karar ve onaylanırsa doğacak aşağı akış sonucu: “tez açılır”, “zincir ilerler”, “izleme kuralı değişir”.
- Ham sonuç, çıkarılan hüküm ve kaynak pasajı.
- `proposed_outcome` ile `accepted_outcome` arasındaki alan bazlı fark.
- Olgusal hata ile yargısal anlaşmazlığın ayrımı.
- Eksik veya doğrulanamayan alanlar.
- Üç açık eylem: olduğu gibi kabul, reddet/yeniden çalıştır, gerekçeli override.

Fonlanmış tez, izleme sözleşmesi ve sermaye etkili kararlar için toplu “hepsini onayla” olmamalı. Ara adımlarda ise bu kadar ağır bir kapı gerekmeyebilir.

Idea-generation’ın parlak HTML raporu faydalı bir analiz artefaktıdır ama adjudication yüzeyi değildir. Hatta sunum kalitesi modeli olduğundan daha ikna edici gösterebilir. Kontrol ekranı estetikten önce farkları, kaynakları ve eksikleri göstermelidir.

## 3. İnsan hatası engellenmez; sınırlandırılır, görünürleştirilir ve düzeltilir

Tek kişilik sistemde gerçek bir “dört göz” kontrolü kurulamaz. Aynı kişiye iki kez onaylatmak çoğunlukla güvenlik tiyatrosudur. Bunun yerine üç katman gerekir:

- Mekanik önleme: lot toplamları, pozisyon dengeleri, zorunlu gerekçe, kaynak ve geçiş invariant’ları.
- Bağımsız tespit: broker reconciliation’ı, kurumsal işlem kaynağı, veri tazeliği kontrolü.
- Append-only düzeltme: eski kararı değiştirmek yerine ona bağlanan tipli telafi olayı.

Yargısal kararlar tekrar tekrar sorgulanmamalı; alarm yorgunluğu üretir. Fakat canlı para riskini bastıran kararlar süreli olmalı. Örneğin fonlanmış tezdeki sapmayı “önemsiz” sayan override şunları taşımalı:

```text
reason
review_due_at veya valid_until
hangi kanıtın kararı değiştireceği
etkilenen pozisyon
```

Vade dolunca yeniden görünür; sonsuza kadar bastırılamaz.

Yanlış lot eşleştirme, orijinal kayda bağlı ve toplam hisse/nakit dengesini koruyan bir düzeltmeyle giderilir. Yanlışlıkla kapatılan tez tipli bir kayıt-düzeltme olayıyla geri alınabilir; fakat gerçek fikir değişikliği “yanlış kayıt” diye maskelenemez, yeni tez gerektirir.

## 4. Haftalık gerçek emek tahmini

Şu varsayımlarla hesaplıyorum:

- 87 isim 4–6 haftalık kayan coverage cycle içinde taranıyor; her hafta 87’si birden değil.
- Haftada 3–5 analitik sonuç üretiliyor.
- 10–15 açık tezin mekanik kontrolü otomatik ve insan yalnız istisnaları görüyor.
- Nitel kontroller bütün tezlerde haftalık değil, vadeleri dağıtılmış.
- Haftada 0–3 işlem var ve broker uzlaştırması büyük ölçüde hazırlanmış geliyor.

Bu durumda:

| İş | Haftalık süre |
|---|---:|
| Günlük kuyruk taraması | 0,5–1 saat |
| Keşif/selection batch incelemesi | 1–1,5 saat |
| Kritik adjudication’lar | 0,75–1,5 saat |
| Tez sapmaları ve vadeli nitel okumalar | 1–2 saat |
| İşlem, lot ve reconciliation | 0,5–1 saat |
| Aylık portföy oturumunun haftalık karşılığı | 0,5–0,75 saat |

Normal hafta yaklaşık **5–7 saat**, bilanço yoğun veya gerçek sapmalı hafta **8–12 saat** ister.

Bugünkü JSON/CLI, elle üç komut ve her adımda insan kapısı korunursa bunun **9–14 saate** çıkacağını düşünüyorum. Her 87 ismi haftalık taramak ve bütün ara çıktıları adjudicate etmek ise rahatlıkla 15 saati aşar; o sistem tek kişilik yan faaliyet olmaktan çıkar.

## Neyi feda ederdim?

İlk feda edeceğim şey her ara workflow sonucunda insan adjudication’ıdır. Tearsheets, comps ve earnings-preview makine doğrulamasından geçerek “provisional evidence” olarak zincirde ilerleyebilir. İnsan kapısını şu dört yerde korurdum:

- Pitch sonucundan tez açılması.
- İzleme sözleşmesinin kabulü veya değiştirilmesi.
- Fonlanmış tezde sapmanın bastırılması.
- İşlem ve reconciliation kayıtları.

İkinci olarak bütün tezleri aynı sıklıkta nitel okumayı feda ederdim. Fonlanmış/kırılgan tez daha sık, fonlanmamış ve sakin tez daha seyrek görülür; ancak her birinin kesin bir azami sessizlik süresi olur.

Üçüncü olarak “evrenin tamamı her hafta” hedefini bırakırdım; kayan coverage cycle kullanırdım.

Lot bütünlüğünü, reconciliation’ı, kurumsal işlemleri ve pitch→tez kapısını feda etmezdim. Bunlar bürokrasi değil, gerçek para ile sistem kaydı arasındaki sınırdır. En büyük YAGNI ise her analitik adımda eşit ağırlıkta insan onayıdır.