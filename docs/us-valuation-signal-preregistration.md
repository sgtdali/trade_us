---
status: registered
registered: 2026-08-04
amends: none
amendment_1: 2026-08-04 (veri erisilebilirligi; sonuclara BAKILMADAN yapildi)
amendment_2: 2026-08-04 (veri erisilebilirligi; sonuclara BAKILMADAN yapildi)
amendment_3: 2026-08-05 (Degisiklik 1 geri alindi; sonuclara BAKILMADAN yapildi)
amendment_4: 2026-08-05 (veri erisilebilirligi; sonuclara BAKILMADAN yapildi)
---

# Ön Kayıt — ABD Değerleme Sinyali, 3 Aylık Ufuk

Bu belge **veriye bakılmadan önce** yazılmış ve commit edilmiştir. Amacı, sonuçları
gördükten sonra hipotezi, metriği, parametreyi veya başarı ölçütünü değiştirme
imkânını ortadan kaldırmaktır. Sonuç raporu bu belgeye referans verir; bu belge
sonuç görüldükten sonra değiştirilmez, yalnız `amends` alanıyla yeni bir ön kayıt
açılarak üzerine yazılır.

## Neden bu belge var

2026-08-04'te tamamlanan 15 aylık walk-forward koşusunda (bkz.
[docs/us-market-pipeline.md](us-market-pipeline.md)) LLM karar katmanının bir aylık
ufukta ölçülebilir sinyali bulunamadı: `non-alinmaz` eksi `alinmaz` sepetinin aylık
farkı +%0,01, t=+0,01. Buna karşılık ham rapor metriklerinden `current_ratio`
3 aylık ufukta IC +0,307 verdi ve 15 ayın ilk yarısında seçilip ikinci yarısında
test edildiğinde +3,73 puan taşıdı.

Ancak bu bulgu **aynı 15 ayda 33 test taranarak** elde edildi ve sonuçlar −%25 ile
+%58 arasında savruldu. Bu, teknik analiz backtestlerindeki aşırı uyum (overfitting)
tuzağının tam kendisidir. Aynı oturumda iki kez bu tuzağa düşüldü: `tez_var`
sepetinin +%17,10'u aslında tek hisselik bir portföydü, `net_working_capital`'ın
+%57,88'i mutlak tutar olduğu için büyüklük vekiliydi.

Ayrıca daha önemli bir eksik tespit edildi: projenin **asıl tezi** değerlemedir
("ucuz ve iyi şirket al"), fakat şimdiye kadar test edilen metrikler LLM'e verilen
19 operasyonel orandan ibaretti. Değerleme çarpanları (`val.method.*`) donmuş
artifact'lerde mevcut olmasına rağmen hiç sınanmadı.

## Kullanılmamış veri, tek kullanımlık kaynaktır

`current_ratio` 2025-01 – 2026-03 verisinde seçildi. **2016-2024 dönemine hiç
bakılmadı.** O dönem bu ön kayıt için gerçek örnek-dışı testtir ve bir kez
harcanabilir. "Olmadı, şu parametreyi de deneyelim" turu yapılırsa bu avantaj yok
edilmiş olur ve sonuç artık örnek-dışı sayılamaz.

## Hipotez

> Emsallerine göre düşük değerlemeli şirketler, 3 aylık ufukta yüksek değerlemeli
> olanlardan daha iyi getiri sağlar.

Ekonomik mekanizma: fiyat, sahip olunan nakit akışına göre düşükse, beklenen getiri
yüksektir. Değerleme farkının kapanması çeyrekler alır; bir aylık ufuk bu mekanizmayı
göstermek için kısadır (15 aylık koşuda bir aylık ufukta sinyal bulunamaması bu
hipotezle çelişmez).

## Birincil sinyal — tek, önceden seçilmiş

`val.method.earnings_yield.reported_parent`

