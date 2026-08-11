# Sonuç — beklenti-fiyat uyumsuzluğu: yön doğru, ama şanstan ayırt edilemedi

**Ön kayıt:** [us-expectation-price-divergence-preregistration.md](us-expectation-price-divergence-preregistration.md)
(2026-08-07, hiçbir sapma hesaplanmadan yazıldı)
**Ölçüm tarihi:** 2026-08-07
**Örneklem:** 194 olay, 21 takvim çeyreği

## Bir cümlede

Hipotez **düştü** — ama beklediğim biçimde değil: işaret **doğru yönde** çıktı
ve üst-alt farkı ekonomik olarak anlamlıydı, fakat rank korelasyonu şans
bandının içinde kaldı.

## Ana test

| | |
|---|---|
| gözlem | 194 (21 takvim çeyreği) |
| Spearman (sapma ↔ sonraki 21 seans) | **−0,0525** |
| şans bandı (10.000 kümelenmiş permütasyon) | −0,1614 .. +0,0642 |
| konum | **band içinde** |
| alt üçte bir (fiyat en az tepki verenler) | −%0,75 |
| üst üçte bir (fiyat en çok tepki verenler) | −%2,35 |
| fark | **+%1,60** (maliyet sonrası +%1,40) |

**Ön kayıt kuralı 2 uygulandı: band içinde → hipotez düşer.**

## Ama üç şey kaydedilmeli

### 1. İşaret hipotezin istediği yönde

ρ negatif ve üst-alt farkı +%1,60. Yani fiyatı haberin gerektirdiğinden az
tepki veren şirketler, çok tepki verenlerden **daha iyi** getirmiş. Bu tam
olarak hipotezin öngördüğü şey.

Karar istatistiği ρ'dur ve o bandın içindedir. Ama "yön de yanlıştı" demek
doğru olmaz — yön doğruydu, büyüklük ayırt edilemedi.

### 2. ρ ile çeyrek farkı ayrışıyor

ρ = −0,053 (zayıf) ama üst-alt farkı %1,60 (büyük). ρ bütün sıralamayı, çeyrek
farkı yalnız uçları ölçer. Uçlarda bir şey olup ortada olmaması mümkündür —
ama 194 gözlemde uçlar 64'er isimdir ve bu ayrışma tek başına bir bulgu
değildir. Ön kayıt uç dilimleri ayrı test etmeyi **önceden reddetmişti**.

### 3. Bu sonuç, aşırı tepki testiyle ÇELİŞİYOR

| test | koşullandırma | n | ρ | konum |
|---|---|---|---|---|
| [aşırı tepki](us-overreaction-result.md) | EPS sürprizi | 498 | **+0,0825** | **dışında** |
| bu test | yönlendirme değişimi | 194 | **−0,0525** | içinde |

İşaretler **ters**. Biri bandın dışında ve devam diyor, diğeri bandın içinde ve
zayıfça yetişme diyor.

Bu temiz biçimde çözülmüyor ve çözülmüş gibi sunulmayacak. İki olası okuma var
ve ikisi de bu veriyle ayrılamaz:

- Koşullandırma değişkeni önemli: sürprize göre sapma ile yönlendirmeye göre
  sapma farklı şeyler ölçüyor olabilir.
- Ya da ikisi de gürültü ve ters işaretler bunun göstergesi.

**Her iki sonucu da tek başına almamak gerekir.**

## Güç — önceden yazılmıştı ve tuttu

Ön kayıt "ayırt edilebilir en küçük etki ρ ≈ 0,14" diyordu. Gözlenen band yarı
genişliği ~0,11-0,16, yani tahmin doğru çıktı.

**Bu negatif sonucun anlamı: etki varsa ρ ≈ 0,11'den küçüktür.** "Yok" değil,
"bu örneklemde görünmez".

## Kapsama

| eleme sebebi | |
|---|---|
| farklı/okunamayan mali yıl | **274** |
| çeyrek aralığı dışı | 80 |
| ileri pencere yok | 9 |
| seans değil / kapsam dışı | 1 |

En büyük kayıp yine **yıl çıkarımı** — 274 gözlem. Bu, üçüncü kez aynı yerde
kanıyor ve düzeltilirse örneklem iki katına çıkar, güç de belirgin artar.

## Nokta-zaman kontrolü (ön kayıt, zorunlu)

```
giris tarihi - yonlendirme tarihi
  min 2 gun, medyan 2 gun, maks 5 gun, negatif olan: 0
```

Temiz. Yönlendirme açıklama anında yayınlanıyor, giriş iki seans sonrasında.
Bu kontrol, aynı gün geri çekilen bir tablodan sonra zorunlu hâle getirilmişti
([us-mechanical-families-result.md](us-mechanical-families-result.md)).

## Bundan sonra

Hipotez bu örneklemde düştü ama **öldü sayılmaz**, ve sebebi net: örneklem 194,
görülebilir eşik 0,11. Elenemeyen aralık (ρ 0,05-0,11) küçük ama sıfır değil.

Örneklemi büyütmenin iki yolu var ve ikisi de elimizde:

1. **Yıl çıkarımını düzeltmek** — 274 gözlemin çoğu geri gelir, örneklem ~400'e
   çıkar, eşik ~0,10'a iner.
2. **S&P 500 fiyat defteri** — şu an yalnız 60 şirketin donmuş defteri var.
   500 şirket eklenirse örneklem birkaç kata çıkar.

Bunlar yapılırsa test **kendi ön kaydıyla** yeniden koşulur; bu belgedeki sonuç
o zaman "daha küçük örneklemde band içindeydi" olarak alıntılanır, gizlenmez.

## Sınırlar

- 60 şirket, 2020-2026, ABD büyük sermaye.
- Yönlendirme, analist konsensüsünün yerine kullanıldı. Doğru vekil revizyon
  paneliydi ve o veri satın alınmadan elde edilemiyor.
- "Beklenen tepki" sıralama bazlı hareketli ortalamayla kuruldu; farklı bir
  uydurma farklı bir sapma verirdi. Ham tepkinin de band içinde çıkması
  (ρ −0,011) bu endişeyi hafifletiyor, ortadan kaldırmıyor.
