Alındı. Özellikle şunlar önemliydi: `standalone_downside_sum`'ın açıkça diagnostic olması (hepsi aynı anda olmaz varsayımı değil), binding constraint'in sıralı liste + `binding_state` ile temsili, headroom ile "en sıkı cap'ten uzaklık"ın ayrılması, bütün seçeneklerin AYNI şemayı kullanması ve hepsinin TÜM portföyü temsil etmesi (yalnız değişiklik parçalarını değil), `status_quo`'nun da tüm ölçüleri taşıması, `preferred_bps_nav`'ın zorunlu olmaması ("bandı savunabiliyor ama içindeki optimumu savunamıyorsa yapay kesinlik üretme"), ve proposal'ın immutable olup karar ekseninin ayrı projection olması.

Üç tur kaldı. Bu turda temel altyapıyı kapatalım: OLAY ZARFI VE DEPOLAMA. Kısa ve kesin olmanı istiyorum -- bu ikisi ilk yazılacak dosyalar.

(1) `event-envelope.schema.json`. 27. turda V2 zarfı için alan saymıştık (`sequence`, `batch_id`, `subject_type`/`subject_id`, `causation_id`, `occurred_at`/`recorded_at`). Şimdi kesin listeyi ver. Özellikle şunları netleştir:

- `subject` tek mi çoğul mu? Bir `reconciliation_completed` olayı hem hesabı hem birden fazla security'yi ilgilendiriyor. Tek subject + ek `related_refs` mi, yoksa çoklu subject mi?
- `causation_id` ve `correlation_id` ikisi de gerekli mi, yoksa biri yeterli mi?
- `actor` nasıl temsil edilir: insan mı sistem mi, ve hangi yetkiyle? (`operating_authority_ref` her olayda mı durmalı?)
- Idempotency anahtarı zarfın parçası mı yoksa payload'ın mı?
- `sequence` kim tarafından ne zaman atanır ve zarfın içinde mi yoksa depolama katmanında mı yaşar?

(2) SQLITE DEPOLAMA ŞEKLİ. Somut tablo listesi ve kritik constraint'ler. En az: events, batches, artifacts, snapshots/projections. Ama asıl merak ettiğim üç şey:

- Tek yazarlı commit kapısını SQLite'ta nasıl garanti ediyoruz? (WAL modu, `BEGIN IMMEDIATE`, tek bağlantı, dosya kilidi?)
- `global_position` ve `stream_position` nasıl atanır ve boşluksuz olmak zorunda mı?
- Batch atomikliği: bir batch'in tüm olayları tek transaction'da yazılıyor, tamam -- ama okuyucu yarım batch görebilir mi? (Yani projection okurken "commit edilmiş batch" filtresi gerekiyor mu, yoksa transaction bunu zaten sağlıyor mu?)

(3) VE PRATİK BİR SORU: Bu sistemde eşzamanlılık gerçekten var mı? Tek operatör, tek makine, elle tetiklenen işlemler. Belki de tek yazarlı kapı için karmaşık bir mekanizmaya gerek yok -- bir dosya kilidi ve "aynı anda iki komut çalıştırma" disiplini yetebilir. Ama 2. turda "disiplinle çözülür" cevabını çürütmüştük. Şimdi fon tarafında aynı soru: gerçek risk ne, ve en basit yeterli çözüm ne?

(4) Son olarak: bu üç dosya (`core-types`, `event-envelope`, SQLite DDL) yazıldığında elimizde çalışan ne olur? Yani ilk anlamlı "bu iş yürüyor" anı hangi noktada gelir?
