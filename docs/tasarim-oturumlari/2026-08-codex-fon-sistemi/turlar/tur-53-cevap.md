Ana hüküm: Saydığın temaslar iş açısından doğru, fakat bunlar **beş ayrı teknik entegrasyon olmamalı**. Fon ile eklenti arasında tek bir sınır olmalı: araştırma talebi dışarı çıkar, skill sonucu provisional döner, doğrulanıp adjudicate edilir, yalnız kabul edilmiş capital input fon çekirdeğine girer.

```text
fon olayı/snapshot
→ research_work_request
→ araştırma orkestratörü + skill
→ provisional araştırma artefaktları
→ contract validation
→ insan adjudication
→ capital_input_manifest
→ deterministik risk/proposal motoru
```

## 1. Temas yüzeyleri

| Temas | Gerçek rolü | V0 |
|---|---|---|
| Underwritten sete kabul | Pitch lead; tearsheet/comps destek olabilir. Kabul edilmiş sonuç security’yi investable yapabilir. | Fon omurgası V0’da gerekmez; ilk araştırma entegrasyonu budur. |
| Tez izleme/re-underwrite | Tracker lifecycle sahibidir; deep-dive yeni olayın analitik desteğidir. | İkinci entegrasyon dilimi. |
| Downside/valuation güncellemesi | Ayrı lifecycle teması değil; underwriting veya monitoring vakasının hedefli support işidir. Comps/scenario yalnız aday üreticidir. | Skill gerekmez; insan typed girdiyi elle sağlayabilir. |
| Discovery | Idea-generation yalnız araştırma adayı üretir; investable veya capital-actionable hükmü vermez. | En son gelir. |
| Driver yoğunlaşması yorumu | Risk motoru alarmı deterministik üretir; economic-impact veya portfolio-risk-management yalnız açıklama/araştırma desteği verir. | V0 dışı ve koşullu. |
| Performans geri beslemesi | Eksik altıncı temas: attribution veya karar incelemesi yeni tez/re-underwrite/calibration işi açabilir. Policy’yi otomatik değiştiremez. | Attribution sonrasında. |

Dolayısıyla muhasebe/NAV V0’da **sıfır skill**, ilk risk/proposal sürümünde de teknik olarak **sıfır skill** gerekir. İnsan, gerekli capital input’ları typed biçimde elle girebilir. Skill entegrasyonu bu girdilerin üretimini iyileştirir; fonun doğruluğunu kurmaz.

## 2. Yön ve çalışma biçimi

İki yön semantik olarak farklıdır ama aynı dayanıklı altyapıyı kullanmalıdır:

- **Fon → araştırma:** `research_work_requested`. Asenkron görevdir; risk motoru bir LLM çağrısını beklemez ve aynı transaction içinde skill çalıştırmaz.
- **Araştırma → fon:** `capital_input_adjudicated`. Skill completion değil, kabul edilmiş sürümlü domain artefaktı gelir.

“Kullanıcı şimdi çalıştır” dese bile teknik akış senkron RPC olmamalı; görev açılır, attempt çalışır, sonuç kaydedilir ve ayrı bir adjudication ile etkinleşir. Gerekli girdi gelmemişse risk motoru beklemez: sonuç `insufficient_research_input` olur, yeni risk artırımı bloklanır veya yalnız statüko/de-risk seçenekleri üretilebilir.

## 3. Aradaki sözleşme

Tek, zamanla yamalanan bir `adjudicated_capital_input` kaydı yanlış olur. Alanların üreticileri ve bayatlama ritimleri farklıdır. Ayrı sürümlü nesneler gerekir:

- `thesis_version`
- `underwriting_readiness_decision`
- `downside_case`
- `valuation_anchor`
- `risk_driver_exposure_set`
- `monitoring_contract/status`

Fon motorunun okuduğu tek şey ise bunları exact sürüm ve digest’leriyle bağlayan immutable bir **`capital_input_manifest`** olmalıdır. Readiness kararı diğer nesnelere referans verir; valuation veya downside sonradan değiştiğinde eski readiness sessizce geçerli kalamaz.

Skill doğrudan bunların hiçbirini etkinleştiremez. Skill yalnız `proposed_*` artefakt üretir. Raw kanıt provenance ve şema kontrolüyle otomatik kaydedilebilir; fakat investable kabulü, readiness, downside, valuation hükmü, driver eşlemesi veya tez governance’ı fonu etkiliyorsa V0’da insan adjudication’ı zorunludur. İnsan kapısı her skill çağrısından önce değil, **araştırma hükmünün capital input’a dönüşmesinden önce** durur.

## 4. Eklenti kapatılırsa

Fon şunları kaybetmez:

- Broker importu, nakit, pozisyon ve lot gerçeği
- NAV, performans ve reconciliation
- Policy ve hard-limit kontrolleri
- Drawdown, korelasyon ve deterministik risk alarmları
- Mevcut kabul edilmiş girdilerden proposal üretimi
- İnsan onayı, icra, fill ve audit izi

Şunları kaybeder:

- Otomatik discovery ve şirket araştırması
- Yeni pitch/tez adayları
- Downside, valuation ve driver yorumlarının otomatik taslakları
- Yeni kanıtın tez üzerindeki nitel yorumu
- Araştırma önceliklendirmesi ve anlatısal açıklamalar

Zamanla mevcut capital input’lar bayatlar. Doğru davranış eski hükümleri sonsuza kadar kullanmak değil, onları `stale`/`insufficient` sayıp yeni risk alımını daraltmaktır. Böylece eklenti kapatıldığında sistemin **araştırma kapsaması azalır; muhasebe ve sermaye güvenliği bozulmaz**.

Kısacası: eklenti fonun içinde çalışan bir karar motoru değil, değiştirilebilir bir araştırma sağlayıcısıdır. Fon şemaları skill adlarını bilmemeli; skill ve model kimliği yalnız provenance’da görünmelidir.