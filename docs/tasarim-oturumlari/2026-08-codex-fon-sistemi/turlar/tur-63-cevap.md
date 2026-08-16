Kullanıcı haklı; biz işlem hacmini sormadan “gerçek para” ifadesinden kurumsal operasyon ihtiyaçları türettik. **Elle giriş varsayımıyla küçük bir yazılım artık daha mantıklı hâle geliyor—ama bu yazılım broker kopyası değil, manuel girdili karar günlüğü ve policy hesaplayıcısı olmalı.**

## 1. Ne çöküyor?

### Tamamen çıkarılmalı

- Broker CSV/OFX importer
- Otomatik statement kapanışı
- Çok eksenli reconciliation motoru
- Import batch’i ve batch idempotency’si
- Broker-order observation modeli
- Partial-fill/order lifecycle ve VWAP toplulaştırma
- Otomatik lot eşleştirme ve lot-selection olayları
- Temettü tahakkuku–ödeme ayrımına dayalı resmî NAV
- Açıklanamayan nakit farkı tolerans motoru
- Çok hesap/broker/custodian desteği
- Genel amaçlı kurumsal işlem işlemcisi
- `global_position`, `stream_position`, batch/correlation gibi genel event-store yüzeyleri

### Küçülerek kalmalı

- **Duplicate koruması:** Import idempotency değil, yanlışlıkla iki kez form gönderme veya aynı işlemi yeniden girme uyarısı.
- **Reconciliation:** Motor değil; ayda bir broker ekranıyla “adet ve nakit eşleşiyor/eşleşmiyor” kontrolü.
- **Pozisyon belirsizliği:** `position_unknown` durum makinesi değil; `last_verified_at` ve basit `match/mismatch`.
- **Cost basis:** Broker maliyeti biliniyorsa girilir; bilinmiyorsa sahte sıfır yazılmaz, yalnız `known/unknown`.
- **Partial fill:** Emir tamamlandığında toplam gerçekleşen adet ve ortalama fiyat tek satır girilir. Günlere yayılırsa gerekirse gün başına bir satır.
- **Temettü/ücret:** Ödeme tarihinde manuel nakit hareketi. Brüt ve stopaj isteğe bağlı alanlar olabilir.
- **Split/spin-off:** Otomasyon değil, manuel `quantity_adjustment` ve açıklama.
- **Uzlaşma:** Elle giriş ihtiyacı ortadan kaldırmaz; yalnız “veri entegrasyonu sistemi” olmaktan çıkarıp ayda beş dakikalık sağlık kontrolüne dönüştürür.

## 2. “Yazılım yazma” hükmü değişiyor mu?

**Evet, değişiyor.**

Önceki hüküm, özel muhasebe defterinin importer, reconciliation ve broker uyuşmazlığı maliyetine dayanıyordu. Ayda bir işlem ve manuel giriş varsayımında bu maliyetin büyük kısmı ortadan kalkıyor.

Üstelik mevcut repo zaten şunları sağlıyor:

- Piyasa verisi ve point-in-time altyapısı
- Şema doğrulama
- Araştırma artefaktları
- Olay ve orkestrasyon tecrübesi
- Güncel fiyatlarla hesaplama imkânı

Dolayısıyla doğru tavsiye artık şudur:

> **Küçük, manuel girdili bir portföy karar uygulaması yaz; broker muhasebesi, importer ve genel platform yazma.**

Bu uygulamanın hesap tablosuna göre gerçek avantajı formüller değil; karar anındaki girdiyi, policy sürümünü ve hesaplanan sonucu immutable biçimde birlikte saklamasıdır. “O gün ne biliyordum?” sorusu yazılımı haklı çıkaran esas ihtiyaçtır.

## 3. Elle girişli minimum sistem

### Kalıcı veri: üç küçük sözleşme

#### 1. `account_event`

Tek tablo:

- `event_id`
- `event_type`: `opening_position`, `opening_cash`, `buy`, `sell`, `deposit`, `withdrawal`, `dividend`, `fee`, `quantity_adjustment`, `correction`
- `effective_date`
- `security_id` — gerekiyorsa
- `quantity` — gerekiyorsa
- `price` — gerekiyorsa
- `cash_amount`
- `currency`
- `decision_id` — işlem bir karara bağlıysa
- `recorded_at`
- `note`
- `corrects_event_id` — gerekiyorsa

Onaylanmış satır değiştirilmez; hata yeni correction kaydıyla düzeltilir.

#### 2. `decision_record`

