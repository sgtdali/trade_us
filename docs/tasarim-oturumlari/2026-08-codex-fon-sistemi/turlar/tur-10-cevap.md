Net hükmüm: kanonik canlı defter Git’te olmamalı. Git kodun ve şemaların geçmişidir; olay defterinin yazma otoritesi değildir. Git’te ancak kanonik defterden üretilmiş, mühürlü denetim checkpoint’leri bulunabilir.

Bunu özellikle güçlü söylüyorum çünkü geçmişi kontrol ettiğimde dosya için üç değil yedi commit görünüyor; aralarında `Reset PEI workflow history for a clean start` ve `Reset the shortlist idea run for a clean restart` da var. Yani V1 defteri yalnız teoride değil, fiilen de daha önce yeniden yazılmış.

### 1. Sequence ve Git dalları

Monoton `sequence` kalmalı, fakat yalnız tek kanonik ledger içinde anlamlı olmalı. Branch üzerinde kanonik sequence üretmek yasak olmalı.

Kimlikler şöyle ayrılır:

- `event_id`: dal ve makineden bağımsız UUID/ULID.
- `batch_id`: birlikte kabul edilen olayların kimliği.
- `sequence`: yalnız kanonik writer’ın commit anında verdiği sıra.
- `batch_index`: olayın batch içindeki sırası.

İki branch’in ürettiği analizler kanonik olay değil, henüz sequence almamış draft/import paketleridir. Kanonik writer’a ulaştıklarında güncel projection’a karşı yeniden doğrulanır, çakışmıyorlarsa sequence atanarak commit edilirler. İki süreç aynı makinede de farklı branch’lerde de çalışsa aynı yazma kapısına gider.

Hash zinciri sequence’ın alternatifi değildir. İki dal iki farklı parent hash’ten devam ederse yalnız ledger fork’u üretir; “hangisi gerçek?” sorusunu çözmez. Hash zinciri bütünlük kontrolüdür, yazma koordinasyonu değildir.

Fiziksel olarak burada SQLite’ı savunurum. Event sourcing, JSONL kullanmak demek değildir. SQLite transaction’ı çoklu süreç yazımlarını serileştirir; on binlerce olay bu ölçek için önemsizdir. `events.jsonl` istenirse deterministic export olarak üretilebilir ama sisteme geri okunacak otorite olmaz.

### 2. Batch atomikliği

Batch’i tek bir domain olayı veya dev bir JSON satırı yapmazdım. Domain olayları ayrı kalmalı; atomiklik fiziksel depoda sağlanmalı.

Kavramsal model:

- `batches`: `batch_id`, olay sayısı, ilk/son sequence, önceki batch hash’i, batch hash’i, commit zamanı.
- `events`: `event_id`, `batch_id`, `batch_index`, `sequence`, zarf ve payload.

Tek DB transaction’ı batch satırını ve bütün olaylarını birlikte yazar. Ya tamamı görünür ya hiçbiri görünmez. Projection yalnız committed batch’leri okur.

Hash’i olay başına değil batch başına zincirlemek daha anlamlıdır:

`batch_hash = hash(previous_batch_hash + canonical_batch_content)`

Snapshot da `(ledger_id, through_batch_id, through_sequence, ledger_root_hash)` taşır. Batch içindeki olayların dosyada art arda durmasına güvenmez.

JSONL otorite olarak korunacaksa ikinci tercih, tek büyüyen dosya yerine her batch için immutable segment dosyasıdır: önce geçici dosya, sonra aynı filesystem içinde atomik rename. Fakat bunun index ve kurtarma mekaniği kısa sürede küçük bir veritabanına dönüşür. SQLite daha dürüst çözümdür.

### 3. Git geçmişinin yeniden yazılması

Risk gerçektir ama ikiye ayrılmalı.

Snapshot yalnız path veya sequence’a bakarsa geçmiş yeniden yazıldığında sessizce yanlış veriye bağlanabilir. Snapshot zorunlu olarak content hash doğrularsa farklı içerik aynı snapshot gibi görünemez; hash uyuşmaz ve sistem durur. Git rewrite bu durumda sessiz doğruluk hatası değil, erişilebilirlik hatası üretir.

Yine de hash zinciri tek başına kötü niyetli yeniden yazmayı engellemez: defteri değiştiren biri bütün sonraki hash’leri de yeniden hesaplayabilir. Bunun için dışarıda sabitlenmiş checkpoint gerekir. Bu sistemin gerçekçi tehdit modeli muhtemelen kötü niyetli operatör değil, kazara silme ve bozuk merge’dür. Dolayısıyla şunlar yeterli:

- Kanonik ledger Git dışında.
- Düzenli, bağımsız ve geri yüklenebilir backup.
- Git’e veya başka arşive periyodik mühürlü checkpoint manifesti.
- Snapshot açılırken zorunlu hash doğrulaması.

Regülatör düzeyinde değiştirilemezlik istenirse imzalı checkpoint veya harici WORM arşiv gerekir; bugün bunu kurmak YAGNI olur.

Ayrıca append-only sistemde Git revert, rebase veya checkout domain geri alma mekanizması olamaz. Hatalı olaylar silinmez; düzeltme, iptal veya reversal olayı eklenir.

