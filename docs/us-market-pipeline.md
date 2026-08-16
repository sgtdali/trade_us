---
status: accepted
updated: 2026-08-09
---

# ABD Piyasası SEC Pipeline Tasarımı

> **Yürürlükte (2026-08-16 teyidi).** Veri katmanı tasarımı olduğu gibi
> geçerli. Yeni portföy karar günlüğü bu hattı **değiştirmeden** kullanıyor:
> SEC çekme, XBRL normalizasyonu, değerleme motoru ve `pack.json` üretimi
> aynı kalıyor; yeni sistem bunların çıktısını tüketiyor. Bkz.
> [pei-company-lifecycle-tasarim.md](pei-company-lifecycle-tasarim.md)
> Bölüm 12 (kapsam dışı).

## Amaç ve sınırlar

İlk hedef, ABD merkezli ve US-GAAP kullanan 10-12 standart şirket için ücretsiz
resmî SEC verisinden mevcut kanonik finansal sözleşmeyi üretmek ve mevcut oran,
sinyal, değerleme ve raporlama motorlarını değiştirmeden değerleme raporu almaktır.

- Mevcut BIST komutları, dosya yolları, artifact'ları ve testleri aynı kalır.
- ABD ve BIST akışları birbirinden bağımsız çalıştırılır.
- ABD şirket verileri repo kökündeki `us/` çalışma alanında tutulur.
- Ortak motor kopyalanmaz; yalnız kararlı Python API'leri çağrılır.
- KAP, Google Drive ve NotebookLM ABD pilotunun bağımlılığı değildir.
- İlk pilot banka, sigorta, REIT, holding ve yabancı ihraççıları kapsamaz.
- Belirsiz veri tahmin edilmez; üretim fail-closed durur.

## Dizin ve sahiplik

> **Not (2026-08-11):** Bu bölüm, `us/` bir workspace olarak BIST'in yanında
> yaşadığı `fundamentaltrading` reposu için yazıldı. `trade_us` reposuna
> taşındıktan sonra `us/` sarmalayıcısı kaldırıldı (tüm repo zaten ABD hattı)
> ve paketler `fundamental_pipeline`/`fundamental_pipeline_us` yerine
> `engine`/`adapter` olarak adlandırıldı. Aşağıdaki ağaç bugünkü karşılığı
> gösteriyor; tasarım gerekçesi (neden ayrı bir workspace/motor kopyası
> seçildiği) hâlâ geçerli, sadece yol ve isimler güncel.

```text
config/companies/                 # ABD şirket kimliği ve routing kayıtları
config/sec/                       # CIK ve kanonik metrik eşlemeleri
raw-cache/sec/                    # git dışı, yeniden indirilebilir SEC cache'i
raw/sec-filings/                  # seçilmiş fact'lerin küçük, kalıcı kaynak snapshot'ları
data/                             # kanonik/authored ve generated artifact'lar
src/engine/                       # ortak motor (oran/sinyal/değerleme), vendored kopya
src/adapter/                      # SEC adaptörü ve ABD orkestratörü
tests/us/                         # yalnız adaptör/orkestratör testleri
```

`adapter`, `engine` paketinin açık `data_root`/`root` sözleşmelerini kullanır.

## Veri akışı

1. SEC ticker-CIK listesi ve Submissions API ile 10-K/10-Q accession'ları keşfedilir.
2. `as_of` kesimine göre erişilebilir filing seçilir; gelecekteki filing kullanılmaz.
3. Filing'e ait XBRL ZIP indirilir ve SHA-256 ile yerel cache'e alınır.
4. Arelle ile standart ve filer-extension fact'leri, context, unit, dimension ve
   presentation ilişkileri birlikte okunur.
5. Kanonik metrik eşlemesi önce standart US-GAAP adaylarını, sonra açıkça
   onaylanmış extension eşlemelerini dener.
6. Dönem, birim, kapsam ve filing kimliği doğrulanarak
   `financial-direct.schema.json` sözleşmesi üretilir.
7. En güncel iki 10-K ile son 10-Q birlikte işlenir. 10-Q'nun kendi karşılaştırma
   sütunu ayrı dönem artifact'ına dönüştürülür; böylece ortak motor TTM bazını
   `son FY + güncel YTD - önceki yıl YTD` olarak gerçek dönemlerden kurar.
8. Mevcut ortak motor oranları, sinyalleri ve teknik görünümü üretir;
   değerleme motoru mevcut yöntemleri çalıştırır.
9. SEC filing metnindeki Item 1A bölümü deterministik risk sınıflarına; yıllık
   filing içindeki standart US-GAAP dipnot fact'leri borç/ASC 842 vade, faiz ve
   açıklanmış tahvil para birimi profiline çevrilir.
