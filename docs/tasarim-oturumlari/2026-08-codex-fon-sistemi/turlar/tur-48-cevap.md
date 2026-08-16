Temel karar: yarın doldurulacak paket tek bir dev JSON değil, iki insan kararı ve iki işletim sözleşmesidir:

1. `fund_definition`: Hangi hesapların fon olduğu ve raporlama para birimi.
2. `capital_policy`: O fon üzerinde hangi sermaye kararlarının meşru olduğu.
3. `policy_validation_spec`: Policy motorunun geçmesi gereken sınamalar.
4. `operating_authority`: Geçmiş doğrulamaya dayanarak sistemin hangi yetki seviyesinde çalışacağı.

Açılış tarihi policy değildir; `opening_account_state_asserted` olayına aittir. Bu sınırı şimdi korumazsak policy kısa sürede state çöplüğüne dönüşür.

## 1. `capital-policy.schema.json`

### Ortak tip ve yokluk kuralları

`null` hiçbir yerde politika hükmü sayılmamalı. Sayısal limitler şu ayrık biçimi kullanmalı:

```json
{"mode": "bounded", "value_bps": 1000}
{"mode": "unbounded_by_policy"}
{"mode": "disabled"}
{"mode": "not_applicable"}
{"mode": "monitor_only"}
```

Anlamları farklıdır:

- `unbounded_by_policy`: Kavram uygulanıyor ama policy sınır koymuyor.
- `disabled`: Mekanizma bilinçli olarak kapalı.
- `not_applicable`: Kavram bu mandate’e uygulanamaz.
- `monitor_only`: Ölçülür ve gösterilir, ihlal üretmez.
- `required_from_user`: Yalnız `document_state: draft` iken kullanılabilen authoring işareti; etkin policy’de yasaktır.

Temel primitive’ler:

| Tip | Temsil |
|---|---|
| Kimlik | UUIDv7 |
| Ağırlık/oran eşiği | Tamsayı bp; `100 = %1`, `10000 = %100` |
| Çarpan/kur/oran | `decimalString` |
| Para | `{amount: decimalString, currency: ISO-4217}` |
| Takvim günü | `LocalDate` |
| Kesin zaman | `UtcInstant` |
| Sürüm | SemVer |
| İçerik referansı | UUIDv7 + `sha256:` digest |

Policy kendi digest’ini içinde taşımamalı; kendini hash’leyen belge paradoksu doğar. Digest, artifact manifestinde ve aktivasyon olayında tutulur.

### Kimlik ve yürürlük

| Alan | Tip | Aktivasyonda zorunlu | Açık hüküm |
|---|---|---:|---|
| `schema_version` | SemVer | Evet | Yok |
| `policy_series_id` | UUIDv7 | Evet | Yok |
| `policy_revision_id` | UUIDv7 | Evet | Yok |
| `policy_version` | SemVer | Evet | Yok |
| `fund_definition_ref` | Sürümlü artifact ref | Evet | Draft’ta `required_from_user` |
| `document_state` | `draft \| ratified` | Evet | Yok |
| `created_at` | UtcInstant | Evet | Yok |
| `created_by_actor_id` | UUIDv7 | Evet | Yok |
| `intended_effective_from` | UtcInstant | Evet | Yok |
| `supersedes_revision_id` | UUIDv7 veya hüküm | Evet | İlk policy’de `not_applicable` |

`intended_effective_from`, policy’yi kendiliğinden etkinleştirmez. Gerçek yürürlük `capital_policy_activated` olayının `effective_from` alanıyla başlar.

### Amaç ve ufuk

| Alan | Tip | Zorunlu | Değerler |
|---|---|---:|---|
| `objective.type` | enum | Evet | `absolute_return` |
| `objective.underwriting_horizon_months` | `{minimum, maximum}` integer | Evet | Örn. `3–18` |
| `objective.capital_horizon` | ayrık nesne | Evet | `open_ended \| date_bounded \| required_from_user` |
| `objective.liquidity_need_mode` | enum | Evet | `none_foreseen \| commitments_recorded_separately \| required_from_user` |
| `objective.portfolio_review_cadence` | enum | Evet | `monthly` |
| `objective.research_monitoring_cadence` | enum | Evet | `weekly` |
| `objective.change_required_at_review` | boolean | Evet | `false` |

