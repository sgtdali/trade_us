# Bulgu — LLM bu şirketlerin yönlendirme geçmişini ezbere biliyor

**Tarih:** 2026-08-06
**Kapsam:** Tek şirket (ABT), 18 nokta-zaman tahmini. Bir sonuç değil, bir
**yöntem uyarısı** — ama tasarımı değiştirdiği için ayrı kayda geçiyor.

## Neden bakıldı

[us-guidance-forecast-result.md](us-guidance-forecast-result.md) ödülün
tamamının yönlendirme değişiminin **kalıntısında** olduğunu ölçtü. Sıradaki
soru, bir dil modelinin o kalıntıyı önceden görüp göremediğiydi. Aradığımız şey
artık **pozitif** bir sonuç olduğu için, modelin cevabı zaten bilmesi ihtimali
öldürücü hâle geldi.

## Kaynak daraltması yetmiyor

İlk deneme `nlm notebook query --source-ids` ile sorguyu 2023-07-20'ye kadarki
11 kaynağa daralttı. Model doğru cevabı verdi (+0,04) ve gerekçesinde
**2023-10-18 tarihli belgeyi adıyla andı** — o belge izin verilen kümede
değildi.

Aynı soru, yalnız önceki belgeleri içeren **temiz bir defterde** `UNKNOWN`
cevabını aldı. Yani parametre modeli kısıtlamıyor; kısıtlama defterin
**içeriğiyle** sağlanmalı.

Bu yüzden nokta-zaman disiplini yapısal kuruldu: belgeler kronolojik sırayla
eklenir, her eklemeden sonra bir sonraki açıklama sorulur.

## Ezber, ölçüldü

Yapısal olarak temiz kurulumda bile, **eski dönemlerde** model gerçek sayıları
biliyor.

| dönem | sıfır-olmayan tahmin | **tam isabet** | ortalama \|hata\| |
|---|---|---|---|
| 2024-07-18 ve öncesi | 6 | **5** | 0,095 |
| 2024-07-18 sonrası | 1 | **0** | 0,181 |

Tam isabetler: +0,20 · +0,30 · +0,04 · +0,04 · +0,01.

Sürekli bir dolar değerinde beş tam isabet tahminle açıklanamaz. Model
Abbott'ın yönlendirme geçmişini eğitim verisinden hatırlıyor.

**"UNKNOWN" cevabı beni yanılttı.** Onu bilgisizlik sandım; oysa reddetme
davranışıymış — prompt tahmin yapmaya zorlayınca hafızadan konuşuyor. Bir
modelin "bilmiyorum" demesi, bilmediğinin kanıtı değildir.

Hataların yeri de bunu doğruluyor: en büyük ıskalamalar mali yıl geçişleri
(−0,800 ve +0,160), yani hatırlanacak tek bir revizyon sayısının olmadığı
noktalar.

## İkinci gözlem — temiz pencerede beceri görünmüyor

2024-07 sonrası model neredeyse her seferinde `UNCHANGED` diyor ve gerçek
değişimleri kaçırıyor: +0,480, +0,525, −0,195. Ezberi olmayınca elinde bir şey
kalmıyor gibi görünüyor.

**Bu bir sonuç değildir.** Tek şirket, 7 gözlem, istatistik yok. Yalnızca test
edilmesi gereken hipotezi netleştiriyor.

## Tasarıma etkisi

1. **2024 ortasından önceki dönemler LLM tahmin testinde kullanılamaz.** Ne
   ölçülürse ölçülsün ezberle kirlidir.
2. Kullanılabilir pencere **2024-07 → 2026-07**, ~8 çeyrek. 58 şirkette
   ~400 gözlem — yeterli.
3. Maliyet düştü: yüklemeler aynı (bağlam gerekli), sorgular şirket başına
   ~20'den ~8'e.
4. **Tam isabet oranı kalıcı bir kontrol olarak raporlanacak.** Temiz olduğunu
   varsaydığımız pencerede de sürekli değerlerde tam isabetler görülürse,
   sonuç ne olursa olsun şüphelidir.

## İkinci model — agy, ve durum daha kötü

