En önemli düzeltme şu: “çekirdek skill” artık “fonun çekirdeği” anlamına gelemez. Fonun zorunlu çekirdeğinde hiçbir LLM skill’i yoktur; önceki altı skill, hedef araştırma alt sisteminin çekirdeğidir.

## 1. 23 skill’in fon çerçevesindeki yeni hükmü

| Skill | Eski hüküm | Yeni hüküm | Gerekçe / koşul |
|---|---|---|---|
| catalyst-calendar | Gereksiz | **Koşullu** | Kanonik tarih kaynağı olamaz; fakat çoklu/örtüşen katalizörlerin sermaye karar penceresine etkisini analiz etmek için kullanılabilir. |
| company-tearsheet | Çekirdek | **Araştırma çekirdeği** | Issuer baseline üretir; doğrudan sermaye kararı veya ağırlık üretmez. |
| comps-valuation | Çekirdek | **Araştırma çekirdeği** | `valuation_anchor` üretiminin hafif ve varsayılan yoludur. |
| dcf-model-builder | Gereksiz/V1 dışı | **Escalation** | Comps ve implied-expectations sermaye kararına yetmiyorsa ve workbook bakım sorumluluğu açıkça kabul ediliyorsa açılır. |
| deck-report-qc | Gereksiz | **Gereksiz** | Dış dolaşım veya sunum üretimi ürün amacı değil. |
| earnings-deep-dive | Çekirdek | **Araştırma çekirdeği** | Yeni filing/earnings kanıtının mevcut tez veya aktif vaka üzerindeki etkisini inceler. |
| earnings-preview | Koşullu | **Koşullu** | Özellikle fonlanmış tezlerde beklentiyi olay öncesinde dondurmak için; her adayda rutin çalışmaz. |
| economic-impact-report | Gereksiz | **Koşullu** | Artık subject’i vardır: `risk_driver` veya `portfolio_exposure_cluster`; maddi makro/politika şoklarında çoklu pozisyon etkisini analiz eder. |
| equity-model-update | Gereksiz/V1 dışı | **Koşullu, model yoluna bağlı** | Yalnızca kanonik ve sermaye kararında kullanılan bir workbook varsa devreye girer. |
| event-driven-analyzer | Gereksiz | **Koşullu** | Getiri dağılımı birleşme, regülasyon, dava veya başka ayrık bir olaya bağlıysa kullanılır. |
| financials-normalizer | Gereksiz | **Gereksiz** | Kanonik finansal veri otoritesi deterministik PIT/XBRL hattıdır; LLM normalizasyonu ikinci otorite yaratır. |
| idea-generation | Çekirdek | **Araştırma çekirdeği** | Challenger ve discovery hattını besler; fonun muhasebe çekirdeği için değil, fırsat üretimi için gereklidir. |
| initiating-coverage | Escalation | **Escalation** | Normal baseline + hedefli support yetersizse ve insan geniş kapsamlı underwriting maliyetini onaylarsa çalışır. |
| long-short-pitch | Çekirdek | **Araştırma çekirdeği** | Long-only karar modu, zorunlu ayı/red-team bölümü ve `recommended_expression=long|none` sınırıyla tez üretir. |
| meeting-prep | Gereksiz | **Gereksiz** | Tanımlı yönetim/analist toplantısı iş akışı yok. |
| memo-builder | Koşullu | **Koşullu** | Dönem sonu fon/karar sentezi için sunum katmanıdır; domain state veya sermaye kararı üretmez. |
| model-audit-tieout | Gereksiz/V1 dışı | **Koşullu, model yoluna bağlı** | Workbook sermaye kararına girdi olacaksa güvenilmeden önce zorunlu hâle gelir; workbook yoksa çalışmaz. |
| portfolio-risk-management | Gereksiz | **Koşullu support** | Deterministik risk motoru veya allocator değildir; olağandışı pozisyon riski, exposure yorumu ve yapılandırılmış risk incelemesinde danışmanlık yapar. |
| public-equity-investing | Meta | **Meta** | Çalıştırılmaz; plugin politikası, ortak sözleşmeler ve routing standardı sağlar. |
| scenario-sensitivity-generator | Koşullu | **Koşullu** | `downside_case` zorunludur ama bu skill zorunlu üreticisi değildir; mevcut base case üzerinde doğrusal olmayan hassasiyet gerekiyorsa çağrılır. |
| thesis-tracker | Çekirdek | **Araştırma lifecycle çekirdeği** | Kanıtı teze göre yorumlar ve durum değişikliği önerir; kanonik state’i kendisi değiştirmez. |
| three-statement-model-builder | Gereksiz/V1 dışı | **Escalation** | Tezin anlaşılması gerçekten entegre tahmin modeli gerektiriyorsa ve sürekli bakım sahibi atanıyorsa açılır. |
| user-context | Gereksiz | **Gereksiz** | Mandate, capital policy ve kullanıcı bağlamının kanonik sahibi repodur; plugin-local hafıza ikinci otorite yaratır. |

