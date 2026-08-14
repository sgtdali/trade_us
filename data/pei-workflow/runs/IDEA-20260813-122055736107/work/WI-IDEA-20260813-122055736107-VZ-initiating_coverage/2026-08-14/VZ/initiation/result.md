# Verizon Communications (VZ) — İlk Kapsama Raporu

| Alan | Sonuç |
|---|---|
| Yatırım postürü | **İzleme listesi / kanıt bekle** |
| Yeni pozisyon | **Başlatma** |
| Mevcut pozisyon | **Tut; artırma** |
| İç hedef fiyat | **Yok — sermaye getirisi kapısı geçilmedi** |
| Fiyat | 48,22 $ — 13 Ağustos 2026 |
| Piyasa değeri | 200,34 milyar $ |
| Zaman ufku | 3–18 ay; haftalık izleme, aylık karar |
| Kanıt güveni | Raporlanmış verilerde orta-yüksek |
| Underwriting hazırlığı | Düşük / ön çalışma |

Finansal tablolar 30 Haziran 2026 dönem sonuna, konsensüs ve piyasa verileri 13 Ağustos 2026’ya aittir. Temel sayısal kaynak [P1 — pack.json](</C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/runs/IDEA-20260813-122055736107/work/WI-IDEA-20260813-122055736107-VZ-initiating_coverage/2026-08-14/VZ/initiation/pack.json>)’dır.

## PM kararı

VZ’nin operasyonel dönüşümü gerçek sinyaller veriyor: müşteri kaybı düştü, telefon ve genişbant net eklemeleri toparlandı, maliyet disiplini iyileşti ve yönetim 2026 rehberliğini yükseltti. Ancak “dönüşüm başladı” görüşü artık farklılaştırılmış bir tez değil; hisse son bir ayda %12,58 yükselmiş ve olumlu EPS revizyonları oluşmuş durumda.

Asıl yatırım eşiği, bu iyileşmenin düşük cihaz yenileme hacmi ve geçici çalışma sermayesi desteğinden bağımsız biçimde serbest nakit akışına, borç azalmasına ve sermaye maliyetinin üzerinde getiririye dönüşmesidir. Frontier, fiber ve AI Connect yatırımlarının after-financing getirileri henüz gösterilmediği için olumlu sahiplik sonucu ya da savunulabilir hedef fiyat bulunmuyor.

## Tezin üç ayağı

### 1. Müşteri ekonomisi iyileşiyor, fakat kanıt dönemi kısa

Verizon’ın resmi ikinci çeyrek açıklamasında:

- Mobility ve broadband hizmet geliri 23,4 milyar $, büyüme %2,8.
- Postpaid telefon net ekleme 184 bin.
- Genişbant net ekleme 348 bin; bunun 193 bini FWA, 155 bini fiber.
- Toplam genişbant bağlantısı 17,1 milyon.
- Düzeltilmiş FAVÖK 13,7 milyar $ ve marj %40,1.
- H1 serbest nakit akışı 10,2 milyar $ olarak raporlandı.

