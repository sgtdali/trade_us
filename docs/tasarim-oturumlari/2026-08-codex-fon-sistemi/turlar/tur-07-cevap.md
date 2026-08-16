İkna oldum: doğru seçenek (c). Context bundle zorunlu, denetlenebilir ve fresh-session fallback için tek başına yeterli olmalı; resume ise bundle’ın yakalayamadığı ara muhakeme ve negatif bilgiyi koruyan ek değer olarak ilk sürümde kalmalı. Resume hiçbir zaman gerekli bilgi kaynağı hâline gelmemeli.

## 1. Açıkların tam listesi

- **UZLAŞTIK — Çift defter:** `events.jsonl` tek otoritedir; ticker bazlı thesis-tracker dosyaları yalnız yeniden üretilebilir projection’dır.
- **UZLAŞTIK — Tez açılışının üreticisi:** Kabul edilmiş `actionable_candidate` pitch sonucu, `workflow_completed + thesis_opened` olaylarını aynı atomik batch’te üretir.
- **UZLAŞTIK — Tez idempotency’si:** Aynı pitch completion olayı en fazla bir tez açabilir; ticker başına aynı anda tek açık tez bulunur.
- **UZLAŞTIK — Onay kavramı:** Ledger’a yazma yetkisi, makine doğrulaması, insanın `accepted_for_use` kararı ve gerçek-dünya icrası ayrı kapılardır.
- **UZLAŞTIK — B terfi döngüsü:** `unresolved B → thesis_tracker → required pitch` yolu kapıyı dolanır; thesis-tracker pre-thesis watchlist değildir.
- **UZLAŞTIK — Aktif zincire yeni screen:** Yeni screen zinciri geri sarmaz ve insan uzlaştırması üretmez; evidence olur, pitch tarafından tartılır.
- **ANLAŞAMADIK — Bayatlık:** Sen `(workflow, completed_at, data_stamp)` eklenmesini yeterli görüyorsun; ben bunun gerekli ama yetersiz olduğunu, “yalnız bucket/setup değişirse bayat” kuralının veri dönemine özgü invalidation ile genişletilmesi gerektiğini düşünüyorum.
- **UZLAŞTIK — Tek state’e aşırı yük:** Candidate, tez, security readiness, önerilen action ve gerçek exposure aynı state’e sıkıştırılamaz.
- **UZLAŞTIK — Retirement çelişkisi:** `active/wind_down/closed` lifecycle ayrımı gerekir; tez kırılmış ama satılmamış pozisyon `wind_down` olur.
- **UZLAŞTIK — Fonlama olayı yokluğu:** Gerçek işlemler tez referanslı olaylardır; işlem kaydı yokluğundan `flat` türetmek yasaktır.
- **UZLAŞTIK — Portföy belirsizliği:** `open_position`, `confirmed_flat_as_of` ve `position_unknown` ayrılmalı; uzlaştırılmamış defter sermaye kararını bloklamalıdır.
- **UZLAŞTIK — Haftalık kontrol verisi:** Mekanik monitoring ayrı taze snapshot ile çalışmalı; `no_deviation` dahil her kontrol iz bırakmalıdır.
- **UZLAŞTIK — Sermaye karşılaştırması boşluğu:** `thesis_opened`, yeni ismin mevcut pozisyonlarla karşılaştırılmasına kabul kapısıdır; pitch portföy-relative yapılmaz.
- **ANLAŞAMADIK — Supersede:** Sen tracker yeni tez açamayacağı için `superseded` değerinin atılmasını savunuyorsun; ben tracker’ın yalnız re-underwrite pitch istemesini, yeni pitch’in eski tezi atomik olarak supersede edebilmesini savunuyorum.
- **AÇIK — Tur kapanışı:** Bütün dilimlerin başarıyla bitmesi yerine terminal/partial kapanış önerildi, fakat kesin kapanış ve timeout politikası kararlaştırılmadı.
- **AÇIK — Tur 1’de elenen isim:** C sayılmaması ve ayrı `not_advanced` disposition taşıması önerildi, kesin hükme bağlanmadı.
- **AÇIK — Tur 1 olay granülerliği:** Dilim başına toplu olay önerildi; ticker başına olay mı, toplu olay mı olacağı kesinleşmedi.
- **AÇIK — Tekrarlanan `route_unsupported`:** Kalıcı dışlama olmadan aynı blocker’ın her tur yeni iş üretmesinin nasıl bastırılacağı kararlaştırılmadı.
- **UZLAŞTIK — Paralel yazım kaybı:** Analiz paralel olabilir, fakat global ledger commit’i seri ve atomik olmalıdır.
- **UZLAŞTIK — Fiziksel ölçek:** Tek mantıksal ledger korunur; fiziksel segmentler, batch commit ve yeniden üretilebilir snapshot kullanılabilir.
- **UZLAŞTIK — İnsan tetiklemeli/insan adımlı ayrımı:** Mekanik komut zinciri otomatikleşebilir; insan analitik kabul ve gerçek işlem kapılarında kalır.
- **UZLAŞTIK — Resume:** Zorunlu context bundle ile birlikte kullanılır; gizli session hafızası kanonik bilgi kaynağı değildir.
- **AÇIK — Session reset sınırı:** Pitch’te sonlandırma ve maddi setup değişiminde fresh session önerildi, kesin politika kararlaştırılmadı.
- **AÇIK — 500 ölçeğindeki Tur 2:** Tek global final yerine hiyerarşik eleme gerekebilir; gerçek finalist sayısı ölçülmeden karar verilmedi.

