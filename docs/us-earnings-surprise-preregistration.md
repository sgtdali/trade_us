# Ön kayıt — kazanç sürprizi bu evrende para kazandırdı mı

**Yazılma tarihi:** 2026-08-06
**Durum:** Hiçbir korelasyon hesaplanmadan yazıldı. Alpha Vantage `EARNINGS`
verisi çekilmiş ve yalnız şekli incelenmişti (çeyrek sayısı, alan adları, bir
örnek kayıt); hiçbir getiri eşleştirilmemişti.

## Soru

Kullanıcının sorusu: *"bu konsensuslar bu 60 firma için kâr ettirmiş mi?"*

Bu soru, üzerinde çalıştığımız yeniden tasarımın **öncülünü** test ediyor.
Tasarım, LLM'e "gelecek çeyrek konsensüsü aşacak mı" diye sormayı öneriyor.
Eğer sürprizler bu evrende fiyatı hareket ettirmiyorsa, sürprizi mükemmel
tahmin etmek bile para kazandırmaz ve tasarım daha başlamadan ölür.

## Veri

Alpha Vantage `EARNINGS`: çeyrek başına `reportedDate`, `estimatedEPS`
(açıklama öncesi konsensüs), `reportedEPS`, `surprisePercentage`, `reportTime`.

**Örneklem şu an 60 değil 21 şirket.** Ücretsiz kademe günde 25 istek veriyor;
alfabetik olarak ilk 21 çekilebildi (AAPL … CSCO). Alfabetik sıra getiriyle
ilişkisiz ama **sektörle ilişkisiz değil** — bu alt küme sağlık ve temel
tüketimde yoğun. Kural şimdi sabitleniyor; kota açıldıkça 60'ın tamamında
**aynı kuralla** yeniden koşulacak ve iki sonuç da raporlanacak.

Fiyat: `ic-2021-v1` ve `ic-2024-v1` donmuş defterleri, birleşik kapsam
2020-05-08 → 2026-08-05. Yalnız bu aralığa düşen açıklamalar kullanılır.

## Tanımlar (önceden sabit)

- **Tepki penceresi.** `reportTime == "post-market"` ise açıklamayı izleyen ilk
  seans; `"pre-market"` ise açıklama seansının kendisi. Yanlış hizalama tepkiyi
  tamamen kaçırır, bu yüzden ayrı ele alınır.
- **Giriş.** Tepki seansının **ertesi** seansının açılışı. Tepkinin kendisi
  hiçbir zaman getiriye dahil edilmez — o bilgi alım anında zaten geçmiştir.
- **Piyasa düzeltmesi.** Aynı pencerede evrenin eşit ağırlıklı ortalama
  getirisi çıkarılır. Düzeltilmemiş getiri 2020-2026'da sektör değil rejim
  ölçer.
- **Sinyal.** `surprisePercentage`, olduğu gibi, dönüştürülmeden.

## Test edilecekler

| # | soru | pencere | karar |
|---|---|---|---|
| **1** | **sürpriz sonrası sürüklenme** | giriş → +21 seans | **ANA TEST** |
| 2 | sürprizler fiyatı oynatıyor mu | tepki penceresi | öncül, karar vermez |
| 3 | daha uzun sürüklenme | giriş → +63 seans | karar vermez |

**Yalnız 1 karar tetikler.** 2 ve 3 bağlam içindir ve raporlanır.

2'nin karar vermemesinin sebebi: tepki ticareti yapılamaz, açıklamayı önceden
göremezsiniz. Ama 2 sıfırsa 1'in pozitif çıkması şüphelidir ve öyle okunur.

## İstatistik

Havuzlanmış Spearman (sürpriz yüzdesi ↔ piyasa-düzeltilmiş getiri), tüm
olaylar üzerinde. Anlamlılık, **açıklama tarihine göre kümelenmiş** permütasyon
ile: aynı takvim çeyreğindeki olaylar birlikte karıştırılır, çünkü aynı çeyrekte
açıklama yapan şirketlerin getirileri bağımsız değildir. 10.000 tekrar.

Ayrıca ekonomik büyüklük: üst üçte bir − alt üçte bir, olay başına ortalama
piyasa-düzeltilmiş getiri, yüzde olarak. Bu rakam **işlem maliyeti öncesidir**
ve öyle raporlanır; çift yönlü maliyet %0,20 varsayılır (`TRANSACTION_COST_RATE`
ile aynı).

## Karar kuralı

1. **Ana test bandın dışında ve pozitif** → sürpriz sürüklenmesi bu evrende
   var. Sonraki adım: tahmin zincirinin 2. aşaması anlamlı hale gelir.
2. **Ana test band içinde** → sürüklenme yok. **Sürpriz tahmini tasarımı bu
   haliyle düşer**, çünkü doğru tahmin bile paraya çevrilemez. Yeni bir
   tasarım gerekir; bu tasarım kurtarılmaya çalışılmaz.
3. **Üst-alt üçte bir farkı %0,20'nin altında** → istatistiksel olarak anlamlı
   olsa bile pratik olarak ölüdür ve 2. madde gibi işlem görür.

## Önceden reddedilenler

- Ufuk taraması yok: yalnız 21 ve 63 seans, 63 karar vermez.
- Sürpriz eşiği aranmaz (">%5 sürpriz" gibi); ham sıralama kullanılır.
- Sektör/büyüklük kırılımı yok.
- Sonuç negatifse "21 şirket azdı" gerekçesi **kısmen** geçerlidir ve tam
  evren koşusu zaten planlıdır; ama 60'lık koşu da negatifse tasarım düşer.
- `reportTime` alanı eksik olan olaylar dışarıda bırakılır, tahmin edilmez.