10. Finansal sonuç tarihinin çevresindeki 8-K HTML exhibit'leri Inline XBRL
   üzerinden taranır. Yalnız tekil ve dönemle eşleşen issuer-reported EBITDA veya
   net-debt APM fact'i kabul edilir; bulunamazsa açıkça `not disclosed` kalır.
11. Yirmi dört şirketlik authored emsal evreni karşılaştırma artifact'larını üretir;
   rapor medyanı ayrıca altışar şirketlik Retail, Beverages, Packaged Food veya
   Household and Personal Care grubuna daraltılır. ABD'ye özel, tamamen İngilizce
   şablon render edilir.

Tek şirketlik uçtan uca komut:

```powershell
$env:SEC_USER_AGENT = "fundamentaltrading-local/0.1 your-email@example.com"
us-pipeline run-company --ticker KO --as-of 2026-08-03 `
  --cutoff-instant 2026-08-03T23:59:59Z --enrich-peers
```

Komut son erişilebilir iki 10-K ile son 10-Q filing'ini işler. En güncel finansal baz,
filing tarihine göre değil rapor dönemi bitiş tarihine göre seçilir; yeni 10-K,
önceki 10-Q'dan daha güncelse raporun `latest_period` ve `fy_period` değerleri
aynı olabilir. SEC User-Agent kullanıcı tarafından gerçek bir iletişim adresiyle
verilir; repoda kimlik bilgisi tutulmaz.

`--enrich-peers`, o tarih için değerleme sonucu bulunan emsal evreni üyelerinin
karşılaştırmalarını yeniler ve raporlarını yeniden üretir. Evrene kaydedilmiş ancak
henüz çalıştırılmamış şirketler atlanır; çalıştırılan ticker emsal evreninde yoksa
komut sessizce eksik rapor üretmek yerine açık hatayla durur.

İlk on şirketlik pilotu ve ardından emsal karşılaştırmalarını tek seferde üretmek için:

```powershell
us-pipeline run-pilot --as-of 2026-08-03 `
  --cutoff-instant 2026-08-03T23:59:59Z
```

`companyfacts` ana finansal kayıt değil, filing keşfi ve bağımsız çapraz kontrol
kaynağıdır. Ana provenance accession'a bağlı tek filing'dir.

## Pay adedi ve piyasa verisi

SEC cover page'deki doğrudan `EntityCommonStockSharesOutstanding`, ekonomik
olarak spot outstanding paydır. Bu değer sahte biçimde `issued_shares` ve
`treasury_shares=0` olarak gösterilmez. Ortak market contract'ına geriye uyumlu
bir `direct_outstanding` alternatifi eklenir; mevcut BIST
`issued_shares - treasury_shares` yolu değişmeden kalır.

Fiyat, mevcut provider arayüzü üzerinden ABD ticker sembolüyle yfinance'dan
alınır. Fiyat ile SEC pay adedinin tarihleri ve hisse sınıfı uyuşmuyorsa market
snapshot üretilmez.

## Drive, NotebookLM ve metinsel veri

SEC arşivi kalıcı kaynak olduğu ve filing başına XBRL paketi küçük olduğu için
Google Drive kullanılmaz. NotebookLM de bu akışın bağımlılığı değildir. Filing-text
adaptörü Item 1A metnini accession'a bağlı kaynak snapshot'ı olarak saklar ve
kanıt bulunan risk kategorilerini deterministik biçimde üretir. Güncel 10-Q'da
maddi yeni risk bölümü yoksa son 10-K risk tabanı açık provenance ile devralınır.

Temel net borç ve borç baskısı XBRL finansal tablolardan hesaplanır. Vade dilimleri,
sabit/değişken faiz ve para birimi kırılımı kaynakta güvenilir biçimde
ayrıştırılamıyorsa tahmin edilmez; raporda kapsam sınırı olarak kalır. Drive veya
NotebookLM ancak ileride bu dipnot ayrıntılarının SEC metin/tablo ayrıştırmasıyla
güvenilir biçimde alınamadığı kanıtlanırsa ayrıca değerlendirilir.

Yıllık dipnot ayrıntıları, güncel rapor bir 10-Q'ya dayanıyorsa son 10-K kaynak
kimliği korunarak güncel borç profiline taşınır; böylece eski dipnot tablosu güncel
çeyrek rakamı gibi sunulmaz. Dönem etiketleri takvim yılı varsaymaz: örneğin COST
`fiscal Q3 2026 YTD (36 weeks) ended May 10, 2026`, SJM ise
`2026 fiscal year ended April 30, 2026` biçiminde gösterilir.

