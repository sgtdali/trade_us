Not: “Çekirdek”, hedef mimarideki çekirdek adayı ifade eder; gölge koşuları geçmeden prodüksiyon yetkisi verildiği anlamına gelmez. Pack/çıktı adları hedef sözleşmelerdir, bugünkü kodun mevcut durumu değildir.

## 1. 23 skill’in tam envanteri

| Skill | V1 hükmü | Rol | Nerede kullanılır | Tetikleyici / koşul | Pack sözleşmesi | Çıktı sözleşmesi | İnsan kapısı |
|---|---|---|---|---|---|---|---|
| catalyst-calendar | Gereksiz | Yok | Tarih ve pencere yönetimi deterministik `next_events`/trigger katmanının sorumluluğudur. |  |  |  |  |
| company-tearsheet | Çekirdek | Support / lead | Ticker için kaynaklı issuer baseline ve veri boşlukları üretir. | Baseline yok, bayat veya maddi şirket değişikliği var | `issuer_baseline.v1` | `issuer_baseline_assessment.v1` | Hayır; provisional evidence |
| comps-valuation | Çekirdek | Support | Pitch’in kullanacağı savunulabilir valuation anchor’ı üretir. | Güncel/destekli valuation anchor yok | `valuation.v1` | `valuation_anchor.v1` | Hayır; hatalı/eksik peer seçimi kontratı bloklar |
| dcf-model-builder | Gereksiz | Yok | Workbook üretimi ve bakım yükü V1 kapasitesini aşar. |  |  |  |  |
| deck-report-qc | Gereksiz | Yok | Dış dolaşıma girecek deck veya rapor yoktur. |  |  |  |  |
| earnings-deep-dive | Çekirdek | Lead / support | Yeni sonuçların beklentiye, vakaya veya açık teze etkisini analiz eder. | `earnings_evidence_available`; yalnız tarih gelmesi yetmez | `event_evidence.v1` | `post_print_assessment.v1` | Hayır; domain etkisi tracker/pitch kapısında değerlendirilir |
| earnings-preview | Koşullu | Support | Sonuç öncesi beklenti barını, KPI’ları ve falsifier sorularını dondurur. | Doğrulanmış yaklaşan sonuç + açık tez veya öncelikli aktif vaka | `issuer_baseline.v1` + pre-event overlay | `expectation_snapshot.v1` | Hayır; çıktı değiştirilmeden mühürlenir |
| economic-impact-report | Gereksiz | Yok | Tema/makro subject modeli ve çok-ticker aktarım mekanizması V1’de yoktur. |  |  |  |  |
| equity-model-update | Gereksiz | Yok | V1 workbook tutmaz; güncellenecek kanonik model yoktur. |  |  |  |  |
| event-driven-analyzer | Gereksiz | Yok | Birleşme, düzenleyici olay ve özel durum expected-return hattı ürün sınırı dışındadır. |  |  |  |  |
| financials-normalizer | Gereksiz | Yok | Kanonik finansal normalizasyonu deterministik PIT/XBRL hattı yapar; LLM ikinci otorite olamaz. |  |  |  |  |
| idea-generation | Çekirdek | Lead | Evreni batch-relative araştırma önceliğine göre tarar; yatırım tavsiyesi üretmez. | Lifecycle dikey dilimi kanıtlandıktan sonra açılan discovery batch’i | `screen_batch.v1` | `screen_batch_result.v1` | Hayır; sonuç kalıcı dışlama veya tez yaratamaz |
| initiating-coverage | Escalation | Lead | Baseline, hedefli support ve pitch’in çözemediği şirket-geneli underwriting boşluğunu araştırır. | Başarısız/blocked pitch + açık capability gap + insan onayı | Escalation açılırken özel olarak sabitlenir | `initiation_report.v1`; doğrudan tez açmaz | Evet; çalıştırılmadan önce |
| long-short-pitch | Çekirdek | Lead | Long-only karar modunda resmî görüş adayını, bear case’i ve falsifier’ları üretir. | Vaka pitch’e hazır ve gerekli kanıt yetenekleri mevcut | `pitch_decision.v1` | `pitch_decision_envelope.v1` + sürümlü nesne referansları | Evet; tez açılmadan önce |
| meeting-prep | Gereksiz | Yok | Yönetim/analist toplantısı veya diligence-call iş akışı yoktur. |  |  |  |  |
| memo-builder | Koşullu | Support | Dönem-sonu sentezi veya insan-okunur araştırma özeti üretir; lifecycle yönetmez. | Kullanıcı açıkça dönem-sonu memo ister | `dashboard_payload` / presentation payload | `period_end_memo.v1` | Hayır; yalnız sunum artefaktı |
| model-audit-tieout | Gereksiz | Yok | V1’de workbook olmadığı için audit/tie-out nesnesi de yoktur. |  |  |  |  |
| portfolio-risk-management | Gereksiz | Yok | Capital policy ve benchmark yoktur; skill ayrıca portföy-geneli allocator değildir. |  |  |  |  |
| public-equity-investing | Meta | Meta | Ortak kaynak, invocation ve support-routing standartlarını sağlar; doğrudan çalıştırılmaz. | Her plugin-backed koşunun policy dependency’si | `contract_manifest` içinde politika referansları | Yok | Hayır |
| scenario-sensitivity-generator | Koşullu | Support | Var olan base case üzerine diagnostic scenario overlay üretir. | Sürümlemeli `base_case_ref` var ve pitch belirsizliği gerçekten senaryo istiyor | `valuation.v1`; `base_case_ref` zorunlu | `scenario_overlay.v1`; PM action threshold yasak | Hayır |
| thesis-tracker | Çekirdek | Lifecycle | Mevcut tezi yeni kanıt karşısında tekrar değerlendirir; yeni tez açamaz. | Kanıt/sapma, `review_due_at` veya insan talebi | `thesis_update.v1` | `thesis_assessment.v1` | Governance-state değişikliği veya kapanış önerisinde evet |
| three-statement-model-builder | Gereksiz | Yok | Workbook kurma ve sürekli bakım yükü V1’in zaman bütçesine uymaz. |  |  |  |  |
| user-context | Gereksiz | Yok | Kanonik bağlam repo’daki mandate/config’dir; skill de ordinary workflow’larda kullanılmamasını söyler. |  |  |  |  |