Gerçek planlı para çekimleri policy’ye yazılmaz; `capital_commitment` state’inde yaşar. Policy yalnız bunların deployable capital’dan düşülmesini emreder.

### Uygun yatırım

| Alan | Tip | Zorunlu | Değer |
|---|---|---:|---|
| `eligibility.direction` | enum | Evet | `long_only` |
| `eligibility.security_types` | kapalı enum listesi | Evet | `us_listed_common_equity` |
| `eligibility.listing_countries` | ISO ülke listesi | Evet | `US` |
| `eligibility.shorting` | feature mode | Evet | `disabled` |
| `eligibility.leverage` | feature mode | Evet | `disabled` |
| `eligibility.derivatives` | feature mode | Evet | `disabled` |

### Nakit

| Alan | Tip | Zorunlu | Değer |
|---|---|---:|---|
| `cash.full_investment_required` | boolean | Evet | `false` |
| `cash.role` | enum | Evet | `legitimate_residual` |
| `cash.operational_floor.rule` | enum | Evet | `max_of_relative_and_absolute` |
| `cash.operational_floor.relative_bps_nav` | bp integer | Evet | Provisional `200` |
| `cash.operational_floor.absolute` | MoneyLimit | Evet | Başlangıçta `disabled` olabilir |
| `cash.target` | BpLimit | Evet | `disabled` |
| `cash.ceiling` | BpLimit | Evet | `unbounded_by_policy` |
| `cash.commitment_treatment` | enum | Evet | `deduct_before_deployable_capital` |

### Kapasite

| Alan | Tip | Zorunlu | Değer |
|---|---|---:|---|
| `capacity.max_active_positions` | pozitif integer | Evet | Provisional `10` |
| `capacity.minimum_active_positions` | IntegerLimit | Evet | `disabled` |
| `capacity.position_count_enforcement` | enum | Evet | `hard_max_only` |

### Yoğunlaşma

| Alan | Tip | Zorunlu | Değer |
|---|---|---:|---|
| `concentration.max_security_weight` | BpLimit | Evet | Kullanıcı kararı |
| `concentration.max_issuer_weight` | BpLimit | Evet | Kullanıcı kararı |
| `concentration.related_issuer_aggregation` | enum | Evet | `enabled` |
| `concentration.sector_weight_limit` | BpLimit | Evet | V0’da `monitor_only` veya kullanıcı tavanı |
| `concentration.causal_driver_limit` | BpLimit | Evet | V0’da `monitor_only` |
| `concentration.unknown_driver_treatment` | enum | Evet | `review_required` |

Security ve issuer tavanı aynı şey değildir: GOOG ve GOOGL ayrı security, aynı issuer’dır.

### Boyutlandırma

| Alan | Tip | Zorunlu |
|---|---|---:|
| `sizing.base_weight_formula` | Kapalı enum | Evet |
| `sizing.readiness_multipliers` | Sabit anahtarlı nesne | Evet |
| `sizing.min_economic_position` | BpLimit | Evet |
| `sizing.unknown_downside_treatment` | enum | Evet |
| `sizing.binding_rule` | enum | Evet |

`readiness_multipliers` serbest anahtarlı map olmamalı. Kapalı sözlüğü olan sabit nesne olmalı:

```json
{
  "watchlist": {"status": "enabled", "multiplier": "0"},
  "starter": {"status": "enabled", "multiplier": "0.5"},
  "core": {"status": "enabled", "multiplier": "1"},
  "exceptional": {"status": "disabled"}
}
```

Böylece yanlış yazılmış `startr` gibi bir anahtar sessizce kabul edilmez.

`base_weight_formula`:

```text
deployable_capital_fraction / max_active_positions
```

`binding_rule`:

```text
minimum_of_all_hard_capacities
```

### Kayıp ve risk bütçesi

| Alan | Tip | Zorunlu |
|---|---|---:|
| `risk.position_scenario_loss_budget_bps_nav` | bp integer | Evet |
| `risk.loss_budget_applies_to` | enum listesi | Evet |
| `risk.downside_case_requirement` | enum | Evet |
| `risk.unknown_downside_treatment` | enum | Evet |
| `risk.portfolio_stress_limit` | BpLimit | Evet |
| `risk.drawdown_response_ladder` | sıralı rung listesi | Evet |
| `risk.automatic_liquidation` | feature mode | Evet |

