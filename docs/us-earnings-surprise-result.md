# Sonuç — kazanç sürprizi bu evrende para kazandırdı mı

**Ön kayıt:** [us-earnings-surprise-preregistration.md](us-earnings-surprise-preregistration.md)
(2026-08-06, hiçbir getiri eşleştirilmeden yazıldı)
**Ölçüm tarihi:** 2026-08-06
**Örneklem:** 21 şirket, 498 açıklama, 2020-05-12 → 2026-05-01, 25 takvim çeyreği

## Bir cümlede

Sürprizler bu evrende fiyatı **gerçekten oynatıyor** (açıklama tepkisi +%2,59
üst-alt üçte bir, şans bandının çok dışında) ama açıklamadan **sonra** girmek
para kazandırmıyor — sürüklenme pozitif değil, hafif negatif. Yani değer,
sürprizi **önceden bilmekte**; sonradan takip etmekte değil.

## Öncül testi — sürprizler fiyatı oynatıyor mu

| | |
|---|---|
| Spearman (sürpriz ↔ tepki getirisi) | **+0,1930** |
| şans bandı (10.000 kümelenmiş permütasyon) | −0,064 .. +0,074 |
| konum | **band dışında** |
| üst üçte bir − alt üçte bir | **+%2,59** (üst +%1,59, alt −%1,00) |

Bu, ön kayıtta karar tetiklemeyen bir test olarak yazıldı ve öyle kaldı. Ama
sorduğu şeyi cevapladı: **evet, konsensüsü aşmak fiyata geçiyor.**

Ayrıca bu, projede ilk kez elde edilen **çalışan bir pozitif kontroldür.**
[us-mechanical-sweep-preregistration.md](us-mechanical-sweep-preregistration.md)
momentumu bile ayırt edemediğimizi göstermişti ve "düzenek hiçbir şey göremiyor
olabilir mi" sorusu açıktı. Aynı fiyat defteri, aynı permütasyon çerçevesi,
açık bir sinyal üretti. Düzenek çalışıyor; aylık kesitsel IC ölçümünün gücü
düşük, olay çalışmasınınki değil.

## Ana test — açıklamadan sonra sürüklenme

| | |
|---|---|
| Spearman | **−0,0911** |
| şans bandı | −0,081 .. +0,058 |
| konum | band dışında, **negatif tarafta** |
| üst üçte bir − alt üçte bir | **−%0,86** (üst −%0,68, alt +%0,18) |
| 63 seans (ikincil, karar vermez) | −0,0447, band içinde, −%0,90 |

Konsensüsü aşan şirketler sonraki ay **geride kalıyor.** Bu, literatürdeki
sürpriz sonrası sürüklenmenin (PEAD) tersidir. Okunuşu: fiyat açıklama günü
aşırı tepki veriyor (+%2,59), sonraki ay bunun yaklaşık üçte birini geri
veriyor.

**Ön kayıt kuralı uygulandı: hipotez düştü.** Kural "band dışında ve pozitif"
diyordu; sonuç band dışında ama negatif. Bu ihtimali önceden yazmamıştım —
kuralın eksikliği bu, ve eksikliği sonradan doldurup sonucu kurtarmıyorum.

**Ters çevirip strateji yapmıyorum.** "Aşanları sat, kalanları al" +%0,86 brüt
görünüyor; sonucu gördükten sonra işaret çevirmek, ön kaydın tam olarak
engellemek için var olduğu şeydir. Kendi ön kaydıyla, kendi örneklem-dışı
dönemiyle test edilmeden bu bir bulgu değildir.

## Sağlamlık — sürpriz yüzdesi küçük paydada patlıyor

Uç olaylara bakınca sorun görüldü: `surprisePercentage`, beklenen kâr sıfıra
yakınken anlamsızlaşıyor. Beklenti −0,01, gerçekleşen +0,01 → "%200 sürpriz".
Uçların neredeyse tamamı tek bir şirketti (CELH) ve bir olayda −%2136'lık
"hayal kırıklığı" o gün **+%8,67** getirmişti — bu bir sinyal değil, ölçüm
bozukluğu.

Aynı test iki alternatif ölçekle tekrarlandı. Ölçülen şey aynı, ölçeği farklı;
karar kuralı değiştirilmedi.

