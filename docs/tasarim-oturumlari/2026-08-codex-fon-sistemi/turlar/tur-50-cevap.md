## 1. `event-envelope.schema.json`

Karar: **tek primary subject + çoğul related refs**. Çoklu primary subject, stream sıralamasını belirsizleştirir.

`reconciliation_completed` örneğinde primary subject `account`; etkilenen security’ler `related_refs` olur.

```json
{
  "schema_version": "1.0.0",
  "event_id": "uuidv7",
  "event_type": "fund.reconciliation_completed",
  "event_version": "1.0.0",
  "batch_id": "uuidv7",

  "scope": {
    "scope_type": "fund",
    "scope_id": "uuidv7"
  },

  "subject": {
    "subject_type": "account",
    "subject_id": "uuidv7"
  },

  "related_refs": [
    {
      "relation": "affects",
      "subject_type": "security",
      "subject_id": "uuidv7"
    }
  ],

  "correlation_id": "uuidv7",
  "causation": {
    "kind": "event",
    "id": "uuidv7"
  },

  "actor": {
    "actor_type": "human",
    "actor_id": "uuidv7"
  },

  "authority_basis": {
    "mode": "explicit_user_action"
  },

  "idempotency": {
    "scope": "broker:account-id:reconciliation",
    "key": "statement-id:2026-09-01"
  },

  "occurrence": {
    "precision": "instant",
    "occurred_at": "2026-09-01T20:01:00Z"
  },

  "recorded_at": "2026-09-01T20:02:00Z",
  "artifact_refs": [],
  "payload": {}
}
```

### Kesin hükümler

- `subject` tektir. Gerçekten çoklu aggregate değişimi gerekiyorsa tek batch içinde her stream için ayrı olay yazılır.
- `correlation_id` zorunludur; bütün iş akışını bağlar.
- `causation` ayrıca gereklidir; doğrudan nedeni gösterir:

```text
root | command | event | decision
```

Root olayında:

```json
{"kind": "root"}
```

- `actor` zorunludur:

```text
human | system | external_source
```

System actor ayrıca `component_id` ve `component_version`; external source `source_id` taşır.

- `operating_authority_ref` her olayda bulunmaz. `authority_basis` ayrık nesnesi kullanılır:

```text
not_required
explicit_user_action
operating_authority
external_observation
```

`operating_authority` ise grant ref zorunludur. Fill gibi dış gerçeklerde `external_observation` kullanılır.

- Idempotency payload’a değil zarfa aittir. Commit mekanizması payload şemasını açmadan duplicate’i yakalayabilmelidir.
- `batch_id`, commit kapısı tarafından transaction öncesinde atanır ve zarfın parçasıdır.
- `recorded_at`, commit kapısı tarafından atanır.
- `occurred_at` her zaman bilinemeyeceği için `occurrence` ayrık tiptir:

```json
{"precision": "instant", "occurred_at": "UtcInstant"}
{"precision": "date", "occurred_on": "LocalDate"}
```

- Eski genel `approval` alanı kaldırılır. Onay, ayrı bir domain olayıdır.
- `sequence` zarfın içinde değildir. Storage metadata’dır.

## 2. SQLite depolama

### Asgari tablolar

| Tablo | İşlev |
|---|---|
| `schema_migrations` | DDL sürümü |
| `event_batches` | Atomik commit ve request idempotency |
| `event_streams` | Her primary subject stream’inin head pozisyonu |
| `events` | Kanonik olaylar |
| `artifacts` | Immutable artefakt metadata’sı |
| `event_artifacts` | Event–artifact rol bağlantısı |
| `artifact_dependencies` | Artefakt bağımlılık DAG’ı |
| `projection_checkpoints` | Projector’ın son işlediği global position |
| `projection_snapshots` | Immutable projection snapshot referansları |

Domain tabloları (`positions`, `cash`, `lots`, `nav`) bundan sonra gelir ve tamamen yeniden üretilebilir cache’lerdir.

### `event_batches`

Kritik alanlar:

```text
batch_id                    UUIDv7 PK
request_idempotency_scope   TEXT
request_idempotency_key     TEXT
correlation_id              UUIDv7
recorded_at                 UtcInstant
event_count                 INTEGER
batch_digest                sha256
writer_instance_id          TEXT
expected_stream_heads_json  TEXT
```

Constraint:

```text
UNIQUE(request_idempotency_scope, request_idempotency_key)
CHECK(event_count > 0)
CHECK(json_valid(expected_stream_heads_json))
```

Batch için `pending/committed` status tutulmaz. Transaction başarılıysa batch vardır; başarısızsa hiç yoktur.

### `event_streams`

```text
stream_type
stream_id
last_stream_position
```

```text
PRIMARY KEY(stream_type, stream_id)
CHECK(last_stream_position >= 0)
```

### `events`

Kritik alanlar:

```text
global_position      INTEGER PRIMARY KEY
event_id             UUIDv7 UNIQUE
batch_id             UUIDv7 FK
batch_index          INTEGER
stream_type
stream_id
stream_position      INTEGER
event_type
event_version
recorded_at
correlation_id
idempotency_scope
idempotency_key
envelope_json
event_digest
```

Constraint’ler:

```text
UNIQUE(batch_id, batch_index)
UNIQUE(stream_type, stream_id, stream_position)
UNIQUE(idempotency_scope, idempotency_key)
UNIQUE(event_digest)
CHECK(batch_index >= 0)
CHECK(stream_position > 0)
CHECK(json_valid(envelope_json))
```

`events` ve `event_batches` üzerinde `UPDATE` ve `DELETE` işlemlerini reddeden trigger bulunmalı.

