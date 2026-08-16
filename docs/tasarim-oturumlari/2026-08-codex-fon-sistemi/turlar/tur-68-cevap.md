## 1. Üç gerçek hafta

### A. Sessiz hafta

Gece döngüleri şunları yaptı:

- SEC accession’larını kontrol etti.
- Yeni fiyat snapshot’larını aldı.
- Review tarihlerini taradı.
- Aynı olayların yeniden işlenmediğini doğruladı.
- Yeni filing, fiyat şoku veya vadesi gelmiş inceleme bulmadı.
- Hiçbir skill çalıştırmadı.

Pazartesi kullanıcı `fund inbox` açtığında şunu görür:

```text
ARAŞTIRMA DÖNGÜSÜ

Son başarılı çalışma   18 Ağustos 03:04
Aktif tez              8
Yeni kanıt             0
Adjudication bekleyen  0
Başarısız iş           0
Gecikmiş inceleme      0

Yaklaşan:
- MSFT review_due      12 gün
- NVDA earnings        tahmini, henüz doğrulanmadı

İşlem gerekmiyor.
```

Kullanıcı iki-üç dakika bakar ve kapatır. Haftalık `no_change` kaydı üretilmez; bu aylık `fund review` oturumunun işidir.

**İnsan yükü: 2–5 dakika.**

---

### B. Bir tezin filing’i geldi

Salı gecesi sistem NVDA için yeni 10-Q accession’ı gördü:

1. Filing’i indirdi.
2. XBRL/normalize hattını çalıştırdı.
3. Aktif monitoring contract’taki iki mekanik kuralı değerlendirdi.
4. Brüt marj kuralında breach buldu.
5. İki nitel soruyu pack’e ekledi.
6. Sabit recipe’yi çalıştırdı:

```text
earnings-deep-dive → thesis-tracker
```

7. Çıktıyı doğruladı ve adjudication kuyruğuna koydu.
8. Tezi otomatik `broken` yapmadı; yalnız `review_required` işaretledi.

Kullanıcının gördüğü:

```text
[ADJUDICATION GEREKİYOR]

NVDA — 2026 Q2 filing review

Mekanik sonuç:
- Gross margin: %74,2 → %71,9
- Kural: önceki yılın 200 bp altı
- Sonuç: BREACHED

Nitel inceleme:
- Hyperscaler capex siparişe dönüşüyor mu?
  Skill: kanıt karışık
- Pricing power zayıflıyor mu?
  Skill: erken olumsuz sinyal

Tracker önerisi:
- Thesis: active → review_required
- Readiness: core → starter
- Downside: -%24 → -%31

[Kaynakları aç]
[Accept]
[Reject]
[Human-authored replacement]
[Defer]
```

Bu ekranda ağırlık, maliyet, P&L ve olası satış görünmez. Kullanıcı araştırma hükmünü 10–25 dakika inceler. Kabul ettikten sonra isterse ayrı `trade-preview` ekranında sermaye etkisini görür.

**İnsan yükü:**

- Dar ve açık güncelleme: 5–10 dakika
- Maddi hüküm değişikliği: 20–30 dakika

---

### C. Yoğun hafta

Aynı hafta:

- NVDA’da fiyat şoku oluştu.
- MSFT’nin review tarihi doldu.
- Discovery koşusu yeni bir aday çıkardı.

Sistem şunları yaptı:

1. NVDA için `independent_then_reconcile` review çalıştırdı. İlk geçişte fiyat, pozisyon ve P&L’i modele göstermedi.
2. MSFT için tracker’ı mevcut assessment’a karşı çalıştırdı.
3. Yeni aday için belirlenmiş onboarding recipe’sini çalıştırdı.
4. İşleri seri yürüttü; aynı teze ilişkin yinelenen işleri birleştirdi.
5. Sonuçları tek kuyruğa koydu.

Pazartesi görünümü:

```text
BUGÜN / BU HAFTA

1. NVDA — maddi fiyat/tez ayrışması
   Tür: adjudication
   Durum: review_required
   Son tarih: bugün
   Tahmini inceleme: 20–30 dk

2. MSFT — dönemsel thesis review
   Tür: adjudication
   Maddi breach: yok
   Son tarih: 3 gün
   Tahmini inceleme: 5–10 dk

3. ADBE — yeni aday assessment
   Tür: candidate review
   Fonlanmış değil
   Son tarih: 7 gün
   Tahmini inceleme: 15–25 dk

BİLGİ
- 5 tezde yeni olay yok.
- 1 geçici SEC hatası otomatik retry ile düzeldi.
```

Kullanıcı önce NVDA’yı, sonra MSFT’yi ele alır. Aday vakasını vakit yoksa erteler; mevcut sermaye yeni adaydan önce gelir.

**İnsan yükü: 40–65 dakika.** Gerçekten karmaşık sonuçlarda 75–90 dakikaya çıkabilir; bu olağan hafta değil, yoğun hafta tavanıdır.

## 2. Süre bütçesi

Eski “haftada 10–15 dakika” bütün sistem için fazla iyimserdi. Bu rakam yalnız sessiz operasyon haftası için geçerlidir.