## Güvenilirlik ve hata davranışı

- SEC istekleri tanımlı User-Agent, rate limit ve sınırlı retry ile yapılır.
- Cache yazımı atomiktir; aynı accession/hash tekrarında no-op olur.
- Amendment ve restatement seçimi accession seviyesinde açıkça kaydedilir.
- Birden fazla uygun fact varsa context/statement/period kuralları tek aday
  üretemediği sürece işlem durur.
- Extension eşlemesi ticker'a özel hesaplama kodu değildir; versionlanmış veri
  konfigürasyonudur ve hesap özdeşlikleriyle doğrulanır.
- Ham SEC cache'i kaynak gerçeğidir; generated çıktı yeni girdiye dönüşmez.

## Test stratejisi ve kabul kapısı

1. SEC istemcisi ve cache için ağsız unit testleri.
2. Fact/context seçimi ve extension eşlemesi için küçük accession fixture'ları.
3. Kanonik finansal JSON için schema ve muhasebe özdeşliği testleri.
4. Doğrudan outstanding pay yolu için yeni contract/unit testleri; mevcut BIST
   issued-minus-treasury testlerinin hiçbiri değiştirilmez.
5. USD + US_GAAP uçtan uca ortak-motor integration testi.
6. Bir gerçek şirket için accession-pinned regression/golden rapor.
7. Pilot genişlemesinde her şirket için veri-kapsam matrisi ve rapor doğrulaması.
8. Son kabul kapısında mevcut tam test suite'i ve ABD testleri birlikte geçer.

## Pilot varsayımları

- Tek kullanıcılı yerel batch çalışma; birkaç dakikalık süre kabul edilebilir.
- Pilot şirketleri USD, US-GAAP, domestic filer ve standard corporate'tır.
- Aynı/benzer sektörden şirketler seçilerek peer karşılaştırması anlamlı tutulur.
- Bir defalık kontrollü extension eşlemesi kabul edilir; sessiz ticker patch'i
  kabul edilmez.
- SEC dışı ücretli veri kullanılmaz.

## Pilot evreni ve doğrulanan çıktı

2026-08-03 kesimi için aşağıdaki 10 şirketin iki 10-K + son 10-Q finansalları,
fundamental analiz artifact'ları, piyasa ve teknik snapshot'ları, değerleme
girdileri, değerleme sonuçları ve İngilizce değerleme raporu uçtan uca üretildi:

`KO`, `PEP`, `MDLZ`, `GIS`, `SJM`, `KHC`, `CL`, `PG`, `WMT`, `COST`.

Pilot seçiminde çoklu ekonomik pay sınıfı veya maddi geçici/imtiyazlı sermaye
köprüsü gerektiren şirketler basit standart şirket akışına zorlanmadı. Bu,
veri eksikliği değil kapsam kapısıdır; pay sınıflarını `treasury=0` gibi bir
varsayımla tek sınıfa indirmek yasaktır.

On raporun tamamında beş boyutlu emsal artifact'ı üretilir; raporda ekonomik
karşılaştırılabilirliği korunabilen Current Ratio ve Earnings Yield işletme modeli
eşleşmiş medyanla gösterilir. Belge kaynaklı riskler ve teknik görünüm de bulunur. Ara
dönemi en güncel finansal baz olan sekiz şirkette gerçek TTM değerleri kullanılır;
`GIS` ve `SJM` için en güncel dönem yıllık olduğundan rapor doğal olarak FY bazlıdır.
Kiralama sunum dili US-GAAP için ASC 842 olarak gösterilir. ABD değerleme raporları
tamamen İngilizcedir; BIST raporları mevcut Türkçe şablonda kalır. İki raporlama
katmanı ekonomik formülleri paylaşır ancak metin/şablon sahipliği ayrıdır.

Evren daha sonra dört dengeli işletme-modeli cohort'una, toplam 24 şirkete
genişletildi:

- Retail: `BJ, COST, DG, KR, TGT, WMT`
- Beverages: `CELH, FIZZ, KDP, KO, MNST, PEP`
- Packaged Food: `CAG, CPB, GIS, KHC, MDLZ, SJM`
- Household and Personal Care: `CHD, CL, CLX, KMB, NWL, PG`

2026-08-03 kesimi için 24 şirketin de İngilizce değerleme raporu üretilmiştir.
Peer medyanı subject şirketi dışarıda bırakır; coverage paydası ise subject dahil
tam matched cohort büyüklüğüdür.

## ABD karar katmanı

