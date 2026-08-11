# İleriye dönük tahmin defteri

**Neden bu defter var.** [us-llm-contamination-finding.md](us-llm-contamination-finding.md)
geçmişe dönük LLM tahmin testinin bu evrende yapılamadığını ölçtü: her iki model
de bu şirketleri 2026'ya kadar biliyor, ve anonimleştirme çalışmıyor çünkü
okunması istenen içerik kimliği veren içeriktir.

Geriye tek temiz yol kaldı: **henüz gerçekleşmemiş bir olayı tahmin etmek.**
Kontaminasyon yapısal olarak imkânsız — model, olmamış bir şeyi hatırlayamaz.

Bu defterin tek işi tahminleri **gerçekleşmeden önce** kayda geçirmek. Git'e
girmesi tarih damgasıdır; sonradan düzeltilemez.

## Yanında tutulan ikinci kayıt — konsensüs vintage'ı

**2026-08-07'den itibaren** her tahminle birlikte analist konsensüsünün o
günkü hâli de kaydediliyor: `data/consensus/snapshot-YYYY-MM-DD.json`.

**Bir düzeltme.** Daha önce bu belgede ve
[us-expectation-price-divergence-preregistration.md](us-expectation-price-divergence-preregistration.md)'de
"konsensüsün tarihsel vintage'ı ücretsiz elde edilemiyor" yazmıştım. Bu **kısmen
yanlıştı**: Yahoo'nun `eps_trend` alanı 90 günlük izi veriyor.

```
DELL, FY2027 EPS konsensusu
  current 18,41   7g 18,38   30g 18,37   60g 18,32   90g 12,98
```

Uzun tarihsel panel hâlâ kurulamıyor (90 günden geriye gitmiyor), dolayısıyla
o belgelerdeki **kararlar değişmiyor**. Değişen şu: bugünden itibaren haftalık
snapshot alınırsa gerçek bir vintage paneli birikir, ve bu ancak başlarsak
birikir.

Her snapshot şunları taşır: kazanç ve gelir konsensüsü (ortalama, düşük,
yüksek, analist sayısı — yani **dağılım**), 7/30/60/90 günlük EPS revizyon izi,
son 7/30 gündeki yukarı-aşağı revizyon sayıları, fiyat hedefleri.

Bu, senin gündemindeki iki aileyi ileriye dönük test edilebilir kılıyor:
**analyst revisions** ve **estimate dispersion**. İkisi de "veri yok" diye
kapatılmıştı.

Snapshot dosyaları **yeniden üretilemez** — yarın bugünün konsensüsü hiçbir
yerden alınamaz — bu yüzden repoya girer ve değiştirilmez.

## Kayıt biçimi

Her tahmin şunları taşır: tarih, model, tahmin, güven, ve **çözüm ölçütü** —
neyin doğru sayılacağı ve ne zaman bakılacağı. Sonuç geldiğinde aynı satıra
işlenir, tahmin **değiştirilmez**.

---

## 1 — ABT, 2026 üçüncü çeyrek açıklaması

**Kayıt tarihi:** 2026-08-07
**Bilinen son durum:** 2026-07-16 açıklaması, FY2026 yönlendirmesi
$5,45 – $5,60 (orta nokta **5,525**)
**Çözüm:** Abbott'ın Ekim 2026'daki Item 2.02 8-K'sındaki FY2026 düzeltilmiş
seyreltilmiş EPS yönlendirmesinin orta noktası eksi 5,525.
**Girdi:** yalnız 2026-07-16 ve öncesi (yönlendirme geçmişi + üç FY2026
bülteninin yönlendirme/görünüm bölümleri, 5.861 karakter)

| kaynak | yön | orta nokta değişimi | ima edilen aralık | güven |
|---|---|---|---|---|
| **agy** (gemini-3.6-flash-high) | RAISE | **+0,025** | $5,50 – $5,60 | 8/10 |
| **claude** (opus) | RAISE | **+0,025** | $5,50 – $5,60 | 6/10 |
| **mekanik taban** (son değişimin tekrarı) | RAISE | **+0,045** | — | — |

