En sert hükmüm şu: On altı turda iyi bir lifecycle tasarladık ama henüz tanımlanmamış bir portföy inşa politikasının çevresine kurduk. Binanın iç tutarlılığı arttı; temelin eksik olduğunu geç fark ettik.

## Üç mandate gerilimi

### 1. “Aylık rebalans” yanlış adlandırılmış ve fazla yetkilendirilmiş

Mandate aslında “ayda bir değiştir” demiyor; `change_required: false` diyor ve hold’u geçerli sonuç sayıyor. Bu nedenle aylık ritim bir **karar penceresi**, işlem veya yeniden optimizasyon emri değildir.

Biz bunu dokümanda “aylık rebalans” diye adlandırarak farkında olmadan şu yetkiyi verdik:

> Her ay bütün tezleri yeniden karşılaştır, ağırlıkları değiştirmeyi düşün.

Bu, yeni bilgi olmadan uygulanırsa 3–18 aylık temel analiz stratejisini aylık rotasyon stratejisine dönüştürür. Özellikle verinin ortalama 46 günlük olduğu bir sistemde aylık tekrar, daha taze karar değil aynı eski verinin tekrar yorumlanması olabilir.

Doğru çerçeve bence:

```text
Haftalık: kontrol yüzeyi ve vadesi gelen istisnalar
Filing/event: tezi yeniden değerlendirme
Aylık: portföy bütünlüğü ve tahsis gözden geçirmesi
İşlem: yalnız yeni kanıt, fiyat/değerleme değişimi veya açık sermaye kısıtı varsa
```

Tez “hold” derken portföyün trim demesi meşru olabilir; örneğin yoğunlaşma, nakit ihtiyacı veya mutlak kayıp bütçesi yüzünden. Ama bu mandate’te bu kısıtların hiçbiri yok. Dolayısıyla mevcut hâliyle portföy oturumunun tezi ezmesini meşrulaştıracak bir dayanağı da yok.

Başlık 4 karar 1 “aylık rebalans”tan “aylık portföy gözden geçirmesi; varsayılan sonuç no-change” biçimine dönmeli.

### 2. Portföy inşa çıpasının yokluğu gerçek

Long-only, ABD’de listeli ve adi hisse olmak portföy inşa kuralları değil, uygunluk kurallarıdır. Likidite tabanının uygulanmaması da doğru; hiçbir şeyi elemeyen kısıtı sırf kurumsal görünsün diye eklememeliyiz.

Fakat bunlardan sonra şu sorular cevapsız kalıyor:

- Bir fikir “iyi” olsa bile ne kadar alınabilir?
- İki iyi fikirden hangisine daha fazla sermaye verilir?
- Toplam sermayenin ne kadarı nakitte kalabilir?
- Tek isimde kabul edilen azami kayıp veya sermaye nedir?
- On fikir barı geçtiğinde ağırlıklar eşit mi, risk bazlı mı, conviction bazlı mı?

`position_count=null` tek başına sorun değil; sayı gerçekten fikirlerden türeyebilir. Ama ağırlıklandırma ve kayıp bütçesi de yoksa problem matematiksel olarak eksik tanımlıdır. Aynı tez kümesi için sonsuz sayıda “uygun” portföy üretilebilir.

Bu nedenle `mandate.json` bugün bir **araştırma mandate’i**, tam bir **sermaye politikası** değil. İkisini ayırmak daha dürüst olur:

```text
research_mandate
    evren, yön, araç, ufuk, araştırma ritmi

capital_policy
    sermaye tabanı, nakit yaklaşımı, tek-isim riski,
    kayıp bütçesi, ağırlıklandırma ilkesi, işlem eşiği
```

Kullanıcı capital policy tanımlayana kadar sistem portföyü gösterebilir, uzlaştırabilir ve koşullu seçenekler sunabilir; kanonik hedef ağırlık veya “rebalans” öneremez.

### 3. Benchmark yokluğu skill’i tamamen bozmaz, fakat rolünü küçültür

`portfolio-risk-management` gerçekten `long_only_pm` için benchmark active weight ve tracking error vurguluyor. Fakat skill aynı zamanda eksik bağlamda “conditional risk screen” üretmesini ve implementation-ready öneri vermemesini söylüyor.