Sürekli üretim akışında üç ayrı model çıktısı ve Claude Opus denetimi kullanılmaz.
Şirketin İngilizce değerleme raporu tek başına Codex `gpt-5.6-sol`, `high`
reasoning'e verilir; strict JSON Schema ile alınan sonuç sayısal kanıt kontrolünden
geçirilerek immutable `us/data/decisions/{TICKER}/{AS_OF}/decision.json` kaydına
yazılır. Aynı tarihli kayıt varsa yeniden LLM çağrısı yapılmaz.

```powershell
python -m fundamental_pipeline_us.cli run-decisions --workspace us `
  --as-of 2026-08-03 --tickers BJ COST DG KR TGT WMT --max-workers 3
```

Retail pilotunda BJ, DG ve TGT `sartli`; COST, KR ve WMT `alinmaz` sonucunu aldı.
26 sayısal kanıtın tamamı rapor metninde doğrulandı. Eski çoklu-model ve Opus
çıktıları yalnız karşılaştırma kaydıdır.

Portföy kararı da Codex Sol/high kullanır; en fazla iki eşit %50 pozisyon seçebilir
ve nakit bırakabilir:

```powershell
python -m fundamental_pipeline_us.cli run-portfolio --workspace us `
  --as-of 2026-08-03 --tickers BJ COST DG KR TGT WMT
```

İlk koşu DG %50 + nakit %50 üretti. Ancak `alinmaz` şirketlerden portföy modeline
yalnız tek cümlelik özet verildiği için COST ve KR hakkındaki itirazlar tam kayıt
incelenmeden oluştu. Bu itirazlar çözülmüş yeniden değerlendirme değildir; mevcut
portföy artifact'ının bilinen kapsam sınırıdır. Altı şirketlik cohort ölçeğinde tüm
şirket kararlarını tam kayıtla verme değişikliği henüz uygulanmadı.

Bu kapsam BIST raporuyla ekonomik çekirdek eşitliğini sağlar; ayrıntılı borç vade,
faiz ve para birimi tabloları, şirketin açıkladığı canonical EBITDA mutabakatı ve
kiralama yükümlülüğü kırılımı kaynakta doğrulanamadığında bilinçli olarak boş kalır.

## Rapor semantiği ve QC kararları (2026-08-04)

WMT ve KO raporlarının üç bağımsız LLM tarafından incelenmesinden sonra yalnız
ekonomik doğruluk ve yanlış yönlendirme riski taşıyan bulgular uygulandı:

- Önceki yıl YTD FCF'si negatifken oluşan pozitif FCF dönüşümü, olumlu sinyal
  listesinden çıkarılıp `base-effect review` sınıfına alınır; mekanik TTM ve yield
  rakamı korunur fakat tekrar eden run-rate olarak yorumlanamaz.
- `net_profit_trend`, kullandığı veriyle uyumlu biçimde `Consolidated Net Income
  Trend` olarak etiketlenir ve cari/karşılaştırma tutarları birlikte gösterilir.
- Konsolide FCF'nin TTM ana-ortaklık/konsolide net kâr oranıyla paylaştırılması
  doğrudan raporlanmış nakit akışı değil, açıkça `parent-attributed proxy`dir.
- Son 10-Q'da ayrı lease carrying amount bulunmazsa son 10-K tutarı tarihli ve
  `supplementary/stale` olarak gösterilebilir; güncel EV'ye ikame edilmez. KO için
  2025-FY değerleri 321 milyon USD current ve 1.401 milyon USD noncurrent'tır.
- Authored geniş evren raporda işletme-modeli eşleşmesine göre bölünür: WMT/COST
  Retail, KO/PEP Beverages, GIS/KHC/MDLZ/SJM Packaged Food, CL/PG Household and
  Personal Care. Ticker'a özel hesaplama koşulu yoktur; sınıflandırma veridir.
- Mali yıl etiketi takvim yılıyla aynı olmak zorunda değildir. Özellikle WMT
  FY2027 Q1'in 2026'da bitmesi issuer fiscal-year convention notuyla açıklanır.

## Point-in-time walk-forward backtest (2025 pilotu)

Backtest, canlı ABD artifact kökünü ve BIST akışlarını değiştirmeden
`us/backtests/{RUN_ID}/` altında çalışır. İlk pilot sabit 24 şirket ve dört operating-model
cohort'u için 2025-01-01 tarihinden başlayan aylık walk-forward simülasyondur. Bu sabit
evren survivorship ve universe-selection bias taşır; sonuç yalnız bu 24 şirket içindeki
karar katmanının ileri-tarihli simülasyonunu ölçer.