Birincil sinyal tektir ve sonradan değiştirilmez. Sonuç bu sinyalle raporlanır.

## İkincil sinyaller — ayrıca raporlanır, birincilin yerini almaz

`val.method.fcf_yield.standard_equity`, `val.method.price_to_book.parent_equity`,
`val.method.ev_to_ebit.core`, `current_ratio`

Bunlar keşif amaçlıdır. İçlerinden biri birincilden iyi çıkarsa bu, hipotezin
doğrulandığı anlamına gelmez; yalnız ileride ayrı bir ön kayıtla test edilecek yeni
bir aday olduğu anlamına gelir.

## Kural — parametre taraması yapılmayacak

- Her çeyrek başında sinyale göre sıralama; **üst N = 8** şirket, eşit ağırlık.
- Kontrol: **alt N = 8** (long-short farkı asıl okunacak büyüklüktür; piyasa
  yönünden bağımsızdır).
- Yeniden dengeleme 3 ayda bir, örtüşmeyen dönemler.
- Uygulama fiyatı bir sonraki işlem gününün adjusted open'ı; iki yönlü turnover
  için %0,10 maliyet; nakit üç aylık ABD Hazine oranıyla büyür. (Mevcut backtest
  primitifleriyle aynı: `adjusted_open`, `transaction_cost`, `cash_period_return`,
  `portfolio_period_return`.)
- N, ufuk, eşik, ağırlıklandırma ve maliyet varsayımı **sonuç görüldükten sonra
  değiştirilmeyecektir.**

## Evren ve dönem

- Evren: **23** tüketim malları şirketi. Survivorship ve sektör yoğunlaşması
  biası açıkça kabul edilir; sonuç bu evrenin dışına genellenmez.

  > **Değişiklik 2 (2026-08-04, sonuçlara bakılmadan önce).** BJ evrenden
  > çıkarılmıştır. İki mekanik sebep: (1) Haziran 2018 halka arzı nedeniyle
  > 2019'dan önce hiç 10-K'sı yok, oysa değerleme tabanı yıllık + ara dönem
  > gerektiriyor; (2) 2019 ve 2020 10-K'larının XBRL paketleri beklenen ana
  > belgeyi (`bj-2019...x10k.htm`) içermiyor, dolayısıyla ayrıştırılamıyor.
  > Motor evrenin tamamı için rapor üretemediğinde ayı durdurduğu için BJ tek
  > başına 26 çeyreğin hepsini düşürüyordu. Çıkarma kararı hiçbir getiri veya
  > sinyal incelenmeden verilmiştir. Yön açısından muhafazakârdır: BJ dönem
  > içinde güçlü performans gösteren yeni bir isimdir, dolayısıyla çıkarılması
  > uzun-only sonucu yukarı değil aşağı çeker. Doğru çözüm point-in-time evren
  > (şirketin verisi olduğu tarihte dahil edilmesi) olurdu; motor sabit evren
  > varsaydığı için bu testte uygulanmamış, ayrı bir iş olarak kaydedilmiştir.
