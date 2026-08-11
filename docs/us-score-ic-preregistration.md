# Ön kayıt — LLM puanının kesitsel sıralama gücü (IC)

**Yazıldığı tarih:** 2026-08-05
**Durum:** veri çekilmeden önce yazıldı ve commit edildi.

Bu belge, sonuç görülmeden önce sabitlenmiştir. Değişiklik gerekirse silinmez;
altına tarihli bir ek yazılır. Aynı disiplin
[us-valuation-signal-preregistration.md](us-valuation-signal-preregistration.md)
belgesinde uygulanmış ve orada hipotez elenmişti.

## Hipotez

Bir değerleme raporuna bakıp 0-100 arası çekicilik puanı veren LLM'in puanı,
**aynı ay içindeki diğer şirketlere göre**, sonraki ayın getirisini sıralar.

Ölçülen şey portföy getirisi değildir. "Sepet kazandı mı" sorusu ayda tek
gözlem verir; "yüksek puan verdiklerim düşük puanlılardan iyi mi gitti" sorusu
aynı LLM çağrılarından ayda 60 gözlem verir.

## Neden bu ölçüm

Daha önce ölçüldü (2026-08-05, mevcut 24 şirketlik staples evreni):

| panel | kesit | ort. IC | t | şans bandı | yüzdelik |
|---|---|---|---|---|---|
| score-2025-v1 (0-100) | 6 | −0,032 | −0,41 | −0,141 .. +0,142 | 35,0 |
| event-2025-v1 (0-100) | 14 | −0,012 | −0,22 | −0,090 .. +0,092 | 42,7 |
| wf-2025-v3 (üç kademe) | 15 | −0,042 | −0,73 | −0,087 .. +0,089 | 21,4 |

Üçü de bandın içinde. Ama bu paneller **IC ≥ 0,09'un altındaki hiçbir şeyi
göremezdi** ve gerçek dünyada iyi bir sinyalin IC'si 0,02-0,05 bandındadır.
Yani sonuç "sinyal yok" değil, "0,09'dan büyük sinyal yok"tur. Üstelik üç panel
aynı 15 ayı ve aynı getirileri ölçtüğü için bağımsız üç kanıt da değildir.

## Evren

60 şirket, dört sektör, her sektörde dört alt-tema × üç isim.

- **Consumer Staples (mevcut 24):** değişmedi.
- **Industrials (12):** CAT, DE, CMI / HON, EMR, ETN / MMM, ITW, PH / UNP, CSX, NSC
  *(bkz. Ek 1 — ilk yazılan liste PCAR ve ROK içeriyordu)*
- **Health Care (12):** JNJ, MRK, PFE, ABBV, LLY, BMY / MDT, SYK, BSX, BDX, ABT, ZBH
- **Technology (12):** AAPL, CSCO, DELL, HPQ / MSFT, ORCL, ADBE / TXN, ADI, AVGO, NVDA, AMD

Seçim ölçütleri, sonuca bakılmadan önce: (1) `generic` metrik modülüne uyan
standart kurumsal muhasebe — bankalar, sigorta ve GYO'lar bu yüzden dışarıda;
(2) 2021'den itibaren kesintisiz 10-K/10-Q; (3) staples'tan ve birbirinden
farklı getiri sürücüsü. Enerji ve biyoteknoloji, kronik negatif kâr ve değer
düşüklüğü gürültüsü nedeniyle bilerek dışarıda bırakıldı.

SEC fizibilite taraması 2026-08-05'te koşuldu: 36/36 isim çözüldü ve
2021-01-01'den itibaren en az 5 adet 10-K, 16 adet 10-Q'ya sahip.

## Ölçüm

- Aylık ızgara. Her ayın ilk işlem seansı bilgi kesimi, getiri o seansın
  açılışından bir sonraki ayın aynı noktasına.
- Her ay her şirket için değerleme raporu üretilir ve tek bir LLM çağrısıyla
  0-100 puanlanır. Portföy kurulmaz, alım satım yapılmaz.
