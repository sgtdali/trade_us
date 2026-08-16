Evet; birçok davranış kuralı property’ye çevrilebilir. Ama küçük bir düzeltme: property-based test matematiksel kanıt değildir. Çok geniş bir alanda karşı-örnek arar ve bulduğunu küçültür; “geçti” demek evrensel doğruluk ispatı değildir. Bununla birlikte burada örnek-bazlı testten çok daha güçlüdür.

## 1. Policy motorunun matematiksel özellikleri

Şu gösterimi kullanalım:

- `P`: policy sürümü
- `S`: adjudicate edilmiş, değişmez girdi snapshot’ı
- `U(P,S,i)`: `i` pozisyonunun policy-compliant azami ağırlığı
- `F(P,S)`: policy’ye uygun bütün portföylerin kümesi
- `E(P,S)`: motor çıktısı

### Saflık ve determinizm

- `E(P,S) = E(P,S)`: aynı kanonik girdiler aynı semantik çıktıyı üretir.
- Pozisyonların giriş sırası sonucu değiştirmez.
- Kullanılmayan bir metadata alanındaki değişiklik sonucu değiştirmez.
- Aynı snapshot tekrar işlendiğinde yeni trade/proposal ihtiyacı icat edilmez.
- Bütün ilgili geçmiş state snapshot’a dahilse gizli process/session state sonucu etkileyemez.

### Muhasebe ve uygulanabilirlik

- Bütün pozisyon ağırlıkları `>= 0` olmalıdır.
- Pozisyon ağırlıkları + nakit, tolerans içinde `%100` olmalıdır.
- Her önerilen ağırlık kendi eligible bandı içinde ve `<= U(P,S,i)` olmalıdır.
- Motor ya hard-limit uyumlu sonuç üretir ya da açıkça `infeasible/blocked` döner; geçersiz sonucu “en iyi çaba” diye sunamaz.
- Risk azaltma proposal’ı mevcut hard-limit ihlalinin şiddetini artıramaz.
- Yeni risk artırımı, `position_unknown`, bayat veri veya başarısız reconciliation altında mümkün olamaz.

### Monotonluk

Bunlar her zaman nihai portföy ağırlığına değil, ilgili güvenlik zarfına uygulanmalıdır:

- Downside kaybı kötüleşirse `U` artamaz.
- Loss budget daralırsa `U` artamaz.
- Readiness düşerse ilgili pozisyonun üst bandı genişleyemez.
- Gap-risk sınıfı ağırlaşırsa `U` artamaz.
- Issuer/sector/driver/liquidity limiti sıkılaşırsa `U` artamaz.
- Asgari nakit yükselirse deployable capital artamaz.
- Veri kalitesi veya tazeliği kötüleşirse actionability artamaz.
- Replacement hurdle yükselirse hurdle’ı geçen adaylar kümesi genişleyemez.
- İşlem maliyeti yükselirse discretionary trade kümesi genişleyemez; zorunlu risk azaltımları bundan ayrıdır.
- Daha sıkı policy altında uygun portföy kümesi genişleyemez:

`P_sıkı`, `P_gevşek`ten daha kısıtlıysa  
`F(P_sıkı,S) ⊆ F(P_gevşek,S)` olmalıdır.

Önemli sınır: Bir ismin riski kötüleştiğinde diğer isimlerin ağırlıkları artabilir; çünkü boşalan kapasite başka yerlere veya nakde gider. Dolayısıyla “her ağırlık monoton olmalıdır” yanlış property’dir. Monoton olan, kötüleşen ismin kendi güvenlik tavanı ve toplam uygun portföy kümesidir.

### Ekonomik eşdeğerlik

- Hisse bölünmesi: adet `×n`, fiyat `/n` olduğunda pozisyon değeri, ağırlık ve risk sonucu değişmemelidir.
- Bütün para değerleri aynı katsayıyla ölçeklendiğinde, mutlak parasal eşikler hariç ağırlık sonuçları değişmemelidir.
- Fiyatlar ve FX tutarlı biçimde başka para birimine çevrildiğinde ekonomik sonuç değişmemelidir.
- Eklenen policy-ineligible bir security mevcut portföy sonucunu değiştirmemelidir.
- Ekonomik olarak özdeş iki pozisyon, kimlikleri dışında aynı risk bandını almalıdır.

### Histerezis ve state-machine özellikleri