Kayıp bütçesini readiness sınıfına göre değiştirmem. Tek bir policy bütçesi kullanırım. Readiness zaten ağırlığı `0 / 0.5 / 1` ile küçültüyor; ayrıca starter’a farklı loss budget vermek aynı yargıyı iki kez saymak olur.

`loss_budget_applies_to` en az:

```json
["fundamental_downside", "single_name_gap"]
```

Motor en kötü kabul edilmiş senaryoyu kullanır.

Drawdown listesi sıradan bir array değil, şu invariant’ları taşıyan merdivendir:

- Eşikler pozitif kayıp büyüklüğü olarak ve kesin artan sırada yazılır.
- Bir rungkaki eylemler önceki rungların eylemlerine eklenir.
- Hiçbir rung otomatik satış emri üretmez.

Örnek:

```json
[
  {
    "drawdown_bps_from_peak": 1000,
    "actions_added": ["warning_and_review"]
  },
  {
    "drawdown_bps_from_peak": 1500,
    "actions_added": ["freeze_net_new_risk"]
  },
  {
    "drawdown_bps_from_peak": 2000,
    "actions_added": [
      "freeze_non_risk_reducing_proposals",
      "full_portfolio_reunderwrite"
    ]
  }
]
```

### İşlem ve histerezis

| Alan | Tip | Zorunlu |
|---|---|---:|
| `trading.no_trade_band.formula` | enum | Evet |
| `trading.no_trade_band.absolute_weight_delta_bps` | bp integer | Evet |
| `trading.no_trade_band.relative_target_weight_bps` | bp integer | Evet |
| `trading.minimum_economic_trade` | BpLimit veya MoneyLimit | Evet |
| `trading.band_bypass_reasons` | kapalı enum listesi | Evet |
| `trading.price_tolerance.increase_risk_bps` | bp integer | Evet |
| `trading.price_tolerance.reduce_risk` | BpLimit | Evet |
| `trading.proposal_max_age_market_sessions` | integer | Evet |
| `trading.execution_quantity_basis` | enum | Evet |
| `trading.manual_execution_required` | boolean | Evet |

No-trade bandı:

```json
{
  "formula": "max_absolute_relative",
  "absolute_weight_delta_bps": 100,
  "relative_target_weight_bps": 2000
}
```

Buradaki `2000`, hedef ağırlığın `%20`si demektir; NAV’ın %20’si değildir.

Bandı geçersiz kılabilecek kapalı sözlük:

```json
[
  "thesis_broken",
  "hard_limit_breach",
  "reconciliation_repair",
  "authority_reduction",
  "position_legitimacy_failure"
]
```

### Ölçüm sözleşmesi

| Alan | Tip | Zorunlu |
|---|---|---:|
| `measurement.base_currency_source` | enum | Evet |
| `measurement.nav_cut` | enum | Evet |
| `measurement.market_calendar` | enum/katalog kimliği | Evet |
| `measurement.price_basis` | enum | Evet |
| `measurement.fx_conversion_required` | boolean | Evet |
| `measurement.primary_return_method` | enum | Evet |
| `measurement.owner_outcome_method` | enum | Evet |
| `measurement.benchmark_mode` | enum | Evet |
| `measurement.hurdle_mode` | enum | Evet |
| `measurement.missing_input_behavior` | enum | Evet |

`base_currency` burada tekrar edilmez; `fund_definition`dan gelir.

Önerilen başlangıç:

- `nav_cut: us_official_market_close`
- `primary_return_method: twr`
- `owner_outcome_method: xirr`
- `benchmark_mode: disabled`
- `hurdle_mode: disabled`
- `missing_input_behavior: fail_closed`

### Değişiklik ve override

| Alan | Tip | Zorunlu |
|---|---|---:|
| `governance.owner_actor_id` | UUIDv7 | Evet |
| `governance.scheduled_review_cadence` | enum | Evet |
| `governance.tightening_cooling_off_days` | integer | Evet |
| `governance.loosening_cooling_off_days` | integer | Evet |
| `governance.emergency_override_max_days` | integer | Evet |
| `governance.retroactive_changes` | feature mode | Evet |
| `governance.loosen_to_cure_existing_breach` | feature mode | Evet |
| `governance.human_activation_required` | boolean | Evet |
| `governance.validation_report_required` | boolean | Evet |
| `assumption_refs` | artifact ref listesi | Evet |
| `calibration` | provisional alan listesi | Evet |
| `unresolved_decisions` | draft-only liste | Draft’ta |

