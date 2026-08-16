# Portföy işletim sistemi — tasarım

> Dosya adı (`pei-company-lifecycle-tasarim.md`) tarihseldir. Doküman bir
> araştırma ömür döngüsü tasarımı olarak başladı; 2026-08-16'da ürünün
> asıl hedefinin **fon yönetimi** olduğu netleşince kapsamı genişledi.

## Sistem nedir

Bu sistem, tek sahibin kendi sermayesini disiplinli biçimde yönetmek için
kurulan bir **portföy işletim sistemidir**: broker gerçekliğinden pozisyon,
nakit ve NAV üretir; capital policy'ye göre risk sınırlarını hesaplar;
araştırmayı sermaye ihtiyaçlarına yönlendirir; hedef portföy ve işlem
önerileri üretir; gerçekleşen sonuçları performans ve karar kalitesi
açısından ölçer. **Sistem emir iletmez, işlemi onaylamaz veya icra etmez**
-- insan karar verir ve broker'da uygular.

Kapsam dışı: hukuki fon yapısı (dış yatırımcı, katılma payı, ücret, resmi
NAV, saklama), vergi danışmanlığı ve mevzuat uyumu.

Araştırma bu sistemin **alt sistemidir**, merkezi değil. Sermaye kararının
girdilerinden yalnızca biridir.

Durum: dört turluk bir tasarım tartışmasından geçti (2026-08-14 → 08-16).
Hiçbir karar henüz koda dökülmedi.

**Bu dokümanı nasıl okumalı.** Üç katmanı var ve karıştırılırsa yanıltır:

| Bölüm | Ne işe yarar |
|---|---|
| **Geçerli tasarım** (hemen aşağıda) | Bugün doğru olan tek yer. Uygulamaya başlayan buradan okur. |
| **Karar günlüğü** | Tarihsel kayıt: kararlar, gerekçeleri ve *reddedilen alternatifler*. "Neden böyle" sorusu buradan cevaplanır. |
| **Gözden geçirme 1.-4. tur** | Kararların nasıl değiştiği ve hangi kod kusurlarının doğrulandığı. 3. tur skill envanteri, 4. tur fon reframe'i. |

Karar günlüğündeki maddelerin bir kısmı sonradan revize ya da iptal edildi;
her biri yerinde `> **REVİZE EDİLDİ**` veya `> **İPTAL**` notu taşıyor. **Notu
olan bir maddeyi tek başına okumayın.** Çelişki görürseniz Geçerli tasarım
kazanır.

> **4. tur uyarısı.** Karar günlüğü ve 1.-3. gözden geçirme turları
> araştırma-merkezli yazıldı; oralardaki "V1", "ürün sınırı" ve "kapsam
> dışı" ifadeleri 4. turda tersine döndü. Hangi kararın öldüğü, hangisinin
> ayakta kaldığı "Gözden geçirme — 4. tur"da madde madde listelidir.

Ham tartışma kaydı: [docs/tasarim-oturumlari/2026-08-codex-fon-sistemi/](tasarim-oturumlari/2026-08-codex-fon-sistemi/README.md)
(42 tur, tek codex oturumu).

## Neden bu doküman var

`src/adapter/pei_workflow.py`'deki `project()` fonksiyonu, her adayı
`run_id:ticker` ikilisiyle anahtarlıyor (satır ~419). Bu yüzden aynı ticker
(ör. ADBE) farklı idea-generation koşularında tarandığında, her koşu
tamamen ayrı, birbirinden habersiz bir "aday" kaydı oluşturuyor.

Kullanıcı düzenli (haftalık olabilir, kesin değil) idea-generation koşuları
planlıyor. Bu durumda aynı ticker zaman içinde defalarca taranacak ve
"güncel durum" sorusu ("ADBE şu an ne durumda?") belirsizleşiyor.