| ölçek | n | tepki ρ | tepki üst-alt | sonraki ay ρ | konum |
|---|---|---|---|---|---|
| ham yüzde (ilk ölçüm) | 498 | +0,1930 | +%2,59 | −0,0911 | dışında |
| fiyata bölünmüş (SUE) | 498 | +0,1733 | +%2,28 | −0,0966 | dışında |
| yüzde, \|beklenti\| ≥ 0,10$ | 486 | +0,1864 | +%2,13 | −0,0764 | **içinde** |

**Tepki sonucu sağlam:** üç ölçekte de bandın dışında, fark %2,1-2,6. CELH
bozukluğu sonucu yaratmıyor.

**Sonraki ayın negatifliği kırılgan:** üç ölçekten birinde bandın içine
düşüyor. Zaten ters çevirip strateji yapılmayacaktı; bu onu ayrıca
gereksizleştiriyor.

## Tavan — mükemmel öngörü ne kadar eder

Tepki farkı (+%2,59) sürprizi **tam bilen** birinin çeyreklik kazancıdır. Kimse
tam bilemez. Sürprizin sıralamasına kontrollü gürültü ekleyip verilen bir tahmin
becerisinde gerçekte ne kadarının yakalandığı ölçüldü:

| tahmin becerisi (Spearman) | çeyrek | yıllık | işlem maliyeti sonrası yıllık |
|---|---|---|---|
| tam bilgi (tavan) | +%2,59 | ~+%10,3 | ~+%9,5 |
| 0,5 | +%1,54 | +%6,2 | +%5,4 |
| 0,4 | +%1,25 | +%5,0 | +%4,2 |
| **0,3** | **+%0,94** | **+%3,8** | **+%3,0** |
| **0,2** | **+%0,61** | **+%2,4** | **+%1,6** |
| 0,1 | +%0,32 | +%1,3 | +%0,5 |

Maliyet çeyrekte bir tam devir, çift yönlü %0,20.

Bu tablo bütün girişimin sınırını çiziyor: **LLM'in sürpriz tahmini konsensüsle
0,2'nin altında korelasyon veriyorsa uğraşmaya değmez.** 0,3 civarı yılda ~%3
net demektir — benchmark'ı yenmek için anlamlı bir başlangıç.

## Mekanik taban ve uçtan uca test — projenin en önemli bulgusu

LLM'e bir şey sormadan önce zorunlu kontrol grubu kuruldu: **geçmiş sürpriz
geçmişi bir sonraki sürprizi tahmin ediyor mu?** Nokta-zaman: her tahmin
yalnız o tarihten önceki açıklamaları kullanır, `|beklenti| ≥ 0,10$` filtresiyle.

| naif kural | olay | rank kor. | konum |
|---|---|---|---|
| son 8 çeyrek ortalaması | 507 | +0,2467 | band dışında |
| **son 4 çeyrek ortalaması** | 507 | **+0,3288** | band dışında |
| son çeyrek | 507 | +0,3142 | band dışında |

Sürpriz **tahmin edilebilir** ve eşiğin (0,20) belirgin biçimde üstünde. Yakalama
eğrisine göre bu yılda ~%3 net demek olmalıydı.

**Olmadı.** Zincir uçtan uca koşulduğunda — geçmişle tahmin et, açıklamadan önce
gir, tepki getirisini al:

| | |
|---|---|
| kontrol: tahmin ↔ gerçekleşen sürpriz | +0,3377 |
| **asıl soru: tahmin ↔ tepki getirisi** | **+0,0155** |
| şans bandı | −0,090 .. +0,053 → **band içinde** |
| üst üçte bir − alt üçte bir | +%0,39 (net +%0,19, yıllık ~+%0,8) |

Ayrıştırma sebebi gösteriyor:

| sürprizin bileşeni | tepkiyle | üst-alt |
|---|---|---|
| **tahmin edilebilir** (geçmiş ortalaması) | +0,0155 | +%0,39 |
| **tahmin edilemeyen** (kalıntı) | **+0,1959** | **+%2,26** |
| ham sürpriz | +0,1978 | +%2,11 |

**Ödemenin tamamı kalıntıda.** Piyasa, geçmişten çıkarılabilen kısmı zaten
kusursuz fiyatlıyor — hangi şirketin alışkanlıkla aştığını herkes biliyor ve o
aşma fiyatı oynatmıyor.

### Bunun yapısal sonucu