## 2. Doldurulmuş draft örneği

Aşağıdaki örnekte `required_from_user` nesneleri yalnız draft authoring tipidir. Policy ratify/activate edilmeden önce gerçek tipe dönüşmeleri zorunludur.

Önce küçük `fund_definition`:

```json
{
  "$schema": "fund:schemas/fund/fund-definition.schema.json",
  "schema_version": "1.0.0",
  "fund_id": "01991f3a-7b2c-7a11-8c44-4b90ab513001",
  "fund_definition_revision_id": "01991f3a-7b2c-7a12-8c44-4b90ab513002",
  "document_state": "draft",
  "owner_actor_id": "01991f3a-7b2c-7a13-8c44-4b90ab513003",
  "included_account_ids": {
    "decision_status": "required_from_user",
    "question_id": "fund_perimeter.accounts"
  },
  "opening_as_of": {
    "decision_status": "required_from_user",
    "question_id": "fund_perimeter.opening_date"
  },
  "base_currency": {
    "decision_status": "required_from_user",
    "question_id": "measurement.base_currency"
  }
}
```

Capital policy draft’ı:

```json
{
  "$schema": "fund:schemas/fund/capital-policy.schema.json",
  "schema_version": "1.0.0",
  "policy_series_id": "01991f3a-7b2c-7a21-8c44-4b90ab513010",
  "policy_revision_id": "01991f3a-7b2c-7a22-8c44-4b90ab513011",
  "policy_version": "0.1.0",
  "fund_definition_ref": {
    "fund_id": "01991f3a-7b2c-7a11-8c44-4b90ab513001",
    "revision_id": "01991f3a-7b2c-7a12-8c44-4b90ab513002",
    "digest": {
      "decision_status": "required_from_user",
      "question_id": "fund_definition.must_be_ratified_first"
    }
  },
  "document_state": "draft",
  "created_at": "2026-08-16T12:00:00Z",
  "created_by_actor_id": "01991f3a-7b2c-7a13-8c44-4b90ab513003",
  "intended_effective_from": "2026-09-01T00:00:00Z",
  "supersedes_revision_id": {
    "mode": "not_applicable"
  },

  "objective": {
    "type": "absolute_return",
    "underwriting_horizon_months": {
      "minimum": 3,
      "maximum": 18
    },
    "capital_horizon": {
      "decision_status": "required_from_user",
      "question_id": "capital_purpose.horizon"
    },
    "liquidity_need_mode": {
      "decision_status": "required_from_user",
      "question_id": "capital_purpose.foreseeable_withdrawals"
    },
    "portfolio_review_cadence": "monthly",
    "research_monitoring_cadence": "weekly",
    "change_required_at_review": false
  },

  "eligibility": {
    "direction": "long_only",
    "security_types": ["us_listed_common_equity"],
    "listing_countries": ["US"],
    "shorting": "disabled",
    "leverage": "disabled",
    "derivatives": "disabled"
  },

  "cash": {
    "full_investment_required": false,
    "role": "legitimate_residual",
    "operational_floor": {
      "rule": "max_of_relative_and_absolute",
      "relative_bps_nav": 200,
      "absolute": {
        "mode": "disabled"
      }
    },
    "target": {
      "mode": "disabled"
    },
    "ceiling": {
      "mode": "unbounded_by_policy"
    },
    "commitment_treatment": "deduct_before_deployable_capital"
  },

  "capacity": {
    "max_active_positions": 10,
    "minimum_active_positions": {
      "mode": "disabled"
    },
    "position_count_enforcement": "hard_max_only"
  },

  "concentration": {
    "max_security_weight": {
      "decision_status": "required_from_user",
      "question_id": "risk_envelope.max_single_security_weight"
    },
    "max_issuer_weight": {
      "decision_status": "required_from_user",
      "question_id": "risk_envelope.max_single_issuer_weight"
    },
    "related_issuer_aggregation": "enabled",
    "sector_weight_limit": {
      "mode": "monitor_only"
    },
    "causal_driver_limit": {
      "mode": "monitor_only"
    },
    "unknown_driver_treatment": "review_required"
  },

  "sizing": {
    "base_weight_formula": "deployable_capital_divided_by_max_active_positions",
    "readiness_multipliers": {
      "watchlist": {
        "status": "enabled",
        "multiplier": "0"
      },
      "starter": {
        "status": "enabled",
        "multiplier": "0.5"
      },
      "core": {
        "status": "enabled",
        "multiplier": "1"
      },
      "exceptional": {
        "status": "disabled"
      }
    },
    "min_economic_position": {
      "mode": "disabled"
    },
    "unknown_downside_treatment": "ineligible_for_new_risk",
    "binding_rule": "minimum_of_all_hard_capacities"
  },

  "risk": {
    "position_scenario_loss_budget_bps_nav": {
      "decision_status": "required_from_user",
      "question_id": "risk_envelope.position_loss_budget",
      "proposed_value_bps": 100
    },
    "loss_budget_applies_to": [
      "fundamental_downside",
      "single_name_gap"
    ],
    "downside_case_requirement": "human_adjudicated_required",
    "unknown_downside_treatment": "ineligible_for_new_risk",
    "portfolio_stress_limit": {
      "decision_status": "required_from_user",
      "question_id": "risk_envelope.portfolio_stress_limit"
    },
    "drawdown_response_ladder": [
      {
        "drawdown_bps_from_peak": 1000,
        "actions_added": ["warning_and_review"]
      },
      {
        "drawdown_bps_from_peak": 1500,
        "actions_added": ["freeze_net_new_risk"]
      },
      {
        "drawdown_bps_from_peak": 2000,
        "actions_added": [
          "freeze_non_risk_reducing_proposals",
          "full_portfolio_reunderwrite"
        ]
      }
    ],
    "automatic_liquidation": "disabled"
  },

  "trading": {
    "no_trade_band": {
      "formula": "max_absolute_relative",
      "absolute_weight_delta_bps": 100,
      "relative_target_weight_bps": 2000
    },
    "minimum_economic_trade": {
      "mode": "disabled"
    },
    "band_bypass_reasons": [
      "thesis_broken",
      "hard_limit_breach",
      "reconciliation_repair",
      "authority_reduction",
      "position_legitimacy_failure"
    ],
    "price_tolerance": {
      "increase_risk_bps": 250,
      "reduce_risk": {
        "mode": "unbounded_by_policy"
      }
    },
    "proposal_max_age_market_sessions": 1,
    "execution_quantity_basis": "recalculate_from_approved_weight_at_execution",
    "manual_execution_required": true
  },

  "measurement": {
    "base_currency_source": "fund_definition",
    "nav_cut": "us_official_market_close",
    "market_calendar": "XNYS",
    "price_basis": "promoted_official_eod_close",
    "fx_conversion_required": true,
    "primary_return_method": "twr",
    "owner_outcome_method": "xirr",
    "benchmark_mode": "disabled",
    "hurdle_mode": "disabled",
    "missing_input_behavior": "fail_closed"
  },

  "governance": {
    "owner_actor_id": "01991f3a-7b2c-7a13-8c44-4b90ab513003",
    "scheduled_review_cadence": "quarterly",
    "tightening_cooling_off_days": 0,
    "loosening_cooling_off_days": 7,
    "emergency_override_max_days": 7,
    "retroactive_changes": "disabled",
    "loosen_to_cure_existing_breach": "disabled",
    "human_activation_required": true,
    "validation_report_required": true
  },

  "assumption_refs": [],

  "calibration": {
    "status": "provisional",
    "validation_gate": "property_golden_replay_and_two_shadow_cycles",
    "items": [
      {
        "json_pointer": "/cash/operational_floor/relative_bps_nav",
        "basis": "design_anchor"
      },
      {
        "json_pointer": "/capacity/max_active_positions",
        "basis": "operator_capacity_anchor"
      },
      {
        "json_pointer": "/sizing/readiness_multipliers",
        "basis": "design_anchor"
      },
      {
        "json_pointer": "/risk/drawdown_response_ladder",
        "basis": "design_anchor"
      },
      {
        "json_pointer": "/trading/no_trade_band",
        "basis": "design_anchor"
      },
      {
        "json_pointer": "/trading/price_tolerance/increase_risk_bps",
        "basis": "design_anchor"
      }
    ]
  },

  "unresolved_decisions": [
    {
      "question_id": "fund_perimeter",
      "owner": "user",
      "blocking": true
    },
    {
      "question_id": "measurement.base_currency",
      "owner": "user",
      "blocking": true
    },
    {
      "question_id": "capital_purpose",
      "owner": "user",
      "blocking": true
    },
    {
      "question_id": "risk_envelope",
      "owner": "user",
      "blocking": true
    }
  ]
}
```

