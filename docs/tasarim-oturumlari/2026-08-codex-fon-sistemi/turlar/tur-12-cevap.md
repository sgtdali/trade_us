Net tercihlerim şöyle: fiyat eşikleri yasaklanmamalı ama kurumsal işlem-duyarlı olmalı; lot seviyesinde analitik takip kurulmalı ama vergi motoru yapılmamalı; tez performansı ile portföy katkısı farklı para birimi katmanlarında ölçülmeli; manuel idempotency kimliğini kullanıcı değil sistem üretmeli; aylık rebalans ise skill entegrasyonunu beklememeli.

### 1. Kurumsal işlemler

Ayrı bir kurumsal işlem olayı şart. Fiyat eşiğini yasaklamak yanlış çözüm olur; piyasa değeri ve çarpan, “80 doların altında yeniden bak” hükmüyle ekonomik olarak aynı şey değildir.

En azından şu gerçekleri taşıyan `security_corporate_action_effective` gerekir:

- Kalıcı `security_id`; ticker kimlik değildir.
- İşlem türü: split, reverse split, stock/cash dividend, ticker değişimi, merger/conversion, spin-off.
- Ex-date ve effective time.
- Oran, nakit bileşen ve para birimi.
- Oluşan yeni security’ler.
- Kaynak ve kaynak sürümü.

Split 4:1 olduğunda iki ayrı sonuç çıkar:

- Lot projection’ında 100 hisse 400’e, hisse başı maliyet dörtte bire dönüşür; toplam ekonomik maliyet değişmez.
- 80 dolarlık fiyat eşiği aynı bazda 20 dolara rebased edilir.

Kuralın kendisini değiştirmek gerekmez. Kural şunları taşımalıdır:

- `threshold_value=80`
- `price_basis_date`
- `adjustment_policy=corporate_action_adjusted`
- Kullanılan corporate-action/price-series sürümü

Kontrol ya fiyatı ve eşiği aynı adjusted-price bazına getirir ya da ikisini de ham bazda karşılaştırır. Birini adjusted, diğerini raw kullanmak yasaktır.

Kurumsal işlem tespit edilmiş ama adjustment tamamlanmamışsa sonuç `deviation` değil `indeterminate: data_adjustment_pending` olmalı. Böylece split yanlışlıkla re-underwrite tetiklemez.

Kaynak güvenilir broker/custodian ise olay makine doğrulamasından sonra otomatik kabul edilebilir; gerçek portföy miktarı yine sonraki `portfolio_reconciled` ile doğrulanır. Yalnız piyasa verisi kaynağı varsa beklenen miktar projekte edilir ama reconciliation durumu “pending” kalır.

Spin-off ayrıca yeni bir problem yaratır: portföye henüz tezi olmayan bir security girebilir. Sistem bunu reddedemez. Yeni exposure, kaynak pozisyonun `origin_thesis_id`’sini taşımalı fakat `security_readiness=not_decision_grade` ve zorunlu insan incelemesi üretmelidir.

### 2. Lot ve maliyet tabanı

Lot seviyesini savunuyorum; tez-bazlı sanal defter ise lotlardan türetilmiş projection olmalı, ikinci otorite değil.

Her alış/fill şunları oluşturur:

- `lot_id`
- `account_id`
- `security_id`
- `thesis_id_at_entry`
- trade ve settlement zamanı
- miktar, fiyat, işlem para birimi
- ücretler ve ücret para birimi

Satış olayı açık lot tahsislerini taşımalı. İnsan lot seçmek istemezse sistem FIFO gibi açık bir varsayılanla öneri üretir; kullanılan yöntem ve tahsisler yine kaydedilir. Broker sonradan farklı lot eşlemesi verirse reversal/correction olayıyla düzeltilir.

Burada “analitik lot” yaptığımızı açık söylemek gerekir; vergi lotu, wash-sale ve ülkeye özgü maliyet hesaplama motoru yapmıyoruz. Vergisel doğruluk gerekirse broker verisi otorite olur.

Supersede ileride uygulanırsa eski lotun `thesis_id_at_entry` değeri değiştirilemez. İki ayrı görünüm gerekir:

- İlk underwriting attribution: lot başlangıçtan beri hangi tez altında kazanıp kaybetti?
- Mevcut stewardship: kalan pozisyon yeni teze hangi tarih ve devir fiyatıyla teslim edildi?

Devir olayı tarihsel bağlantıyı yeniden yazmaz. Fakat supersede mekanizması zaten YAGNI listesinde olduğu için V1’de yalnız lot şemasının buna izin vermesi yeterlidir.

Ortalama maliyet projection olarak gösterilebilir ama otorite olamaz. “Bu tezle ne kazandım?” sorusu lotlar, satış tahsisleri, ücretler, temettüler ve kurumsal işlemler olmadan doğru cevaplanamaz.

### 3. Para birimi

Önerdiğin ayrım doğru, fakat iki değil üç katman daha açıklayıcı:

1. Security’nin yerel toplam getirisi: ABD hissesi için USD fiyat + temettü.
2. Yatırım hükmünün başarısı: USD bazında, tercihen sektör/benchmark’a göre relatif getiri.
3. Portföye katkı: portföyün tanımlı baz para biriminde; USD/TRY etkisi ayrıca gösterilir.