Dolayısıyla iki ihtimal var:

- Benchmark uydurulursa mandate çiğnenir.
- Benchmark açıkça yok denirse skill çalışabilir ama yalnız koşullu tek-pozisyon analizi verir.

İkinci yol geçerli; fakat aylık portföy allocator’ı olmaya yetmez. Üstelik loss budget, exposure limit ve bağlayıcı likidite kısıtı da yoksa skill’in “binding constraint” seçebileceği malzeme kalmıyor.

Sonuç: Skill katalogdan tamamen atılmak zorunda değil, fakat yalnız açık bir pozisyon-sizing sorusu ve kullanıcı tarafından verilmiş risk bütçesi olduğunda çağrılmalı. Aylık portföy inşasını ona devretme kararı yanlıştı.

## Beş eksen fazla ağır mı?

Evet. Bugün sıfır tezli sistem için beş kalıcı eksen fazla modellenmiş. Daha önemlisi, tabloda aynı varlığa ait olmayan gerçekleri “tez eksenleri” diye birleştirdik:

- `actual_exposure` tez gerçeği değil, broker/portföy gerçeğidir.
- `recommended_action` kalıcı durum değil, belirli tarihli bir değerlendirmedir.
- `security_readiness` de çoğunlukla son pitch veya re-underwrite sonucudur.
- `thesis_lifecycle` ile `company_thesis_status` önemli ölçüde örtüşür.
- `superseded` için gerçek bir mekanizma hâlâ yoktur.

Ben bugün bunu üç kalıcı eksene bile indirmezdim; iki otoritatif gerçek ve bir tarihli değerlendirme olarak modellendirdim:

```text
1. Thesis
   active / review_required / broken / closed

2. Actual exposure
   reconciled long/flat veya unknown; miktar ve as-of

3. Dated assessment
   add/hold/trim/exit/re-underwrite; geçerlilik tarihiyle
```

Bunlardan diğerleri türetilir:

```text
broken thesis + long exposure = wind_down
active thesis veya non-flat/unknown exposure = monitoring_required
latest accepted pitch/re-underwrite = security readiness
```

`wind_down` yararlı bir kavramdır ama ayrı elle yönetilen eksen olmak zorunda değildir. `superseded` ilk sürümden çıkarılmalı. Yeni fikir gerçekten doğarsa eski tez kapanır ve yeni `thesis_id` açılır.

Yani beş eksenli model düşünsel ayrımları bulmamıza yardım etti; üretim veri modeli olarak aynen korunması gerekmiyor.

## Lot defteri gerekli mi?

Tam lot eşleştirme motoru şu aşamada YAGNI. Vergisel lot otoritesi broker’dır; bu araştırma sistemi ikinci bir broker muhasebesi kurmamalı.

Ama “ortalama maliyet + yılda bir ekstre” de yetersiz. Bir yıl boyunca unutulmuş işlem, split veya yanlış adet taşımak gerçek para tarafında kabul edilemez.

Daha hafif doğru çözüm:

- Her fill append-only işlem olarak kaydedilir.
- Broker işlem kimliği ve ham ekstre referansı korunur.
- Güncel adet ve broker-reported average cost uzlaştırma snapshot’ında tutulur.
- Her işlemden sonra veya en az aylık reconciliation yapılır.
- Satışta tax-lot matching sistem içinde çözülmez; broker sonucu kaynak kabul edilir.
- Tez performansı, teze bağlı nakit akışları üzerinden hesaplanır.

Ticker başına tek açık tez kuralı varken “bu tezle ne kazandım?” sorusu için tax-lot motoruna çoğunlukla ihtiyaç yoktur. Tam lot eşleştirme ancak aynı ticker’da eşzamanlı stratejiler veya vergi optimizasyonu gerçekten ortaya çıktığında eklenmeli.

Aynı şekilde tam kurumsal işlem motoru da ilk sürüm için fazla ağırdır. Broker uzlaştırmasının adet/maliyet farkını yakalaması ve fiyat eşiklerinin split-adjusted veri kullandığının doğrulanması yeterli başlangıç olabilir.

