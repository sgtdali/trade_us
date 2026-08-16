## 1. Bu on turun özeti

**Policy’nin sınanması:** Klasik strateji backtest’i; hindsight, survivorship ve tarihsel yargı eksikliği nedeniyle güvenilir kabul edilmedi. Bunun yerine dört bağımsız kanıt katmanı benimsendi: property testleri, golden senaryolar, mekanik tarihsel replay ve iki aşamalı gölge koşu. Bunlar kârlılığı kanıtlamaz; policy’nin tehlikeli olmadığını, motorun doğru uygulandığını ve sürecin işletilebilir olduğunu gösterir. Canlı yetki A0–A4 merdiveniyle, policy’den ayrı bir `operating_authority` nesnesi üzerinden kademeli verilir.

**Somut şema:** Kanonik olaylar, SQLite depolama, projection sözleşmeleri ve immutable artefaktlar birbirinden ayrıldı. Para/adet exact decimal string, kimlikler UUIDv7; zaman ve issuer/security/listing ayrımları açıkça tanımlandı. Açılış kitabı sentetik fill yerine `opening_account_state_asserted` ile alınacak; olay zarfı ve SQLite transaction’ları idempotent, atomik replay sağlayacak. İlk dilim yaklaşık 30 şema değil, açılış kitabı → pozisyon/nakit → NAV → replay zincirini kanıtlayan **7 tam şema + 3 stub + 1 DDL** ile sınırlandı.

## 2. Önceki turlarla çelişki

Temel bir mimari çelişki yok; fakat üç doğrudan daraltma dokümana işlenmeli:

| Konu | Yeni hüküm |
|---|---|
| Adım 0–1 | Capital policy bütün altyapıyı bloklamaz. Dört kullanıcı kararı policy’nin etkinleştirilmesini, risk motorunu ve proposal üretimini bloklar; core types, olay zarfı, SQLite DDL, opening-state şeması ve fixture çalışması beklemeden başlayabilir. `policy_validation_spec`, policy yazıldıktan sonra ve motor kodlanmadan önce hazırlanır. |
| `config/` ve `data/` | `config/capital-policy.json` yalnız düzenlenebilir taslaktır; runtime otoritesi, mühürlenmiş policy artefaktı ile `capital_policy_activated` olayıdır. Config dosyası etkinleştirmeden sonra ikinci gerçeklik kaynağı sayılamaz. |
| Onay semantiği | Olay zarfından genel `approval` alanının kaldırılması önceki kararla tamamen uyumludur. Makine doğrulaması, analitik kabul ve sermaye/icra yetkisi ayrı domain kayıtlarıdır; `authority_basis` bunların yerine geçen genel bir onay değildir. |

Ek daraltma: `sequence` domain olayından çıkarılıp depolama metadata’sına taşındı; geniş risk/proposal şemaları ise ilk çalışan dilimden sonraya bırakıldı.

## 3. Yarın ne yapılacak

1. Kullanıcı dört blokaj kararını cevaplar: fon perimetresi, baz para birimi, sermaye amacı ve risk zarfı.
2. Cevaplar beklenirken broker hesapları, açılış tarihi ve kaynak ekstre/export dosyaları envanterlenir; henüz import yapılmaz.
3. `core-types`, `event-envelope` ve SQLite DDL sözleşmeleri kesinleştirilir; atomiklik, idempotency ve replay kabul fixture’ları yazılır.
4. Açılış kitabı, pozisyon/nakit projection’ı ve NAV için 7 tam şema + 3 stub sınırı dondurulur.
5. Dört cevap geldikten sonra `fund_definition`, `capital_policy` ve `policy_validation_spec` tamamlanır; policy activation, risk motoru ve proposal çalışması o zamana kadar bekler.

## 4. Son söz

En kolay yanlış anlama, replay edilebilir ve deterministik bir sistemin otomatik olarak doğru olduğuna inanmaktır. Sistem aynı yanlış fiyatı, yanlış FX’i veya kötü seçilmiş policy sayısını kusursuz biçimde tekrar üretebilir. Bu yüzden ilk başarı ölçütü “iyi proposal verdi” değil; broker gerçeğini kayıpsız aldı, bilinmeyeni sıfıra çevirmedi, aynı girdiyi çoğaltmadı ve aynı manifestten aynı state’i üretti olmalıdır. Sermaye yetkisi ancak bundan sonra gelir.