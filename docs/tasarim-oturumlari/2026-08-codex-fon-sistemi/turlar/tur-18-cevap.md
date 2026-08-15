## 1. Doğrusal zincir ile lead+support gerçekten çelişiyor mu?

Altyapı düzeyinde çelişmek zorunda değiller; mevcut hâlleriyle çelişiyorlar.

Event-driven orkestratör bir lead workflow’un ihtiyaç duyduğu support işleri sırayla çalıştırabilir. Fakat bu ancak zincir şu anlamdaysa meşrudur:

```text
pitch lead run
├─ tearsheet support
├─ comps support
├─ scenario support
└─ pitch hero artifact + kanonik hüküm
```

Bugünkü config ise her adımı eşit workflow kabul ediyor; her biri kendi `workflow_completed`, `allowed_next` ve route hükmüne sahip. Bunun üç zararı var:

- Destek skill’i, lead’in sahip olması gereken sonraki rota kararını verebiliyor.
- Companion/support artefaktı bağımsız lifecycle kapısına dönüşüyor.
- Bir şirketin ihtiyacına göre seçilecek support işleri herkese uygulanan sabit önkoşullar oluyor.

Dolayısıyla `tearsheet → comps → pitch` lead’in iç execution planıysa sorun yok; üç eşit lifecycle workflow’uysa eklentinin niyetini bozuyor.

Envanteri **lead+support modeline göre** yapmalıyız. Orkestratör kalır ama sabit zincir yerine event-driven görev grafiği yürütür.

Dört rol kullanmayı öneriyorum:

- **Lead workflow:** İlk gerçek araştırma hükmünü ve insanın açacağı hero artefaktı sahiplenir.
- **Embedded support:** Lead’in belirlediği dar bir workstream’i çözer; candidate/thesis lifecycle’ını doğrudan değiştirmez.
- **Lifecycle workflow:** Aynı aggregate üzerinde tekrar çalışır; örneğin thesis_id bazlı izleme.
- **Meta/router:** Lead seçer veya politika sağlar; analitik sonuç olayı üretmez.

Rol skill’e kalıcı yapıştırılmaz. `company-tearsheet` bağımsız tearsheet talebinde lead, pitch içinde support olabilir.

Bunun config sonucu da şudur:

- `required_workflows`, `hard_artifact_requirements` ile `support_policy` olarak ayrılmalı.
- `allowed_next`, kanonik lifecycle geçişi olmaktan çıkıp en fazla `handoff_suggestions` olmalı.
- Lead’in support planı çalışma anında context ve eksik kanıta göre belirlenmeli.
- Yalnız lead hero artefaktı ve kanonik araştırma hükmü üretmeli.
- Support çıktıları lead context’ine girer; ayrı insan onay kapısı oluşturmaz.

Mevcut config’te özellikle `pitch.required_workflows=["tearsheet"]` fazla katı: pitch’in ihtiyacı belirli bir skill completion’ı değil, güncel ve yeterli issuer baseline’ıdır. Bu baseline tearsheet, earnings deep dive, initiation veya doğrudan pack tarafından karşılanabilir.

## 2. 23 skill için kaba triyaj

Burada **ÇEKİRDEK**, “her çalıştırmada çağrılır” değil, “V1 dikey diliminin eksiksiz olması için bu capability bulunmalıdır” demektir.

### ÇEKİRDEK — 6

| Skill | Rol | V1’deki yeri |
|---|---|---|
| `public-equity-investing` | Meta/router | Lead seçimi, sahiplik sınırı ve support planı politikasını sağlar; `pack_step` veya domain `result_contract` almaz. |
| `idea-generation` | Lead | 87 isimlik kapsamlı batch’i araştırma önceliğine ayırır; scoped A/B/C/Reject ve sonraki araştırma ihtiyacını üretir. |
| `company-tearsheet` | Embedded support; gerektiğinde standalone lead | Kimlik, iş modeli, finansal baseline ve veri boşluklarını standardize eder; fakat her ticker için zorunlu bağımsız lifecycle adımı olmaz. |
| `long-short-pitch` | Lead | Long-only yapılandırmayla resmî, falsifiable araştırma görüşünü kurar; kabul edilen sonucu `thesis_opened` kapısına götüren tek workflow’dur. |
| `thesis-tracker` | Repeatable lifecycle lead | `thesis_id` bazında yeni kanıtı, bozulma koşullarını ve inceleme sonucunu tekrar tekrar değerlendirir. |
| `earnings-deep-dive` | Event-triggered lead | Kaçınılmaz çeyreklik sonuçları tez etkisine çevirir; çıktı yeni pitch değil, mevcut teze evidence/assessment olur. |

Çekirdekler arasında tek evrensel zincir yoktur:

```text
Keşif: idea-generation
Yeni görüş: long-short-pitch (+ gerektiği kadar support)
İzleme: thesis-tracker
Çeyreklik olay: earnings-deep-dive → thesis evidence
```

`company-tearsheet` bu akışların içinde tekrar kullanılabilen baseline support’tur.

### KOŞULLU — 11

