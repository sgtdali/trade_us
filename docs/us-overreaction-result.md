# Sonuç — piyasa aşırı tepki verip fırsat bırakmıyor, tersine devam ediyor

**Ön kayıt:** [us-overreaction-preregistration.md](us-overreaction-preregistration.md)
(2026-08-07, hiçbir kalıntı hesaplanmadan yazıldı)
**Ölçüm tarihi:** 2026-08-07
**Örneklem:** 498 açıklama, 21 şirket, 25 takvim çeyreği, 2020-2026

## Bir cümlede

Hipotez **düştü ve ters yönde düştü**: sürprizin haklı çıkardığından fazla düşen
hisse toparlanmıyor, düşmeye devam ediyor.

## Ana test

| | |
|---|---|
| gözlem | 498 (25 takvim çeyreği) |
| Spearman (aşırı tepki ↔ sonraki ay) | **+0,0825** |
| şans bandı (10.000 kümelenmiş permütasyon) | −0,0919 .. +0,0508 |
| konum | **band dışında, POZİTİF tarafta** |
| alt üçte bir (en çok düşenler) | **−%0,73** |
| üst üçte bir (en çok çıkanlar) | +%0,07 |

Hipotez **negatif** işaret gerektiriyordu. Pozitif çıktı: aşırı hareket, sonraki
ay aynı yönde devam ediyor.

**Ön kayıt kuralı 3 uygulandı:** *band dışında ama pozitif → hipotez düşer,
işaret çevrilip momentum hikâyesi kurulmaz.* Bu sonuç bir strateji üretmez;
kendi ön kaydı ve örneklem-dışı doğrulaması olmadan "kazananı al" cümlesi
kurulamaz.

## Aşırı tepki, ham tepkiden fazla bir şey söylemiyor

| | ρ | konum | alt-üst |
|---|---|---|---|
| aşırı tepki (kalıntı) | +0,0825 | dışında | −%0,80 |
| ham tepki getirisi | +0,0625 | dışında | −%0,61 |

Sürprize göre düzeltmek tabloyu değiştirmedi. Yani "haklı düşüş" ile "aşırı
düşüş" ayrımı, sonraki ay getirisi açısından bir şey ifade etmiyor.

## İkincil sonuçlar — karar vermezler, ve neden vermediklerini yazıyorum

| alt küme | n | ρ | konum | alt-üst |
|---|---|---|---|---|
| yalnız en çok **düşenler** | 166 | −0,0560 | **içinde** | **+%1,73** |
| yalnız en çok **çıkanlar** | 166 | +0,0802 | içinde | −%0,75 |

En çok düşenlerin içinde, hipotezin beklediği yönde bir iz var: en aşırı düşenler
+%0,54, daha az düşenler −%1,19, fark **+%1,73**.

**Bunun üstüne inşa edilmiyor**, üç sebeple:

1. **Bandın içinde.** ρ −0,056, band −0,093 .. +0,152. Şanstan ayırt
   edilemiyor.
2. **Ön kayıtta karar tetiklemeyeceği yazılıydı.** İki ucu ayrı test edip
   geçeni ana sonuç yerine koymak, bu protokolün engellemek için var olduğu
   şeydir ([olcum-metodolojisi.md](olcum-metodolojisi.md) 1c).
3. **Ayrılamayan bir karışıklık var ve önceden yazılmıştı.** Alt üçte bir,
   kurumsal olayların ve gerçek kötü haberin yoğunlaştığı yerdir. Oradaki
   toparlanmanın aşırı tepki mi yoksa hayatta kalma etkisi mi olduğu bu testle
   ayrılmaz.

Bu iz, kendi ön kaydıyla ve daha büyük bir örneklemle ayrıca test edilebilir.
Bugünkü sonucun parçası değildir.

## Bunun bağlamı

[us-earnings-surprise-result.md](us-earnings-surprise-result.md) ham sürprizi
sonraki aya karşı test etmiş ve düşmüştü (ρ −0,0911, sağlamlıkta bir ölçekte
band içine giriyordu). Orada bir ipucu vardı: en çok ıskalayanlar +%0,18, en çok
aşanlar −%0,68.

Bu test o ipucunu koşullandırarak aradı ve **bulmadı** — dahası ters işaret
verdi. İki ölçüm birlikte okununca: **açıklama sonrası girmek para
kazandırmıyor**, ne takip ederek ne de tersine oynayarak.

Değer, açıklama gününün kendisinde ve orada da yönlendirme değişiminde
([us-guidance-signal-result.md](us-guidance-signal-result.md)).

## Sınırlar

- 21 şirket, Alpha Vantage sürpriz kapsamı bu kadar. 60 şirketlik yönlendirme
  koşullu ikincil test bu belgede yapılmadı.
- 2020-2026, ABD büyük sermaye.
- "Beklenen tepki" sıralama bazlı hareketli ortalamayla kuruldu; parametre
  seçimi yapılmadı (pencere `max(15, n/12)` olarak sabitlendi) ama farklı bir
  uydurma farklı bir kalıntı verirdi. Ham tepkiyle sonucun aynı çıkması bu
  endişeyi hafifletiyor, ortadan kaldırmıyor.