- No-trade bandı içindeki hareket discretionary trade üretmez.
- Aynı event iki kez attach edilirse iki görev/proposal doğmaz.
- Drawdown kötüleştikçe inceleme seviyesi düşemez.
- Fiyat toparlanması tek başına inceleme dondurmasını kaldıramaz.
- Dondurma yalnız gerekli `review_completed/adjudicated` geçişiyle kalkar.
- Material input değişikliği açık proposal’ı geçersiz kılar veya yeni sürüme taşır.
- Kısmi fill sonrası kalan miktar gerçekleşmiş fill’lerden yeniden türetilir.
- Aynı statement iki kez import edilirse ikinci ekonomik kayıt oluşmaz.

Bunlar saf fonksiyon property’sinden ziyade state-machine property’leridir ama yine otomatik üretilebilir işlem dizileriyle sınanabilir.

## 2. Property’ye indirgenemeyenler

Property testleri şu soruları tek başına cevaplayamaz:

- `-%15` drawdown’da “eklemeyi dondur” kararının ekonomik olarak doğru olup olmadığı
- Bir challenger’ın incumbent’tan gerçekten daha iyi olup olmadığı
- Driver taksonomisinin ekonomik dünyayı doğru temsil edip etmediği
- Bir valuation/downside girdisinin yatırım açısından makul olup olmadığı
- Corporate action’ın özel hukuki/ekonomik anlamı
- Proposal açıklamasının insan tarafından anlaşılabilirliği
- Operatörün gereken adjudication’ı 6–9 saat içinde yapabilmesi
- İnsan override’ının gerekçesinin kaliteli olup olmadığı
- Policy’nin para kazandırma ihtimali

Bunlar açık fixture ve beklenen sonuç taşıyan örnek senaryolar ister. Property testleri örnek senaryoların yerine geçmez; bilinmeyen kombinasyonları arayan ikinci savunma hattıdır.

## 3. Fixture mimarisi

Tek bir “temsili kitap” yeterli değildir. Üç katman gerekir.

### A. Üretilmiş kitaplar

Property testleri için binlerce kitap üretilir:

- 0–12 pozisyon
- Çeşitli cash seviyeleri
- Limit altı/üstü ağırlıklar
- Farklı readiness/downside/gap sınıfları
- Ayrışık veya yoğunlaşmış driver yapıları
- Taze/bayat/unknown/reconciliation-failed state’ler

Valid, boundary ve invalid state generator’ları ayrı olmalıdır. Generator’ın kendisi de domain sözleşmesidir; yalnız rastgele sayı üretmemelidir.

### B. Altın sentetik fixture’lar

İnsan tarafından okunabilen 6–8 küçük kanonik kitap tutulmalıdır:

1. Tamamen nakit kitap
2. Tek ve aşırı yoğun pozisyon
3. Dengeli 10 isim
4. Farklı sektörlerde ama aynı driver’a bağlı kitap
5. Bütün limitlere yaklaşmış tam kitap
6. Hard-limit ihlalli kitap
7. Bayat/uzlaştırılmamış kitap
8. Split, temettü ve kısmi fill içeren kitap

Bunlar regresyon, dokümantasyon ve “motor neden böyle yaptı?” incelemesi içindir.

### C. Sabitlenmiş tarihsel yollar

Gerçek fiyat yolları kullanılabilir fakat test sırasında canlı sağlayıcıdan çekilmemelidir. Her fixture:

- Kaynak
- Tarih aralığı
- `known_at/as_of`
- Corporate action ayarlaması
- İçerik hash’i

taşıyan değişmez veri paketi olmalıdır.

Kullanıcının gerçek açılış kitabı ayrıca bir acceptance fixture olur; fakat tek test kitabı olamaz. Aksi hâlde motor yalnız bugünkü portföye göre şekillenir.

## 4. `policy_validation_spec` inşa sırasında nereye girer?

Evet, motor kodundan önce yazılmalıdır.

Düzeltilmiş sıra:

1. Capital Policy’nin amaç, sözlük ve provisional parametreleri yazılır.
2. `policy_validation_spec` yazılır ve beklenen davranışlar dondurulur.
3. Policy ve validation spec’i taşıyacak şemalar kurulur.
4. Risk/policy motoru uygulanır.
5. Motor, validation spec’i geçmeden `decision_grade` sayılamaz.
6. Tam kabul raporu üretilmeden policy `active` olamaz.

Dolayısıyla validation spec, risk motorunun yazılmasını değil; **tamamlanmış ve sermaye kararında kullanılabilir sayılmasını** bloklar.

