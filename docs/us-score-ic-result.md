# Sonuç — LLM puanının kesitsel sıralama gücü (IC)

**Ön kayıt:** [us-score-ic-preregistration.md](us-score-ic-preregistration.md)
(2026-08-05, veri çekilmeden önce yazıldı; Ek 1-5)
**Ölçüm tarihi:** 2026-08-06
**Koşu:** `us/backtests/ic-2024-v1`

## Bir cümlede

60 şirketlik dört sektörlü bir evrende, aylık değerleme raporlarına 0-100 puan
veren `gemini-3.6-flash-high`'in puanı, sonraki dönem getirilerini **ölçülebilir
biçimde sıralamadı**; 21 kesitte ortalama IC −0,023 ve %95 üst sınır **+0,030**.

## Ana ölçüm — 1 aylık ufuk

| | |
|---|---|
| kesit | 21 (2024-08 → 2026-04) |
| evren | 60 şirket (kapsama boşlukları hariç 58-60/ay) |
| ortalama IC | **−0,0231** |
| standart hata | 0,0270 |
| t | −0,86 |
| şans bandı (10.000 permütasyon) | −0,047 .. +0,047 |
| konum | dağılımın 21. yüzdelik dilimi, **band içinde** |
| %95 üst sınır | **IC < +0,030** |
| üst çeyrek − alt çeyrek | dönem başına −%0,25 (21 dönemin 10'u pozitif) |

Aylık IC'ler −0,314 ile +0,179 arasında salındı; tutarlı bir işaret yok.

## Ufuk testi (Ön kayıt Ek 4)

| ufuk | kesit | ort. IC | t | şans bandı | bağımsız gözlem |
|---|---|---|---|---|---|
| 1 ay | 21 | −0,0231 | −0,86 | ±0,047 | 21 |
| 3 ay | 21 | −0,0239 | −1,02 | ±0,047 | ~7 |
| 12 ay | 13 | −0,0308 | −1,24 | ±0,059 | ~1 |

Üç ufuk da bandın içinde, üçü de negatif tarafta ve **birbirine çok yakın**.
Ufku uzatmak sonucu değiştirmedi.

Bu, olay tabanlı sistemin dayandığı varsayımı test ediyordu: portföy 14 ayda üç
kez değişmişti, yani ortalama tutma süresi ~4,7 aydı ve sistem örtük olarak
çeyrek uzunlukta bir sinyale bahis oynuyordu. O varsayım destek bulmadı.

**Bu ufuklar karar tetiklemez ve tetiklemedi** (Ek 4'te önceden sabitlendi).
Örtüşen pencerelerde kesitler bağımsız değildir; permütasyon bandı bunu
düzeltmez — her kesit kendi içinde permüte edilir, kesitler arası bağımlılık
korunur — dolayısıyla bandlar **olduğundan dar** okunur. Bir "band içinde"
sonucu bundan güçlenir, bir "band dışında" sonucu güvenilmez olurdu.

**Bir çelişki, olduğu gibi:** IC negatifken üst çeyrek − alt çeyrek farkı 3
aylık ufukta +%1,22 (13/21 pozitif), 12 aylıkta +%1,84 (7/13). IC bütün
sıralamayı, çeyrek farkı yalnız uçları ölçer; uçlarda hafif bir etkinin ortada
tersine dönmesi mümkündür. Ancak bu rakamlar ~7 ve ~1 bağımsız gözlemden gelir
ve tek başına hiçbir şey iddia etmez. Kayda geçirilmesinin sebebi, sonucun
tamamının burada olması gerektiğidir.

## Tekrarlanabilirlik (Ön kayıt Ek 2)

| | |
|---|---|
| ortak şirket-ay | 144 |
| rapor metni birebir aynı | 69 (güvenilirlik yalnız bunlardan) |
| rapor metni farklı | 75 (girdi değişmiş, dışarıda) |
| \|Δpuan\| | ortalama 3,4 · medyan 2,0 · maks 20 |
| test–retest Spearman | **+0,960** (havuzlanmış) |
| sırası ±6'dan fazla oynayan | 0/69 |

Aynı şirket, aynı gün, aynı rapor, iki bağımsız koşu — sıralama korelasyonu
0,96. **Sorun modelin rastgele cevap vermesi değil.** Model kendini tekrarlıyor;
tutarlı biçimde işe yarayan bir sıralama yapamıyor. Zayıflama √0,960 ≈ 0,98,
yani gözlenen IC'nin ~%98'i gerçektir ve granülerlik (58 şirkette 13-19 farklı
puan) ayrıca ölçüldü: tavan 0,980, etkisi %2.

`IC / √güvenilirlik` bir **üst sınır** olarak −0,024 verir; hiçbir kararı
tetiklemez (Ek 2'de önceden yazıldı).

## Ne iddia edildi, ne edilmedi

**Edilen:** Bu evrende, bu puanla, bu dönemde, IC ≥ +0,03 büyüklüğünde bir
kesitsel sıralama gücü **yoktur**. 0,08 ve 0,05 pratik olarak dışlanmıştır
(bu sonucun çıkma olasılığı sırasıyla ~%0 ve %0,2).

**Edilmeyen:** Hipotez **elenmiş sayılmamıştır**. Ön kayıttaki durma kuralının
3. maddesi band içinde kalındığında 60 aya uzatmayı öngörür; koşu kota nedeniyle
21 kesitte sonlandırıldı (Ek 5). Elenemeyen aralık IC 0,01-0,02'dir ve 12
pozisyonlu bir portföyde bu, işlem maliyeti öncesi yılda ~%1-2'ye karşılık
gelir — bir benchmark'ı yenmez.

**Erken sonlandırma sonucu seçmez.** Kalan üç ayın ortalamayı bandın üstüne
taşıyabilmesi için her birinin **+0,536** IC vermesi gerekirdi; 21 ayda görülen
en yüksek değer +0,179, teorik tavan ~0,98 (Ek 5'te sonuç görülmeden
hesaplandı).

## Bu sonucu bağlama oturtan üç şey

1. **Girdide zaten sinyal yoktu.** Değerleme metriklerinin kesitsel sıralama
   gücü 2016-2024 örnekleminde ayrıca test edilmiş ve elenmişti
   ([us-valuation-signal-result.md](us-valuation-signal-result.md)). Prompt
   modele "yalnız aşağıdaki rapora dayan" der. Raporda bilgi yoksa onu okuyan
   bir model bilgi üretemez.
2. **Dört bağımsız olmayan koşu aynı yeri gösteriyor.** wf-2025-v3 (−0,042),
   event-2025-v1 (−0,012), score-2025-v1 (−0,032), ic-2024-v1 (−0,023). Dördü
   de negatif. Gerçek IC +0,05 olsaydı en güçlü ölçümün negatif çıkma olasılığı
   %2'dir.
3. **Model tarafı elendi.** Tutarlılık 0,96 olduğu için "model gürültülü olduğu
   için sinyal görünmüyor" savunması kapalıdır. Darboğaz okuyucu değil, okunan
   şeydir.

## Bilinen sınırlar

- **Hayatta kalma ve evren seçim yanlılığı.** Evren bugünkü listeden, benim
  tarafımdan seçildi; 2024-2026 arasında borsadan çıkan isim yok.
- **Tek model, tek prompt.** Sonuç `gemini-3.6-flash-high` ve
  `direct-score.v1` içindir.
- **Eğitim verisi kontaminasyonu ölçülmedi.** Model bu dönemi bilebilir. Etkisi
  tek yönlüdür: pozitif bir sonucu şüpheli kılardı, negatif bir sonucu değil.
- **Büyük sermayeli, verimli fiyatlanan bir evren.** Yanlış fiyatlamanın daha
  olası olduğu küçük sermaye segmenti test edilmedi.
- **21 kesit, 24 değil.** Ek 5.

## Bundan sonra

Ön kayıt uzatmaya (60 ay) izin verir ve kural hâlâ geçerlidir. Ancak elenemeyen
aralık (IC 0,01-0,02) zaten işe yaramaz büyüklükte olduğu için uzatmanın pratik
getirisi düşüktür: üst sınırı +0,030'dan ~+0,009'a indirir, yani "muhtemelen
yok"u "ölçüldü, yok"a çevirir.

Ölü olduğu **ölçülerek** gösterilen yollar, bir daha denenmemek üzere:

- prompt / model / puanlama ölçeği tasarımı (kanıt: tutarlılık 0,96)
- ufku uzatmak (kanıt: 1, 3, 12 ay aynı sonuç)
- portföy kuralları, pozisyon sayısı, tetikleyici tasarımı (kanıt: seçim
  rastgeleden ayırt edilemedi, 58,9. yüzdelik)

Test edilmemiş kalanlar: **girdi içeriği** (raporda olmayan bilgi türleri) ve
**evren** (küçük sermaye). Her ikisi de yeni birer hipotezdir ve kendi ön
kayıtlarını gerektirir.