Yeni dağılım:

- 6 araştırma çekirdeği
- 9 koşullu
- 3 escalation
- 4 gereksiz
- 1 meta

Buradaki en önemli iki sınır:

- `downside_case` çekirdek bir domain artefaktıdır; `scenario-sensitivity-generator` yalnızca koşullu üreticilerinden biridir.
- `risk_driver_registry` çekirdek domain state’idir; `economic-impact-report` ona kanıt ve yorum önerir, registry’yi kendisi değiştiremez.

Workbook kümesi artık “değersiz” değildir; fakat daha önemli hâle gelmesi onu rutinleştirmez. Tam tersine, modelin sermaye kararına etkisi arttıkça oluşturma, güncelleme ve audit zincirinin tamamı birlikte üstlenilmelidir. Yarım workbook yolu kabul edilmemelidir.

## 2. Hiçbir skill’in karşılamadığı fon platformu işleri

Boyutlar yaklaşık olarak: küçük 2–5 gün, orta 1–2 hafta, büyük 2–4 hafta. İşler paralel ve örtüşebilir; süreler doğrudan toplanmamalıdır.

| Kod | Platform işi | Boyut | Blokladığı / bağımlılığı |
|---|---|---:|---|
| C1 | Fon, hesap, security, para birimi ve broker kimlikleri | Orta | Bütün muhasebe, reconciliation ve performansı bloklar. |
| C2 | Kanonik append-only finansal olay defteri, atomik commit ve idempotency | Büyük | Tüm projection ve denetim izinin temelidir. |
| C3 | Sürümlü capital policy, policy assumption ve override yönetişimi | Orta | Risk motoru ve proposal üretimini bloklar. |
| C4 | Açılış portföyü onboarding’i ve broker snapshot aktarımı | Orta | Gerçek mevcut portföy bilinmeden NAV/risk/proposal üretilemez. |
| C5 | Broker CSV/OFX/manual activity importer ve kaynak provenance’ı | Büyük | Düzenli fill, nakit ve corporate-action girişini bloklar. |
| C6 | Fill, dış nakit akışı, temettü, vergi, ücret, faiz ve corporate-action olay modeli | Büyük | Pozisyon, nakit ve NAV doğruluğunu bloklar. |
| C7 | Pozisyon, lot, maliyet tabanı ve nakit projection’ları | Büyük | NAV, risk, attribution ve proposal’ı bloklar. |
| C8 | Fiyat/FX/as-of valuation katmanı | Orta | NAV, ağırlık, risk ve performansı bloklar. |
| C9 | Çok eksenli reconciliation motoru | Büyük | Broker gerçekliğiyle sistem gerçekliğine güvenmeyi bloklar. |
| C10 | NAV, dış akış ayrımı, TWR, MWR/XIRR ve drawdown omurgası | Büyük | Performans, drawdown tetikleri ve risk bütçesini bloklar. |
| C11 | Deterministik risk motoru | Büyük | Limit, loss budget, gap riski, likidite, driver yoğunluğu ve proposal güvenliğini bloklar. |
| C12 | Kontrollü causal-driver registry ve exposure eşlemesi | Orta | Driver yoğunlaşması analizini bloklar; minimum muhasebe fonunu bloklamaz. |
| C13 | `policy_eligible`, `underwritten_investable` ve `capital_actionable_now` materializer’ları | Orta | Hangi isimlerin sermaye yarışına girebildiğini belirler. |
| C14 | Ağırlık bandı, binding constraint, no-trade band ve replacement-hurdle hesaplayıcısı | Büyük | Portföy önerisi üretilmesini bloklar. |
| C15 | `portfolio_proposal` sürümleme, geçerlilik, alternatif, onay ve override lifecycle’ı | Orta | Yetkili sermaye kararını bloklar. |
| C16 | Trade intent, insan broker icrası, fill/deviation/expiry köprüsü | Büyük | Kararın gerçek portföye kontrollü biçimde geçmesini bloklar. |
| C17 | Pozisyon/tez/karar attribution’ı ve dondurulmuş counterfactual değerlendirme | Büyük | Fonun öğrenme ve hesap verebilirlik katmanını bloklar; ilk işlemi bloklamaz. |
| C18 | Operatör yüzeyi, kuyruklar, recovery, replay, backup, audit ve regresyon testleri | Büyük | Güvenli tek kişilik işletimi bloklar; C2’den itibaren parça parça kurulmalıdır. |