16–32 otomatik review recipe’sinin yıllık adjudication bedeli yaklaşık:

- %75 dar güncelleme × 5–10 dakika
- %25 maddi güncelleme × 20–30 dakika

Toplam: yaklaşık **3–7 saat/yıl**.

Buna ek olarak:

- Aylık portföy review: 2–3 saat/yıl
- Yılda 12 işlem/karar kaydı: 2–3 saat/yıl
- Inbox ve sessiz hafta kontrolleri: 2–4 saat/yıl
- Yeni aday değerlendirmeleri: yoğunluğa göre 3–6 saat/yıl

Dürüst toplam:

- **Mevcut kitabın işletimi:** ortalama 15–25 dakika/hafta
- **Düzenli yeni aday araştırması dahil:** ortalama 25–40 dakika/hafta
- **Sessiz hafta:** 2–5 dakika
- **Filing haftası:** 10–30 dakika
- **Nadir yoğun hafta:** 45–90 dakika

Otomasyon insan yükünü iki yönde etkiler: hatırlama, veri toplama ve skill çalıştırma yükünü kaldırır; fakat daha önce atlanabilecek incelemeleri görünür hâle getirir. İkincisi “otomasyonun yarattığı iş” değil, doğru işletimin gerçek maliyetidir.

## 3. Küçük kuyruk

P0–P4 gereksizdir. Üç sınıf yeterlidir:

### Q0 — Engelleyici

- Veri gerçeği güvenilmez
- Döngü art arda başarısız
- Açık sermaye kararı gerekli assessment olmadan bekliyor
- Kritik monitoring verisi üretilemiyor

Yeni risk artırımı çözülene kadar bloklanabilir.

### Q1 — Adjudication gerekli

- Filing/earnings sonucu
- Mekanik breach
- Review_due
- Yeni assessment
- Tez durum değişikliği önerisi

Sıralama:

1. Son tarihi geçmiş olan
2. Fonlanmış tez
3. Mekanik breach veya maddi olay
4. Rutin review
5. Fonlanmamış aday
6. Oluşturulma zamanı

### Q2 — Bilgi

- Sapmasız kontrol
- Yaklaşan review
- Tahmini earnings tarihi
- Retry ile düzelmiş hata
- Yeni kanıt bulunmadı özeti

İnsan eylemi gerektirmez.

### `fund inbox` ve `fund review`

Aynı şey değildir:

- `fund inbox`: Olay-güdümlü günlük/haftalık iş kutusu
- `fund review`: Aylık portföy kararı oturumu

`fund review`, açık Q0/Q1 maddelerini üstte gösterir. Maddi adjudication çözülmemişse kullanıcı yine `no_change` diyebilir; ancak sistem bunu “temiz review” değil, `no_change_with_pending_review` olarak kaydeder.

## 4. Gece bir şey ters giderse

Bir kez retry tek başına yeterli değildir. Küçük ama sınıflandırılmış toparlanma gerekir.

### Veri kaynağı hatası

- Aynı cycle içinde bir kez retry
- Başarısızsa veri “değişmedi” sayılmaz; `unavailable` olur
- Skill çalıştırılmaz
- Sonraki gece otomatik yeniden denenir
- İki ardışık cycle başarısızsa Q0/Q1 uyarısı oluşur

### Codex/skill transport hatası

- Aynı dondurulmuş input ile bir kez retry
- Sonraki cycle’da bir kez daha denenebilir
- Duplicate work item açılmaz
- Üç başarısız cycle’dan sonra otomatik deneme durur

### Şema/kontrat hatası

- Bir otomatik repair denemesi
- Hâlâ geçersizse sonuç adjudication’a sunulmaz
- `contract_failed` olarak kullanıcıya gösterilir

### Bilgisayar kapalıysa

Task Scheduler `StartWhenAvailable` ile sonraki açılışta cycle’ı çalıştırır. Sistem son görülen accession ve review watermark’ından devam ettiği için aradaki filing kaybolmaz.

### Geç veya bayat sonuç

Sonuç geldiğinde daha yeni evidence veya assessment varsa otomatik kabul kuyruğuna girmez; `superseded_result` olarak bilgi bölümüne taşınır.

Sabah durum özeti açık olmalıdır:

```text
Son cycle        BAŞARISIZ — 03:17
SEC refresh      başarılı
Price refresh    başarısız, 2. ardışık deneme
Skill jobs       1 başarılı / 1 başarısız
Thesis state     hiçbir otomatik değişiklik yapılmadı

Eylem:
[Retry now] [Hata ayrıntısı] [Bu işi ertele]
```

Temel güvenlik kuralı:

> **Otomasyon başarısız olduğunda sistem sessiz kalmaz, eski veriyi yeniymiş gibi kullanmaz ve tez durumunu ilerletmez. Aynı işi sonsuza kadar da tekrarlamaz.**

Bu işletim döngüsünde kullanıcının işi süreç yönetmek değil, yalnız gerçek araştırma hükümlerini değerlendirmektir.