Her run başında SEC filing metadatası, karar fiyatı, performans fiyatı ve nakit oranı
ledger'ları bir kez dondurulur ve hash'lenir. Rapor/LLM girdileri yalnız karar cutoff'unda
bilinen filing'leri ve ham tarihsel kapanış fiyatını kullanır. Ex-post total-return hesabı
için corporate-action-aware fiyatlar ayrı ledger'da tutulur ve hiçbir zaman rapora veya
LLM'e verilmez. Bugünkü indirme zamanı tarihsel bilginin piyasada mevcut olduğu zamanla
karıştırılmaz; her gözlemin `available_at` zamanı kendi kaynak olayından gelir.

Aylık sıra şu şekildedir:

1. Ayın ilk ABD işlem gününde karar verilir; bilgi kesimi önceki tamamlanmış seansın
   kapanışıdır ve filing'in kamuya açıklanma tarihi de bu kesimi geçemez.
2. 24 şirketin point-in-time raporu üretilir. Eksik tek rapor bile ayı durdurur.
3. Her rapor Codex `gpt-5.6-sol`, `high` ile birbirinden izole değerlendirilir.
4. Önceki portföyün tez testleri kodla değerlendirilir. Portföy modeli 24 tam şirket
   kararını, önceki portföyü ve yalnız o tarihe kadar gerçekleşmiş pozisyon durumunu görür;
   benchmark, göreli performans ve gelecek veri prompt'a girmez.
5. Portföy en fazla dört hisseden oluşur; her pozisyon tam %25'tir, bir cohort'tan en
   fazla iki hisse seçilir ve kullanılmayan kısım nakitte kalır.
6. Emirler bir sonraki işlem gününün adjusted open değerinden uygulanır. Alış ve satış
   turnover'ının her biri için %0,10 maliyet düşülür. Nakit, günlük 3 aylık ABD Hazine
   oranıyla büyür. Eksik fiyat, oran veya corporate action ayı fail-closed durdurur.
7. Benchmark aynı 24 şirketin her ay eşit ağırlıklandırılmış total-return portföyüdür.
   Birincil başarı ölçütü net model portföyü getirisi eksi net benchmark getirisidir;
   bu ölçüt LLM'e açıklanmaz.

Her ayın artifact'ları immutable'dir ve hash zinciriyle önceki aya bağlanır:

```text
us/backtests/{RUN_ID}/months/2025-01/
  cutoff.json
  reports/{TICKER}.md
  company-decisions/{TICKER}.json
  prior-portfolio.json
  thesis-evaluation.json
  portfolio-decision.json
  execution.json
  monthly-performance.json
```

Son karar ayının getirisi, on üçüncü bir LLM kararı üretmeden sonraki planlı işlem
sınırında kapatılır:

```bash
python -m fundamental_pipeline_us.cli backtest-close-performance --run-root us/backtests/walk-forward-2025-v1 --month 2025-12
```

Aynı girdilerle tamamlanmış bir ay yeniden LLM çağrısı yapmaz. Teknik LLM hatası aynı
prompt ve aynı girdilerle en fazla iki kez denenir; model yargısı beğenilmediği için
retry yapılmaz. Gelecek filing, belirsiz availability zamanı, gelecekteki peer gözlemi,
geçersiz LLM JSON'u, portföy kısıtı ihlali, eksik fiyat/oran/corporate action veya kırık
hash zinciri run'ı durdurur. İlk uygulama kabul kapısı Ocak 2025 tam oluşumunun ve Şubat
2025 taşıma/yeniden dengelemesinin deterministik olarak tamamlanmasıdır.

## Public Equity Investing tarihsel replay — Idea Generation

### Amaç ve kapsam

Bu replay, geçmiş bir karar gününde kullanıcının ChatGPT'deki Public Equity
Investing akışını tek komutla başlatmış gibi çalışmalıdır. Amaç açıklama günü
kâr/zararını tahmin etmek değil; 2025 Ocak'tan başlayarak her karar tarihinde
60 şirketi yeniden taramak, seçilen adayları eklentinin sonraki araştırma
adımlarından geçirmek, portföyü kurmak ve takip eden aylarda aynı sistemi
point-in-time disiplinle sürdürmektir.

İlk doğrulama ayı Ocak 2025'tir:

- karar tarihi: `2025-01-02`;
- bilgi kesimi: `2024-12-31T23:59:59Z`;
- ilk uygulanabilir işlem seansı: `2025-01-03`;
- evren: dört sektörde 60/60 şirket;
- model: `gemini-3.1-pro-high`;
- web ve model konektörleri: kapalı;
- yerel deterministik ayrıştırma: açık ve çıktı manifestinde kayıtlı.

