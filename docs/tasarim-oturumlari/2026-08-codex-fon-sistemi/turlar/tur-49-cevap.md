Ana model şu olmalı:

```text
portfolio_risk_snapshot   immutable hesap artefaktı
        ↓
portfolio_proposal        immutable seçenek belgesi
        ↓
portfolio_decision        ayrı insan olayı
        ↓
execution_plan/tickets    immutable yetkilendirilmiş niyet
        ↓
broker observations/fills dış dünya gerçekleri
```

Hiçbir katman bir önceki belgeyi “status alanını değiştirerek” güncellememeli.

## 1. `portfolio-risk-snapshot.schema.json`

Beklediğin yapı doğru. Üç önemli ek ve iki sınır düzeltmesi yaparım:

- `data_quality` ve `proposal_gate` ayrıca bulunmalı.
- Reconciliation/position legitimacy açıkça taşınmalı.
- “Toplam downside” tek sayı olarak sunulmamalı; tekil downside toplamı ile tanımlı portföy senaryosu ayrılmalı.
- Hedef ağırlık, turnover ve işlem kararı risk snapshot’a ait değildir.
- “Kapasite neden kullanılmadı?” ancak deterministik engelse snapshot’a, fırsat maliyeti/insan tercihi ise proposal’a aittir.

### Üst düzey yapı

```text
schema_version
risk_snapshot_id
fund_id
as_of
calculated_at
calculation_status
provenance
portfolio_metrics
exposure_summaries
scenario_results
security_rows
limit_evaluations
assumption_evaluations
data_quality
proposal_gate
```

### Kimlik ve provenance

| Alan | Tip |
|---|---|
| `risk_snapshot_id` | UUIDv7 |
| `fund_id` | UUIDv7 |
| `as_of` | UtcInstant |
| `market_session_date` | MarketSessionDate |
| `calculated_at` | UtcInstant |
| `calculation_status` | `complete \| monitoring_only \| blocked` |
| `policy_ref` | Exact revision + version + digest |
| `portfolio_snapshot_ref` | Artifact ref + digest |
| `nav_snapshot_ref` | Artifact ref + digest |
| `market_snapshot_ref` | Artifact ref + digest |
| `research_capital_inputs_ref` | Readiness/downside/driver snapshot ref |
| `assumption_set_ref` | Artifact ref |
| `input_manifest_ref` | Manifest ID + digest |
| `producer` | Engine ID, version, code digest, config digest |

`monitoring_only` sonuç gösterilebilir ama proposal girdisi olamaz. Proposal yalnız `complete` snapshot kabul eder.

### Portföy ölçümleri

```text
nav
long_market_value
settled_cash
unsettled_cash
reserved_cash
operational_cash_floor
deployable_capital
cash_weight_bps_nav
invested_weight_bps_nav
active_position_count
unknown_position_count
disputed_position_count
unreconciled_position_count
current_drawdown_bps
active_drawdown_rung
active_drawdown_actions[]
max_single_name_gap_loss_bps_nav
standalone_downside_sum_bps_nav
```

`standalone_downside_sum_bps_nav` açıkça diagnostic olmalı. “Bütün şirketlerin bağımsız downside’ları aynı anda olur” varsayımı değildir.

Gerçek portföy stresleri ayrı taşınır:

```json
{
  "scenario_id": "driver.ai_capex_contraction",
  "scenario_type": "causal_driver",
  "loss_bps_nav": 1350,
  "affected_security_ids": [],
  "aggregation_method": "scenario_specific",
  "input_ref": {}
}
```

### Exposure özetleri

Ayrı diziler:

- `issuer_exposures`
- `sector_exposures`
- `causal_driver_exposures`
- `currency_exposures`
- `unclassified_exposures`

Her satırda mevcut ağırlık, policy modu, varsa limit, kalan kapasite ve katkı yapan security’ler bulunmalı.

### Security satırı

```text
security_id
issuer_id
listing_id
position_state
reconciliation_state
policy_legitimacy_state
current_quantity
market_value
current_weight_bps_nav
readiness_class
thesis_ref
downside_case_ref
gap_case_ref
driver_refs[]
eligibility
weight_capacity
data_quality
```

`eligibility` üç ayrı gerçeği taşımalı:

```json
{
  "policy_eligible": true,
  "underwritten_investable": true,
  "capital_actionable_now": false,
  "reason_codes": ["position.reconciliation_stale"]
}
```

`weight_capacity`:

```json
{
  "eligible_weight_band": {
    "minimum_bps_nav": 0,
    "maximum_bps_nav": 650
  },
  "policy_compliant_max_weight_bps_nav": 650,
  "current_additional_capacity_bps_nav": 125,
  "constraint_evaluations": [],
  "primary_binding_constraint_ids": []
}
```

### Binding constraint

Tek enum yetersiz; sıralı liste doğru.

Her constraint:

```json
{
  "constraint_id": "constraint:security:NVDA:downside",
  "constraint_type": "fundamental_downside_capacity",
  "constraint_instance_ref": "downside-case-id",
  "cap_weight_bps_nav": 650,
  "current_headroom_bps_nav": 125,
  "distance_from_tightest_cap_bps": 0,
  "rank": 1,
  "binding_state": "binding",
  "reason_codes": ["loss_budget.position_cap"],
  "input_refs": []
}
```

`constraint_type` kapalı enum:

```text
readiness_cap
fundamental_downside_capacity
gap_capacity
security_limit
issuer_limit
sector_limit
causal_driver_limit
cash_capacity
liquidity_capacity
position_count_capacity
policy_assumption_block
```

`binding_state`:

```text
binding
co_binding
near_binding
non_binding
blocked
not_applicable
```

Kurallar:

- En düşük cap `binding`dir.
- Aynı cap’i üretenler `co_binding`dir.
- `near_binding`, engine config’te kayıtlı açıklama toleransına göre belirlenir.
- Liste `cap_weight_bps_nav` artan sırada tutulur.
- `primary_binding_constraint_ids`, listeden türetilen kolaylık alanıdır; ayrı hüküm değildir.

`current_headroom` ile `distance_from_tightest_cap` karıştırılmamalı:

- Headroom: kendi cap’i − mevcut ağırlık.
- Distance: kendi cap’i − en sıkı cap.

### Limit değerlendirmesi

```json
{
  "limit_id": "policy.max_issuer_weight",
  "scope_type": "issuer",
  "scope_id": "issuer-id",
  "mode": "bounded",
  "metric": "weight_bps_nav",
  "comparator": "less_than_or_equal",
  "observed_value": "925",
  "limit_value": "1000",
  "remaining_capacity": "75",
  "status": "pass",
  "severity": "hard",
  "contributor_security_ids": [],
  "reason_codes": []
}
```

`status`:

```text
pass
near_limit
breach
blocked
monitor_only
not_applicable
```

`remaining_capacity` signed olabilmeli; breach durumunda negatif değer taşır.

### Policy assumption değerlendirmesi

```json
{
  "assumption_id": "assumption.liquidity.retail_scale",
  "assumption_ref": {},
  "predicate_id": "liquidity.position_to_adv_below_threshold",
  "evaluated_at": "2026-09-01T20:05:00Z",
  "status": "valid",
  "observed_value": "0.0008",
  "threshold_value": "0.001",
  "consequence_if_invalid": "block_new_risk",
  "evidence_refs": []
}
```

Durumlar:

```text
valid
invalid
indeterminate
expired
```

### Data quality ve proposal kapısı

```json
{
  "data_quality": {
    "blocking_findings": [],
    "warnings": [],
    "stale_input_refs": [],
    "unknown_cost_basis_count": 0,
    "unpriced_security_count": 0
  },
  "proposal_gate": {
    "status": "eligible",
    "reason_codes": []
  }
}
```

Proposal gate:

```text
eligible
monitoring_only
blocked
```

## 2. `portfolio-proposal.schema.json`

Proposal bir yaşam döngüsü kaydı değil, immutable seçenek belgesidir. İçine mutable `status` veya insan onayı yazılmaz.

### Üst düzey yapı

```text
schema_version
proposal_id
fund_id
generated_at
decision_as_of
market_session_date
proposal_kind
trigger
authority_context
provenance
proposal_outcome
options[]
validity_contract
decision_deadline
data_quality
```

### Kimlik ve provenance

