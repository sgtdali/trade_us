# Ön kayıt — mekanik sinyal taraması ve örneklem-dışı takip

**Yazılma tarihi:** 2026-08-06
**Durum:** Bölüm 1 (tarama) koşuldu ve sonucu aşağıda. Bölüm 2 (örneklem-dışı
test) **sonuç görülmeden** yazıldı; 2021-2024 koşusu bu satırlar yazılırken
arka planda üretimdeydi ve hiçbir IC hesaplanmamıştı.

## Neden

[us-score-ic-result.md](us-score-ic-result.md) LLM puanı için IC ≥ +0,03'ü
dışladı. Açık kalan soru şuydu: bu, LLM hakkında bir sonuç mu, yoksa ölçüm
düzeneğinin hiçbir şey göremediğinin bir işareti mi? Bunu ayırmanın yolu bir
**pozitif kontrol** koymaktır — bilinen, sağlam bir anomaliyi aynı düzenekte
ölçmek. Görebiliyorsak düzenek çalışıyordur.

## Bölüm 1 — tarama (koşuldu)

On sinyal veri görülmeden sabitlendi, hepsi raporlandı, seçim yapılmadı.
Evren ve dönem `ic-2024-v1` ile aynı: 60 şirket, 21 kesit (2024-08 → 2026-04),
1 aylık ileri getiri, ortalama Spearman IC.

Çoklu test düzeltmesi: **max |t|** üzerinden permütasyon (2.000 tekrar, her
kesit kendi içinde karıştırılır). İlk denememde `max |ortalama IC|`
kullanmıştım; bu yanlıştır, çünkü en yüksek varyanslı sinyale göre kalibre olur
ve düşük varyanslı bir sinyali haksız cezalandırır. t standartlaştırır.

| sinyal | kesit | ort. IC | SE | t |
|---|---|---|---|---|
| momentum_12_1 *(pozitif kontrol)* | 21 | +0,0633 | 0,0562 | +1,13 |
| momentum_6_1 | 21 | +0,0454 | 0,0517 | +0,88 |
| reversal_1m | 21 | −0,0459 | 0,0500 | −0,92 |
| low_volatility | 21 | −0,0764 | 0,0568 | −1,34 |
| net_margin | 21 | +0,0325 | 0,0424 | +0,77 |
| gross_margin | 21 | +0,0283 | 0,0332 | +0,85 |
| revenue_growth | 10 | −0,0019 | 0,0882 | −0,02 |
| earnings_growth | 10 | +0,0452 | 0,0793 | +0,57 |
| accruals | 13 | +0,0165 | 0,0463 | +0,36 |
| **fcf_conversion** | 21 | **+0,0530** | **0,0242** | **+2,19** |

Aile eşiği: **|t| > 3,22**. Hiçbiri geçmedi.

### Bölüm 1'in asıl sonucu güç analizi

| sinyal | görülebilir en küçük IC | IC 0,05'i görmek için gereken kesit |
|---|---|---|
| momentum_12_1 | 0,181 | 274 |
| low_volatility | 0,183 | 281 |
| net_margin | 0,136 | 156 |
| gross_margin | 0,107 | 96 |
| **fcf_conversion** | **0,078** | **51** |

**Pozitif kontrol sonuçsuz kaldı.** Momentum doğru işarette ve makul büyüklükte
(+0,063) çıktı ama SE 0,056 ile sıfırdan ayrılmıyor. Yani bu düzeneğin gerçek
bir sinyali yakaladığına dair elimizde hâlâ kanıt yok.

**Bu, LLM sonucunu geçersiz kılmaz.** LLM puanının SE'si 0,027'ydi ve IC ≥ 0,03
gerçekten dışlandı. Sinyalden sinyale güç değişir; LLM puanı aylar arasında
momentumdan çok daha durağan davrandığı için SE'si yarısı kadardı. Doğru ifade:
*LLM için "yok" denebilir, evren için "hiçbir şey yok" denemez.*

### Bilinen sınırlar

- `revenue_growth`, `earnings_growth`, `accruals` yalnız 10-13 kesitte
  hesaplanabildi (`comparison_value` kapsaması). Bunlar için hiçbir şey
  söylenemez.
- İlk koşuda nakit akış metrik kimliğini yanlış yazdım
  (`net_cash_from_operating`, doğrusu `cf_net_operating_activities`); bu
  `accruals`'ı bozmuş ve `fcf_conversion`'ı sabit sıfır yapmıştı. Tablo
  düzeltilmiş koşudandır.
- `fcf_conversion` yalnız net kâr > 0 olduğunda tanımlı (n≈57/60). Bu bir
  hayatta kalma filtresi değil ama bir seçim; zarar eden şirket dışarıda kalır.

## Bölüm 2 — örneklem-dışı test (sonuç görülmeden yazıldı)

### Hipotez

`fcf_conversion` = faaliyet nakit akışı / net kâr, yüksek olanı üstte olacak
şekilde sıralandığında, sonraki ay getirilerini pozitif yönde sıralar.

Bu, Bölüm 1'de bir **bulgu değildir** — on testin içinde t = 2,19 tam olarak
şansla beklenen şeydir. Takip edilmesinin tek sebebi, bu düzeneğin ölçebildiği
tek sinyal olmasıdır (gereken kesit 51, diğerlerinde 96-281).

### Örneklem

`us/backtests/ic-2021-v1`, 37 aylık kesit (2021-08 → 2024-07). Bu aylar Bölüm
1'de kullanılmadı. LLM çağrısı içermez, yalnız finansal artifact ve fiyat
gerekir. Koşu bu ön kayıt yazılırken üretimdeydi ve hiçbir IC hesaplanmamıştı.

Not: 2021-2024 farklı bir faiz rejimidir. Bu, testi zorlaştırır, kolaylaştırmaz
— sinyal rejime bağlıysa burada görünmez. Rejim bahanesi sonradan
kullanılamaz; şimdiden kabul ediliyor.

### İstatistik ve karar kuralı

Aynı istatistik: kesitlerin ortalama Spearman IC'si. Tek sinyal test edildiği
için aile düzeltmesi yok, eşik **|t| > 1,96**, ve ayrıca permütasyon bandı
(10.000 tekrar) raporlanır.

1. **37 kesitte t > 1,96 ve işaret pozitif** → sinyal ayakta kalır. Havuzlanmış
   58 kesit ayrıca raporlanır. Sonraki adım: işlem maliyeti altında portföy
   testi.
2. **t < 1,96** → sinyal düşer. Bir daha bakılmaz, alt dönemlere bölünmez,
   ufuk taranmaz.
3. **İşaret ters (t < −1,96)** → sinyal düşer. Ters çevrilip yeniden test
   **edilmez**.

### Önceden reddedilenler

- Ufuk taraması yok. Yalnız 1 ay.
- Alt evren (sektör, büyüklük) kırılımı yok.
- Eşik/kesme noktası aranmaz; ham sıralama kullanılır.
- Sonuç negatifse "2021-2024 rejimi farklıydı" gerekçesi geçersizdir; yukarıda
  önceden kabul edildi.

## Kayıt

Kod: `scratchpad/mech_sweep.py` (kalıcı değil; Bölüm 2 için repoya alınacak).
Tohum 20260806, 2.000 permütasyon (Bölüm 1), 10.000 (Bölüm 2).