Aynı nokta-zaman tahmini `agy` (`gemini-3.6-flash-high`) ile tekrarlandı. Orada
nokta-zaman **yapısal olarak** garanti: prompt'u biz kuruyoruz, o tarihten
sonraki hiçbir şey gönderilmiyor.

ABT, sözde temiz pencere (2024-07 sonrası, 8 tahmin):

| | sıfır-olmayan tahmin | tam isabet | ortalama \|hata\| |
|---|---|---|---|
| agy | 3 | **2** | **0,031** |
| NotebookLM | 2 | 1 | 0,158 |

agy'nin ortalama hatası **3,1 sent**. Ve gerekçeleri açık ediyor:

> *"At its next quarterly earnings release **on January 22, 2025**, Abbott is…"*
> — gelecekteki açıklamanın tarihini adıyla veriyor
>
> *"At its next quarterly release in January 2026, Abbott **introduced** initial…"*
> — gelecekteki bir olayı **geçmiş zamanla** anlatıyor

Ayrıca 2025-10-15'te +0,53 dedi, gerçekleşen +0,525 — eşiğin kılpayı dışında
kaldığı için "tam isabet" sayılmadı ama aynı şey.

**agy'nin bilgisi 2026'ya kadar uzanıyor.** NotebookLM'de 2024 ortasında biten
kontaminasyon, agy'de hiç bitmiyor.

## Sonuç: geçmişe dönük LLM tahmin testi bu evrende yapılamaz

Verimiz 2026-07'ye kadar; her iki modelin bilgisi de o aralığa giriyor. Temiz
tarihsel pencere **yok**. Önceki bölümde "2024-07 → 2026-07 kullanılabilir"
demiştim; agy ölçümü bunu **geçersiz kılıyor** ve o plan iptal edilmiştir.

Geriye kalan yollar:

1. **İleriye dönük test** — henüz gerçekleşmemiş açıklamalar. Yapısal olarak
   temiz, ama çeyrekte bir veri.
2. **Ezberlenmemiş evren** — küçük sermaye ya da daha az takip edilen piyasalar.
   Neyin ezberlendiği bilinmiyor; test edilmeden varsayılamaz.
3. **Tahmin dışı kullanım** — kontaminasyonun sonucu değiştirmediği işler.

## Anonimleştirme denendi ve çalışmıyor

Fikir şuydu: şirketi tanıtan her şeyi silersek model ezberine ulaşamaz.
Uygulandı — özel isimler ve segment adları maskelendi (`Entity1`, `Entity2`…),
bütün parasal değerler şirkete özel bir çarpanla ölçeklendi (yüzdeler
korunarak, aksi hâlde ekonomik anlam bozulur), mutlak tarihler dönem
etiketlerine çevrildi.

Model, anonim metinden şirketi **tanıdı**: `Abbott Laboratories | 2024 | 10`.

Ayrıştırma, nerenin sızdırdığını gösterdi:

| gönderilen | cevap |
|---|---|
| yalnız sayılar (ölçeklenmiş yönlendirme geçmişi) | `UNKNOWN \| 0` |
| yalnız metin (isimler maskeli) | `Abbott Laboratories \| 10` |

**Ölçekleme işe yarıyor, maskeleme yaramıyor.** Parmak izi sayılarda değil
anlatıda: iş kollarının bileşimi, "COVID testleri hariç organik büyüme", ürün
hattı kapatma kararı. Özel isimler silinse bile bu anlatı tek bir şirketi
tarif ediyor.

Ve çıkmaz burada: **modelin okumasını istediğimiz bilgi ile şirketi tanıtan
bilgi aynı şeydir.** Anlatıyı silmek sinyali de siler; geriye "sağlam büyüme
bekliyoruz" gibi içeriksiz ifadeler kalır. Daha sert maskeleme teknik olarak
mümkün ama testi anlamsızlaştırır.

Anonimleştirme yolu kapanmıştır. Kapanma gerekçesi spekülasyon değil ölçümdür,
ve maliyeti bir saatti.

## GERI CEKME (2026-08-07, ayni gun) -- agy INTERNETE BAKIYORDU

Yukaridaki "ucuncu model" bolumu ve **2026-08-06 tarihli agy bolumu YANLISTIR.**
Sebep ezber degil, **canli web aramasi.**

