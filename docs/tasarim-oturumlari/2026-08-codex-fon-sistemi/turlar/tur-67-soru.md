Bu tam aradığım şeydi. Sabit dispatch tablosu (router değil), `fund research-cycle` günlük tek komut, Task Scheduler yeterli, ve değişen invariant: **"Aktif ve kullanıcı tarafından önceden onaylanmış bir dispatch kuralı analizi otomatik başlatabilir; araştırma hükmünün kabulü ve sermaye etkisi yine insana aittir."** Kullanıcının önüne boş form değil, çalıştırılmış sonuç gelmesi de doğru.

Ve iki aşamalı adjudication'ın bozulmadığı açıklaman ikna edici: amaç insanın modeli görmesini engellemek değil, araştırma hükmünü sermaye sonucundan ayırmaktı.

Şimdi ikinci itiraza geçiyoruz: TEZ TAKİBİ. Kullanıcı "bunu bu şekilde insana komple devredemezsiniz" dedi.

Son üç turda tez takibini şuna indirmiştik: `assessment_record` içinde bir downside yüzdesi ve bir `review_due` tarihi; `fund review` gecikmiş incelemeleri listeliyor. Yani sistem izlemiyor, yalnız tarihi hatırlatıyor. Bu yetersiz.

Ama tam monitoring motoruna da (typed metric ID'leri, PIT/restatement semantiği, `no_deviation`/`deviation`/`indeterminate`/`data_missing` sözlüğü, monitoring_contract_version, effective_at, policy revision kuralları) 8 tez için geri dönmek istemiyorum.

Aradığım şey yine "otomatik ama küçük". Sorularım:

(1) BU ÖLÇEKTE TEZ İZLEME GERÇEKTE NE YAPMALI? 8 açık tez, her birinin belki 2-4 koşulu. Bunların kaçı mekanik olarak kontrol edilebilir ve o kontrol ne kadar iş? Bence repo zaten ciddi bir avantaj sağlıyor: XBRL çıkarımı, normalize finansallar, point-in-time, market snapshot var. Yani "gelir büyümesi %15'in altına indi mi", "brüt marj 200 bp geriledi mi", "FCF marjı %20'nin altına indi mi" gibi şeyler mevcut boru hattından çekilebilir görünüyor. Doğru mu, yoksa aradaki eşleme (tezdeki koşul → repodaki metrik) sandığımdan pahalı mı?

(2) İZLEME SÖZLEŞMESİ EN KÜÇÜK HÂLİYLE NE OLUR? Tam sözleşme çok alanlıydı (metric_id, operator, unit, period basis, source contract, known_at policy, revision policy, tolerance, missing-data policy, effective_from, cadence). 8 tez için bunun kaçı gerçekten gerekli? Ve bir tez için kaç kural makul -- 2 mi 5 mi? Fazla kural koymak her hafta yanlış alarm, az koymak izlemeyi anlamsız yapıyor.

(3) NİTEL KOŞULLAR NE OLACAK? 11. turda tasarımın kendi kendini yalanladığı yeri bulmuştuk: ölçülemeyen koşullar "haftalık oturumda listelenir" deniyordu ama sapma yoksa oturum açılmıyordu. Bu ölçekte doğru çözüm ne -- nitel koşulun kendi `review_due`'su mu olmalı, yoksa yeni filing geldiğinde deep-dive zaten onlara bakacak mı?

(4) TEZ NESNESİ NE KADAR OLMALI? Şu an dört nesnemiz var (`capital_policy`, `assessment_record`, `decision_record`, `account_event`) ve tez ayrı bir nesne değil -- assessment'ın içinde. Ama "sistem tezi izlesin" diyorsak tezin kendi kimliği, durumu ve geçmişi olması gerekiyor gibi. 4. turdaki üç eksenli model (tez durumu `active`/`review_required`/`broken`/`closed` + gerçek exposure + tarihli değerlendirme) bu ölçekte doğru mu, yoksa daha da küçük mü olmalı?

Ve şunu net söyle: `assessment_record` ile `thesis` aynı şey mi, ayrı mı? Bir tez zaman içinde birden fazla assessment alıyor gibi görünüyor -- yani tez kalıcı nesne, assessment onun tarihli fotoğrafı. Doğru mu?

(5) VE İZLEMENİN ÇIKTISI NE OLUYOR? Mekanik kontrol bir sapma buldu. Sonra ne oluyor -- doğrudan `thesis-tracker` skill'i mi çalışıyor (yani 66. turdaki dispatch tablosuna bir kural daha mı ekleniyor), yoksa önce insana mı gösteriliyor? Ben ilkini savunuyorum çünkü sapmayı yorumlamak tam da skill'in işi. Ama o zaman her sapmada bir LLM çağrısı oluyor; yanlış alarm oranı yüksekse maliyet ve gürültü sorun olur.