## 2. Mevcut dokümanda değişen kararlar

- **Başlık 0:** Thesis-tracker bağımsız defter değil, `events.jsonl` projection’ı olmalı; pitch kabulü ve tez açılışı atomik olmalı.
- **Başlık 0 ve 5:** `retired` tek başına yeterli değil; lifecycle, company status, security readiness, recommended action ve actual exposure ayrılmalı.
- **Başlık 1:** Unresolved B, thesis-tracker’a düşmemeli; tracker yalnız açılmış tezleri işler.
- **Başlık 2, Karar 2:** “Tezi olmayan her isim yeni screen ile serbestçe güncellenir” yanlış; aktif araştırma zincirindeki screen yalnız evidence olmalı.
- **Başlık 2, Karar 3:** “Paralellik pratikte yok, disiplinle çözülür” gerekçesi Başlık 3 tarafından geçersiz kılındı; analiz paralel, commit seri olmalı.
- **Başlık 2, Karar 4:** `completed_workflows` isim listesi olamaz; workflow instance, tamamlanma zamanı ve input/data snapshot kimliği taşımalı.
- **Başlık 3:** Tur/dilim için manifest, terminal dilim durumu, Tur 1 disposition’ı ve açık round kapanış kuralı gerekli.
- **Başlık 3’ün kabul edilen bedeli:** Yeni aday–incumbent karşılaştırması pre-thesis aşamada yapılmaz; `thesis_opened` sonrasında Başlık 4’e devredilir.
- **Başlık 4:** Haftalık kontrol ayrı monitoring snapshot kullanmalı ve sapma olmasa da kontrol olayı yazmalıdır.
- **Başlık 4, Karar 6:** Portföy işlemleri global ledger’da tez referanslı olaylardır; ayrıca portföy uzlaştırma olayı gerekir.
- **Başlık 5:** “Fonlanmamış tez”, işlem yokluğu değil, belirli tarih itibarıyla uzlaştırılmış `flat` durumudur.
- **Adımlar arası hafıza kararı:** Resume kalır; fakat her adımın immutable context bundle’ı fresh session için yeterli olmalı ve ledger’a hash’li artefakt olarak bağlanmalıdır.
- **Orkestrasyonun genel onay modeli:** `approved` analitik doğruluk anlamına gelmez; `accepted_for_use` ayrı insan hükmüdür.

## 3. Kullanıcının karar vermesi gereken tercihler

1. Gerçek hedef ölçek ve kadans nedir: 87 mi, 500 mü; bir turun kabul edilebilir azami süresi kaç gün?
2. İnsan hangi analitik artefaktları tek tek kabul edecek: her workflow, yalnız karar-bearing çıktılar veya dilim/zincir bazlı toplu onay?
3. Bir tur eksik dilimlerle kapatılabilir mi; kaç gün ve hangi asgari kapsama sonrasında partial Tur 2 kabul edilir?
4. Aynı anda kaç aktif araştırma zinciri ve ne kadar model bütçesi/concurrency kabul edilebilir?
5. Portföy ne sıklıkta uzlaştırılmalı ve yeni tez açıldığında sermaye karşılaştırması hemen mi, yalnız aylık rebalansta mı yapılmalı?