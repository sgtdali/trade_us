Haklısın: önceki cevabımda `commit` derken analitik onay kapısını sessizce yutmuşum. `validate → commit` otomatik olabilir demek, mevcut anlamıyla insanın analiz onayını kaldırmak olurdu.

Asıl sorun `approval` kelimesinin iki farklı şeyi taşıması:

- “Bu olay deftere teknik olarak kabul edilebilir.”
- “Bu analitik hükme güveniyorum ve sonraki kararlar bunu kullanabilir.”

Bunlar ayrılmalı.

## Onay kapılarını nasıl keserdim?

| Sınıf | Örnek | Kural |
|---|---|---|
| Makine doğrulanabilir | Şema, hash, kaynak varlığı, sayısal tie-out, trigger karşılaştırması | Otomatik çalışır ve sistem yetkisiyle kaydedilir |
| Analitik yargı | Bucket, peer seçimi, valuation yorumu, pitch actionability, thesis status | Downstream kullanımdan veya state değişiminden önce insan kabulü gerekir |
| Gerçek-dünya icrası | Alım, satım, pozisyon relink, portföy uzlaştırması | Her zaman açık insan eylemi; otomatikleştirilemez |

Bugünkü `approval.status=approved` alanını “analiz doğrudur” diye değil, “olayın ledger’a yazılması yetkilendirildi” diye yorumlamak gerekir. Bir model sonucunun üretildiği, sistem tarafından otomatik kaydedilebilir bir gerçektir; içeriğinin kabul edildiği anlamına gelmez.

Bu nedenle olay dizisi kavramsal olarak şöyle olmalı:

```text
analysis_generated
analysis_validation_completed
analysis_accepted_for_use | analysis_rejected
```

İlk ikisi sistem olayıdır. Üçüncüsü analitik artefaktlarda insan olayıdır. Projection, bucket veya workflow rotasını ancak `accepted_for_use` sonrasında değiştirmelidir.

Ortadaki sınıf için kuralım şu:

> Bir model çıktısı başka bir yargı workflow’una controlling input olacaksa, adayları eleyecekse veya kalıcı lifecycle geçişi doğuracaksa önce insan tarafından `accepted_for_use` edilmelidir.

Bu, yalnız zincir sonunda onaydan daha güvenli. Yanlış peer seçilmiş bir comps’u otomatik olarak pitch’e sokup hatayı zincirin sonunda yakalamak hem maliyetli hem anchoring yaratır. Ama her teknik alt artefakta insan onayı da gerektirmez: pack üretimi, normalize veri, kaynak bağlama ve mekanik kontroller otomatik olabilir.

Somut karşılıkları şöyle:

Tur 1 sonucu, isimleri Tur 2’den elediği için dilim bazında insan kabulü ister; ticker başına değil. Tur 2 bucket’ları topluca kabul edilir. Tearsheet, comps ve earnings çıktıları sonraki analize girmeden artefakt düzeyinde kabul edilir. Pitch kabul edildiğinde ayrıca ikinci bir “tez açayım mı?” onayı istemem: kabul edilmiş `actionable_candidate` sonucu otomatik ve atomik olarak `thesis_opened` üretir. Portföy önerisinin kabulü ise gerçek işlem değildir; işlem hâlâ ayrı insan eylemidir.

Bu model otomasyonun sınırını netleştirir: orkestratör üç mekanik komutu tek çalıştırmaya indirebilir, fakat `accepted_for_use` kapısında durur. İnsan işi ortadan kalkmaz; klavye işi azalır. Eğer 40 analitik artefakt gerçekten insan yargısı gerektiriyorsa bunu otomasyonla yok olmuş gibi gösteremeyiz. Ya aktif zincir sayısını azaltırız ya da daha fazla makine doğrulaması geliştiririz.

## İlk iki-üç turda gerçekten patlayacaklar

Bunları kronolojik riskle ayırıyorum.

### İlk üretim olayından önce çözülmesi gerekenler

En başta onay semantiği çözülmeli. `approved` hem ledger admission hem analitik endorsement olarak kalırsa daha sonra otomasyon eklemek bütün geçmiş olayların anlamını belirsizleştirir. Bu doğrudan olay şemasına şimdi girmeli.

Tek commit kapısı da ilk paralel dilimden önce zorunlu. Mevcut read-modify-replace, 87 isimde bile iki süreç aynı anda yazdığı ilk gün sessiz veri kaybettirir. Segment ve snapshot şart değil; fakat yazımların seri olması, batch kimliği, monoton sequence ve atomik commit sınırı şimdi gerekli.

Tur 1/Tur 2 olay semantiği de ilk turdan önce tanımlanmalı: round manifesti, slice kimliği, dilim terminal durumları, toplu Tur 1 sonucu ve ayrı Tur 2 bucket sonucu. Aksi hâlde ilk yarım kalan dilimde turun kapatılıp kapatılamayacağı ve Tur 1’de elenen ismin ne olduğu belirsizleşir.

### İlk B adayı ve ilk ikinci turdan önce çözülmesi gerekenler

B terfi fallback’i hemen düzeltilmeli. `unresolved → thesis_tracker → required pitch` yolu ilk gerçek B zincirinde kendi kapısını dolanır. B için tracker’ın pre-thesis watchlist olmadığı şimdi sabitlenmeli.

