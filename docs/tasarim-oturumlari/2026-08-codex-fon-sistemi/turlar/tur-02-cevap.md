Evet: `events.jsonl` tek otorite olmalı. Thesis-tracker’ın ticker bazlı JSONL’leri ancak yeniden üretilebilir bir projection/materialized view olabilir; bağımsız yazma yüzeyi olmamalı. Skill’in “append-only thesis tracker” şartını fiziksel olarak ikinci bir append-only defter tutmak diye okumaya gerek yok. Mantıksal tez geçmişi zaten `events.jsonl` içindeki `thesis_opened`, `evidence_update`, `decision_update`, `thesis_closed` olaylarının sırasıdır.

Pitch onaylanırken `workflow_completed` ile koşullu `thesis_opened` aynı atomik event batch’ine yazılmalı. Sonrasında ticker bazlı tracker ister her okumada türetilir, ister güvenilir olmayan bir cache olarak materialize edilir. Cache silinip yeniden üretilebilmelidir.

İdempotency için yalnız `result_sha256` kullanmazdım. Aynı metin teorik olarak farklı ticker veya iş kalemlerinde meşru olabilir; farklı biçimlenmiş aynı pitch de farklı hash üretir. Anahtar nedensellik olmalı:

`thesis_opened` olayının idempotency anahtarı = onu doğuran onaylı `pitch workflow_completed.event_id`.

Başka deyişle bir pitch completion olayı en fazla bir tez açabilir. `thesis_id` de bu nedenden deterministik türetilebilir. Buna ek olarak ayrı bir alan kuralı gerekir: tasarım gerçekten “ticker başına aynı anda tek açık tez” diyorsa, farklı bir pitch completion olsa bile mevcut açık tez varken ikincisi açılamaz; yeni sonuç mevcut teze evidence olur veya önceki tez açıkça kapatılır/supersede edilir. Result hash taşıma katmanındaki tekrarları, causal event kimliği ise iş kuralındaki tekrarları önler.

### Zincirin ortasındaki isim

Düzeltmene tamamen katılıyorum: sorun yalnız `in_progress` anı değil. İlk workflow başladığı andan pitch’in terminal sonucuna kadar yaşayan bir “aktif araştırma ipliği” var ve mevcut tasarımda bunun birinci sınıf kimliği yok.

Ama iki seçenek arasında aktif zincirdeki isimleri keşif havuzundan tamamen çıkarmayı seçmezdim. Bir zincir insan yüzünden üç hafta beklerse isim üç hafta cross-sectional price discovery’den kaybolur. Daha kötüsü, yeni screen’in getireceği olumsuz sinyali görmezden gelerek eski setup üzerinde pitch’e kadar yürüyebilir.

Benim tercihim: isim taramaya girsin, fakat yeni screen sonucu aktif zincirin kontrol durumunu doğrudan ezmesin. Screen sonucu önce bir gözlem/evidence olarak kaydedilsin. Aynı A/B ve aynı ekonomik setup ise zincir devam eder; C/Reject veya maddi setup değişimi ise zinciri sessizce çöpe atmak yerine `reconciliation_required` durumuna getirir. Hazırlanmış iş tamamlanabilir ve sonucu kaybolmaz, fakat sonraki adım uzlaştırma yapılmadan hazırlanmaz.

Yani hariç tutma kriterini “açık tezi veya aktif zinciri var mı?” şeklinde genişletmezdim. Daha doğru ayrım şu:

Keşif taramasına katılma ile screen sonucunun workflow’u yönetme yetkisi farklı şeylerdir.

Açık tezli isimleri taramama kararı ayrıca tartışılabilir; fakat aktif zinciri taramadan çıkarmak, donmuş araştırma riski yaratır.

### Bayatlık konusunda

Sınıflandırmanı düzeltiyorum: haklısın, `completed_workflows`’un yalnız isim listesi olması öncelikle eksik veri modelidir; tek başına karar çelişkisi değildir. `(workflow, completed_at, input snapshot/data epoch)` kaydı gerekli.

Fakat “üçlü yeterlidir ve bucket/setup kararına hiç dokunmaya gerek yoktur” kısmına tam katılmıyorum. Dokümandaki “yalnız bucket veya setup değiştiyse bayat sayılır” cümlesi fazla güçlü. Veri dönemi değiştiğinde de bayatlama olabilecekse “yalnız” artık doğru değildir.

Ben bunu kararı çöpe atmak değil, iki ayrı invalidation sebebini ayırmak olarak görüyorum:

Bucket/setup değişimi, workflow’un cevapladığı sorunun değiştiğini gösterir. Veri damgası ise aynı soruya verilen cevabın eski kanıtla üretildiğini gösterir.

Üstelik tek bir genel `pack_data_as_of` damgası da her zaman yeterli olmaz. Pack’in piyasa tarihi her gün değişiyorsa salt damga karşılaştırması her şeyi her gün bayatlatır. Tearsheet için yeni finansal yayın dönemi, comps için fiyat/konsensus dönemi, earnings-preview için event snapshot’ı farklı anlam taşır. Dolayısıyla senin üçlün gerekli ve büyük ölçüde doğru; fakat “pack’in veri damgası” workflow’un tükettiği ilgili veri dönemlerini temsil etmeli. Son kanaatim: bucket/setup kuralının özü yanlış değil, tek bayatlık nedeni olduğu iddiası yanlış.

