# Sonuç — üç mekanik aile, hiçbiri işlem yapılabilir sinyal vermedi

**Ön kayıt:** [us-mechanical-families-preregistration.md](us-mechanical-families-preregistration.md)
(2026-08-07, hiçbir özellik hedefle karşılaştırılmadan yazıldı)
**Ölçüm tarihi:** 2026-08-07
**Örneklem:** ~1.379 açıklama olayı, 60 şirket, 2020-2026

## Bir cümlede

Post-earnings dynamics, fundamental momentum ve quality change ailelerinin on
özelliğinden **hiçbiri** aile eşiğini geçmedi; bileşik skor da geçmedi.

## Birincil tablo — özellik → sonraki 21 seans (işlem yapılabilir)

| özellik | n | ρ | t | üst-alt |
|---|---|---|---|---|
| A1 çeyrek arası bildirim sayısı | 1.319 | −0,0357 | −1,34 | −%0,66 |
| A2 ek item kodu | 1.379 | +0,0214 | +0,95 | −%0,52 |
| B1 gelir büyüme ivmesi | 1.379 | +0,0477 | +0,96 | +%0,43 |
| B2 kâr büyüme ivmesi | 1.376 | +0,0445 | +1,01 | +%0,14 |
| B3 gelir büyümesi | 1.379 | +0,0358 | +0,70 | +%0,03 |
| C1 brüt marj değişimi | 1.238 | −0,0172 | +0,03 | +%0,02 |
| C2 net marj değişimi | 1.377 | +0,0309 | +1,12 | +%1,06 |
| C3 FCF dönüşümü değişimi | 1.264 | +0,0046 | −0,29 | −%0,11 |
| C4 tahakkuk değişimi | **196** | +0,1110 | −0,31 | +%1,19 |
| **D1 bileşik** | 1.377 | +0,0404 | +0,70 | +%0,79 |

**Aile eşiği |t| > 3,91.** En yüksek değer +1,12.

> **DÜZELTME (2026-08-07).** Bu tablonun ilk hâli hatalı bir t istatistiği
> kullanıyordu: `t = ρ / sd(null)`, yani permütasyon null'ı sıfır merkezli
> varsayılmıştı. Kümelenmiş permütasyonda null sıfırda merkezlenmez
> ([olcum-metodolojisi.md](olcum-metodolojisi.md) 0d-2). Merkeze göre yeniden
> hesaplandı; **hüküm değişmedi** (hiçbiri aile eşiğini geçmiyor) ama t
> değerleri değişti — B1 +2,15'ten +0,96'ya, C4 +1,85'ten −0,31'e.
>
> İlk hâlde *"tek başına test edilseydi B1 ve C4 anlamlı görünürdü"* yazmıştım.
> **Düzeltilmiş değerlerle bu doğru değil**; o cümle geri çekilmiştir.

**Karar kuralı 2 uygulandı:** bileşik geçmedi, aile düzeyinde sinyal yok.
Ağırlıklar sonradan ayarlanmadı.

## İkincil tablo GERİ ÇEKİLDİ — kendi kusurum

Ön kayıt ikinci bir tablo öngörüyordu: özellik → tepki penceresi, "bu haber mi"
sorusu için, karar vermeyen. O tablo **ileri bakış içeriyor** ve sayıları
yayınlanmıyor.

**Sebep.** Özellik, dosyalama tarihinden **önce biten** son finansal dönemden
hesaplanıyor. Ama o dönem, dosyalamadan yalnız 16-33 gün önce bitiyor — yani
**tam o açıklamada yayınlanan çeyrek**:

```
ABT   dosyalama 2026-07-16  ->  kullanilan donem sonu 2026-06-30  (16 gun once)
CAT   dosyalama 2026-04-30  ->                        2026-03-31  (30 gun once)
AAPL  dosyalama 2026-07-30  ->                        2026-06-27  (33 gun once)
```

Tepki penceresini bu özellikle açıklamak, açıklamanın içeriğiyle açıklamanın
kendi gününü açıklamaktır. Brüt marj değişimi orada t = +5,26 verdi; bu bir
bulgu değil, **tanım gereği** öyle çıkması gereken bir sayı.

**Birincil tablo bu kusurdan etkilenmez:** giriş tepkiden iki seans sonra ve o
noktada veri kamuya açıktır. İşlem yapılabilirlik korunuyor.

Ön kayıt ikincil tabloyu "karar vermez" diye işaretlemişti, dolayısıyla hiçbir
karar kirlenmedi. Ama sayılar bulgu gibi sunulamaz.

## Kapsama

| eleme sebebi | |
|---|---|
| C4 tahakkuk değişimi | yalnız **196** gözlem (nakit akış artifact kapsaması) |
| C1 brüt marj değişimi | 1.238 (brüt kâr her şirkette yok) |
| A1 | 1.319 (ilk açıklamada "önceki" yok) |

C4'ün ρ değeri en yüksek olan (+0,111) ama örneklemi en küçük olan özellik ve
merkeze göre t'si **negatif** (−0,31) — yani ρ'su null'ının merkezinin bile
altında. Bu **"işe yarıyor" değil, "ölçülemedi"** demektir.

## Bunun ailelere göre okunuşu

- **Post-earnings dynamics:** çeyrek arası bildirim sayısı ve ek item kodu,
  sonraki ay getirisini sıralamıyor. Açıklama tipine göre drift farkı
  bulunamadı.
- **Fundamental momentum:** ivme ile seviye arasında anlamlı bir fark yok
  (B1 t = +0,96, B3 t = +0,70) ve ikisi de aile eşiğinin çok altında. Önceki
  taramada bu aile 10 kesitte ölçülmüştü; şimdi 1.379 gözlemde ölçüldü ve
  **yine yok**.
- **Quality change:** marj ve nakit kalitesi değişimleri sonraki ayı
  sıralamıyor.

## Ayrıştırma yapılmadı, çünkü gerekmedi

Ön kayıt, aile eşiğini geçen her özellik için tahmin edilebilir/kalıntı
ayrıştırmasını zorunlu kılıyordu. Hiçbir özellik geçmediği için o adım
tetiklenmedi.

## Sınırlar

- 60 şirket; S&P 500 için fiyat defterimiz yok.
- 2020-2026, ABD büyük sermaye, tek ufuk (21 seans).
- Aile eşiği 3,91 yüksek; **tek başına test edilen** bir hipotez için doğru eşik
  1,96'dır. Bu tarama, on hipotezi birlikte test etmenin bedelini ödüyor ve bu
  bilinçli bir tercih — tek tek koşup geçeni raporlamak düzeltilmemiş çoklu test
  olurdu.
- Negatif sonuç, bu ailelerin **hiç** sinyal taşımadığını göstermez; bu
  örneklemde ve bu tanımlarla, aile düzeltmesinden sonra ayırt edilebilir bir
  şey yok. Görülebilir en küçük etki, çoğu özellik için ρ ≈ 0,09'dur.