Bu aşamada gelecek getirileri açılmadı. Dolayısıyla aşağıdaki sonuçlar bir
performans sonucu değil, veri ve karar akışı kabul testidir.

### Point-in-time girdi sözleşmesi

Her şirket için yalnızca kesim anında yayımlanmış aşağıdaki malzeme kullanılır:

1. son erişilebilir 10-K/10-Q finansal raporu ve mevcut pipeline'ın ürettiği
   finansal, değerleme ve piyasa özeti;
2. son erişilebilir 8-K Item 2.02 ile ilişkili Exhibit 99.1 kazanç açıklamasından
   çıkarılan kanıt;
3. accession/source kimliği, filing tarihi, kaynak dosya hash'i ve kesim
   doğrulaması;
4. sayısal yönlendirme aralığı ancak iki uç da kaynak belgede birebir
   doğrulanabiliyorsa;
5. `raised/lowered/reaffirmed` gibi revizyon dili ancak kaynak metin bu sınıfı
   açıkça destekliyorsa.

Tarihsel konsensüs, transkript, pozisyonlanma ve short-interest verisi donmuş
pakette yoksa `unavailable` olarak işaretlenir; model bunları tahmin veya genel
piyasa bilgisiyle dolduramaz. Ocak paketinde son 8-K kanıtı 60/60 şirkette
mevcuttur; 28 şirkette iki ucu doğrulanmış sayısal yönlendirme, 37 şirkette
açık revizyon dili desteği vardır.

### Ocak 2025 deney kaydı

| Deneme | Girdi ve çıktı biçimi | Ham dağılım | Kabul kapısı sonucu |
|---|---|---|---|
| v1 | Finansal/değerleme/fiyat paketi, strict JSON | A 25 / B 9 / C 12 / Reject 14 | **Reddedildi.** 27 desteksiz revizyon veya olay iddiası, tekrarlanan variant-wedge dili ve bütün A adaylarının tek araştırma akışına zorlanması |
| v2 | v1 + cutoff-safe 8-K/Exhibit 99.1 kanıtı, strict JSON | A 17 / B 11 / C 20 / Reject 12 | **Reddedildi.** 17 A adayında aynı büyüme/değer/yönlendirme gerekçesi, aynı earnings-deep-dive rotası ve şablonlaşmış ilk beş kart |
| v3 | Aynı zengin paket, eklentiye daha yakın doğal Markdown | A 4 / B 14 / C 17 / Reject 25 | **Reddedildi.** 17 kez tekrarlanan gerekçe, bütün A'ların long-short-pitch'e yönelmesi, şablon PM kartları ve kaynakta olmayan konsensüs iddiası |

v3'ün A listesi `NVDA`, `ADBE`, `CL`, `ETN` idi; bu liste kalite kapısından
geçmediği için portföy girdisi değildir. Üç koşunun çıktıları hata örneği ve
regresyon kanıtı olarak korunur, sonuçları geriye dönük düzeltilmez.

### Kabul edilen çalışma mimarisi

Tek bir kullanıcı komutu korunur; 60 ayrı prompt üretilmez. Ancak tek modele
60 şirketi bir defada sıralatma yaklaşımı kaldırılır. Koordinatör koşuyu şu
şekilde parçalar:

```text
tek kullanıcı komutu
  -> donmuş 60 şirketlik kaynak paketi
  -> Consumer/Staples (24) iş akışı
  -> Health Care (12) iş akışı
  -> Industrials (12) iş akışı
  -> Technology (12) iş akışı
  -> dört iş akışının kompakt, kaynaklı aday çıktıları
  -> 60 şirketi birlikte gören nihai sentez
  -> deterministik + semantik kalite kapısı
  -> kabul edilirse sonraki eklenti adımları; değilse koşu reddi
```

Sektör iş akışlarının görevi nihai portföy seçmek değil, kendi işletme
modellerine uygun metrik ve kanıtlarla aday araştırması yapmaktır. Her biri
şirket bazında kaynak referansı, olumlu tez, variant perception, tez bozucu
kanıt, veri eksikleri ve önerilen sonraki araştırma akışını döndürür. Nihai
sentez dört çıktıyı birlikte görerek doğal A/B/C/Reject dağılımını ve ilk derin
çalışma alt kümesini belirler. Ayrıntılı PM kartları yalnızca bu dinamik alt
kümeye yazılır.

Bu yapı eklentinin idea-generation yönergesindeki workstream decomposition
davranışını korur: kullanıcı aynı sohbet içinde tek istek verir, iç çalışma
paralel uzman akışlarına ayrılır, tek birleşik cevap geri gelir.

### Artifact ve yeniden başlatma sözleşmesi

