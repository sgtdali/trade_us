Katılıyorum: Başlık 4 karar 3 ve 4 mevcut hâliyle uygulanabilir değil. Üstelik temel hata eşik şemasından önce geliyor: `first_rejection`, tam bir tez izleme sözleşmesi değildir. En erken reddetme sebebi olabilir ama tezin bütün falsifier’larını, uyarı sinyallerini ve kill criterion’larını taşımaz.

Bu yüzden agy’nin görevi “metni eşiğe dönüştürmek” değil, pitch’ten kaynak bağlantılı bir taslak izleme sözleşmesi çıkarmak olmalı.

### 1. Eşik çıkarımının sadakati

Çıkarılan hiçbir kural insan onayı olmadan aktifleşmemeli. Fakat bunun için ayrı bir ikinci “tez açayım mı?” kapısı kurmak gerekmez. Pitch kabul ekranı aynı anda şunları göstermeli:

- Orijinal metin ve tam kaynak pasajı.
- Agy’nin önerdiği normalize kural.
- Ölçülebilirlik sınıfı.
- Veri kaynağı ve kontrol ritmi.
- Modelin metne eklediği varsayımlar.

İnsan pitch’i kabul ederken izleme sözleşmesini de onaylar/düzeltir. Atomik batch’te `analysis_adjudicated` ve bu ilk sözleşmeyi taşıyan `thesis_opened` yazılır.

Burada sert bir sınır gerekir: metinde sayı, dönem veya açık operasyonel tanım yoksa agy bunları icat edemez. “Hyperscaler capex backlog’a dönüşmezse” ifadesini keyfî olarak “iki çeyrek backlog büyümesi <%10” yapamaz. Sonuç `qualitative`, `not_mechanically_evaluable` olmalıdır. İnsan yeni bir sayısal kural eklerse bunun kökeni `human_authored` olur; “metinden çıkarıldı” diye sunulmaz.

Bir mekanik kural da yalnız `(metric, operator, threshold)` değildir. En azından şunları belirlemelidir: metrik tanımı, birim, dönem/TTM/çeyrek, kaynak, karşılaştırma operatörü, tolerans, tek dönem mi ardışık dönemler mi, revision politikası ve eksik veri davranışı.

Eşik ihlali de tezi otomatik `broken` veya `wind_down` yapmamalı. Mekanik sistem yalnız sapma üretir; eksen değişikliği adjudicated thesis assessment gerektirir. Aksi hâlde veri eşleme hatası gerçek pozisyon çıkışını tetikleyebilir.

### 2. Nokta-zamanlı veri ve restatement

İki cevap gerçekten tutulmalı ama aynı sorunun iki çelişkili cevabı olarak değil:

- `as_known_at`: Kontrol tarihinde sistemin bildiği veriyle sonuç.
- `restated_lookback`: Bugün bilinen revize veri geçmiş dönem hakkında ne söylüyor?

Her gözlem en az şu iki zamanı taşımalı:

- `period_end`: Verinin ekonomik olarak ait olduğu dönem.
- `known_at`: Bu değerin sistem tarafından ne zaman bilinebilir olduğu.

Ayrıca kaynak sürümü/accession, retrieved time ve varsa `supersedes_observation_id` gerekir.

Q2 örneğinde:

- Q2’de bilinen değer %21’dir; o haftaki `no_deviation` olayı doğru kalır.
- Q4’te %19 restatement’i yeni bir observation olarak eklenir; eski değer silinmez.
- Q4 kontrolü mevcut bilgiyle breach üretir ve ayrıca `retrospective_breach_for_period=Q2` taşır.
- Sistem “tez Q2’de bilinen bilgiyle bozuktu” demez; “Q2 ekonomisi sonradan açıklanan bilgiye göre eşiği ihlal etmiş” der.

Dolayısıyla geçmiş kontroller yalan olmaz. Karar kalitesini de hindsight ile bozmayız. Bütün geçmişi her hafta yeniden hesaplamak gerekmez; yalnız revize edilen gözlemlerin etkilediği kural/dönemler için lookback çalışır.

### 3. Eşiklerin değiştirilmesi

Eşikler değiştirilebilir olmalı fakat yerinde güncellenmemeli. Burada ayrı, immutable `monitoring_policy_version` gerekir.

Senin “eski eşik ölmesin” sezgin doğru; fakat eski ve yeni eşiği sonsuza kadar paralel aktif tutmak gereksiz alarm üretir. Daha iyi model:

- Eski sürüm tarihsel olarak korunur ve geçmiş tarihler için geçerli kalır.
- Yeni sürüm belirli bir `effective_at` ile prospektif olarak aktifleşir.
- Eski sürüm `superseded` olur ama silinmez.
- Her geçmiş kontrol, o tarihte geçerli policy sürümüyle yorumlanır.

Her revizyon ayrı ve göze batan bir `thesis_monitoring_policy_revised` olayı olmalı. `thesis_assessment_recorded` içinde sessiz bir alan değişikliği olmamalı.

Revizyon nedenleri ayrılmalı:

- `extraction_correction`: İlk normalize kural kaynak metne sadık değildi.
- `metric_mapping_change`: Aynı ekonomik fikir için veri tanımı/kaynağı değişti.
- `clarification`: Belirsiz operasyonel ayrıntı netleştirildi.
- `thesis_amendment`: Ekonomik bozulma koşulunun kendisi değişti.

