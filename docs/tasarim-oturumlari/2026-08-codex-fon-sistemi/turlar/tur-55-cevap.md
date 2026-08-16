Ana karar: `research_work_request` bir **kalıcı karar ihtiyacıdır**; kuyruk öğesi değildir. Kuyruk, açık taleplerin güncel fon durumu, deadline ve kapasiteyle yeniden sıralanmış projection’ıdır.

## 1. `research_work_request` sözleşmesi

Olay zarfı `event_id`, actor, subject, causation ve zamanları zaten taşır. Payload şu gruplardan oluşmalı:

```text
research_work_request_id: UUIDv7
request_schema_version
fund_id

requested_capability
required_output_contract: {name, version}

origin:
  origin_event_refs[]
  risk_snapshot_ref?
  proposal_ref?
  capital_input_manifest_ref?

decision_context:
  decision_type
  decision_ref?
  decision_to_inform
  blocked_or_at_risk_actions[]
  decision_deadline
  capital_at_risk:
    bps_nav
    amount?
    currency?
    as_of
    risk_snapshot_ref

research_question:
  primary_question
  current_uncertainty
  possible_capital_effects[]
  required_evidence[]
  stop_conditions[]

voi:
  admission_basis
  decision_impact
  decision_changeability
  estimated_effort
  gate_result
  rationale

work_equivalence_key
priority_basis_at_creation
```

Önemli hükümler:

- `requested_capability`, skill adı değil `downside_case.v1`, `valuation_anchor.v1`, `thesis_assessment.v1` gibi domain çıktısı ister.
- `admission_basis`: `policy_required` veya `voi_passed`.
- VOI için `decision_impact`, `decision_changeability`, `estimated_effort` ordinal kalır; tek yapay skor üretilmez.
- `decision_impact:none` veya `decision_changeability:none` ise, policy zorunluluğu yoksa request açılamaz.
- `possible_capital_effects` en az bir makul bulgunun hangi kararı değiştirebileceğini gösterir.
- `status`, güncel sıra, seçilen skill, attempt ve sonuçlar ilk request olayının içine yazılmaz.

Request’i deterministik `research_demand_planner` veya insan üretir. Skill yalnız kendi episode’u içinde `support_request_proposed` önerebilir; üst düzey fon araştırma ihtiyacı yaratamaz.

İlk olay `research_work_requested`dır. Sonraki routing, authorization, fulfillment ve cancellation ayrı olaylardır. Kuyruk bunlardan türetilir.

## 2. Research case ve episode bağlantısı

Request doğrudan case değildir:

```text
bir veya daha çok request
→ work container
→ episode
→ lead/support attempt’leri
→ artefaktlar
→ request fulfillment
```

Araştırma router’ı şu kararı verir:

- Tez öncesi security underwrite işi → mevcut açık `research_case`e bağlanır veya yenisi açılır.
- Açık tez güncellemesi → yeni research case açmaz; `thesis` altında bir review episode’u açar.
- Driver/portföy-geneli soru → kendi driver/portfolio research container’ına gider.

Teknik olarak ortak bir `work_episode` şeması kullanılabilir; `container_type` bunun `research_case`, `thesis` veya `risk_driver_case` olduğunu belirtir.

Fon şunu söyler:

> “Bu karar için `downside_case.v1` gerekiyor; soru bu, deadline bu, risk altındaki sermaye bu.”

Fon şunu söylemez:

> “Scenario skill’ini çalıştır.”

Lead seçimini araştırma orkestratörü; capability, mevcut artefaktlar, subject state’i, katalog sürümü ve support bütçesine göre yapar. Seçim `research_work_routed` olayıyla gerekçeli kaydedilir. İnsan route’u değiştirebilir ama fon motoru skill kimliği bilmez.

Fon bir cevap süresi garantisi almaz. Routing sonrasında kuyruk tahmini tamamlanma zamanı gösterebilir. Deadline’a yetişmeyecekse request `capacity_blocked` görünür; fon eksik-input kurallarıyla yoluna devam eder.

## 3. Dedup ve öncelik

Aynı security’ye ait olaylar otomatik olarak tek işe indirgenmez. Dedup iki seviyelidir:

1. **İdempotency:** Aynı origin event + capability + decision ref ikinci request’i doğuramaz.
2. **Semantik gruplama:** Farklı geçerli request’ler aynı episode tarafından cevaplanabiliyorsa birlikte yürütülür.

`work_equivalence_key` kabaca şunlardan türetilir:

```text
subject
+ required_output_contract
+ decision_scope
+ evidence_cycle_id
```

Örneğin haftalık sapma ile earnings olayı aynı yeni sonuç hakkında tez değerlendirmesi istiyorsa iki request korunur fakat tek deep-dive/tracker episode’una bağlanabilir. Driver yoğunlaşması farklı subject ve output contract taşıyorsa ayrı kalır. Bir episode birden fazla request’i tamamlayabilir; hangi artefaktın hangisini karşıladığı açıkça kaydedilir.

R0–R5 ile sermaye büyüklüğü aynı şey değildir:

- R sınıfı ilk leksikografik anahtardır.
- Deadline yakınlığı ikinci,
- risk altındaki sermaye üçüncü,
- changeability ve effort sonraki bağlayıcılardır.

Dolayısıyla bir iş hem `R2` hem `capital_at_risk:82bp` olabilir. Bu 82 bp, diğer R2 işleri arasında sırasını belirler; R1’i geçmesini sağlamaz.

Bir düzeltme: **R0 çoğunlukla araştırma işi değildir.** Sermaye gerçeği bilinmiyorsa çözüm skill değil reconciliation/importer’dır. R0 birleşik operatör kuyruğunda kalır; plugin araştırma kuyruğu normalde R1–R5’tir.

## 4. Kullanıcının gördüğü yüzey

Kuyruk kartı şuna benzer:

> **NVDA — downside_case güncellemesi**  
> R2 · 82 bp sermaye riski · karar son tarihi 5 gün  
> Neden: yeni earnings kanıtı + mevcut downside bayat  
> Bloklanan eylem: pozisyon artırımı  
> Tahmini efor: orta · önerilen route: deep-dive lead

Kullanıcı karta tıklayınca soruyu, kaynak olayları, mevcut capital input’ları, mümkün sermaye etkilerini, gerekli kanıtı, önerilen lead/support bütçesini ve maliyeti görür.

V0 sınırı:

1. Kullanıcı bir kez **“araştırmayı çalıştır”** diyerek execution’ı yetkilendirir.
2. Orkestratör pack hazırlama, lead çalıştırma, izinli support, retry ve contract validation’ı kendi yürütür.
3. Yalnız eksik maddi kanıt, bütçe aşımı, route belirsizliği veya provisional sonuç hazır olduğunda durur.
4. Kullanıcı yeniden ancak capital input adjudication’ında devreye girer.

Yani insan işi başlatır ve hükmü kabul eder; her teknik adımı elle sürmez. İleride düşük riskli rutin işler operating authority ile otomatik çalıştırılabilir, fakat capital input’a otomatik dönüşemez.

## 5. İptal ve değişen fon durumu

Fon “skill’i” değil, **karar ihtiyacını** iptal eder. Request silinmez; `research_work_cancelled` veya `research_work_superseded` olayı eklenir.

- Başlamadıysa episode açılmaz veya aktif talepten çıkarılır.
- Çalışıyorsa `cancellation_requested` olur; süreç durdurulamıyorsa sonuç tamamlanabilir ama `quarantined_late_result` sayılır.
- Quarantine sonucu yeni bir request ve adjudication olmadan capital input olamaz.
- Bir episode üç request’i karşılıyorsa yalnız biri iptal edildiğinde diğer ikisi nedeniyle çalışmaya devam eder.
- Pozisyon satıldıysa fonlanmış pozisyon kararına ait request kapanır; isim challenger olarak hâlâ değerliyse sessizce kapsam değiştirilmez, yeni request açılır.
- Tez `broken` olduğunda “pozisyonu artırmalı mıyım?” request’i iptal edilir; gerekiyorsa ayrı bir wind-down/re-underwrite request’i doğar.

Request, attempt başlamadan önce ve provisional sonuç adjudication’a sunulmadan önce güncel fon state’ine karşı yeniden doğrulanmalıdır. Böylece araştırma bir hafta sürerken sermaye sorusu ortadan kalkmışsa eski cevap yeni kararın içine sızamaz.