"Monolitik pack + geç budama" düzeltmeni kabul ediyorum -- `pop()` ile budamak, üretim maliyetini zaten ödemiş olmak demek. Yedi pack sözleşmesini (özellikle benim atladığım `pitch_decision.v1`'i), kanonik veri ürünü / pack sözleşmesi adlandırma ayrımını, zaman eksenlerinin bölüm bazında zorunlu olmasını, "hash veriyi doğrulamaz, modelin ne gördüğünü doğrular" ayrımını ve Tur 1 ince pack'inin altı sorusu + `insufficient_screen_evidence` güvenlik sınırını alıyorum.

Şimdi ÇIKTI TARAFINA geçiyoruz. Mevcut durumu çıkardım:

result_contract'lar (katalogda):
  tearsheet            -> profile_and_data_gaps_only
  earnings_preview     -> expectation_bar_and_triggers
  earnings_deep_dive   -> post_print_thesis_and_action_implications
  comps                -> valuation_assumptions_and_gates
  pitch                -> pitch_verdict_thesis_and_rules
  thesis_tracker       -> append_only_thesis_record
  scenario             -> scenario_ranges_and_pm_action_thresholds
  initiating_coverage  -> initiation_thesis_valuation_and_underwriting_status

Ve schemas/ altında sekiz çıkarım şeması var: pei-comps-extraction, pei-earnings-preview-extraction, pei-idea-screen-extraction, pei-initiating-coverage-extraction, pei-pitch-extraction, pei-promotion-evaluation-extraction, pei-scenario-extraction, pei-tearsheet-extraction, artı pei-thesis-record.

Dört sorum var:

(1) BU SEKİZ ŞEMA YENİ MODELDE NE OLUR? Bazıları doğrudan ölüyor gibi: initiating_coverage V1'de escalation oldu, scenario'nun "pm_action_thresholds"ı V1'de yasak (capital policy yok). Bazıları ise eksik: pitch artık dört ayrı nesneye referans veren bir zarf üretmeli. Sen bu sekizi tek tek gözden geçir ve her biri için söyle: kalır mı, değişir mi, ölür mü, ve yerine ne gelir. Özellikle `scenario_ranges_and_pm_action_thresholds` ve `post_print_thesis_and_action_implications` adlarındaki "action" kelimeleri beni rahatsız ediyor -- bunlar V1'de üretilmemesi gereken şeyi contract adına yazmışız.

(2) ÇIKARIMIN KENDİSİ NE KADAR GÜVENİLİR OLMALI? 2. turda agy'nin fail-open noktalarını konuşmuştuk (boş bucket -> "B", boş ticker sessizce atlanıyor, şemanın null'lara izin vermesi). Şimdi somut sor: bir çıkarım şeması ne zaman "geçerli ama boş" bir sonucu reddetmeli? Örneğin pitch çıkarımı `kill_criteria: []` döndürürse bu geçerli bir pitch mi? Ben hayır diyorum -- falsifier'ı olmayan tez, tez değil. Ama bu kuralı şemaya mı (required + minItems) yoksa doğrulama katmanına mı koymalı?

(3) MODEL/EFFORT TABLOSU HÂLÂ DOĞRU MU? Bugünkü SKILL_MODEL_CONFIG: idea-generation terra/high, tearsheet terra/medium, comps terra/high, pitch sol/xhigh, thesis-tracker luna/medium, earnings-deep-dive sol/high, earnings-preview sol/high, initiating-coverage sol/xhigh, scenario terra/high. Bu turlarda öğrendiklerimizle bakınca birkaç şey tuhaf duruyor: (a) thesis-tracker luna/medium -- ama artık tracker V1'in işletim döngüsünün merkezi ve tez durumu değişikliği öneriyor, bu ucuz modele bırakılacak bir iş mi? (b) earnings-preview sol/high -- ama sen preview'in çekirdek kısmını "dar bir beklenti snapshot'ı"na indirdin, o hâlâ sol/high mi gerektirir? (c) support rolündeki comps ile lead rolündeki comps aynı modeli mi kullanmalı, yoksa rol modeli etkilemeli mi? Tabloyu yeni role göre revize et.

(4) BİR ÇALIŞMANIN "BAŞARILI" SAYILMASI NE DEMEK? Bugün ölçüt basit: codex exit 0 ve bir result.md üretti. Ama bu turlarda çok daha sert kriterler koyduk (valuation_anchor zorunlu, monitoring taslağı zorunlu, `recommended_expression=short` kontrat ihlali, `unaccounted_for` ticker'lar batch'i kapatmıyor). Bu doğrulamaların tamamı nereye ait: çıkarım şemasına mı, ayrı bir "contract validator"a mı, yoksa adjudication ekranına mı? Ben ayrı bir validator katmanı olması gerektiğini düşünüyorum çünkü şema sözdizimini, validator anlamı, insan ise yargıyı kontrol eder -- üç ayrı şey. Katılıyor musun, ve validator'ın çıktısı bir olay mı olmalı?