- Test dönemi: **2018-Q2 – 2024-Q4** (örnek-dışı), 27 çeyrek.

  > **Değişiklik 4 (2026-08-05, sonuçlara bakılmadan önce).** 2016-Q1 – 2018-Q1
  > arasındaki 9 çeyrek üretilemez ve bu bir kod eksiği değildir: evrendeki bazı
  > şirketlerin (özellikle CELH) o dönemde SEC'e sundukları filing'lerde XBRL
  > paketi hiç bulunmamaktadır — küçük raporlayan şirketler için XBRL o yıllarda
  > zorunlu değildi. On dört ayrı adaptör düzeltmesinden sonra bu dokuz çeyrek
  > değişmeden kaldı; veri fiziken mevcut değil. Fiilî pencere 2018-Q2'de başlar
  > ve 27 çeyrek verir. Hipotez, birincil sinyal, N, ufuk ve başarı ölçütü
  > değişmemiştir; hiçbir getiri veya sinyal incelenmemiştir.

  > **Değişiklik 3 (2026-08-05, sonuçlara bakılmadan önce).** Değişiklik 1 geri
  > alınmış, kayıtlı 2016 başlangıcı geri getirilmiştir. Değişiklik 1'in tek
  > gerekçesi BJ'nin 2018 öncesinde var olmamasıydı; Değişiklik 2 ile BJ zaten
  > evrenden çıkarıldığı için pencereyi kısaltmaya gerek kalmamıştır. Ayrıca
  > inline XBRL öncesi paketleri okuyamayan adaptör düzeltilmiş (bkz. commit
  > 96ee7e2), dolayısıyla 2016-2018 filing'leri artık işlenebilir. Net etki:
  > 23 şirket, 26 yerine **36** çeyrek. Bağımsız dönem sayısı bu testin bağlayıcı
  > kısıtı olduğu için tercih bu yöndedir. Hipotez, birincil sinyal, N, ufuk ve
  > başarı ölçütü değişmemiştir; hiçbir getiri veya sinyal incelenmemiştir.

  > **Değişiklik 1 (2026-08-04, sonuçlara bakılmadan önce).** Ön kayıt 2016-2024
  > diyordu. Fiyat ledger'ı dondurulduğunda 24 şirketlik evrenin 2016'da mevcut
  > olmadığı görüldü: BJ 2018-06-28'de halka arz olmuş, ilk fiyatı o tarihte
  > başlıyor. Evrenin tamamının fiyatlandığı ilk tarih 2018-06-28'dir. Bu nedenle
  > test dönemi 2018-Q3'te başlatılmıştır. Değişiklik yalnız veri
  > erişilebilirliğinden kaynaklanmaktadır; hiçbir getiri, sinyal veya sonuç
  > incelenmeden yapılmıştır ve hipotez, birincil sinyal, N, ufuk ile başarı
  > ölçütü aynen korunmuştur. Bağımsız dönem sayısı 36'dan 26'ya düşmüştür; bu,
  > istatistiksel gücü azaltır ve sonuç raporunda tekrar belirtilecektir.
- 2025-2026 ayrıca ve **açıkça örnek-içi** olarak raporlanır; başarı ölçütüne dahil
  edilmez.

## Başarı ölçütü — önceden tanımlı

Hipotez şu iki koşulun **ikisi birden** sağlanırsa elenmemiş sayılır:

1. 2016-2024'te üst-8 eksi alt-8 farkı pozitif.
2. Bu fark test edilen yılların çoğunda (≥ %60) pozitif — yani tek bir rejime
   yığılmamış.

Sağlanmazsa hipotez elenir ve LLM katmanı bu tez üzerinde daha fazla
çalıştırılmaz.

## Raporlama kuralları

- **Bütün** sinyaller raporlanır, başarısızlar dahil. En iyisini seçip diğerlerini
  saklamak yasaktır.
- Yıl bazında kırılım zorunludur.
- Çoklu karşılaştırma açıkça belirtilir: 5 sinyal test edilmektedir, dolayısıyla
  tek bir t>2 sonucu keşif sayılmaz.
- Pozitif sonuç "strateji bulundu" diye değil, **"hipotez elenmedi"** diye yazılır.

## Bilinen sınırlar (sonuç ne olursa olsun geçerli)

- 24 şirket tek sektörde ve birbirine yüksek korele; ~36 çeyrek nominal gözlem
  verse de etkin bağımsız gözlem sayısı belirgin biçimde daha azdır.
- Evren bugünkü hayatta kalanlardan oluşur.
- Değerleme çarpanları SEC verisinden türetilir; muhasebe politikası farkları
  şirketler arası karşılaştırmayı sınırlar.
- Bu test bir strateji üretmez; yalnız bir hipotezi eler veya elemez.
