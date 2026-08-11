# Sonuç — ayrım yapılamıyor, ve sebebi kodda değil cebirde

**Ön kayıt:** [us-implied-expectations-preregistration.md](us-implied-expectations-preregistration.md)
(2026-08-07, hiçbir ima edilen değer hesaplanmadan yazıldı)
**Ölçüm tarihi:** 2026-08-07
**Örneklem:** 435-555 olay, 60 şirket

## Bir cümlede

Hiçbir değişken aile eşiğini geçmedi (yasanın dördüncü doğrulaması) — ama asıl
sonuç şu: **"piyasa inanmıyor mu, yoksa çarpanı mı düşürüyor" ayrımı fiyat ve
tahminden yapılamaz.** Bu bir ölçüm eksikliği değil, bir tanımlanabilirlik
sorunu.

## Tablo — 63 seans

| değişken | n | ρ | t | üst-alt |
|---|---|---|---|---|
| I1 kendi tarihine göre ucuzluk | 435 | −0,0560 | −1,67 | −%0,83 |
| I2 inanmama açığı | 435 | −0,0560 | −1,67 | −%0,83 |
| I3 çarpan cezası (evren medyanına göre) | 555 | −0,0762 | −1,95 | −%2,24 |
| I4 kendi bandındaki dilim | 435 | −0,0426 | −1,49 | −%0,26 |

**Aile eşiği |t| > 2,31. Hiçbiri geçmedi.** Karar kuralı 4.

## I1 ve I2 aynı sayı — benim tasarım hatam

Tabloda ρ, t ve üst-alt farkı **birebir aynı**. Tesadüf değil, cebir:

```
m = fiyat / yonlendirme              (guncel carpan)
M = sirketin kendi tarihsel medyani
i = fiyat / M                        (ima edilen kâr)

I1 = (M - m) / M              = 1 - m/M
I2 = (yonlendirme - i) / yonlendirme = 1 - m/M
```

Sayısal kontrol de doğruladı: M=11,5, yönlendirme=14, fiyat=120 için ikisi de
+0,254658.

**Ön kayıtta bunları iki ayrı değişken sandım. Aynı değişkenmiş.**

## Ve asıl sonuç: ayrım tanımlanabilir değil

Hata koddan değil, sorunun yapısından geliyor.

```
fiyat = carpan × kâr beklentisi
```

Elinde **bir denklem ve iki bilinmeyen** var. Fiyat düşükse bunun sebebi düşük
kâr beklentisi mi, düşük çarpan mı — **veriden çıkarılamaz.** Birini dışarıdan
sabitlemen gerekir.

Ne sabitlersen sabitle, cevap o varsayımdan çıkar:

- **Şirketin kendi tarihsel çarpanını** anchor alırsan (bizim I2), "ima edilen
  kâr" güncel çarpanın yeniden ölçeklenmiş hâli olur — yeni bilgi taşımaz. Bu
  tam olarak yaşandı.
- **Sektör/evren çarpanını** anchor alırsan, aynı şey evren medyanıyla olur; I3
  zaten o karşılaştırmanın kendisi ve ondan türetilecek bir "ima edilen kâr"
  onun cebirsel ikizi olur.
- **Modelden gelen bir "adil çarpan"** alırsan, cevap iskonto oranı ve terminal
  büyüme varsayımlarının bir fonksiyonu olur — veriden değil.

Yani soru şöyle sorulduğunda cevaplanabilir değil:

> *"Piyasa konsensüsü kabul etmiyor mu, yoksa kabul edip düşük değer mi
> biçiyor?"*

**Ayrım gerçek ve ekonomik olarak anlamlı.** Ama fiyat ve tahminden ölçülemez;
ölçmek için üçüncü, bağımsız bir gözlem gerekir — örneğin opsiyon fiyatlarından
ima edilen belirsizlik, ya da kredi marjlarından ima edilen risk. İkisi de
elimizde yok.

## I3 de aynı döngüselliği taşıyor (dış inceleme, 2026-08-07)

Bağımsız bir okuma bu belgeyi denetledi ve I1=I2 özdeşliği ile tanımlanabilirlik
sorununu aynı şekilde buldu. Bir nokta **eklendi ve haklı**, burada kayda
geçiyor:

**Güncel çarpan `C = P / G`'dir — paydada yönlendirmenin kendisi var.**
Dolayısıyla I3'ü *"piyasa kârı kabul ediyor ama çarpanı düşürüyor"* diye
yorumlamak döngüseldir: çarpanı hesaplamak için G'yi zaten kabul etmiş
oluyoruz.

I3 **betimleyici ölçü olarak geçerli kalır** — aynı G bütün evrene ve bütün
dönemlere tutarlı biçimde uygulanıyor, dolayısıyla sıralama anlamlıdır. Geçersiz
olan yalnız nedensel yorumdur.

Bu, yukarıdaki tanımlanabilirlik sonucunu güçlendiriyor: yalnız I2 değil,
**üç değişkenin hiçbiri** "inanmamak vs iskonto" ayrımını taşımıyor.

## Doğru okuma — ve o test zaten koşuldu

Ayrım düşünce geriye üç geçerli **betimleyici** değişken kalıyor, ve iddia şu
olmalı:

> ~~"Piyasa yönlendirmeye inanmıyor."~~
> **"Yönlendirme doğru kabul edildiğinde şirket, kendi geçmişine ya da evrene
> göre normalden düşük bir ileri çarpanda işlem görüyor."**

Bu üç değişken bu koşuda **zaten ölçüldü**:

| doğru adlandırma | bu belgedeki | t | eşik |
|---|---|---|---|
| kendi tarihsel medyanına göre iskonto | I1 | −1,67 | 2,31 |
| kendi bandındaki yüzdelik dilim | I4 | −1,49 | 2,31 |
| evren medyanına göre iskonto | I3 | −1,95 | 2,31 |

**Hiçbiri geçmiyor.** Yani *"kim kendi normaline göre alışılmadık ucuz"* sorusu —
kesitsel testin sormadığı, gerçekten yeni olan soru — ölçüldü ve sonraki 63
seans getirisini sıralamadı.

Ön kayıttaki başlık ve yorum çerçevesi hatalıydı; **ölçülen değişkenler
doğruydu** ve yeniden koşulmalarını gerektiren bir şey yok.

## Geriye kalan iki gerçek değişken

Ayrım çökünce elde iki bağımsız ölçüm kalıyor ve ikisi de test edildi:

- **kendi tarihine göre ucuzluk** (I1/I2, aynı şey): t −1,67
- **evrene göre ucuzluk** (I3): t −1,95

İkisi de eşiğin altında. **I3 en güçlüsü ve üst-alt farkı −%2,24** — yani evrene
göre ucuz olanlar daha kötü getirmiş, ön kayıttaki işaretin tersi. Eşiği
geçmediği için bulgu değil ve işaret çevrilmiyor;
[us-forward-valuation-result.md](us-forward-valuation-result.md)'deki aynı ters
eğilimle tutarlı ve orada da rejimle karıştığı yazılmıştı.

## Betimleyici iddia ayakta

Ön kayıtta yazılmıştı ve tekrarlanmalı: bu test *"fiyatın konsensüse göre
nerede durduğunu tarif edebiliriz"* iddiasını **çürütmüyor**. Tarif edilebilir —
ileri çarpan hesaplanır, kendi geçmişiyle ve evrenle karşılaştırılır, tablo
kurulur. Hepsi doğrudur.

Çürütülen tek şey: *"o yüzden yükselecek."*

## Sınırlar

- Tarihsel medyan asgari 4 önceki gözlemle kuruldu; şirket başına en fazla ~20
  çeyrek var, medyan gürültülü. I1/I2 ve I4 bundan zayıflıyor.
- 60 şirket, 2020-2026, ABD büyük sermaye.
- Yönlendirme, analist konsensüsünün vekili; gerçek konsensüs vintage'ı
  2026-08-07'den itibaren birikiyor.
- Sektör medyanı anchor olarak **bilinçli kullanılmadı** (ön kayıt): sektör
  tanımı bir seçimdir ve sonucu ona duyarlı kılardı. Bu tercih, yukarıdaki
  tanımlanabilirlik sonucunu değiştirmez — sektör kullanılsaydı da aynı cebirsel
  ikizlik çıkardı.