Yeni koşular aşağıdaki mantıksal yapıyı kullanmalıdır; v1-v3 tarihsel çıktıları
mevcut konumlarında değiştirilmeden kalır:

```text
us/backtests/{RUN_ID}/months/{YYYY-MM}/idea-generation/
  input-manifest.json
  universe-pack.json
  workstreams/{consumer-staples,health-care,industrials,technology}.json
  synthesis.json
  synthesis.md
  validation.json
```

Manifest model kimliğini, prompt/skill sürümünü, cutoff'u ve bütün girdi
hash'lerini taşır. Aynı hash kümesiyle tekrar çalıştırma mevcut artifact'i
yeniden kullanır. Teknik/API hatasında aynı girdilerle sınırlı yeniden deneme
yapılabilir; beğenilmeyen yatırım yargısı için sessiz model tekrarı yapılamaz.
Kesintide tamamlanan iş akışları korunur ve koşu kaldığı aşamadan sürer.

### Zorunlu kalite kapıları

- 60 şirketin her biri tam bir kez yer alır; eksik veya mükerrer ticker yoktur.
- Rank değerleri benzersizdir ve bucket toplamları 60 ile mutabıktır.
- Her kaynak kimliği donmuş manifestte bulunur ve cutoff'tan sonrasına sarkmaz.
- Revizyon ve sayısal yönlendirme iddiaları deterministik kaynak bayraklarıyla
  uyumludur.
- Konsensüs, pozisyonlanma veya benzeri eksik veriler hakkında desteksiz iddia
  bulunmaz.
- Tekrarlanan rationale/variant-wedge şablonları ve tüm A adaylarını aynı
  workflow'a zorlayan çıktılar reddedilir.
- Öncelikli alt küme dinamiktir; 60 şirket için mekanik olarak ayrıntılı kart
  üretilmez.
- Kalite kapısından geçmeyen sonuç sonraki araştırma veya portföy aşamasına
  ilerleyemez.

### Mevcut durum ve sonraki kabul testi

Point-in-time veri paketi, 8-K kanıt ayrıştırması, prompt üretimi ve tek-model
v1-v3 doğrulamaları çalışır durumdadır. Dört workstream + nihai sentez
orkestrasyonu henüz uygulanıp çalıştırılmamıştır. Bir sonraki kabul testi yine
Ocak 2025 üzerinde yapılacak; ancak mimari ve kalite kapıları sonuç görülmeden
önce sabitlenecektir. Bu test kabul edilmeden Şubat ayına, sonraki eklenti
adımlarına veya portföy performansına geçilmez.

## Canlı akış: paket doğrudan artifact'ten (2026-08-10)

Plugin akışı backtest ağacından ayrıldı. Canlı veri `us/live/current` altında
yaşıyor; `us/backtests/` kökleri (ic-2021-v1, ic-2024-v1) ölçüm kanıtı olarak
dokunulmadan duruyor.

**Paket artık rapor ayrıştırmıyor.** `live_pack.py` çarpanları
`valuation-results`'tan, fiyat ve piyasa değerini `valuation-inputs`'tan, dönem
ve temel kalemleri finansal JSON'lardan, trendleri `signals`'tan okuyor. Eski
üretici markdown raporu regex'le ayrıştırıyordu; bu hem rapor üretimini zorunlu
kılıyordu hem başlık formatı değişince kırılıyordu.

**Rapor üretimi canlı yoldan çıktı.** `generate_report` bayrağı
`run_us_valuation`, `run_company_workflow`, `generate_us_peer_comparisons` ve
dönem çıktı paketinde var; **varsayılan açık**, yalnız canlı yol `False`
geçiyor. Backtest ve BIST yolları değişmedi. Render ve doğrulama duruyor,
atlanan yalnız diske yazma.

**Rapora bağlı mekanizmalar artifact'e taşındı.** Bir kesimin tamamlanmış
sayılması artık markdown saymakla değil, her şirketin o kesim için değerleme
sonucu olmasıyla ölçülüyor (`live_refresh.month_is_complete`). Zorlama
temizliği kesimin `valuation-results` / `valuation-inputs` / `market-inputs`
klasörlerini siliyor.

**Kesim = son kapanmış seans.** Klasör adı paketin üretildiği gün
(`us/pei/<üretim-günü>/`), kesim ise fiyat defterindeki son seans. İkisinin
farklı olması normaldir: Pazartesi sabahı üretilen paketin kesimi Cuma'dır.

**Her kesim kendi kapsama kaydını taşır.** `months/<kesim>/coverage.json`
evrenin kaçının çıktığını ve **eksiklerin adını** tutar. Sayım koşunun kendi
listesinden değil artifact'ten yapılır: günlük tazeleme yalnız yeni bildirim
gelen şirketleri işler ve o listeyi evren saymak tam bir kesimi boşluk gibi
gösterirdi.

