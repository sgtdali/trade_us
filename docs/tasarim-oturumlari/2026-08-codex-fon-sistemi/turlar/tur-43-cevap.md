Üçlü ayrım doğru, fakat araya dördüncü bir katman koymalıyız: **mekanik tarihsel replay**. Böylece “backtest” kelimesinin iki farklı iddiasını ayırabiliriz.

## 1. Dört ayrı sınama türü

| Tür | Cevapladığı soru | Hüküm |
|---|---|---|
| Strateji backtest’i | “Bu sistem geçmişte para kazandırır mıydı?” | **Şimdilik geçersiz.** Tarihsel tez/readiness yok; geriye dönük üretim hindsight, bugünkü evren survivorship taşır. |
| Mekanik tarihsel replay | “Verili karar girdileri ve tarihsel fiyat yolu altında policy ne yapardı?” | **Geçerli.** Alpha’yı değil; nakit, turnover, band, limit, drawdown ve işlem davranışını sınar. |
| Sentetik stres/property testi | “Uç ve sınır durumlarında policy tutarlı mı?” | **Zorunlu.** En ucuz ve en yüksek getirili ilk testtir. |
| Prospektif gölge koşu | “Bugünün bilgisiyle üretilen gerçek kararlar zaman içinde kullanılabilir mi?” | **Zorunlu.** En gerçekçi fakat en yavaş doğrulamadır. |

Dolayısıyla klasik strateji backtest’ini şimdi kurmazdım. Savunulabilir dar biçimi şudur:

- Tez, readiness veya hindsight üretme.
- Bunları dışarıdan verilmiş sabit girdiler kabul et.
- Tarihsel fiyat, nakit akışı, corporate action ve execution gecikmelerini oynat.
- Sonuç olarak getiri/Sharpe değil; limit ihlali, turnover, nakit yeterliliği, proposal sayısı ve policy davranışı raporla.