- Her ay için Spearman sıralama korelasyonu (puan, sonraki ay getirisi).
- Test istatistiği: 24 ayın ortalama IC'si.
- Anlamlılık, normallik varsayılmadan, **her kesitte puanların permüte
  edilmesiyle** kurulur (10.000 tekrar). Şans bandı budur.

## Karar kuralı — sonuca bakılmadan sabitlendi

1. İlk koşu **24 ay**dır (2024-08 → 2026-07). Bu, gerçekçi bir etki
   büyüklüğüne (IC ≈ 0,05) ulaşan en küçük koşudur.
2. Ortalama IC permütasyon bandının **dışında** kalırsa: sonuç kaydedilir,
   uzatma yapılmaz.
3. Ortalama IC bandın **içinde** kalırsa: 60 aya (2021-08 → 2026-07) uzatılır.
   Gerekçe önceden yazılıdır — 24 ay yalnızca IC ≥ 0,05'i görebilir ve 0,03'lük
   gerçek bir sinyal bu koşuda görünmezdi. Uzatma, sonuç beğenilmediği için
   değil, gücün yetersizliği önceden bilindiği için yapılır.
4. 60 ayda da band içinde kalınırsa hipotez **elenmiş** sayılır. Üçüncü bir
   uzatma yoktur.

## Önceden bildirilen güç

Ölçülen kesit-içi IC standart sapması 24 isimde 0,196 (teorik `1/√(n−1)` =
0,209 ile uyumlu). 60 isimde beklenen 0,122.

| ay | tespit eşiği (2σ) |
|---|---|
| 24 | 0,050 |
| 36 | 0,041 |
| 60 | 0,032 |

## Kapsam dışı

- Portföy kurma, ağırlıklandırma, sektör tahsisi. Sinyal bulunursa ikinci
  aşamada ele alınır (12 pozisyon, sektör başına 3, sektör-nötr).
- Olay tabanlı kadans. Ölçüm aylık ızgaradadır; olay tabanlılık bir işletme
  sorusudur ve maliyeti bu evrende ölçüme uygun değildir (60 isim × ~900 olay
  günü = 54.000 şirket-rapor, ~43 saat).
- İşlem maliyeti, likidite, uygulanabilirlik.

## Bilinen yanlılıklar

- **Hayatta kalma yanlılığı.** Evren bugünkü listeden seçildi; 2021-2026
  arasında borsadan çıkan veya birleşen isimler yok. Sonuç bu yüzden gerçek bir
  stratejinin getirisi değil, yalnızca puanın sıralama gücüdür.
- **Evren seçim yanlılığı.** Sektörler ve isimler benim tarafımdan seçildi.
- **Tek model.** Ölçüm `gemini-3.6-flash-high` içindir; başka bir modelin
  puanı hakkında bir şey söylemez.

---

## Ek 1 — 2026-08-05: Industrials alt-tema dengesizliği

**Değişiklik.** Industrials evreninden PCAR ve ROK çıkarıldı, CSX ve NSC
eklendi. Sektör 3/3/3/3 oldu: Machinery (CAT, DE, CMI), Automation (HON, EMR,
ETN), Diversified (MMM, ITW, PH), Transport (UNP, CSX, NSC).

**Gerekçe.** İlk liste Transport alt-temasında tek isim (UNP) bırakıyordu. Tek
üyeli bir cohort'ta "cohort başına en fazla 2" tavanı hiçbir şey kısıtlamaz;
ayrıca tek isim bir alt-temayı temsil etmez. Bunu ben fark etmedim, evren
dosyalarıyla şirket konfiglerinin ve fiyat eşlemesinin aynı kümeyi tanımlamasını
doğrulayan test yakaladı (`tests/us/test_peers.py`).

