Varsayımlar: tek broker hesabı, tek sahip, yaklaşık 10 pozisyon, EOD değerleme, resmi fon muhasebesi/vergi motoru yok ve broker’dan en azından yapılandırılmış CSV/OFX alınabiliyor. Yalnız PDF varsa süre uzar.

## 1. Yeni inşa sırası

| # | Adım | Ne yapılır? | Neden bu sırada? | “Bitti” tanımı | Tahmin |
|---:|---|---|---|---|---:|
| 0 | Fon sözleşmesi ve Capital Policy v0 | Ürün sınırı, base currency, yatırım uygunluğu, nakit, sizing/readiness, kayıp bütçesi, yoğunlaşma, histerezis, drawdown, governance ve policy assumption’lar sayısallaştırılır | Sonraki bütün hesapların neyi doğru sayacağı buna bağlıdır | Policy’de sessiz `null` yok; örnek üç portföy kararı deterministik olarak pass/fail oluyor; gevşetme governance’ı tanımlı | 3–5 gün |
| 1 | Kanonik finansal omurga | Portfolio/account/security, cash activity, external flow, transaction, fill, snapshot ve policy kimlikleri; tek yazarlı ledger, idempotency, replay, backup/recovery kurulur | Gerçek para state’i güvenilir olmadan NAV veya karar kurulamaz | Aynı import iki kez duplicate üretmiyor; crash/replay aynı state’i veriyor; iç karar ile dış broker gözlemi ayrılıyor | 1–2 hafta |
| 2 | Açılış kitabı ve broker importer | Broker positions/cash/activity içeri alınır; opening book, statement batch, çok-boyutlu reconciliation ve discrepancy akışı kurulur | Sistem önce gerçekte neye sahip olduğunu bilmelidir | Gerçek bir ekstre iki kez güvenle içeri alınabiliyor; position/cash eşleşiyor; açıklanamayan fark görünür ve yeni riski blokluyor | 1–2 hafta; PDF-only ise +1–2 |
| 3 | NAV ve temel performans | Fiyat/FX, cash, dividends, fees, external flows; NAV snapshot, TWR, MWR, P&L ve drawdown hesaplanır | Ağırlık, kayıp bütçesi ve performans aynı NAV paydasına dayanır | Elle hesaplanan fixture ile NAV/TWR/MWR eşleşiyor; para yatırma TWR’ı bozmuyor; eksik fiyat/NAV sessiz geçmiyor | 1–2 hafta |
| 4 | Deterministik risk engine | Weight, cash, issuer/sector limitleri, downside/gap kapasitesi, liquidity assumption, drawdown, driver registry ve breach olayları | Proposal ancak mevcut kitabın risk kapasitesi biliniyorsa üretilebilir | Aynı snapshot aynı `portfolio_risk_snapshot`ı veriyor; gap, limit, driver ve assumption test vakaları doğru alarm üretiyor | 1–2 hafta |
| 5 | Portfolio proposal ve karar kapısı | Eligible band, policy-compliant max, replacement hurdle, status quo/alternatifler, validity contract, trigger ve insan onayı kurulur; research girdileri başlangıçta elle verilebilir | Fonun asıl ürünü mevcut kitaptan hedef kitaba geçiş kararıdır | Mevcut snapshot’tan `no_change` veya gerekçeli proposal çıkıyor; hard limit aşılmıyor; onaysız proposal sermaye state’ini değiştirmiyor | 1–2 hafta |
| 6 | İcra köprüsü ve operasyon yüzeyi | Trade ticket, icra-anı adet hesabı, partial fills, unplanned trades, cash activity, post-trade reconciliation, expiry/deviation ve basit “Bugün” yüzeyi kurulur | Karar gerçek dünyaya güvenle bağlanmadan sistem fon yönetemez | `snapshot → proposal → approval → ticket → fill import → reconciliation → yeni NAV` uçtan uca çalışıyor; partial/unplanned senaryolar kaybolmuyor; recovery provası geçiyor | 2–3 hafta |
| 7 | Gelişmiş attribution ve accountability | Position/thesis/decision attribution, counterfactual path, execution shortfall ve üç aylık performance/process review eklenir | Temel fon çalıştıktan sonra karar mekanizmasının kalitesi ölçülebilir | Bir replacement kararı statükoya karşı; bir tez para/claim/process eksenlerinde değerlendirilebiliyor | 2–3 hafta |
| 8 | Araştırma–sermaye arayüzü | Dört set, R0–R5 kuyruk, VOI kapısı, manual readiness/downside/driver girişi ve portföyden research task üretimi kurulur | Araştırmanın çıktısı doğrudan LLM eylemi değil, adjudicated capital input olmalıdır | Bir risk olayı research task açıyor; kabul edilen sonuç weight bandını yeniden hesaplatıyor; research target’ı doğrudan değiştiremiyor | 1–2 hafta |
| 9 | Kanıt–pitch–tez–tracker dikey dilimi | Evidence collector, pack/sidecar, validator, pitch adjudication, thesis, monitoring ve üç gölge vaka kurulur | Fon omurgası kanıtlandıktan sonra araştırma otomasyonu sermayeye bağlanabilir | Üç gölge vaka geçiyor; kabul edilen pitch investable set’e giriyor; tracker yeni tez açamıyor; eksik kanıt fail-closed | 3–5 hafta |
| 10 | Discovery ve ölçekleme | Policy-eligible evren, küçük batch’ler, portföy moduna göre discovery bütçesi ve challenger/replacement akışı eklenir | Yeni fikir hacmi ancak bütün downstream döngü çalışınca güvenlidir | Discovery araştırma adayı üretir ama sermaye kararı üretmez; dolu kitapta minimum opsiyonellik sürer; pipeline kapasiteyi aşmıyor | 2–3 hafta |