### Defter ve artefaktlar Git’te nasıl ayrılmalı?

“Repo’dan yeniden üretilebilirlik” ilkesini düzeltmek gerekiyor. Doğru formül şudur:

`Git code revision + kanonik ledger checkpoint + içerik-adresli artefakt deposu`

Repo tek başına canlı operasyonel gerçeğin tamamı değildir.

Git’te kalması gerekenler:

- Kod, şemalar, config ve migration tanımları.
- Workflow talimatları ve şablonlar.
- İstenirse kanonik ledger’dan üretilmiş mühürlü checkpoint manifestleri.
- Küçük ve lisans açısından sakıncasız, immutable araştırma artefaktlarının kopyaları.

Git’in dışında, içerik hash’iyle saklanması gerekenler:

- Kanonik ledger/SQLite dosyası ve backup’ları.
- Kullanılmış context bundle ve exact input pack.
- `result.md` ve yapılandırılmış extraction.
- Portföy işlemleri ve pozisyon verisi.
- Büyük, lisanslı veya hassas veri artefaktları.

Artefaktların tamamını Git’ten çıkarmak şart değil; önemli olan Git kopyasının otorite olmaması ve çalışma branch’ine bağlı path’lerin kanonik olaylarda kullanılmaması. Olay, `artifact_dir/result.md` gibi kırılgan bir path yerine `artifact_id`, SHA-256, boyut ve media type taşımalı.

### 4. Çok-artefaktlı atomiklik

Filesystem ile ledger arasında gerçek tek transaction yok. Bunu iki-fazlı commit icat ederek değil, işlemleri doğru sıraya koyarak çözeriz:

1. Result ve extraction geçici staging alanında tamamen yazılır.
2. Dosyalar kapatılır, mümkünse flush/fsync yapılır.
3. Şema, kaynak ve kontrat doğrulamaları çalışır.
4. Her artefaktın hash’i ve boyutu hesaplanır.
5. Artefaktlar aynı filesystem içindeki içerik-adresli nihai konumlarına atomik rename ile yayımlanır.
6. En son DB transaction’ı olayları ve artefakt referanslarını commit eder.

Bu sırayla committed bir olayın yarım artefakta işaret etmesi normal süreç çökmesiyle mümkün olmaz. Çöküş 5 ile 6 arasında olursa yalnız yetim ama eksiksiz bir artefakt kalır. Bu zararsız ve tercih edilen hata yönüdür.

Her açılışta bütün geçmişi taramak gereksizdir. Başlangıç kurtarması yalnız:

- staging’de kalan geçici dosyaları,
- son commit/batch’in bütünlüğünü,
- bekleyen attempt’leri

kontrol eder. Tam artefakt-hash taraması periyodik bakım olabilir. Referanssız nihai artefaktlar hemen silinmemeli; `attempt_id` sayesinde kurtarılabilir, belirli bir bekleme süresinden sonra garbage collection’a aday olur.

`agy` extraction da ayrıca immutable artefakt sayılmalı. Event gerekli normalize edilmiş hükmü taşıyabilir ama extraction’ın tam çıktısına hash ile geri dönebilmelidir.

### 5. V1’den V2’ye göç

Projector’ın sonsuza kadar iki zarf bilmesini savunmuyorum. Fakat V1 dosyasını yerinde değiştirip aynı ledger’mış gibi davranmayı da savunmam.

Doğru çözüm yeni bir ledger generation başlatmaktır:

1. V1 dosyası olduğu gibi dondurulur.
2. V1’in tam hash’i ve olay sayısı kaydedilir.
3. Deterministik migration ile yeni bir V2 ledger üretilir.
4. V2 genesis/checkpoint kaydı şunları taşır:
   - kaynak `ledger_id`
   - V1 root hash
   - 57 kaynak olay
   - migration sürümü ve mapping manifesti
   - üretilen V2 root hash
5. Runtime projector yalnız V2 bilir.
6. Ayrı bir migration doğrulayıcısı gerektiğinde V1’den V2’yi tekrar üretip hash’i karşılaştırabilir.

Bu append-only ilkesinin ihlali değildir; eski ledger’ı yeniden yazmıyorsun, yeni temsilli bir ledger lineage başlatıyorsun. Append-only ilkesi, veri formatının sonsuza kadar değişemeyeceği anlamına gelmez.

Eski `event_id`’ler mümkün olduğu yerde korunabilir. Bir V1 olayı iki gerçeğe ayrılmak zorundaysa yeni kimlikler deterministik biçimde eski kimlikten türetilir ve mapping manifestine yazılır. Eksik bilgi uydurulmaz; `legacy_import` ve `unknown` olarak işaretlenir.

57 olay ve tek gerçek run varken bunu şimdi yapmak doğru. İki yıl sonra binlerce olay arasında V1’in üç anlamlı `source_interpretation_corrected` kayıtlarını yorumlamak çok daha pahalı olur.

Özet kararım: V1’i mühürle, V2’yi yeni kanonik ledger olarak kur, kanonik sequence’ı tek writer/SQLite transaction’ıyla ver, Git’i ise kod geçmişi ve mühürlü denetim aynası olarak kullan. “Branch üzerinde olay üretip JSONL merge etmek” desteklenen bir çalışma biçimi olmamalı.