Sonuncusu sıradan bakım değildir; re-underwrite gerektirir. Özellikle eski eşik breach olmuşken yeni eşik gevşetiliyorsa sistem şunları açıkça göstermelidir:

> Eski kural: breach  
> Yeni kural: pass  
> Revizyon sonucu: mevcut ihlal artık ihlal sayılmıyor

Bu durumda eski breach iptal edilmez. `security_readiness` en azından adjudication bitene kadar `re_underwrite` olur; değişiklik temel tezi dönüştürüyorsa `company_thesis_status=changed` gündeme gelir.

Her revizyonda bir defalık “köprü değerlendirmesi” yeterlidir:

- Eski kural mevcut veriyle ne diyordu?
- Yeni kural mevcut veriyle ne diyor?
- Yeni kural önceki gözlemlere uygulansaydı sonuç değişir miydi?

Böylece goalpost kaydırma görünür olur; eski kuralı her hafta sonsuza kadar paralel koşturmak gerekmez.

### 4. Ölçülemeyen koşullar

Burada tasarım açıkça kendi kendini yalanlıyor. “Haftalık oturumda listelenir” denmiş ama sapma yoksa haftalık oturum açılmıyor. Dolayısıyla listeyi kimse görmüyor.

Her nitel kural şunları taşımak zorunda olmalı:

- Beklenen kanıt kaynağı.
- Sorumlu kişi.
- `review_mode`: olay-güdümlü veya takvim-güdümlü.
- `next_review_due`.
- Azami bayatlık süresi.
- İncelemenin hangi sonucu üreteceği.

“Hyperscaler capex backlog’a dönüşüyor mu?” muhtemelen haftalık değil, earnings/10-Q sonrası kontrol edilmelidir. Her hafta insana tüm nitel koşulları göstermek bildirim körlüğü yaratır. Doğru model, haftalık mekanik koşunun yalnız şunları göstermesidir:

- Bu hafta vadesi gelen nitel kontroller.
- Vadesi geçmiş olanlar.
- Kontrol edilenler.
- Henüz vadesi gelmeyenler.

Vadesi gelen nitel kural incelenmediyse o tez için genel sonuç `no_deviation` olamaz; `incomplete` veya `indeterminate` olmalıdır. “Ölçebildiğimiz alanlarda sapma görmedik” ile “tez sağlıklı” aynı hüküm değildir.

Ayrı olay tipi patlamasına gerek yok. `thesis_check_completed`, `check_kind=mechanical|qualitative` ve kullanılan policy/rule kimliklerini taşıyabilir. `monitoring_run_closed` da kapsama oranını ve overdue sayısını gösterir.

### 5. Ölçülebilir eşiği olmayan tez

Açılabilmeli. Fakat “ölçülebilir eşiği yok” ile “izleme planı yok” kesinlikle aynı şey değildir.

Fail-closed kuralı şöyle olmalı:

> Her tez, ölçülebilir eşik taşımasa bile onaylanmış bir izleme sözleşmesi taşımadan açılamaz.

Tamamen nitel bir tez için sözleşme şunlardan oluşabilir:

- Olay-güdümlü inceleme: earnings, müşteri açıklaması, backlog disclosure.
- Takvim-güdümlü insan incelemesi.
- Belirli kanıtın ortaya çıkması için son tarih.
- Azami yeniden-underwrite aralığı.

Bu zaman eşiği otomatik retire üretmez. Süresi dolduğunda zorunlu inceleme üretir. İnceleme yapılmazsa tez açık kalabilir ama `security_readiness=not_decision_grade` veya `re_underwrite` olur; yeni fonlama/add kararı bloke edilir. Mevcut pozisyon varsa izleme yükümlülüğü devam eder.

Aylık rebalans bunu ikame etmez. Portföy oturumunda ismin görülmesi, nitel falsifier’ın gerçekten okunup adjudicate edildiğini kanıtlamaz. Bu nedenle Başlık 5’teki “aylık temas donmayı yeterince önler” savunması zayıf ve revize edilmeli.

Altı ayın doğru süre olup olmadığı yatırım tercihidir; bazı tezlerde bir earnings döngüsü, bazılarında 30 gün, bazılarında 90 gün olabilir. Şema sabit süreyi değil `next_review_due` ve `max_staleness` alanlarını taşımalı.

En net revizyon şu olur:

> Agy, `first_rejection`’ı otomatik olarak ölçülebilir eşiklere dönüştürmez; pitch’in bütün falsifier ve kill criterion’larından kaynak bağlantılı taslak izleme sözleşmesi çıkarır. İnsan bu sözleşmeyi pitch kabulü sırasında onaylar. Her aktif tez ya mekanik kuralla ya zamanlanmış nitel incelemeyle kapsanır; “izlenemeyen açık tez” yasaktır.

Bence tasarımın en kırılgan yeri eşiklerin yanlış sayısallaştırılması değil, `no_deviation` sonucunun “tez sağlıklı” gibi okunabilmesi. Sistem yalnız ölçebildiği altkümede sessizse, bunu tam kapsama hükmü gibi sunmamalı.