## 2. Kademeli devreye alma

### A. 26 Ağustos köprüsü ve hemen sonrası

- **earnings-deep-dive:** Birincil sonuç kanıtı geldikten sonra CRM/NVDA için elle çalıştırılır; çıktı karantinada tutulur, domain’e commit edilmez.
- **company-tearsheet:** Yalnız post-print karşılaştırmasını engelleyen issuer-baseline boşluğu varsa support olarak kullanılır.
- **earnings-preview:** Yeniden çalıştırılmaz; mevcut CRM/NVDA çıktıları mühürlenmiş beklenti artefaktı olarak okunur.
- **public-equity-investing:** Yalnız runtime policy dependency’sidir; executable workflow değildir.

Bu kademede pitch, tracker, discovery, scenario ve initiation açılmaz.

### B. Gölge koşu ve ölçüm dönemi

- **long-short-pitch:** Üç farklı vakada deftere yazmadan sınanır; karar kalitesi ve düzeltme yükü ölçülür.
- **thesis-tracker:** Örnek/gölge tezler ve tarihsel filing’ler üzerinde false-positive, false-negative ve insan süresi ölçülür.
- **comps-valuation:** Pitch’in gerçekten valuation desteğine ihtiyaç duyduğu vakalarda tek support olarak sınanır.
- **company-tearsheet:** Issuer baseline’ın pitch ve deep-dive’a yetip yetmediği ölçülür.
- **earnings-deep-dive:** Gerçek sonuç döngülerinde `post_print_assessment` kalitesi ölçülür.
- **earnings-preview:** Bir sonraki doğrulanmış sonuç öncesinde, gerçekten sonradan sınanabilir beklenti üretip üretmediği test edilir.

### C. Yalnız ölçüm sonrasında

- **idea-generation:** Pitch–tez–tracker dikey dilimi çalışmadan yeni vaka hacmi yaratmamak için discovery daha sonra açılır.
- **scenario-sensitivity-generator:** Base-case şartı ve gerçek ek karar değeri kanıtlanırsa support olur.
- **initiating-coverage:** Yalnız tekrarlanan, belgelenmiş capability gap görülürse insan onaylı katalog-dışı escalation olarak açılır.
- **memo-builder:** Operatörün dönem-sonu sentez ihtiyacı fiilen ortaya çıkarsa eklenir.

Gereksiz sınıfındaki skill’ler “sonraki kademe” değildir; ürün sınırı değişmedikçe açılmaz.

## 3. Skill ilişkilerinin üç kuralı