Aktif araştırma zincirine gelen yeni screen’in yalnız evidence olması da ikinci turdan önce gerekli. Aksi hâlde tearsheet/comps tamamlamış fakat pitch bekleyen ilk ticker, yeni screen tarafından geri sarılır veya tamamlanmış işi çöpe gider.

`completed_workflow` kaydı da şimdiden yalnız isim olmaktan çıkmalı. En az workflow instance kimliği, tamamlanma zamanı, input/context snapshot kimliği ve ilgili veri dönemlerini taşımalı. Kesin freshness politikaları daha sonra kalibre edilebilir; fakat provenance alanları ilk günden yoksa eski tamamlanmaları sonradan güvenilir biçimde dolduramayız.

Session resume içinse tersine karar verirdim: ilk sürümde uzun ömürlü resume kurmazdım. Her adımı persisted context bundle ile fresh session’da çalıştırırdım. Önce denetim ve bağlam doğruluğunu kanıtlar, resume’u daha sonra yalnız optimizasyon olarak eklerdim.

### İlk tez açılmadan önce çözülmesi gerekenler

`pitch completion → thesis_opened` aynı global ledger’da atomik olmalı; ticker tracker yalnız projection olmalı. Causal idempotency anahtarı ve “ticker başına en fazla bir açık tez” invariant’ı ilk tezden önce zorunlu. Aksi hâlde ilk actionable pitch bile çift-defter veya çift-tez hasarı yaratabilir.

Beş eksen ve `wind_down` da ilk tez kaydıyla birlikte gelmeli. Bunları sonradan eklemek eski `retired` olaylarının ne anlama geldiğini yorumlama göçü yaratır.

Buna karşılık tam `superseded` workflow’unu şimdi kurmak gerekmez. Değer şemada bulunabilir veya sonradan eklenebilir; fakat re-underwrite pitch, atomik tez değiştirme ve pozisyon relink mekanizmasını gerçek bir supersede ihtiyacı çıkana kadar inşa etmek YAGNI olur.

### İlk gerçek işlemden önce çözülmesi gerekenler

`portfolio_transaction_recorded`, işlem idempotency’si, tez referansı, `portfolio_reconciled` ve `position_unknown` ilk gerçek işlem sisteme alınmadan önce zorunlu. Burada “sonra düzeltiriz” tehlikelidir; işlem yokluğunu `flat` sayan geçmiş veri üretildiğinde hangi dönemlerin gerçekten uzlaştırıldığını geri kuramayız.

Haftalık monitoring pack’i, her kontrolün izi ve `no_deviation/deviation/indeterminate/data_missing` ayrımı ise ilk otomatik haftalık kontrolden önce yapılmalı. Discovery’nin ilk sürümünü çıkarmak için şart değildir.

## Güvenle ertelenebilecekler

Fiziksel ledger segmentasyonu ve projection snapshot’ları bugün gerekli değil. Şemada sequence/batch sınırını hazırlamak yeterli; gerçek performans ölçülene kadar tek kilitli append akışı ve tam replay 87 isimde çalışabilir. On binlerce olaya gelmeden optimizasyon yapılabilir.

500 isim için hiyerarşik Tur 2 de bugün yapılmamalı. Önce 87 isimde gerçek finalist sayısı ve context kalitesi ölçülmeli. Tek Tur 2’nin sınırı gerçekten görülmeden üçüncü kademe icat etmek YAGNI olur.

Tekrarlanan `route_unsupported` için fingerprint/cooldown mekanizması da ertelenebilir. İlk birkaç turda gürültü ölçülmeden genel bir susturma politikası kurmak, değişmiş bir fırsatı yanlışlıkla bastırabilir.

Otomatik qualitative trigger yorumlama, broker entegrasyonu, çoklu hesap desteği, eşzamanlı birden fazla açık tez ve arka plan scheduler’ı da bugün yapılmamalı.

## Şu an özellikle düzeltilmemesi gerekenler

Uzun ömürlü Codex session altyapısı kurulmamalı; fresh session + tam context bundle daha basit ve denetlenebilir.

Genel amaçlı `reconciliation_required` durumu eklenmemeli; yeni screen aktif zincirde evidence olarak kalmalı ve pitch tarafından tartılmalı.

Her olası lifecycle kombinasyonu için ayrı event type üretilmemeli. Event’ler gerçek domain eylemlerini taşımalı; `funded`, `monitoring_required`, `watchlist` gibi değerler mümkün olduğunca projection’dan türetilmeli.

`superseded`, hiyerarşik turnuva, segment rotation ve otomatik tam zincir yürütme ilk sürümün kritik yolu değil. Bunların extension point’leri korunmalı ama mekanizmaları şimdiden kurulursa henüz görmediğimiz kullanım desenleri için gereksiz mimari üretiriz.

Ben ilk uygulama sınırını şu cümleyle koyardım:

> Önce olayların anlamını, atomikliğini ve kim tarafından kabul edildiğini doğru kur; ardından tek bir 87 isimlik turu fresh session’larla, batch onaylarla ve gerçek tez açılışına kadar uçtan uca yürüt. Ölçek optimizasyonlarını ancak bu akıştan ölçüm aldıktan sonra ekle.

Bu yaklaşım 500 hedefini kapatmıyor; fakat 500 için tasarlıyoruz diye ilk sürümde dağıtık event sistemi, çok seviyeli turnuva ve uzun ömürlü session yönetimi icat etmemizi engelliyor.