Policy ile spec ayrı olmalıdır:

- `capital_policy`: Yetkili kurallar ve parametreler
- `policy_validation_spec`: Property’ler, fixture’lar, toleranslar ve beklenen sonuçlar
- `policy_validation_report`: Belirli engine/policy/spec sürümlerinin koşu sonucu
- `policy_activated`: Bu üçünün hash’lerine referans veren insan kararı

Referans yönü:

`validation_spec -> policy_version`  
`validation_report -> policy + spec + engine_version + fixture_set`  
`policy_activated -> validation_report`

Policy’nin içine test sonucu yazılmaz; aksi hâlde kural ile kuralın kanıtı birbirine karışır.

## 5. Determinizmin gerçek sınırı

Determinizm LLM’den önce değil, **adjudication’dan sonra** başlar.

Kanonik proposal girdisi şunların sürümlü/hash’li birleşimidir:

- Adjudicate edilmiş readiness
- Onaylı downside case
- Onaylı valuation anchor
- Onaylı driver eşlemesi
- Reconciled pozisyon/nakit snapshot’ı
- Sabit fiyat/FX snapshot’ı
- Capital-policy sürümü
- Açık proposal/execution state’i
- Engine sürümü

Aynı:

`input_manifest_hash + policy_hash + engine_version`

için aynı semantik proposal gövdesi çıkmalıdır. Timestamp, proposal ID ve log metadata’sı bu karşılaştırmaya dahil edilmez.

“Aynı hafta iki kez çalıştırırsam aynı sonuç gelir mi?” doğru soru değildir. Doğru soru:

> İki koşunun kanonik girdi manifestleri aynı mı?

- Aynıysa sonuç aynı olmalıdır; değilse P0 hatadır.
- Fiyat yenilenmiş, LLM yeniden çalışmış veya adjudication değişmişse girdiler farklıdır; sonuç da değişebilir.
- Sistem bu durumda sessiz farklılık değil, input diff göstermelidir.

LLM çıktısı öneridir; adjudicate edilmiş nesne oluşmadan proposal motoruna giremez.

## 6. Süre ve çalışma sıklığı

### İlk kurulum

Validation paketinin ilk sürümü yaklaşık:

- Spec ve altın fixture’lar: 3–5 gün
- Generator/property/state-machine testleri: 3–5 gün
- Replay ve raporlama: 2–4 gün

Toplam: yaklaşık **1,5–2,5 hafta**. Bu, risk motoru çalışmasıyla kısmen paralel ilerleyebilir.

### Sürekli koşular

| Sıklık | İçerik | Hedef süre |
|---|---|---:|
| Her commit | Şema, unit, temel property, altın fixture | 1–3 dakika |
| Merge/nightly | Binlerce property örneği, state-machine, sabit replay | 10–30 dakika |
| Risk/proposal kodu değişince | Tam deterministik suite + eski/yeni çıktı diff’i | 30–60 dakika |
| Her policy sürümünde | Tam suite, duyarlılık matrisi, kabul raporu | 1–2 saat hesap + 2–4 saat insan incelemesi |
| Material policy değişikliğinde | Tam suite + yeni gölge dönem | Değişikliğe göre 1–2 aylık forward gözlem |
| Üç aylık inceleme | Override, counterexample, fixture ve varsayım gözden geçirmesi | Yarım gün |

CI’da property koşuları deterministik seed ile yapılabilir; daha geniş gece koşuları yeni girdiler arayabilir. Bulunan en küçük karşı-örnek kalıcı regresyon fixture’ına çevrilmelidir. Hypothesis sabit seed/derandomized CI, başarısız girdilerin saklanması ve tekrar oynatılması mekanizmalarını doğrudan destekliyor. [Hypothesis resmî dokümantasyonu](https://hypothesis.readthedocs.io/en/latest/settings.html)

Gerçek fiyat verisi regresyon sırasında canlı çekilmemelidir. Veri güncellendiğinde testin kendisi değişmemeli; yeni tarihsel paket ayrı sürüm ve hash ile eklenmelidir. Canlı veri kontrolü ayrı bir integration/surveillance testidir; kanonik policy sonucunu test eden fixture değildir.

En kısa hüküm: **Property testleri motorun kurallara sadakatini, golden fixture’lar kuralların anlamını, tarihsel replay gerçekçi davranışı, gölge koşu ise işletilebilirliği sınar. Dördünden biri diğerinin yerine geçmez.**