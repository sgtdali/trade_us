# Sonuç — beklentiye göre değerleme de ödemiyor (yasanın üçüncü doğrulaması)

**Ön kayıt:** [us-forward-valuation-preregistration.md](us-forward-valuation-preregistration.md)
(2026-08-07, hiçbir oran getiriyle eşleştirilmeden yazıldı; **null çıkacağı
önceden tahmin edildi**)
**Ölçüm tarihi:** 2026-08-07
**Örneklem:** 487 olay, 60 şirket

## Bir cümlede

Şirketin kendi yönlendirmesi doğru kabul edilip fiyat ona göre değerlendiğinde,
hiçbir değişken aile eşiğini geçmedi — ve önceden yazılan tahmin buydu.

## Birincil tablo — 63 seans

| değişken | n | ρ | t | üst-alt |
|---|---|---|---|---|
| F1 ileri kazanç getirisi | 487 | −0,0875 | **−1,98** | −%2,98 |
| F2 geriye dönük kazanç getirisi | 487 | −0,0772 | −1,72 | −%2,39 |
| **F3 ileri − geri farkı** | 487 | **−0,0054** | −0,14 | +%0,76 |
| F4 ima edilen getiri | 487 | −0,0156 | −0,19 | +%0,73 |

**Aile eşiği |t| > 2,34 (4 değişken). Hiçbiri geçmedi.**

> **DÜZELTME (2026-08-07).** t istatistiği null'ın merkezine göre yeniden
> hesaplandı ([olcum-metodolojisi.md](olcum-metodolojisi.md) 0d-2). Bu tabloda
> değişim küçük (F4 −0,36 → −0,19) ve **hüküm aynı**; ABD verisinde null zaten
> sıfıra yakın merkezleniyordu. BIST'te öyle değildi ve orada sonucu
> değiştirdi.

Karar kuralı 2 uygulandı: **yasanın üçüncü doğrulaması.**

## Üç şey kaydedilmeli

### 1. İşaretler ön kayıttakinin tersi

Ön kayıt hepsini **pozitif** varsaymıştı (yüksek kazanç getirisi = ucuz →
yüksek getiri). Çıkan negatif: beklentisine göre ucuz olanlar daha **kötü**
getirmiş, F1'de üst-alt farkı −%2,98.

Hiçbiri eşiği geçmediği için bu bir bulgu değildir ve **işaret çevrilmiyor.**
Ayrıca 2020-2026, büyümenin değeri belirgin biçimde geçtiği bir dönemdir; bu
eğilim sinyal değil **rejim** olabilir ve bu testle ayrılamaz.

### 2. F1 tek başına test edilseydi "anlamlı" olurdu

t = −1,98, tek test eşiği 1,96. Dört değişkenin ailesinde eşik 2,34 ve geçmiyor.

Bu, çoklu test düzeltmesinin somut bedeli — ve bu sefer **ters yönde** bir
"bulgu" üretecekti: *"beklentisine göre ucuz hisseler geride kalıyor, p < 0,05."*
Tek başına koşulsaydı yayınlanabilir görünürdü.

### 3. Kullanıcının asıl sorusu (F3) tam sıfır

F3 = (yönlendirme − TTM) / fiyat, yani **şirketin geleceği geçmişinden ne kadar
farklı**. ρ = −0,005, t = −0,14. Ölçülebilir hiçbir sıralama gücü yok.

Bu, sorunun en doğrudan hâliydi ve cevabı en net olanı: beklentinin geçmişten
sapması, fiyatta zaten var.

## Yasanın üçüncü doğrulaması

| ölçüm | tahmin edilebilir kısım | kalıntı |
|---|---|---|
| EPS sürprizi | +%0,39 | +%2,26 |
| yönlendirme değişimi | +%1,38 | +%6,85 |
| **beklentiye göre değerleme** | **eşiği geçmiyor** | — |

Yönlendirme, tanımı gereği tahmin edilebilir kısımdır — profesyonel
ekstrapolasyonun kendisi. Ona dayalı bir değerleme sıralaması, kamuya açık bir
beklentiyi yeniden paketlemekten ibarettir ve fiyat onu zaten içerir.

**Ön kayıt bu sonucu önceden tahmin etmişti** ve "pozitif sonuç negatiften daha
bilgilendirici olur" diye yazmıştı. Pozitif çıkmadı; yasa ayakta.

## Güç

Örneklem beklenenden büyük çıktı (487, tahmin ~200). SE ≈ 0,045, aile eşiğiyle
**görülebilir en küçük etki ρ ≈ 0,106**.

Negatif sonucun anlamı: **etki varsa 0,106'dan küçüktür.** F1'in −0,0875'i bu
sınırın hemen altında ve ters yönde.

## Kapsama

| eleme sebebi | |
|---|---|
| 4 çeyrek gerçekleşen yok | 68 |
| kaynakta doğrulanmadı | 65 |
| ileri pencere yok | 31 |
| seans değil / kapsam dışı | 3 |

Bu testte yıl çıkarımı kullanılmadı (yönlendirme değişimi değil **seviyesi**
ölçülüyor), bu yüzden diğer testlerdeki 274'lük kayıp yok — örneklem 487 ile
bugüne kadarki en büyüğü.

## Nokta-zaman kontrolü

```
giris - yonlendirme tarihi -> min 2, medyan 2, maks 5 gun, negatif: 0
```

Temiz.

## Sınırlar

- 60 şirket, 2020-2026, ABD büyük sermaye.
- Yönlendirme, analist konsensüsünün yerine kullanıldı; konsensüsün tarihsel
  vintage'ı elde edilemiyor.
- Mutlak adil değer hesaplanmadı ve bu bilinçliydi — iskonto oranı seçmek
  sonucu varsayıma bağımlı kılardı. Bu test "bu hisse %30 ucuz" sorusunu
  cevaplamaz, "beklentisine göre evrende nerede duruyor" sorusunu cevaplar.
- Değer eğiliminin negatif çıkması rejimle karışıyor ve ayrılmadı.