## Tez merkezlilik yanlış öncül mü?

Kısmen yanlış kullandık; fakat tezin kendisi yanlış soyutlama değil.

3–18 aylık temel analiz yaklaşımında şu sorular doğası gereği tezdir:

- Neden bu şirket?
- Piyasa neyi yanlış fiyatlıyor?
- Ne doğru çıkmalı?
- Hangi kanıt fikri bozar?

Sade bir sıralama modeli bunları taşımaz. Üstelik mevcut A/B/C çıktısı cardinal expected-return skoru değildir; araştırma önceliğidir. Benchmark, karşılaştırılabilir skor ve ağırlıklandırma fonksiyonu olmadan “ranking + threshold” daha basit görünür ama daha dürüst değildir. A’nın B’den kaç birim daha iyi olduğunu bilmiyoruz.

Bizim hatamız tezi iki ayrı işin merkezine koymaktı:

1. Araştırma hafızası ve bozulma takibi — tez burada doğru merkezdir.
2. Portföy ağırlıklandırması — tez tek başına burada yeterli değildir.

Doğru model hibrittir:

```text
Keşif: bağlama bağlı sıralama ve öncelik
Araştırma: sade yatırım tezi
Portföy: ayrı ve açık sermaye politikası
```

Tez “neden sahip olunabilir?” sorusunu cevaplar. Capital policy “ne kadar sahip olunabilir?” sorusunu cevaplar. Şu anda yalnız birincisi tanımlı.

## Bugün sıfırdan yazsaydım

On altı turdaki kararların yaklaşık üçte birini ilk sürüme koyardım. İnşa edeceğim ince dikey dilim şu olurdu:

- SQLite’ta tek-yazarlı append-only olay defteri, idempotency ve immutable artefakt hash’leri.
- Küçük, kayan keşif batch’leri; A/B/C mutlaka comparison-set kimliği taşır.
- Fresh context bundle kullanan workflow zinciri.
- Yalnız pitch → tez geçişinde insan kapısı.
- Basit tez kaydı: durum, yatırım gerekçesi, kill koşulları, sonraki inceleme tarihi.
- Önce metinsel/manual izleme; yalnız açık ve kolay metrikler için mekanik eşik.
- İşlem olayları, broker snapshot’ı, reconciliation ve `position_unknown`.
- P0–P4 “Bugün” kuyruğu ve kanıt merkezli basit HTML yüzeyi.
- Haftalık kuyruk kontrolü, filing/event-driven tez incelemesi, aylık no-change-varsayılanlı portföy gözden geçirmesi.
- Gerçek işlem yalnız insan tarafından.

İlk sürümde yazmayacaklarım:

- Beş eksenli tez state machine’i.
- Tam tur kapanışı, waived dilim ve coverage deadlock mekaniği.
- Tax-lot eşleştirme motoru.
- Genel amaçlı kurumsal işlem motoru.
- Her kill criterion’ı kapsayan metric DSL.
- Retrospective breach’in bütün restatement semantiği.
- Kanonik blob deposu + iki görünüm; ilk aşamada immutable yol + hash yeterli.
- `superseded`.
- Otomatik aylık rebalans.
- Portfolio-risk-management entegrasyonu.
- Benchmark, sektör limiti veya korelasyon kuralı uydurmak.

Önce tek bir uçtan uca gerçeği kanıtlardım:

```text
screen → pitch → tez → gerçek alım → broker reconciliation
→ bir monitoring kontrolü → hold veya exit
```

Bu bir kez gerçek parayla çalışmadan geri kalan lifecycle’ın çoğu doğrulanmış gereksinim değil, iyi düşünülmüş varsayımdır.

Bugünkü kanaatim: Tasarım yanlış değil; **erken kurumsallaşmış**. En büyük hata olay şemasında veya tez eksenlerinde değil, henüz tanımlanmamış bir capital policy varmış gibi portföy katmanını tasarlamamızdı. Önce sistemin araştırma defteri mi, yoksa sermaye tahsis sistemi mi olduğu kesinleşmeli. Şu an güvenle inşa edilebilecek olan birincisidir.