# Sonuç — yönlendirme değişiminin mekanik tahmini

**Ön kayıt:** [us-guidance-forecast-preregistration.md](us-guidance-forecast-preregistration.md)
(2026-08-06, hiçbir özellik hedefle karşılaştırılmadan yazıldı)
**Ölçüm tarihi:** 2026-08-06
**Örneklem:** 193 gözlem (koşu hızı farkında 76), 58 şirket, 2021-2026

## Bir cümlede

Yönlendirme değişimi **kısmen tahmin edilebilir** — bir önceki değişim tek
başına ρ +0,26 veriyor ve aile düzeltmesini geçiyor — ama **ön kayıtta
tanımlanan bileşik skor geçmedi**, çünkü altı özellikten birinin yönünü yanlış
tahmin etmiştim.

## Ölçüm

| özellik | n | ρ | t | sonuç |
|---|---|---|---|---|
| 1 koşu hızı farkı | 76 | +0,1622 | +1,54 | geçmedi |
| **2 son yönlendirme değişimi** | 184 | **+0,2645** | **+3,82** | **aile eşiğini geçer** |
| 3 son 4 değişimin ortalaması | 184 | +0,0416 | +0,59 | geçmedi |
| 4 aralık genişliği | 193 | −0,0186 | −0,27 | geçmedi |
| 5 genişlikteki değişim | 193 | −0,0407 | −0,65 | geçmedi |
| **6 yönlendirmenin yaşı** | 193 | **−0,2129** | **−2,99** | **eşiği geçer, TERS YÖNDE** |
| **7 bileşik sıra skoru** | 193 | +0,0207 | +0,30 | **geçmedi** |

Aile eşiği |t| > 2,18 (7 özellik, 10.000 kümelenmiş permütasyon).
Hiçbir getiri kullanılmadı.

## Ne oldu

**Bulunan gerçek şey:** yönlendirme değişimleri **otokorele**. Geçen çeyrek
yükselten şirket bu çeyrek de yükseltme eğiliminde (ρ +0,26, t +3,82). Bu,
sandbagging alışkanlığının ölçülmüş hâli.

**Benim hatam:** 6 numarayı yanlış tanımlamışım. Ön kayıtta "uzun süre
dokunulmamış yönlendirme revizyona yaklaşır" yazdım — bu bir **büyüklük**
sezgisi, ama hedef **işaretli** değişim. Yaş, değişimin yönünü değil boyutunu
tahmin edebilirdi; işaretli bir hedefe pozitif işaret atamak baştan hatalıydı.
Veri tersini söylüyor: yönlendirmesine uzun süre dokunmayan şirket dokunmamaya
devam ediyor (ρ −0,21).

**Sonuç:** bileşik skor, 6 numaranın ters işareti yüzünden birbirini götürdü ve
+0,02'de kaldı.

## Karar kuralı uygulandı

Ön kayıt maddesi 3: *"Tek tek özellikler geçip bileşik geçmezse → bileşiğin
ağırlıkları sonradan ayarlanmaz. Sonuç olduğu gibi raporlanır."*

**Ağırlıkları düzeltmiyorum.** 6 numaranın işaretini çevirip bileşiği yeniden
koşmak, sonucu gördükten sonra modeli sonuca uydurmak olurdu — ve o rakam
hiçbir şey ifade etmezdi. Kural bu ihtimal için önceden yazılmıştı ve
uygulanıyor.

**2 numaranın tek başına eşiği geçmesi bir başlangıç noktasıdır, sonuç
değildir.** Yedi özellik içinden geçeni seçip onun üstüne inşa etmek, aynı seçim
yanlılığıdır. Üzerine kurulacak her şey **kendi ön kaydını** gerektirir ve
örneklem-dışı doğrulanmalıdır.

## Kapsama sorunu

269 gözlem "farklı veya okunamayan mali yıl" nedeniyle düştü — en büyük tek
kayıp ve hâlâ zayıf halka yıl çıkarımı. 73 gözlem çeyrek aralığı dışında kaldı.

**Koşu hızı farkı yalnız 76 gözlemde hesaplanabildi** (193'ün %39'u). Bunun
sebebi, çeyreğin tamamının gerçekleşen düzeltilmiş EPS'inin çıkarılabilmiş
olması şartı. En güçlü olacağını düşündüğüm özellik en zayıf kapsamaya sahip ve
t = 1,54 ile sonuçsuz kaldı — yani "işe yaramıyor" değil, "ölçülemedi".

## Bunun anlamı