Raporumuz geçmiş finansallardan oluşur. Geçmiş finansallar, sürprizin tam olarak
**tahmin edilebilir** bileşenini üretir — yani sıfır kazandıran bileşeni. Para,
geçmişten çıkarılamayan kısımdadır ve o kısım tanımı gereği raporda yoktur.

Bu, [us-score-ic-result.md](us-score-ic-result.md)'nin neden negatif çıktığını da
açıklıyor. 21 ay boyunca modele kamuya açık geçmiş finansalları verip "bu şirket
cazip mi" diye sorduk. Verilen bilgi zaten fiyattaydı. Model kötü okumadı;
okunacak yeni bir şey yoktu.

**Bir LLM'in bu evrende değer üretebilmesi için, geçmiş finansallarda
bulunmayan bilgiye erişmesi gerekir** — yönetim yönlendirmesi, telekonferans
metni, emtia/kur gibi dış değişkenler. Prompt, model veya puanlama ölçeği
değişikliği bu duvarı aşmaz.

### Sınırlar

- "Tahmin edilebilir" tanımı seçilen mekanik modele bağlıdır (son 4 çeyrek
  ortalaması). Daha iyi bir mekanik model sınırı kaydırır ve kalıntıyı küçültür;
  bu, sonucu **güçlendirir**, zayıflatmaz.
- 21 şirket, 479-507 olay, 2020-2026.

## Bu, tasarımın neresini öldürdü, neresini ayakta bıraktı

Önerilen zincir üç aşamalıydı:

- **Aşama 1** (tahmin doğru mu) — **etkilenmedi**, hâlâ ilk adım.
- **Aşama 2** (konsensüsten farklı ve haklı mı) — **ayakta ve artık
  fiyatlandırıldı.** Ödülü +%2,59/çeyrek tavanla, gereken beceri eşiği 0,2 ile
  biliniyor.
- **Aşama 3** (fark getiriyi sıralıyor mu, açıklama sonrası) — **öldü.**
  Sürüklenme yok. İşlem açıklamadan **önce** açılmalı.

Yani tasarım daralıyor ama yönü netleşiyor: değer, açıklama gününün kendisinde.

## Bilinen sınırlar

- **21 şirket, 60 değil.** Alfabetik ilk 21 (AAPL…CSCO); alfabetik sıra
  getiriyle ilişkisiz ama sektörle ilişkisiz değil — bu alt küme sağlık ve
  temel tüketimde yoğun. Alpha Vantage ücretsiz kademesi günde 25 istek ve
  **kotayı IP başına sayıyor**, ikinci bir anahtar açmıyor. Kalan 39, aynı
  kuralla iki günde tamamlanacak ve iki sonuç da raporlanacak.
- **2020-2026.** COVID çöküşü, toparlanma ve faiz rejimi değişimi içeride.
- **Tepki penceresi tek seans.** Kısmi öngörünün gün içinde ne kadarını
  yakalayabileceği ölçülmedi.
- **Konsensüs kalitesi denetlenmedi.** Alpha Vantage'ın `estimatedEPS`'inin
  hangi tarihteki konsensüs olduğu belgelenmiyor; açıklama öncesi olduğu
  varsayılıyor.
- **Kendi iki hatam sonuca dahil değil ama kayda geçer.** İlk koşuda (a)
  `idx_on_or_after` kapsam dışı açıklamaları defterin ilk seansına bağlıyordu
  ve 2000-2019'un tamamı 2020 Mayıs'ının getirisiyle eşleşmişti; (b) piyasa
  bacağı açıklama gününden, hisse bacağı girişten başlıyordu — iki seanslık
  kayma her olaya aynı yönde negatif bindirme yapıyordu (düzeltilmiş
  getirilerin hepsinin −%3 civarı olması bunun işaretiydi). İkisi de
  düzeltildikten sonraki rakamlar yukarıdadır.

## Bundan sonra

Ölçülmesi gereken tek şey kaldı ve eşiği belli: **LLM'in sürpriz tahmininin
gerçekleşen sürprizle rank korelasyonu 0,2'yi geçiyor mu.** Kendi ön kaydını
gerektirir. Mekanik ekstrapolasyon (aynı verinin naif devamı) zorunlu kontrol
grubudur — CAT denemesinde mekanik tahmin 24,55, LLM 21,97, konsensüs 24,72
çıkmıştı ve LLM yönü ters tutturmuştu; tek gözlem hiçbir şey söylemez ama
kontrolün neden zorunlu olduğunu gösterir.