### Pozisyon atama

- `global_position`, SQLite tarafından insert sırasında atanır.
- `stream_position`, commit kapısı tarafından `event_streams` head’i okunup artırılarak atanır.
- İkisi de yalnız commit transaction’ı içinde oluşur.
- İkisi de **boşluksuz olmak zorunda değildir**.
- Güvence: benzersiz, monoton sıralama. “Pozisyon 57 yoksa veri bozuk” varsayımı yapılmaz.
- Komutun `expected_stream_position` değeri mevcut head ile uyuşmuyorsa commit `stale_stream` ile reddedilir.

`global_position` ve `stream_position`, okuma API’sinin döndürdüğü committed event record’da görünür; event’in hash’lenen domain zarfında bulunmaz.

## Tek yazarlı commit

En küçük yeterli çözüm:

```text
SQLite local file
PRAGMA journal_mode=WAL
PRAGMA synchronous=FULL
PRAGMA foreign_keys=ON
PRAGMA busy_timeout=5000
BEGIN IMMEDIATE
```

Commit akışı:

1. `BEGIN IMMEDIATE`
2. Batch idempotency anahtarını kontrol et.
3. Expected stream head’lerini doğrula.
4. Stream position’ları ayır ve head’leri güncelle.
5. Batch satırını ekle.
6. Bütün event, artifact metadata ve linklerini ekle.
7. `COMMIT`

Duplicate batch retry edilirse yeni olay üretilmez; önceden commit edilmiş batch döndürülür.

Global tek bağlantı veya ayrı daemon gerekmez. Her süreç kendi SQLite bağlantısını açabilir; SQLite writer lock onları serileştirir. “Tek yazarlı” burada tek fiziksel bağlantı değil, **tek commit kod yolu + SQLite’ın tek writer transaction’ı** demektir.

### Okuyucu yarım batch görebilir mi?

Hayır. Batch satırı, olaylar, stream head güncellemeleri ve linkler aynı transaction’daysa SQLite okuyucusu ya eski state’i ya da tamamını görür.

Bu nedenle:

- `committed = true` filtresi gerekmez.
- Yarım batch temizleme mekanizması gerekmez.
- Projection, kendi okuma transaction’ı içinde tutarlı snapshot görür.
- Projector state’i ile checkpoint’i de aynı projection transaction’ında yazılır.

Artifact bytes DB dışında tutuluyorsa önce immutable dosya yazılır, sonra DB transaction’ında kaydedilir. Çökme yalnız zararsız yetim dosya bırakabilir; olayın referans verdiği eksik artefakt bırakmamalıdır.

## 3. Gerçek eşzamanlılık riski

Tek operatöre rağmen eşzamanlılık vardır:

- İki terminal komutu.
- Dashboard ile CLI’ın aynı anda yazması.
- Import retry’ı.
- Trigger süreci ile manuel işlem.
- Kullanıcının aynı düğmeye iki kez basması.
- Çökme sonrası aynı komutun yeniden çalıştırılması.

Dosya kilidi + disiplin yeterli değildir; stale lock, unutulan kod yolu ve crash recovery sorunları doğurur.

En basit yeterli çözüm:

- Haricî lock dosyası yok.
- Queue/daemon/leader election yok.
- Yerel SQLite.
- Bütün yazımlar için tek `commit_batch()` uygulama kapısı.
- `BEGIN IMMEDIATE`.
- DB unique constraint’leri.
- Batch ve event idempotency.
- Expected stream position kontrolü.

WAL correctness sağlamaz; okuyucuların writer sırasında çalışmasını kolaylaştırır. Correctness’i transaction ve constraint’ler sağlar.

SQLite dosyası ağ paylaşımında veya Git içinde yaşamamalı; yerel diskte olmalı ve SQLite backup API ile yedeklenmelidir.

## 4. İlk anlamlı çalışma anı

Üç dosyanın yalnız yazılması henüz çalışan fon üretmez; yalnız sözlüğü ve depolama anayasasını verir.

İlk gerçek “altyapı çalışıyor” kapısı şu testtir:

1. İki olaylı bir batch commit edilir.
2. Aynı request tekrar gönderildiğinde duplicate oluşmaz.
3. İki eşzamanlı writer’dan olay kaybolmaz.
4. Commit ortasında zorlanan crash sonucunda okuyucu ya sıfır ya iki olay görür; bir olay göremez.
5. DB kapanıp açıldıktan sonra replay aynı sıralı event setini verir.
6. Stale `expected_stream_position` commit’i reddedilir.
7. Event veya batch `UPDATE/DELETE` edilemez.

İlk **domain anlamlı** an ise hemen sonraki küçük dikey dilimdir:

```text
opening_account_state_asserted
→ atomik commit
→ cash/position projection
→ replay
```

Aynı açılış batch’i iki kez içeri alındığında pozisyon ve nakit ikiye katlanmıyorsa, crash sonrası aynı projection yeniden üretilebiliyorsa, fon omurgasının gerçekten yürümeye başladığı ilk an odur.

### Karar özeti

- Primary subject tek; diğer varlıklar `related_refs`.
- Correlation ve causation farklı işler yaptığı için ikisi de korunur.
- Yetki her olayda değil, koşullu `authority_basis` ile taşınır.
- Sequence domain zarfında değil SQLite metadata’sındadır.
- SQLite transaction zaten batch görünürlüğünü atomik sağlar; committed flag gereksizdir.
- Tek operatör için gereken çözüm dosya kilidi değil, `BEGIN IMMEDIATE` kullanan tek commit kapısıdır.