### Plugin'in veri talebi

Plugin hiçbir yerde geçmiş veri uzunluğu istemiyor; sayısal talepleri ileriye
dönük tahmin ufku. Geçmişe dair sözleşmesi **tazelik** ve etiket disiplini:

| Veri | Bayat sayılma eşiği | Durumumuz |
|---|---|---|
| Fiyat / piyasa değeri / FD | 1 seanstan eski | son kapanış |
| Kamuya açık finansallar | daha yeni bildirimle geçersizleşince | dosyalama tetikli tazeleme |
| Konsensüs | 30 gün (bilanço civarı 7-14) | günlük anlık görüntü |

Geçmişi yalnız niteliksel kullanıyor ("marj kendi geçmişinin üstünde"), minimum
dönem sayısı vermiyor. Elimizde şirket başına ortanca 5 dönem var (3 yıllık +
1-2 çeyrek), fiyatta 960 seans.

### Bilinen sınır

Yeni bir evren getirmek tek komut değil: evren `peer-universes/*.json`
üyelerinin birleşiminden türüyor ve yeni grup şirket başına config, emsal
ailesi ataması, konsensüs evren dosyası ve ayrı bir canlı kök istiyor
(`RUN_ID` sabit). Hesap ucuz (~30 şirket sıfırdan 15 dakika); zorluk config
kurulumunda.

## Karar günlüğü

| Karar | Alternatifler | Gerekçe |
|---|---|---|
| İzole `us/` kökü + yan paket | Tam kopya; tüm çekirdeği TR/US refactor | BIST regresyon yüzeyini küçültür, motor kopyasını önler. |
| Accession-bazlı filing XBRL ana kaynak | Yalnız `companyfacts`; quarterly bulk set | Custom tag ve as-filed dönem bağlamını korur, 10-12 şirkette küçüktür. |
| Arelle dar adaptör bağımlılığı | XBRL'i elde parse etmek | Context/dimension/custom taxonomy hatalarını yeniden üretmez. |
| Drive ve NotebookLM yok | KAP akışını ABD'ye taşımak | SEC arşivi ve yapılandırılmış filing verisi yeterlidir. |
| Direct outstanding ortak alternatifi | `treasury=0` uydurmak; ABD'ye özel market snapshot | Ekonomik semantiği korur ve genel, geriye uyumlu bir sözleşmedir. |
| Önce tek şirket dikey dilimi | Doğrudan 12 şirkete batch | Şema ve dönem hatalarını çoğaltmadan erken doğrular. |
| İki 10-K + son 10-Q ve karşılaştırma artifact'ı | Yalnız son filing; sentetik TTM | Gerçek önceki-YTD sütunuyla TTM'yi ortak motorun dönem cebiri üzerinden kurar. |
| SEC Item 1A için deterministik metin adaptörü | NotebookLM; risksiz rapor | Ücretsiz, accession-bağlı ve yeniden üretilebilir risk kapsamı sağlar. |
| Tek authored tüketim malları evreni + işletme modeli alt grupları | Tek geniş medyan; ticker'a özel emsal listeleri | Artifact üretimini tek yerde tutarken raporda perakende, içecek, paketli gıda ve kişisel bakım iş modellerini karıştırmaz. |
| Baz etkili FCF'yi review sınıfına ayır | Otomatik pozitif sinyal; öznel normalize FCF üretmek | Ham dönem cebirini korur, negatif karşılaştırma bazını tekrarlayan performans gibi sunmaz ve kanıtsız normalizasyon yapmaz. |
| Eski yıllık lease tutarını yalnız supplementary göster | Güncel EV'ye eski tutarı eklemek; bilgiyi tamamen gizlemek | Kaynakta bulunan son taşıma değerini görünür yapar ama bilanço tarihlerini karıştırmaz. |
| Ayrı İngilizce ABD rapor şablonu | Tek iki-dilli şablon; sonradan çeviri | BIST sunumunu etkilemeden doğal US-GAAP/SEC terminolojisi ve tam dil izolasyonu sağlar. |
| Standart XBRL dipnot fact'leri + kontrollü inheritance | Serbest metin tahmini; NotebookLM | Vade/lease/faiz bilgisini ücretsiz, sayısal ve accession-bağlı tutar. |
| 8-K exhibit'lerinde yalnız tekil issuer fact'i | Hesaplanmış EBITDA'yı issuer-reported saymak | Non-GAAP semantiğini korur; açıklanmayan ölçüyü uydurmaz. |