### Nasil bulundu

Kullanici sordu: "internetten ariyor olabilir mi?" Bir tutarsizlik zaten
vardi ve gozden kacirmistim -- kesim testinin promptu acikca *"no tools, no
search"* diyordu ve UNKNOWN aliyordu; tahmin promptunda **oyle bir talimat
yoktu** ve tam isabet geliyordu.

Modele dogrudan soruldu:

```
Web araman var mi?              YES
Bu mesajda kullandin mi?        YES
ABT FY2026 yonlendirmesi?       $5,55 - $5,80   (birebir dogru)
Bugunun tarihi?                 2026-08-07      (agirliklardan bilinemez)
```

### Kesin deney

Ayni ABT 2025-10-15 tahmini uc kosulda kosuldu:

| kosul | tahmin | gerceklesen |
|---|---|---|
| A) arama serbest | **+0,52** | +0,525 |
| B) arama yasakli (prompt'ta) | **UNCHANGED 0,00** | +0,525 |
| C) `--dangerously-skip-permissions` YOK | bos cikti (arac onayi bekliyor) | -- |

**Arama engellendiginde model bilmiyor ve yanlis tahmin ediyor.** Cevap
agirliklarda degil.

### Kok sebep: kendi cagri bicimimiz

`agy --dangerously-skip-permissions` **arac kullanimini otomatik onayliyor** ve
biz bu bayragi **butun agy cagrilarinda** kullandik. Istemedigimiz aramalar
sessizce onaylanmis. Bayrak olmadan (kosul C) model arac izni istiyor ve
gozetimsiz kosuda bos donuyor -- yani bayrak zorunluydu ve yan etkisi
fark edilmedi.

`agy --help` cikisinda araclari kapatan bir bayrak yok; tek kaldirac prompt.

### Bunun etkiledigi ve ETKILEMEDIGI sonuclar

**Etkilenen:**

- Bu belgedeki agy bolumleri (2026-08-06 ve 2026-08-07) -- **geri cekildi.**
  agy'nin bilgisinin 2026'ya uzandigi iddiasi yanlisti.
- `docs/us-forward-predictions.md`'deki 165 tahmin: **agy web erisimiyle**
  uretildi. Gelecek olaylar heniz gerceklesmedigi icin cevap sizmasi mumkun
  degil, ama iddia degisiyor: "yonlendirme gecmisinden akil yuruten bir model"
  degil, "**guncel haber ve konsensuse erisimi olan** bir model" tahmin etti.
  Ekim puanlamasinda bu boyle raporlanacak.

**Etkilenmeyen:**

- **Butun mekanik olcumler** (surpriz, yonlendirme, degerleme, cokus, BIST,
  ima edilen beklenti). Hicbirinde LLM yok.
- **Skor-IC null sonucu.** Kontaminasyon pozitif sonucu sisirir, negatifi
  degil; arama olsaydi puanlar daha iyi olurdu, daha kotu degil. Null ayakta.