**Sonuçtan bağımsızdır.** Bu ekin yazıldığı anda hiçbir puan üretilmemiş, hiçbir
getiri hesaplanmamıştı; değişiklik yalnızca evrenin yapısal dengesiyle ilgilidir.
CSX ve NSC, listedeki diğer isimlerle aynı ölçütlerden geçti (SEC'te çözülüyor,
2021'den itibaren 6 adet 10-K ve 17 adet 10-Q, `generic` modele uyan standart
kurumsal muhasebe) ve adaptörden kırılmadan geçti.

**Güç hesabına etkisi yok:** evren büyüklüğü 60'ta kaldı.

---

## Ek 2 — 2026-08-05: Tekrarlanabilirlik kontrolü (ek çağrı gerektirmez)

**Neden.** Ölçtüğümüz IC, prosedürün kendi gürültüsüyle sınırlıdır. Aynı şirketi
aynı gün iki kez puanladığımızda farklı sonuç alıyorsak, gözlenen IC gerçek
sinyalin **zayıflatılmış** hâlidir ve bu zayıflamanın büyüklüğünü bilmeden
sonucu yorumlayamayız. Bunu sonuç geldikten sonra merak etmek geç olur.

**Fırsat.** `score-2025-v1` koşusu 24 staples şirketini altı ay boyunca
puanlamıştı: aynı model (`gemini-3.6-flash-high`), aynı prompt
(`direct-score.v1.en.md`), aynı kesim tarihleri (2024-12-31, 2025-01-31,
2025-02-28, 2025-03-31, 2025-04-30, 2025-05-30) — hepsi bu çalışmanın aylık
ızgarasıyla birebir örtüşüyor. Bu koşu o altı ayı zaten yeniden puanlayacak,
yani karşılaştırma **144 şirket-ay** için sıfır ek maliyetle elde edilir.

**Girdilerin aynılığı ayrıca doğrulanır.** Değerlemenin kullandığı fiyat ham
kapanıştır ve iki koşunun donmuş defterleri 706 seansın 705'inde aynıdır
(düzeltilmiş kapanışta ~330 seans farklıdır ama fark 8. hanededir ve rapora
girmez). Yine de varsayılmaz: örtüşen 144 şirket-ay için **rapor metinleri
karşılaştırılır** ve tekrarlanabilirlik yalnızca raporu birebir aynı olan
alt küme üzerinden hesaplanır. Böylece ölçülen şey girdi farkı değil, modelin
kendi belirsizliğidir.

**Raporlanacaklar.**
1. Rapor metni birebir aynı olan şirket-ay sayısı (144 üzerinden).
2. O alt kümede puan farkının dağılımı: ortalama ve medyan `|Δpuan|`.
3. Ay içi kesitlerde iki koşu arasındaki Spearman sıralama korelasyonu
   (test–retest güvenilirliği), aylık ve havuzlanmış.
4. Sıralaması ±6 sıradan fazla oynayan isimlerin oranı (24 isimlik kesitte).

**Yoruma etkisi — önceden sabitlenmiştir.** Karar kuralı değişmez: durma kuralı
(Ek yok, ana belgedeki 1-4. maddeler) **ham IC** üzerinden işler. Güvenilirlik
yalnızca yorum için raporlanır ve ikincil, açıkça etiketlenmiş bir tanımlayıcı
olarak `IC / √güvenilirlik` verilir — bu bir **üst sınırdır**, test istatistiği
değildir ve hiçbir kararı tetiklemez.

**Beklenen kısıt.** Kontrol yalnız 24 staples şirketini ve 6 ayı kapsar; yeni 36
şirket ve kalan 18 ay için tekrarlanabilirlik ölçülmez. Staples alt kümesinden
elde edilen güvenilirliğin evrenin tamamı için geçerli olduğu **varsayılmaz**,
sonuçta bu sınır açıkça yazılır.

---

## Ek 3 — 2026-08-06: Kurumsal işlem kaynaklı kapsama boşluğu

