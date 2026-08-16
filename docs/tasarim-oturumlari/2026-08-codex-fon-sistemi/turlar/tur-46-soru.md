Gölge koşunun iki aşamalı olması (önce KÖR paralel, sonra kâğıt icra), `authority_level`'ın capital policy alanı değil ayrı `operating_authority` nesnesi olması, A0-A4 merdiveni, fark sözlüğünün önceden dondurulması ve "agreement rate başarı metriği değildir" uyarısı -- hepsi alındı. "Para bağlamayan bir prototip test edilmeden çalışabilir; sermaye miktarı öneren bir motor çalışamaz" cümlesi de doğrulama aparatının gerekçesi olarak dokümana girecek. Bu konu kapandı.

Şimdi ikinci ve son konuya geçiyoruz: SOMUT ŞEMA. Yedi tur var. Amaç, bu tartışmanın çıktısını "şu nesne şu alanları taşır" seviyesinden çıkarıp gerçekten yazılabilir hâle getirmek.

Bu turda üst düzey stratejiyi kararlaştıralım, sonraki turlarda nesne ailelerine ineriz.

Mevcut durum: repoda `schemas/` klasörü var ve 20+ JSON Schema dosyası taşıyor (company, financial-*, market-*, eod-*, pei-*-extraction, pei-workflow-event...). Yani bu repo zaten JSON Schema kullanıyor ve `jsonschema` ile doğruluyor.

(1) KAÇ TEMSİL, HANGİSİ OTORİTE? Elimizde en az üç temsil ihtiyacı var: olay şeması (deftere ne yazılabilir), depolama şeması (SQLite tabloları), ve projection/okuma şeması (pozisyon, NAV, risk snapshot gibi türetilmiş görünümler). Bunlar aynı şeyin üç yüzü mü, yoksa bağımsız mı? Ben şunu düşünüyorum: **olay şeması otoritedir**, depolama ondan türetilir (veya en azından ona uymak zorundadır), projection ise tamamen türetilmiş olduğu için kendi şemasına ihtiyaç duymaz -- yalnız kod içi tip olur. Ama emin değilim: projection'ın da sözleşmesi olması gerekir mi (ör. `portfolio_risk_snapshot` bir dosyaya yazılıp saklanacaksa)?

(2) PARA NASIL TEMSİL EDİLİR? Bu bence en pahalı "sonradan değiştirilemez" karar. Seçenekler: float (kesinlikle hayır), decimal string ("123.45"), veya tamsayı minor unit (12345 cent). Fon sisteminde ağırlık hesapları, NAV, kayıp bütçesi bp hesapları, FX çevrimi ve kısmi hisse hepsi bu karara bağlı. Ne öneriyorsun ve hangi alanlarda hangi tip? Ayrıca ADET nasıl temsil edilir -- kesirli hisse var mı, varsa nasıl?

(3) ZAMAN NASIL TEMSİL EDİLİR? Bu tartışmada bir sürü zaman ekseni türettik: `as_of`, `known_at`, `period_end`, `occurred_at`, `recorded_at`, `market_as_of`, `effective_from`, `settlement_date`, `trade_date`. Hepsi UTC timestamp mı, bazıları tarih mi? Borsa günü kavramı (trade date) ile timestamp'i karıştırmamak lazım. Ve kullanıcı Türkiye'de, borsa ABD'de -- "bugün" ne demek?

(4) KİMLİKLER. `event_id`, `security_id`, `thesis_id`, `proposal_id`, `attempt_id`, `lot_id`... Format ne olmalı: UUID mi, ULID mi (sıralanabilir), yoksa okunabilir prefix'li mi (`PROP-2026-0001`)? Tek kişilik bir sistemde okunabilirlik önemli ama çakışma riski de düşük. Ve `security_id` özel bir durum: ticker olamayacağını konuştuk, ama ne olacak -- CIK mi, FIGI mi, kendi ürettiğimiz bir id mi?

(5) SÜRÜMLEME. Şema sürümü nerede durur: dosya adında mı (`capital-policy.v1.json`), dokümanın içinde bir alanda mı, ikisinde de mi? Ve bir şema değiştiğinde eski olaylar ne olur -- her olay kendi şema sürümünü mü taşımalı?

(6) Ve pratik bir soru: bu şemaları yazmak kaç dosya eder ve hangi sırayla yazılmalı? Yani yarın oturup şema yazmaya başlasak, ilk hangi dosyayı açarız?