Yönlendirme değişiminin **tahmin edilebilir bir bileşeni var** ve o bileşen
şirketin kendi geçmiş davranışından geliyor.

Bu, [us-earnings-surprise-result.md](us-earnings-surprise-result.md)'deki
desenin aynısı olabilir: orada geçmiş sürprizler bir sonrakini ρ +0,33 ile
tahmin ediyordu ama tahmin edilebilen kısım **sıfır kazandırıyordu**, çünkü
piyasa onu zaten fiyatlıyordu.

Test edilmesi gereken bir sonraki şey bu ayrıştırmadır: yönlendirme değişiminin
**tahmin edilebilir** kısmı mı yoksa **kalıntısı** mı açıklama günü hareketini
üretiyor. [us-guidance-signal-result.md](us-guidance-signal-result.md) toplam
etkiyi ölçtü (+%6,45); ayrıştırma hangi yarısının ödediğini söyler.

Eğer sürprizdeki gibi çıkarsa — tamamı kalıntıda — o zaman mekanik tahmin
işe yaramaz ve geriye kalan tek yol, geçmiş veride **olmayan** bilgidir: dil,
çeyrek arası bildirimler, dış değişkenler. LLM'in yeri orasıdır ve o zaman
gerekçesi ölçülmüş olur.

## Ayrıştırma — yukarıdaki soru cevaplandı (aynı gün, 119 gözlem)

Tahmin edici önceden sabitti: **bir önceki yönlendirme değişimi**. Yedi
özellikten aile eşiğini geçen tek özellik oydu; yeni bir tahmin edici aranmadı,
çünkü sonucu gördükten sonra en iyisini seçmek olurdu.

| yönlendirme değişiminin bileşeni | ρ | şans bandı | konum | üst-alt |
|---|---|---|---|---|
| **tahmin edilebilir** (önceki değişim) | −0,0312 | −0,153..+0,109 | **içinde** | +%1,38 |
| **kalıntı** (gerçekleşen − tahmin) | **+0,4196** | −0,085..+0,187 | **dışında** | **+%6,85** |
| ham değişim (ikisinin toplamı) | +0,4520 | −0,134..+0,155 | dışında | +%8,47 |

**Ödemenin tamamı yine kalıntıda.** Tahmin edilebilir kısım bandın içinde ve
sıfırdan ayırt edilemiyor.

*(Not: tahmin edilebilir kısmın üst-alt farkı +%1,38 görünüyor ama rank
korelasyonu bandın içinde. İkisi çelişebilir — ρ bütün sıralamayı, çeyrek farkı
yalnız uçları ölçer. Ön kayıtlı istatistik ρ'dur ve karar ona göre verilir.)*

### Aynı yasa, ikinci kez ve bağımsız değişkende

| | tahmin edilebilir | kalıntı |
|---|---|---|
| EPS sürprizi | +%0,39 | +%2,26 |
| **yönlendirme değişimi** | **+%1,38** | **+%6,85** |

İki farklı değişken, iki bağımsız ölçüm, aynı sonuç: **piyasa, şirketin kendi
geçmişinden çıkarılabilen her şeyi fiyatlıyor.** Bir örnek tesadüf olabilirdi;
iki bağımsız örnek bir düzenlilik.

### Pratik sonucu

Mekanik yönlendirme tahmini **para etmez** — çalışsa bile (ρ +0,26 ile
çalışıyor). Ödül tamamen, şirketin geçmiş davranışından **çıkarılamayan** kısmı
öngörmekte.

Ve ödül büyük: kalıntı yönlendirme değişimi %6,85, EPS sürprizi kalıntısının
(%2,26) **üç katı**.

Bu, LLM'in bu projede ilk kez ölçülmüş bir gerekçeye sahip olduğu yerdir. Ama
gerekçe "LLM başarır" değil, şudur: **geriye kalan bilgi, mekanik bir kuralın
erişemeyeceği yerdedir** — dil, çeyrek arası bildirimler, dış değişkenler.
Başarıp başaramayacağı ayrı bir soru ve kendi ön kaydını gerektirir.

## Sınırlar

- Tek dönem (2021-2026), tek evren, örneklem-dışı doğrulama yok.
- Yıl çıkarımı gözlemlerin yarısından fazlasını eliyor.
- Koşu hızı farkı düşük kapsamada ölçüldü ve sonuçsuz.
- 6 numara ölçüldü ama **ön kayıtta yanlış tanımlanmıştı**; ters işaretli sonucu
  bir bulgu olarak değil, bir spesifikasyon hatası olarak okumak gerekir.
