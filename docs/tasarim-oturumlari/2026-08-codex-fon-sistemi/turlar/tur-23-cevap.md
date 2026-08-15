Kısa hükmüm: pitch long-only olarak kısıtlanmalı ama ayı tezi zorunlu red-team olarak korunmalı; `red_team_only` verdict olmaktan çıkarılmalı; pitch sonucu tek zarf içinde ayrı, sürümlü nesnelere referans vermeli; support bütçesi model seçimine ek olarak sınırlandırılmalı; initiating-coverage ise V1’de otomatik yol olmaktan tamamen çıkarılmalı.

## 1. Long-short-pitch’in long-only kullanımı

Orta yol hem mümkün hem skill’in doğasına uygun. Skill zaten zayıf katalizörleri ve disconfirmers’ı pressure-test etmeyi istiyor [long-short-pitch](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/long-short-pitch/SKILL.md:40).

Pitch girdisi şu sınırları taşımalı:

```text
audience_mode: long_only_pm
permitted_expression: common_equity_long | no_position
prohibited_expressions: short | option | pair | leveraged
capital_action_authority: none
```

Buna karşılık analizde şu bölüm zorunlu kalmalı:

```text
adversarial_bear_case:
  strongest_bearish_interpretation
  downside_mechanism
  evidence_supporting_it
  evidence_that_would_refute_it
  implication_for_long_thesis
```

Yani model “short öneremez”, fakat “bu long fikrini en güçlü şekilde kim, neden reddeder?” sorusunu cevaplamak zorundadır. Bu skill’in modunu bozmaz; trade expression ile adversarial reasoning’i ayırır.

Kısıt yalnız prompt’ta kalmamalı. Çıktıda `recommended_expression=short/options/pair` görülürse kontrat ihlali olmalı; sonradan filtreleyip long’a çevirmek yasak. Çünkü filtreleme, short mantığının verdict’i kirletmesini görünmez kılar.

Bir ek sınır: V1 sermaye tahsis sistemi olmadığı için “actionable” burada “uzun tez açmaya aday” demektir; “pozisyon başlat” demek değildir.

## 2. Pitch verdict’i ile episode disposition eşlemesi

Önce bir düzeltme: `ready_for_pitch`, pitch episode’unun sonucu olamaz; pitch’ten önceki episode’un sonucudur. Pitch episode’u için ayrı terminal sözlük gerekir.

| Pitch sonucu | Episode sonucu |
|---|---|
| `actionable_candidate` | `thesis_opening_proposed`; insan kabul ederse vaka kapanır ve tez açılır |
| `watchlist` | Eksiksiz watch contract varsa `watch_until`; yoksa `blocked: watch_contract_incomplete` |
| `pass_for_now` | `decline_proposed`; insan onayıyla `declined` |
| `red_team_only` | Lifecycle hükmü üretmez; `analysis_only_completed` |

Skill sözleşmesine göre `watchlist`, katalizör/değerleme/kanıt bekleyen fikir; `pass_for_now`, risk-getiri veya kanıt barını geçmeyen fikirdir [output-contract.md](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/long-short-pitch/references/output-contract.md:57). Dolayısıyla `pass_for_now`’ı belirsiz watch’a çevirmemeliyiz. Somut olarak beklenen bir kanıt varsa doğru verdict zaten `watchlist` olmalıdır.

Beklenen kanıtı pitch lead yazmalı:

```text
question
accepted_evidence
expected_window
upgrade_condition
kill_condition
expiry
```

Yazmazsa insanın downstream’de boşluğu doldurması beklenmez; sonuç `blocked` olur.

Daha temel bir şema düzeltmesi de gerekiyor: `red_team_only` aslında verdict değil analiz modudur; skill de bunu “kullanıcı eleştiri istiyor, işlem önerisi değil” diye tanımlıyor. Dolayısıyla mevcut tek enum ikiye ayrılmalı:

```text
analysis_mode: decision | red_team
decision_posture: actionable_candidate | watchlist | pass_for_now | null
```

## 3. Pitch result contract

Senin ayrımına katılıyorum: tek dev JSON yerine bir hero artefakt ve ayrı sürümlü domain nesneleri olmalı. Fakat bunların tek pitch completion transaction’ında birbirine bağlanması gerekir.

```text
pitch_result:
  hero_artifact_ref
  pitch_decision_ref
  valuation_anchor_ref
  monitoring_contract_draft_ref
  thesis_scope_ref
```

Sahiplik şöyle kesilmeli:

- `pitch_decision`: verdict, tez taslağı, variant perception, what-must-be-true, falsifier’lar, katalizör ve kanıt hazır olma seviyesi.
- `valuation_anchor`: bağımsız ve sürümlü nesne; comps veya başka yöntem üretmiş olabilir. Pitch onu değiştirmez, seçer ve bu vaka için uygulanabilirliğini değerlendirir.
- `monitoring_contract_draft`: henüz tez olmadığı için tez nesnesine yazılamaz; research case’e bağlı taslaktır. İnsan tez açılışında adjudicate eder ve kanonik thesis monitoring contract’a dönüşür.
- `thesis_scope`: tezin iddia ettiği alfa mekanizması ve bilinen karıştırıcı maruziyetler.

Burada önceki kararımızı biraz daraltırım: `exposures_to_retain / must_not_hedge` gibi tam `exposure_intent` V1’de zorunlu olmamalı. Bunlar capital policy ve hedge kararına ait. V1’de yalnız `intended_alpha` ile `known_confounding_exposures` yeterlidir.

Çapraz doğrulamalar:

- `actionable_candidate` için desteklenmiş `valuation_anchor` zorunlu.
- `actionable_candidate` için adjudicate edilebilir monitoring taslağı zorunlu; izlenemeyen tez açılamaz.
- `watchlist` için eksiksiz watch contract zorunlu.
- Artefaktlardan biri eksikse pitch metni üretilmiş olabilir ama karar tamamlanmış sayılmaz.

## 4. Pitch support bütçesi

Model kademelendirmesi gerekli ama yeterli değil. Terra/high çağrılar ucuzlayabilir; sayıları sınırsızsa toplam maliyet ve döngü riski değişmez.

Her pitch episode’u tek bir yürütme zarfıyla yetkilendirilmeli:

```text
planned_inputs:
  issuer_baseline
  valuation_anchor

dynamic_support_policy:
  allowed_skills: [comps, earnings_deep_dive, scenario]
  max_automatic_supports: 1
  max_model_tier: terra/high
  recursive_support: false
  extension_requires_human: true
```

Burada önceden planlanmış zorunlu artefaktlar ile lead’in çalışma sırasında istediği dinamik support ayrılmalı. Örneğin vaka zaten comps’a ihtiyaç duyduğu için o artefakt baştan plana konmuşsa “dinamik support” sayılmaz.

İnsan her support çağrısını tek tek onaylamamalı. Episode hazırlanırken lead + planlı support zarfını bir kez görür; yalnız bütçe aşımı yeniden onaya gelir. Sol/xhigh bir support otomatik açılamaz. Initiating-coverage zaten support olarak hiç çağrılamaz.

V1’de varsayılan dinamik limit olarak bir support’u savunurum. İkinci support ihtiyacı çoğu zaman ya sorunun yeterince hedefli olmadığını ya da vakanın V1 sınırını aştığını gösterir.

## 5. Initiating-coverage koşulu

“Ancak başarısız pitch’ten sonra” kuralına tam katılmıyorum. Çünkü pitch şu nedenlerle başarısız olabilir:

- earnings kanıtı henüz gelmemiştir,
- valuation anchor eksiktir,
- veri bayattır,
- watch contract tamamlanmamıştır.

Bunların hiçbiri full initiating coverage gerektirmez. Başarısız her pitch’i initiation’a yükseltmek en pahalı fallback’i varsayılan hâle getirir.

Daha önemli hüküm şu: initiating-coverage V1’de otomatik olarak hiç çalışmamalı. Skill kendisini açıkça “model-backed full initiation” olarak tanımlıyor [initiating-coverage](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/initiating-coverage/SKILL.md:38), trade pitch’in yerine kullanılmamasını söylüyor [aynı dosya](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/initiating-coverage/SKILL.md:42). Workbook/model kümesini V1 dışında bıraktığımıza göre decision-grade initiation’ın zemini yok.

V1 sonucu:

```text
capability_gap:
  code: full_underwrite_required_outside_v1

episode_disposition:
  blocked
```

Idea-generation’ın initiation önerisi yalnız `capability_gap_proposed` olabilir; çalışma yetkisi değildir. Bugünkü üç prodüksiyon initiation koşusu bu nedenle yeni tasarıma göre yanlış yönlendirilmiştir. Çıktıları evidence olarak korunabilir ama “doğru tamamlanmış workflow” sayılmamalıdır.

Gelecekte initiation açılırsa başarısız pitch şartı aranmaz. Şu koşullar baştan mevcutsa doğrudan initiation gerçekten daha ucuz olabilir:

- Soru bir setup’ın pitch edilebilirliği değil, kalıcı coverage kurulmasıdır.
- Şirket-geneli forecast ve değerleme mimarisi zorunludur.
- Baseline + hedefli support soruyu yapısal olarak cevaplayamaz.
- İnsan model/report bakım yükünü açıkça kabul eder.

Ama bu V2/V3 meselesidir. Mevcut V1 kataloğunda initiating-coverage’ın doğru rolü “insan onaylı, ürün sınırı dışı escalation”dır; normal handoff veya pitch support’u değildir.