| Skill | Koşul | Rol ve sınır |
|---|---|---|
| `catalyst-calendar` | Bir tez basit `next_events` listesini aşan birden fazla kesin/tahmini katalizör taşıyorsa | Pitch veya thesis-tracker altında catalyst support; sıradan earnings tarihleri için ayrı hero workflow çalıştırılmaz. |
| `comps-valuation` | Relative valuation, peer seçimi veya premium/discount tezin karar menteşesiyse ve güncel denominator’lar varsa | Pitch’e valuation support veya açıkça istenmiş bağımsız valuation lead’i; herkese zorunlu adım değil. |
| `dcf-model-builder` | Uzun dönem nakit akışı/değerleme tartışması tezin ana taşıyıcısıysa ve model kurmanın maliyeti haklıysa | Model/workbook lead’i veya pitch support; hızlı fikirlerde çalıştırılmaz. |
| `earnings-preview` | Açık tez veya yüksek öncelikli aday earnings’e yaklaşıyorsa ve pre-print hazırlık gerçekten sonraki araştırma kararını değiştirecekse | Ayrı event lead’i; evrendeki her isim için her çeyrek otomatik çalışmaz. |
| `economic-impact-report` | Politika, makro, emtia veya sektör şoku birden fazla izlenen şirketi/tezi aynı mekanizmayla etkiliyorsa | Çok-isimli lead araştırma; çıktısı ilgili tezlere evidence ve research queue olarak dağıtılır. |
| `equity-model-update` | Kullanıcının gerçekten kullandığı mevcut bir workbook/model varsa ve yeni actual/guidance ona işlenecekse | Workbook lead’i; model yoksa control pack veya hayalî model üretilmez. |
| `event-driven-analyzer` | Merger, spin, aktivizm, regülasyon, dava veya benzeri kontrol edici tarihli olay varsa | O olayın lead’i; genel şirket tezinin rutin adımı değildir. |
| `financials-normalizer` | Kaynak finansallar dağınık, çelişkili, farklı birim/dönemli veya disclosure değişimi yüzünden karşılaştırılamazsa | Embedded support; repo’nun mevcut PIT/XBRL çıktıları yeterliyse çağrılmaz. |
| `meeting-prep` | Gerçek bir management/IR, sell-side, expert veya internal PM toplantısı planlandıysa | Toplantı hero artefaktının lead’i; normal araştırma hattının adımı değildir. |
| `model-audit-tieout` | Bir model tez, valuation veya insan kararı için load-bearing kanıt hâline geldiyse | Model QA lead’i/support’u; model bulunmayan V1 akışında çalışmaz. |
| `scenario-sensitivity-generator` | Mevcut bir base case üzerinde breakpoint, nonlinear driver veya senaryo skew’u karar için gerçekten gerekliyse | Pitch/model/thesis support; base case üretmez ve standart zorunlu pitch adımı olmaz. |

### GEREKSİZ — 6

| Skill | Gerekçe |
|---|---|
| `initiating-coverage` | V1’de tearsheet + hedefli support + pitch ile karşılanan işi ağır bir kurumsal initiation paketine dönüştürüyor; mevcut katalogdan çıkarılmalı. |
| `memo-builder` | Tek operatörlü sistemde IC/client/formal circulation yok; pitch ve thesis artefaktları aynı araştırma bilgisini yeterince taşıyor. |
| `deck-report-qc` | V1’de dış dolaşım paketi yok; lead skill’in kendi kaynak ve render QA’sı yeterli, ayrı circulation workflow’u gereksiz. |
| `portfolio-risk-management` | Capital policy ve benchmark yok, hedging araçları da mandate dışında; implementation-ready sizing üretemez ve V1 araştırma sınırını aşar. |
| `three-statement-model-builder` | Sıfır tezli, 5–7 saatlik sistem için entegre formula-workbook üretimi ve bakımı orantısız; gerçek ihtiyaç çıkarsa V2’de yeniden değerlendirilir. |
| `user-context` | Repo’daki mandate/config/event ledger kanonik bağlamdır; plugin-local hafıza ikinci bir preference ve source otoritesi yaratır. |

## Mevcut sekiz workflow açısından ilk sonuç

- **Kalır ama rolü değişir:** `tearsheet`, `earnings_deep_dive`, `pitch`, `thesis_tracker`.
- **Koşullu capability olur:** `earnings_preview`, `comps`, `scenario`.
- **V1 kataloğundan çıkar:** `initiating_coverage`.
- **Kataloğa açıkça alınmalı:** `idea-generation`; bugün bridge’e özel, katalog dışı ayrıcalıklı yol olmamalı.
- **Meta olarak tanımlanmalı:** `public-equity-investing`; normal workflow veya candidate adımı değildir.

En önemli karar şu: Bundan sonraki envanter sorusu “Bu skill zincirde nereye gelir?” değil, şu olmalı:

> “Hangi lead kararını sahipleniyor; o karar için hangi support işleri hangi kanıt eksikliğinde çağrılıyor; yalnız lead’in hangi sonucu lifecycle’a yazılıyor?”

Bu çerçeve kabul edilirse sonraki turlarda `pack_step`, prerequisite, output contract, model/effort ve insan kapısını doğru seviyede tanımlayabiliriz.