Buradaki policy şema-valid bir `draft` olabilir ama `ratified` olamaz. Ratification validator şu dört koşulu aramalı:

- `required_from_user` kalmamış olmalı.
- `unresolved_decisions` boş olmalı.
- Provisional değerlerin validation spec’i bulunmalı.
- Referans verilen `fund_definition` ratified ve hash’lenmiş olmalı.

## 3. Policy/state sınırı

| Kavram | Nerede yaşar | Gerekçe |
|---|---|---|
| Dahil broker hesapları | `fund_definition` | Fonun kimliği; ağırlıklandırma kuralı değil |
| Açılış tarihi ve bakiyeleri | Opening olayları | Tarihli gerçek; policy değil |
| Base currency | `fund_definition` | Değişmesi performans lineage’ını değiştirir |
| Güncel NAV | Projection | Her fiyat hareketiyle değişir |
| Güncel nakit | Projection | Fill, temettü ve akışlarla değişir |
| `deployable_capital` | Projection | NAV − rezervler − pending obligations − cash floor |
| Operational cash floor kuralı | Capital policy | State’ten tutar türeten kural |
| O günkü cash floor tutarı | Projection | Policy × güncel NAV sonucu |
| Planlı para çekimi | `capital_commitment` state’i | Zamanlı dış yükümlülük |
| Pozisyon tavanı | Capital policy | Sermaye kararının sınırı |
| Güncel pozisyon sayısı | Projection | Gerçek portföy state’i |
| Readiness çarpanları | Capital policy | Sınıfa verilecek sermaye etkisi |
| Bir ismin readiness sınıfı | Adjudicated research state | Güncel analitik hüküm |
| Loss budget | Capital policy | Kabul edilebilir NAV kaybı |
| Bir ismin downside tahmini | Adjudicated research artifact | Şirkete ve tarihe özgü |
| Eligible weight band | Projection | Policy + NAV + downside + limitlerin sonucu |
| Target weight | `portfolio_proposal` | Tarihli insan/karar çıktısı |
| Güncel drawdown | Performance projection | NAV serisinden türetilir |
| Drawdown eylem merdiveni | Capital policy | Drawdown’a verilecek tepki |
| Fiyat/FX değerleri | Market state | Tarihli gözlem |
| Fiyat/FX kabul kuralı | Measurement contract/policy | Hangi girdinin kullanılabilir olduğunu belirler |
| Aktif policy | Event projection | `capital_policy_activated/superseded` olaylarından türetilir |
| Operasyon yetkisi | `operating_authority` projection | Policy’den bağımsız, süreli işletim yetkisi |