Araştırma tarafındaki F1–F18 ile bu liste doğrudan toplanıp “36 bağımsız modül” sayılmamalıdır. Kimlik, olay defteri, artefakt, doğrulama, operatör yüzeyi, recovery ve test altyapısı iki tarafta ortaktır. Birleşik sistem yaklaşık 25–30 ayrı platform yeteneğine dönüşür.

Sonuç yine de açık: bu artık skill orkestratörü değildir. Bu, araştırma sağlayıcısı olarak plugin kullanabilen bir portföy işletim sistemidir. Skill çağırma mekanizması yazılımın muhtemelen yalnızca %10–15’idir; geri kalanı para, state, yetki, güvenilirlik ve denetim altyapısıdır.

Bu kapsam ayrımı süre tahminini de keskinleştirir:

- Minimum fon omurgası: 8–11 hafta.
- Fon + tek araştırma dikeyi: 16–24 hafta.
- C1–C18 ile F1–F18’in tamamının üretim kalitesinde olgunlaştırılması: 24–36 hafta ve sonrasında sürekli bakım.

Dolayısıyla önceki 16–24 hafta tahmini, “bütün hedef platform” değil, daraltılmış birleşik dikey dilim için geçerlidir.

## 3. Fon tarafında LLM’e ihtiyaç var mı?

Minimum çalışan fon döngüsünde LLM zorunlu değildir.

Muhasebe, NAV, risk, limit, proposal envelope, onay, icra, fill ve reconciliation tamamen deterministik motorlar + insan yetkisiyle çalışabilir. Bu önemli bir özellik: plugin bozulsa veya kaldırılsa bile fonun defteri ve kontrol sistemi çalışmaya devam etmelidir.

LLM’in fon tarafındaki meşru rolleri yalnızca danışmanlık ve açıklamadır:

- Deterministik proposal’ı insan dilinde özetlemek; yalnızca mevcut alanları açıklayabilir, yeni sayı veya kural icat edemez.
- İki sermaye alternatifi arasındaki nitel farkları karşılaştırmak; karar veremez ve hedef ağırlığı commit edemez.
- `risk_driver` ve transmission-path etiketi önermek; insan onayı olmadan registry’ye yazamaz.
- Reconciliation uyuşmazlığının olası nedenlerini sıralamak; düzeltme olayı üretemez.
- Downside/gap senaryosu önermek; sayısal etkiler validator ve insan kapısından geçer.
- Dönem sonu attribution ve policy-review bulgularını sentezlemek; policy’yi otomatik değiştiremez.
- Eksik veya çelişkili veriyi açıklayan bir araştırma görevi önermek; kanonik veriyi tamamlanmış sayamaz.

Kesinlikle LLM’e verilmemesi gerekenler:

- Fill, nakit, lot, maliyet tabanı veya corporate-action kaydı
- NAV, TWR, MWR, ağırlık ve P&L hesabı
- Security/broker kimliği eşlemesinin sessiz kabulü
- Limit, loss-budget, likidite, gap ve drawdown hesapları
- Policy uyumluluğu ve binding constraint tespiti
- Proposal geçerliliği ve yeniden onay gereksinimi
- Nihai hedef ağırlık, işlem onayı veya emir iletimi
- Reconciliation farkının otomatik düzeltilmesi
- Capital policy değişikliği veya override
- İnsan adjudication’ı gerektiren thesis/risk state değişimleri

Kısacası: fon çekirdeğinde LLM bir otorite değil, açıklayıcı ve analitik danışmandır. LLM tamamen çıkarıldığında sistem daha az akıllı olabilir; fakat daha az doğru, daha az tutarlı veya muhasebe bakımından eksik olmamalıdır. Bu, mimarinin en güçlü bağımsızlık testi olmalıdır.