```text
proposal_id
fund_id
risk_snapshot_ref
policy_ref
portfolio_snapshot_ref
research_comparison_ref
input_manifest_ref
producer
operating_authority_ref
```

`proposal_kind`:

```text
scheduled_review
event_driven
manual_review
replacement_review
risk_remediation
```

`proposal_outcome`:

```text
no_change
change_proposed
blocked
indeterminate
```

### Seçeneklerin yapısı

Bütün seçenekler aynı `portfolio_option` şemasını kullanmalı. Farklı tipler karşılaştırmayı zorlaştırır.

Kurallar:

- Tam olarak bir `status_quo`.
- `change_proposed` ise tam olarak bir `primary`.
- En fazla iki `alternative`.
- `no_change`, `blocked` veya `indeterminate` ise primary zorunlu değildir.
- Her seçenek bütün portföyü temsil eder; yalnız değişiklik parçalarını değil.

```json
{
  "option_id": "uuidv7",
  "role": "primary",
  "summary_reason_codes": [],
  "position_targets": [],
  "cash_target_band": {},
  "replacement_pairs": [],
  "portfolio_effects": {},
  "limit_evaluations": [],
  "implementation_preview": {}
}
```

`role`:

```text
status_quo
primary
alternative
```

Bir position target:

```json
{
  "security_id": "uuidv7",
  "current_weight_bps_nav": 525,
  "proposed_action": "add",
  "target_weight_band": {
    "minimum_bps_nav": 600,
    "preferred_bps_nav": 625,
    "maximum_bps_nav": 650
  },
  "eligible_weight_band_ref": {},
  "binding_constraint_ids": [],
  "reason_codes": []
}
```

Action sözlüğü:

```text
hold
initiate
add
trim
exit
```

`preferred_bps_nav` zorunlu olmak zorunda değildir. Sistem yalnız bandı savunabiliyor ama bandın içindeki optimumu savunamıyorsa açıkça atlanır; yapay kesinlik üretilmez.

### Portfolio effects

Her option için:

```text
resulting_cash_weight_bps_nav
deployable_cash_after
turnover_bps_nav
estimated_transaction_cost
standalone_downside_sum_bps_nav
scenario_results[]
max_single_name_gap_loss_bps_nav
position_count
issuer/sector/driver exposure summaries
hard_breach_count
warning_count
```

`status_quo` da bunların tamamını taşır. Böylece alternatifler aynı ölçüler üzerinden kıyaslanır.

### Replacement

```json
{
  "candidate_security_id": "new-id",
  "incumbent_security_id": "old-id",
  "replacement_hurdle_status": "cleared",
  "comparison_ref": {},
  "frozen_counterfactual_id": "uuidv7",
  "reason_codes": []
}
```

Durum:

```text
cleared
not_cleared
indeterminate
not_applicable
```

### Validity contract

```text
required_policy_revision/digest
required_risk_snapshot_id/digest
required_portfolio_snapshot_id/digest
required_authority_level
valid_until
maximum_market_sessions
price_bands[]
permitted_weight_bands[]
maximum_cash_impact
maximum_downside_bps_nav
required_reconciliation_state
invalidating_event_types[]
```

Geçersizleştiren olaylar en az:

```text
policy_superseded
authority_revoked
hard_limit_breach_detected
portfolio_snapshot_changed_materially
reconciliation_became_disputed
thesis_broken
corporate_action_recorded
market_price_outside_band
proposal_expired
```

## Proposal durum makinesi

Tek `status` yerine iki bağımsız projection ekseni gerekir.

### Karar ekseni

```text
pending_review
deferred
approved
reapproval_required
approval_revoked
rejected
cancelled
expired
superseded
```

Başlıca geçişler:

```text
pending_review → approved | rejected | deferred | cancelled | expired | superseded
deferred       → pending_review | cancelled | expired | superseded
approved       → reapproval_required | approval_revoked | expired | superseded
reapproval_required → approved | approval_revoked | expired | superseded
```

Yasaklar:

- `rejected → approved` yasak; yeni proposal gerekir.
- `expired/superseded → approved` yasak.
- `approved → rejected` yasak; `approval_revoked` kullanılır.
- Material input değişmişse aynı proposal reapproved edilemez; yeni proposal gerekir.
- Fill gelmesi proposal’ı geriye dönük approved yapamaz.