Bu test “policy para kazandırırdı” diyemez; “policy bu koşullarda nasıl davranırdı” diyebilir. Geçmiş veri üzerinde çok sayıda parametre deneyip en iyi sonucu seçmek backtest overfitting riskini doğrudan üretir; dolayısıyla replay sonuçları provisional sayıları optimize etmek için kullanılmamalıdır. [Lawrence Berkeley National Laboratory çalışması](https://escholarship.org/content/qt4hn4t174/qt4hn4t174.pdf)

Bu katmanlama, model doğrulamasını kavramsal sağlamlık, sürekli izleme ve sonuç analizi olarak ayıran daha genel doğrulama yaklaşımıyla da uyumludur. [Federal Reserve SR 11-7](https://www.federalreserve.gov/boarddocs/srletters/2011/sr1107a1.pdf)

## 2. Stres testinin başarısızlık kriteri

Policy kendi kendisini doğrulayamaz. Ayrı ve önceden dondurulmuş bir `policy_validation_spec` gerekir. Bu belge uygulamadan türetilmez; sistem değişmezlerinden ve beklenen davranıştan yazılır.

### Kesin başarısızlıklar

Policy şu durumlardan herhangi birini üretiyorsa başarısızdır:

- Long-only sistemde negatif pozisyon veya kaldıraç önerir.
- Ağırlıklar ve nakit toplamı muhasebe toleransı içinde %100 etmez.
- Hard issuer, loss-budget, gap-risk veya nakit sınırını aşan proposal üretir.
- Bayat, uzlaştırılmamış veya `position_unknown` veriyle yeni risk artırır.
- `broken` veya `unadjudicated` pozisyona ekleme önerir.
- Fiyat düşüşü/drawdown nedeniyle otomatik satış kararı verir.
- İnsan onayı olmadan trade intent üretir.
- Split veya başka kurumsal işlemi ekonomik kayıp gibi yorumlar.
- Aynı policy ve aynı snapshot için farklı sonuç üretir.
- Eski policy sürümüyle üretilmiş proposal’ı yeni policy altında geçerli sayar.

### Davranışsal başarısızlıklar

Bunlar muhasebe hatası değildir ama policy’nin saçma davrandığını gösterir:

- Daha kötü downside senaryosu izin verilen ağırlığı artırır.
- Readiness düşürülünce ağırlık bandı genişler.
- Policy sıkılaştırılınca daha fazla risk alınabilir hâle gelir.
- No-trade bandı içindeki küçük fiyat hareketleri sürekli işlem üretir.
- Yalnızca nakit girişi olduğu için fikir kalitesi değişmeden zorunlu alım doğar.
- Kitap doluyken yeni aday replacement hurdle’ı geçmeden pozisyonu iter.
- Fiyat toparlandığı için tamamlanmamış drawdown incelemesi kendiliğinden kapanır.
- Parametrede küçük değişiklik, açıkça tanımlanmış eşik dışında çok büyük portföy değişikliği yaratır.
- Aynı kural aynı gerekçeyle tekrar tekrar insan override’ı gerektirir.

Sonuncusu özellikle önemlidir: tekrar eden override “insan istisnası” değil, yanlış policy kalibrasyonu veya eksik model işaretidir.

## 3. Capital Policy v0 kabul kapısı

Bu kapı sayıların optimal veya kârlı olduğunu kanıtlamaz. Yalnızca dört iddiayı destekler:

1. **Uygulanabilir:** Kurallar birbiriyle çelişmeden portföy üretebiliyor.
2. **Güvenli:** Bilinen olumsuz senaryolarda hard sınırlar korunuyor.
3. **Kararlı:** Küçük değişiklikler gereksiz işlem veya büyük sıçrama üretmiyor.
4. **İşletilebilir:** Tek operatör sistemi haftalık zaman bütçesi içinde kullanabiliyor.

Canlı sermayeye sınırlı yetki verilmeden önce şu kapıların tamamı geçilmelidir:

### A. Dondurulmuş sözleşmeler

- `capital_policy.v0`
- `policy_validation_spec.v0`
- Testlerde kullanılacak scenario/replay seti

Beklenen sonuçlar test çalıştırılmadan önce yazılmalıdır; sonuç görüldükten sonra başarı kriteri değiştirilmemelidir.

### B. Zorunlu senaryo seti

En az şu aileler bulunmalıdır:

- Tek isimde -%20, -%40 ve -%70 gap
- Piyasa genelinde -%10, -%20 ve -%35 düşüş
- Aynı driver’a bağlı birkaç pozisyonun birlikte düşmesi
- Büyük nakit girişi ve çekimi
- Kısmi fill, iptal, üç günlük execution gecikmesi
- Split, temettü ve ücret
- Bayat fiyat, eksik FX, reconciliation farkı
- Band ve limitlerin hemen altı/hemen üstü
- `core → starter`, `intact → review_required → broken` geçişleri
- Kitap doluyken yeni challenger

Bütün kesin başarısızlık kriterleri **%100 geçmelidir**.

### C. Parametre duyarlılığı

Amaç en iyi parametreyi seçmek değil, kırılganlığı görmek olmalıdır. Örneğin:

- Azami pozisyon: 8 / 10 / 12
- Loss budget: 75 / 100 / 125 bp
- No-trade bandı: 0,5 / 1,0 / 1,5 yüzde puan
- Starter çarpanı: 0,4 / 0,5 / 0,6

Komşu değerler bambaşka portföyler üretiyorsa provisional merkez değer “makul” kabul edilmemelidir.

### D. Prospektif gölge koşu

Minimum kabul:

- İki tam aylık proposal döngüsü
- En az bir event-driven inceleme; gerçek olay yoksa kontrollü enjeksiyon
- Bütün önerilerin policy sürümü, snapshot ve binding constraint ile açıklanabilmesi
- Çözümlenmemiş hard breach bulunmaması
- Aynı kural için tekrar eden override bulunmaması
- Haftalık işletim yükünün 6–9 saat bütçesini aşmaması
- P0/P1 kuyruğunun tanımlı sürede kapanması

Bu kapı geçildiğinde policy “kanıtlanmış strateji” değil, **sınırlı canlı pilot için provisionally fit** sayılır. İlk canlı kullanım starter boyutlarıyla yapılmalı; yeni sistem yalnızca hesapladı diye mevcut kitap topluca yeniden kurulmalıdır denmemelidir.

En net hükmüm şu: **Stres testi policy’nin tehlikeli olmadığını, gölge koşu kullanılabilir olduğunu gösterebilir; ikisi de para kazandıracağını gösteremez.** Gerçek yatırım yeteneğine dair kanıt ancak ileriye dönük, dondurulmuş kararların zaman içindeki sonuçlarından birikir.