Operational cash floor yalnız oran olmamalı. Doğru biçim:

```text
max(relative NAV floor, absolute operational floor, known capital commitments)
```

Fakat absolute floor gerçekten gerekmiyorsa `disabled` yazılabilir. `null` bırakılamaz.

## 4. `operating_authority` ve `policy_validation_spec`

### `operating-authority-grant.schema.json`

Grant immutable bir karardır; sonradan `revoked: true` diye değiştirilmez. Revocation ayrı olaydır.

Asgari alanlar:

```text
authority_grant_id             UUIDv7
schema_version                 SemVer
fund_id                        UUIDv7
policy_ref                     exact revision + version + digest
authority_level                A0 | A1 | A2 | A3 | A4
effective_from                 UtcInstant
expires_at                     UtcInstant
granted_at                     UtcInstant
granted_by_actor_id            UUIDv7
validation_report_refs[]       exact report + digest
scope.account_ids[]            UUIDv7
scope.allowed_actions[]        enum
scope.max_single_trade_bps_nav BpLimit
scope.max_daily_risk_increase  BpLimit
scope.policy_eligible_only     boolean
scope.manual_approval_required boolean
scope.manual_execution_required boolean
reversion_level_on_expiry      A0–A3
revocation_triggers[]          closed enum
```

Yetki merdiveni:

| Seviye | Sistem ne yapabilir |
|---|---|
| A0 | Gerçeği kaydeder; sermaye proposal’ı üretmez |
| A1 | Kör paralel gölge proposal üretir; gerçek state’i etkilemez |
| A2 | Gölge proposal’ları kâğıt üzerinde icra eder ve shadow NAV üretir |
| A3 | Sınırlı, küçük ve geri döndürülebilir canlı proposal üretebilir; insan onayı ve icrası şart |
| A4 | Policy kapsamındaki tam proposal setini üretebilir; yine emir iletemez, insan onayı ve broker icrası şart |