- **NotebookLM bulgusu** ayri bir arac ve ayri incelenmeli. Dun temiz defterde
  UNKNOWN alinmisti; artimli defterdeki tam isabetlerin kaynagi (ezber mi,
  NotebookLM'in kendi aramasi mi) **bu deneyle cozulmedi** ve acik kaldi.

### Ve tersine acilan kapi

Kosul B gosteriyor ki **arama prompt'la engellenebiliyor**, ve engellendiginde
model gercekten bilmiyor. Bu, kullanicinin ilk sezgisini geri getiriyor:
`gemini-3.1-pro-high` icin **2025-01 sonrasi temiz bir tarihsel pencere
olabilir.**

Ama tek gozlemle karar verilmez ve "arama yapma" yumusak bir talimattir. Bunun
kurulmasi icin gereken sey ayri bir on kayit ve **her cagri icin dogrulama**:
cevabin icinde arama izi var mi, ve tam isabet orani ne. Bu, yeni bir tasarim
sorusudur ve bugun cozulmedi.

## Ucuncu model denendi: dogrudan sorgu testi GECERLI BIR KONTROL DEGIL (2026-08-07)

`gemini-3.1-pro-high` denendi cunku bilgi kesiminin 2024 sonunda bittigi
dusunuluyordu. Oyleyse 2025-01 -> 2026-08 arasi **temiz bir tarihsel pencere**
olurdu ve ileri defteri beklemeden yuzlerce gozlem elde edilirdi.

### Dogrudan sorgu testi siniri keskin gosterdi

agy CLI uzerinden, "yalniz egitim verinden cevapla, bilmiyorsan UNKNOWN de":

| soru | tarih | cevap |
|---|---|---|
| NVDA FQ1 2025 geliri | 2024-05-22 | **$26,0B** dogru |
| NVDA bolunme orani | 2024-05-22 | **10'a 1** dogru |
| AAPL FQ4 2024 net satis | 2024-10-31 | **$94,9B** dogru |
| META Q4 2024 geliri | 2025-01-29 | UNKNOWN |
| NVDA FQ4 2025 geliri | 2025-02-26 | UNKNOWN |
| ADBE FQ1 2025 geliri | 2025-03-12 | UNKNOWN |
| META Q1 2025 geliri | 2025-04-30 | UNKNOWN |
| NVDA FQ1 2026 geliri | 2025-05-28 | UNKNOWN |

**Pozitif kontrol atesledi** -- model bildiginde kurusuna kadar veriyor,
refleksif UNKNOWN demiyor. Test iyi kurulmustu.

### Ama tahmin gorevinde ayni model rakami verdi

Ayni modelle ABT'de nokta-zaman tahmini, yalniz 2025 sonrasi:

```
tahmin tarihi    tahmin  gerceklesen   hata
2025-04-16       +0,050       +0,000   0,050
2025-07-17       +0,020       +0,000   0,020
2025-10-15       +0,525       +0,525   0,000   <-- TAM ISABET
2026-01-22       +0,000       -0,195   0,195
2026-04-16       +0,000       +0,045   0,045
```

**+0,525**, virgulden sonra uc hane, guven **10/10**, ve serideki en buyuk
degisim. Gerekcesinde *"At its next earnings release in January"* diyor.

Bu akil yurutmeyle bulunamaz: 5,675'i tam tutturmak icin Abbott'in FY2026
yonlendirme araliginin orta noktasini bilmek gerekir. "Yaklasik %10 artar" demek
5,68 verir, 5,675 vermez.

### Sonuc: dogrudan sorgu, kesim tarihini OLCMUYOR

Model, *"Meta Q4 2024 geliri neydi"* diye soruldugunda UNKNOWN diyor; *"gelecek
ceyrek yonlendirmeyi ne yapacak"* diye soruldugunda ayni donemin rakamini
veriyor.

Ikisi celiskili degil. **Olgu beyani ile tahmin gorevinde bilgi kullanimi
farkli davranislardir.** Model birincisinde reddediyor, ikincisinde kullaniyor.

Dogrudan sorgu testi -- pozitif kontroluyle birlikte, iyi kurulmus haliyle bile
-- **kesim tarihini degil reddetme sinirini olcer.** Kontaminasyon kontrolu
olarak kullanilamaz.

Bu, asagidaki 8b maddesinin ikinci ve daha guclu ornegidir: dun NotebookLM temiz
defterde UNKNOWN dedi ve zorlaninca hatirladi; bugun baska bir model dogrudan
soruda UNKNOWN dedi ve tahmin gorevinde hatirladi.

**Temiz tarihsel pencere bu modelde de yok.** Ileri defter tek gecerli tasarim
olarak kaliyor.

## Kalici kontrol

Sürekli değerlerde **tam isabet oranı**, bundan sonra her geçmişe dönük LLM
ölçümünden önce koşulur. Ucuz, ve bu gece iki farklı modelde de tek başına
sonucu belirledi.

## Bu bulgunun kendi sınırı

Tek şirket. Kesim noktası ABT'de 2024 ortası görünüyor ama bu tek bir gözlemdir
ve modelin gerçek bilgi kesimi belgelenmiş değildir. Tam koşuda kesim, tam
isabet oranının dönem bazında dağılımıyla **ölçülerek** doğrulanacak, varsayılmayacak.