**Gerçekleşen:** _(Ekim 2026'da doldurulacak)_

### Not edilecek iki şey

1. **İki bağımsız model aynı sayıda birleşti** ve ikisi de aynı aralığı
   (`$5,50 – $5,60`) verdi. Bu bir doğruluk kanıtı değil — aynı girdiden aynı
   çıkarımı yapmış olabilirler — ama tesadüf de değil.
2. **İkisi de mekanik tabandan AYRIŞIYOR.** Taban son değişimin tekrarını
   (+0,045) söylerken modeller yarısını (+0,025) söylüyor. Ayrışmanın yönü
   doğru çıkarsa bu, modellerin geçmiş ekstrapolasyonunun ötesinde bir şey
   okuduğunun ilk işareti olur.

### Tasarım değişikliği — 2026-08-07: yalnız agy

Bu ilk giriş iki modelden alındı ve ikisinin aynı sayıda buluşması kayda
geçirildi. **Sonraki girişler yalnız `agy` ile yapılacak**, çünkü claude
kotası tükendi.

Kaybedilen şey, bağımsız bir çapraz kontroldür ve bu bir eksiktir: iki model
aynı girdiden aynı çıkarımı yapmış olabilirdi, ama farklı çıkmaları da
bilgilendirici olurdu. Tek modelle bunu göremeyiz.

Kaybedilmeyen şey: mekanik taban her tahminle **aynı anda** kaydediliyor, yani
karşılaştırma noktası sonradan seçilmiyor. Asıl ölçüm bu.

### Bu tek gözlemin ne olduğu ve ne olmadığı

Bir gözlem hiçbir şey kanıtlamaz. Üçü de doğru çıkabilir, üçü de yanlış. Tek
değeri, **temiz olması** — ve temiz gözlemlerin biriktiği tek yer burası.

Ölçülebilir bir sonuç için bu deftere düzenli ekleme gerekir. Evrenin tamamı
(58 şirket) için aynı tahminler bugün kaydedilirse, Ekim-Kasım 2026'da **~58
temiz gözlem** olur — yani "yıllar" değil, bir çeyrek.

---

## 2 — S&P 500 toplu kayıt, 2026-08-07

**165 tahmin**, `us/guidance/_forward/predictions-2026-08-07.jsonl`.
Model `gemini-3.6-flash-high`. Her satırda tahminle **aynı anda** kaydedilen
mekanik taban (son yönlendirme değişiminin tekrarı) var.

| | |
|---|---|
| tahmin | 165 |
| yön dağılımı | RAISE 107, UNCHANGED 55, **LOWER 3** |
| tahmin medyanı | +0,050 |
| mekanik taban medyanı | +0,050 |
| tahmin ortalaması | +0,216 |
| taban ortalaması | +0,138 |

197 şirket "yönlendirme geçmişi yetersiz" diye atlandı (üç noktadan az).

### Şimdiden not edilmesi gerekenler

**1. Taban oranı sorunu.** Tahminlerin **%65'i RAISE**. Yönlendirme
revizyonları zaten yukarı ağırlıklıysa, "hep yükseltir" diyen bir model de
yüksek isabet tutturur. Bu yüzden puanlamada asıl ölçüt **yön isabeti değil,
sıralama gücü** (gerçekleşen değişimle rank korelasyonu) olacak. Şimdi
yazılıyor ki Ekim'de sonuç görülüp uydurulmasın.

**2. Bir gözlemimi düzeltiyorum.** ABT ve DELL'e bakıp "model her seferinde
mekanik tabandan daha temkinli" demiştim. 165 tahminde tabandan küçük tahmin
edenlerin oranı **84/165 = %51** — yazı tura. **İki gözlemden desen çıkarmışım
ve yoktu.**

**3. LOWER yalnız 3.** Model neredeyse hiç aşağı revizyon öngörmüyor. Gerçekte
aşağı revizyonlar bundan sık olacaksa, model onları sistematik olarak
kaçıracak — ve asıl para orada olabilir.

### ONEMLI DUZELTME (2026-08-07): tahminler WEB ERISIMLI bir modelden

`agy --dangerously-skip-permissions` arac kullanimini otomatik onayliyor ve
`gemini-3.6-flash-high` bu cagrilarda **web aramasi yapabiliyordu**. Dogrudan
soruldugunda modelin arama yaptigi ve bugunun tarihini bildigi olculdu.

**Tahminlerin gecerliligi bozulmaz:** hedef olaylar henuz gerceklesmedi, yani
aranacak bir cevap yok.

**Ama iddia degisir.** Kayittaki 165 tahmin, "yonlendirme gecmisinden akil
yuruten bir model"in degil, **guncel haber, analist yorumu ve konsensuse
erisimi olan** bir modelin tahminleridir. Ekim puanlamasinda bu boyle
raporlanacak ve mekanik tabanla karsilastirma bu isikta okunacak.

Bir sonraki toplu kayitta iki surum alinmali: **arama serbest** ve **arama
yasakli**. Ikisinin farki, "web erisimi bu iste ne katiyor" sorusunu dogrudan
olcer.

### Puanlama planı (Ekim-Kasım)

Her şirketin bir sonraki Item 2.02 açıklaması geldiğinde:

1. Gerçekleşen yönlendirme değişimi hesaplanır
2. Üç sıralama karşılaştırılır: **agy**, **mekanik taban**, **analist
   konsensüsü** (2026-08-07 snapshot'ından — o da bugün kaydedildi)
3. Ölçüt: gerçekleşenle rank korelasyonu, kümelenmiş permütasyon, null'ın
   merkezine göre t
4. Kontaminasyon kontrolü: sürekli değerlerde tam isabet oranı