**Bulgu.** İlk puanlanan kesitte NVDA 90 ile en yüksek şirketti ve gerekçesi
"F/K 6,76x" diyordu. Gerçek değer ~67x. Kapak sayfası pay adedi 2024-05-24
tarihliydi (bölünme öncesi 2.460.000.000), fiyat ise 2024-07-31 (bölünme
sonrası 117,02) — araya 2024-06-10'daki 10'a 1 bölünme girmişti. Piyasa değeri
288 milyar hesaplanmıştı, gerçeği 2.880 milyar.

**Düzeltme.** Pay adedinin tarihi ile değerleme tarihi arasına bir kurumsal
işlem giriyorsa piyasa değeri kurulmaz. Gerçek bölünme ile spin-off as-of
anında filed veriden ayırt edilemez (bölünme pay adedini çarpar, spin-off
değiştirmez, fiyat beslemesi ikisini de aynı sütuna yazar), bu yüzden hiçbiri
varsayılmaz.

**Kapsama boşluğu — ölçümden önce bildirilir.**

| ay | şirket | araya giren işlem |
|---|---|---|
| 2024-08 | NVDA | 2024-06-10 ×10 |
| 2024-08, 2024-09 | AVGO | 2024-07-15 ×10 |
| 2025-11 … 2026-02 | HON | 2025-10-30 ×1,061 |
| 2026-03 … 2026-05 | BDX | 2026-02-10 ×1,272 |
| 2026-07 | HON | 2026-06-29 ×0,9535 |

Toplam **11 şirket-ay / 1.500 (%0,7)**. Bunların 8'i spin-off olduğu için pay
adedi aslında doğruydu; ayrım as-of anında yapılamadığı için onlar da dışarıda
kaldı. Kesit büyüklüğü o aylarda 60 değil 58-59'dur ve Spearman bunu doğal
olarak taşır.

**Karar kuralına etkisi yok.** Boşluk getiriyle ilişkili değil, kurumsal takvimle
ilişkilidir. İlk ayın 60 puanı bu bulgudan önce üretildiği ve NVDA'nın hatalı
piyasa değeri teknoloji emsal medyanını da kirlettiği için **tamamen silinmiş**,
o ay yeniden puanlanacaktır.

---

## Ek 4 — 2026-08-06: Ufuk testi (sonuç görülmeden yazıldı)

**Yazıldığı an neyin bilindiği.** 1 aylık ufukta 10 kesitlik ara sonuç
görülmüştür (ortalama IC −0,0218, band içinde, %95 üst sınır +0,026). **3 ve 12
aylık ufuklarda hiçbir sonuç hesaplanmamıştır.** Bu ek, o hesap yapılmadan önce
yazılmış ve commit edilmiştir.

**Neden gerekli.** Ölçüm boyunca ileri getiri hep 1 aylıktı. Değerleme ve kalite
sinyallerinin çalıştığı bilinen ufuklar bundan uzundur; bir ay içinde fiyatı
belirleyen şey büyük ölçüde haber akışı ve rotasyondur. Daha somutu: olay
tabanlı sistem, farkında olmadan çeyrek uzunlukta bir sinyale bahis oynuyordu —
14 ayda portföy 3 kez değişti, yani ortalama tutma süresi ~4,7 aydı — ve o
varsayım hiç test edilmedi. Bu ek, sonradan bir ufuk taraması yapıp en iyisini
seçme ihtimalini kapatmak için kuralı önceden sabitler.

**Test edilecek ufuklar: yalnızca ikisi.** 3 ay ve 12 ay. Ara değerler (2, 4, 6,
9) taranmayacaktır; taranırsa en iyisini seçmek kaçınılmaz olur ve seçilen şey
büyük olasılıkla gürültü olur.

**İstatistik.** Ana ölçümle aynı: her kesitte puan ile ileri getirinin Spearman
korelasyonu, kesitler üzerinden ortalama, anlamlılık 10.000 kesit-içi
permütasyondan.

**Örtüşme açıkça bildirilir.** Aylık ızgarada h aylık ufuk h−1 ay örtüşür ve
bağımsız gözlem sayısı yaklaşık `kesit / h`'dir:

