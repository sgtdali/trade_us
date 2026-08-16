İki hükmüm var. Birincisi: önceki `analysis_proposed` önerimi geri çekiyorum; `result_attached` zaten öneriyi taşıyor. İkincisi: “tur” tek kavram altında hem evren kapsamasını hem finalist karşılaştırmasını taşıyor; asıl karmaşa buradan çıkıyor.

### Analiz sonucu ve kabul

Doğru akış bence şu:

`workflow_requested → workflow_prepared(attempt_id) → analysis_result_attached(proposed_outcome) → analysis_adjudicated`

`analysis_adjudicated.decision` üç değer alır:

- `accepted`
- `accepted_with_override`
- `rejected`

Burada ayrı bir `analysis_proposed` olayı gereksizdir. Öneri, immutable artefakt ve `proposed_outcome` ile zaten `analysis_result_attached` içindedir.

Tek kişinin çalıştırması ayrımı ortadan kaldırmıyor: öneriyi model üretiyor, kullanım yetkisini insan veriyor. Fakat her sonucun otomatik kabul edildiği bir pratik oluşursa sorun olay sayısı değil, sahte onay kapısıdır. Gerçek inceleme yapılmayan workflow’lar `machine_validated` politikasıyla ilerlemeli; deftere insan incelemiş gibi `accepted` yazılmamalı. İnsan kapısı konmuş workflow’da ise 12 ek satır önemsizdir; gerçek maliyet o satırlar değil, insanın okuma süresidir.

Reject, yeni bir `workflow_requested` üretmemeli. Kimlikler şöyle ayrılmalı:

- `workflow_request_id`: yapılması istenen mantıksal iş.
- `attempt_id`: o işi üretmek için yapılan belirli deneme.

Reject edilen deneme kapanır, aynı request altında yeni `attempt_id` açılır. İstek ancak amaç, workflow veya girdi kontratı maddi biçimde değişirse iptal edilip yeni request oluşturulur. Teknik hata da reject değildir; başarısız attempt’tir ve mantıksal request’i kapatmaz.

`accepted_with_override` gerçekten tehlikeli; görünmez bir edit kesinlikle olmamalı. Olay hem `proposed_outcome` hem `accepted_outcome` taşımalı ve ayrıca `overridden_fields`, `override_reason`, `reviewer` bulunmalı. Projection kabul edilen sonucu kullanır ama arayüz daima “model A önerdi, insan B’ye çevirdi” diye göstermelidir. Bir de sınır koyarım: desteklenmeyen sayı, yanlış kaynak veya yanlış peer gibi olgusal sorunlar override edilemez; bunlar reject ve yeni attempt gerektirir. Override yalnız bucket, önem derecesi veya eylem yorumu gibi açık insan hükümleri için kullanılabilir.

Dolayısıyla `workflow_completed` yine türetilmiş durumdur: request’in kabul edilmiş bir attempt’i varsa tamamlanmıştır.

### Tur ortasında uygunluğun değişmesi

Round manifesti tarihsel cohort’u dondurur; canlı uygunluğu dondurmaz. Bu ayrım dört senaryoyu çözüyor.

NVDA’ya Tur 1’den sonra tez açılırsa manifestten silinmez ama Tur 2’ye kabul edilmez. Sonucu `ineligible_before_selection`, nedeni `thesis_opened` olur. Kural çiğnenmez; tarih de yeniden yazılmaz.

Finalist kotasını korumak isteniyorsa Tur 1 sonucu yalnız finalistleri değil, en azından sıralı bir yedek listesini taşımalıdır. NVDA düştüğünde aynı donmuş dilimin sıradaki hâlâ uygun ismi deterministik olarak ilerler. Yedek sırası kaydedilmemişse sonradan dördüncü ismi seçmek yasaktır; slot boş kalır veya dilim açıkça yeniden çalıştırılır.

Tur ortasında tez kapanırsa isim mevcut tura eklenmez, sonraki coverage cycle’ı bekler. “Kalıcı unutulmama” sıfır gecikme demek değildir. Mevcut dilime iliştirmek snapshot’ı ve karşılaştırma setini bozar. Bir turluk gecikme kabul edilemiyorsa sorun snapshot değil, turun fazla uzun sürmesidir.

Evren değişikliklerinde de snapshot değişmez:

- Yeni eklenen isim sonraki cycle’a girer.
- Sektör veya boyut değişikliği mevcut dilimi değiştirmez.
- Delisting, birleşme veya menkul kıymetin ortadan kalkması canlı bir uygunluk iptalidir; isim analiz edilmez ve `ineligible` olarak kapanır.
- Ticker değişikliği üyelik değişikliği değil, kimlik eşlemesidir. Kalıcı kimlik ticker değil `security_id`/`issuer_id` olmalıdır.

Yani snapshot “artık var olmayan hisseyi mutlaka analiz et” demez; “bu turun başlangıç kapsamı buydu” der.

### Dilim kimliği

Üye listesinin donmasına katılıyorum. Fakat dilim kimliği yalnız listenin hash’i olmamalı:

- `slice_id`: tur manifestinde üretilmiş kalıcı kimlik.
- `membership_hash`: üye listesinin bütünlük kontrolü.
- `universe_snapshot_id`
- `slice_policy_version`
- Her denemede ayrıca `attempt_id` ve `input_snapshot_id`.

Kriter dilimin provenance’ıdır, kimliği değildir. Aynı dilim yeniden çalıştırıldığında üyeleri değişmez; yalnız attempt ve muhtemelen veri snapshot’ı değişir. Üyelik değişirse artık aynı dilim değildir.

### Waived dilim

Burada dokümandaki öneriyi bir noktada değiştiririm: teknik olarak `failed` olmuş bir attempt, dilimi terminal yapmamalı. Aksi hâlde tek model hatası tüm isimleri sessizce kapsam dışı bırakabilir.

Dilim için terminal durumlar şunlar olmalı:

- `completed`: kabul edilmiş analiz var.
- `cancelled`: bütün üyeler canlı olarak uygunsuz hâle geldi.
- `waived`: insan, bu dilim değerlendirilmeden turun ilerlemesine gerekçeli olarak izin verdi.

`waived` isimler finalist olmayan sayılmaz, C almaz ve bucket değişikliği yaşamaz. `round_stage1_closed` bunları `not_evaluated` olarak ve eksik kapsam oranıyla taşır. Tur 2 yalnız tamamlanmış dilimlerin sonuçlarını kullanır.

Sonraki turda özel öncelik kuralı koymazdım. İsimler zaten `evren − açık tezli isimler` formülüyle yeniden havuza girer. Böylece Başlık 6 bozulmaz. Bir tur daha beklemeleri, insanın partial close kararının açıkça kabul ettiği bedeldir. Öncelik kuyruğu ancak gerçek kullanımda starvation görülürse eklenmeli.

### Tur gerçekten gerekli mi?

Mevcut “round” iki ayrı şeyi gereksiz yere birleştiriyor:

1. `coverage_cycle`: Evrenin kimlerinin tarandığını ve kimlerin görülmediğini takip eder.
2. `selection_batch`: Hangi finalistlerin aynı anda karşılaştırıldığını tanımlar.

Bunları ayırmayı savunuyorum. Tur kavramını tamamen atmazdım; onu yalnız coverage muhasebesi olarak tutardım. Tur 2 ise açıkça donmuş bir `selection_batch` olur.

87 isimde varsayılan politika, bir coverage cycle kapanınca tek selection batch açmak olabilir; bugünkü tasarım aynen çalışır. 500’de aynı cycle içinde birden fazla bounded selection batch açılabilir. Her A/B/C hükmü mutlaka `comparison_set_id` taşır.

Önceki itirazım hâlâ mantıken geçerli: farklı aday setlerinde üretilen A/B/C’ler küresel olarak karşılaştırılabilir değildir. Fakat bundan çıkan sonuç “mutlaka bütün evreni bekle” olmamalı; “batch-relative hükmü evren-geneli hüküm gibi sunma” olmalıdır.

Tam sürekli akışa geçersek kaybettiğimiz şeyler nettir: bütün uygun isimlerin eşit fırsat bulduğu iddiası, evren-geneli A/B/C anlamı ve doğal tam-kapsam denetimi. Kazandığımız şeyler ise daha düşük gecikme, arızalı dilimlerin izolasyonu ve 500 isimde çalışabilirliktir.

Benim net tercihim: global tur bariyerini domain invariant’ı yapma; `coverage_cycle` ile `selection_batch`i şimdi ayır. İlk sürümde 87 isim için ikisini bire bir eşleştir. Gerçek gecikme veya ölçek baskısı çıktığında aynı olay sözleşmesiyle rolling batch’e geçebilirsin. Böylece bugün gereksiz operasyon karmaşası kurmaz, yarın da şemayı kırmak zorunda kalmazsın.