Revocation trigger’ları en az:

```json
[
  "policy_superseded",
  "validation_regression",
  "unresolved_hard_breach",
  "reconciliation_disputed",
  "nav_stale",
  "input_integrity_failure",
  "manual_revocation"
]
```

Gerçek durum:

```text
grant + revoke/expire events → current_operating_authority projection
```

`authority_level` capital policy alanı değildir. Aynı policy önce A1, sonra A2 ve A3 altında çalışabilir.

### `policy-validation-spec.schema.json`

JSON’un içine çalıştırılabilir formül veya kod koymamalıyız. Aksi hâlde güvenli olmayan küçük bir programlama dili icat ederiz.

Doğru ayrım:

- JSON spec: Hangi testlerin, hangi parametre ve fixture’larla koşulacağını bildirir.
- Test registry/kodu: Property’nin gerçek uygulamasını taşır.
- Immutable artifact’lar: Fixture ve golden çıktıları taşır.
- Validation report: Hangi policy, engine ve input hash’lerinin gerçekten geçtiğini kaydeder.

Asgari alanlar:

```text
validation_spec_id                 UUIDv7
validation_spec_version            SemVer
schema_version                     SemVer
policy_series_id                   UUIDv7
applies_to_policy_schema_version   SemVer
required_engine_contract_version   SemVer
property_suites[]
golden_suites[]
replay_suites[]
shadow_acceptance_criteria
global_tolerances
required_suite_outcomes
fixture_artifact_refs[]
implementation_registry_ref
```

Bir property kaydı:

```json
{
  "property_id": "policy.downside_worsening_never_increases_own_cap",
  "implementation_id": "fund_policy_properties:downside_monotonicity:v1",
  "generator_id": "fund_policy_generators:position_snapshot:v1",
  "sample_count": 5000,
  "seed_policy": "fixed_and_reported",
  "parameters": {},
  "expected_outcome": "pass"
}
```

Golden vaka:

```json
{
  "case_id": "golden.single_name_gap",
  "fixture_ref": {
    "artifact_id": "01991f3a-7b2c-7a31-8c44-4b90ab513020",
    "digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "expected_output_ref": {
    "artifact_id": "01991f3a-7b2c-7a32-8c44-4b90ab513021",
    "digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  },
  "comparator": "exact_domain_comparison",
  "tolerances": {
    "weight_bps": 0,
    "money_decimal": "0"
  }
}
```

Spec exact policy revision’a değil, policy series + schema version’a uygulanabilir. Her validation report ise mutlaka şu dörtlüyü bağlar:

```text
exact policy revision/digest
exact validation spec version/digest
exact engine version/digest
exact fixture/input manifest digest
```

Böylece yalnız bir sayı değiştiğinde spec kopyalanmaz; fakat o yeni sayılarla testlerin yeniden koştuğu kanıtlanır.

## 5. `config/` mı `data/` mı?

Çelişki yok; tanım ile yaşam döngüsü ayrılmalı.

Önerilen yerleşim:

```text
config/fund/
  fund-definitions/
  capital-policies/
  policy-validation-specs/

data / kanonik artifact store:
  sealed policy artifacts
  validation reports
  authority grants
  event ledger
  projections
```

Akış:

1. Kullanıcı policy’yi `config/fund/capital-policies/` altında yazar.
2. Ratification sırasında belge doğrulanır ve immutable artifact deposuna mühürlenir.
3. `capital_policy_activated`, exact revision ve SHA-256 digest’i kaydeder.
4. Hangi policy’nin aktif olduğu config dosya adına bakılarak değil, olaylardan türetilir.
5. Git’teki policy dosyası sonradan değişse bile etkin policy’nin mühürlü bytes’ı kaybolmaz.

`config/mandate.json` ile capital policy aynı anlamda “insan kararıdır”; farkları şudur:

- Mandate araştırma ve uygunluk bağlamıdır.
- Capital policy sürümlü sermaye anayasasıdır.
- Aktivasyon, supersede ve override gerçekleri `data`/olay defterindedir.

Dolayısıyla `config` authoring ve karar tanımıdır; `data` ise o kararın ne zaman yetki kazandığının kanonik tarihidir.