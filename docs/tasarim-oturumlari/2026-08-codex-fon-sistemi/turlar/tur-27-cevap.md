En önemli tespit şu: katalogdaki `result_contract` değerleri bugün gerçek sözleşme değil, yalnızca etikettir. Kod bunları doğrulama için kullanmıyor. Üstelik mevcut JSON şemalarında “required” alanların çoğu `null` veya boş liste kabul ettiği için sözleşme görünürde sert, gerçekte yumuşak.

## 1. Mevcut şemaların kaderi

| Mevcut şema | Hüküm | Yeni karşılığı |
|---|---|---|
| `pei-tearsheet-extraction` | **Değişir** | `issuer_baseline_assessment.v1`: baseline yeterliliği, typed veri boşlukları ve yalnız `handoff_suggestions`; `next_route` lifecycle’ı değiştiremez. |
| `pei-earnings-preview-extraction` | **Değişir** | `pre_print_expectation_snapshot.v1`: freeze time, dönem, typed expectation bar, KPI’lar, falsifier’lar ve beklenen kanıt; `position_action` tamamen çıkar. |
| `pei-idea-screen-extraction` | **Değişir** | `screen_batch_assessment.v1`: batch/comparison-set kimliği, her input security için tam muhasebe, `unaccounted_for`, stage-relative hüküm; boş ticker atlanamaz, boş bucket varsayılamaz. |
| `pei-comps-extraction` | **Yerine yenisi gelir** | `valuation_anchor_candidate.v1`: yöntem, metrik/dönem, fiyat-as-of, peer kümesi ve gerekçesi, ima edilen beklenti, destek durumu, kanıt ve boşluklar. Üç nullable string artık yeterli değil. |
| `pei-pitch-extraction` | **Yerine yenisi gelir** | `pitch_decision_envelope.v1`: verdict, decision posture, analysis mode, önerilen ifade, adversarial bear case ve dört sürümlü nesne referansı: thesis draft, valuation anchor, exposure intent, monitoring-contract draft. |
| `pei-scenario-extraction` | **Mevcut hâli ölür** | Koşullu `scenario_overlay.v1`: `base_case_ref`, epistemik seviye, driver/range, breakpoint ve görüşü değiştirecek kanıt. `pm_action` ve `pm_action_threshold` V1’de yoktur. |
| `pei-initiating-coverage-extraction` | **V1 çekirdeğinden çıkar** | Yalnız insan onaylı escalation’da `initiation_escalation_result.v1`; otomatik route veya tez açma yetkisi yoktur. Target price ancak gerçekten destekleniyorsa taşınır. |
| `pei-promotion-evaluation-extraction` | **B→A terfi şeması olarak ölür** | Gerekirse `watch_condition_assessment.v1`: beklenen kanıt geldi mi sorusunu cevaplar; bucket’ı doğrudan değiştirmez. Yeni episode yeniden hüküm verir. |
| `pei-thesis-record` | **Kanonik kayıt olarak ölür** | Domain tarafında `thesis_definition.v1` + `monitoring_contract.v1`; tracker çıktısında `thesis_assessment_proposal.v1`. Evidence, assessment ve adjudication olayları ayrı kalır. |

Bir de listede olmayan kritik boşluk var: `earnings_deep_dive` için ne extraction şeması ne de `WORKFLOW_EXTRACTION` kaydı bulunuyor. Bugün sonuçta açık bir JSON bloğu yoksa yalnız `workflow` ve `work_item_id` kalabiliyor. Bunun yeni karşılığı `post_print_evidence_assessment.v1` olmalı:

- hangi kanıt yayımlandı;
- beklentiye karşı gerçekleşen;
- KPI ve guidance değişiklikleri;
- earnings-quality bulguları;
- kaynak/provenance;
- araştırma ve tez açısından çıkarımlar;
- eksik filing/transcript/estimate kanıtı.

Adında ve alanlarında `action` olmamalı. Deep-dive lead ise episode disposition’a kanıt sağlar; tracker support ise tez evidence’ı sağlar. Sermaye hükmü vermez.

Aynı nedenle sözleşme adları da değişmeli:

- `post_print_thesis_and_action_implications` → `post_print_evidence_and_research_implications`
- `scenario_ranges_and_pm_action_thresholds` → `scenario_overlay_and_breakpoints`
- `expectation_bar_and_triggers` → `pre_print_expectation_snapshot`
- `append_only_thesis_record` → `thesis_assessment_proposal`

## 2. Şema neyi, validator neyi doğrulamalı?

Üçlü ayrımına tamamen katılıyorum:

1. **JSON Schema söz dizimini ve yerel yapıyı doğrular.**
2. **Contract validator deterministik anlam/invariant kontrolü yapar.**
3. **İnsan analitik yargıyı değerlendirir.**

Şemaya ait olanlar:

- required alanlar;
- type, enum, format;
- `additionalProperties: false`;
- `minItems`, `minLength`, unique ID;
- koşullu zorunluluklar;
- referansların biçimi.

Dolayısıyla `kill_criteria: []` geçersiz olmalı. Falsifier’sız pitch, tez üretemez. Aynı şekilde `what_must_be_true`, `adversarial_bear_case` ve actionable pitch’in monitoring-contract referansı boş olamaz.

Fakat `minItems: 1` yalnız “bir şey yazılmış” olduğunu kanıtlar. Yazılan kriterin gerçekten falsifiable, kaynak metnine sadık ve yeterince somut olduğunu kanıtlamaz.

Validator’a ait olanlar:

- referans verilen artefakt/sürüm/hash gerçekten var mı;
- valuation anchor `supported` mı ve pack’in bilgi kesiminden sonra mı üretildi;
- bütün batch üyeleri muhasebeleştirildi mi;
- monitoring contract’taki rule kimlikleri benzersiz mi;
- gerekli provenance alanları dolu mu;
- çıktı work-item’ın subject’iyle aynı security’ye mi ait;
- long-only mandate’e karşı yasak ifade önerilmiş mi;
- scenario’nun `base_case_ref`i var mı;
- gerekli evidence boşlukları karar niteliğini düşürüyor mu.

Önemli incelik: `recommended_expression` şemada `short` değerini temsil edebilmelidir; validator bunu `forbidden_expression` diye reddetmelidir. Şemadan `short`u tamamen çıkarırsak modelin gerçekten short önerdiğini görünmez hâle getiririz ve ihlal sıradan parse hatasına dönüşür.

İnsana kalanlar:

- peer seçimi gerçekten ikna edici mi;
- tez kanıtın söylediğinden fazlasını mı iddia ediyor;
- falsifier teze sadık mı;
- valuation yöntemi bu şirket için doğru mu;
- override kabul edilebilir mi.

Ayrıca AGY’yi kanonik karar üreticisi yapmazdım. Tercihim, analizi yapan ana modelin aynı koşuda hem insan-okunur sonucu hem şemalı contract sidecar’ını üretmesi olurdu. AGY eski result’ların göçü veya kurtarma amaçlı extractor olarak kalabilir. İkinci, daha ucuz modelin prose’dan tez sözleşmesi icat etmesi kalıcı mimari olmamalı.

## 3. Model/effort politikası

Tablo skill adına göre değil, en azından `(workflow role, reliance class)` üzerinden seçilmeli. Aynı comps çağrısı embedded support iken başka, standalone valuation lead iken başka hata maliyetine sahiptir.

| İş | V1 varsayılanı | Yükseltme |
|---|---|---|
| Idea-generation Stage 1 | terra/medium | Stage 2 karşılaştırması terra/high |
| Company-tearsheet embedded support | terra/medium | Standalone problemli baseline terra/high |
| Comps embedded valuation anchor | terra/high | Standalone/çatışmalı valuation lead sol/high |
| Earnings preview dar snapshot | terra/high | Karmaşık accounting/event underwrite sol/high |
| Earnings deep-dive support | terra/high | Research-case lead veya çelişkili print sol/high |
| Pitch lead | sol/xhigh | Değişmez |
| Thesis mechanical check | **LLM yok** | — |
| Thesis tracker rutin semantic update | terra/high | `broken/changed/retired` önerisi veya çelişkili kanıt sol/high |
| Scenario overlay | terra/high | V1 dışı model-backed karar çalışması ayrıca değerlendirilir |
| Initiating coverage escalation | sol/xhigh | İnsan onayıyla açılır |

Dolayısıyla `thesis-tracker = luna/medium` yanlış genelleme. Luna, en fazla sunum/materialization veya düşük riskli özet için kullanılabilir; governance-state değişikliği öneremez.

`earnings-preview = sol/high` da dar V1 sözleşmesi için fazla ağır. Skill’in kurumsal tam preview varsayımı sol/high’ı açıklıyor; bizim `pre_print_expectation_snapshot` ürünümüz daha dar.

Comps’ta rol modeli etkilemeli. Fakat “lead ise otomatik pahalı” değil; reliance belirleyici olmalı:

- `screen_grade` → terra/high
- `decision_support` → sol/high
- V1’de comps’ın çoğu embedded `decision_support` olacaktır; pitch hâlâ nihai lead’dir.

## 4. “Başarılı çalışma” tanımı

Bugünkü “exit 0 + result.md var” yalnızca **attempt succeeded** demektir. Workflow’un tamamlandığını göstermez.

Doğru sıra:

1. **Process success:** model süreci çıktı verdi.
2. **Extraction success:** structured çıktı üretildi.
3. **Schema valid:** biçim ve yerel cardinality kuralları geçti.
4. **Contract valid:** validator invariant’ları, referansları, provenance’ı ve mandate uyumunu geçti.
5. **Human adjudicated:** yalnız tanımlı insan kapılarında.
6. **Lifecycle committed:** sonuç vakaya/teze domain etkisiyle işlendi.

`workflow_completed` ancak 4. aşamadan sonra yazılmalı. Anlamı da şu olmalı:

> “Bu çalışma ilan edilen sözleşmeyi yerine getiren, mühürlenmiş bir çıktı üretti.”

“Analiz doğrudur” veya “insan kabul etti” demek değildir.

`analysis_proposed` olayını genel olarak geri getirmeye gerek yok. Ara support adımlarında doğrulanmış `workflow_completed` yeterli. Pitch→tez kapısında domain’e özgü adjudication ve atomik `thesis_opened` kullanılır.

Validator çıktısı için önerim:

- Her koşuda hash’li, değişmez bir `validation_report` artefaktı üretilir.
- Başarılı doğrulama için ayrıca olay yazılmaz; `workflow_completed`, report referansını ve `contract_version`ı taşır.
- Geçersiz deneme `workflow_completed` üretmez; attempt store’da `contract_invalid` olarak kalır.
- Retry sınırı aşılır veya vaka ilerleyemezse ancak o zaman domain olayı doğar: örneğin `episode_blocked(reason=contract_invalid)` ya da P2 operatör işi.

Böylece denetim izi korunur ama defter her başarılı schema kontrolü için tören olaylarıyla şişmez. En kritik sözlük ayrımı da şu olur:

- `process_succeeded`
- `contract_validated`
- `human_adjudicated`
- `domain_committed`

Bunları tek `completed` kelimesine sıkıştırmak, bugünkü tasarımın çıktı tarafındaki temel kusurudur.