Bunlar `fact_source_reported` niteliğindedir. [Verizon 2Ç26 sonuçları](https://www.verizon.com/about/news/verizon-delivers-record-2q26-results)

Tüketici postpaid telefon churn’ü ikinci çeyrekte %0,84’e, toplam postpaid telefon churn’ü %0,92’ye indi. Yönetim, müşteri edinme maliyetinin %15 ve elde tutma maliyetinin %17 düştüğünü; ancak yeni tekliflerin yalnızca yaklaşık 40 gündür piyasada olduğunu belirtiyor. Bu nedenle dayanıklılık henüz kanıtlanmış değildir (`issuer_management_claim`). [2Ç26 konferans görüşmesi](https://www.verizon.com/about/file/78235/download?token=5HAlztXV)

Ürün karması da değişiyor:

| Net ekleme | 4Ç25 | 1Ç26 | 2Ç26 | Okuma |
|---|---:|---:|---:|---|
| FWA | 319 bin | 214 bin | 193 bin | Yavaşlama |
| Fiber | 67 bin | 127 bin | 155 bin | Güçlü ivmelenme |

Bu geçiş, fiber yakınsaması açısından olumlu; fakat fiberin sermaye yoğunluğu daha yüksek. Net ekleme başarısının proje bazlı nakit getirisine dönüştüğü henüz gösterilmedi. [2Ç26 finansal ve operasyonel bilgiler](https://www.verizon.com/about/file/78231/download?token=uQv0FBgv)

### 2. Nakit akışı güçlü görünüyor; kalitesi ve kullanım öncelikleri belirsiz

Pack’in H1 2026/H1 2025 karşılaştırması:

| Gösterge | Değişim / seviye | Kanıt etiketi |
|---|---:|---|
| Gelir büyümesi | %1,0 | `fact_provider_standardized` |
| Faaliyet kârı büyümesi | -%4,5 | `fact_provider_standardized` |
| Net kâr büyümesi | -%10,0 | `fact_provider_standardized` |
| Operasyonel nakit akışı büyümesi | %9,9 | `fact_provider_standardized` |
| Faaliyet marjı | %22,45 | `fact_provider_standardized` |
| Net marj | %13,24 | `fact_provider_standardized` |
| OCF/net kâr | 2,03x | `derived_by_pack` |
| ROIC | %6,67 | `derived_by_pack` |

Önemli karşılaştırılabilirlik uyarısı: Frontier işlemi 20 Ocak 2026’da tamamlandı. H1 2026 Frontier’ı konsolide ederken H1 2025 etmiyor; dolayısıyla pack büyümeleri organik veya like-for-like değildir. Pack’in sayıları değiştirilmemiştir, ancak kapsam farkı nedeniyle bunlara saf operasyonel büyüme olarak güvenilemez. İşlem yaklaşık 9,4 milyar $ net nakit ve 12,9 milyar $ üstlenilen borçla, toplam yaklaşık 22,3 milyar $ bedel üzerinden gerçekleşti. [SEC kapanış 8-K’sı](https://www.sec.gov/Archives/edgar/data/732712/000119312526016059/d198618d8k.htm), [Verizon 2025 10-K](https://www.sec.gov/Archives/edgar/data/732712/000073271226000007/vz-20251231.htm)

Yönetimin 2026 beklentileri:

- Mobility ve broadband hizmet geliri büyümesi: %2,5–%3,0.
- Düzeltilmiş EPS: 4,99–5,04 $.
- Serbest nakit akışı: 21,94–22,14 milyar $.
- Capex: 16,0–16,5 milyar $.
- Hisse geri alımı: 4,5 milyar $’a kadar.

Bununla birlikte CFO, H1 nakit akışı iyileşmesinin bir bölümünün düşük cihaz yenileme hacmine bağlı çalışma sermayesi avantajından geldiğini belirtti. Sonbahar promosyonları ve upgrade hacmi normale döndüğünde bu fayda geri dönebilir.

### 3. Değerleme ucuzluk değil, kısmi dönüşüm fiyatlıyor

Pack’in 13 Ağustos 2026 değerlemesi:

- P/E: 12,39x.
- Earnings yield: %8,07.
- Lease hariç EV/raporlanan faaliyet kârı: 12,80x.
- Parent FCF yield: `unavailable`.
- EV/issuer EBITDA: `unavailable`.

P/E paydası pack’te açık biçimde GAAP/adjusted olarak etiketlenmiyor. İkinci çeyrekte GAAP EPS 0,92 $, adjusted EPS 1,30 $ olduğundan, tarihsel P/E ile ileriye dönük adjusted konsensüsü tek seri gibi karşılaştırmak uygun değildir. [Resmi GAAP–non-GAAP köprüsü](https://www.verizon.com/about/file/78233/download?token=glkM72Qa)

## Sermaye yoğun ve finanse edilen büyüme kapısı

### Kapitalizasyon köprüsü

| Kalem | Milyar $ | Baz |
|---|---:|---|
| Piyasa değeri | 200,343 | 13 Ağustos fiyatı |
| Toplam borç | +165,231 | 30 Haziran carrying value |
| Nakit | -1,752 | 30 Haziran |
| **Lease hariç EV** | **363,822** | Pack kanonik EV |
| İşletme kiraları | +23,227 | 30 Haziran |
| **Lease dâhil ekonomik EV** | **387,049** | `derived_calculation` |

Net borç 163,479 milyar $; kiralarla birlikte borç benzeri talepler 186,706 milyar $, yani özsermaye değerinin yaklaşık %93’üdür. Frontier bedeli 30 Haziran bilançosuna zaten yansıdığı için EV köprüsüne tekrar eklenmemiştir.

Pack’in dönem sonu adi hisse sayısıyla uyumlu ima edilen pay sayısı yaklaşık 4,155 milyardır. H1 ortalama basic/diluted pay sayıları yaklaşık 4,186/4,190 milyardır; ancak tam dönem sonu fully diluted köprü mevcut değildir. Bu nedenle seyrelme dâhil kesin pro forma EV verilemiyor.

Borç göstergeleri:

- H1 faiz gideri 3,925 milyar $, yıllık bazda %20 artış.
- Faaliyet kârı/faiz gideri yaklaşık 3,93x.
- Faiz gideri, faaliyet kârının yaklaşık %25,5’i.
- Resmi kredi notları Moody’s Baa1, S&P BBB+ ve Fitch A-, görünümler stabil.
- Resmi borç çizelgesindeki 170,060 milyar $ par değer ile pack’teki 165,231 milyar $ carrying value farklı bazlardır; sayı çatışması değildir. [Verizon sabit getirili yatırımcı sayfası](https://www.verizon.com/about/investors/fixed-income), [30 Haziran borç portföyü](https://www.verizon.com/about/sites/default/files/Verizon-IR-debt-portfolio-63026.pdf)

### Basitleştirilmiş nakit tahsis testi

Mevcut 0,7075 $ çeyreklik temettü korunursa yıllıklandırılmış temettü yaklaşık 11,76 milyar $ ve belirtilen temettü getirisi yaklaşık %5,87 olur. [Verizon temettü geçmişi](https://www.verizon.com/about/investors/dividend-history)

| Basitleştirilmiş 2026 senaryosu | Milyar $ |
|---|---:|
| FCF rehberi | 21,94–22,14 |
| Yıllıklandırılmış temettü | (11,76) |
| Azami geri alım | (4,50) |
| Kalan | **5,68–5,88** |
| 3,2 milyar $ spektrum ödemesi de aynı dönemde yapılırsa | **2,48–2,68** |

Bu bir tahmin değildir; `assumption_inferred` duyarlılığıdır. Temettünün korunmasını, geri alımın tamamen yapılmasını ve spektrum ödemesinin aynı nakit havuzundan çıkmasını varsayar. Çalışma sermayesi, zamanlama ve işlem muhasebesi normalize edilmemiştir.

### Kapının geçmeme nedenleri

Aşağıdaki kanıtlar eksiktir:

- Bakım ve büyüme capex ayrımı.
- Normalleştirilmiş parent-attributed FCF köprüsü.
- Frontier standalone FAVÖK/FCF, entegrasyon maliyeti ve acquisition ROIC.
- Fiber ve AI Connect için yatırım, kullanım, marj, geri ödeme süresi ve proje ROIC’i.
- WACC ve ROIC–WACC spread’i.
- Vade/coupon bazlı tam refinansman modeli.
- Lease-adjusted tutarlı kazanç paydası.
- Dönem sonu fully diluted pay köprüsü.
- Emeklilik ve diğer borç benzeri taleplerin tam normalizasyonu.

Sonuç olarak **Capital-Intensive And Financed Growth Gate geçmemektedir**.

## Konsensüs köprüsü

| Dönem | Gelir | Büyüme | EPS | Büyüme |
|---|---:|---:|---:|---:|
| 2026 | 140,91 milyar $ | %1,97 | 5,012 $ | %6,42 |
| 2027 | 143,59 milyar $ | %1,90 | 5,280 $ | %5,35 |

Bunlar 13 Ağustos 2026 Yahoo/yfinance sokak konsensüsüdür (`estimate_consensus`). EPS bazının GAAP/adjusted tanımı metadata’da açık değildir; şirketin 4,99–5,04 $ adjusted rehberine yakınlığı nedeniyle adjusted olması muhtemeldir, fakat bu yalnızca çıkarımdır.

30 günlük revizyonlar genel olarak olumlu olsa da cari yıl tahmini son yedi günde hafifçe aşağı gelmiştir. Büyük bir yakın dönem “beat” beklentisi kurmak için yeterli ayrışma yoktur.

## Emsal değerleme

Emsal lensleri ayrı tutulmuştur; tek bir birleşik medyan oluşturulmamıştır.

| Lens | P/E | EV/faaliyet kârı | ROIC | Yorum |
|---|---:|---:|---:|---|
| **VZ** | 12,39x | 12,80x | %6,67 | Kısmi dönüşüm fiyatlıyor |
| T — entegre telekom | 7,81x | 11,86x | %5,95 | VZ EV lensinde yaklaşık %7,9 primli |
| TMUS — kablosuz kalite | 18,63x | unavailable | %8,61 | VZ büyüme/kalite iskontolu |
| CHTR/CMCSA — yakınsama | 6,04x | 9,30x | %6,89 | Daha düşük büyüme ve farklı sermaye yapısı |

VZ’nin TMUS’a göre P/E iskontosu yaklaşık %33,5’tir; fakat TMUS’un daha yüksek büyüme ve ROIC’i dikkate alındığında bu otomatik ucuzluk kanıtı değildir. T’ye göre EV/faaliyet kârı primi ise dönüşümün bir bölümünün zaten fiyatlandığını düşündürüyor.

Sokak hedefleri 44–71 $, ortalama 51,56 $ ve medyan 51 $’dır. Cari fiyata göre ortalama yalnızca yaklaşık %6,9, medyan %5,8 yükseliş ima eder. Bunlar konsensüs bağlamıdır; iç hedef fiyat değildir.

### Mekanik değerleme duyarlılığı

Faaliyet kârı, net borç ve pay sayısı sabit tutularak:

| Lease hariç EV/faaliyet kârı | İma edilen fiyat | 48,22 $’a göre |
|---:|---:|---:|
| 11,86x — T benzeri | 41,80 $ | -%13,3 |
| 12,80x — mevcut | 48,22 $ | — |
| 13,50x — koşullu rerating | 53,03 $ | +%10,0 |

Bu tablo hedef fiyat değildir. Kiralar, spektrum ödemesi, seyrelme, kazanç değişimi ve finansman maliyeti modellenmediğinden yalnızca çoklu duyarlılığını gösterir.

## Piyasanın tartıştığı konu ve variant görüş

Piyasa artık müşteri kazanımlarının döndüğünü ve fiyat tekliflerinin işe yaradığını kabul ediyor. Bağımsız yorum da indirimlerin büyümeyi canlandırdığı, fakat henüz belirgin bir fiyat savaşını tetiklemediği yönünde. [Morningstar yorumu](https://www.morningstar.com/stocks/verizon-earnings-price-cuts-have-revived-customer-growth-without-igniting-price-war-thus-far)

Gerçek variant şu sorulardadır:

1. Churn ve müşteri edinme maliyeti iyileşmesi upgrade hacmi normale döndüğünde korunacak mı?
2. Frontier yakınsaması 22,3 milyar $ işlem bedeli ve finansman maliyeti üzerinde değer yaratacak mı?
3. AI Connect sözleşmeleri başlık gelirinden gerçek FCF ve yüksek ROIC’e dönüşecek mi?

Yönetim, Frontier için 2028’e kadar 1 milyar $’ın üzerinde yıllık maliyet sinerjisi ve AI gelirinin 2027’den itibaren anlamlı hale gelmesini bekliyor. Ayrıca Google ile 1 milyar $’ın üzerinde dark-fiber anlaşmasından bahsediyor. Bunlar `issuer_management_claim`; süre, capex, marj ve nakit geri dönüşü açıklanmadığından ana tez değil, yalnızca opsiyonelliktir.

## Senaryolar

| Senaryo | Operasyonel yol | Yatırım sonucu |
|---|---|---|
| Ayı | Churn yeniden yükselir; promosyon ve upgrade maliyetleri döner; FCF rehber altına iner; net borç düşmez | T-benzeri çokluya sıkışma riski; pozitif sahiplik tezi bozulur |
| Baz | 2026 rehberi karşılanır; churn iyileşmesi kısmen korunur; borç yavaş düşer; proje getirileri belirsiz kalır | Mevcut değerleme büyük ölçüde adil; izleme listesi |
| Boğa | Q3/Q4 hizmet geliri hedefleri tutar; FCF çalışma sermayesi desteği olmadan korunur; Frontier/AI getirileri açıklanır; ROIC yükselir | Daha yüksek çoklu mümkün, fakat önce DCF/SOTP ve sermaye köprüsü yeniden kurulmalı |

Sayısal olasılık verilmemiştir; bunu destekleyecek tam model bulunmamaktadır.

## Katalizörler

| Olay | Zaman | Kalite |
|---|---|---|
| Q3 sonuçları | Yahoo tahmini 20 Ekim 2026; şirketçe teyitsiz | Yüksek |
| Q3 yaklaşık %3 ve Q4 yaklaşık %4 hizmet geliri büyümesi | 2H26 | Yüksek; yönetim hedefi |
| Yeni AI Connect anlaşmaları | 2026 sonuna kadar yönetim beklentisi | Düşük-orta; ekonomi açıklanmalı |
| Frontier entegrasyonu ve kaldıraç düşüşü | 2026–2028 | Yüksek, çok çeyrekli |
| BT uluslararası JV kapanışı | 2027, onaylara bağlı | Düşük yakın dönem etkisi |

BT ortak girişimi yaklaşık 4 milyar $ birleşik gelir ve Verizon’dan 625 milyon $ denkleştirme ödemesi öngörüyor; kapanış düzenleyici onaylara bağlıdır. [Verizon–BT ortak girişim duyurusu](https://www.verizon.com/about/news/verizon-bt-group-international-joint-venture)

## Riskler ve tez bozucular

- Tüketici churn’ünün %0,84 seviyesinden yeniden belirgin yükselmesi.
- Net account growth’ün negatife dönmesi veya postpaid/broadband eklemelerinin zayıflaması.
- Q3 yaklaşık %3/Q4 yaklaşık %4 hizmet geliri yolunun kaçırılması.
- FCF’nin 21,94–22,14 milyar $ altında veya capex’in 16,0–16,5 milyar $ üzerinde gerçekleşmesi.
- Düşük upgrade kaynaklı çalışma sermayesi faydasının geri dönmesi.
- Net kaldıraçta 2,5x seviyesinden kalıcı düşüş görülmemesi.
- Frontier sinerjilerinin, cross-sell’in veya proje getirilerinin görünür olmaması.
- AI anlaşmalarının capex, süre, marj ve gelir takvimi olmadan kalması.
- FWA eklemelerindeki yavaşlamanın fiber ivmesiyle telafi edilememesi.
- Faiz oranları ve refinansman maliyeti.
- Lead-kaplı kablolarla ilgili çevresel yükümlülükler. Yatırımcı davasının reddedilmiş olması çevresel/remediasyon riskini ortadan kaldırmaz; şirket olası tutarı ölçememektedir. [SEC risk açıklaması](https://www.sec.gov/Archives/edgar/data/732712/000073271226000007/vz-20251231.htm), [davanın reddi](https://news.bloomberglaw.com/environment-and-energy/verizon-gets-investors-lead-cable-suit-tossed-with-finality)

## İzleme ve aksiyon protokolü

Haftalık izlenecek göstergeler:

- Tüketici ve toplam postpaid telefon churn.
- Gross/net adds ve net account growth.
- Müşteri edinme/elde tutma maliyeti.
- Upgrade hacmi, promosyon ve ARPA.
- Mobility+broadband ve wireless service revenue.
- Fiber/FWA net eklemeleri ve yakınsak müşteri oranı.
- CFO, FCF, capex ve çalışma sermayesi katkısı.
- Net borç/FAVÖK, faiz gideri ve vade finansmanı.
- Frontier entegrasyon gideri, sinerji gerçekleşmesi ve cross-sell.
- AI backlog, kontrat süresi, capex, marj ve nakit getirisi.

Aylık yeniden dengeleme işlem yapma zorunluluğu yaratmaz. Yeni finansal kanıt gelmeden yalnızca fiyat hareketi nedeniyle pozisyon başlatılmamalıdır.

Pozitif yeniden-underwriting için en az bir ek çeyrekte şu üç şart birlikte aranmalıdır:

1. Müşteri ekonomisi ve hizmet geliri hedeflerinin korunması.
2. FCF rehberinin upgrade/çalışma sermayesi normalleşmesine rağmen karşılanması.
3. Net borç düşüşü ile Frontier/fiber/AI yatırım getirilerinin daha görünür hale gelmesi.

ADV yaklaşık 1,17 milyar $ olduğundan perakende ölçeğinde likidite engeli yoktur. Benchmark, short interest, sahiplik, passive pay, crowding ve factor/rates beta verileri bulunmadığından aktif ağırlık veya pozisyon büyüklüğü önerilmemiştir.

## Kaynak ve çatışma kaydı

### Maddi veri çatışmaları

- `instructions.md`, 47,06 $ ile 48,22 $ fiyatlarının -%0,2 ayrıştığını söylüyor; gerçek fark **+%2,46**. Pack’in piyasa değeri ve değerleme alanları 48,22 $ ile matematiksel olarak uyumludur.
- `price_reconciliation.note`, değerlemelerin 47,06 $ kullandığını söylüyor; `valuation`, `valuation_as_of` ve `price_refresh.valuation_at_price_now` alanları 48,22 $’ı kullanıyor. Kaynak-of-truth talimatı gereği kanonik değerleme olarak 13 Ağustos tarihli 48,22 $ ve 12,3883x P/E kullanıldı. Metadata çatışması çözülmemiş olarak kaydedildi.
- Pack’in 165,231 milyar $ borcu carrying value, resmi çizelgedeki 170,060 milyar $ ise par değerdir; bunlar farklı tanımlardır.
- Pack’in transaction filing history alanı işlem durumunu belirlemiyor. Resmi SEC kaynağı Frontier’ın 20 Ocak 2026’da tamamlandığını gösteriyor; bu bir pack çelişkisi değil, web katmanıyla tamamlanan eksik bilgidir.
- Q2 GAAP EPS 0,92 $ ve adjusted EPS 1,30 $ farklı kazanç tanımlarıdır; çatışma değildir.

### Kaynak sicili

| ID | Kaynak | Tür / kullanım |
|---|---|---|
| P1 | [Yerel deterministic pack](</C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/runs/IDEA-20260813-122055736107/work/WI-IDEA-20260813-122055736107-VZ-initiating_coverage/2026-08-14/VZ/initiation/pack.json>) | Birincil sayısal kaynak; 13 Ağustos piyasa/konsensüs, 30 Haziran finansallar |
| S1 | [Verizon 2Ç26 sonuçları](https://www.verizon.com/about/news/verizon-delivers-record-2q26-results) | Şirketçe raporlanan sonuç ve rehberlik |
| S2 | [2Ç26 finansal ve operasyonel ek](https://www.verizon.com/about/file/78231/download?token=uQv0FBgv) | KPI, borç, nakit akışı ve pay sayısı |
| S3 | [2Ç26 konferans görüşmesi](https://www.verizon.com/about/file/78235/download?token=5HAlztXV) | Yönetim yorumu; iddialar ayrıca etiketlendi |
| S4 | [SEC Frontier kapanış 8-K’sı](https://www.sec.gov/Archives/edgar/data/732712/000119312526016059/d198618d8k.htm) | İşlem durumu ve kapanış |
| S5 | [Verizon 2025 10-K](https://www.sec.gov/Archives/edgar/data/732712/000073271226000007/vz-20251231.htm) | İşlem bedeli ve hukuki riskler |
| S6 | [Verizon borç portföyü](https://www.verizon.com/about/sites/default/files/Verizon-IR-debt-portfolio-63026.pdf) | Par değer, vade ve faiz yapısı |
| S7 | [Morningstar](https://www.morningstar.com/stocks/verizon-earnings-price-cuts-have-revived-customer-growth-without-igniting-price-war-thus-far) | İkincil piyasa tartışması |
| S8 | [Bloomberg Law](https://news.bloomberglaw.com/environment-and-energy/verizon-gets-investors-lead-cable-suit-tossed-with-finality) | İkincil hukuki olay |

## Nihai sonuç

**VZ: İzleme listesi / kanıt bekle.**

Şirket operasyonel olarak doğru yönde ilerliyor; ancak 48,22 $ fiyat kısmi dönüşümü zaten yansıtıyor. Net borç, kiralar ve faiz yükü yüksek; mevcut ROIC sermaye maliyetinin üzerinde değer yaratıldığını göstermeye yetmiyor. Frontier, fiber ve AI Connect getirileri ile normalize FCF köprüsü tamamlanmadan olumlu ilk sahiplik kararı veya hedef fiyat verilmemelidir.

Önerilen bir sonraki çalışma, Q3 sonuçlarından sonra `equity-model-update`; bu aşamaya kadar haftalık KPI takibi ve tez kaydıdır. Portföy işlemi öncesinde yatırım komitesi/insan onayı gerekir.