| ufuk | 24 aylık koşuda kesit | ~bağımsız gözlem |
|---|---|---|
| 1 ay | 24 | 24 |
| 3 ay | 22 | ~8 |
| 12 ay | 13 | ~2 |

**Karar kuralı — ana kuralı gevşetmez.**

1. Ana durma kuralı (belgenin başındaki 1-4. maddeler) **yalnız 1 aylık ufuk**
   üzerinden işlemeye devam eder. Ufuk sonuçları onu değiştirmez.
2. **12 aylık ufuk 24 aylık veriyle karara giremez.** ~2 bağımsız gözlemle
   hiçbir sonuç anlamlı değildir; yalnız tanımlayıcı olarak raporlanır. Bu,
   sonucu görmeden şimdi yazılmıştır ki çıkan rakam beğenilse de kullanılmasın.
3. **3 aylık ufuk** için karar yalnızca 60 aya uzatılırsa verilir (o zaman ~20
   bağımsız gözlem olur). 24 aylık koşuda 3 aylık sonuç raporlanır ama hipotezi
   ne doğrular ne eler.
4. Ufuk sonuçlarından hiçbiri, 1 aylık ufuktaki bir null'ı geçersiz kılmak için
   kullanılamaz. İkisi ayrı sorulardır: "bir ay sonrasını sıralıyor mu" ve
   "bir çeyrek sonrasını sıralıyor mu".

**Kapsam dışı.** Ufka göre pozisyon büyüklüğü, tutma süresi optimizasyonu,
işlem maliyeti. Bunlar sinyal bulunursa ikinci aşamanın konusudur.

---

## Ek 5 — 2026-08-06: Koşu 21 kesitte sonlandırıldı

**Ne yapıldı.** Ana ölçüm 24 yerine **21 kesitte** durduruldu. Son üç ay
(2026-05, 2026-06, 2026-07) puanlanmadı.

**Neden.** Kota penceresi başına yaklaşık iki ay ilerleyebiliyoruz ve kalan üç ay
en az bir pencere daha, yani beş saatlik bir bekleme daha gerektiriyordu.
Kullanıcı beklemek istemedi.

**Bu bir sonuç seçimi değildir ve bunu ölçtüm.** 21 kesitte ortalama IC −0,0231,
şans bandı ±0,047. Kalan üç ayın sonucu banda taşıyabilmesi için:

| yön | son 3 ayın ortalama IC'si | 21 ayda görülen |
|---|---|---|
| bandın üstüne (pozitif sinyal) | **+0,536** | en yüksek +0,179 |
| bandın altına (negatif sinyal) | −0,214 | en düşük −0,314 |

Pozitif tarafa dönmesi için üç ayın her birinin, şimdiye kadar görülen en yüksek
değerin üç katını üst üste vermesi gerekirdi (teorik tavan ~0,98). Yani
sonlandırma, sonucu değiştirebilecek bir veriyi dışarıda bırakmıyor. Negatife
kayması aritmetik olarak mümkündür, ama o "sinyal var" değil "puan ters
sıralıyor" bulgusu olurdu ve ayrıca raporlanırdı.

**Sonuç nasıl yazılacak.** "24 ayda elendi" değil, **"21 kesitte ölçüldü, %95
üst sınır IC < +0,030, koşu kota nedeniyle erken sonlandırıldı"**. Durma
kuralının 3. maddesi (band içinde kalırsa 60 aya uzat) geçerliliğini korur;
uzatma kararı verilirse 21 değil 60 kesit üzerinden koşulur.

**Ufuk testi (Ek 4) bu ekin yazıldığı anda henüz hesaplanmamıştır.** 3 ve 12
aylık ufuklarda hiçbir rakam görülmemiştir. Ek 4'ün kuralları aynen geçerlidir:
12 aylık ufuk karar tetiklemez, 3 aylık ufuk yalnız 60 aya uzatılırsa karara
girer. 21 kesitte bağımsız gözlem sayısı 3 aylık ufukta ~7, 12 aylıkta ~1'dir.