Böylece “tez doğruydu ama TL güçlendiği için portföy katkısı zayıftı” ile “hisse gerçekten kötü performans gösterdi” ayrılır.

Operatörün Türkiye’de olması baz para biriminin otomatik TRY olduğu anlamına gelmez. Mandate veya hesap USD bazlı olabilir. `portfolio_base_currency` açık bir portföy ayarı olmalı.

Ledger hiçbir tarihi işlemi sonradan farklı kura çevirmemeli. İşlem ve cash-flow olayları kendi doğal para birimini taşır; değerleme projection’ı kullanılan FX oranını, kaynağını ve `as_of` zamanını kaydeder. Sonuç en az şu üç parçaya ayrılır:

- local/security P&L
- FX translation P&L
- base-currency total P&L

Portfolio-risk-management paketi ayrıca açık FX exposure’ını görmelidir; bu, tezden bağımsız bir portföy riskidir.

### 4. Broker kimliği olmayan manuel idempotency

İşlem alanlarından kusursuz duplicate tespiti matematiksel olarak mümkün değildir. Aynı hesap, ticker, yön, miktar, fiyat ve tarihte iki meşru fill olabilir.

Çözüm, kimliği kullanıcıya uydurtmak değil sistemin giriş oturumu başında üretmesidir:

- Kullanıcı “işlem gir” dediğinde `manual_entry_id`/`command_id` oluşur.
- Commit sonucu kullanıcıya bir receipt ile döner.
- Çökme veya timeout sonrası aynı komut aynı kimlikle yeniden gönderilir; ikinci olay yazılmaz.
- İkinci gerçek alım için yeni giriş başlatılır ve yeni kimlik oluşur.

İşlem fingerprint’i idempotency anahtarı olmamalı. Yalnız uyarı üretmelidir:

> Aynı hesapta benzer zaman, miktar ve fiyatta başka bir kayıt var; bu ayrı bir fill mi?

Kullanıcı aynı işlemi günler sonra sıfırdan yeniden girerse sistem bunu kesin olarak bilemez. Bu kabul edilmesi gereken belirsizliktir; reconciliation yakalamalıdır. Bu nedenle manuel işlem kaydı “var olanı biliyoruz” der ama “başka işlem yok” demez. Güncel broker uzlaştırması olmadan tam pozisyon güveni üretilemez.

Hatalı kayıt silinmez; `portfolio_transaction_reversed` veya orijinale referans veren correction kaydıyla düzeltilir.

### 5. Portfolio-risk-management sözleşmesi

Bu oturumdaki mevcut `portfolio-risk-management` skill’ini okudum. Konuşmada tanımladığımız paket gerekli fakat tek başına yeterli değil. Skill ayrıca şunları bekliyor:

- Mevcut ve önerilen pozisyon büyüklüğü.
- Güncel fiyat ve `as_of`.
- Yatırım ufku ve katalizör.
- Portföy/benchmark bağlamı.
- Mandate ve risk limitleri.
- Likidite/çıkış kapasitesi.
- Loss budget ve stres senaryoları.
- Beta, sektör, faktör, FX, commodity ve yoğunlaşma exposure’ları.
- İstenmeyen risk ile korunmak istenen alpha ayrımı.
- Eksik implementasyon verileri ve karar readiness’i.

Dolayısıyla iki sözleşme ayrılmalı:

- Repo’nun kanonik `portfolio_snapshot.v1` sözleşmesi: tezler, beş eksen, lotlar, exposure, reconciliation, nakit/para birimi, fiyatlar, veri tazeliği ve mandate limitleri.
- Skill adapter sözleşmesi: kanonik snapshot’tan ilgili skill sürümünün ihtiyaç duyduğu context bundle/result contract üretimi.

Domain modelini tek bir skill sürümüne göre şekillendirmek yanlış olur. Skill değişirse adapter değişir; lot ve ledger gerçeği değişmez.

Skill entegrasyonu hazır olana kadar aylık rebalansı durdurmazdım. İlk sürüm:

- Sistem deterministik portföy paketini hazırlar.
- Eksik/unknown alanları görünür biçimde işaretler.
- İnsan paketi kendisi inceler ve `no_change/add/trim/exit/re_underwrite` kararını gerekçesiyle kaydeder.
- Gerçek işlemi yine insan ayrıca girer.
- Aylık `portfolio_review_completed` kaydı, kullanılan snapshot kimliğini ve reconciliation freshness’ini taşır.

Sonradan skill aynı paketi tüketerek öneri üretir; öneri `analysis_adjudicated` olmadan portföy kararına dönüşmez ve hiçbir koşulda işlem üretmez.

Bence burada ilk günden vazgeçilmemesi gereken kısım lot, para birimi, kurumsal işlem ve reconciliation provenance’ıdır. Gelişmiş vergi hesabı, supersede sonrası çift P&L attribution ve otomatik broker import’u ertelenebilir. Ama mutable ortalama-maliyet tablosuyla başlamak sonradan ucuz düzeltilemez; ilk gerçek işlemden önce lot tabanı kurulmalı.