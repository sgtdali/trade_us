# Ön kayıt — piyasa açıklamaya aşırı tepki verip fırsat bırakıyor mu

**Yazılma tarihi:** 2026-08-07
**Durum:** Hiçbir kalıntı hesaplanmadan, hiçbir ileri getiri eşleştirilmeden
yazıldı.

## Hipotez

Piyasa, kazanç açıklamasına **sürprizin haklı çıkardığından fazla** tepki
verdiğinde, izleyen ay bunun bir kısmı geri gelir. Aşırı düşen toparlanır,
aşırı çıkan geri verir.

Test edilen değişken **sürprizin kendisi değil**, tepkinin sürprize göre
**fazlası**: küçük bir ıskalamaya sert düşen hisse aşırı tepkidir, büyük bir
ıskalamaya sert düşen hisse haklıdır.

## Bunun daha önce ölçülenden farkı

[us-earnings-surprise-result.md](us-earnings-surprise-result.md) **ham sürprizi**
sonraki ay getirisine karşı test etti: ρ −0,0911, üst-alt −%0,86, ve sağlamlık
kontrolünde bir ölçekte bandın içine düştü. O test hipotez olarak düştü.

Orada bir ipucu vardı ama ölçülmedi: en çok ıskalayan üçte bir sonraki ay
**+%0,18**, en çok aşan üçte bir **−%0,68** getirmişti. Bu belge, o ipucunu
**koşullandırarak** test eder — ham sıralamayla değil, tepkinin kalıntısıyla.

Ayrıca mekanik taramada `reversal_1m` (takvim ayı dönüşü) ρ −0,046 ile
anlamsızdı; bu ondan farklıdır çünkü **olaya koşullu**dur.

## Değişkenler

- **tepki getirisi**: sürpriz testindeki tanımın aynısı (`reportTime`'a göre
  hizalanmış tek seans, evrenin eşit ağırlıklı ortalaması çıkarılmış).
- **beklenen tepki**: tepki getirisinin sürprize göre uydurulmuş değeri
  (sıralama bazlı, tek değişkenli).
- **AŞIRI TEPKİ = tepki − beklenen tepki.** Yapı gereği sürprizle
  ilişkisizdir; ölçtüğü şey "haklılığın ötesindeki hareket"tir.
- **ileri getiri**: tepki seansının **ertesi** seansından +21 seans, piyasa
  düzeltilmiş. Tepkinin kendisi asla dahil edilmez.

## Test edilecekler

| # | değişken | karar |
|---|---|---|
| **1** | **aşırı tepki → ileri getiri** (tüm örneklem) | **ANA TEST** |
| 2 | yalnız alt üçte bir (en çok düşenler) | karar vermez |
| 3 | yalnız üst üçte bir (en çok çıkanlar) | karar vermez |
| 4 | ham tepki getirisi → ileri getiri | karşılaştırma tabanı |

Hipotez doğruysa **1'in işareti NEGATİF** olmalıdır: aşırı çıkan geri verir,
aşırı düşen toparlanır.

2 ve 3 karar vermez ve bu önceden sabittir — asimetri hipotezin bir parçası ama
uçları ayrı ayrı test edip geçeni seçmek, tam da kaçındığımız şeydir. Sonuçları
bağlam olarak raporlanır.

4, aşırı tepkinin ham tepkiden farklı bir şey ölçtüğünü göstermek içindir.

## Örneklem

**Birincil:** sürpriz verisi olan 498 açıklama (21 şirket, 2020-2026). Alpha
Vantage kapsamı bu kadar.

**İkincil, karar vermez:** yönlendirme değişimine koşullu aynı test (209 olay,
58 şirket). Yönlendirme değişimi açıklama gününü sürprizden daha iyi açıklıyor
(+%6,45'e karşı +%2,59), dolayısıyla kalıntısı daha temiz olabilir — ama örneklem
küçük ve bu belge onu karar mercii saymaz.

## İstatistik

Havuzlanmış Spearman, açıklama takvim çeyreğine göre **kümelenmiş** permütasyon,
10.000 tekrar. Sürpriz testiyle birebir aynı çerçeve.

Ekonomik büyüklük: alt üçte bir − üst üçte bir, olay başına ortalama piyasa
düzeltilmiş getiri. **Çift yönlü işlem maliyeti %0,20** ve bu eşiğin altındaki
her sonuç, bandın neresinde olursa olsun pratik olarak ölüdür.

## Karar kuralı

1. **Ana test bandın dışında ve NEGATİF** → aşırı tepki geri dönüyor. Fark
   %0,20'yi aşıyorsa sonraki adım: uçlarda yoğunlaştırılmış bir portföy kuralı,
   kendi ön kaydıyla.
2. **Band içinde** → aşırı tepki sonraki ay getirisini sıralamıyor. Hipotez
   düşer.
3. **Band dışında ama POZİTİF** → hipotez düşer. **İşaret çevrilip momentum
   hikâyesi kurulmaz** (bkz. [olcum-metodolojisi.md](olcum-metodolojisi.md) 1a).
4. **Band dışında, negatif, ama fark < %0,20** → istatistiksel olarak var,
   pratik olarak ölü. Portföy kuralına geçilmez.

## Önceden reddedilenler

- Ufuk taraması yok: yalnız 21 seans. (Sürpriz testi 63 seansta zaten bir şey
  bulmamıştı.)
- Eşik/kesme noktası aranmaz; ham sıralama.
- Sektör, büyüklük, dönem kırılımı yok.
- Uçlardan geçeni seçip ana test yerine koymak yok (2 ve 3 karar vermez).
- Negatif sonuç, "aşırı tepki tanımı farklı olmalıydı" denerek yeniden
  koşulmaz.

## Bu testin bilinen zayıflığı, şimdiden

Alt üçte bir "en çok düşenler" olduğu için, orada **kurumsal olay, muhasebe
sorunu ya da yapısal kötü haber** yoğunlaşabilir. Toparlanma görülürse bunun
gerçekten aşırı tepki mi yoksa hayatta kalma etkisi mi olduğu bu testle
ayrılmaz. Pozitif sonuç çıkarsa bu ayrım **yapılmamış** olarak raporlanır.