- **Support politikası:** Lead yalnız dar ve bütçeli bir support ihtiyacı önerir; çağrıyı orkestratör yürütür, support lead’i değiştiremez veya vakayı kapatamaz.
- **Artefakt bağımlılığı:** Bir çalışma belirli bir skill’in tamamlanmasına değil, tazelik ve provenance taşıyan sürümlü bir kanıt yeteneğine bağımlıdır.
- **Dispatch:** Domain olayı, subject ve mevcut state uygun lead’i seçtirir; workflow çıktısı doğrudan başka workflow çağırmaz ve `allowed_next` kullanılmaz.

## 4. Dokümanda değişmesi gereken kararlar

- **“V1 hedef mimaridir” → “Hedef mimari henüz hak edilmemiştir”:** Önce mevcut hat güvenli araştırma tezgâhına çevrilir, üç gölge vaka ile dikey dilim kanıtlanır.
- **Dokuz adımlı platform inşası → altı güvenlik yaması + ölçüm:** 9–12 haftalık platform çalışması başarı kanıtına kadar ertelenir.
- **Keşif önce → olay/kanıt hattı önce:** Filing ve earnings döngüsü işletim hattıdır; discovery ancak lifecycle kapasitesi kanıtlanınca açılır.
- **Tam tur/iki aşamalı kapanış motoru → kayan batch:** Sabit round kapanışı, waived dilim ve deadlock semantiği V1 dışıdır.
- **Doğrusal workflow zinciri → research case içinde lead+support:** Lead amacı sabittir; support yalnız kanıt üretir.
- **`required_workflows` → `hard_artifact_requirements` + `support_policy`:** Bağımlılık skill adına değil gereken kanıt yeteneğine yazılır.
- **`allowed_next` → tamamen silinir:** Support, artefakt akışı ve event dispatch üç ayrı mekanizma olur.
- **Lead support’u çalıştırır → lead yalnız ihtiyaç bildirir:** Orkestratör bütçeyi doğrular, ayrı attempt açar ve lead’i yeni attempt’te yeniden çalıştırır.
- **`initiating_coverage` normal katalog workflow’u → katalog-dışı escalation:** Ancak blocked pitch ve insan onayı sonrasında kullanılabilir.
- **`thesis_tracker` terminal candidate adımı → `thesis_id` anahtarlı tekrarlayan lifecycle işi:** Yeni tez açamaz; yalnız assessment üretir.
- **`scenario` PM action threshold üretir → diagnostic overlay:** `base_case_ref` olmadan çalışamaz ve dayandığı kanıtın epistemik seviyesini yükseltemez.
- **`financials-normalizer` support olabilir → V1’de gereksiz:** Finansal normalizasyonun otoritesi deterministik PIT/XBRL hattıdır.
- **Workbook skill’leri koşullu → V1 dışı:** DCF, üç-tablo, model-update ve audit bakım yükü nedeniyle kapalıdır.
- **AGY kanonik hüküm çıkarır → ana çalışma şemalı sidecar üretir:** AGY yardımcı doğrulama olabilir; karar otoritesi değildir.
- **`pack_step` prompt varyantıdır → pack gerçek veri sözleşmesidir:** Bununla birlikte yedi genel pack ailesi hemen kurulmaz; önce karar-kritik üç pack sınanır.
- **Plugin routing domain mimarisidir → provider davranışıdır:** Plugin değiştirilebilir sağlayıcıdır; enum ve routing dili domain şemasına kopyalanmaz.
- **Her adımda hero HTML → `internal_analysis`:** Skill HTML’i yasaklanır; insan yüzeyi orkestratörün ayrı statik karar görünümüdür.

## 5. Kullanıcının cevaplaması gereken yeni sorular

1. **Üç gölge koşunun geçme eşiği nedir?**  
   Kabul edilebilir insan düzeltme süresi, kontrat eksikliği ve hüküm tutarsızlığı sınırı belirlenmezse “başarılı pilot” sonradan keyfî yorumlanır.

2. **Ölçüm dönemi ne zaman sona erer?**  
   Sabit tarih mi, iki gerçek earnings döngüsü mü kullanılacağı platform kararının ne kadar kanıta dayanacağını belirler.

3. **Ölçüm sırasında yeni aday alımı tamamen dursun mu?**  
   Tam duruş işletim yükünü temiz ölçer; küçük manuel giriş ise sistemin gerçek kullanım baskısı altında sınanmasını sağlar.