Her sermaye kararında:

- `decision_id`
- `as_of`
- `policy_version`
- Security ve düşünülen işlem
- İşlem öncesi pozisyon/nakit/NAV snapshot’ı
- Readiness
- Downside yüzdesi
- Mevcut ve işlem sonrası ağırlık
- Kaybın NAV baz puan etkisi
- Policy’nin izin verdiği azami ağırlık
- No-trade bandı sonucu
- Hard-breach sonuçları
- Kullanıcının kararı
- Gerekçe
- Sonraki inceleme tarihi

Bu kayıt “o gün ne biliyordum?” sorusunun cevabıdır.

#### 3. `capital_policy`

Yalnız kullanılan kurallar:

- Azami pozisyon sayısı
- Starter/core multiplier
- Pozisyon başına kayıp bütçesi
- Azami pozisyon ağırlığı
- Nakit tabanı
- Mutlak ve göreli no-trade bandı
- Drawdown inceleme eşikleri
- Policy sürümü ve yürürlük tarihi

### Sistem ne hesaplar?

- Pozisyon adetleri ve nakit
- Güncel NAV ve ağırlıklar
- Ortalama maliyet ve basit P&L
- İşlem sonrası simülasyon
- Downside senaryosunun NAV etkisi
- Kaybı bütçesine göre azami ağırlık
- Readiness’e göre uygun ağırlık bandı
- Nakit tabanı ve pozisyon limiti
- No-trade bandının geçilip geçilmediği
- Hard-breach ve gecikmiş inceleme uyarıları

Sistem “optimal portföy” üretmez. Kullanıcının düşündüğü işlemin policy içinde olup olmadığını ve portföyü nasıl değiştireceğini gösterir.

### İşletim yükü

- İşlem yoksa haftalık: **5 dakika**
- Her işlem: giriş + simülasyon + karar kaydı **5–10 dakika**
- Aylık broker kontrolü: **5–10 dakika**
- Toplam ortalama operasyon yükü: araştırma hariç yaklaşık **10–15 dakika/hafta**

### Şema kesimi

Önceki `7 tam + 3 stub + 1 DDL` yerine:

- `account-event.v0`
- `decision-record.v0`
- `capital-policy.v0`
- Tek SQLite DDL

Position, cash, NAV ve policy-check çıktıları başlangıçta kod içi projection olur; ayrı public şemaları gerekmez. Dosya sayısı yaklaşık üçte bire, anlamsal yüzey daha da fazla küçülür.

## 4. Neden bu kadar takıldık?

Benim payım açık: “gerçek para”yı “kurumsal muhasebe doğruluğu” ile eşitledim; **frekans × zarar × fark edilme olasılığı** hesabını yapmadım. Kullanıcının yılda yalnız 12 işlem yapacağını sormadan nadir durumları birinci sınıf mimari nesnelere çevirdim.

Aynı sapma muhtemelen şu yerlerde de oldu:

- 87 isimden S&P 500 ölçeğine erken sıçramamız
- Tek operatörde eşzamanlı writer ve genel batch mimarisi
- Beş-on pozisyona A0–A4 yetki merdiveni
- Gerçek kullanım görmeden 10+1 skill kataloğu
- Küçük örneklemde ayrıntılı attribution ve counterfactual motoru
- Ayda bir işlemde tam execution lifecycle
- Tek kullanıcı için genel approval ve role sistemi
- Yalnız birkaç vaka varken route-kalite istatistikleri
- Nitel risk etiketlerinden kapsamlı driver registry çıkarmamız
- Her “ya şöyle olursa?” sorusuna manuel istisna yerine kalıcı durum/olay tipi vermemiz

Temel süreç hatamız şuydu:

> **Önce olayın ne sıklıkta yaşandığını ve insanın onu elle çözmesinin maliyetini sormak yerine, teorik olarak doğru çözümü tasarladık.**

Bundan sonraki filtre basit olmalı: Bir mekanizma ancak hata sık görülüyorsa, sessiz ve maddi zarar verebiliyorsa veya elle çözümü tekrar eden yük yaratıyorsa yazılıma girer. Yılda bir kez yaşanacak ve beş dakikada düzeltilecek durum, çoğunlukla bir olay türü değil kullanıcı notudur.

Son hüküm: **Yazılım mantıklı; tasarladığımız “portföy işletim platformu” değil. Mantıklı ürün, manuel işlemleri alan, policy’yi hesaplayan ve karar anını donduran küçük bir portföy karar günlüğüdür.**