### Sistem ne zaman “kötü de olsa fon” olur?

**Adım 6 tamamlandıktan sonra.**

O noktada araştırma girdileri hâlâ elle girilebilir, fakat sistem:

- Sermayeyi ve nakdi bilir.
- NAV ve performansı ölçer.
- Policy ve risk sınırları uygular.
- Hedef portföy önerir.
- İnsan onayını kaydeder.
- İcra ticket’ı üretir.
- Gerçek fills’i alır.
- Broker ile uzlaştırır.
- Yeni state’i yeniden değerler.

Bu kapalı sermaye döngüsüdür. İlk gerçek para ancak Adım 6’nın dry-run ve recovery testleri geçtikten sonra bu sistemle yönetilmelidir. Adım 7’den sonra hesap verebilirliği güçlü; Adım 9’dan sonra araştırma ile beslenen bir fon olur.

### Süre

- İyi bir CSV/OFX broker export’uyla minimum fon dikey dilimi: **8–11 hafta**.
- PDF-only veya dağınık broker verisiyle: **10–14 hafta**.
- Attribution + araştırma entegrasyonu + discovery dâhil hedef sistem: **16–24 hafta**.

Sezgine kısmen katılıyorum: fon omurgasının kavramsal belirsizliği araştırma omurgasından daha düşüktür; muhasebe, NAV ve limitler deterministiktir. Ancak hata toleransı çok daha düşüktür. Import idempotency, reconciliation, cash flows, partial fills ve recovery testleri ciddi süre alır.

Dolayısıyla minimum fon omurgası önceki 9–12 haftalık araştırma V1’iyle **aynı bantta veya biraz daha ucuzdur**; ikisini birleştiren gerçek hedef sistem belirgin biçimde daha uzundur.

## 2. Önceki turlardan ölen veya değişen kararlar

### Tamamen ölenler

- **“V1 araştırma/izleme defteridir, sermaye tahsis sistemi değildir.”**  
  Tersine döndü: ürün tek sahibin sermayesini yöneten fon sistemidir; araştırma onun alt sistemidir.

- **“Sistem hedef ağırlık veya rebalans öneremez.”**  
  Öldü: sistem hedef portföy, sermaye kararı ve işlem önerisi üretebilir; yalnız broker’a emir iletemez.

- **“Portföy sonraki sürümdedir.”**  
  Öldü: portfolio/account/cash/NAV/risk/proposal/execution ilk omurgadır.

- **“Önce araştırma dikey dilimi kanıtlanır.”**  
  Öldü: önce fonun muhasebe–karar–icra döngüsü kanıtlanır; araştırma sonra bağlanır.

- **“Mevcut deneme koşuları korunmalı, bugünkü hat yamalanmalı.”**  
  Öldü: koşular değersiz test verisidir; greenfield finansal omurga kurulabilir.

- **26 Ağustos köprüsü ürün önceliğidir.**  
  Öldü: legacy tetikleyiciler kapatılabilir; köprü yalnız yeni evidence hattı için test fixture’ı istenirse anlamlıdır.

- **9–12 haftalık araştırma V1’i ürün yol haritasıdır.**  
  Öldü: artık yalnız araştırma alt sisteminin eski tahminidir.

### Tersine dönen veya daralanlar

- **Capital policy yokluğu → portföyü kapsam dışı bırakır.**  
  Yeni hüküm: capital policy yokluğu ilk çözülmesi gereken ürün boşluğudur.

- **Capital policy yazılmadan sistem sıralama/sermaye kararı yapamaz.**  
  İlke doğruydu; blokaj kalkıyor çünkü policy v0 artık ilk adımda yazılıyor.

- **`portfolio-risk-management` gereksiz.**  
  Koşullu support oldu: sıra dışı sizing, gap, exposure veya qualitative risk için kullanılabilir; portföy allocator’ı veya risk engine değildir.

- **`thesis_opened` yalnız izlenen görüştür.**  
  Kısmen geri dönüyor: artık security’yi `underwritten_investable_set`e kabul eden kapıdır. Yine alım veya `capital_actionable_now` anlamına gelmez.