**Önemli bulgu:** `docs/pei-workflow-orchestrator.md` (2026-08-12, "Onaylanmış
tasarım" damgalı) Bölüm 6'da zaten şu ilke var:

> "Yeni idea-generation koşusu eski sonucu silmez. Adayın güncel bucket'i
> en son onaylı screen olayından, geçmişi ise önceki olaylardan okunur."

Yani ticker-sürekli kimlik zaten onaylı tasarımın bir parçası. Kodun
(`run_id:ticker` anahtarlaması) bu tasarımdan saptığı görülüyor -- muhtemelen
şimdiye kadar tek bir gerçek prodüksiyon run'ı olduğu için bu sapma hiç
görünür olmadı. Bu, yeniden icat etmek değil, tasarıma geri dönmek meselesi.

Ama kullanıcının "içime sinmedi" tepkisi bunun ötesinde: sadece anahtar
değişikliği değil, **tüm ömür döngüsünün** (araştırma -> tez -> portföy/
izleme -> unutulma) net tasarlanmamış olması asıl sorun.

## Gündem (7 başlık, sıralı)

Bu sıra kasıtlı: 1-2-3 (araştırma tarafı) netleşmeden 4-5-6 (portföy/izleme
tarafı) konuşulamaz; 0 ise 1-6'nın hepsinin üzerine oturduğu zemin.

### 0. Candidate / Tez / Portföy pozisyonu / İzleme kaydı ilişkisi

Şu an elimizde **dört ayrı veri modeli** var, aralarındaki geçiş tanımsız:

- **candidate** -- idea-generation'dan doğan araştırma durumu
  (`project()`'in ürettiği, bu oturumda üzerinde çok çalıştığımız nesne).
- **thesis** -- `thesis_opened` olayı + kendi üç ekseni (company/security/
  position, bkz. `docs/pei-workflow.md` Bölüm 1b). Şu ana kadar hiç
  kullanılmadı.
- **portföy pozisyonu** -- tamamen ayrı bir JSON dosyasında
  (`adapter/portfolio.py`, `data/portfolio.json` gibi), gerçek hisse
  adedi/maliyet/güncel fiyat.
  taşıyor.
- **izleme listesi kaydı** -- yine ayrı (`adapter/watchlist.py`).

Sorulacak: bir candidate ne zaman "tez" olur? Tez ne zaman "pozisyon" olur?
Pozisyon kapanınca candidate/teze ne olur? İzleme listesi bunların neresinde
duruyor -- candidate'in bir alt-durumu mu, yoksa tamamen bağımsız bir liste
mi?

### 1. T0 akışı -- tekil koşunun ömrü

Bir ticker kümesi idea-generation'dan geçip A/B/C'ye ayrılıyor.

- A ve B için akış "aşağı yukarı" biliniyor (bugün B->A terfi kapısı,
  otomatik tetikleyici mekanizması kuruldu) ama **tüm if-durumlarına sahip
  miyiz belli değil**.
- **C için hiçbir şey yok** -- şu an sadece `deprioritized` deyip
  bırakıyoruz, bir daha hiç dönülmüyor.

Alt not: bugün kurduğumuz B->A otomatik terfi kapısı (`evaluate_promotion`)
ve "iş kuyruğunda aktif" (`in_progress`) durumu, yeniden tarama ile
çakışırsa ne olacak? (Bir isim T45'te terfi etti, T60'ta yeniden taranırsa
yeni tarama bu terfiyi geçersiz kılabilir mi?)

### 2. Çoklu / kademeli kohortlar

T0'da bir grup, T15'te başka bir grup taranırsa, bu iki bağımsız koşu
birbiriyle nasıl ilişkilenecek? Sonunda hepsi TEK bir portföyde
birleşecek. Aynı ticker iki farklı kohortta (ör. bir sektör taraması ve
bir genel piyasa taraması) aynı anda çıkarsa ne olur?

### 3. Aynı kohortun zaman içinde tekrar taranması

T0'daki grup T60'ta tekrar mı taranır, yoksa yalnız C'ler mi yeniden
değerlendirilir? Sonra ne olur?

### 4. Portföy takibi

İki farklı şey birbirine karışmamalı:
- **Muhasebe:** kaç hisse tutuyorum, ne kadar kâr/zarar (bugün
  `adapter/portfolio.py` bunu yapıyor).
- **Portföy seviyesinde karar:** yeni bir A adayını eklemeli miyim, mevcut
  pozisyonlarla ne kadar korele/yoğunlaşmış olurum -- bu
  `portfolio-risk-management` (eklentide var, hiç kurulmamış skill,
  kataloğumuzda yok).

### 5. İzleme listesi takibi

Pozisyon olmayan ama izlenen isimler zaman içinde nasıl takip edilir?

### 6. Ne portföyde ne izlemede olan isimler

Bunlar sonsuza kadar mı unutulacak, yoksa bir geri-değerlendirme
mekanizması mı olacak?

## Durum

Gündem kullanıcı tarafından onaylandı (2026-08-14); Başlık 0-6'nın hepsi
2026-08-15'te karara bağlandı. Henüz hiçbir karar koda dökülmedi.

Tasarım sırasında iki karar sonradan geçersiz kaldı ve yerinde öyle
işaretlendi: Başlık 1'in C-kovası hatırlatıcısı (Başlık 3 + 6 onu
gereksiz kıldı) ve Başlık 2'nin taramaya bağlı `re-underwrite`
tetikleyicisi (Başlık 3 tezli isimleri taramadan çıkardı; sorumluluk
Başlık 4'e geçti).

Yedi başlık kapandıktan sonra tasarım, uygulamaya geçmeden önce iki turluk
bir gözden geçirmeden geçirildi (2026-08-15).

**1. tur (yedi tur, ilke seviyesi):** kodda doğrulanmış üç somut hasar,
dokuz kararda revizyon, beş tercih sorusu. Revize edilen kararlar yerinde
işaretlendi; hiçbiri tamamen geçersiz kılınmadı.

**2. tur (on tur, mekanizma seviyesi):** olay sözlüğü, defterin fiziği,
eşiklerin veri modeli, skill sözleşmeleri ve insan yüzeyi ele alındı.
Yirmiden fazla kod/config kusuru doğrulandı, bir karar tamamen iptal
edildi (Başlık 4 karar 5), 1. turun beş eksenli modeli üçe indirildi ve
tasarımın altındaki asıl boşluk bulundu: **sermaye politikası yok.**

**3. tur (on beş tur, skill envanteri):** eklentideki 23 skill tek tek
ele alındı; hangisine ihtiyaç var, nerede ve nasıl kullanılır, sisteme
nasıl bağlanır, birbirleriyle ilişkileri ne. Sonuç: 6 çekirdek, 3
koşullu, 1 escalation, 12 gereksiz, 1 meta. Bu tur ayrıca doğrusal
workflow zincirini lead+support modeliyle değiştirdi, `allowed_next`'i
sildi ve **"V1" etiketini geri çekti** -- hedef mimari çizildi ama henüz
hak edilmedi.

> **Bir düzeltme (kullanıcı, 2026-08-16).** Repodaki mevcut koşular
> (idea-generation shortlist'i ve ondan doğan tearsheet/preview/
> initiation/scenario işleri) **deneme koşularıdır; korunması gereken bir
> değer taşımazlar.** Bu doküman mevcudu değil, olması gerekeni tarif
> eder. Bu düzeltmenin bir sonucu var: 3. turda önerilen "platformu şimdi
> kurma, mevcut hattı yamala" tavsiyesi kısmen *"bugünkü sistem gerçek
> analiz üretiyor, onu kaybetme"* öncülüne dayanıyordu. Öncül düşünce
> tavsiyenin bu ayağı da düşüyor; geriye yalnız **"kanıtlanmamış
> soyutlamaları kalıcı veri modeline gömme"** gerekçesi kalıyor -- ki bu
> tek başına da geçerlidir ama daha zayıf bir kısıttır. Üç gölge vaka
> kapısı (aşağıda) bu yüzden korunuyor; "önce yamala" kısmı ise mevcut
> koşuları koruma gerekçesiyle savunulamaz.

**4. tur (on tur, fon çerçevesi):** kullanıcı esas hedefin bir **fon
yönetme sistemi** olduğunu belirtti. Bu, önceki iki turun ürün sınırını
tersine çevirdi: capital policy yokluğu kapsam gerekçesi değil, ilk
tasarım problemidir. Aggregate root `research_case/thesis`ten
`fund/portfolio`ya taşındı; capital policy v0, deterministik risk motoru,
NAV/performans omurgası, `portfolio_proposal` ve icra köprüsü tasarlandı;
inşa sırası fon-önce olarak yeniden yazıldı. Araştırma tarafının üç
turluk birikimi çöpe gitmedi -- **yanlış olan bu katmanların varlığı
değil, ürünün merkezi sanılmalarıydı.**

**5. tur (on tur, sınama ve şema):** capital policy'nin gerçek para riske
edilmeden nasıl sınanacağı (dört kanıt katmanı, A0-A4 yetki merdiveni) ve
tasarımın somut şemaya dönüşü (para/zaman/kimlik/sürümleme kararları, olay
zarfı, SQLite depolama). Turun en değerli çıktısı bir kesim: ~30 şemalık
yüzey, ilk çalışan dilim için **7 tam şema + 3 stub + 1 DDL**'e indirildi.

**6. tur (yedi tur, entegrasyon):** fon ile eklenti skill sisteminin nasıl
konuşacağı. Beş iş teması **tek teknik sınıra** indirildi; `capital_input_
manifest` arayüz nesnesi tanımlandı; adjudication iki aşamaya bölündü
(araştırma hükmü sermaye etkisi görülmeden yargılanır); görünürlük matrisi
ve "sermaye tutarı modele gösterilmez" kuralı kondu; inşa sırası revize
edildi (manuel capital-input katmanı risk motorunun önüne).

## Geçerli tasarım (2026-08-16 itibarıyla)

Bu bölüm dört tasarım turundan sonra ayakta kalan resmi veriyor.
Karar günlüğüyle çelişirse bu bölüm kazanır.

### Temel döngü

Fon sisteminin aggregate root'u `fund/portfolio` ve onun zaman içindeki
sermaye durumudur. Araştırma sisteminin root'u (`research_case/thesis`)
bunun altındadır.

```
mevcut portföy → fırsat/tez seti → hedef portföy → insan onayı
→ işlem önerileri → insan icrası → fill/reconciliation
→ NAV/risk/performans → yeni karar
```

Bu döngü araştırma döngüsünü (`keşif → araştırma → pitch → tez → izleme`)
**kapsar**; tersi doğru değildir.

Bir fon sisteminin on üç birinci sınıf nesnesinden sekizi tasarımda hiç
yoktu, dördü kısmiydi:

| Nesne | Durum |
|---|---|
| `fund/account`, `capital_policy`, `cash_and_flows`, `nav_snapshot`, `risk_exposure/limit`, `portfolio_proposal`, `order_proposal`, `performance/attribution` | **Yok** |
| `security_master`, `transaction/fill`, `position/lot`, `reconciliation/corporate_action` | Kısmi |
| `research_case/thesis/evidence` | Güçlü |

### `config/mandate.json` ikiye ayrılmalı

Bugünkü içerik bir *araştırma mandate*'idir: evren, yön, araç, ufuk,
araştırma ritmi. İçinde pozisyon sayısı (`null`), benchmark (`null`),
sektör limiti, kayıp bütçesi ve ağırlıklandırma ilkesi yok; likidite tabanı
ölçülüp bilinçli olarak uygulanmıyor. Geriye kalan "long only / adi hisse /
ABD listeli" kuralları portföy inşa kuralı değil, **uygunluk** kuralıdır.

Eksik olan `capital_policy`, ürünün sınırı değil **ilk tasarım
problemidir.** (3. tura kadar bu yanlış okundu: "capital policy yok, o
hâlde portföyü kapsam dışı bırakalım" denmişti.)

### Fon değişmezleri

Uygulamada ihlal edilmemesi gerekenler. Araştırma tarafının değişmezleri
ayrıca aşağıda.

1. **Broker**, gerçekleşmiş pozisyon/nakit/fill gerçeğinin; **sistem** ise
   bunların policy meşruiyetinin otoritesidir.
2. Her ekonomik hareket ayrı, tipli ve kaynaklı bir kayıttır; pozisyon,
   nakit, maliyet ve NAV mutable tablolardan değil bu kayıtlardan türetilir.
3. Dış nakit akışları yatırım performansından ayrılmadan getiri
   hesaplanamaz.
4. Her NAV `as_of`, fiyat, FX, nakit ve reconciliation durumunu taşır;
   bayat veya uzlaştırılmamış NAV karar kalitesinde sayılamaz.
5. Her sermaye önerisi belirli bir capital-policy sürümüne ve değişmez
   portföy snapshot'ına bağlıdır; geçmiş kararlar yeni policy ile yeniden
   yorumlanamaz.
6. Deterministik motor **güvenli ağırlık aralığını ve bağlayıcı kısıtları**
   üretir; nihai hedef ağırlığı kendiliğinden seçmiş gibi davranamaz.
7. Policy'ye aykırı öneri insan onayıyla sessizce geçerli hâle gelemez;
   ayrı, gerekçeli ve **süreli** override gerekir.
8. Sistem emir iletmez; onaylanmış sermaye kararı, işlem niyeti, broker
   emri ve fill birbirinden ayrı gerçeklerdir.
9. Kanonik gerçek **fill**'dir; emir miktarı veya onaylanan miktar
   gerçekleşmiş pozisyon sayılamaz.
10. Plan dışı işlem reddedilemez çünkü gerçektir; fakat `unadjudicated`
    sayılır ve meşruiyet kurulana kadar yeni risk artırımı bloke edilir.
11. Reconciliation tek boolean değildir; pozisyon, nakit, işlemler, maliyet
    temeli ve kurumsal işlemler ayrı ayrı uzlaştırılır.
12. Reconciliation farkı geçmişi değiştirerek kapatılamaz; eksik fill,
    kurumsal işlem veya düzeltme olayı eklenir.
13. Nakit muhasebede birinci sınıf varlık, tahsiste meşru residual'dır;
    fikir yoksa yatırım zorunluluğu yoktur.
14. Kayıp bütçesi **stop-loss değildir**; pozisyon açılmadan önce uygulanan
    boyutlandırma sınırıdır.
15. Fiyat düşüşü veya drawdown otomatik satış üretemez; inceleme, ekleme
    dondurması veya yeni sermaye kararı tetikler.
16. Policy sıkılaştırması hemen uygulanabilir; **gevşetme** sürümlü,
    gerekçeli ve bekleme sürelidir.
17. P&L, tez doğruluğu ve karar kalitesi ayrı gerçeklerdir; biri diğerinden
    türetilemez.
18. Counterfactual yalnız karar anında dondurulmuş alternatif için
    ölçülebilir; sonradan seçilmiş kıyas geçersizdir.
19. Performans sonucu capital policy'yi otomatik değiştiremez; yalnız insan
    incelemesine sinyal üretir.
20. **LLM kaldırıldığında** fon daha az açıklayıcı olabilir; ama muhasebe,
    risk, NAV, policy uyumu ve icra gerçekliği daha az doğru olamaz. Bu,
    mimarinin bağımsızlık testidir.

### Capital policy v0

Bir anlatı belgesi değil, **sermaye kararlarının çalıştırılabilir
anayasası**. Güncel NAV, nakit, pozisyon, fiyat ve aktif tezler policy'ye
yazılmaz -- onlar portföy state'idir; policy yalnız o state üzerinde hangi
kararların meşru olduğunu tanımlar. `null` bir politika değildir: her alan
ya gerçek bir değer ya `not_applicable` / `unbounded_by_policy` /
`disabled` gibi açık bir hüküm taşır.

| Bölüm | Asgari alanlar | Yoksa sistem neyi veremez |
|---|---|---|
| Kimlik/yürürlük | `policy_id`, `version`, `effective_from`, `status`, `owner` | Bir kararın hangi kuralla alındığı ve replay sonucu bilinemez |
| Amaç/ufuk | `objective: absolute_return`, underwriting ufku, karar kadansı, `change_required:false` | Aylık bakışın neden aylık işlem olmadığı açıklanamaz |
| Uygun yatırım | long_only, common_stock_only, us_listed, leverage/shorting/options: false | Önerinin mandate uygunluğu doğrulanamaz |
| Nakit | `full_investment_required`, `operational_cash_floor`, `cash_target`, `cash_ceiling` | "Bu nakit kullanılmalı mı" cevaplanamaz |
| Kapasite | `max_active_positions`, minimum sayının niteliği, izleme bütçesi | Yeni pozisyonun operasyonel kabulü bilinemez |
| Yoğunlaşma | `max_issuer_weight`, `max_sector_weight`, related-issuer toplama | Portföy-fit ve limit ihlali hesaplanamaz |
| Boyutlandırma | `base_weight_formula`, readiness sınıfları/çarpanları, `min_economic_weight`, `max_position_weight` | "Ne kadar" sorusu cevaplanamaz |
| Kayıp/risk bütçesi | pozisyon başına `scenario_loss_budget_bps_nav`, portföy stres eşiği, downside girdisi zorunluluğu | Savunulabilir üst pozisyon büyüklüğü üretilemez |
| İşlem politikası | review kadansı, no-trade bandı, minimum ekonomik işlem, zorunlu işlem istisnaları | Hangi hedef farkının işlem doğuracağı bilinemez |
| Ölçüm referansı | `base_currency`, resmi NAV zamanı, fiyat/FX kaynağı, performans yöntemi | Ağırlık, risk bütçesi ve performans ortak paydaya oturmaz |
| Değişiklik/override | onay yetkisi, cooling-off, acil override süresi, geriye yürümeme | Limit değişikliği ile gerçek karar birbirine karışır |

**Boyutlandırma — conviction değil "underwriting readiness".** Pitch'in
"high confidence" demesi doğrudan daha büyük pozisyon yaratmaz.

```
base_weight       = deployable_capital_fraction / max_active_positions
readiness_weight  = base_weight × readiness_multiplier

policy_compliant_max_weight = min(
    readiness_weight, thesis_downside_capacity, gap_capacity,
    issuer_capacity, sector_capacity, cash_capacity,
    liquidity_capacity, max_position_weight)
```

Readiness merdiveni: `watchlist 0×` / `starter 0.5×` / `core 1.0×` /
`exceptional ≤1.25×` (V0'da kapalı olması makul). Eğim yalnız typed
kanıttan türetilir (kabul edilmiş aktif tez, destekli ve güncel valuation
anchor, tanımlı downside, onaylı izleme sözleşmesi, maddi veri boşluğu yok,
yoğunlaşma kontrol edilmiş, pozisyon state'i biliniyor). **Readiness
çarpanı hiçbir hard risk limitini genişletemez.**

Kayıp bütçesi kapasitesi: `downside_capacity_weight =
allowed_position_loss_bps / |downside_return|`. Downside tahmini zayıfsa
bütçe büyütülmez; ağırlık küçültülür veya isim watchlist'te kalır.

**Nakit:** muhasebede birinci sınıf pozisyon, tahsiste meşru residual. Beş
uygun isim varsa ağırlıkları %100'e normalize etmek yanlıştır; boş kapasite
nakitte kalır. Yüksek nakit uyarı üretebilir, otomatik yatırım zorunluluğu
doğurmaz.

**Pozisyon sayısı:** hard minimum yok (düşük kaliteli isim almaya zorlar);
hard üst sınır var ve izleme kapasitesinden türetilir. Çeşitlendirme,
minimum isim sayısıyla değil tek-isim/sektör tavanları ve nakde kalma
serbestliğiyle sağlanır.

**İşlem eşiği (histerezis).** Mandate'in kendi yazılı gerilimini (3-18 ay
ufuk vs aylık ritim) çözen mekanizma budur:

```
band_half_width = max(absolute_weight_threshold,
                      relative_threshold × target_weight)
trade_candidate = |current_weight - target_weight| > band_half_width
```

Üstüne minimum ekonomik büyüklük ve maliyet vetosu gelir; `broken`/`closed`
tez, hard limit ihlali ve risk düzeltmesi bandı geçersiz kılar.
*Aylık ritim yeniden karar verme ritmidir, yeniden işlem yapma ritmi
değildir.*

**Değişiklik yönetişimi.** Policy'nin sahibi yalnız kullanıcıdır; sistem
öneri üretebilir, etkinleştiremez. Akış: `değişiklik önerildi → mevcut
kitap etkisi önizlendi → cooling-off → insan onayı → etkinleşti`. Geriye
yürümez. Sıkılaştırma hemen, gevşetme bekleme süresiyle. **Mevcut bir
ihlali "yok etmek" için limit gevşetilemez.** Acil istisna policy
değişikliği değil, dar kapsamlı ve süreli `policy_override`'dır. Önerilen
ritim: üç aylık planlı policy incelemesi; aylık portföy incelemesinde
policy tartışılmaz, yalnız uygulanır.

### Hedef portföyü kim kurar

Üç katman, sınırlar net:

| Katman | Ne yapar |
|---|---|
| **Deterministik güvenlik çekirdeği** | `eligible_weight_band`, `policy_compliant_max_weight`, `binding_constraints`, no-trade bandı, limit ihlalleri, işlem listesi |
| **Analitik yargı** (araştırma) | Downside'ın makullüğü, gizli faktör örtüşmesi, valuation güvenilirliği, fırsat maliyeti, veri boşluklarının büyüklüğü |
| **İnsan** | Readiness ve downside girdisini kabul, trade-off'u çözme, nihai hedef onayı veya gerekçeli override |

*LLM sermaye miktarını keyfî belirlemez; matematik de fırsat maliyetini
çözmüş gibi davranmaz.* Tam otomatik hedef portföy için ortak bir beklenen
getiri dağılımı, kovaryans modeli ve açık optimizasyon amacı gerekirdi --
üçü de yok.

**Fırsat maliyeti: replacement hurdle.** Mevcut pozisyon statüko avantajına
sahiptir; yeni aday yalnız "iyi" olduğu için değil, **finanse edeceği
pozisyondan belirgin biçimde daha iyi** olduğu için yer açabilir. Bütün
investable set'i tek puana sıralamak sahte hassasiyet olur. Aday hurdle'ı
geçmiyorsa sonuç otomatik `retain_incumbent`; geçiyor ama trade-off varsa
insan karar verir. Veri karşılaştırılamıyorsa `indeterminate`, işlem yok.

**`portfolio_proposal`** kimlik/geçerlilik, sabitlenmiş girdiler
(policy ref + hash, portföy snapshot, market snapshot, research snapshot,
calculator version, eksik/bayat girdiler), security bazında mevcut ve hedef
durum (binding constraints ve kullanılmayan kapasite gerekçesi dâhil),
portföy düzeyi toplamlar, geçiş/işlem etkisi (band, turnover, maliyet,
nakit etkisi), limit kontrolleri ve karar alanlarını taşır. Alternatifler
**sınırlı**: her zaman `status_quo`, birincil öneri, ve yalnız maddi
trade-off varsa en fazla bir-iki tane. *Onlarca optimize portföy sunmak
insan kapısını karar tiyatrosuna çevirir.*

**Tetikleyiciler.** Takvim bir *review* tetikler; her review proposal
üretmez. Aylık inceleme varsayılan `no_change`. Takvimi beklemeyenler:
fonlanmış tezin `broken`/`closed` olması, hard limit ihlali, pozisyonun
uzlaştırılamaması, kurumsal işlem, büyük dış nakit akışı, yeni policy
sürümü, fill sonrası proposal'ın state ile uyumsuzlaşması.
`position_unknown` durumunda yeni sermaye proposal'ı üretilmez.

### Risk

Long-only, hedge/short/kaldıraç yoksa risk yalnız **neyi tuttuğun, ne kadar
tuttuğun, toplam ne kadar yatırımda olduğun ve ne zaman azalttığın**
üzerinden yönetilir. Ama araçların az olması ölçülmesi gereken risklerin az
olduğu anlamına gelmez: çözüm ayrı bir LLM değil, portföy çekirdeğinin
içinde deterministik bir `risk_engine`.

- **Ortak sürücü riski** faktör modeli olmadan: kontrollü bir
  `risk_driver_registry` (portföyde gerçekten görülen 8-15 maddi sürücü) +
  pozisyon bazında driver exposure. LLM etiket önerebilir, kanonik eşlemeyi
  insan kabul eder. Yanına rolling korelasyon: **driver nedensel hipotez,
  korelasyon ampirik alarmdır.** Sektör limitleri hard, driver yoğunlaşması
  V0'da soft review.
- **Drawdown** otomatik satış üretmez, **zorunlu yeniden inceleme**
  tetikler. Dış nakit akışlarından arındırılmış TWR wealth index üzerinden
  hesaplanır. Dondurma fiyat toparlandı diye değil, inceleme bitince kalkar.
- **Gap/kuyruk riski** ayrı bir kapasite kısıtıdır: `gap_capacity_weight =
  allowed_gap_loss_bps / |assumed_gap_return|`. `max_position_weight` sıfıra
  gidişte mutlak kaybı sınırlar; gap kapasitesi daha gerçekçi bir −%30/−%40
  olayında bütçenin ne kadarının kullanıldığını gösterir. İkisi birbirinin
  alternatifi değildir.
- **Geçici varsayımlar** typed olmalı (`policy_assumption`: predicate,
  gözlenen değer, kaynak, review vadesi, yeniden değerlendirme olayları,
  başarısızlık aksiyonu). "Likidite uygulanmıyor" kalıcı hüküm olarak
  yanlıştır; doğrusu "mevcut NAV ve hedef büyüklüklerde bağlayıcı değildir"
  -- ve bu ölçülebilir bir varsayımdır.
- **Stop-loss yok.** Fiyat stop'u gap riskini koruyamaz ve 3-18 aylık bir
  ufukta piyasa gürültüsünü tez bozulmasıyla karıştırır. Fiyatın meşru rolü
  `price_move_review_required` tetiklemektir; hedefi sıfıra indiren şey
  fiyat değil, hard gerçeklerdir (delisting, fraud, solvency, tez
  `broken`/`closed`, policy ihlali).

### Performans ve hesap verebilirlik

Üç ayrı gerçek asla tek "başarı" puanında birleşmez:

| Gerçek | Ölçüsü |
|---|---|
| Para ne yaptı | TWR (strateji), MWR/XIRR (sahip deneyimi), P&L, drawdown |
| Tezde öngörülen dünya gerçekleşti mi | `supported` / `partially_supported` / `falsified` / `unresolved` / `not_testable` |
| Karar o anda kaliteli miydi | Ex-ante süreç kalitesi kontrol listesi |

Bundan süreç×sonuç matrisi çıkar: *iyi süreç + kötü sonuç* = downside
kalibrasyonu incelenir; *kötü süreç + iyi sonuç* = şanslı kötü karar,
yöntem ödüllendirilmez.

**Benchmark yasağı ile referans yasağı aynı şey değildir:** *benchmark*
(aktif ağırlık ve tracking error'ı yöneten bağlayıcı karşılaştırma --
mandate yasaklıyor), *hurdle* (aşılması beklenen minimum -- gerekli),
*context series* (endeks, enflasyon -- yalnız bağlam). Sistem
`active_return`, `alpha` veya "endeksi yendi" dili kullanmaz.

**Attribution** üç eksende: pozisyon (fiyat, temettü, FX, maliyet; nakit de
ayrı satır), tez (fonlanma, ağırlıklı gün, P&L, drawdown, outcome sınıfı),
ve karar (`decision_evaluation_contract` ile dondurulmuş statüko
karşı-olgusu). Çoklu işlemde sahte tek-isim nedenselliği kurulmaz; paket
`decision_bundle` olarak statükoya karşı değerlendirilir.

**Counterfactual** yalnız karar anında dondurulmuşsa izlenir; sonradan
kazanan isim seçilmez. Sunum dili "kaçırdığın kazanç" değil, **kural
kalitesi**dir.

**Küçük örneklemde** (yılda 10-20 karar) öncelik sırası: (1) muhasebe ve
policy bütünlüğü -- bir geçiş kapısı, (2) süreç uyumu -- erken dönemin ana
öğrenme kaynağı, (3) finansal sonuç -- zorunlu raporlanır ama tek başına
policy'yi değiştiremez. Kural ya uygulanmıştır ya uygulanmamıştır; bu
küçük örneklemde de kesindir.

Geri besleme otomatik değildir: performans katmanı `calibration_signal` /
`policy_review_signal` / `process_breach` / `data_quality_issue` üretir;
policy değişikliği yine cooling-off ve insan onayından geçer.

### İcra köprüsü

Üç gerçek karıştırılmaz: **karar niyeti** (onaylanan hedef ağırlık ve risk
sınırı), **insan icrası** (broker'a gerçekte ne girildiği), **broker
gerçeği** (ne, kaç adet, hangi fiyattan gerçekleşti).

> Broker pozisyonun **varlığında** otoritedir; sistem pozisyonun
> **meşruiyetinde** otoritedir.

- İnsan **ağırlık bandını** onaylar; adet icra anında güncel NAV/fiyatla
  türetilir. Ama proposal bir `validity_contract` taşır (fiyat bandı,
  ağırlık bandı, azami nakit etkisi, azami downside, gerekli policy sürümü,
  geçersizlik olayları) ve aşılırsa `reapproval_required` olur.
- **Plan dışı işlem** reddedilemez ama normalleştirilmez: pozisyon açık,
  `policy_state: unadjudicated`, tez bağı yok, kayıp bütçesi
  değerlendirilmemiş. Yeni risk eklemek bloklanır. Sonradan tez bağlanırsa
  `linked_post_execution: true` kalır; geçmişe onay uydurulmaz.
- **Her fill ayrı kanonik kayıttır**; toplulaştırma yalnız projection.
  Kısmen dolup iptal edilmek başarısızlık değil, terminal bir execution
  outcome'dur -- ama ayrıca `implementation_status: target_not_reached`
  doğurur.
- **Reconciliation tek boolean değildir**: pozisyon, nakit, işlemler,
  maliyet temeli ve kurumsal işlemler ayrı ayrı, her biri kendi `as_of`'uyla.
  Uyuşmazlıkta sistem eski olayı değiştirmez; `discrepancy` durumu kalır ve
  yeni risk bloklanır.
- **Nakit/temettü/ücret** farktan tahmin edilmez; broker activity/statement
  export'u ayrıştırılır. Kaynağı bilinmeyen fark `unexplained_cash_
  difference` olur ve attribution tamamlanmaz.

Manuel köprünün yükü haftada ~0,5-1,5 saat (yoğun haftada 1,5-2,5). Yükü en
çok azaltan tek yatırım: **broker CSV/OFX export'unu idempotent biçimde
içeri alan, satırları typed fill/cash activity'ye çeviren ve insana yalnız
uyuşmazlıkları gösteren importer.**

### Araştırma ↔ sermaye geri beslemesi

> Araştırmanın önceliğini merak değil **risk altındaki sermaye** belirler;
> discovery ise bugünkü sermayeyi korumak için değil, yarının fırsat
> maliyetini görünür tutmak için korunan bir bütçe alır.

Kuyruk leksikografiktir: **R0** sermaye gerçeği bilinmiyor · **R1**
fonlanmış sermayede acil kayıp riski · **R2** fonlanmış pozisyonda yakın
karar · **R3** açık proposal'ı bloklayan soru · **R4** investable
challenger · **R5** yeni discovery.

Kapasite paylaşımı portföy moduna göre (operasyon süresi düşüldükten sonra
kalan araştırma bütçesinin oranı): `defensive` %100/%0 · `book_maintenance`
%80/%20 · `balanced` %70/%30 · `deployment` %50/%50. Discovery en fazla iki
ardışık hafta tamamen preempt edilebilir; sonrasında korunan minimum blok
gelir.

Dört küme: `universe → policy_eligible_universe →
underwritten_investable_set → capital_actionable_now → funded_portfolio`.
Pozisyon tavanının dolu olması bir ismi investable set'ten çıkarmaz; yalnız
`capital_actionable_now` olmasını replacement kararına bağlar.

**VOI kapısı:** pahalı her araştırma işi küçük bir sözleşme taşır (karar
nesnesi, son tarih, mevcut belirsizlik, olası bulgular ve her bulgunun
sermaye etkisi, risk altındaki sermaye, gereken kanıt, tahmini efor, durma
koşulu). Ordinal yeterli: `decision_impact` / `decision_changeability` /
`effort`. Kural: **araştırma sonucunda kararın değişmesi şart değildir;
başlamadan önce makul sonuçlardan en az birinin kararı değiştirebilmesi
şarttır.** `decision_impact: none` → çalışma açılmaz.

Kitap doluyken discovery'nin amacı on birinci pozisyonu eklemek değil,
**onuncunun hâlâ sermayeyi hak ettiğini sınayacak opsiyonellik üretmektir.**

### Araştırma ↔ fon sınırı

Fon ile eklenti arasında **tek bir sınır** vardır. Fon bir skill istemez, bir
*karar girdisi* ister.

```
fon olayı / karar ihtiyacı
   → research_work_request        (capability ister: downside_case.v1)
   → araştırma orkestratörü        (lead/support seçimi burada)
   → provisional artefakt
   → contract + kaynak doğrulaması
   → İNSAN KAPISI 1               (araştırma hükmü, sermaye etkisi görülmeden)
   → kanonik sürümlü capital input
   → capital_input_manifest        (karar anında mühürlenir)
   → deterministik risk/proposal motoru
   → İNSAN KAPISI 2               (portföy etkisi ve sermaye kararı)
```

**Fon skill adı bilmez.** `requested_capability` bir domain çıktısıdır
(`downside_case.v1`, `valuation_anchor.v1`, `thesis_assessment.v1`); hangi
skill'in cevaplayacağına araştırma orkestratörü karar verir ve gerekçesini
`research_work_routed` ile kaydeder. Fon şemaları skill adı taşımaz; skill
ve model kimliği yalnız provenance'da görünür.

**İki aşamalı adjudication.** Kullanıcı önce araştırma hükmünü *sermaye
sonucunu görmeden* yargılar; ancak kaydedildikten sonra sistem yeni downside
kapasitesini, eligible bandı ve olası proposal etkisini gösterir. Aksi hâlde
kullanıcı kabul edeceği downside'ın kendisini satışa zorlayacağını görüp
analitik hükmü yumuşatır. Aşama 1'de görülmeyenler: pozisyon ağırlığı, P&L,
ortalama maliyet, önerilen trade, `capital_at_risk`.

**Sermaye tutarı modele gösterilmez.** "82 bp risk altında" demek downside
analizini iyileştirmez, modeli pozisyonu savunmaya teşvik eder. Sermaye
riski yalnız orkestratörün öncelik, güvence (assurance tier) ve maliyet
kararını etkiler; ciddiyet `decision_deadline` ve `reliance_class` ile
anlatılır.

**Görünürlük** skill adına değil `(skill, execution_role,
requested_capability, assessment_mode)` bileşimine bağlıdır. Kapalı
profiller: `none` / `funded_flag_only` / `position_context` /
`portfolio_exposure_context`. Pitch, tracker, deep-dive, comps, tearsheet ve
idea-generation fon durumunu **görmez**; yalnız `portfolio-risk-management`
ve `economic-impact-report`'un portföy overlay modu görür -- o da P&L ve
ortalama maliyet olmadan (sunk-cost yanlılığı).

**Anchoring için üç assessment modu:** `de_novo` (önceki hüküm
gösterilmez -- pitch), `update_against_prior` (değişimi ölçmek için önceki
hüküm zorunlu -- tracker), `independent_then_reconcile` (önce bağımsız
üretilir, ikinci geçişte mevcut kabul edilmiş nesneyle farkı açıklanır --
karar-kritik downside/valuation).

**`capital_input_manifest`** security başına, belirli bir anda geçerli kabul
edilmiş araştırma girdilerini exact sürüm ve digest'leriyle bağlayan
immutable bir manifesttir. Bileşenleri: thesis version, readiness kararı,
downside case, valuation anchor, driver exposure set, monitoring
contract/status. **Tek bir `manifest_valid` bayrağı yoktur** -- manifest
kısmen kullanılabilir olabilir (hard-limit trim için yeterli, yeni risk için
yetersiz). Her bileşen kendi freshness durumunu taşır (`current` /
`review_due` / `stale` / `superseded` / `invalidated` / `disputed` /
`missing`).

Önemli ayrım: **güncel fiyat `valuation_anchor`'ın parçası değildir** --
anchor yöntem/varsayım taşır, fiyat market snapshot'tan gelir,
`capital_actionability` ikisinin karşılaştırmasından türer. Bu yüzden fiyatın
günlük değişmesi readiness'i günlük bozmaz.

Manifestin içeriği türetilir; **karar anındaki örneği mühürlenir.** Böylece
eski bir proposal "bugün araştırma ne diyor" sorusunu değil, "o karar
verilirken sistem tam olarak ne biliyordu" sorusunu cevaplar.

**Açılış kitabı** (`legacy_hold_only`): tezi, readiness'i ve downside'ı
olmayan pozisyonlar için `policy_compliant_max_weight` sıfır değil
**`not_computable`** olur; mevcut ağırlık hedef sayılmaz; yeni alım
bloklanır; hard-limit ihlali varsa trim üretilir; ama **yalnız araştırma
eksik diye otomatik satış üretilmez.** Normalleşme `onboarding_underwrite`
ile olur -- ayrı bir skill değil, pitch'in bir execution mode'u; *sunum
genişliği azaltılabilir, kanıt standardı azaltılamaz*; en fazla `starter`
readiness verir.

**Eksik girdi × mümkün aksiyon:** statüko her durumda mümkündür (ama bu bir
*hold tavsiyesi* değil, yalnız mevcut gerçekliği değiştirmeyen seçenek);
hard-limit trim her durumda mümkündür; yeni pozisyon/artırma tez, readiness,
downside, anchor veya monitoring eksikse **bloklanır**; replacement hükmü
bloklanır; exit ise eksiklik nedeniyle otomatik üretilmez.

### İnşa sırası

Varsayımlar: tek broker hesabı, tek sahip, ~10 pozisyon, EOD değerleme,
resmi fon muhasebesi/vergi motoru yok, broker'dan en azından yapılandırılmış
CSV/OFX alınabiliyor (yalnız PDF varsa süreler uzar).

> **SIRA REVİZE EDİLDİ (6. tur).** Manuel capital-input katmanı risk
> motorunun **önüne** taşındı ve eski Adım 8 ikiye bölündü. Gerekçe: aksi
> hâlde risk motoru, hesaplaması gereken readiness/downside girdilerinin
> yalnız ileride kurulacak plugin'den gelebileceğini varsayar ve "LLM'siz
> fon çekirdeği" bağımsızlık testi bozulur.
>
> Yürürlükteki sıra: **0** policy · **1** defter · **2** açılış kitabı +
> importer · **3** NAV/performans · **4 (yeni)** sağlayıcı-bağımsız
> capital-input substrate (manuel authoring, doğrulama, iki aşamalı
> adjudication, `capital_input_manifest`) · **5** risk motoru · **6**
> proposal ve karar kapısı · **7** icra köprüsü *(← "kötü de olsa fon"
> eşiği burada)* · **8** attribution · **9** `research_work_request` +
> routing + episode + provenance · **10** ilk skill adapter (`comps-
> valuation`) + gölge koşu · **11** pitch–tez–tracker lifecycle · **12**
> discovery.
>
> Aşağıdaki tablonun "bitti" tanımları geçerliliğini korur; yalnız adım
> numaraları kayar ve iki yeni adım eklenir.

| # | Adım | Neden bu sırada | "Bitti" tanımı | Tahmin |
|---:|---|---|---|---:|
| 0 | **Fon sözleşmesi + Capital Policy v0** | Sonraki bütün hesapların neyi doğru sayacağı buna bağlı | Policy'de sessiz `null` yok; örnek üç karar deterministik pass/fail oluyor; gevşetme yönetişimi tanımlı | 3-5 gün |
| 1 | **Kanonik finansal omurga** | Gerçek para state'i güvenilir olmadan NAV veya karar kurulamaz | Aynı import iki kez duplicate üretmiyor; crash/replay aynı state'i veriyor; iç karar ile dış broker gözlemi ayrı | 1-2 hafta |
| 2 | **Açılış kitabı + broker importer** | Sistem önce gerçekte neye sahip olduğunu bilmeli | Gerçek ekstre iki kez güvenle içeri alınabiliyor; pozisyon/nakit eşleşiyor; açıklanamayan fark görünür ve yeni riski blokluyor | 1-2 hafta (PDF-only: +1-2) |
| 3 | **NAV ve temel performans** | Ağırlık, kayıp bütçesi ve performans aynı NAV paydasına dayanır | Elle hesaplanan fixture ile NAV/TWR/MWR eşleşiyor; para yatırma TWR'ı bozmuyor; eksik fiyat sessiz geçmiyor | 1-2 hafta |
| 4 | **Deterministik risk engine** | Proposal ancak mevcut kitabın risk kapasitesi biliniyorsa üretilebilir | Aynı snapshot aynı `portfolio_risk_snapshot`ı veriyor; gap/limit/driver/assumption test vakaları doğru alarm üretiyor | 1-2 hafta |
| 5 | **Portfolio proposal + karar kapısı** | Fonun asıl ürünü mevcut kitaptan hedef kitaba geçiş kararıdır | Snapshot'tan `no_change` veya gerekçeli proposal çıkıyor; hard limit aşılmıyor; onaysız proposal sermaye state'ini değiştirmiyor | 1-2 hafta |
| 6 | **İcra köprüsü + operasyon yüzeyi** | Karar gerçek dünyaya güvenle bağlanmadan fon yönetilemez | `snapshot → proposal → onay → ticket → fill import → reconciliation → yeni NAV` uçtan uca; partial/unplanned senaryolar kaybolmuyor; recovery provası geçiyor | 2-3 hafta |
| 7 | **Attribution ve hesap verebilirlik** | Temel fon çalıştıktan sonra karar kalitesi ölçülebilir | Bir replacement kararı statükoya karşı, bir tez para/claim/process eksenlerinde değerlendirilebiliyor | 2-3 hafta |
| 8 | **Araştırma–sermaye arayüzü** | Araştırmanın çıktısı doğrudan LLM eylemi değil, adjudicated capital input olmalı | Risk olayı research task açıyor; kabul edilen sonuç weight bandını yeniden hesaplatıyor; research target'ı doğrudan değiştiremiyor | 1-2 hafta |
| 9 | **Kanıt–pitch–tez–tracker dikey dilimi** | Fon omurgası kanıtlandıktan sonra araştırma otomasyonu sermayeye bağlanabilir | Üç gölge vaka geçiyor; kabul edilen pitch investable set'e giriyor; tracker yeni tez açamıyor; eksik kanıt fail-closed | 3-5 hafta |
| 10 | **Discovery ve ölçekleme** | Yeni fikir hacmi ancak bütün downstream döngü çalışınca güvenli | Discovery araştırma adayı üretir ama sermaye kararı üretmez; dolu kitapta minimum opsiyonellik sürer | 2-3 hafta |

> **Daraltma (5. tur).** Capital policy bütün altyapıyı bloklamaz. Dört
> kullanıcı kararı policy'nin **etkinleştirilmesini**, risk motorunu ve
> proposal üretimini bloklar; `core-types`, olay zarfı, SQLite DDL, açılış
> durumu şeması ve kabul fixture'ları cevap beklemeden yazılabilir.
> `policy_validation_spec` ise policy yazıldıktan sonra ve motor
> kodlanmadan önce hazırlanır -- motorun yazılmasını değil, **karar
> kalitesinde sayılmasını** bloklar.

**Sistem Adım 6'dan sonra "kötü de olsa bir fon"dur.** O noktada araştırma
girdileri hâlâ elle girilebilir, ama sermaye döngüsü kapalıdır: sistem
sermayeyi ve nakdi bilir, NAV ve performansı ölçer, policy ve risk
sınırlarını uygular, hedef portföy önerir, insan onayını kaydeder, ticket
üretir, gerçek fill'leri alır, broker ile uzlaştırır, yeni state'i yeniden
değerler. **İlk gerçek para ancak Adım 6'nın dry-run ve recovery testleri
geçtikten sonra bu sistemle yönetilmelidir.**

Süre: minimum fon omurgası **8-11 hafta** (iyi broker export'uyla; dağınık
veriyle 10-14). Fon + tek araştırma dikeyi **16-24 hafta**. C1-C18 ile
F1-F18'in tamamının üretim kalitesinde olgunlaşması 24-36 hafta ve
sonrasında sürekli bakım.

Fon omurgasının kavramsal belirsizliği araştırma omurgasından düşüktür
(muhasebe, NAV ve limitler deterministiktir) ama hata toleransı çok daha
düşüktür: import idempotency, reconciliation, cash flows, partial fills ve
recovery testleri ciddi süre alır.

**Yetki kademeli olmalı.** En az bir tam broker uzlaştırması ve iki gölge
proposal döngüsü görülmeden mevcut portföyü sırf yeni sistem öyle hesapladı
diye topluca yeniden kurmak tehlikelidir: önce gerçeği doğru kaydet, sonra
kararları gölgede üret, en son küçük ve geri döndürülebilir sermaye
değişiklikleriyle güven kazan.

---

## Araştırma alt sistemi

Aşağıdaki bölümler ilk üç turun ürünüdür ve **geçerliliğini korur** --
yalnız yeri değişti: bunlar ürünün merkezi değil, sermaye kararını besleyen
alt sistemdir. Yanlış olan bu katmanların varlığı değil, ürünün merkezi
sanılmalarıydı.

### Değişmezler (araştırma tarafı)

Bunlar iki turda da ayakta kaldı ve uygulamada ihlal edilmemeli.

1. **Tek mantıksal gerçeklik kaynağı.** Tek otoritatif olay akışı; tez
   görünümü ondan türetilir, ikinci bir defter kurulmaz. Fiziksel olarak
   tek dosya olmak zorunda değil.
2. **Analiz paralel, commit seri.** Dilimler aynı anda LLM çalıştırabilir;
   olayların deftere eklenmesi tek yazarlı, atomik bir kapıdan geçer.
3. **Gerçek alım/satımı yalnız insan yapar.** Sistem hiçbir koşulda emir
   üretmez.
4. **İşlem kaydı yokluğundan `flat` türetmek yasaktır.** Üç ayrı durum:
   `open_position`, `confirmed_flat_as_of`, `position_unknown`. Sonuncusu
   portföy kararını bloklar.
5. **İzlenemeyen açık tez yasaktır.** Ölçülebilir eşiği olmayan tez
   açılabilir, ama onaylanmış bir izleme sözleşmesi (metinsel koşul +
   `next_review_due` + azami sessizlik süresi) olmadan açılamaz.
6. **`no_deviation` "tez sağlıklı" demek değildir.** Sistem yalnız
   ölçebildiği altkümede sessizdir; vadesi gelen nitel kontrol yapılmamışsa
   sonuç `no_deviation` olamaz, `incomplete`/`indeterminate` olur.
7. **`approved` analitik doğruluk anlamına gelmez.** Üç ayrı kapı var:
   makine doğrulanabilir (otomatik), analitik yargı (insan kabulü), gerçek
   dünya icrası (asla otomatik değil).
8. **Her A/B/C hükmü karşılaştırma kümesi kimliği taşır.** Dilim-göreceli
   ya da batch-göreceli bir hüküm, evren-geneli hüküm gibi sunulamaz.
9. **Tez açma yetkisi yalnız pitch'tedir.** İzleme/tracker mevcut tezi
   güncelleyebilir, yeni tez açamaz.
10. **Bir ticker = tek kayıt, aynı anda tek açık tez.** `thesis_opened`'ın
    idempotency anahtarı onu doğuran pitch olayının kimliğidir.

### Tez modeli (üç eksen)

İlk turdaki beş eksenli model ikinci turda sadeleştirildi: eksenlerin bir
kısmı aynı varlığa ait değildi (`actual_exposure` bir portföy gerçeği,
`recommended_action` tarihli bir değerlendirme).

| Gerçek | Değerler |
|---|---|
| **Tez durumu** | `active` / `review_required` / `broken` / `closed` |
| **Gerçek exposure** | uzlaştırılmış `long`/`flat` veya `unknown` (+ miktar, as-of) |
| **Tarihli değerlendirme** | `add`/`hold`/`trim`/`exit`/`re-underwrite` (+ geçerlilik tarihi) |

Diğerleri türetilir: `broken` tez + sıfır olmayan exposure = *wind down*;
`active` tez veya sıfır olmayan/bilinmeyen exposure = *izleme zorunlu*; son
kabul edilmiş pitch/re-underwrite = *security readiness*.

`thesis_opened` V1'de **"resmî, kanıt ağırlıklı ve izlenebilir bir yatırım
görüşü oluştu"** demektir -- birinci turda konduğu gibi "sermaye
karşılaştırmasına kabul kapısı" değil. Capital policy olmadığı için o kapı
var olmayan bir odaya açılıyordu.

### Skill mimarisi

**Doğrusal zincir bırakıldı.** Eklentinin kendi yönlendirme felsefesi
(`shared/plugin-routing-map.json`) "ilk gerçek yatırım hükmünün sahibi bir
*lead* skill seçilir, destek skill'leri onun atadığı dar iş kollarını
çözer" diyor. Bizim `tearsheet → comps → pitch` zincirimiz bunu düzleştirip
her adımı eşit ağırlıkta bir lifecycle workflow'u yapmıştı; sonucu, destek
adımının lead'in amacını ele geçirebilmesiydi.

Dört rol var ve **rol skill'e kalıcı yapıştırılmaz** (aynı skill bir bağlamda
lead, başka bağlamda support olabilir): *lead* (ilk gerçek hükmün ve hero
artefaktın sahibi), *embedded support* (dar bir iş kolunu çözer, lifecycle'ı
değiştiremez), *lifecycle* (aynı aggregate üzerinde tekrar çalışır), *meta*
(politika sağlar, analitik sonuç üretmez).

**Üç ilişki, üç ayrı mekanizma.** Bugünkü `allowed_next` üçünü tek oka
sıkıştırmış durumda; silinmeli.

1. **Support politikası** — Lead yalnız dar ve bütçeli bir support *ihtiyacı
   bildirir*; çağrıyı orkestratör yürütür. Lead kendi oturumu içinde başka
   codex çağrısı yapmaz: `support_request_proposed` döner, episode
   `awaiting_support` olur, support ayrı `attempt_id` ile taze oturumda
   çalışır, lead artefakt eklenmiş context bundle ile yeni bir attempt olarak
   yeniden çalışır. Support lead'i değiştiremez, vakayı kapatamaz, kendi
   support'unu açamaz.
2. **Artefakt bağımlılığı** — Bir çalışma bir skill'in *tamamlanmasına* değil,
   tazelik ve provenance taşıyan sürümlü bir *kanıt yeteneğine* bağımlıdır.
   Pitch "comps çalıştı mı" diye sormaz, "destekli `valuation_anchor` var mı"
   diye sorar. Katalogdaki `required_workflows` bu yüzden
   `hard_artifact_requirements` + `support_policy` diye ikiye ayrılmalı.
3. **Dispatch** — Domain olayı + subject + mevcut state uygun lead'i seçer.
   Workflow çıktısı doğrudan başka workflow çağırmaz; ürettiği şey en fazla
   bağlayıcı olmayan `handoff_suggestions`'tır.

**Katalog: 10 çalıştırılabilir + 1 meta.**

| Sınıf | Skill'ler |
|---|---|
| Çekirdek (6) | `idea_generation`, `company_tearsheet`, `comps`, `earnings_deep_dive`, `pitch`, `thesis_tracker` |
| Koşullu (3) | `earnings_preview`, `scenario`, `memo_builder` |
| Escalation (1) | `initiating_coverage` — katalog-dışı, yalnız bloklu pitch + insan onayı |
| Meta (1, `executable: false`) | `public_equity_investing` — runtime policy bağımlılığı |

Gereksiz sayılan 12 skill için gerekçeler 3. tur bölümündeki envanter
tablosunda. Bunlar "sonraki kademe" değildir; ürün sınırı değişmedikçe
açılmazlar.

**Çekirdek olmak prodüksiyon yetkisi değildir.** Altı çekirdeğin dördü
(pitch, comps, tracker ve idea-generation'ın yeni hâli) bu sistemde henüz
hiç çalışmadı. Triyaj skill metinleri okunarak yapıldı; bu bir hipotezdir,
kanıt değil. Aşağıdaki gölge vaka kapısı bu yüzden var.

### Araştırma dikey dilimi ve gölge vaka kapısı

> **SIRALAMASI GEÇERSİZ (4. tur).** Aşağıdaki plan tablosu araştırma-önce
> sıralamasına göre yazılmıştı; fon çerçevesinde bu sıra tersine döndü.
> Yürürlükteki inşa sırası için "Geçerli tasarım → İnşa sırası"na bakın:
> araştırma dikey dilimi orada **Adım 9**'dur ve fon omurgası (Adım 0-6)
> kanıtlandıktan sonra gelir. Aşağıdaki **gölge vaka kapısı ve tablodaki
> "bitti" tanımları geçerliliğini korur**; yalnız sıra değişmiştir.

> **"V1" etiketi geri çekildi (3. tur).** Aşağıdaki plan doğru bir hedef
> mimari tarif ediyor ama henüz hak edilmedi: en pahalıya patlayacak karar
> `long-short-pitch`'in çekirdek ve tek tez-açıcı adım olmasıdır, çünkü
> bütün değer `pitch → adjudication → thesis_opened → monitoring` hattına
> dayanıyor ve pitch hiç çalışmadı. Pitch yanlış çıkarsa yalnız bir adapter
> değil; tez sözleşmesi, izleme sözleşmesi, insan kapısı ve tracker girdisi
> birlikte yanlış tasarlanmış olur.

**Kapı: üç gölge vaka.** Pitch ve tracker lifecycle'a bağlanmadan önce,
deftere hiçbir şey yazmadan üç vakada elle sınanır: biri yerleşik ve görece
basit şirket, biri beklenti/opsiyonellik ağırlıklı, biri veri veya segment
yapısı zor. Ölçülenler: karar sözlüğüne uyum, `valuation_anchor`'ın gerçekten
desteklenmesi, falsifier kalitesi, eksik kanıtı dürüstçe `blocked` sayabilme,
ikinci koşuda temel hükmün kararlılığı, insanın düzeltmeye harcadığı süre.
Üç vakanın ikisinde ağır yeniden yazım gerekiyorsa pitch çekirdek değildir;
değiştirilebilir bir sağlayıcı adayıdır. Tracker aynı testi tarihsel bir
filing üzerinde geçmeli — ama tracker'ın başarısızlığı daha ucuzdur, domain
modeli doğruysa başka prompt veya insan değerlendirmesiyle değiştirilebilir.

**Sıra değişti (3. tur): olay/kanıt hattı önce, keşif sonra.** Keşif sistemin
*edinim* döngüsü, filing/olay hattı ise *işletim* döngüsüdür. Bir isim
araştırmaya girdikten sonra yeni bilginin baskın kaynağı çeyreklik
sonuçlardır; mandate'in kendi ölçümü de bunu söylüyor (aylık kararlar
ortalama 46 günlük veriye dayanıyor, şirket-aylarının %32'sinde 30 gün
içinde yeni bir 10-Q/10-K geliyor). Keşif hattını önce kurmak, işletemeyeceğimiz
kadar çok vaka üretir.

Sıra kasıtlı: her adım bir öncekinin kanıtladığı şeye dayanıyor.

| # | Adım | Neden bu sırada | "Bitti" tanımı |
|---|---|---|---|
| 0 | **Ürün sınırını dondur** | Olayların ve durumların anlamı, ürünün araştırma defteri mi allocator mı olduğuna bağlı | `thesis_opened` yalnız izlenen görüş olarak tanımlı; sistem capital policy olmadan ağırlık öneremiyor ama insan işlemini kaydedebiliyor |
| 1 | **Kanonik defter ve kimlikler** | Sonraki her şey güvenilir replay, idempotency ve tek yazarlı commit'e dayanıyor | Tek yazarlı transaction'lı defter; eşzamanlı commit testi olay kaybetmiyor; replay aynı projection'ı üretiyor; event / `workflow_request_id` / `attempt_id` / `artifact_id` / `security_id` kimlikleri ayrı |
| 2 | **Kanıt ve tetikleyici katmanı** | İşletim döngüsü budur; tarihe göre iş açan bir sistem yanlış zamanda yanlış analiz üretir | `date_due` asla `trigger_satisfied` üretmiyor; `release_observed` → `evidence_available` iki aşaması çalışıyor; SEC `items`/8-K Item 2.02 typed katmana taşınıyor; `expected_window` ve `window_expired` tanımlı |
| 3 | **Tek ticker için zincir** | Evren ölçeğine çıkmadan artefakt/context/extraction zincirini kanıtlamak gerekir | Elle seçilen bir ticker taze oturumda tam context bundle ile pitch'e kadar gidiyor; her artefakt hash'li; extraction hatası görünür ve zinciri durduruyor; support yalnız orkestratör üzerinden ve en fazla bir kez açılıyor |
| 4 | **Gölge vaka kapısı** | Pitch/tracker lifecycle'a bağlanmadan önce kanıt gerekir | Üç vakada deftere yazmadan pitch, birinde tracker çalıştırıldı; kontrat uyumu, falsifier kalitesi, kararlılık ve insan düzeltme süresi ölçüldü; geçme eşiği önceden yazılmıştı |
| 5 | **Pitch adjudication + sade tez** | Asıl domain değeri resmî görüşün güvenilir oluşması | İnsan ham sonucu, çıkarılmış hükmü ve kaynak pasajını aynı yüzeyde görüyor; kabul edilen pitch atomik ve idempotent tek tez açıyor; reject tez açmıyor; izleme sözleşmesi aynı kapıda onaylanıyor |
| 6 | **Minimum izleme döngüsü** | Açılıp bir daha bakılmayan tez yalnız arşiv kaydıdır | Her açık tez metinsel kill koşulu ve `review_due_at` taşıyor; kontrol sonucu `no_deviation`/`deviation`/`indeterminate`/`data_missing`; mekanik motor yalnız onaylı typed rule'dan çalışıyor, metinsel hücre parse etmiyor |
| 7 | **Operatör yüzeyi** | Doğru olay modeli, operatör bakmazsa çalışmaz; kapılar töreni engellemeli | Kuyruk tüm vadeli işleri öncelikle gösteriyor; kritik kararlar kanıt yanında alınabiliyor; override'lar süreli; normal kullanım JSON okumayı gerektirmiyor |
| 8 | **Keşif batch'i** | Lifecycle kapasitesi kanıtlanmadan yeni vaka hacmi üretmek yükü patlatır | Batch girdisi donuyor; her ticker sonuç veya `unaccounted_for` alıyor; eksik aday batch'in kapanmasını engelliyor; sabit finalist kotası doldurulmuyor; her hüküm `comparison_set_id` taşıyor |
| 9 | **Portföy defteri ve uzlaştırma** | Sistem işlem önermese bile pozisyonu yanlış bilmemeli -- ama yarım portföy takibi yanlış güvenden kötüdür | İnsan fill girebiliyor; broker snapshot'ı uzlaştırılıyor; exposure `long`/`flat`/`unknown` türetiliyor; uyuşmazlık en yüksek öncelikli işi doğuruyor; tax-lot eşleştirme yok |

> **Kesme önerisi (3. tur).** Yukarıdaki plan hâlâ büyük. İlk çalışan sürüm
> için: adım 9 (portföy) sonraya bırakılır ve sistem açıkça "portföy
> gerçeğinin sahibi değilim" der; adım 8 (keşif) sonraya bırakılır, vakalar
> elle açılır; `earnings_preview`, `scenario`, `memo_builder` ve
> `initiating_coverage` kapalı başlar; ilk çalışan skill seti beşe iner
> (`company-tearsheet`, `comps`, `pitch`, `earnings-deep-dive`,
> `thesis-tracker`); tam web uygulaması yerine yerel statik karar yüzeyi +
> dar komutlar kurulur. Bu kesilmiş sürümün hedefi tek bir hattı uçtan uca
> kanıtlamaktır: *baseline → valuation anchor → pitch → insan adjudication →
> tez + izleme sözleşmesi → kanıt → deep-dive/tracker → governance
> adjudication.*

**Operatör kuyruğu (adım 7)** tek giriş, leksikografik öncelik: **P0** pozisyon
bilinmiyor / uzlaşmıyor / işlenmemiş kurumsal işlem · **P1** fonlanmış tezde
sapma, kırık tezle açık pozisyon · **P2** vadesi geçmiş nitel inceleme, bayat
uzlaştırma · **P3** zinciri tıkayan adjudication · **P4** keşif işleri. Aynı
sınıfta önce `due_at`. Kuyruk öğeleri olaylardan türetilir, ayrı defter
değildir.

**İnsan kapısı yalnız dört yerde kalır:** pitch → tez geçişi, izleme
sözleşmesinin kabulü/değişimi, fonlanmış tezde sapmanın bastırılması, işlem
ve uzlaştırma kayıtları. Ara adımlar (tearsheet, comps, earnings-preview)
makine doğrulamasından geçip *provisional evidence* olarak ilerler.

**Tahmini insan yükü (3. turda güncellendi):** normal hafta **6-9 saat**,
yoğun kazanç haftası 10-14. (1. tahmin 5-7 saatti; skill mimarisi
netleştikten sonra iyimser alt sınır olduğu görüldü.) Bugünkü JSON/CLI
yüzeyi ve her adımda insan onayıyla 9-14 saat; tüm evreni haftalık tarayıp
her ara çıktıyı onaylamak 15 saati aşar ve tasarım ihlalidir.

Bunun tutması için sert WIP sınırları gerekiyor: aynı anda en fazla 2 aktif
research case, haftada en fazla 2-3 insan nitel tez incelemesi, pitch başına
en fazla 1 otomatik support, `no_deviation` sonuçları insan kuyruğuna
düşmez, preview her adayda değil yalnız maddi pre-print ihtiyacında çalışır.

**Kurma süresi tahmini:** kesilmiş sürüm (yukarıdaki kesme önerisi) haftada
15-20 saatlik çalışmayla ~9-12 takvim haftası; dokümandaki tam hedef mimari
16-22 hafta; bir gerçek kazanç döngüsüyle sertleşmiş hâli 18-24 hafta.
Claude/codex şema, adapter ve test yazımını hızlandırır; olay anlamını,
hata semantiğini, gerçek veriyle doğrulamayı ve operatör yüzeyini aynı
oranda hızlandırmaz.

### V1'de açıkça yapılmayacaklar

Her biri savunulabilir ama hiçbiri bugün doğrulanmış bir ihtiyaç değil.

- **Otomatik portföy inşası / rebalans** -- capital policy yok, üretilecek
  ağırlıkların dayanağı olmaz.
- **`portfolio-risk-management` aylık entegrasyonu** -- skill portföy-geneli
  allocator değil (bkz. 2. tur skill denetimi).
- **Benchmark / active weight / tracking error** -- mandate benchmark
  varsayılmasını açıkça yasaklıyor.
- **Beş eksenli tez state machine'i** -- ayrımların çoğu türetilebilir.
- **`superseded` lifecycle'ı** -- onu doğuracak mekanizma yok; yeni görüş
  yeni `thesis_id` ile açılır.
- **Tam tur/Stage 2 kapanış motoru** (waived dilim, partial close, deadlock
  semantiği) -- 87 isimde kayan batch yeterli.
- **Tam tax-lot eşleştirme** -- vergisel otorite broker'dır.
- **Genel kurumsal işlem motoru** -- önce uzlaştırma ve split-adjusted
  veriyle gerçek olay sıklığı görülmeli.
- **Genel amaçlı metric DSL / tam restatement motoru** -- sıfır tez varken
  erken soyutlama. (`known_at` / `period_end` yine de baştan saklanmalı.)
- **Content-addressed blob deposu + ikinci okunabilir görünüm** -- V1'de
  immutable yol + hash yeterli.
- **Git'i kanonik olay deposu yapmak** -- merge ve history rewrite domain
  atomikliğini korumuyor.
- **Uzun ömürlü resume'a doğruluk açısından bağımlılık** -- context bundle
  taze oturum için tek başına yeterli olmalı.
- **500 isim optimizasyonu** -- önce 87 isim ve ölçülmüş insan kapasitesi.
- **Capital policy kısıtlarını uydurmak** -- benchmark, sektör limiti,
  pozisyon sayısı veya kayıp bütçesi kullanıcı kararı olmadan eklenmez.

3. turdan eklenenler (skill tarafı):

- **Workbook üreten dört skill** (`dcf-model-builder`,
  `three-statement-model-builder`, `equity-model-update`,
  `model-audit-tieout`) -- birbirini doğuran bir bakım ekosistemi; ilk
  workbook üretildiği anda güncelleme, kaynak-hücre eşleme, tie-out ve
  stale-output sorunları başlar. "Model gerekiyorsa tezi açma" dürüst
  sınırdır: `blocked, reason: model_required_outside_scope`.
- **`allowed_next` alanı** -- support, artefakt akışı ve event dispatch üç
  ayrı mekanizmadır, tek oka sıkıştırılamaz.
- **Lead'in kendi oturumu içinde support çağırması** -- iç içe codex
  çağrısı gizli maliyet ve denetlenemeyen orkestrasyon üretir.
- **Yedi genel pack ailesinin ve sekiz bölümlü katalog şemasının hemen
  kurulması** -- hedef mimari için doğru, ilk sürüm için ağır. Önce
  karar-kritik üçü (deep-dive, pitch, tracker) sınanır.
- **Rol × reliance model matrisi** -- başlangıçta workflow başına sabit
  model yeterli.
- **Her adımda hero HTML artefaktı** -- skill'ler non-interactive koşuda
  aksi söylenmezse buna kayıyor. Her iş kalemi açık artefakt politikası
  taşımalı: `artifact_mode: internal_analysis`, `forbidden:
  standalone_html`. İnsan yüzeyi orkestratörün kendi ekranıdır.
- **Plugin'in enum ve routing dilini domain şemasına kopyalamak** --
  aksi hâlde "değiştirilebilir sağlayıcı" iddiası kâğıt üzerinde kalır.

## Karar günlüğü

### Başlık 0 — Candidate / Tez / Portföy / İzleme ilişkisi (2026-08-14)

**Karar:** Tez (thesis-tracker) merkezi kavram.

- `pitch` (long-short-pitch) adımı `actionable_candidate` verdiktiyle
  bittiğinde **otomatik** bir tez açılır (thesis-tracker'ın zaten kurulu
  `data/thesis-tracker/<ticker>/<thesis_id>.jsonl` şeması, three-axis:
  company/security/position). Bu, B->A terfi kapısındaki gibi insansız bir
  otomasyon -- ama gerçek sermaye tahsisi değil, yalnız "resmi, kanıt
  ağırlıklı görüş oluştu" demek.
- **Portföy, tezden ayrı, gerçek-dünya defteri.** Tezin `position` ekseni
  (add/press/hold/trim/exit/wait_for_proof/re-underwrite) bir öneri/yargı;
  gerçekten kaç hisse alındığı/hangi fiyattan insanın doğruladığı, ayrı bir
  kayıt (mevcut `portfolio.py` gibi mutable bir defter, ama artık tezle
  çapraz referanslı). Tez "trim" derken hâlâ tam pozisyondaysa bu fark
  görünür bir uyarı olur. Gerekçe: gerçek alım/satımı yalnız insan yapabilir
  (sistem hiçbir zaman otomatik emir vermiyor), o yüzden "tez öneriyor" ile
  "gerçekten yapıldı" ayrı kalmalı.
- **Tez, pozisyon açıldıktan sonra da yaşamaya devam eder** -- tek seferlik
  bir "kapı" değil, pozisyon süresince paralel, sürekli güncellenen bir
  izleme kaydı (append-only, yeni kanıt eklene eklene). Haftalık kontrolde
  "tez hâlâ ayakta mı" sorusu burada cevaplanır (`docs/pei-workflow.md`
  Bölüm 1b'deki three-axis tam bunun için). Pozisyon kapanınca tez
  `retired` olur, silinmez.
- **Watchlist tek ve otomatik.** Deprioritized/rejected/tez-retired
  olmayan her şey (tez öncesi aktif candidate'lar + tezi olup henüz
  fonlanmamış olanlar + portföyde olup tezi hâlâ izlenen isimler) otomatik
  watchlist'te sayılır -- ayrı bir "ekle" adımı yok. Hangi aşamada olduğu
  (tez-öncesi / tez-var-fonlanmamış / portföyde-izleniyor) açıkça
  etiketlenmeli.

> **REVİZE EDİLDİ (gözden geçirme, 2026-08-15).** Üç noktada:
> (1) thesis-tracker'ın `data/thesis-tracker/<ticker>/<thesis_id>.jsonl`
> dosyaları **bağımsız defter olamaz** -- `events.jsonl` tek otorite,
> tracker dosyaları ondan yeniden üretilebilir bir projection. İki
> append-only defter tutmak bu ölçekte gereksiz bir iki-fazlı commit
> problemi icat eder. (2) Pitch kabulü ile tez açılışı **aynı atomik
> batch'te** yazılmalı, aksi hâlde biri yazılıp diğeri yazılmadığında
> keşif hattı ile tez defteri birbirini yalanlar. (3) "Pozisyon kapanınca
> tez `retired` olur" cümlesi Başlık 5'le çelişiyordu ve tek `retired`
> kelimesi dört ayrı gerçeği taşıyamıyor; beş eksenli model için gözden
> geçirme bölümüne bakın.

**Bunun sonucu, Başlık 6'yı basitleştiriyor:** "ne portföyde ne
izlemede" olan isimler artık yalnızca deprioritized/rejected/tez-retired
olanlar -- yani tanım gereği zaten "aktif olmayan" demek. Başlık 6'nın
gerçek sorusu: bu ölü isimler için periyodik bir yeniden-değerlendirme
mekanizması var mı, yoksa gerçekten kalıcı olarak mı öyle kalıyorlar
(Başlık 3 ile birlikte ele alınacak).

**Değerlendirilen alternatif:** Portföyün tezin position ekseninden
otomatik türetilmesi (ayrı defter yok) -- reddedildi, çünkü gerçek
alım/satım kararını yalnız insan verebilir/uygulayabilir.

### Başlık 1 — T0 akışı: A/B eksik durumlar ve C kovası (2026-08-14)

**Bulgu (koddan doğrulandı):** `project()`'te C kovası (ve tanımsız her
bucket) için hiçbir tetikleyici/hatırlatma mekanizması yok --
`status_reason: "deprioritized until a later screen"` diyor ama "sonraki
tarama" otomatik hiçbir yerde tetiklenmiyor. Bugünkü gerçek veride tek C
adayı: AAPL.

**Kararlar:**

1. ~~**C kovasına hafif, zamanlı bir hatırlatıcı eklenir.** B'nin tetikleyici
   mekanizmasına benzer ama gevşek: **3 ay** sonra `manual_review_required`
   üretilir (C, "bu ekranda ilginç değil" demek, kısa vadeli bir olaya değil
   zamana bağlı bir yeniden-bakış).~~
2. ~~**Hatırlatıcı tarihi geldiğinde otomatik yeniden tarama YAPILMAZ** --
   yalnız insana işaret edilir (`manual_review_required`). Gerçekten yeniden
   taramayı başlatmak insanın kararı.~~

   > **1. ve 2. MADDELER GEÇERSİZ (Başlık 3 + 6, 2026-08-15).** Evren artık
   > turlar hâlinde sürekli yeniden taranıyor ve keşif havuzundan yalnız
   > açık tezliler dışlanıyor. C'deki bir isim bir sonraki turda zaten
   > yeniden değerlendirilecek; ayrı bir 3 aylık hatırlatıcı boşa çalışan
   > bir mekanizma olurdu. **Kurulmayacak.**
3. **`route_unsupported` (bloklu) isimler için ayrı bir hatırlatıcıya gerek
   yok.** Fail-closed davranış zaten doğru; bir isim sonsuza kadar bloklu
   kalabilir. Asıl çözüm hatırlatma değil, **eksik skill'leri (ör.
   equity-model-update, event-driven-analyzer) kataloğa eklemek** --
   ayrı bir aksiyon maddesi, tasarım kararı değil.
4. **Pitch'in 4 kapalı sözlük sonucundan yalnız `actionable_candidate` tez
   açar.** `watchlist` / `pass_for_now` / `red_team_only` hiçbir tez açmaz;
   isim normal candidate durumunda kalır (Başlık 0'a göre zaten otomatik
   watchlist'te sayılır).
5. **(İLK FAZ) Tez açıldıktan sonra otomatik araştırma zinciri DURUR.**
   Başlık 0'da "tez pozisyon süresince sürekli izlenir/beslenir" dedik, ama
   bunun *otomatik* mi elle mi olacağı ayrı bir soru: ilk fazda `thesis_
   opened` sonrası next_workflow kalıcı `None` kalmaya devam eder (bugünkü
   kod davranışı korunur), yeni kanıt toplamak (earnings-deep-dive
   çalıştırmak, teze evidence eklemek) bilinçli bir insan eylemi olur.
   Otomatik besleme (bugün B için kurduğumuz `waiting_for_trigger` gibi)
   sonraki bir fazda değerlendirilebilir -- şimdi YAGNI.

**Not (tasarım kararı değil, ayrı düzeltilecek bug):** `WORKFLOW_MAP`'in
substring-eşleştirmesi, bir adımın metni birden fazla rota önerdiğinde
(ör. ADBE: "önce thesis-tracker, Q3 tarihi teyit edilince earnings-preview")
hangisinin seçileceğini sözlük sırasına göre belirliyor, metindeki asıl
sıraya göre değil -- ayrı bir doğruluk düzeltmesi gerekiyor.

### Ek bulgu -- adımlar arası hafıza (2026-08-14)

**Bulgu (koddan doğrulandı, tasarım kararı değil, düzeltilecek bug):**
`prepare_work_item()` ([pei_workflow.py:1507-1516](../src/adapter/pei_workflow.py))
bir sonraki adımı hazırlarken aynı ticker+run için tamamlanmış önceki
workflow'ların `result.md`'lerini doğru şekilde buluyor ve
`workflow_prepared` olayının `required_context_artifacts` alanına
kaydediyor. Ama `run_codex_analysis()` ([pei_workflow.py:892-916](../src/adapter/pei_workflow.py))
bunu hiç kullanmıyor -- codex'e yalnızca o adımın taze `pack.json` +
`instructions.md`'si veriliyor, önceki adımın çıktısı ne kopyalanıyor ne
referans veriliyor. Bu, `pitch` gibi `required_workflows` tanımlı
adımların kendi talimatındaki ("Build on the earlier result artifacts
supplied with this pack...") beklentiyle çelişiyor.

Kullanıcının asıl noktası daha genel: manuel ChatGPT kullanımında TEK bir
oturum açılıp o ticker için tüm zincir (tearsheet → earnings-preview →
comps → pitch → thesis-tracker) aynı konuşmada yapılıyor -- model
`required_workflows`'ta resmî olarak tanımlı olsun olmasın, o ticker için
o oturumda olan HER ŞEYİ hatırlıyor. Bizim mevcut per-step "taze process"
mimarimiz bunu hiç yakalamıyor.

**Karar: `codex exec resume` ile gerçek oturum sürekliliği kullanılacak.**

- Her `codex exec` çağrısı bir `session id` üretiyor (stdout'ta
  görünüyor, doğrulandı: `-m`/`-c model_reasoning_effort=` resume
  sırasında da geçerli -- yani bir ticker'ın zinciri aynı oturumda devam
  ederken her adım kendi model/effort ayarını (Terra/Sol/Luna tablosu)
  korur, resume bunu bozmaz).
- Bir ticker+run için tamamlanan her adımın `session_id`'si kaydedilir
  (workflow_completed payload'ına yeni bir alan). Sonraki adım, taze bir
  `codex exec` yerine `codex exec resume <session_id> -m <yeni_model> -c
  model_reasoning_effort=<yeni_effort> ...` ile aynı oturumu sürdürür.
- **Denetim izi bundan etkilenmez.** result.md, pack.json ve
  yapılandırılmış event payload'ları (agy çıkarımı) olduğu gibi kaydedilmeye
  devam eder -- session sürekliliği yalnızca LLM'i nasıl SÜRDÜĞÜMÜZÜ
  optimize ediyor, "ne olduğunu" kaydeden şey değişmiyor. Böylece
  `pei-workflow-orchestrator.md`'nin "repo'dan yeniden üretilebilir olmalı"
  ilkesi ihlal edilmiyor -- geçmişi ANLAMAK için session'a hiç ihtiyaç
  yok, yalnız zinciri aynı sadakatte SÜRDÜRMEK için kullanılıyor.
- **`resume` başarısız olursa (oturum bulunamadı/süresi geçti) otomatik
  olarak dosya-bazlı yedek moda geçilir:** taze bir session başlatılır ama
  o ticker+run için tamamlanmış TÜM önceki `result.md`'ler açıkça
  eklenir/referans verilir (yalnız `required_workflows`'ta tanımlı olanlar
  değil). İnsan müdahalesi gerekmez, zincir kopmaz, sadece daha pahalı
  çalışır.
- Bu zincir mekanizması **idea-generation'ı kapsamaz** -- idea-generation
  evren/kohort seviyesinde tek bir koşu, bir ticker'ın "oturumu" değil.
  Zincir, o ticker için ilk gerçek per-ticker adımdan (ör. tearsheet)
  başlar.

> **REVİZE EDİLDİ (gözden geçirme, 2026-08-15).** Karar korunuyor ama
> şartlandı: **resume hiçbir zaman gerekli bir bilgi kaynağı olamaz.** Her
> adım için, o adımın tek başına taze bir oturumda çalıştırılmasına yetecek
> değişmez bir *context bundle* üretilmeli (kullanılan pack, önceki result
> artefaktları, son adımdan beri gelen olay deltası, geçerli setup/bucket
> snapshot'ı, talimatlar, hangi oturumun resume edildiği) ve bu bundle
> `workflow_prepared` olayına hash'li kaynak artefakt olarak bağlanmalı.
> Resume bunun **üstüne** gelir; bundle'ın yakalayamadığı ara muhakemeyi ve
> "şuna baktım, önemsizdi" türü negatif bilgiyi korur. Test şu: bir sonuç
> yalnız eski oturumun gizli hafızası sayesinde anlaşılabiliyorsa denetim
> ilkesi zaten ihlal edilmiştir.
> Buna bağlı olarak dokümandaki "geçmişi ANLAMAK için session'a hiç ihtiyaç
> yok" cümlesi daraltılmalı: repo onaylı kararın kanıtını, modelin açık
> girdilerini ve olay nedenselliğini anlamaya yeter; aynı model iç durumunu
> yeniden üretme garantisi vermez.
>
> **Oturumun ömrü:** per-ticker oturum ilk gerçek ticker workflow'uyla başlar
> ve normalde pitch'in terminal sonucunda ölür. Tez açıldıktan sonraki
> haftalık incelemeler eski pitch oturumunu resume ETMEMELİ -- yoksa
> pitch'in ikna çerçevesi yıllarca tez incelemelerine taşınır. Tur değişimi
> tek başına oturumu öldürmez, ama setup maddi olarak değiştiyse mantıksal
> zincir sürse bile fiziksel oturum kapatılmalı: *zinciri sıfırlamadan
> konuşma bağlamını sıfırlayabiliriz.*
>
> **CLI'da doğrulanan sapmalar (codex-cli 0.145.0, 2026-08-15):** Yukarıdaki
> komut şekli olduğu gibi çalışmıyor.
> - `codex exec resume` alt-komutunun `-C/--cd`, `--add-dir`, `-s` bayrakları
>   **yok**. Oturum dosyasında `cwd` kayıtlı olmasına rağmen resume onu geri
>   yüklemiyor, process'in cwd'sini alıyor -- yani per-adım artifact dizini
>   kaybolur. Çözüm: `-C`'yi **global bayrak olarak `exec`'ten önce** vermek
>   (test edildi, çalışıyor). Bugünkü kodda `-C` `exec`'ten sonra duruyor.
> - `thread_id` resume'lar boyunca **değişmiyor**; ticker başına tek id
>   saklamak yeterli. Id `--json` çıktısının ilk satırından alınır:
>   `{"type":"thread.started","thread_id":"..."}`. `-o` ile birlikte
>   kullanılabilir, sonuç dosyası etkilenmez.
> - Adım adım model değiştirmek (Terra/Sol/Luna tablosu) çalışıyor ama her
>   farklı modelde `{"type":"error","message":"This session was recorded
>   with model X but is resuming with Y..."}` item'ı üretiyor. Zararsız
>   (exit 0), ama `--json` ayrıştırırken `type:"error"` item'larını hata
>   sayan bir parser zinciri boşuna kırar.
> - `-s read-only` bu Windows kurulumunda **hiç uygulanmıyor** -- taze
>   `codex exec` ile de dosya yazılabiliyor (kontrol testi yapıldı). Resume
>   regresyonu değil, önceden var olan bir boşluk: `~/.codex/config.toml`
>   `sandbox_mode = "danger-full-access"` ve `approval_policy = "never"`
>   diyor, bayrak bunu ezmiyor. Mevcut kodun sandbox'landığı varsayımı
>   tutmuyor.
> - Oturum meta verisinde PEI eklentisinin **subagent thread'leri fork
>   ettiği** görülüyor (`thread_source: subagent`). Bir `codex exec` çağrısı
>   birden fazla rollout dosyası üretebiliyor; kök thread'in id'si
>   saklanmalı, `--last` yanlış thread'i yakalayabilir.

### Başlık 2 — Çoklu / kademeli kohortlar (2026-08-15)

Somut senaryo: T0'da "Tech sektörü" taraması NVDA'yı A'ya koyup zinciri
yürütüyor; T15'te "Genel piyasa" taraması aynı ticker'ı bu sefer B'ye
koyuyor. Bugünkü kodda bu iki koşu birbirinden habersiz iki ayrı candidate
üretiyor ve iş kuyruğunda NVDA için ikinci, sıfırdan bir zincir beliriyor.

**Kararlar:**

1. **Candidate anahtarı `run_id:ticker` yerine sadece `ticker`.** Bir
   ticker = tek kayıt. Hangi olayın hangi koşudan geldiği zaten her
   event'in kendi `run_id`'sinde duruyor, denetim izi kaybolmuyor. Bu
   yeniden icat değil, `pei-workflow-orchestrator.md` Bölüm 6'daki onaylı
   ticker-sürekli kimlik ilkesine geri dönüş.
   *Reddedilen alternatif:* bir ticker'ın birden fazla paralel araştırma
   ipliği (sektör taraması vs. genel tarama ayrı ayrı ilerler) taşıması --
   sonunda tek tez ve tek portföy pozisyonu olacağı için iplikleri
   birleştirme problemi doğuruyor, karşılığı olmayan karmaşıklık.

2. **Kademe kuralı: yeni screen aktif işi kesmez.** `thesis_opened`
   durumundaki bir isim yeni bir taramadan doğrudan etkilenmez. Diğer tüm
   durumlar (`ready` / `waiting` / `blocked` / `deprioritized` /
   `completed`) yeni screen ile serbestçe güncellenir.
   *Reddedilen alternatifler:* "en son tarama koşulsuz kazanır" (ilerlemiş
   işi geri sarar), "her çakışma insana sorulur" (haftalık taramada el işi
   biriktirir).

   > **REVİZE EDİLDİ (gözden geçirme, 2026-08-15).** "Tezi olmayan her isim
   > serbestçe güncellenir" fazla geniş. Tez ancak pitch'ten SONRA açılıyor;
   > yani tearsheet+comps'u bitmiş, pitch'i bekleyen bir isim tez sahibi
   > değil ve bu kurala göre yeni tarama onu geri sarabiliyor -- iki adımlık
   > tamamlanmış iş çöpe gidiyor. Doğru ayrım "tezi var mı" değil, **"aktif
   > araştırma zinciri var mı"**. Yeni karar: aktif zincirdeki isim taramaya
   > **girer** (çıkarılırsa donmuş araştırma riski doğar), ama screen sonucu
   > zincirin durumunu ya da rotasını **yönetmez** -- evidence olarak düşer
   > ve zincirin son adımı (pitch) onu tartar. İlke: *keşif taramasına
   > katılmak ile screen sonucunun workflow'u yönetme yetkisi ayrı
   > şeylerdir.*
   >
   > *Reddedilen alternatif (gözden geçirmede önerilip geri çekildi):* yeni
   > bir `reconciliation_required` durumu -- Başlık 2'nin zaten reddettiği
   > "her çakışma insana sorulur" seçeneğinin adı değişmiş hâli olurdu ve
   > sürekli dönen turlarda o kuyruk hiç boşalmazdı.

3. **`in_progress` için özel davranış tanımlanmadı.** Tüm akış insan
   tetiklemeli ve seri (`cmd_start_idea` / `cmd_prepare` / `cmd_run_codex`
   / `cmd_attach_result`, `scripts/us_pei_dashboard_bridge.py`); bir iş
   sürerken yeni tarama başlatmak pratikte olmuyor. Kod bunu engellemiyor
   ama fail-closed bir guard eklenmedi -- bilerek yarım bırakılmış bloklu
   bir işin başka taramaları kilitlememesi için. Disiplinle çözülür.

   > **REVİZE EDİLDİ (gözden geçirme, 2026-08-15).** Bu kararın gerekçesi
   > ("akış seri, bir iş sürerken yeni tarama başlatmak pratikte olmuyor")
   > **Başlık 3 tarafından çürütüldü**: Başlık 3 açıkça "aynı gün birkaç
   > dilim ayrı oturumlarda çalıştırılabilir" diyor, yani paralellik artık
   > tasarımın kendi parçası. Dahası paralelliğin asıl riski state çakışması
   > değil, **veri kaybı**: `append_events()` tüm defteri okuyup tamamını
   > geri yazıyor, iki süreç aynı sürümü okursa son yazan diğerinin
   > olaylarını siliyor (kodda doğrulandı, bkz. gözden geçirme bölümü).
   > Yeni ilke: **analiz paralel, commit seri.** Dilimler aynı anda LLM
   > çalıştırabilir; onaylı olayların deftere eklenmesi tek yazarlı, kilitli
   > (ya da compare-and-swap korumalı) tek bir kapıdan geçmek zorunda.
   > "Disiplinle çözülür" artık yeterli değil.

4. **Bayatlama, bucket/setup değişimine bağlı.** Yeni screen aynı bucket +
   aynı setup diyorsa `completed_workflows` korunur, zincir kaldığı yerden
   devam eder. Bucket veya setup değiştiyse eski analiz artık farklı bir
   soruyu cevaplıyor demektir -- ilgili adımlar bayat sayılır ve
   `_first_missing_prerequisite` onları yeniden çalıştırır.
   Gerekçe: sinyal zaten screen'in kendisinde, ayrı bir gün-sayısı
   konfigürasyonu gerekmiyor.
   *Reddedilen alternatifler:* workflow başına tazelik penceresi (her adım
   için gün sayısı kararlaştırma yükü), her screen'in zinciri sıfırlaması
   (haftalık taramada hiçbir zincir bitmez), bayatlamanın hiç olmaması
   (bugünkü davranış -- 2 ay eski tearsheet üzerine pitch yazılabiliyor).

   > **REVİZE EDİLDİ (gözden geçirme, 2026-08-15).** Karar uygulanabilir
   > değil: `completed_workflows` bugün yalnız workflow **adlarından** oluşan
   > bir liste, hangi veri dönemiyle veya hangi setup sürümüyle tamamlandığı
   > kaydedilmiyor. Yani "bucket/setup değişti mi" sorusunu soracak alan
   > bile yok. Her kayıt en az (workflow instance kimliği, tamamlanma zamanı,
   > girdi/context snapshot kimliği, ilgili veri dönemleri) taşımalı --
   > bunlar ilk günden yoksa eski tamamlanmalar sonradan güvenilir biçimde
   > doldurulamaz.
   >
   > *Kalan anlaşmazlık:* kuralın kendisindeki **"yalnız"** tartışmalı.
   > Gözden geçirmede öne sürülen karşı görüş: bucket/setup değişimi
   > *sorunun* değiştiğini gösterir, veri damgası ise *cevabın* eski kanıtla
   > üretildiğini -- şirket yeni çeyrek açıkladığında bucket hiç değişmeden
   > de tearsheet bayatlar (`docs/pei-workflow.md` Bölüm 151 bunu zaten
   > söylüyor). Karara bağlanmadı.

5. **Artifact dizinleri ticker-merkezli olur.** Per-ticker adımlar
   `data/pei-workflow/runs/<run_id>/work/...` altından çıkıp ticker altında
   toplanır; run dizini yalnız idea-generation çıktısı (evren/kohort
   seviyesi, bir ticker'a ait değil) için kalır. Bir ticker'ın tüm geçmişi
   tek yerde okunur. Göç gerekiyor ama bugün tek gerçek run olduğu için
   ucuz.
   *Açık uçlu detay (uygulama sırasında netleşecek):* aynı ticker aynı
   workflow'u bayatlama sonrası ikinci kez çalıştırabileceği için dizin ve
   iş kalemi kimliği tarih ayırıcı taşımalı (ör.
   `companies/<ticker>/<tarih>-<workflow>/`); `run_id`'nin iş kalemi
   kimliğindeki rolü de buna göre yeniden düşünülmeli.

**Kademe kuralının sonucu (Başlık 0'a bağlanıyor):** Tezi açık bir isim
yeni taramada düşerse (ör. A→C) bu sinyal sessizce olay günlüğüne
gömülmez -- yeni screen teze **evidence** olarak eklenir ve `position`
ekseni `re-underwrite`'a çekilir. Tez ayakta kalır, otomatik iş
tetiklenmez; haftalık kontrolde "tez hâlâ geçerli mi" sorusu bu kayıtla
cevaplanır. thesis-tracker'ın mevcut sözlüğü kullanılıyor, yeni kavram
icat edilmiyor.
*Reddedilen alternatifler:* `manual_review_required` üretmek (candidate
blocked'a düşer, tez durumuyla çelişir), yalnız panelde bir "conflicting
screen" rozeti (tezin kendi kaydında iz bırakmadığı için tez okunduğunda
sinyal kaybolur).

> **SONRADAN GEÇERSİZ KALDI (Başlık 3, 2026-08-15).** Başlık 3'te tezli
> isimlerin tarama hattına hiç girmemesine karar verildi. Tezli bir isim
> hiç screen edilmiyorsa "yeni taramada düşme" olayı da hiç gerçekleşmez
> -- yani bu tetikleyici mekanizmasız kaldı. Karar (yeni kanıt gelince
> `re-underwrite`) hâlâ doğru, ama **tetikleyicisini Başlık 4 (portföyde
> olan tezler) ve Başlık 5 (tezi olup fonlanmamışlar) tanımlamak
> zorunda** -- aksi hâlde açık tezler hiçbir kaynaktan beslenmez.

### Başlık 3 — Kapsama ve kademeli tarama (2026-08-15)

Başlık 3 gündemde "aynı kohortun zaman içinde tekrar taranması" olarak
yazılmıştı; konuşuldukça asıl sorunun **evren büyüdüğünde taramanın nasıl
kademelendirileceği** olduğu ortaya çıktı. Evren bugün 87 isim ama sabit
değil, ileride S&P 500 ölçeğine çıkabilir. Tek bir taramaya 500 isim
verilirse -- pack inceltilse bile -- çıktı kalitesi düşer. Dilimleme
şart. Ama dilimleme "haftada bir dilim" demek değil; aynı gün birkaç
dilim ayrı oturumlarda çalıştırılabilir.

**Ampirik olduğu için burada karara bağlanmayanlar** (config parametresi
olarak dışarı alınacak, ilk turda ölçülüp ayarlanacak; koda gömülmeyecek):
dilim boyutu (bir oturumda kaç ticker) ve pack inceltmesi (ticker başına
hangi alanlar kalır). İkisi de ölçmeden bilinemez.

**Kararlar:**

1. **İki turlu yapı.** Tur 1: dilimler kendi içinde taranır, her dilim
   kendi finalistlerini işaretler (dilim-göreceli yargı). Tur 2: tüm
   dilimlerin finalistleri tek bir oturumda yan yana karşılaştırılır,
   gerçek A/B/C orada belirlenir. Bu, "inceltme" sorusunu da doğal olarak
   çözüyor: Tur 1 ince pack + çok isim, Tur 2 tam pack + az isim.
   *Reddedilen alternatifler:* mutlak eşik (dilimden bağımsız sabit
   kriterler; daha basit ama eşiklerin kendisi tanımsız), göreceli ama
   ikinci tur yok (her dilimin finalisti doğrudan A sayılır -- zayıf
   dilimlerden de A üretir, portföy seviyesinde çöp birikir).

2. **Dilim kriteri: sektör + boyut düzeltmesi.** Sektör birincil kriter,
   çünkü dilim-göreceli yargının anlamlı olması için isimlerin
   karşılaştırılabilir olması gerekiyor ("yazılım şirketleri arasında en
   cazip 3" anlamlı, "bu rastgele 25 arasında en cazip 3" değil). Ama saf
   sektör dilimlemesi işlemiyor: bugünkü evrende technology 31,
   consumer-staples 24, health-care 15, industrials 12,
   communication-services 5 -- 5 isimlik dilimden 3 finalist %60 geçiş
   oranı demek. Bu yüzden büyük sektörler alt-gruplara bölünür, çok
   küçükler komşu sektörle birleştirilir; dilimler hedef boyuta çekilir.

3. **Tarama hattı saf keşiftir; tezli isimler hiç girmez.** Tur 1 ve Tur
   2, yalnızca tezi olmayan isimler için çalışır. Dilimler kurulurken
   tezli isimler evrenden çıkarılır; tez `retired` olunca isim keşif
   havuzuna geri döner.
   Gerekçe: portföy/tez kararı ile araştırma önceliği **farklı sorular**.
   Portföydeki bir isim "daha iyi bir aday çıktı" diye elenmez -- pozisyon
   sayısı artırılabilir, ağırlıklar yeniden dengelenebilir, korelasyon ve
   yoğunlaşma devreye girer. Bu kararı araştırma sıralamasıyla aynı
   oturuma sıkıştırmak ikisini de bozar.
   *Reddedilen alternatifler:* tezli isimlerin Tur 1'i atlayıp doğrudan
   Tur 2'ye girmesi (yeni adaylarla aynı ölçekte görülürlerdi ama Tur 2'ye
   dolaylı bir eleme yetkisi yüklenirdi), tezli isimlerin kendi sektör
   diliminde normal taranması (Tur 1 elemesi dilim-göreceli ve zayıf bir
   sinyal; `re-underwrite` gibi güçlü bir mekanizmayı tetiklemesi yanlış
   alarm üretir).
   **Bedeli, açıkça kabul edildi:** "bu yeni aday mevcut pozisyonumdan
   daha iyi mi" karşılaştırması tarama hattında hiç yapılmaz; o soruyu
   Başlık 4'teki portföy oturumu cevaplamak zorunda.

   > **REVİZE EDİLDİ (gözden geçirme, 2026-08-15).** Kabul edilen bedelin
   > **karşılığı yoktu**: Başlık 3 karşılaştırmayı Başlık 4'e devretti, ama
   > Başlık 4'ün portföy oturumu yalnız açık tezleri ve pozisyonları görüyor.
   > A çıkmış, tearsheet+comps'u yapılmış ama pitch'e gelmemiş bir isim iki
   > oturumun arasından düşüyordu -- karşılaştırma hiçbir yerde yapılmıyordu.
   > Kapatan ilke: **`thesis_opened`, sermaye karşılaştırmasına kabul
   > kapısıdır.** Tez açılan isim otomatik olarak portföy oturumunun
   > gündemine girer; karşılaştırma gecikmeli ama karar-kalitesinde olur.
   > Pitch öncesi aday henüz falsifier/risk-reward/eşik taşımadığı için
   > incumbent'la kıyaslanmaması kayıp değil, bilinçli bir epistemik eşik.
   >
   > *Reddedilen alternatifler:* portföy oturumuna olgunlaşmış A adaylarını
   > da sokmak (farklı olgunluktaki nesneleri kıyaslar, oturumu ikinci bir
   > pitch mekanizmasına çevirir), pitch'in pack'ine portföyü koymak (güçlü
   > bir tez sırf sektör ağırlığı yüksek diye `non-actionable` çıkabilir --
   > company/security/action ayrımı tam orada bozulur).

4. **Tur 2, tüm dilimler bitince tek seferde çalışır.** Bir "tur" = tüm
   evrenin dilimlerinin taranması + sonunda tek bir finalist karşılaştırma
   oturumu. Finalistler tur bitene kadar bekler.
   *Reddedilen alternatif:* periyodik Tur 2 (her gün biriken finalistlerle)
   -- her Tur 2 farklı bir aday kümesiyle karşılaştırma yapardı, yani
   dilim-göreceli sorunun aynısı bir üst katmanda tekrarlanırdı.
   *Kabul edilen bedel:* ilk dilimin finalisti tur uzunluğu kadar bekler.

**Not:** Bu tasarım, gündemdeki orijinal "T0'daki grup T60'ta tekrar mı
taranır" sorusunu kapsıyor -- evren turlar hâlinde sürekli yeniden
taranıyor, hiçbir isim kalıcı olarak unutulmuyor. Bu, **Başlık 1'in 1.
kararını (C kovasına 3 aylık hatırlatıcı) gereksiz kılıyor olabilir**:
C'deki bir isim zaten bir sonraki turda yeniden değerlendirilecek.
Başlık 6 ele alınırken bu madde tekrar gözden geçirilmeli.

### Başlık 4 — Portföy takibi (2026-08-15)

Başlık 3, tarama hattını saf keşfe ayırdığı için açık tezleri besleme
sorumluluğu tamamen buraya düştü. Ayrıca gündemdeki "muhasebe" ile
"portföy seviyesinde karar" ayrımı korunuyor: ilki bizim tuttuğumuz
defter, ikincisi skill'in işi.

**Kararlar:**

1. **Ritim mandate'ten geliyor, icat edilmiyor.** idea-generation
   talimatındaki mandate zaten "Review weekly, rebalance monthly ... 
   neither is obliged to [change the portfolio]" diyor. Buna karşılık iki
   ayrı oturum: **haftalık tez sağlığı** ve **aylık rebalans**. Farklı
   sorular oldukları için ayrı kalıyorlar.
   *Reddedilen alternatifler:* tek haftalık oturum (her hafta tam rebalans
   düşüncesi gereksiz işlem dürtüsü yaratır), olay-güdümlü/takvimsiz
   (mandate'in ritmiyle çelişir, sessiz dönemlerde portföy hiç gözden
   geçirilmez).

   > **REVİZE EDİLDİ (2. tur, 2026-08-15).** Ritim mandate'ten alındı ama
   > mandate'in **kendi yazılı uyarısı** görülmedi: `known_tension` alanı
   > "eklentinin varsayılan temel analiz ufku 3-18 ay iken bu mandate aylık
   > rebalans yapıyor; ölçüldü: aylık kararlar ortalama 46 günlük veriye
   > dayanıyor ve şirket-aylarının %32'sinde karardan sonraki 30 gün içinde
   > yeni bir 10-Q/10-K geliyor" diyor. Ayrıca mandate `change_required:
   > false` diyor -- yani "ayda bir değiştir" değil, "ayda bir bakabilirsin,
   > tutmak da geçerli sonuç". Biz ona **"rebalans" adını vererek** farkında
   > olmadan her ay tüm tezleri yeniden karşılaştırma yetkisi verdik; bu,
   > 3-18 aylık bir tezin position eksenini ömrü boyunca 12+ kez ezme
   > yetkisidir ve stratejiyi sessizce aylık rotasyona çevirir.
   > **Yeni ad ve varsayılan:** "aylık portföy gözden geçirmesi", varsayılan
   > sonuç `no_change`. İşlem için yeni kanıt, değerleme değişimi, nakit
   > ihtiyacı ya da açık bir sermaye kısıtı gerekir.

2. **Haftalık kontrol iki kademeli: önce mekanik, sonra gerekirse derin.**
   Her açık tezin kayıtlı beklentileri taze veriyle LLM'siz karşılaştırılır;
   yalnız sapma gösterenler için `thesis_tracker` oturumu açılır. Sessiz
   haftalarda hiç LLM çağrısı olmaz. `check_triggers` altyapısı zaten var.
   *Reddedilen alternatifler:* her tez için ayrı oturum (10 tez = haftada
   10 oturum, çoğu "değişen bir şey yok" diyecek), tek toplu oturum (tez
   başına derinlik düşer -- dilim-göreceli sorunun aynısı).
   **Bu, Başlık 2'de mekanizmasız kalan `re-underwrite` tetikleyicisinin
   yaşadığı yerdir.**

   > **REVİZE EDİLDİ (gözden geçirme, 2026-08-15).** İki eksik:
   > (1) Mekanik kontrolün dayandırıldığı `check_triggers()` altyapısı bu iş
   > için **çalışmıyor** -- fonksiyon `state != "waiting"` olan her adayı
   > atlıyor, yani `thesis_opened` durumundaki bir ismin eşikleri hiçbir
   > zaman değerlendirilmiyor (kodda doğrulandı). Haftalık kontrol, tezin
   > eşiklerini normalize metrik kimliklerine bağlayan **ayrı ve küçük bir
   > monitoring snapshot'ı** ile çalışmalı (`market.py` / `live_pack.py` /
   > `point_in_time.py` üstünde); `thesis_tracker`'ın kendi pack'i ancak
   > sapma sonrası derin inceleme açıldığında üretilir.
   > (2) **Sapma olmasa da iz bırakılmalı.** Yalnız sapmalar kaydedilirse
   > "kontrol edildi, temizdi" ile "üç haftadır hiç çalıştırılmadı" ayırt
   > edilemez. Her tez için sonuç en az dört değerden biri olmalı:
   > `no_deviation` / `deviation` / `indeterminate` / `data_missing`.
   > Yalnız `deviation` yeni bir `thesis_tracker` oturumu tetikler;
   > `indeterminate` hiçbir zaman sessizce "temiz" sayılmaz. Haftalık koşu
   > ayrıca beklenen tezlerin kaçının gerçekten kontrol edildiğini gösteren
   > bir kapanış kaydı taşımalı ki yarım kalmış kontrol görünür olsun.

3. **Sapma ölçüsü teze özeldir, jenerik değil.** Tez açılırken (pitch
   `actionable_candidate` → `thesis_opened`) `first_rejection`'ın metinsel
   hali agy çıkarımıyla ölçülebilir eşiklere dönüştürülür ve tez kaydına
   yazılır.
   *Reddedilen alternatif:* her tez için aynı jenerik ölçü seti (yeni
   bilanço, fiyat eşiği, revizyon dengesi, değerleme sapması) -- kurmak
   kolay ama tezin asıl bozulma koşulunu yakalamaz.

4. **Ölçülemeyen bozulma koşulu atılmaz, metinsel saklanır.** Pack'te
   karşılığı olmayan koşullar (ör. "hyperscaler capex'i backlog'a
   dönüşmezse") tez kaydında metin olarak kalır ve haftalık oturumda
   "elle kontrol edilecek koşullar" olarak listelenir. Ölçülebilenler
   mekanik kontrole girer.
   *Reddedilen alternatifler:* sert fail-closed (tüm koşullar ölçülebilir
   değilse tez açılmaz -- en değerli nitel tezler tam bu yüzden bloklanır),
   ölçülemeyenleri atmak (tezin asıl gerekçesi kaybolur).

5. **Aylık rebalans mantığı `portfolio-risk-management` skill'ine
   devredilir.** Histerezis, ağırlıklandırma, korelasyon ve yoğunlaşma
   kurallarını kendimiz tanımlamıyoruz; skill zaten bu iş için yazılmış.
   Bizim işimiz orkestrasyon: skill'i kataloğa eklemek, portföy paketini
   üretmek, çıktısını kaydetmek. Repo'nun mevcut deseniyle tutarlı --
   analitik yargı skill'in, akış bizim.
   **Açık iş:** skill kurulu olmadığı için girdi/çıktı sözleşmesi
   bilinmiyor. `config/pei-workflows.json`'a eklenecek `pack_step`,
   `required_workflows` ve `result_contract` alanları ancak skill
   incelendikten sonra doldurulabilir.

   > **İPTAL (2. tur, 2026-08-15).** Bu karar yanlıştı ve skill okunmadan
   > verilmişti. `portfolio-risk-management` 0.1.31'in Mode Selection
   > tablosunda **üç mod var ve üçü de tek pozisyon hakkında**:
   > `position_sizing`, `hedge_design`, `integrated_risk_plan`. Portföy
   > bağlamı orada bir **girdi kısıtı**, kararın konusu değil. Skill'i her
   > isim için ayrı çağırsak bile o cevapları birleştiren mantık bizde
   > kalıyor -- ki kararın gerekçesi tam olarak o mantığı kendimiz
   > tanımlamamaktı. Ayrıca skill `long_only_pm` modunda benchmark active
   > weight / tracking error bekliyor, mandate ise benchmark varsayılmasını
   > yasaklıyor.
   > **Yerine:** aylık portföy-geneli kararın sahibi insandır. Sistem
   > kanonik paketi ve deterministik teşhisleri hazırlar; skill yalnız
   > insanın seçtiği tekil bir pozisyonda ve açık bir risk bütçesi varken
   > sizing/hedge derinleşmesi için opsiyonel çağrılır.
   > **Genelleştirilebilir ders:** bir skill'e devretmeden önce (i) hangi
   > soruyu cevapladığı, (ii) kararın kardinalitesi (ticker mı, tez mi,
   > pozisyon mu, tüm portföy mü) ve (iii) N çıktıyı birleştirecek gizli
   > bir karar kalıp kalmadığı yazılmalı. Üçüncüsü bu hatayı doğrudan
   > yakalardı -- Başlık 3'ün Başlık 4'e yazdığı karşılıksız çekle aynı
   > hata.

6. **Portföy defteri olay tabanlı olur.** Append-only işlem kaydı
   (alım/satım/temettü; tarih, fiyat, adet ve **hangi teze bağlı**);
   mevcut pozisyonlar bundan türetilir. Repo'nun geri kalanıyla aynı desen
   (`events.jsonl`, append-only tez kaydı). Gerekçe: "bu tezle ne zaman
   girdim, ne kazandım" sorusu ancak böyle cevaplanabilir -- tezlerin
   gerçekten işe yarayıp yaramadığını ölçmenin tek yolu bu.
   *Reddedilen alternatifler:* mutable pozisyon tablosu (kapanan pozisyon
   iz bırakmadan siliniyor), olay defteri + türetilmiş önbellek (10-20
   pozisyon ölçeğinde gereksiz).

> **REVİZE EDİLDİ (gözden geçirme, 2026-08-15).** Karar doğru ama eksik ve
> eksiği gerçek parayla ilgili. (1) İşlem kaydı **ayrı bir defter değil**,
> global `events.jsonl` içinde tez referanslı bir olay olmalı (işlem türü,
> ticker, `thesis_id`, gerçekleşme zamanı, yön, adet, fiyat, masraf, insan
> onayı); idempotency anahtarı broker işlem kimliği ya da kullanıcının
> verdiği işlem kimliği. (2) Bu olayı **üretecek hiçbir komut yok** --
> bugünkü bridge'de `cmd_start_idea` / `cmd_prepare` / `cmd_run_codex` /
> `cmd_attach_result` var, işlem girişi yok. (3) En kritiği: **işlem kaydı
> yokluğundan `flat` türetmek yasak olmalı.** İnsan alıp kaydetmeyi
> unutursa sistem tezi sonsuza kadar fonlanmamış sanar ve aylık rebalansa
> yanlış girdi verir. Bunun için ayrı bir portföy uzlaştırma olayı gerekiyor
> ve üç durum ayrılmalı: `open_position` (kayıtlı ve uzlaştırılmış),
> `confirmed_flat_as_of` (belirtilen tarihte uzlaştırılmış sıfır),
> `position_unknown` (defter güncel değil). `position_unknown` "fonlanmamış"
> diye yorumlanamaz; portföy girdisini güvenilmez sayıp sermaye kararını
> bloklamalı.

**Önemli not:** Mevcut `src/adapter/portfolio.py` / `data/portfolio/
portfolio.json` **dummy bir çalışma**; bu tasarımda referans alınmadı.
Gerçek defter yukarıdaki 6. maddeye göre sıfırdan kurulacak.

### Başlık 5 — İzleme listesi takibi (2026-08-15)

Bu başlığın sorusu ("pozisyon olmayan ama izlenen isimler zaman içinde
nasıl takip edilir") büyük ölçüde önceki kararlardan türedi. Başlık 0'daki
otomatik watchlist'in üç etiketi şu an şöyle kapsanıyor:

| Etiket | Takip mekanizması |
|---|---|
| tez-öncesi aktif candidate | keşif hattı turları (Başlık 3) |
| tez var, fonlanmamış | haftalık tez sağlığı (Başlık 4) + aylık rebalansta "fonlanmalı mı" |
| portföyde, tezi izleniyor | haftalık tez sağlığı (Başlık 4) |

**Ayrı bir izleme mekanizması kurulmuyor** -- watchlist zaten bu üç
durumun türevi, kendi başına bir süreç değil.

**Karar: fonlanmamış tez süresiz açık kalır.** Tez yalnız bozulunca (kendi
eşikleri tetiklenince) `retired` olur. Fonlanmamış olmak tezin yanlış
olduğunu göstermez -- fiyat henüz gelmemiş olabilir.
*Reddedilen alternatifler:* periyodik zorunlu tazeleme, sabit süre
sonunda otomatik retire (iyi bir tezi yalnızca zaman geçtiği için çöpe
atar).

> **REVİZE EDİLDİ (gözden geçirme, 2026-08-15).** "Fonlanmamış tez" tanımı
> düzeltildi: işlem kaydının **yokluğu** değil, belirli bir tarih itibarıyla
> uzlaştırılmış `flat` durumu (bkz. Başlık 4 karar 6 revizyonu). Ayrıca
> tezin ölümü tek adımda olmuyor: tez kırıldığında doğrudan `retired`
> olmaz, önce `wind_down`'a geçer -- insan satana kadar gerçek pozisyon
> izlenmeye devam eder. `wind_down → closed` geçişi ancak uzlaştırılmış
> exposure sıfıra indiğinde yapılabilir. Tersi de geçerli: insanın tamamen
> satması tezi otomatik kapatmaz (yoğunlaşma/likidite/vergi nedeniyle
> sıfırlanmış ama hâlâ geçerli bir tez, fonlanmamış açık tez olarak aylık
> rebalansta yeniden değerlendirilebilir).

*Değerlendirilen risk ve neden kabul edilebilir olduğu:* Başlık 4'te
jenerik taban seti reddedilip teze özel eşikler seçildiği için, eşikleri
hiç tetiklenmeyen bir tez teorik olarak "donabilir" -- üstelik tez açık
olduğu sürece o isim keşif hattına da girmiyor (Başlık 3). Ancak aylık
rebalans oturumu **tüm açık tezleri** görüyor (Başlık 4, karar 5), yani
eşikleri sessiz bir tez de ayda bir `portfolio-risk-management` masasına
geliyor. Donma tam değil; periyodik temas aylık rebalanstan sağlanıyor.

### Başlık 6 — Ne portföyde ne izlemede olan isimler (2026-08-15)

Gündemin sorusu: bu isimler sonsuza kadar mı unutulacak, yoksa bir
geri-değerlendirme mekanizması mı olacak?

Başlık 3'ün tur yapısı bunu zaten çözdü: evren turlar hâlinde sürekli
yeniden taranıyor, yani hiçbir isim kalıcı olarak kaybolmuyor.

**Karar: keşif havuzu = evren − açık tezli isimler. Başka hiçbir kalıcı
dışlama yok.** `deprioritized`, `rejected` ve tez-`retired` isimler her
turda normal şekilde yeniden değerlendirilir. Tek kural, istisna yok;
ayrı bir "geri-değerlendirme mekanizması" kurulmuyor çünkü turların
kendisi zaten o işi yapıyor.
*Reddedilen alternatifler:* Reject'e bir tur soğuma süresi (ikinci bir
zamanlama kuralı ve "kaçıncı turdayız" muhasebesi getirir), Reject'in
kalıcı olup elle geri alınması (şirketler değişir; kalıcı damga zamanla
yanlışa döner).

**Sonucu:** Başlık 1'in 1. ve 2. kararları (C kovasına 3 aylık
hatırlatıcı) geçersiz kaldı ve yukarıda öyle işaretlendi.

---

## Gözden geçirme — 1. tur (2026-08-15)

> Bu turun bazı sonuçları **2. turda değiştirildi** (beş eksenli model,
> `thesis_opened`'ın sermaye kapısı olması, Başlık 4 karar 5'in ayakta
> kalması, olay sözlüğü). Etkilenen yerler aşağıda işaretli; birleşik hâl
> için "Geçerli tasarım" bölümüne bakın.

Yedi başlık kapandıktan sonra, uygulamaya geçmeden önce tasarım codex CLI
üzerinde (gpt-5.6-sol / high) tek bir oturumda yedi tur tartışıldı. Amaç
iş yaptırmak değil, tasarımı bir başka bakışa sınatmaktı: açıkta kalan
if-durumları, birbiriyle çelişen kararlar, tetikleyicisi olmayan
mekanizmalar. Oturum sürekliliği için dokümanın kendi `codex exec resume`
kararı kullanıldı -- yani tasarım kendi mekanizmasıyla denendi.

Aşağıdaki maddelerin çoğu ilgili karara yerinde `> **REVİZE EDİLDİ**` notu
olarak da işlendi; bu bölüm birleşik resmi ve gerekçeleri veriyor.

### Kodda doğrulanan üç hasar

Bunlar görüş değil, okunarak doğrulanmış davranışlar.

1. **Olay defteri paralel yazımda sessizce veri kaybediyor.**
   `append_events()` tüm defteri okuyor
   ([pei_workflow.py:323](../src/adapter/pei_workflow.py)) ve mevcut+yeni
   olayların tamamını tek atomik replace ile geri yazıyor (satır 337-338).
   İki süreç aynı sürümü okursa son yazan diğerinin olaylarını siler;
   satır 334'teki `duplicate event_id` guard'ı yalnız kendi okuduğunu
   gördüğü için koruma sağlamaz. Atomik replace, eşzamanlı
   read-modify-write kaybını çözmez. Başlık 3'ün paralel dilimleri bu
   hasarı ilk gün tetikler.

2. **Tasarımın üzerine kurulduğu otomasyonun üretici tarafı yok.**
   `thesis_opened` kodda yalnız `project()` içinde **tüketiliyor**
   (satır 548-549); onu üreten hiçbir şey yok. `generate_draft_events()`
   pitch sonucunun `actionability` alanına bakıp tez açmıyor. Başlık 0'ın
   tamamı bu otomasyonun üzerine kurulu.

3. **Açık tezin eşikleri hiçbir zaman kontrol edilmiyor.**
   `check_triggers()` `state != "waiting"` olan her adayı atlıyor
   (satır ~1610). `thesis_opened` durumundaki bir isim bu filtreden hiç
   geçmez. Başlık 4'ün haftalık mekanik kontrolü tam da bu altyapıya
   dayandırılmıştı.

### Onay kavramının ayrılması

Gözden geçirmenin tek en değerli çıktısı. `approval` bugün iki ayrı şeyi
taşıyor ve bu yüzden otomasyon tartışması yapılamıyor: *"bu olay deftere
teknik olarak kabul edilebilir"* ile *"bu analitik hükme güveniyorum,
sonraki kararlar bunu kullanabilir"*. Ayrılınca üç kapı çıkıyor:

| Sınıf | Örnek | Kural |
|---|---|---|
| Makine doğrulanabilir | şema, hash, kaynak varlığı, sayısal tie-out, eşik karşılaştırması | otomatik çalışır, sistem yetkisiyle kaydedilir |
| Analitik yargı | bucket, peer seçimi, valuation yorumu, pitch actionability, tez durumu | kullanımdan veya state değişiminden önce insan kabulü |
| Gerçek-dünya icrası | alım, satım, pozisyon yeniden bağlama, portföy uzlaştırma | her zaman açık insan eylemi, otomatikleştirilemez |

Kural: **bir model çıktısı başka bir yargı adımına controlling input
olacaksa, aday eleyecekse veya kalıcı lifecycle geçişi doğuracaksa, önce
insan tarafından kabul edilmeli.** Bugünkü `approval.status=approved`
alanı "analiz doğrudur" değil, "olayın deftere yazılması yetkilendirildi"
diye yorumlanmalı; analitik kabul ayrı bir hüküm.

Buradan çıkan ikinci ilke: **insan tetiklemeli olmak, insan tarafından
adım adım sürülmek demek değildir.** Bugünkü sistem her ikisi de; ölçeklenmeyen
kısım ikincisi. Orkestratör `prepare → run_codex → attach → extract →
validate` zincirini tek çalıştırmaya indirebilir ama analitik kabul
kapısında durur. İnsan şu kapılarda kalır: turu başlatmak ve bütçesini
onaylamak, partial tur kapatmak, desteklenmeyen/çözülmemiş istisnaları
karara bağlamak, portföy hükmünü değerlendirmek, gerçek işlemi yapmak ve
kaydetmek, portföyü uzlaştırmak.

Somut karşılıkları: Tur 1 sonucu dilim bazında kabul edilir (ticker başına
değil), Tur 2 bucket'ları topluca kabul edilir, tearsheet/comps/earnings
çıktıları sonraki analize girmeden artefakt düzeyinde kabul edilir. Pitch
kabul edildiğinde ayrıca ikinci bir "tez açayım mı" onayı istenmez --
kabul edilmiş `actionable_candidate` otomatik ve atomik olarak tez açar.

### Tezin beş ekseni

> **2. TURDA SADELEŞTİRİLDİ.** Aşağıdaki beş eksen kavramsal ayrımları
> bulmakta işe yaradı ama üretim veri modeli olarak fazla ağır: eksenlerin
> bir kısmı aynı varlığa ait değil (`actual_exposure` bir portföy gerçeği,
> `recommended_action` tarihli bir değerlendirme), `thesis_lifecycle` ile
> `company_thesis_status` büyük ölçüde örtüşüyor ve `superseded`'ın hâlâ
> mekanizması yok. Üç eksenli yürürlükteki hâl için "Geçerli tasarım →
> Tez modeli"ne bakın. Aşağıdaki tablo tarihsel kayıt olarak duruyor.

Başlık 0 + 5'teki tek `retired` kelimesi dört ayrı gerçeği taşıyamıyordu:
tezin entelektüel geçerliliği, PM hükmü, gerçek pozisyon ve izleme
zorunluluğu. Ayrılan eksenler:

| Eksen | Değerler |
|---|---|
| `thesis_lifecycle` | `active`, `wind_down`, `closed`, `superseded` |
| `company_thesis_status` | `untested`, `strengthening`, `intact`, `watch`, `impaired`, `broken`, `changed` |
| `security_readiness` | `ready`, `conditional`, `re_underwrite`, `not_decision_grade` |
| `recommended_action` | `add`, `press`, `hold`, `trim`, `exit`, `hedge`, `wait_for_proof`, `re_underwrite` |
| `actual_exposure` | `long`, `short`, `flat`, `unknown` (+ adet ve uzlaştırma tarihi) |

`monitoring_required` ayrı yazılabilir bir durum değil, türetilir: *tez
`active`/`wind_down` ise veya gerçek exposure sıfır değilse izleme
zorunludur; exposure bilinmiyorsa izleme zorunlu ve portföy kararı
bloklu.*

Yasaklar: `closed`/`superseded` tez yeniden açılamaz (yeni görüş yeni
`thesis_id` ister); kapalı teze bağlı yeni alış yapılamaz; `broken` tezde
`add`/`press` önerisi bulunamaz; `wind_down → closed` normalde yalnız
uzlaştırılmış exposure `flat` iken mümkün; `closed` + sıfır olmayan
exposure normal durum değil, açık bir bütünlük ihlali olarak gösterilmeli;
ve yalnız işlem kaydı yokluğundan `flat` türetmek yasak.

İki sınama hâli:

- *Tez kırıldı, exit önerildi, insan henüz satmadı:* `wind_down` +
  `broken` + `re_underwrite` + `exit` + `long`, izleme zorunlu.
- *İnsan tamamen sattı ama tez hâlâ geçerli:* `active` + `intact` +
  (`wait_for_proof`/`hold`) + `flat`, izleme zorunlu.

### Tez açılışının bütünlüğü

`pitch completion → thesis_opened` aynı global defterde **atomik** olmalı;
ticker bazlı tracker yalnız projection. Idempotency anahtarı hash değil
**nedensellik** olmalı: `thesis_opened`'ın anahtarı onu doğuran onaylı
pitch `workflow_completed.event_id`'sidir -- yani bir pitch completion en
fazla bir tez açabilir, `thesis_id` bundan deterministik türetilebilir.
Ayrıca **ticker başına aynı anda tek açık tez** invariant'ı gerekli: açık
tez varken ikinci tez açılamaz, yeni sonuç mevcut teze evidence olur ya da
eski tez açıkça kapatılır. (Hash taşıma katmanındaki tekrarları, nedensel
kimlik iş kuralındaki tekrarları önler.)

Tez açma yetkisi **yalnız pitch'te** kalır. Haftalık `deviation` yolu
mevcut tezin eksenlerini güncelleyebilir (`changed`, `broken`,
`re_underwrite` diyebilir) ama yeni tez açamaz -- açabilseydi
`thesis_tracker` sessizce pitch'in yerine geçerdi.

### Kalan anlaşmazlıklar

**Bayatlama ekseni.** Başlık 2 karar 4'ün revizyon notunda ayrıntısı var:
`completed_workflows`'a provenance alanları eklenmesi konusunda uzlaşıldı;
"yalnız bucket/setup değişirse bayat" kuralındaki *yalnız*'ın kalıp
kalmayacağı karara bağlanmadı.

**`superseded`.** Bu dokümanı yazan taraf değerin atılmasını savundu
(tez açıkken o isim keşif havuzunda olmadığı için yeni pitch hiç doğmaz --
yani kâğıtta var, mekanizması yok). Karşı görüş: haftalık inceleme
`re_underwrite` derse insan tetiklemeli bir *yeniden-pitch* istenebilir,
o pitch eski tezi atomik olarak supersede edebilir; bu, "yıllarca
değiştirilen bir tezin başlangıçtaki tezmiş gibi görünmesini" engeller.
Pratikte yakınsandı: **değer şemada kalsın, mekanizması şimdi
kurulmasın.**

### Karara bağlanmayanlar

- **Tur kapanışı.** Öneri: tur, tüm dilimler *başarılı* olduğunda değil,
  tüm dilimler *terminal olarak çözümlendiğinde* (`completed` / `failed` /
  insan tarafından `waived`) kapanır; zaman aşımı turu kendiliğinden
  kapatmaz, yalnız "kapatma kararı gerekiyor" sinyali üretir; insan
  gerekçeli bir *partial close* yapabilir ve o turun Tur 2 sonucu eksik
  kapsamlı olduğunu taşır. Kesin politika belirlenmedi.
  Not: `route_unsupported` bir dilimi bloklamamalı -- dilim analizi
  üretilip kabul edildiyse, içindeki bir finalistin downstream rotasının
  desteklenmemesi dilimin bitmediği anlamına gelmez.
- **Tur 1'de elenen ismin dispozisyonu.** Öneri: elenen isim **C değildir**
  -- C, finalistlerin küresel karşılaştırmasından çıkan bir hüküm; Tur 1
  elemesi "bu dilimden finale ilerlemedi" demek. Ayrı bir `not_advanced`
  disposition'ı ve ayrı bir olay ailesi gerekiyor; bucket değişimine
  dayalı bayatlama yalnız Tur 2'nin nihai screen olayına uygulanabilir.
  Kesinleşmedi.
- **Tur 1 olay granülerliği.** Öneri: ticker başına olay değil, **dilim
  başına tek toplu olay** (`round_id`, `slice_id`, evren snapshot kimliği,
  finalistler, finalist olmayanlar, ticker bazlı gerekçeler, sonuç hash'i).
  Gerekçe: Tur 1'de model 25 bağımsız karar vermiyor, 25 şirketi birbirine
  göre değerlendirip tek bir sıralama üretiyor; ticker başına olay bu
  karşılaştırmalı hükmü yapay olarak parçalar. Asıl maliyet satır sayısı
  değil **commit sayısı**: 500 ticker'ı 500 ayrı read-modify-write ile
  yazmak felaket, 20 dilimi 20 atomik batch'le yazmak makul. Kesinleşmedi.
- **Tekrarlanan `route_unsupported` gürültüsü.** Başlık 6 kalıcı dışlama
  bırakmadığı için bloklu bir isim her turda yeniden A olup yine aynı
  yerde bloklanacak. Öneri: blocker'ın parmak izini (setup + önerilen rota
  + katalog sürümü) saklayıp aynı üçlü tekrar ettiğinde yeni iş
  üretmemek. Kesinleşmedi; ilk turlarda gürültü ölçülmeden genel bir
  susturma kurmak değişmiş bir fırsatı bastırabilir.
- **Oturum sıfırlama sınırı.** Pitch'te sonlandırma ve maddi setup
  değişiminde taze oturum önerildi (bkz. resume revizyon notu), kesin
  politika yazılmadı.

### Ölçek hükmü

Dürüst değerlendirme: **bugünkü hâliyle bu 500 isimlik bir sistem değil.**
`config/universes/sp500.json` hedefi gösteriyor, bugünkü orkestrasyonun o
hedefi taşıdığını göstermiyor. Kabaca: domain tasarımının %70-80'i 500'de
ayakta kalır (candidate/tez/portföy ayrımı, ticker-sürekli kimlik, açık
tezlerin keşiften çıkarılması, iki aşamalı eleme, `thesis_opened` sermaye
kapısı, beş eksenli tez modeli); yürütme ve persistence tasarımının
%20-30'u kalır.

500'e çıkmak için feda edilmesi gerekenler: her mekanik adımda insan
komutu, ticker başına Tur 1 commit'i, tek dosyayı her seferinde baştan
yazma, bütün finalistleri tek Tur 2 oturumunda karşılaştırma (20 dilimden
üçer finalist 60 isim eder -- tam pack ile 60 ismi tek oturumda
karşılaştırmak, tasarımın kaçtığı bağlam kalitesi sorununu bir üst
katmanda yeniden üretir), ve her adayın aynı derinlikte ilerlemesi
beklentisi (sistem bir öncelik kuyruğu ve aktif-zincir kapasitesi
taşımalı).

Feda edilmeyecekler: tek mantıksal gerçeklik kaynağı, append-only geçmiş,
insanın gerçek sermaye üzerindeki tek yetkisi, company/security/portfolio
ayrımı. Bunlar ölçeğin sorunu değil, ölçeği güvenli tutan kısımlar.

Not: haftalık tez kontrolü evren büyüklüğüyle değil **açık tez sayısıyla**
ölçekleniyor; 500 isim bu tarafı doğrudan büyütmüyor. Yük discovery ve
tez-öncesi araştırmada.

### Uygulama sırası

Önerilen sınır: *önce olayların anlamını, atomikliğini ve kim tarafından
kabul edildiğini doğru kur; ardından tek bir 87 isimlik turu uçtan uca
yürüt; ölçek optimizasyonlarını ancak bu akıştan ölçüm aldıktan sonra
ekle.*

**İlk üretim olayından önce** (şemaya şimdi girmezse sonradan göç pahalı):
onay semantiğinin ayrılması; tek commit kapısı (batch kimliği, monoton
sequence, atomik commit sınırı -- segment/snapshot şart değil); Tur 1/Tur 2
olay semantiği (round manifesti, dilim kimliği, terminal dilim durumları).

**İlk B adayı ve ikinci turdan önce:** B terfi fallback'inin düzeltilmesi;
aktif zincire gelen screen'in yalnız evidence olması; `completed_workflows`
provenance alanları.

**İlk tez açılmadan önce:** atomik `pitch → thesis_opened`; nedensel
idempotency anahtarı; ticker başına tek açık tez invariant'ı; beş eksen ve
`wind_down`. (Bunları sonradan eklemek eski `retired` olaylarının ne
anlama geldiğini yorumlama göçü yaratır.)

**İlk gerçek işlemden önce:** işlem olayı, işlem idempotency'si, tez
referansı, portföy uzlaştırma olayı ve `position_unknown`. Burada "sonra
düzeltiriz" tehlikeli: işlem yokluğunu `flat` sayan geçmiş veri
üretildiğinde hangi dönemlerin gerçekten uzlaştırıldığı geri kurulamaz.

### Şimdi yapılmaması gerekenler (YAGNI)

Fiziksel defter segmentasyonu ve projection snapshot'ları (87 isimde tek
kilitli append + tam replay çalışır; şemada sequence/batch sınırını
hazırlamak yeter). 500 için hiyerarşik Tur 2 (önce 87'de gerçek finalist
sayısı ve bağlam kalitesi ölçülmeli). `route_unsupported` için
fingerprint/cooldown. Genel amaçlı bir `reconciliation_required` durumu.
Tam `superseded` mekanizması (re-underwrite pitch + atomik tez değiştirme
+ pozisyon yeniden bağlama). Otomatik nitel tetikleyici yorumlama, broker
entegrasyonu, çoklu hesap, aynı anda birden fazla açık tez, arka plan
scheduler'ı.

Ayrıca: her olası lifecycle kombinasyonu için ayrı olay tipi üretilmemeli.
Olaylar gerçek domain eylemlerini taşımalı; `funded`, `monitoring_required`,
`watchlist` gibi değerler mümkün olduğunca projection'dan türetilmeli.

## Gözden geçirme — 2. tur (2026-08-15)

Aynı codex oturumunda on tur daha (t8-t17). 1. tur ilke seviyesindeydi; bu
tur mekanizmaya indi: olay şeması, defterin fiziği, eşiklerin veri modeli,
skill sözleşmeleri, insan yüzeyi. Sonunda beklenmedik bir yere vardı --
temelin (capital policy) eksik olduğu yerine.

Turun kapanış hükmü: **"Tasarım yanlış değil; erken kurumsallaşmış. En
büyük hata olay şemasında veya tez eksenlerinde değil, henüz tanımlanmamış
bir capital policy varmış gibi portföy katmanını tasarlamamızdı."**

### Kodda ve config'te doğrulanan kusurlar

Aşağıdakiler tasarım görüşü değil, açılıp görülmüş davranışlardır.
Tamamı bu repoda doğrulandı.

**Defter ve kalıcılık**

| Kusur | Yer |
|---|---|
| `append_events()` tüm defteri okuyup mevcut+yeni içeriğin tamamını `os.replace` ile yazıyor; iki süreç aynı sürümü okursa son yazan diğerinin olaylarını sessizce siliyor | [pei_workflow.py:323, 337](../src/adapter/pei_workflow.py) |
| Duplicate `event_id` kontrolü yalnız sürecin okuduğu eski sürümü gördüğü için eşzamanlı yazarlara karşı koruma sağlamıyor | [pei_workflow.py:334](../src/adapter/pei_workflow.py) |
| `events.jsonl` git'te izleniyor ve yedi commit'inin ikisi "clean reset" ("Reset PEI workflow history for a clean start", "Reset the shortlist idea run for a clean restart"); append-only'i git zorlamıyor | `git log` |
| Olay zarfı `run_id` + `ticker` merkezli; round, thesis ve portfolio gibi farklı aggregate'ları doğal temsil etmiyor | olay şeması |

**Workflow ve projection**

| Kusur | Yer |
|---|---|
| `thesis_opened` yalnız tüketiliyor; onu üreten hiçbir komut/extractor/geçiş yok | [pei_workflow.py:548](../src/adapter/pei_workflow.py) |
| `check_triggers()` `state != "waiting"` olan her adayı atlıyor → açık tezin eşikleri bu yoldan hiçbir zaman kontrol edilmiyor | [pei_workflow.py:1610](../src/adapter/pei_workflow.py) |
| `source_interpretation_corrected` tek olayda üç iş yapıyor: kaynak düzeltmesi, B→A terfi (`promoted_to`), workflow rotası değişimi (`mapped_workflow`) -- genel amaçlı state yama kanalı olmuş | [pei_workflow.py:524-547](../src/adapter/pei_workflow.py) |
| `thesis_tracker` config'te tek seferlik terminal candidate adımı: `pack_step:null`, `required_workflows:["pitch"]`, `allowed_next:[]` -- oysa doğası gereği `thesis_id` ile anahtarlanan tekrarlayan bir lifecycle işi | [config/pei-workflows.json](../config/pei-workflows.json) |
| `candidate_screened`'in bucket'ı karşılaştırma kümesi kimliği taşımıyor; dilim-göreceli hüküm mutlak durum gibi projekte ediliyor | project() |
| `waiting_for_trigger` bir domain olayı değil, adayın türetilmiş durumunu olay tipi olarak taşıyor | olay sözlüğü |
| `run_codex_analysis()` `required_context_artifacts`'i fiilen kullanmıyor (1. turdan devreden bilinen bug) | [pei_workflow.py:892](../src/adapter/pei_workflow.py) |

**agy / yapılandırılmış çıkarım**

| Kusur | Yer |
|---|---|
| 24.000 karakter sınırı metni kesmiyor ama tüm çıkarımı `PeiWorkflowError` ile durduruyor; domain sınırı Windows argv taşıma sınırına bağlanmış. Ayrıca `result_attached` bundan önce yazıldığı için "bekliyor" ile "çıkarım başarısız" ayrılamıyor | [pei_workflow.py:993](../src/adapter/pei_workflow.py) |
| `bucket = c.get("bucket") or "B"` -- eksik bucket sessizce B oluyor | [pei_workflow.py:1261](../src/adapter/pei_workflow.py) |
| `if not raw_ticker: continue` -- boş ticker'lı aday hiçbir hata veya `unaccounted_for` kaydı olmadan atlanıyor | [pei_workflow.py:1258](../src/adapter/pei_workflow.py) |
| Metin agy'ye verilmeden Unicode sanitizasyonundan geçiyor; tanınmayan karakterler `?` olabiliyor, yani extractor immutable artefaktın birebir metnini görmüyor | [pei_workflow.py:959](../src/adapter/pei_workflow.py) |

Teşhis: **sistem operasyonel hatalarda fail-closed, anlamsal eksikliklerde
fail-open.**

**Portföy**

| Kusur | Yer |
|---|---|
| `portfolio.py` append-only işlem defteri değil, `upsert_position`/`delete_position` kullanan mutable pozisyon tablosu; yalnız `shares` ve tek `avg_cost` taşıyor -- para birimi, uzlaştırma provenance'ı, kurumsal işlem ve `position_unknown` yok | [portfolio.py:126, 173](../src/adapter/portfolio.py) |
| Bridge'de işlem kaydı ve broker uzlaştırma komutu yok (dokuz komut: status, artifact, prepare, validate, approve, events, catalog, thesis, universe) | [us_pei_dashboard_bridge.py:254](../scripts/us_pei_dashboard_bridge.py) |
| `mandate.json` sermaye tabanı, kayıp bütçesi, ağırlıklandırma ve yoğunlaşma çıpası içermiyor -- kod hatası değil, portföy otomasyonunu bloklayan config boşluğu | [config/mandate.json](../config/mandate.json) |

**Bu turda doğrulanmayan iddialar.** Kodlamadan önce ayrıca açılmalı:
`call_agy_structured`'ın dönen nesnede yalnız `dict` kontrolü yapıp agy'nin
`SUCCESS` beyanına güvenmesi; pitch çıkarım şemasının `null` alanlara ve boş
`kill_criteria`'ya izin vermesi; idea şemasının boş `candidates` dizisini
kabul edip dondurulmuş girdi listesiyle uzlaştırma yapmaması;
`attach_result()`'ın artefakt/manifest/olay sıralaması; `long-short-pitch`
skill'inin "intended alpha / unwanted risk" ayrımını yapılandırılmış çıktı
olarak üretmemesi.

### Skill denetimi

Üç skill okundu (paket sürümü 0.1.31). Ders şu: **bir skill'in hangi soruyu
cevapladığını okumadan ona devretmek, karşılığı olmayan çek yazmaktır.**

| Skill | Tasarımın beklediği | Gerçekte yaptığı | Hüküm |
|---|---|---|---|
| `portfolio-risk-management` | Portföydeki tüm isimler arasında ağırlık dağıtımı / rebalans | Tek security için sizing, hedge veya birleşik risk planı; portföy yalnız kısıt girdisi | **Uyuşmuyor** → Başlık 4 karar 5 iptal |
| `thesis-tracker` | Haftalık tüm tezleri tarayan mekanik sağlık motoru + derin inceleme | Bir tezi kanıtla güncelleme, pillar/status/action değerlendirmesi, append-only changelog | Derin incelemeyle **uyuyor**, mekanik taramayla uyuşmuyor |
| `idea-generation` | Dilim içi finalist seçimi ve batch içinde A/B/C | Verilen aday setini araştırma önceliğine göre A/B/C/Reject sınıflandırma | **Kullanılabilir**, ek sözleşme şart |

Bunlardan çıkan üç uygulama kuralı:

1. **Mekanik tarama repo'nun işi, tracker'ın değil.** İki ayrı paket
   gerekiyor: küçük deterministik `monitoring_snapshot` (mekanik motorun
   girdisi) ve zengin `thesis_update_pack` (sapma sonrası tracker'ın
   girdisi). Açık işlerdeki "`thesis_tracker`'a `pack_step` bağlanmalı"
   maddesi bu yüzden yanlış yazılmıştı.
2. **Stage 1'de skill'in A/B/C'si bastırılmaz**, ama `candidate.bucket`
   gibi bağlamsız kanonik bir alana da yazılmaz -- `scope=slice`,
   `comparison_set_id`, `skill_version` taşıyan bir değerlendirme olarak
   saklanır. `Reject` (analitik hüküm) ile `not_advanced` (kapasite/seçim
   sonucu) birleştirilmez.
3. **Finalist kotası tavan olmalı, hedef değil.** idea-generation paketinin
   workflow referansı "Kill weak ideas aggressively. A shorter, sharper
   list is better than a broad undifferentiated screen." diyor
   (`references/workflow.md:78` -- SKILL.md'de değil). Zayıf dilim sıfır
   finalist üretebilir. Not: "en fazla üç" sayısı metinden gelmiyor, bizim
   kapasite kararımız.

Skill'in kendi sınırı tasarımın bir varsayımını da doğruluyor:
idea-generation "`Advance to deeper work` bir araştırma önceliği durumudur;
yatırım tavsiyesi, onaylanmış pozisyon veya cazip giriş noktası değildir"
diyor. Yani A olmak ile alınabilir olmak arasına skill'in kendisi de mesafe
koyuyor.

### Olay sözlüğü

1. turda "olayların anlamı ilk üretim olayından önce çözülmeli" denmişti;
bu turda sözlük çıkarıldı. Ayırt edici test:

> **Olay, geçmiş zamanda olmuş tek bir gerçeği mi anlatıyor, yoksa bir
> tablonun state'ini mi tarif ediyor?**

Bugünkü sekiz tipin hükmü: `workflow_prepared` ve `result_attached` yaşar
(artefakt alımı gerçek bir olay); `candidate_screened` yeni üretimde ölür
(A/B/C artık toplu batch sonucundan türetilir, aynı gerçeği iki kez
kaydetmenin anlamı yok); `workflow_completed` yanlış modellenmiş (aynı anda
extraction, kabul, rota seçimi ve candidate geçişi taşıyor);
`waiting_for_trigger` yanlış modellenmiş (`trigger_registered` /
`trigger_satisfied` / `trigger_cancelled` olmalı, "waiting" projection'dan
türer); `source_interpretation_corrected` bölünmeli (B→A terfi için
`promotion_evaluated`, dar anlamlı kaynak düzeltmesi ayrı);
`manual_review_required` gerçek bir iş talebi ama candidate'ı otomatik
`blocked` yapmamalı.

Zarf da değişmeli: her olayda zorunlu `run_id` + `ticker` istemek, round
kapanışı ve portföy uzlaştırması gibi olaylara sahte kimlik koydurur. V2
zarfı en az `sequence`, `batch_id`, `subject_type`/`subject_id`, opsiyonel
ticker/run/round/thesis kimlikleri, `causation_id`, `occurred_at` ve
`recorded_at` taşımalı.

**Kimlikler ayrılmalı:** `workflow_request_id` (yapılması istenen mantıksal
iş) ile `attempt_id` (o işi üretmek için yapılan belirli deneme). Reject
edilen deneme kapanır, aynı request altında yeni attempt açılır; teknik
hata da reject değil, başarısız attempt'tir. Kabul kararı ayrı bir olayla
kaydedilir ve `accepted`/`accepted_with_override`/`rejected` değerlerini
alır -- override edilmişse `proposed_outcome`, `accepted_outcome`,
`overridden_fields` ve gerekçe birlikte durur. **Olgusal hatalar (yanlış
sayı, yanlış kaynak, yanlış peer) override edilemez; reject ve yeni attempt
gerektirir.** Override yalnız açık insan hükümlerinde (bucket, önem
derecesi, eylem yorumu) kullanılabilir ve canlı para riskini bastırıyorsa
`valid_until`/`review_due_at` taşımak zorundadır.

**Kanonik defter git'ten çıkmalı.** Git kodun ve şemaların geçmişidir,
olay defterinin yazma otoritesi değildir: iki dal aynı `sequence`'ı üretir,
çatışmasız merge iki batch'i iç içe geçirip atomikliği bozar, rebase/amend
geçmişi yeniden yazar (ve bu repoda zaten iki kez yapılmış). Öneri: SQLite
üzerinde tek yazarlı, transaction'lı defter; git'te kod, şema, config ve
istenirse mühürlü checkpoint manifestleri. "Repo'dan yeniden üretilebilir"
ilkesi de düzeltilmeli: *git code revision + kanonik ledger checkpoint +
içerik-adresli artefakt deposu.*

### Eşikler ve izleme sözleşmesi

Başlık 4 karar 3 mevcut hâliyle uygulanabilir değil. Temel hata şema
seviyesinden önce: `first_rejection` tam bir izleme sözleşmesi değildir --
en erken reddetme sebebi olabilir ama tezin bütün falsifier'larını ve kill
criterion'larını taşımaz.

**Yeni çerçeve:** agy metni doğrudan ölçülebilir eşiğe çevirmez; pitch'in
falsifier ve kill criterion'larından **kaynak bağlantılı taslak izleme
sözleşmesi** çıkarır. İnsan bunu pitch kabulüyle aynı ekranda onaylar.
Sert sınır: metinde sayı, dönem veya açık operasyonel tanım yoksa agy
bunları icat edemez -- sonuç `not_mechanically_evaluable` olur. İnsan
sayısal kural eklerse kökeni `human_authored`'dır, "metinden çıkarıldı"
diye sunulmaz.

Bir mekanik kural `(metrik, operatör, eşik)` değildir; metrik tanımı,
birim, dönem/TTM, kaynak, tolerans, tek dönem mi ardışık mı, revizyon
politikası ve eksik veri davranışı gerekir. **Eşik ihlali tezi otomatik
`broken` yapmaz** -- mekanik sistem yalnız sapma üretir; eksen değişimi
insan hükmü ister. (Aksi hâlde bir veri eşleme hatası gerçek pozisyon
çıkışı tetikleyebilir.)

**Nokta-zamanlı veri.** Her gözlem `period_end` (ekonomik dönem) ve
`known_at` (ne zaman bilinebilirdi) taşır. Restatement eski gözlemi
silmez; geçmiş `no_deviation` kaydı doğru kalır, yeni kontrol
`retrospective_breach_for_period` ile ayrıca işaretlenir. Böylece ne geçmiş
kontroller yalan olur ne de karar kalitesi hindsight'la bozulur.

**Eşikler değiştirilebilir ama yerinde güncellenmez.** Ayrı bir
`monitoring_policy_version` ve `effective_at` gerekir; eski sürüm geçmiş
tarihler için geçerli kalır. Revizyon nedeni ayrılmalı:
`extraction_correction`, `metric_mapping_change`, `clarification`,
`thesis_amendment`. Sonuncusu sıradan bakım değildir, re-underwrite ister.
Eski eşik breach vermişken yeni eşik gevşetiliyorsa sistem bunu açıkça
göstermek zorunda (*eski kural: breach / yeni kural: pass*) -- yatırımda
klasik kendini kandırma biçimi budur.

**Ölçülemeyen koşullar.** Tasarım burada kendi kendini yalanlıyordu:
"haftalık oturumda listelenir" deniyor ama sapma yoksa oturum açılmıyor,
yani listeyi kimse görmüyor. Her nitel kural beklenen kanıt kaynağı,
`review_mode` (olay-güdümlü / takvim-güdümlü), `next_review_due` ve azami
bayatlık süresi taşımalı. Haftalık koşu vadesi gelen/geçen nitel
kontrolleri gösterir; vadesi gelmiş kontrol yapılmadıysa o tez için sonuç
`no_deviation` **olamaz**.

### Kurumsal işlemler ve lot

Kurumsal işlemler hem defteri hem izleme sözleşmesini aynı anda bozuyor:
4:1 bölünmede pozisyon işlemlerden türetiliyorsa 100 hisse görünmeye devam
eder (gerçekte 400), ve "fiyat 80'in altına inerse" eşiği fiyatı 45 görüp
tez bozulmadığı hâlde anında tetiklenir. Çözüm eşikleri fiyat cinsinden
yasaklamak değil (insanlar tezlerini fiyat cinsinden düşünür); kural
`price_basis_date` ve `adjustment_policy` taşır, kontrol fiyatı ve eşiği
aynı bazda karşılaştırır. **Kurumsal işlem tespit edilip adjustment
tamamlanmamışsa sonuç `deviation` değil `indeterminate` olmalı.**

V1 için tam lot motoru YAGNI (vergisel otorite broker'dır), ama "ortalama
maliyet + yılda bir ekstre" de yetersiz -- bir yıl unutulmuş işlem veya
yanlış adet taşımak gerçek para tarafında kabul edilemez. Ara çözüm: her
fill append-only işlem olayı, broker işlem kimliği ve ekstre referansı,
uzlaştırma snapshot'ında güncel adet ve broker-reported average cost, her
işlemden sonra veya en az aylık uzlaştırma.

**Manuel idempotency:** işlem alanlarından kusursuz duplicate tespiti
matematiksel olarak mümkün değil (aynı gün aynı fiyattan iki meşru kısmi
alım olabilir). Kimliği kullanıcıya uydurtmak yerine sistem giriş oturumu
başında üretir; fingerprint yalnız uyarı doğurur. Kalan belirsizliği
uzlaştırma yakalar -- manuel kayıt "var olanı biliyoruz" der, "başka işlem
yok" demez.

**Para birimi üç katman:** security'nin yerel getirisi (USD), yatırım
hükmünün başarısı (USD, tercihen relatif), portföye katkı (portföyün baz
para biriminde, FX etkisi ayrı gösterilir). `portfolio_base_currency` açık
bir ayar olmalı; operatörün Türkiye'de olması baz para biriminin otomatik
TRY olduğu anlamına gelmez. Ledger hiçbir tarihi işlemi sonradan farklı
kura çevirmez.

### 1. tura göre ne değişti

| Konu | 1. tur | 2. tur |
|---|---|---|
| Tez modeli | Beş kalıcı eksen | İki otoritatif gerçek + bir tarihli değerlendirme |
| `wind_down` | Elle yönetilen lifecycle ekseni | `broken` tez + sıfır olmayan exposure'dan türetilir |
| `superseded` | Şemada rezerv | V1'den çıkarıldı |
| `thesis_opened` | Sermaye karşılaştırmasına kabul kapısı | Resmî, izlenen araştırma görüşü (sermaye tarafı capital policy'ye kaldı) |
| Başlık 4 karar 5 | Aylık rebalans skill'e devredilir | İptal; skill yalnız tekil sizing/hedge için |
| Aylık ritim | "Aylık rebalans" | "Aylık portföy gözden geçirmesi", varsayılan `no_change` |
| Analitik kabul | Her çıktı için `analysis_proposed` + `analysis_reviewed` | Geri çekildi; ara adımlar provisional, insan kapısı dört yerde |
| Stage 1 sözlüğü | A/B/C bastırılır, yalnız nominated/not_advanced | Skill'in A/B/C'si korunur ama `comparison_set_id` ile kapsamlandırılır |
| Tur mekaniği | Terminal dilim durumları, partial close, coverage kapanışı | V1'den ertelendi; kayan batch yeterli |
| Eşik çıkarımı | agy `first_rejection`'ı ölçülebilir eşiğe çevirir | agy yalnız taslak sözleşme çıkarır; metinsel koşul + inceleme vadesi zorunlu |
| Lot | Lot seviyesi takip + satışta lot eşleştirme | Fill olayları + broker average cost + uzlaştırma |
| Artefakt | Content-addressed depo + insan görünümü | V1'de immutable yol + SHA-256 + attempt bağlantısı |
| Onay yüzeyi | JSON/CLI yeterli | İnsan-okunabilir karar yüzeyi birinci sınıf gereksinim |
| Mandate | Tek `mandate.json` | `research_mandate` + (yazılmamış) `capital_policy` |

## Gözden geçirme — 3. tur: skill envanteri (2026-08-16)

Aynı codex oturumunda on beş tur daha. Konu: eklentideki (public-equity-
investing 0.1.31) **23 skill**. Hangisine ihtiyaç var, nerede ve nasıl
kullanılır, sisteme nasıl bağlanır, birbirleriyle ilişkileri ne.

Ölçüt sıkı tutuldu: sistem bir araştırma/izleme defteri; capital policy yok,
benchmark yok, tek operatör, haftada 6-9 saat, long-only, opsiyon/kaldıraç/
açığa satış yok, aylık gözden geçirme varsayılanı `no_change`.

### 23 skill

Tablodaki "hüküm" hedef mimarideki adaylığı ifade eder; gölge vaka kapısını
geçmeden prodüksiyon yetkisi anlamına gelmez. Pack ve çıktı adları hedef
sözleşmelerdir, bugünkü kodun durumu değil.

| Skill | Hüküm | Rol | Nerede kullanılır | Koşul / tetikleyici | Pack | Çıktı | İnsan kapısı |
|---|---|---|---|---|---|---|---|
| `long-short-pitch` | Çekirdek | Lead | Long-only karar modunda resmî görüş adayı, bear case, falsifier'lar | Vaka pitch'e hazır ve kanıt yetenekleri mevcut | `pitch_decision` | `pitch_decision_envelope` + sürümlü nesne referansları | **Evet** — tez açılmadan önce |
| `thesis-tracker` | Çekirdek | Lifecycle | Mevcut tezi yeni kanıt karşısında yeniden değerlendirir; yeni tez açamaz | Kanıt/sapma, `review_due_at` veya insan talebi | `thesis_update` | `thesis_assessment` | Governance değişimi / kapanış önerisinde **evet** |
| `earnings-deep-dive` | Çekirdek | Lead/support | Yeni sonucun beklentiye, vakaya veya açık teze etkisi | `evidence_available` — yalnız tarih gelmesi yetmez | `event_evidence` | `post_print_assessment` | Hayır; domain etkisi tracker/pitch kapısında |
| `comps-valuation` | Çekirdek | Support | Pitch'in kullanacağı savunulabilir `valuation_anchor` | Güncel/destekli anchor yok | `valuation` | `valuation_anchor` | Hayır; eksik peer gerekçesi kontratı bloklar |
| `company-tearsheet` | Çekirdek | Support/lead | Kaynaklı issuer baseline + veri boşlukları | Baseline yok, bayat ya da maddi şirket değişimi | `issuer_baseline` | `issuer_baseline_assessment` | Hayır; provisional evidence |
| `idea-generation` | Çekirdek | Lead (batch) | Evreni batch-göreceli araştırma önceliğine ayırır | Lifecycle kanıtlandıktan sonra açılan batch | `screen_batch` | `screen_batch_result` | Hayır; kalıcı dışlama veya tez yaratamaz |
| `earnings-preview` | Koşullu | Support | Sonuç öncesi beklenti barını dondurur | Doğrulanmış yaklaşan sonuç + açık tez veya öncelikli vaka | `issuer_baseline` + pre-event overlay | `expectation_snapshot` | Hayır; çıktı değiştirilmeden mühürlenir |
| `scenario-sensitivity-generator` | Koşullu | Support | Var olan base case üzerine diagnostic overlay | Sürümlü `base_case_ref` var ve belirsizlik gerçekten senaryo istiyor | `valuation` + `base_case_ref` | `scenario_overlay` | Hayır |
| `memo-builder` | Koşullu | Support | Dönem-sonu sentez; lifecycle yönetmez | Kullanıcı açıkça ister | presentation payload | `period_end_memo` | Hayır; yalnız sunum |
| `initiating-coverage` | Escalation | Lead | Baseline + support + pitch'in çözemediği şirket-geneli underwriting boşluğu | Bloklu pitch + belgelenmiş capability gap + insan onayı | Escalation açılırken sabitlenir | `initiation_report`; doğrudan tez açamaz | **Evet** — çalıştırılmadan önce |
| `public-equity-investing` | Meta | Meta | Ortak kaynak/invocation/support-routing standartları | Her plugin-backed koşunun policy bağımlılığı | — | — | — |
| `catalyst-calendar` | Gereksiz | — | Tarih ve pencere yönetimi deterministik trigger katmanının işi | | | | |
| `dcf-model-builder` | Gereksiz | — | Workbook bakım yükü kapasiteyi aşar | | | | |
| `three-statement-model-builder` | Gereksiz | — | Aynı bakım ekosistemi; entegre tahmin workbook'u orantısız | | | | |
| `equity-model-update` | Gereksiz | — | Güncellenecek kanonik model tutulmuyor | | | | |
| `model-audit-tieout` | Gereksiz | — | Workbook yoksa audit nesnesi de yok | | | | |
| `portfolio-risk-management` | Gereksiz | — | Capital policy/benchmark yok; ayrıca portföy-geneli allocator değil | | | | |
| `financials-normalizer` | Gereksiz | — | Normalizasyon otoritesi deterministik PIT/XBRL hattı; LLM ikinci otorite olamaz | | | | |
| `event-driven-analyzer` | Gereksiz | — | Birleşme/özel durum expected-return hattı ürün sınırı dışı | | | | |
| `economic-impact-report` | Gereksiz | — | `external_event` subject modeli ve çok-ticker aktarımı yok | | | | |
| `deck-report-qc` | Gereksiz | — | Dış dolaşıma girecek paket yok | | | | |
| `meeting-prep` | Gereksiz | — | Toplantı/diligence-call akışı yok | | | | |
| `user-context` | Gereksiz | — | Kanonik bağlam repo'nun mandate/config'i; skill de ordinary workflow'da çağrılmamasını söylüyor | | | | |

### Skill uyum denetimi — üç uyuşmazlık

Ders: **bir skill'in hangi soruyu cevapladığını okumadan ona devretmek,
karşılığı olmayan çek yazmaktır.** Devretmeden önce şunlar yazılmalı: (i)
cevapladığı kesin soru, (ii) kararın kardinalitesi — ticker mı, tez mi,
pozisyon mu, tüm portföy mü, (iii) N çıktıyı birleştirecek gizli bir karar
kalıp kalmadığı. Üçüncüsü Başlık 4 karar 5 hatasını doğrudan yakalardı.

- **`portfolio-risk-management`** üç modunun (`position_sizing`,
  `hedge_design`, `integrated_risk_plan`) hepsi tek pozisyon hakkında;
  portföy orada girdi kısıtı, kararın konusu değil. Portföy-geneli allocator
  değil → Başlık 4 karar 5 iptal.
- **`thesis-tracker`** derin inceleme için doğru araç ama **mekanik taramayı
  sahiplenmiyor**: bütün açık tezleri LLM'siz dolaşmak, PIT gözlemleri
  eşiklerle karşılaştırmak ve kapsama kapatmak repo'nun monitoring
  motorunun işi. Ayrıca config'te tek seferlik terminal candidate adımı
  olarak modellenmiş; `thesis_id` ile anahtarlanan tekrarlayan lifecycle işi
  olmalı.
- **`idea-generation`** dilim üzerinde çalışabilir ama iki turlu yapıyı
  bilmez. Skill'in doğal A/B/C/Reject hükmü bastırılmaz, ama bağlamsız
  `candidate.bucket`'a da yazılmaz — `scope=slice`, `comparison_set_id`,
  `skill_version` taşıyan bir değerlendirme olarak saklanır. `Reject`
  (analitik hüküm) ile `not_advanced` (kapasite/seçim sonucu) birleştirilmez.

### Eklentinin ortak katmanı

`run_codex_analysis` bugün skill'e "referans verdiğin shared dosyaları da
oku" diyor. Bu iyi niyetli ama denetlenemez: hangi sözleşmenin gerçekten
uygulandığı kanıtlanamaz ve eklenti güncellenince aynı workflow sessizce
farklı kurallarla çalışır. Her iş kalemi bir **`contract_manifest`**
taşımalı: plugin sürümü, lead skill yolu + sha256, zorunlu shared
sözleşmeler + sha256, orkestratör override'ları, artefakt ve support
politikası.

Öncelik sırası: *mandate ve ürün sınırı > iş kalemi talimatı > orkestratör
kontratı > focused skill > eklenti varsayılanları.*

Zorunlu analitik sözleşmeler: focused skill'in `SKILL.md`'si ve semantic
output referansları, şemsiyenin cross-skill runtime kontratı,
`pm-judgment-heuristics`, support kullanılıyorsa
`support-layer-routing-contract` ve `equity-research-support-standard`,
değerleme varsa `equity-valuation-pm-standard`.

Güvenle override edilecekler: her substantive koşuda otomatik polished HTML
üretme varsayımı, her adımda "full working analysis", benchmark/active
weight/position action zorunlulukları, plugin-local `user-context` hafızası,
capital policy yokken sizing/hedge hükümleri, dış dolaşım paketleme
standartları.

Kısacası: **eklentinin yatırım muhakemesi ve kanıt disiplini alınır, sunum
bürokrasisi ve portföy varsayımları ölçeğimize göre daraltılır.**

### Pack mimarisi

Bugünkü `pack_step` bir veri sözleşmesi değil: sistem büyük bir üst-küme
pack kuruyor, sonunda bazı alanları budayarak adım varyantı üretiyor —
yani hesaplama maliyeti zaten ödenmiş oluyor. Doğrusu **kanonik snapshot →
pack recipe → adıma özel materialized pack**. "Her adım aynı gerçeği görsün"
hedefi aynı JSON'u vermekle değil, hepsini aynı snapshot kimliklerinden
üretmekle sağlanır.

Yedi pack sözleşmesi: `screen_batch`, `baseline_analysis`,
`valuation_analysis`, `earnings_update`, `pitch_decision`,
`monitoring_snapshot` (LLM değil, mekanik motorun typed girdisi),
`thesis_update`. `dashboard_payload` sekizinci pack değil, bunlardan
türetilen sunum yüküdür.

Zaman ekseni tek bir üst `as_of` olamaz; bölümün veri türüne göre zorunlu:
`structural_as_of`; `period_end` + `published_at` + `known_at` + accession;
`market_as_of`; `consensus_as_of`; `event_time` + `observed_at` + tarih
kesinliği; ve pack'in kendi `built_at` + `knowledge_cutoff`'u.

Tur 1 ince pack'i için ilk hedef **ticker başına 1-2 KB**. İçinde kalması
gerekenler: kimlik ve sektör/boyut, 1-2 cümlelik kaynaklı maruziyet özeti,
son finansal dönem (`period_end` + `known_at`), küçük kalite/büyüme seti,
bir-iki sektör-uygun ileri değerleme metriği (ham değer + dilim yüzdeliği),
beklenti yönü, en yakın katalizör ve tarih kesinliği, kalite/bayatlık
bayrakları, eligibility durumu, eksik alanlar, ve batch düzeyi source
registry'ye referans. Çıkması gerekenler: tam tablolar, uzun seriler,
ayrıntılı konsensüs, peer listeleri, uzun valuation history, release metni,
önceki anlatısal sonuçlar, portföy bilgisi ve her türlü işlem dili.
**Güvenlik sınırı:** bir isim bunlarla değerlendirilemiyorsa büyük pack'e
sessizce genişlemek yerine `insufficient_screen_evidence` üretir.

### Çıktı sözleşmeleri ve doğrulama

Katalogdaki `result_contract` değerleri bugün gerçek sözleşme değil, etiket
— kod onları doğrulama için kullanmıyor. Mevcut çıkarım şemalarında
"required" alanların çoğu `null` veya boş liste kabul ettiği için sözleşme
görünürde sert, gerçekte yumuşak.

Sözleşme adlarındaki `action` kelimeleri de yanlış: V1'de üretilmemesi
gereken şey adın içine yazılmış. `post_print_thesis_and_action_implications`
→ `post_print_evidence_and_research_implications`;
`scenario_ranges_and_pm_action_thresholds` → `scenario_overlay_and_
breakpoints`; `expectation_bar_and_triggers` → `pre_print_expectation_
snapshot`; `append_only_thesis_record` → `thesis_assessment_proposal`.

**Üç katmanlı doğrulama.** Şema söz dizimini ve yerel yapıyı (required,
enum, `additionalProperties: false`, `minItems`); validator deterministik
anlamı ve invariant'ları (referans edilen artefakt var mı, anchor
`supported` mı, batch üyeleri tam mı, long-only mandate ihlali var mı,
scenario'nun `base_case_ref`i var mı); insan analitik yargıyı.

Buradan çıkan iki somut kural: `kill_criteria: []` **geçersiz olmalı** —
falsifier'ı olmayan tez, tez değildir. Ve `recommended_expression` şemada
`short` değerini **temsil edebilmeli**, validator onu reddetmeli — şemadan
çıkarırsak modelin gerçekten short önerdiğini görünmez kılar ve ihlal
sıradan bir parse hatasına dönüşür.

**"Tamamlandı" tek kelime olamaz.** Dört ayrı gerçek: `process_succeeded`
(model çıktı verdi), `contract_validated` (şema + invariant geçti),
`human_adjudicated` (yalnız tanımlı kapılarda), `domain_committed` (vakaya/
teze işlendi). `workflow_completed` ancak ikinciden sonra yazılmalı ve
anlamı "ilan edilen sözleşmeyi yerine getiren mühürlü çıktı üretildi"
olmalı — "analiz doğrudur" değil.

**Çıkarım mimarisi değişmeli:** ikinci ve ucuz bir modelin prose'dan tez
sözleşmesi çıkarması kalıcı mimari olmamalı. Analizi yapan ana model aynı
koşuda hem insan-okunur sonucu hem şemalı sidecar'ı üretmeli; agy eski
sonuçların göçü veya kurtarma extractor'ı olarak kalabilir.

### Model/effort politikası

Model skill adına göre değil **(rol, reliance sınıfı)** üzerinden seçilmeli;
aynı comps çağrısı embedded support iken başka, standalone valuation lead
iken başka hata maliyeti taşır.

| İş | Varsayılan | Yükseltme |
|---|---|---|
| Idea-generation dilim taraması | terra/medium | Finalist karşılaştırması terra/high |
| Company-tearsheet embedded support | terra/medium | Sorunlu baseline terra/high |
| Comps embedded valuation anchor | terra/high | Çatışmalı valuation lead sol/high |
| Earnings preview dar snapshot | terra/high | Karmaşık muhasebe sol/high |
| Earnings deep-dive support | terra/high | Vaka lead'i veya çelişkili sonuç sol/high |
| Pitch lead | sol/xhigh | — |
| Mekanik tez kontrolü | **LLM yok** | — |
| Thesis tracker rutin güncelleme | terra/high | `impaired`/`broken`/kapanış önerisi sol/high |
| Scenario overlay | terra/high | — |
| Initiating coverage escalation | sol/xhigh | İnsan onayıyla |

Bugünkü tabloda iki hata var: `thesis-tracker = luna/medium` yanlış
genelleme (tracker artık işletim döngüsünün merkezi ve governance değişimi
öneriyor; luna en fazla sunum/materyalizasyon için), ve
`earnings-preview = sol/high` dar snapshot sözleşmesi için fazla ağır.

### Katalog şeması (v2)

`config/pei-workflows.json` yalnız `workflows` sözlüğü olmaktan çıkmalı:
`catalog_schema_version`, `runtime_defaults`, `policy_dependencies`,
`pack_contracts`, `artifact_contracts`, `validator_sets`, `workflows`,
`dispatch_routes`.

Workflow girdisindeki alanlar ve gerekçeleri: `skill_id` (katalog kimliğini
eklentiye bağlar), `executable` (policy bağımlılığını çağrılabilir
workflow'dan ayırır), `availability` (core/conditional/escalation_only/
disabled), `eligible_roles` (rolü kalıcı yapıştırmadan sınırlar),
`subject_types` (yanlış subject'le çağrıyı önler), `dispatch_eligibility`,
`input_pack` (gerçek pack contract + builder + sürüm), `hard_artifact_
requirements` (skill completion değil, kanıt yeteneği + tazelik + eksiklik
davranışı), `support_policy` (izinli support'lar, hangi boşluk için, bütçe,
`support_may_change_lead: false`), `output_contracts` (koşullu zorunlu
sidecar'lar), `validation_policy`, `model_policy` (rol/reliance kuralları),
`human_gates` (hangi geçiş öncesinde ve hangi koşulda), `lifecycle_
authority` (`may_propose` / `may_commit`), `runtime_contracts`,
`artifact_policy`, `execution_policy` (operasyonel retry ile kontrat
başarısızlığını ayırır).

`workflow_request_id`, `attempt_id`, gerçek `execution_role` ve seçilmiş
support bütçesi katalog alanı değil, runtime iş kalemi alanıdır.

### Bu bir skill orkestratörü değil

Skill'lerin sahiplendiği: yatırım sorusunun analitik yöntemi, peer seçimi ve
değerleme yorumu, earnings-quality muhakemesi, variant perception ve
falsifier üretimi, yeni kanıtın tez açısından yorumu.

Platformun sahiplendiği: gerçeklik/kimlik/zaman, hangi kanıtın gerçekten
geldiği, modelin tam olarak ne gördüğü, çıktının sözleşmeyi karşılayıp
karşılamadığı, hangi geçişin önerildiği ve kimin onayladığı, yeniden
çalıştırmanın duplicate üretmemesi, insanın bugün ne yapması gerektiği.

**Yazılım işinin %75-85'i skill çağırmanın dışında.** Doğru ad:
*plugin-backed research operations platform*. Skill/sağlayıcı domain
olaylarında otorite değil, yalnız provenance olmalı.

Skill'in kapsamadığı işler (boyut: küçük = birkaç gün, orta = 1-2 hafta,
büyük = 3-5 hafta; haftada 15-20 saat varsayımıyla):

| İş | Boyut |
|---|---|
| Domain sözlüğü ve kimlikler (event/request/attempt/artifact, `security_id`, research case, episode, thesis, comparison set) | Orta |
| Kanonik defter: tek yazarlı transaction, atomik batch, lineage | Büyük |
| Projection/read-model katmanı | Büyük |
| Artefakt registry ve staging, yetim artefakt kurtarma | Orta |
| Research-case/episode orkestratörü: lead kilidi, support bütçesi, retry, seri commit | Büyük |
| Katalog + `contract_manifest` | Küçük-orta |
| Pack builder mimarisi (kanonik snapshot → pack recipe) | Büyük |
| Structured sidecar + contract validator | Büyük |
| Evidence collector (SEC `items`, 8-K Item 2.02, accession, kanıt yeterliliği) | Orta |
| Trigger/window yöneticisi | Orta |
| Tez lifecycle ve materializer | Orta-büyük |
| Mekanik monitoring motoru (typed rule, PIT/restatement semantiği) | Orta |
| Operatör yüzeyi (kuyruk + adjudication ekranı) | Büyük |
| Discovery/batch motoru | Orta-büyük |
| Portföy günlüğü ve uzlaştırma | Büyük |
| Tutarlılık/kurtarma araçları | Orta |
| Eval/regresyon paketi (plugin sürüm karşılaştırması) | Orta |
| Çalıştırma izolasyonu ve plugin sürüm pinleme | Orta |

En kritik teknik yol ilk sekizi; bunlar tamamlanmadan daha fazla skill
eklemek yalnız daha fazla doğrulanamayan metin üretir.

### Kademeli devreye alma

**Kademe 1 — dikey dilimi kanıtla.** `company-tearsheet`, `comps`,
`long-short-pitch`, `earnings-deep-dive`, `thesis-tracker`. Pitch ve tracker
gölge vaka kapısından geçmeden lifecycle'a bağlanmaz.
`public-equity-investing` yalnız policy bağımlılığı olarak yüklenir.

**Kademe 2 — ölçüm.** Aynı beş skill gerçek kanıt döngülerinde ölçülür:
kontrat geçme oranı, olgusal hata, yasak action üretimi, insan adjudication
süresi, support ihtiyacı, maliyet. Her workflow için birkaç sabit vaka
üzerinde eklenti ile yerel ince prompt karşılaştırılır.

**Kademe 3 — ölçüm sonrası.** `idea-generation` (lifecycle çalışmadan yeni
vaka hacmi üretmemek için sona bırakılır), `earnings-preview` (dar snapshot
sözleşmesiyle), `scenario` (base-case şartı ve gerçek ek karar değeri
kanıtlanırsa), `initiating-coverage` (tekrarlayan ve belgelenmiş capability
gap görülürse), `memo-builder` (dönem-sonu sentez ihtiyacı fiilen doğarsa).

Gereksiz sınıfındakiler bir sonraki kademe değildir; ürün sınırı
değişmedikçe açılmazlar.

### Özeleştiri

3. turun kendi sonuçlarına yönelttiği eleştiriler:

- **Triyaj kanıt değil hipotez.** Skill metinlerini okumak, skill'in neyi
  iddia ettiğini kanıtlar; bizim verimizle kaliteli çalıştığını, kullanışlı
  çıktı verdiğini, birleştiğinde hata büyütmediğini veya haftalık kapasiteye
  uyduğunu kanıtlamaz.
- **Yine erken kurumsallaştık.** Sekiz bölümlü katalog, yedi pack ailesi,
  validator kural dili ve rol×reliance matrisi hedef mimari için makul, ilk
  çalışan sürüm için ağır.
- **Başarı ölçütümüz yok.** "Kontrata uydu" ile "yatırım araştırmasına değer
  kattı" farklı şeyler; skill başına küçük bir insan puanlama rubriği
  olmadan model/effort kararları süslü tahmindir.
- **Aynı sağlayıcıdan gelen lead ve support bağımsız kanıt değildir.** Comps
  ile pitch aynı varsayımı tekrarlayarak sahte teyit üretebilir; support'un
  kaynak ve varsayım farkı görünür olmalı.
- **Plugin sürümüne yapısal bağlanma riski.** Sağlayıcının bugünkü
  enum'larını, artefakt hiyerarşisini ve routing dilini domain şemasına
  kopyalarsak "değiştirilebilir sağlayıcı" iddiası kâğıtta kalır.

Eklenti hakkındaki son hüküm: **"bırakmak için de mimarinin temeli yapmak
için de kanıt yok."** 0.1.31 pinlenir, domain çekirdeği eklentiden bağımsız
kurulur, yüksek-yargılı dört-beş skill kullanılır, tearsheet ve dar
preview'in ileride yerel prompt veya deterministik raporla değiştirilmesine
açık kalınır.

## Gözden geçirme — 4. tur: fon çerçevesi (2026-08-16)

Aynı codex oturumunda on tur daha (t33-t42). Kullanıcıdan gelen iki
düzeltmeyle başladı:

1. **Repodaki mevcut koşuların hiçbir önemi yok** -- deneme koşularıdır,
   korunacak değer taşımazlar, kodlar değiştirilebilir. Bu, 3. turdaki
   "platformu şimdi kurma, mevcut hattı yamala" tavsiyesinin bir ayağını
   düşürdü (o tavsiye kısmen "bugünkü sistem gerçek analiz üretiyor"
   öncülüne dayanıyordu).
2. **Esas hedef bir fon yönetme sistemidir** -- sadece araştırma yapıp
   rapor veren, takip ve yorumdan ibaret bir şey değil.

İkincisi tasarımın merkezini değiştirdi. 2. turda "capital policy yok, o
hâlde V1 bir araştırma ve izleme defteridir" diye ürün sınırı ilan
etmiştik; 3. turda `portfolio-risk-management`'ı gereksiz sayıp portföy
defterini plandan geriye atmıştık. Doğrusu şuydu: **capital policy yoksa
tasarlanmalıdır, çünkü sistemin varlık sebebi odur.**

### Ölen kararlar

| Karar | Yerine |
|---|---|
| "V1 araştırma/izleme defteridir, sermaye tahsis sistemi değildir" | Ürün, tek sahibin sermayesini yöneten fon sistemidir; araştırma alt sistemdir |
| "Sistem hedef ağırlık veya rebalans öneremez" | Sistem hedef portföy, sermaye kararı ve işlem önerisi üretebilir; yalnız **emir iletemez** |
| "Portföy sonraki sürümdedir" | Portfolio/account/cash/NAV/risk/proposal/execution ilk omurgadır |
| "Önce araştırma dikey dilimi kanıtlanır" | Önce fonun muhasebe–karar–icra döngüsü kanıtlanır |
| "Mevcut hattı koruyarak yamala" | Koşular değersiz test verisi; greenfield finansal omurga kurulabilir |
| Deneme koşularına özel geçiş planı | Kapsam dışı; yalnız yeni kanıt hattı için test fixture'ı olarak anlamlı |
| 9-12 haftalık araştırma V1'i yol haritasıdır | Artık yalnız araştırma alt sisteminin eski tahmini |

### Tersine dönen veya daralan kararlar

- **Capital policy yokluğu → portföyü kapsam dışı bırakır.** Yeni hüküm:
  ilk çözülmesi gereken ürün boşluğudur.
- **`portfolio-risk-management` gereksiz** → koşullu support; sıra dışı
  sizing, gap veya exposure yorumu için. Hâlâ allocator veya risk engine
  değil.
- **`thesis_opened` yalnız izlenen görüştür** → kısmen geri döndü: artık
  security'yi `underwritten_investable_set`e kabul eden kapıdır. Yine alım
  veya `capital_actionable_now` demek değildir.
- **Pitch/action dili sermaye dışıdır** → daraldı: pitch target weight veya
  işlem üretmez, ama kabul edilmiş tez sermaye değerlendirmesini besler.
  `add/trim/exit` yalnız portfolio proposal katmanında yetkilidir.
- **Tek mantıksal gerçeklik kaynağı** → daraldı: sistem iç kararların
  otoritesidir; broker fills/positions/cash ve piyasa fiyat kaynağı dış
  otoritelerdir. Bir source-of-truth matrisi gerekir.
- **Keşif havuzu = evren − açık tezliler** → dört kümeli akışa ve
  portföy-modlu discovery bütçesine dönüştü.
- **Skill kataloğu 10+1 ürünün ana mimarisidir** → araştırma alt sisteminin
  hedef kataloğudur; fon omurgasını tanımlamaz.

### Ayakta kalan kararlar

Aylık review'ın varsayılan `no_change` olması (histerezisle güçlendi);
research mandate ile capital policy ayrımı; company/security/thesis/capital
action ayrımı; insanın gerçek icranın sahibi olması; analiz/adjudication/
domain commit ayrımı; tek yazarlı idempotent replay edilebilir defter;
git'in kanonik defter olmaması; işlem yokluğundan `flat` türetilememesi ve
`position_unknown`; fill'lerin ayrı kanonik kayıt olması; reconciliation'ın
çok boyutluluğu; nakdin birinci sınıf gerçek olması; "conviction değil
readiness"; kayıp bütçesinin stop olmaması; drawdown'ın otomatik satış
üretmemesi; driver ile korelasyonun farkı; `no_deviation` ≠ sağlıklı;
PIT/provenance zorunluluğu; tez açma yetkisinin yalnız pitch'te olması;
evidence/assessment/adjudication ayrımı; lead'in support'u yürütmemesi;
plugin'in değiştirilebilir sağlayıcı olması; insan yüzeyinin güvenlik
mimarisinin parçası olması; performansın policy'yi otomatik değiştirmemesi.

### Skill envanteri fon çerçevesinde

En önemli düzeltme: **"çekirdek skill" artık "fonun çekirdeği" anlamına
gelemez. Fonun zorunlu çekirdeğinde hiçbir LLM skill'i yoktur.** Önceki altı
skill, hedef *araştırma alt sisteminin* çekirdeğidir.

Yeni dağılım: **6 araştırma çekirdeği, 9 koşullu, 3 escalation, 4 gereksiz,
1 meta.** Değişenler:

| Skill | Eski | Yeni | Gerekçe |
|---|---|---|---|
| `economic-impact-report` | Gereksiz | Koşullu | Artık subject'i var: `risk_driver` / `portfolio_exposure_cluster` |
| `catalyst-calendar` | Gereksiz | Koşullu | Katalizör artık sermaye karar penceresine bağlı; kanonik takvim otoritesi değil |
| `dcf-model-builder`, `three-statement-model-builder` | V1 dışı | Escalation | Comps ve implied-expectations sermaye kararına yetmiyorsa ve bakım sorumluluğu açıkça kabul ediliyorsa |
| `equity-model-update`, `model-audit-tieout` | V1 dışı | Koşullu (model yoluna bağlı) | Workbook sermaye kararına girdi olacaksa audit zorunlu hâle gelir |
| `portfolio-risk-management` | Gereksiz | Koşullu support | Deterministik risk motoru veya allocator değil; danışman |

İki sınır önemli: **`downside_case` çekirdek bir domain artefaktıdır**,
`scenario-sensitivity-generator` yalnız koşullu üreticilerinden biridir. Ve
**`risk_driver_registry` çekirdek domain state'idir**;
`economic-impact-report` ona kanıt önerir, registry'yi değiştiremez.

Workbook kümesi artık "değersiz" değil; ama daha önemli hâle gelmesi onu
rutinleştirmez -- tam tersine, oluşturma/güncelleme/audit zinciri birlikte
üstlenilmelidir. **Yarım workbook yolu kabul edilmemelidir.**

### Fon platformu işleri (C1-C18)

Hiçbir skill'in karşılamadığı, yazılması gereken işler. (Boyut: küçük 2-5
gün, orta 1-2 hafta, büyük 2-4 hafta; paralel çalışılabilir, süreler
doğrudan toplanmaz.)

| Kod | İş | Boyut |
|---|---|---:|
| C1 | Fon, hesap, security, para birimi ve broker kimlikleri | Orta |
| C2 | Kanonik append-only finansal olay defteri, atomik commit, idempotency | Büyük |
| C3 | Sürümlü capital policy, policy assumption ve override yönetişimi | Orta |
| C4 | Açılış portföyü onboarding'i ve broker snapshot aktarımı | Orta |
| C5 | Broker CSV/OFX/manual activity importer ve provenance | Büyük |
| C6 | Fill, dış nakit akışı, temettü, vergi, ücret, faiz, corporate-action olay modeli | Büyük |
| C7 | Pozisyon, lot, maliyet tabanı ve nakit projection'ları | Büyük |
| C8 | Fiyat/FX/as-of valuation katmanı | Orta |
| C9 | Çok eksenli reconciliation motoru | Büyük |
| C10 | NAV, dış akış ayrımı, TWR, MWR/XIRR, drawdown omurgası | Büyük |
| C11 | Deterministik risk motoru | Büyük |
| C12 | Causal-driver registry ve exposure eşlemesi | Orta |
| C13 | `policy_eligible` / `underwritten_investable` / `capital_actionable_now` materializer'ları | Orta |
| C14 | Ağırlık bandı, binding constraint, no-trade band, replacement-hurdle hesaplayıcısı | Büyük |
| C15 | `portfolio_proposal` sürümleme, geçerlilik, alternatif, onay, override lifecycle'ı | Orta |
| C16 | Trade intent, insan icrası, fill/deviation/expiry köprüsü | Büyük |
| C17 | Attribution ve dondurulmuş counterfactual değerlendirme | Büyük |
| C18 | Operatör yüzeyi, kuyruklar, recovery, replay, backup, audit, regresyon | Büyük |

Araştırma tarafındaki F1-F18 ile bu liste toplanıp "36 modül" sayılmaz;
kimlik, olay defteri, artefakt, doğrulama, operatör yüzeyi, recovery ve test
altyapısı ortaktır. Birleşik sistem yaklaşık **25-30 platform yeteneğine**
dönüşür. Skill çağırma mekanizması yazılımın muhtemelen **%10-15**'idir;
geri kalanı para, state, yetki, güvenilirlik ve denetim altyapısıdır.

### Fon tarafında LLM'in yeri

Minimum çalışan fon döngüsünde **LLM zorunlu değildir**. Muhasebe, NAV,
risk, limit, proposal envelope, onay, icra, fill ve reconciliation tamamen
deterministik motorlar + insan yetkisiyle çalışabilir.

LLM'in meşru rolleri yalnız danışmanlık ve açıklamadır: deterministik
proposal'ı insan dilinde özetlemek (yeni sayı veya kural icat etmeden), iki
alternatifin nitel farkını karşılaştırmak, `risk_driver` etiketi önermek,
reconciliation uyuşmazlığının olası nedenlerini sıralamak, downside/gap
senaryosu önermek, dönem sonu bulgularını sentezlemek.

Kesinlikle verilmeyecekler: fill/nakit/lot/maliyet/corporate-action kaydı;
NAV, TWR, MWR, ağırlık, P&L hesabı; kimlik eşlemesinin sessiz kabulü;
limit/loss-budget/likidite/gap/drawdown hesapları; policy uyumluluğu ve
binding constraint tespiti; proposal geçerliliği; nihai hedef ağırlık,
işlem onayı veya emir iletimi; reconciliation farkının otomatik
düzeltilmesi; capital policy değişikliği veya override.

### Kalan uyarı

> En büyük tehlike LLM halüsinasyonu değil, **deterministik görünen
> kuralların sahte kesinlik üretmesidir.** Capital Policy v0 kanıtlanmış bir
> yatırım sistemi değil, açık varsayımlardan oluşan ilk anayasadır;
> matematik onu tutarlı yapar, doğru yapmaz.

## Gözden geçirme — 5. tur: sınama ve şema (2026-08-16)

Aynı oturumda on tur daha (t43-t52). İki konu: capital policy'nin gerçek
para riske edilmeden sınanması, ve tasarımın somut şemaya dönüştürülmesi.

### Policy nasıl sınanır

**Klasik backtest geçersizdir.** Girdilerin çoğu tarihsel olarak var olmayan
yargılardır: geçmiş bir tarih için tez, readiness ve downside üretmek
hindsight bulaştırır; bugünkü evren dosyası survivorship taşır. Yerine dört
bağımsız kanıt katmanı:

| Katman | Neyi sınar | Zorunlu mu |
|---|---|---|
| **Property testleri** | Motorun kurallara sadakati; rastgele üretilmiş binlerce girdide invariant | Evet |
| **Golden fixture'lar** | Kuralların anlamı; 6-8 okunabilir kanonik kitap | Evet |
| **Mekanik tarihsel replay** | Gerçekçi davranış; alfa iddiası yok, nakit/turnover/band/limit davranışı | Evet |
| **Gölge koşu** | İşletilebilirlik | Evet |

Dördü birbirinin yerine geçmez. Replay sonuçları provisional sayıları
**optimize etmek için kullanılamaz** -- o an kapı bir overfitting makinesine
dönüşür.

**Davranışsal başarısızlıkların çoğu monotonluk özelliğidir** ve otomatik
sınanabilir: downside kötüleşirse ilgili pozisyonun tavanı artamaz; loss
budget daralırsa tavan artamaz; readiness düşerse band genişleyemez; policy
sıkılaşırsa uygun portföy kümesi genişleyemez (`F(P_sıkı,S) ⊆
F(P_gevşek,S)`). Sınır önemli: monoton olan **kötüleşen ismin kendi
tavanı** ve toplam uygun küme; diğer isimlerin ağırlıkları artabilir, çünkü
boşalan kapasite başka yere veya nakde gider.

Property'ye indirgenemeyenler örnek senaryo ister: bir eşiğin ekonomik
olarak doğru olup olmadığı, challenger'ın gerçekten daha iyi olup olmadığı,
driver taksonomisinin dünyayı temsil edip etmediği, operatörün adjudication'ı
zaman bütçesinde yapabilmesi.

**Determinizm LLM'den önce değil, adjudication'dan sonra başlar.** Doğru
soru "aynı hafta iki kez çalıştırsam aynı sonuç gelir mi" değil, **"iki
koşunun kanonik girdi manifestleri aynı mı"**dır. Aynıysa sonuç aynı
olmalıdır; değilse sistem sessiz farklılık değil input diff göstermelidir.

**Gölge koşu iki aşamalıdır:** önce *kör paralel* (sistem önerisini
mühürler, kullanıcı kendi kararını kaydetmeden görmez -- karar farkını
ölçer), sonra *kâğıt icra* (öneri görülür, simülasyonda onaylanır, fiyat
geçersizleşmesi/kısmi fill/expiry/reconciliation çalışır, broker emri yok --
uygulanabilirliği ölçer). Küçük tutarlı gerçek işlem bunun devamı değil,
zaten sınırlı canlı pilottur.

İnsanla sistemin farklı karar vermesi tek başına başarısızlık değildir; fark
önce sınıflandırılır (input farkı / policy boşluğu / motor kusuru / insan
policy sapması / yargı farkı / operasyon farkı / kayıt yetersizliği).
**Agreement rate başarı metriği değildir** -- insan ve sistem aynı anda aynı
yanlışı da yapabilir. İnsan sürekli policy dışı davranıyorsa "motor
başarısız" denmez; ya kullanıcı yazılı policy'ye inanmıyordur ya policy
gerçek tercihleri temsil etmiyordur -- her iki hâlde de canlı yetkiye
geçilmez.

**Yetki merdiveni (A0-A4)** ayrı bir `operating_authority` nesnesidir,
capital policy alanı değil -- aynı policy hem gölgede hem canlıda
kullanılabilir, ve operasyonel arıza yetkiyi düşürürken ekonomik policy
değişmeyebilir.

| Seviye | Sistem ne yapabilir | İlerleme kapısı |
|---|---|---|
| A0 Kayıt | Gerçeği, NAV'ı ve riski gösterir; sermaye önermez | Açılış kitabı ve bir statement dönemi uzlaştırılmış |
| A1 Kör gölge | Mühürlü proposal üretir, karar öncesi göstermez | İki aylık döngü + bir olay vakası; hard failure yok |
| A2 Kâğıt icra | Proposal'ı gösterir; order/fill/expiry/reconciliation'ı simüle eder | Fiyat geçersizleşmesi, kısmi fill, iptal, uzlaştırma uçtan uca çalışmış |
| A3 Sınırlı canlı | Pilot tavanıyla sınırlı proposal'lar insan onayına açılır | Bir tam statement kapanışı + iki uzlaştırılmış canlı döngü |
| A4 Normal canlı | Policy kapsamındaki tam proposal seti | Sürekli işletim; otomatik emir yetkisi hiçbir zaman doğmaz |

`authority_grant` immutable'dır; revocation ayrı olaydır. Revocation
tetikleyicileri kapalı sözlük (policy superseded, validation regression,
çözülmemiş hard breach, disputed reconciliation, stale NAV, input integrity
failure, manuel).

**Kabul kapısı** dört iddiayı destekler, kârlılığı değil: uygulanabilir /
güvenli / kararlı / işletilebilir. Beklenen sonuçlar test koşulmadan önce
yazılır; sonuç görüldükten sonra kriter değiştirilmez. Parametre duyarlılığı
en iyi değeri seçmek için değil **kırılganlığı görmek** için ölçülür --
komşu değerler bambaşka portföyler üretiyorsa merkez değer "makul"
sayılamaz.

### Şema kararları

Dört temsil, farklı sorumluluklar: kanonik olaylar + hash'li artefaktlar
(otorite), SQLite (atomiklik ve saklama), kalıcı projection'lar (karar
arayüzü, şemalı), geçici kod nesneleri (şemasız). Önemli düzeltme: **olay
şeması otorite değildir**; kabul edilmiş olay örnekleri ve referans
verdikleri değişmez artefaktlar otoritedir. Şema yalnız deftere neyin kabul
edilebileceğini belirler.

| Karar | Hüküm |
|---|---|
| **Para** | `{amount: decimalString, currency: ISO-4217}`. Float yasak. Minor-unit integer de reddedildi (FX, kesirli hisse, bölünme oranı, kesirli kuruş için yetersiz). SQLite'ta `TEXT` -- `NUMERIC` affinity metni REAL'a çevirip hassasiyet kaybettirir. |
| **Adet** | `decimalString`; kesirli hisse baştan desteklenir, izin verilen adım broker yeteneğinden gelir. Global "en fazla dört ondalık" kuralı konmaz. |
| **Eşikler** | Policy'nin yazdığı oranlar bp integer (`100 = %1`); hesaplanmış ağırlıklar bp'ye yuvarlanmaz. |
| **Zaman** | Üç tip: `UtcInstant` (gerçek an), `LocalDate` (ekonomik takvim günü -- gece yarısı timestamp'ine çevirmek yasak), `MarketSessionDate` (borsa takvimi). **"Bugün" kanonik veri alanı değildir**: scheduler bir `evaluation_instant` alır, operatör tarihi ve borsa seansı ondan ayrı türetilir. |
| **Kimlik** | UUIDv7 (sıralanabilir). Okunabilir `PROP-2026-0042` yalnız `display_ref`; foreign key veya idempotency anahtarı olamaz. |
| **Menkul kıymet** | Üç seviye: `issuer_id` / `security_id` / `listing_id`. GOOG-GOOGL aynı issuer farklı security; ticker değişimi hiçbirini değiştirmez; delisting listing'i kapatır, security'yi değil. CIK issuer'a bağlı haricî kimliklerden biridir, `issuer_id`'nin yerine geçmez. |
| **Sürümleme** | Dosya adı + `$id` + veri örneği birlikte sürüm taşır. Yayınlanmış şema değiştirilmez; eski olaylar yeniden yazılmaz, projector upcaster ile çevirir. `schema_version` / `policy_version` / `engine_version` ayrı anlamlardır, tek alana sıkıştırılamaz. |
| **Yerleşim** | Yeni fon şemaları `schemas/fund/` altında; mevcut düz dosyalar taşınmaz. |

**Açılış kitabı özel bir problemdir.** Sentetik "opening fill" **yasak** --
olmamış bir işlem uydurmak sahte işlem tarihi, nakit çıkışı, elde tutma
süresi ve karar attribution'ı üretir. Ayrı bir `opening_account_state_
asserted` olayı kullanılır ve `cost_basis_status` taşır
(`lot_level_known` / `aggregate_only` / `partial` / `unknown`). **Maliyet
bilinmiyorsa sıfır yazılmaz**: adet ve piyasa değeri bilinir, açılıştan
sonraki TWR hesaplanır, ama unrealized P&L `unknown` kalır. Maliyet sonradan
bulunursa geçmiş olay değiştirilmez; `opening_cost_basis_supplied` referans
verir.

Diğer muhasebe kararları: **temettü iki olaydır** (ex-date'te alacak,
ödeme tarihinde nakit -- tek olay kullanılırsa aradaki dönemde NAV sahte
düşüş gösterir); `net = gross - withholding - fees` eşitliği validator
tarafından doğrulanır; uzlaştırma ekonomik olay değildir, ayrı ailedir;
**lot bir projection ama lot SEÇİMİ bir olaydır** (satışta hangi lotun
kapandığı karardır, projection'a gömülemez -- sistem sessizce FIFO
varsaymamalıdır); `projected_flat` (fill'lerden sıfır türedi) ile
`confirmed_flat` (broker snapshot'ıyla uzlaştırıldı) ayrıdır.

**Olay zarfı:** tek primary `subject` + çoğul `related_refs` (çoklu primary
subject stream sıralamasını belirsizleştirir); `correlation_id` ve
`causation` ayrı işler yapar, ikisi de gerekli; `actor` zorunlu
(human/system/external_source); yetki her olayda değil ayrık
`authority_basis` ile (`not_required` / `explicit_user_action` /
`operating_authority` / `external_observation`); idempotency payload'da
değil zarfta (commit kapısı payload'ı açmadan duplicate yakalayabilmeli);
`occurred_at` her zaman bilinemeyeceği için `occurrence` ayrık tiptir
(instant veya date); **genel `approval` alanı kaldırıldı** -- onay ayrı bir
domain olayıdır; **`sequence` zarfta değil storage metadata'sındadır.**

**SQLite:** `BEGIN IMMEDIATE` + unique constraint'ler, dosya kilidinden hem
basit hem doğrudur. Batch'te `pending/committed` durumu tutulmaz --
transaction başarılıysa batch vardır, başarısızsa hiç yoktur; okuyucu yarım
batch göremez, `committed` filtresi gereksizdir. `global_position` ve
`stream_position` **boşluksuz olmak zorunda değildir**; güvence benzersiz ve
monoton sıralamadır. `events` ve `event_batches` üzerinde UPDATE/DELETE
reddeden trigger bulunur. WAL correctness sağlamaz -- onu transaction ve
constraint'ler sağlar.

Tek operatöre rağmen eşzamanlılık gerçektir (iki terminal, dashboard + CLI,
import retry, aynı düğmeye iki kez basma, crash sonrası yeniden çalıştırma).
"Disiplinle çözülür" burada da yeterli değildir; ama çözüm dosya kilidi
değil, **tek `commit_batch()` kod yolu**dur.

### V0 kesimi

Beş turda ~30 şemalık yüzey tanımlandıktan sonra kesim yapıldı. İlke:
**genelliği kes, doğruluğu kesme.** Ve: *"kullanılmayan enum değeri geleceğe
hazırlık değil, test edilmemiş davranıştır"* -- yeni değer, gerçekten
üretileceği turda eklenir.

**İlk çalışan dilim: 7 tam şema + 3 stub + 1 DDL.**

| Şimdi tam yazılacak | Stub (dar, kapalı, sürümlü) | Bu dilimde hiç yazılmayacak |
|---|---|---|
| `common` (primitive'ler) | `instrument-master` | Fill/temettü/ücret/vergi/corporate-action şemaları |
| `fund-definition` | `artifact-manifest` | Lot projection ve lot disposition |
| `event-envelope` | `input-manifest` | Reconciliation motoru |
| `opening-accounting-event` | | `policy_validation_spec`, `operating_authority` |
| `valuation-observation-bundle` | | `portfolio_risk_snapshot`, `portfolio_proposal` |
| `fund-state-projections` | | Execution plan/ticket/broker order |
| `nav-snapshot` | | TWR/MWR, attribution, driver registry |
| `fund-ledger.sql` (DDL) | | Araştırma/tez entegrasyonu |

Stub, `additionalProperties: true` demek değildir -- dar ve kapalı olur,
sonra yeni opsiyonel alanlarla veya yeni şema sürümüyle genişler.

**V0'ın tek sorusu:** *Broker kaynaklı bir açılış kitabını exact
para/adetlerle bir kez kaydedip, tekrar çalıştırmada çoğaltmadan,
fiyatlandırıp aynı pozisyon/nakit/NAV state'ini replay edebiliyor muyum?*
Bu soru geçmeden risk snapshot, proposal, authority veya validation spec
yazmak yeniden erken kurumsallaşmadır.

**Şimdi doğru konması gerekenler** (sonradan değiştirmek pahalı): UUID
kimliklerinin anlamı, decimal/money/currency temsili, zaman alanlarının
anlamı, artifact/event/projection ayrımı, exact policy/input/engine
referansları, proposal'ın immutable olması, insan kararının ayrı olay
olması, option'ın tüm portföyü temsil etmesi, target'ın band olabilmesi,
primary subject ve stream kimliği, sürümleme, position state'lerinin
anlamı, maliyet bilinmiyorsa sıfır yazılmaması.

**Sonradan ucuz eklenebilecekler:** yeni constraint türleri, yeni binding
açıklamaları, yeni exposure breakdown'ları, alternatif option'lar, yeni
scenario sonuçları, daha zengin reason code'lar.

Süre: ilk dilimin şemaları **5-8 iş günü**; tanımlanan tüm hedef set 15-25
odaklı iş günü (~4-6 takvim haftası kısmi zamanla). Ayrım önemli: *şemayı
yazmak hızlıdır, doğru şemaya karar vermek değildir* -- Claude/codex
boilerplate, `oneOf`/`$defs`, fixture üretimi ve tutarlılık kontrolünü
hızlandırır; alanın gerçekten gerekli olup olmadığına, iki alanın aynı
gerçeği taşıyıp taşımadığına, muhasebe semantiğine ve geriye uyumluluğa
karar vermeyi hızlandırmaz.

### 5. turun getirdiği daraltmalar

- **Capital policy bütün altyapıyı bloklamaz** (yukarıda İnşa sırasına
  işlendi).
- **`config/` yalnız düzenlenebilir taslaktır**; runtime otoritesi mühürlü
  artefakt + `capital_policy_activated` olayıdır. Etkinleştirmeden sonra
  config dosyası ikinci gerçeklik kaynağı sayılamaz.
- **Zarftan `approval` kaldırıldı** -- bu, 1. turdaki onay ayrımıyla tam
  uyumludur; `authority_basis` genel bir onay alanının yerine geçmez.

### Kalan uyarı

> En kolay yanlış anlama, replay edilebilir ve deterministik bir sistemin
> otomatik olarak doğru olduğuna inanmaktır. Sistem aynı yanlış fiyatı,
> yanlış FX'i veya kötü seçilmiş policy sayısını kusursuz biçimde tekrar
> üretebilir. İlk başarı ölçütü "iyi proposal verdi" değil; broker gerçeğini
> kayıpsız aldı, bilinmeyeni sıfıra çevirmedi, aynı girdiyi çoğaltmadı ve
> aynı manifestten aynı state'i üretti olmalıdır.

## Gözden geçirme — 6. tur: fon ↔ skill entegrasyonu (2026-08-16)

Aynı oturumda yedi tur (t53-t59). Konu: 4. turda "araştırma alt sistemdir"
denmişti ama sınırın nerede olduğu hiç somutlaştırılmamıştı.

Sınırın kendisi "Geçerli tasarım → Araştırma ↔ fon sınırı"na işlendi. Bu
bölüm turun geri kalanını taşır.

### Beş temas değil tek sınır

Fonun skill'e dokunduğu iş noktaları beştir (investable sete kabul, tez
izleme, downside/valuation güncellemesi, discovery, driver yorumu -- artı
altıncısı: performans geri beslemesinden doğan re-underwrite). Ama bunlar
**beş ayrı teknik entegrasyon olmamalıdır.** Hepsi aynı sınırdan geçer.

Yön farkı semantiktir, altyapı ortaktır: fon → araştırma yönü
`research_work_requested` (asenkron görev; risk motoru LLM çağrısını
beklemez, aynı transaction içinde skill çalıştırmaz), araştırma → fon yönü
`capital_input_adjudicated` (skill completion değil, kabul edilmiş sürümlü
domain artefaktı).

**Muhasebe/NAV V0'ında sıfır skill; ilk risk/proposal sürümünde de teknik
olarak sıfır skill gerekir.** İnsan gerekli capital input'ları typed biçimde
elle girebilir. Skill entegrasyonu bu girdilerin *üretimini* iyileştirir,
fonun *doğruluğunu* kurmaz.

### `research_work_request`

Kalıcı bir **karar ihtiyacıdır**, kuyruk öğesi değil; kuyruk açık taleplerin
güncel fon durumu, deadline ve kapasiteyle yeniden sıralanmış
projection'ıdır. Taşıdıkları: `requested_capability` (domain çıktısı, skill
adı değil), `required_output_contract`, origin refs, decision context
(karar tipi, bloklanan aksiyonlar, deadline, `capital_at_risk`), araştırma
sorusu (birincil soru, mevcut belirsizlik, olası sermaye etkileri, gerekli
kanıt, durma koşulları), VOI (`admission_basis`, ordinal impact /
changeability / effort), ve `work_equivalence_key`.

Request'i deterministik bir planlayıcı veya insan üretir; **skill üst düzey
fon araştırma ihtiyacı yaratamaz** (yalnız kendi episode'u içinde
`support_request_proposed` önerebilir).

Dedup iki seviyelidir: idempotency (aynı origin + capability + decision ref)
ve semantik gruplama (farklı geçerli request'ler tek episode tarafından
karşılanabilir). Öncelik leksikografiktir: R sınıfı → deadline → risk
altındaki sermaye → changeability/effort. Yani `R2 + 82bp` bir iş, diğer R2
işleri arasında öne çıkar ama **R1'i geçmez.**

Bir düzeltme: **R0 çoğunlukla araştırma işi değildir.** Sermaye gerçeği
bilinmiyorsa çözüm skill değil reconciliation/importer'dır; R0 birleşik
operatör kuyruğunda kalır, araştırma kuyruğu normalde R1-R5'tir.

İptal, "skill'i" değil **karar ihtiyacını** iptal eder; request silinmez,
`research_work_cancelled`/`superseded` eklenir. Çalışan iş durdurulamıyorsa
sonuç `quarantined_late_result` sayılır ve yeni request + adjudication
olmadan capital input olamaz. Request, attempt başlamadan **ve** provisional
sonuç adjudication'a sunulmadan önce güncel fon state'ine karşı yeniden
doğrulanır -- araştırma bir hafta sürerken sermaye sorusu ortadan kalkmışsa
eski cevap yeni kararın içine sızamaz.

### Adjudication pratiği

Aşama A'da kullanıcı şunları görür: senaryonun causal zinciri, varsayımlar
ve birimler, her önemli sayı için kaynak, mevcut kabul edilmiş case ile alan
bazında fark, yeni/çelişkili/eksik kanıtlar, falsifier bağlantısı, validator
sonuçları. Cevapladığı sorulardan biri kritiktir: **"Bu pozisyona sahip
olmasaydım aynı senaryoyu kabul eder miydim?"**

Süreler: dar güncelleme 5-10 dk, yeni downside case 20-30 dk, maddi varsayım
değişikliği 15-30 dk. **30 dakikayı geçiyorsa defer veya reject.** Haftada
onlarca adjudication kabul edilebilir değildir; sistem normal haftada birkaç
maddi hüküm üretecek kadar dar tutulmalıdır.

**İnsan sayıyı değiştirirse** mevcut önerinin üzerine yazılmaz: olgusal hata
varsa öneri *reject* edilir ve doğru kaynakla yeni case üretilir; bilinçli
daha muhafazakâr yargı ise `human_authored_downside_case` olur, model
artefaktına `derived_from` ile bağlanır ve aynı validator'dan geçer. Bu bir
policy override değildir -- override, geçerli bir girdiye rağmen policy
sınırını aşmaktır.

**Kalite üç katmanda ayrılır:** şema (JSON Schema), kaynak varlığı/dönem/
birim/tie-out/citation lineage (deterministik validator), peer setinin
anlamlılığı ve senaryonun makullüğü (insan). Kalite skill adına göre değil
`plugin_version + skill_digest + model + execution_role +
requested_capability` route'una göre ölçülür; uydurulmuş kaynak veya yasak
sermaye hükmü route'u tek seferde quarantine edebilir.

**Araştırma ile fiyat çelişirse** sistem gösterir ama fiyatı tez hakemi
yapmaz. İki sinyal: `thesis_deteriorating_market_favorable` ve
`thesis_intact_market_adverse`. Tracker'ın ilk analitik geçişi fiyat/P&L
görmeden yapılır; market overlay ayrı gelir. Tez broken + fiyat yükseliyor →
broken hükmü değişmez. Tez intact + fiyat %40 düşmüş → tez otomatik
bozulmaz, ama drawdown policy'si zorunlu re-underwrite ve ekleme dondurması
üretir.

**Bayat adjudication kilitlenme değil, doğru güvenlik davranışıdır** --
muhasebe, NAV, hard-limit trim ve exit çalışmaya devam eder. "Olduğu gibi
uzat" yalnız kısa-form inceleme ile mümkündür (incelenen kanıt penceresi,
kontrol edilen maddi olaylar, sonuç, sonraki vade); hiç kanıt bakmadan
`administrative_extension` karar-kritik girdilerde **yasaktır**. Bütün kitap
stale oluyorsa doğru çözüm süreleri sahte uzatmak değil, pozisyon sayısını
veya kadansı kapasiteye uydurmaktır.

**Törensel onay** kesin ispatlanamaz ama sinyalleri vardır (olağandışı kısa
süreler, %100 kabul oranı, hiç reject/defer olmaması, kaynak panelinin hiç
açılmaması, toplu onaylar, sonradan sık düzeltme). Yüzeyde korumalar: "hepsini
onayla" yok, accept varsayılan seçenek değil, yüksek-reliance case'lerde bir
cümlelik gerekçe zorunlu. Kullanıcı yine de incelemeden geçmek isterse kayıt
`acknowledged_without_full_adjudication` olur -- `human_adjudicated`
sayılmaz, readiness yükseltmez.

> Kullanıcı kendi parasında istediğini yapabilir; sistem bunu "disiplinli
> adjudication yapıldı" diye yalanlayamaz.

### Uygulama sırası ve ilk adapter

İnşa sırası revize edildi (yukarıda İnşa sırası bölümüne işlendi).

**En küçük entegrasyon dilimi iki aşamalıdır.** Önce *skill'siz sınır
testi*: insan-authored bir `proposed_downside_case` → validator → Aşama A
adjudication → `capital_input_manifest` → risk motoru → ağırlık tavanı. Bu
test **plugin olmadan geçmelidir**; böylece adapter bozulduğunda domain
sınırının çalıştığı bilinir. Sonra *ilk gerçek sağlayıcı testi* -- ama tek
downside case tek başına nihai tavanı üretemez; fixture'da tez ve readiness
önceden kabul edilmiş olmalı, yalnız downside eksik bırakılmalı ve downside
kısıtı gerçekten binding olacak şekilde kurulmalıdır.

**İlk adapter `comps-valuation`**: dar capability (`valuation_anchor`), tez
gerektirmez (legacy pozisyonda çalışır), kaynak/peer/dönem/tie-out
deterministik doğrulanabilir, lifecycle açmaz veya kapatmaz. Sıra: comps →
pitch (onboarding underwrite) → tracker → deep-dive → tearsheet →
idea-generation. Tracker veya deep-dive'ı ilk yapmak tavuk-yumurta üretir
(tracker'ın tezi, deep-dive'ın beklenti bağlamı yoktur); pitch'i ilk yapmak
entegrasyon tesisatıyla analitik kaliteyi aynı anda debug ettirir.

Süre: entegrasyon katmanı (skill'ler hariç) **4-7 hafta**; `comps-valuation`
adapter'ı 4-7 iş günü; pitch/onboarding adapter'ı ayrıca 1,5-2,5 hafta;
tracker veya deep-dive ortak altyapıdan sonra 1-2 hafta/adet.

> Önce manuel producer ile sınırı kanıtla, sonra aynı output contract'a
> plugin'i tak. Plugin'i ilk producer yaparsan, hata çıktığında bunun domain
> sözleşmesinden mi, orkestrasyondan mı, prompttan mı yoksa skill'den mi
> geldiğini ayıramazsın.

### Önceki turlarla tutarlılık

Lead+support modeli ve katalog v2 geçerliliğini korur; fonun request
üretmesi yalnız yeni bir talep kaynağıdır, lead seçimi ve episode yapısı
araştırma orkestratöründe kalır. Kataloğa capability/output contract,
görünürlük profili, assessment mode ve assurance politikası eklenir;
`allowed_next` geri gelmez. `capital_input_manifest` 4. turdaki "adjudicated
capital input" kavramının somut paketidir -- yeni bir otorite veya ikinci
defter değildir; bileşenler ve adjudication olayları otoritatiftir, manifest
karar anında onlardan türetilip mühürlenir.

### Kalan uyarı

> En kolay ve en tehlikeli yanlış anlama, "skill çıktısı fona girdi olur"
> cümlesidir. Olmaz: yalnız doğrulanmış ve insan tarafından bağımsız biçimde
> adjudicate edilmiş domain nesneleri fona girdi olabilir. Biri
> `skill result → risk engine` kestirmesi yaparsa bütün güvenlik mimarisi
> çöker. Entegrasyonun başarı ölçütü plugin'i çağırabilmek değil, **plugin'i
> söktüğünde fonun doğru kalması ve aynı sözleşmeye başka bir producer
> takılabilmesidir.**

## Kullanıcı kararı bekleyen sorular

Bunlar teknik değil tercih soruları -- doğru cevabı tasarımdan
türetilemez, kullanıcının kapasitesine ve risk iştahına bağlı. Her birinin
altında neden bir soru olduğu yazılı.

### Bunlar olmadan başlanamaz (4. tur)

Bir insanın oturup bir saatte cevaplayabileceği kadar kısa tutuldu.

1. **Fon perimetresi:** hangi broker hesapları ve nakit bakiyeleri bu
   havuza dahil, açılış tarihi ne?
   *Cevapsızsa açılış portföyü ve NAV kurulamaz.*
2. **Raporlama para birimi:** kanonik NAV USD mi TL mi; diğeri yalnız
   bağlam serisi mi?
   *Cevapsızsa performans ve risk tek ölçüm tabanında hesaplanamaz.*
3. **Sermaye amacı ve kullanım ihtiyacı:** hangi ufukta yönetilecek,
   öngörülebilir çekim/rezerv ihtiyacı var mı?
   *Cevapsızsa deployable capital ve asgari nakit belirlenemez.*
4. **Risk zarfı:** kabul edilebilir portföy drawdown'ı, pozisyon başına
   kayıp bütçesi ve mutlak tek-isim tavanı ne?
   *Cevapsızsa güvenli pozisyon büyüklüğü veya proposal üretilemez.*

**Kayıp bütçesi için çıpa** (piyasa standardı değil, tasarım çıpası):
starter 50-75 bp NAV, core 75-125 bp, merkez 100 bp, insan onaylı hard
tavan 150 bp. %25 downside varsayımında 100 bp → %4 ağırlık. On pozisyonun
hepsi aynı anda downside'a ulaşırsa 100 bp merkez ~%10 NAV kaybı üretir;
korelasyon ve gap için ayrıca daha ağır portföy stresi gerekir.

### Varsayılan çıpayla başlanabilecekler

Azami aktif pozisyon **10** · readiness `starter 0.5× / core 1.0× /
exceptional kapalı` · operasyonel nakit tabanı **%2** · no-trade bandı
**max(1 puan, hedefin %20'si)** · proposal fiyat toleransı **%2-3** ·
drawdown eşikleri **−%10 uyarı / −%15 ekleme dondurma / −%20 tam yeniden
inceleme** · driver yoğunluğu **soft review** · policy gevşetme bekleme
**30 gün veya sonraki üç aylık inceleme** · aylık portföy incelemesi
varsayılan **`no_change`**.

Bunlar optimal oldukları için değil, ilk gerçek verilerle kalibre
edilebilir başlangıç çıpaları oldukları için kullanılabilir.

### İlk hafta

Önceliği kod değil, policy ve broker gerçeğidir -- bilinmeyen veri üzerinde
yazılan muhasebe modeli yeniden yazılır. Ama **dört soruyu beklerken boş
oturmak gerekmiyor** (5. tur daraltması): aşağıdaki 2-4. maddeler cevaptan
bağımsızdır.

1. Fon perimetresini, raporlama para birimini, sermaye amacını ve risk
   zarfını karara bağla. *(Bu, 1. ve 5. maddeleri açar.)*
2. Broker hesaplarını, açılış tarihini ve kaynak ekstre/export dosyalarını
   envanterle -- **henüz import yapma**, yalnız neyin elde olduğunu gör.
3. `core-types`, `event-envelope` ve SQLite DDL sözleşmelerini
   kesinleştir; atomiklik, idempotency ve replay kabul fixture'larını yaz.
4. 7 tam şema + 3 stub sınırını dondur; bu listenin dışına çıkma.
5. Dört cevap geldikten sonra `fund_definition`, `capital_policy` ve
   `policy_validation_spec`'i tamamla. Policy aktivasyonu, risk motoru ve
   proposal çalışması o ana kadar bekler.

Kodlamaya başlamadan önce mevcut portföy üzerinde manuel bir prova da
yararlıdır: NAV, ağırlıklar, kayıp bütçesi, hard limitler ve varsayılan
`no_change` proposal'ı elle hesaplanabiliyor mu?

### Önceki turlardan devam edenler

### Öncelikli (2. turdan)

1. **V1'in resmî sınırı ne: yalnız araştırma/izleme sistemi mi, yoksa
   sermaye tahsis desteği de verecek mi?**
   Capital policy olmadan güvenle inşa edilebilen ürün araştırma
   defteridir; allocator isteniyorsa önce yeni bir karar katmanı gerekir.
   Diğer dört sorunun cevabı buna bağlı.

2. **Capital policy'nin asgari çıpaları ne olacak: kullanılabilir sermaye,
   nakit yaklaşımı, tek isimde azami sermaye/kayıp, ağırlıklandırma
   ilkesi?**
   En az biri olmadan pozisyon büyüklüğü matematiksel olarak eksik
   tanımlıdır -- aynı tez kümesi için sonsuz sayıda "uygun" portföy üretilir.

3. **Aylık gözden geçirmede hangi gerekçeler işlem yapmaya izin verecek?**
   Yeni filing/tez değişimi, değerleme değişimi, nakit ihtiyacı veya açık
   risk kısıtı dışında serbest bırakılırsa aylık ritim, 46 günlük veriyle
   gereksiz rotasyon üretir.

4. **Portföy muhasebesinde hedef doğruluk: broker average cost + teze bağlı
   nakit akışları yeterli mi, yoksa vergi lotu düzeyinde attribution
   gerçekten gerekli mi?**
   Cevap, V1'in basit bir uzlaştırma katmanı mı yoksa ikinci bir broker
   muhasebesi mi kuracağını belirler.

5. **`thesis_opened` ileride ayrıca bir `capital_eligible` hükmü mü
   isteyecek, yoksa araştırma kalitesi ile sermaye uygunluğu hep aynı
   olayda mı kalsın?**
   İkisini aynı olayda birleştirmek, 1. turda çözdüğümüz karışıklığı geri
   getirir.

### 3. turdan (skill envanteri)

6. **Gölge vaka kapısının geçme eşiği nedir?**
   Kabul edilebilir insan düzeltme süresi, kontrat eksikliği ve hüküm
   tutarsızlığı sınırı önceden yazılmazsa "başarılı pilot" sonradan keyfî
   yorumlanır -- ve pitch'in çekirdek olup olmadığı kararı o yoruma kalır.

7. **Ölçüm dönemi ne zaman biter: sabit tarih mi, iki gerçek kazanç
   döngüsü mü?**
   Bu, platform yatırımının ne kadar kanıta dayanacağını belirliyor; erken
   bitirmek kanıtsız inşa, geç bitirmek atıl bekleme demek.

8. **Ölçüm sırasında yeni aday alımı dursun mu?**
   Tam duruş işletim yükünü temiz ölçer; küçük manuel giriş ise sistemi
   gerçek kullanım baskısı altında sınar. İkisi farklı şeyleri öğretir.

### 1. turdan kalanların durumu

- **Ölçek/kadans:** geçerli, ama yeniden çerçevelenmeli -- "aylık rebalans
  sıklığı" yerine coverage cycle süresi, haftalık insan bütçesi ve tez
  başına azami sessizlik süresi olarak sorulmalı.
- **Adjudication granülerliği:** büyük ölçüde karara bağlandı (ara adımlar
  provisional; insan kapısı dört yerde). Soru olmaktan çıktı.
- **Partial tur kapanışı:** V1'de tam tur state machine'i yapılmayacağı
  için ertelendi.
- **Eşzamanlı zincir sayısı:** mimari sorudan operasyonel WIP limitine
  dönüştü; ilk gerçek koşulardan sonra ölçülerek belirlenir.
- **Uzlaştırma sıklığı:** geçerli; 4. sorunun altında "işlem sonrası +
  periyodik broker uzlaştırması" tercihi olarak cevaplanmalı.

1. **Gerçek hedef ölçek ve kadans nedir: 87 mi, 500 mü? Bir tur en fazla
   kaç gün sürebilir?**
   Domain tasarımı 500'de ayakta kalıyor ama yürütme tasarımı kalmıyor;
   yani 87 ile 500 aslında iki farklı sistem ve hangisine yazacağımız baştan
   belli olmalı. Tur süresi de doğrudan bir bedel: Tur 2 tur bitmeden
   çalışmadığı için ilk dilimin finalisti bu sürenin tamamını bekliyor.

2. **Hangi analitik çıktıları tek tek kabul edeceksin: her workflow mu,
   yalnız karar taşıyanlar mı, yoksa dilim/zincir bazlı toplu onay mı?**
   `accepted_for_use` kapısının nereye konduğu doğrudan haftalık el emeğini
   belirliyor; her workflow'u tek tek onaylamak en güvenlisi ama 10 aday ×
   5 adım haftada 50 okuma demek. Bu bir güvenlik/emek takası ve dengeyi
   ancak sistemi çalıştıran kişi kurabilir.

3. **Bir tur eksik dilimlerle kapatılabilir mi; hangi asgari kapsamadan
   sonra partial Tur 2 kabul edilir?**
   Kapatmaya izin vermek eksik kapsamlı bir A/B/C üretir, izin vermemek tek
   bir yarım dilimin tüm finalistleri süresiz bekletmesi demek. Hangi riskin
   tercih edileceği teknik değil, yatırım tercihi.

4. **Aynı anda kaç aktif araştırma zinciri, ne kadar model bütçesi?**
   Sınır konmazsa asıl sorun komut sayısı değil, aynı anda onlarca araştırma
   çıktısını anlamlandırma yükü olur; ayrıca `sol`/`xhigh` adımların maliyeti
   buradan çıkıyor. Sınırın kendisi bir kapasite beyanı.

5. **Portföy ne sıklıkta uzlaştırılacak; yeni tez açılınca sermaye
   karşılaştırması hemen mi, yoksa aylık rebalansta mı yapılacak?**
   "İşlem kaydı yoksa flat" yasaklandığı için sistemin pozisyonu bilmesi
   düzenli uzlaştırmaya bağlı: ne kadar seyrek uzlaştırılırsa o kadar uzun
   `position_unknown` kalınır ve portföy kararı bloklu olur. İkinci kısım
   ise ritim disiplini ile fırsat kaçırma arasında bir takas.

---

## Uçtan uca akış (7 başlığın birleşik sonucu)

> **Bu, ARAŞTIRMA ALT SİSTEMİNİN uzak hedef durumudur; yapılacak olan
> değildir.** Özet yedi başlık kapandığı andaki resmi gösteriyor; dört
> gözden geçirme turunun revizyonlarını içermiyor. Değişenlerden bazıları:
> eşik çıkarımı (5. madde), haftalık kontrolün kaynağı (6.), aylık
> oturumun sahibi (7.), 1-4. maddelerdeki doğrusal zincirin tamamı (artık
> lead+support), ve akışın kendisi -- fon çerçevesinde bu döngü sermaye
> döngüsünün **altında** yer alır. Ne yapılacağı için "Geçerli tasarım →
> İnşa sırası"na bakın; buradaki lifecycle orada Adım 9'dur.

**Keşif hattı** -- evren turlar hâlinde taranır.
1. Keşif havuzu = evren − açık tezli isimler (B6). Havuz sektöre göre,
   hedef boyuta çekilmiş dilimlere bölünür (B3).
2. **Tur 1:** her dilim ayrı oturumda, ince pack ile taranır; dilim kendi
   finalistlerini işaretler (B3).
3. **Tur 2:** tüm dilimler bitince tek oturum; finalistler tam pack ile
   yan yana karşılaştırılır, gerçek A/B/C burada belirlenir (B3).
4. A/B adayları workflow zincirine girer (tearsheet → comps →
   earnings-preview → pitch ...). Candidate ticker ile anahtarlanır, tek
   kayıt (B2). Yeni bir tur eski `completed_workflows`'u yalnız bucket ya
   da setup değiştiyse bayat sayar (B2).
5. `pitch` `actionable_candidate` verirse **otomatik tez açılır** (B0);
   diğer üç verdikte isim candidate olarak kalır (B1). Tez açılışında
   `first_rejection` ölçülebilir eşiklere çevrilir; ölçülemeyenler metin
   olarak saklanır (B4).

**Portföy/tez hattı** -- tez açıldığı andan itibaren.
6. **Haftalık:** her açık tez için önce mekanik eşik kontrolü; yalnız
   sapanlar için `thesis_tracker` oturumu (B4). `re-underwrite` buradan
   tetiklenir.
7. **Aylık:** `portfolio-risk-management` skill'i tüm açık tezleri
   (fonlanmış + fonlanmamış) ve mevcut pozisyonları görür; giriş/çıkış/
   ağırlık yargısını o verir (B4). Gerçek alım/satımı yalnız insan yapar
   (B0); işlemler append-only, teze bağlı defterde tutulur (B4).
8. Fonlanmamış tez süresiz açık kalır, yalnız bozulunca `retired` olur
   (B5). Retired olan isim keşif havuzuna geri döner (B3).

**Watchlist** ayrı bir süreç değil, bu durumların türevidir (B0, B5).

## Kalibrasyon parametreleri (karar değil, ölçülerek ayarlanacak)

Bunlar config'te tutulacak, koda gömülmeyecek:
- dilim boyutu (bir Tur 1 oturumunda kaç ticker)
- Tur 1 pack'inin inceltmesi (ticker başına hangi alanlar)
- dilim başına finalist kotası -- **tavan, hedef değil** (2. tur): zayıf
  dilim sıfır finalist üretebilir, kotayı doldurmak için isim ilerletilmez
- Tur 2'nin girdi üst sınırı
- mekanik sapma kontrolünün tolerans payları

2. turdan eklenenler:
- tez başına azami sessizlik süresi (`max_staleness`) ve nitel inceleme
  vadesi (`next_review_due`) varsayılanları
- eşzamanlı aktif araştırma zinciri üst sınırı (WIP limiti)
- coverage cycle süresi ve haftalık insan bütçesi
- portföy uzlaştırma sıklığı ve `position_unknown` tolerans süresi

> V1'de Tur 1/Tur 2 mekaniği ertelendiği için ilk üç parametre ancak
> keşif batch'i (V1 planı adım 6) çalıştığında ölçülebilir.

## Açık işler (uygulamadan önce netleşmesi gerekenler)

> **4. tur notu.** Aşağıdaki 1-27 numaralı maddeler **araştırma alt
> sistemine** aittir ve İnşa sırasının 8-10. adımlarında ele alınır. Fon
> omurgası (Adım 0-6) önce gelir ve kendi iş listesi C1-C18 olarak "Gözden
> geçirme — 4. tur" bölümünde durur. Sıralamayı karıştırmayın: aşağıdaki
> hiçbir madde fon omurgasını bloklamaz; **capital policy'nin yokluğu ise
> her şeyi bloklar.**

### Fon omurgası (öncelikli)

- **F-0. Capital policy v0 yazılmalı.** Dört blokaj sorusu ("Kullanıcı
  kararı bekleyen sorular" bölümü) cevaplanmadan hiçbir sermaye kararı
  üretilemez. Bu, dokümandaki tek gerçek başlangıç blokajıdır.
- **F-1. `config/mandate.json` ikiye ayrılmalı:** `research_mandate` (mevcut
  içerik) + `capital_policy` (yeni). Mandate'teki `null` alanlar
  (`position_count`, `benchmark`) capital policy'de açık hükümlere
  dönüşmeli.
- **F-2. C1-C18 platform işleri** -- kimlik, defter, importer, projection,
  valuation, reconciliation, NAV/performans, risk motoru, proposal,
  icra köprüsü, attribution, operatör yüzeyi. Ayrıntı 4. tur bölümünde.
- **F-3. Broker CSV/OFX importer** -- manuel yükü en çok azaltan tek
  yatırım; tam broker API'sinden önce yapılmalı.

### Araştırma alt sistemi

1. ~~**`portfolio-risk-management` skill'i incelenmeli.**~~ **KAPANDI
   (2. tur).** Skill okundu (0.1.31); üç modu da tek pozisyon hakkında,
   portföy-geneli allocator değil. Başlık 4 karar 5 iptal edildi. Kalan iş
   farklı: kanonik `portfolio_snapshot` sözleşmesi ile skill adapter'ı
   ayrılmalı, ve skill V1'de yalnız insanın seçtiği tekil pozisyonda
   opsiyonel çağrılmalı.
2. ~~**`thesis_tracker`'a `pack_step` bağlanmalı.**~~ **YANLIŞ YAZILMIŞTI
   (2. tur).** Tek pack yetmez, iki ayrı pack gerekiyor: küçük deterministik
   `monitoring_snapshot` (mekanik motorun girdisi, LLM'siz) ve zengin
   `thesis_update_pack` (sapma sonrası tracker'ın girdisi). Ayrıca
   `thesis_tracker` config'te tek seferlik terminal candidate adımı olarak
   modellenmiş; candidate zincirinden çıkarılıp `thesis_id` ile anahtarlanan
   tekrarlayan bir lifecycle workflow'u olmalı.
3. **Eksik skill'ler kataloğa eklenmeli** (equity-model-update,
   event-driven-analyzer) -- `route_unsupported` isimlerin gerçek çözümü
   (B1, not).
4. **Bilinen iki bug** (tasarım kararı değil): `WORKFLOW_MAP` substring
   eşleştirmesinin metindeki sırayı değil sözlük sırasını izlemesi; ve
   `run_codex_analysis()`'in `required_context_artifacts`'i hiç
   kullanmaması (B1 notları). İkincisi `codex exec resume` kararıyla
   birlikte ele alınacak.
5. **Ticker-merkezli dizin göçü** -- bugün tek gerçek run olduğu için ucuz
   (B2, karar 5).

Gözden geçirmeden gelen ek işler (2026-08-15):

6. **`append_events()` tek commit kapısına alınmalı** -- bugünkü
   read-modify-write eşzamanlı yazımda sessizce olay kaybettiriyor
   (doğrulandı). Paralel dilimlerden ÖNCE yapılmalı: batch kimliği, monoton
   sequence, kilitli/CAS korumalı tek yazar.
7. **`thesis_opened`'ı üretecek kod yazılmalı** -- bugün yalnız tüketiliyor,
   üreticisi yok (doğrulandı). Pitch completion ile aynı atomik batch'te,
   nedensel idempotency anahtarıyla.
8. **`check_triggers()` açık tezleri görmüyor** -- `state != "waiting"`
   filtresi `thesis_opened` adayları atlıyor (doğrulandı). Haftalık kontrol
   ayrı bir monitoring snapshot'ı üzerine kurulmalı; madde 2 bunun
   parçasıdır ama tek başına yetmez.
9. **B terfi fallback'i düzeltilmeli** -- `unresolved`/`indeterminate` B'yi
   `thesis_tracker`'a yöneltmek kendi kapısını dolanıyor: katalogda tracker
   `pitch` tamamlanmasını şart koştuğu için `_first_missing_prerequisite`
   tam da engellenmek istenen pitch'i kuyruğa koyuyor. Tracker tez-öncesi
   bir "B park yeri" değil.
10. **Onay alanının anlamı ayrılmalı** -- `approval.status=approved` bugün
    hem "deftere yazılabilir" hem "analiz doğrudur" anlamına geliyor. İlk
    üretim olayından önce ayrılmazsa sonradan otomasyon eklemek geçmiş
    olayların anlamını belirsizleştirir.
11. **İşlem giriş komutu yok** -- portföy defterinin tamamı buna bağlı
    (B4, karar 6 revizyonu). Bununla birlikte portföy uzlaştırma olayı ve
    `position_unknown` da ilk gerçek işlemden önce gelmeli.
12. **`codex exec resume` komut şekli düzeltilmeli** -- `-C` global bayrak
    olarak `exec`'ten önce verilmeli, yoksa resume artifact dizinini
    kaybediyor (doğrulandı; ayrıntı için resume revizyon notu). Aynı notta
    `-s read-only`'nin bu kurulumda hiç uygulanmadığı da kayıtlı --
    bu, resume'dan bağımsız, bugün de geçerli bir güvenlik boşluğu.

2. turdan gelen ek işler (2026-08-15):

13. **`capital_policy` yazılmalı** -- V1'i bloklamıyor ama portföy
    katmanının tamamını blokluyor. `mandate.json` bugün yalnız araştırma
    mandate'i; sermaye tabanı, nakit yaklaşımı, tek-isim riski, kayıp
    bütçesi ve ağırlıklandırma ilkesi yok. Bu yazılana kadar sistem hedef
    ağırlık veya rebalans öneremez. (Kullanıcı sorusu 1 ve 2.)
14. **Kanonik defter git'ten çıkarılmalı** -- git merge ve history rewrite
    domain atomikliğini korumuyor; bu repoda geçmiş zaten iki kez "clean
    reset" ile kesilmiş. Öneri: SQLite'ta tek yazarlı transaction'lı
    defter, git'te kod/şema/config ve mühürlü checkpoint.
15. **V1 defteri mühürlenip V2 lineage başlatılmalı** -- 57 olay ve tek
    gerçek run varken ucuz. V1 dosyası dondurulur, hash'i ve olay sayısı
    kaydedilir, deterministik migration ile V2 üretilir, runtime yalnız V2
    bilir. Bu append-only ihlali değil, yeni bir defter nesli.
16. **Olay zarfı V2'ye geçmeli** -- `sequence`, `batch_id`, `subject_type`/
    `subject_id`, `causation_id`, `occurred_at`/`recorded_at`; zorunlu
    `run_id`+`ticker` kalkmalı. `workflow_request_id` ile `attempt_id`
    ayrılmalı.
17. **`source_interpretation_corrected` bölünmeli** -- B→A terfi için
    `promotion_evaluated`, dar anlamlı kaynak düzeltmesi ayrı kalır. Bugün
    tek olay bucket atayabiliyor.
18. **agy fail-open noktaları kapatılmalı** -- `bucket ... or "B"` sessiz
    varsayılanı, boş ticker'ın sessizce atlanması, çıkarım başarısızlığının
    kaydedilmemesi (`result_attached` yazılmış ama domain geçişi yok --
    `structured_extraction_failed` durumu gerekiyor), ve 24.000 karakter
    sınırının argv yerine stdin/dosya ile aşılması.
19. **Kurumsal işlem ↔ fiyat eşiği bağı** -- eşik kuralları
    `price_basis_date` ve `adjustment_policy` taşımalı; adjustment
    tamamlanmadan sonuç `deviation` değil `indeterminate` olmalı. Aksi
    hâlde bir hisse bölünmesi tez bozulmadan re-underwrite tetikler.
20. **Operatör yüzeyi (P0-P4 kuyruğu + karar ekranı)** -- planın 7.
    adımı. Bu yapılmazsa tüm adjudication kapıları törene dönüşür ve
    haftalık yük 9-14 saate çıkar.

3. turdan gelen ek işler (2026-08-16) — hepsi kodda/config'te doğrulandı:

21. **`date_due` otomatik iş hazırlayamaz.** `evaluate_trigger` bu tip için
    yalnız `today >= due` dönüyor; oysa tetikleyicinin içinde tarihin tahmin
    olduğu bilgisi (`date_status: "estimated"`) zaten yazılı ve okunmuyor.
    Pack'lerdeki takvim kaynağı da `date_confirmed: false` ve "IR sayfası
    doğrulayana kadar tahmin say" notuyla geliyor. Tarih yalnız *kanıt
    kontrolü vadesi* üretmeli.
22. **Kanıt gözlem katmanı yok.** `FilingRef` SEC'in `items` alanını
    düşürüyor; ham submissions'ta okunan Item 2.02 bilgisi typed katmana
    taşınmıyor. İki seviye gerekiyor: `release_observed` (yeni accession +
    Item 2.02) ve `evidence_available` (asıl belge alındı, hash'lendi,
    dönemi doğrulandı).
23. **Destek adımı lead'in amacını eziyor.** Bir ön koşul adımı çalıştığında
    `workflow_prepared`'daki `requested_workflow` korunuyor ama adım kendi
    rota önerisiyle tamamlandığında asıl istek iz bırakmadan kayboluyor.
    Vaka açıldığında lead ve amaç sabitlenmeli; support yalnız kanıt ve
    bağlayıcı olmayan öneri üretmeli.
24. **İki workflow'un yapılandırılmış çıkarımı hiç yok.**
    `WORKFLOW_EXTRACTION` sözlüğünde `earnings_deep_dive` ve
    `thesis_tracker` bulunmuyor -- ikisi de işletim döngüsünün merkezinde.
    Sonuç metni üretiliyor ama makine okuyamıyor.
25. **`pack_step` veri sözleşmesi değil.** Bugünkü yapı monolitik pack +
    geç budama; adım varyantları esas olarak talimat metni. Kanonik
    snapshot → pack recipe → adıma özel pack mimarisine geçilmeli.
26. **`allowed_next` silinmeli, `required_workflows` ikiye ayrılmalı**
    (`hard_artifact_requirements` + `support_policy`); katalog v2 şemasına
    geçilmeli.
27. **`initiating_coverage` normal katalogdan çıkarılmalı** -- katalog-dışı,
    insan onaylı escalation olmalı; idea-generation'ın önerisi yalnız
    `capability_gap` sinyali sayılmalı, çalıştırma yetkisi değil.