### İcra ekseni

```text
not_authorized
not_started
in_progress
completed_target_reached
closed_target_not_reached
not_applicable
```

Kısmi fill ama hâlâ çalışılan plan `in_progress`tır. Plan kapatıldığında hedefe ulaşılmamışsa `closed_target_not_reached` olur.

### İnsan kararı

Ayrı olay olmalı:

`portfolio_proposal_adjudicated`

Payload:

```text
decision_id
proposal_id
decision
selected_option_id
decided_at
decided_by_actor_id
accepted_target_bands[]
override_records[]
validity_contract_accepted
authority_grant_ref
reason_codes[]
```

`decision`:

```text
approve
reject
defer
```

İnsan proposal dışındaki bambaşka bir hedef seçerse bu basit approval değildir:

- Değişiklik mevcut option’ın önceden tanımlanmış bandı içindeyse onaylanabilir.
- Bandın dışındaysa yeni proposal veya açıkça doğrulanmış `accepted_with_override` kararı gerekir.
- Hard limit override edilemez.
- Proposal belgesi hiçbir durumda değiştirilmez.

Dolayısıyla evet: “onaylanmış proposal” bir projection’dır.

## 3. İcra nesneleri

Bunlar aynı nesnenin durumları değildir; farklı soruları cevaplarlar.

| Nesne | Sorduğu soru | Biçim |
|---|---|---|
| `execution_plan` | Seçilmiş portfolio option nasıl ve hangi sırayla uygulanacak? | Immutable artefakt |
| `trade_ticket` | Bu security’de hangi sınırlar içinde işlem yapmaya yetki var? | Immutable artefakt |
| `broker_order_observation` | Broker’a gerçekten hangi order girildiğini biliyor muyuz? | Opsiyonel gözlem olayı |
| `fill_recorded` | Gerçekte hangi adet, fiyat ve ücretle gerçekleşme oldu? | Kanonik ekonomik olay |

### Execution plan

```text
execution_plan_id
proposal_id
decision_id
selected_option_id
created_at
policy_ref
authority_ref
input_manifest_ref
ticket_refs[]
execution_sequence[]
cash_feasibility
validity_contract
```

Sequence örneği:

```json
[
  {
    "sequence": 1,
    "ticket_id": "sell-ticket",
    "must_complete_before": ["buy-ticket"]
  }
]
```

### Trade ticket

Trade ticket sıradan projection değildir. Proposal ve decision’dan deterministik türetilebilir ama operatöre gösterilmiş yetkili niyeti dondurduğu için immutable artefakt olarak saklanmalıdır.

```text
trade_ticket_id
execution_plan_id
proposal_id
decision_id
security_id
listing_id
action
side
approved_weight_band
quantity_derivation_rule
maximum_notional
price_band
cash_impact_limit
downside_limit
valid_from
valid_until
authority_ref
policy_ref
input_manifest_ref
```

Ticket sabit adet taşımak zorunda değildir:

```text
quantity = approved weight / execution-time NAV and price
```

Hesaplanan adet broker’a girildiği anda order gözlemine yazılabilir.

### Broker order observation

Broker API yoksa zorunlu değildir. Olmayan bir order nesnesi uydurulmamalı.

İnsan “order’ı girdim” bilgisini kaydederse:

```text
broker_order_observation_id
account_id
broker_order_id
trade_ticket_id
observed_at
order_status
side
requested_quantity
order_type
limit_price
time_in_force
source
```

Order status:

```text
submitted
partially_filled
filled
cancelled
rejected
expired
unknown
```

Aynı broker order için her durum değişimi yeni observation olabilir. Eski observation değiştirilmez.

İnsan order bilgisini hiç kaydetmezse doğrudan:

```text
trade_ticket → fill_recorded
```

bağlantısı kabul edilir. Fill’de ticket/order referansı bulunamazsa gerçek fill yine kaydedilir ama:

```text
plannedness: unplanned | unmatched
policy_legitimacy_state: unadjudicated
```

olur.

### Fill

```text
fill_id
account_id
broker_fill_id
broker_order_id
trade_ticket_id
security_id
listing_id
side
quantity
price
trade_currency
gross_consideration
fees[]
trade_date
occurred_at
settlement_date
source_artifact_ref
idempotency_key
plannedness
```