- **Pitch/action dili sermaye dışıdır.**  
  Daraldı: pitch target weight veya işlem üretmez; fakat kabul edilmiş tez sermaye değerlendirmesini besler. `add/trim/exit` yalnız portfolio proposal katmanında yetkilidir.

- **Portföy defteri tez defterine eklenen ayrı kayıt alanıdır.**  
  Değişti: portföy ana aggregate root’tur; tez ve araştırma ona girdi sağlar.

- **Tek mantıksal gerçeklik kaynağı.**  
  Daraldı: sistem iç kararların otoritesidir; broker fills/positions/cash, piyasa kaynağı da fiyat gerçeğinin dış otoriteleridir. Bir source-of-truth matrisi gerekir.

- **Keşif havuzu = evren − açık tezliler.**  
  Değişti: akış `universe → policy_eligible → underwritten_investable → capital_actionable` kümelerine ve portföy-modlu discovery bütçesine dayanır.

- **Skill kataloğu 10+1 ürünün ana mimarisidir.**  
  Daraldı: araştırma alt sisteminin hedef kataloğudur; fon omurgasını veya ilk inşa sırasını tanımlamaz.

### Aynen ayakta kalan veya güçlenen kararlar

- **Aylık portföy review’ı, varsayılan `no_change`.**  
  Aynen kalır ve histerezisle güçlenir: aylık ritim karar yenileme ritmidir, işlem ritmi değildir. Hard risk/tez olayları takvimi beklemez.

- **Research mandate ile capital policy ayrıdır.**  
  Tamamen ayakta; yalnız capital policy artık kapsam dışı değil birinci sınıf artefakttır.

- **Company / security / thesis / capital action ayrımı.**  
  Güçlendi: iyi şirket/tez doğrudan iyi portföy eylemi değildir.

- **İnsan gerçek icranın sahibidir.**  
  Güçlendi ve netleşti: sistem karar ve ticket üretir, insan broker’a iletir.

- **Analiz, adjudication ve domain commit ayrıdır.**  
  Araştırmada da sermaye kararında da korunur.

- **Tek yazarlı, idempotent, replay edilebilir iç ledger.**  
  Gerçek para nedeniyle daha da önemlidir; Git kanonik ledger değildir.

- **Broker gerçeği ile sistem meşruiyeti ayrıdır.**  
  Broker pozisyonun varlığında, sistem policy meşruiyetinde otoritedir.

- **İşlem yokluğundan `flat` türetilemez; `position_unknown` ayrıdır.**  
  Sermaye proposal’larını bloklayan temel invariant olarak kalır.

- **Fills ayrı kanonik kayıtlardır; projection toplulaştırır.**  
  Performans, cash ve reconciliation için korunur.

- **Reconciliation tek boolean değildir.**  
  Position, cash, transaction, cost basis ve corporate action ayrı status taşır.

- **Nakit birinci sınıf gerçektir.**  
  Muhasebede pozisyon, tahsiste meşru residual olarak kalır.

- **Conviction değil underwriting readiness.**  
  LLM sıfatı sermaye ağırlığına çevrilmez.

- **Kayıp bütçesi stop değildir.**  
  Pozisyon öncesi sizing sınırıdır; fiyat hareketi review tetikler.

- **Drawdown otomatik satış değildir.**  
  Capital policy’de zorunlu yeniden inceleme/freeze tetikler.

- **Causal driver ile korelasyon farklıdır.**  
  Biri nedensel hipotez, diğeri ampirik alarm olarak korunur.

- **`no_deviation` tez sağlıklı demek değildir.**  
  Ölçülmeyen veya gecikmiş kontroller görünür kalır.

- **PIT/provenance (`known_at`, `period_end`, source hash) zorunludur.**  
  Araştırma, NAV ve karar attribution’ında daha da önemlidir.

- **Tez açma yetkisi pitch’tedir; tracker yeni tez açamaz.**  
  Aynen kalır.

- **Evidence / assessment / adjudication ayrımı.**  
  Araştırma çıktısının doğrudan sermaye state’i değiştirmesini engeller.

- **Lead support ihtiyacını bildirir, orkestratör yürütür.**  
  Araştırma alt sisteminde aynen kalır.

- **Plugin değiştirilebilir sağlayıcıdır.**  
  Fon domain modeli hiçbir plugin enum’una veya sürümüne bağlanmaz.

- **İnsan yüzeyi güvenlik mimarisinin parçasıdır.**  
  Artık yalnız adjudication değil, proposal, execution, reconciliation ve R0–R5 kuyruğunu da kapsar.

- **Performans policy’yi otomatik değiştirmez.**  
  Calibration signal üretir; değişiklik insan onayı ve cooling-off ister.

Özetle önceki emeğin araştırma, kanıt, adjudication, izleme, provenance ve insan güvenliği katmanları çöpe gitmedi. Yanlış olan onların varlığı değil, **ürünün merkezi sanılmalarıydı**. Şimdi aynı parçalar fonun sermaye döngüsünün altına doğru yere taşınıyor.