### Tur/dilim kör noktası

Burada dört tespitinden üçü ciddi, biri ise doğru model kurulursa daha çok gürültü problemi.

(a) gerçek bir liveness sorunu. Fakat `route_unsupported` olan bir candidate dilimi bloklamamalı. Dilim analizi başarıyla üretildi ve onaylandıysa, içindeki bir finalistin downstream rotasının desteklenmemesi dilimin tamamlanmadığı anlamına gelmez. Asıl deadlock, hiç çalıştırılmayan veya teknik olarak başarısız olup açık kalan dilimdir.

Tur kavramını bırakmazdım; çünkü Tur 2’nin anlamı sabit bir finalist kümesini aynı karşılaştırma düzleminde görmek. Bunun yerine tur başlangıcında evren snapshot’ı ve beklenen dilim manifesti dondurulmalı. Her dilim `completed`, `failed` veya insan tarafından `waived/skipped` gibi terminal bir sonuca ulaşabilmeli. Tur, bütün dilimler başarılı olduğunda değil, bütün dilimler terminal olarak çözümlendiğinde kapanabilmeli.

Zaman aşımı turu kendiliğinden kapatmamalı. Sistem insan tetiklemeli olduğuna göre süre dolması yalnız “tur kapatma kararı gerekiyor” sinyali üretmeli. İnsan eksik dilimi yeniden çalıştırır, açıkça atlar veya turu partial olarak kapatır. Dolayısıyla benim cevabım:

Tur 2, bütün dilimler terminal olduğunda otomatik olarak hazır olur; ayrıca insan gerekçeli bir `partial round close` yapabilir. Salt zaman aşımı kapanış nedeni değil, kapanış kararı tetikleyicisidir.

Partial kapanan turun Tur 2 sonucu da eksik kapsama sahip olduğunu taşımalıdır; tam turla sessizce eşdeğer sayılamaz.

(b) önemli ve kesinlikle tanımlanmalı. Tur 1’de elenen isim C değildir. C, finalistlerin küresel karşılaştırmasından çıkan bir hükümdür; Tur 1 elemesi ise “bu dilimden finale ilerlemedi” demektir. Buna A/B/C dışında `not_advanced` benzeri bir stage disposition gerekir. İlk kez taranan isim hiç final görmediyse bucket’ı gerçekten yoktur; operasyonel durumu keşif havuzunda/deprioritized olabilir ama “C” geçmişi yazılmamalıdır. Dolayısıyla bucket değişimine dayalı bayatlama yalnız Tur 2’nin nihai screen olayı için uygulanabilir; Tur 1 sonucu ayrı bir olay ailesi olmalıdır.

(c) bence biraz fazla “kısır döngü” diye adlandırılmış, fakat gerçek bir maliyet/gürültü sorunu. İsim her tur yeniden değerlendirilmelidir; çünkü hem şirket setup’ı hem de katalog değişebilir. Ancak aynı setup, aynı önerilen rota ve aynı katalog sürümüyle tekrar `route_unsupported` çıkması yeni bir blocker veya yeni manuel iş üretmemelidir. Önceki blocker’ın fingerprint’i korunur; yalnız setup, önerilen rota veya katalog eşlemesi değişince yeniden açılır. Böylece kalıcı dışlama yaratmadan tekrar eden aksiyon bastırılır.

(d) tamamen haklısın ve bu dördünün en tehlikelisi. “Akış seri” gerekçesi Başlık 3 ile geçersizleşmiş. Üstelik risk yalnız aynı ticker’ın state çakışması değil: `events.jsonl` tek gerçeklik kaynağıysa paralel dilimler aynı deftere yazacaktır. Mevcut append yaklaşımı dosyayı okuyup tamamını atomik replace ediyor; iki süreç aynı eski sürümü okuyup yazarsa son yazan diğerinin olaylarını kaybettirebilir. Atomik replace, eşzamanlı read-modify-write kaybını çözmez.

Bu nedenle tasarımın açık ilkesi “analiz paralel, event commit seri” olmalı. Ayrı dilimler aynı anda LLM çalıştırabilir; fakat onaylı olayların tek deftere eklenmesi tek-yazarlı, kilitli veya compare-and-swap korumalı bir kapıdan geçmelidir.

Özet kanaatim: (d) veri bütünlüğü açısından en tehlikelisi; (a) en ciddi deadlock/liveness riski; (b) zorunlu fakat yerel bir semantik eksik; (c) ise turu bloklamadığı sürece ölümcül değil, idempotent gürültü bastırma problemi. Tur kavramını bırakmak yerine, “başarılı tamamlanma” ile “terminal olarak çözümlenme”yi ayırmak tasarımın özünü koruyarak (a)’yı çözüyor.