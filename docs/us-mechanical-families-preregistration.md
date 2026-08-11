# Ön kayıt — üç mekanik aile, tek tarama

**Yazılma tarihi:** 2026-08-07
**Durum:** Hiçbir özellik hedefle karşılaştırılmadan yazıldı.

## Neden tek tarama

Üç ayrı araştırma ailesi test edilecek. Birer birer koşup geçeni raporlamak,
oturumlar arası **düzeltilmemiş çoklu test** olur. Hepsi tek ön kayıtla, tek
aile düzeltmesiyle koşulur ([olcum-metodolojisi.md](olcum-metodolojisi.md) 4).

Ayrıca **LLM yoktur ve bu bilinçlidir**: bu ailelerin hiçbiri dil okumayı
gerektirmiyor, ve mekanik taban kurulmadan bir sonraki adımda LLM'in ne kattığı
ölçülemez.

## Tasarım — olay tabanlı, aylık kesit değil

Önceki mekanik tarama aylık kesit kullandı ve **güç yetersizdi**: momentumu
görmek 274 kesit gerektiriyordu, elimizde 21 vardı. Bu tarama açıklama
olaylarını kullanır — 60 şirket × ~20 çeyrek ≈ 1.200 gözlem.

- **Olay:** bir şirketin Item 2.02 8-K dosyalama tarihi.
- **Hedef (birincil):** tepki seansının **ertesi** seansından +21 seans,
  piyasa düzeltilmiş getiri. Tepkinin kendisi dahil değildir.
- **Hedef (ikincil, karar vermez):** tepki penceresi getirisi. Bir özelliğin
  "haber olup olmadığını" gösterir; alınıp satılabilir değildir.
- **Özellikler:** yalnız o tarihte **bilinen son** finansal artifact'tan
  hesaplanır. Açıklamanın kendi rakamları kullanılmaz.

## Özellikler — veri görülmeden sabit, hepsi raporlanacak

### A. Post-earnings dynamics

Açıklamalar **arasında** gelen bilgi. Item kodları elimizde.

| # | özellik | mantık |
|---|---|---|
| A1 | önceki açıklamadan bu yana **çeyrek arası bildirim sayısı** | Çok bildirim = çok yeni bilgi = daha büyük belirsizlik |
| A2 | aynı 8-K'da Item 2.02 **dışında** kod var mı (0/1) | Yeniden yapılanma, değer düşüşü gibi haberlerle birlikte gelen açıklama farklı davranabilir |

### B. Fundamental momentum

Seviye değil **değişim hızı**. Önceki taramada seviyeler test edildi ve null
çıktı; ivme hiç bakılmadı.

| # | özellik | mantık |
|---|---|---|
| B1 | gelir büyümesi **ivmesi** (bu dönem büyüme − önceki dönem büyüme) | Hızlanan büyüme |
| B2 | kâr büyümesi **ivmesi** | Aynı, kârda |
| B3 | gelir büyümesi **seviyesi** | Önceki taramada 10 kesitte ölçülmüştü; burada kapsama daha iyi |

### C. Quality change

Kalitenin kendisi değil, **iyileşme yönü**.

| # | özellik | mantık |
|---|---|---|
| C1 | brüt marj **değişimi** | Fiyatlama gücü iyileşiyor mu |
| C2 | net marj **değişimi** | Aynı, alt satırda |
| C3 | **FCF dönüşümü değişimi** (faaliyet nakit akışı / net kâr) | Kâr kalitesi iyileşiyor mu |
| C4 | **tahakkuk değişimi** | Kâr ile nakit arasındaki açık kapanıyor mu |

### D. Bileşik

| # | özellik |
|---|---|
| D1 | A-C'nin **rank ortalaması**, işaretler yukarıdaki mantığa göre **şimdi** sabit, ağırlıklar eşit |

**Özellik seçimi yapılmayacak.** Hangisinin işe yaradığına bakıp bileşiği ona
göre kurmak, ölçmeye çalıştığımız şeyi yok eder — bu hata bu projede bir kez
yapıldı ve düzeltilmedi, olduğu gibi raporlandı
([us-guidance-forecast-result.md](us-guidance-forecast-result.md)).

## İstatistik

Havuzlanmış Spearman, açıklama **takvim çeyreğine göre kümelenmiş**
permütasyon, 10.000 tekrar.

Çoklu test: 10 özellik üzerinde **max |t|** aile düzeltmesi. Tek test olsaydı
eşik 1,96 olurdu; ailede ~3 civarı bekleniyor ve gerçek değer permütasyondan
çıkarılıp raporlanacak.

**Ekonomik eşik:** üst-alt üçte bir farkı, çift yönlü **%0,20** işlem
maliyetinin altındaysa sonuç, bandın neresinde olursa olsun pratik olarak
ölüdür.

## Zorunlu ek ölçüm — ayrıştırma

Aile eşiğini geçen **her** özellik için, sonucu raporlamadan önce
[us-earnings-surprise-result.md](us-earnings-surprise-result.md) ve
[us-guidance-forecast-result.md](us-guidance-forecast-result.md)'deki
ayrıştırma koşulur: özelliğin **kendi geçmişinden tahmin edilebilen** kısmı ile
**kalıntısı** ayrı ayrı test edilir.

Gerekçe: iki bağımsız ölçümde, tahmin edilebilir kısım sıfır kazandırdı. Bir
özelliğin getiriyi sıralaması, o sıralamanın **fiyatlanmamış** olduğu anlamına
gelmez. Bu adım atlanırsa sonuç eksiktir.

## Karar kuralı

1. **Bileşik (D1) aile eşiğini geçer ve fark > %0,20** → mekanik aile sinyal
   üretiyor. Sonraki adım: ayrıştırma + portföy kuralı, kendi ön kaydıyla.
2. **Bileşik geçmez** → aile düzeyinde sinyal yok. Tek tek geçen özellikler
   **başlangıç noktası** olarak raporlanır, ağırlıklar sonradan ayarlanmaz.
3. **Geçen ama farkı %0,20 altında** → istatistiksel var, pratik ölü.
4. Herhangi bir özellik geçer ama **ayrıştırmada kalıntısı sıfır** çıkarsa →
   fiyatlanmış, kullanılamaz.

## Önceden reddedilenler

- Ufuk taraması yok: yalnız 21 seans.
- Eşik/kesme noktası aranmaz; ham sıralama.
- Sektör, büyüklük, dönem kırılımı yok.
- Bileşiğin ağırlıkları sonuç görüldükten sonra değiştirilmez.
- Kapsama düşük çıkan özellik telafi edilmez; "ölçülemedi" olarak raporlanır.
- Negatif sonuç, özellik tanımı değiştirilerek yeniden koşulmaz.

## Bilinen sınırlar, şimdiden

- 60 şirket (S&P 500 fiyat defterimiz yok; yalnız bu 60'ın donmuş defteri var).
- 2020-2026, ABD büyük sermaye.
- Finansal artifact kapsaması özellik başına değişecek; ivme hesabı **üç
  ardışık dönem** gerektirdiği için B ve C ailelerinde kayıp beklenir ve
  filtre muhasebesi raporlanır.