Fill `input_manifest_hash` taşımaz. Hesap sonucu değil, dış dünya gözlemidir. Kaynağı ve idempotency kimliği vardır.

Kısmi veya hiç gerçekleşmeyen ticket için ayrıca:

`trade_ticket_closed`

```text
trade_ticket_id
closed_at
outcome
filled_quantity
remaining_quantity
reason
```

Outcome:

```text
fully_filled
partially_filled_cancelled
not_submitted
cancelled
expired
broker_rejected
```

## 4. Input manifest ve hash zinciri

Evet, yapı hash zinciri üretir; fakat doğrusu doğrusal zincir değil, içerik-adresli bir bağımlılık DAG’ıdır.

### Kural

Her hesaplanmış artefakt yalnız doğrudan kullandığı immutable girdileri listeler.

Risk snapshot manifesti:

```text
policy revision
portfolio snapshot
NAV snapshot
market snapshot
research capital inputs
policy assumptions
```

Proposal manifesti:

```text
risk snapshot
review trigger
opportunity/comparison snapshot
operating authority
```

Proposal, risk snapshot’ın altındaki bütün price/position girdilerini tekrar düz listelemez. Bunlara risk snapshot manifesti üzerinden ulaşılır.

Execution plan manifesti:

```text
proposal
portfolio decision
current authority grant
```

Execution-time adet hesabı yapılırsa onun manifesti:

```text
trade ticket
güncel NAV
güncel fiyat
güncel nakit/reconciliation state
```

Fill ise hesap artefaktı olmadığı için input manifest kullanmaz.

### Manifest girdisi

```json
{
  "role": "risk_snapshot",
  "object_type": "portfolio_risk_snapshot",
  "object_id": "uuidv7",
  "schema_id": "fund:portfolio-risk-snapshot",
  "schema_version": "1.0.0",
  "artifact_digest": "sha256:...",
  "as_of": "2026-09-01T20:00:00Z",
  "known_at": "2026-09-01T20:01:00Z",
  "criticality": "required"
}
```

Manifest:

```text
manifest_id
schema_version
created_at
canonicalization_version
inputs[]
```

`inputs[]` deterministik olarak sıralanır; canonical JSON’a çevrilir ve hash’lenir.

### Engine neden ayrıca taşınır?

Aynı input’lar farklı engine sürümüyle farklı sonuç üretebilir. Bu nedenle gerçek determinizm anahtarı yalnız `input_manifest_hash` değildir:

```text
input_manifest_digest
producer.code_digest
producer.version
producer.config_digest
```

Birlikte:

```text
computation_context_digest
```

üretir.

Şu invariant doğrudur:

```text
aynı computation_context_digest
→ aynı kanonik output digest
```

Aksi bir sonuç determinism ihlalidir.

### Nerede hesaplanır?

Domain engine’in içinde değil, artefakt/orkestrasyon katmanında:

1. Doğrudan girdiler immutable ref ve digest’lere çözülür.
2. Manifest canonical biçimde sıralanır ve hash’lenir.
3. Engine yalnız manifestteki girdilerle çalıştırılır; gizli dosya/network okuması yasaktır.
4. Output contract doğrulanır.
5. Output artefakt hash’lenip saklanır.
6. Artefakt, manifest ve olay referansları tek commit kapısında bağlanır.

Transitif bütün girdileri içeren “closure manifest” denetim veya dışa aktarım için sonradan üretilebilir; kanonik manifest değildir.

## Karar özeti

- Risk snapshot hedef veya fırsat maliyeti kararı taşımaz; yalnız kapasite, risk ve engelleri taşır.
- Binding constraint tek enum değil, sıralı ve açıklanabilir evaluation listesidir.
- Proposal immutable seçenek belgesidir; yaşam döngüsü iki eksenli projection’dır.
- İnsan kararı ayrı olaydır; onay proposal içine yazılmaz.
- Execution plan ve trade ticket dondurulmuş yetkili niyettir; broker order observation opsiyonel, fill zorunlu ekonomik gerçektir.
- Hash yapısı doğrudan bağımlılıkları taşıyan DAG’dır; fill hesaplanmış artefakt olmadığı için input manifest taşımaz.