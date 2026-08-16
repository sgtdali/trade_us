Üç ana hüküm çıktı: thesis-tracker kendi otoritatif defterini gerektirmiyor; `DASHBOARD_PACK` tracker girdisi değil sunum çıktısı; skill’in statü sözlüğü doğrudan domain state machine olarak kullanılamaz.

## 1. Skill kendi defterinin sahibi mi?

Hayır. En doğru tarif:

> Domain stateful, thesis-tracker çalıştırması stateless’tir.

Skill geçmiş tezi ve kanıtları girdi olarak görmek istiyor, fakat kendi özel kalıcı deposunu işletmiyor. Materializer:

- Bir `tracker_input.json` okuyor.
- Yeni CSV/XLSX paketi üretiyor.
- Tez statüsüne kendisi karar vermiyor.
- Mevcut tracker’ı yerinde değiştirmiyor [tracker-materializer.md](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/thesis-tracker/references/tracker-materializer.md:3).

Dolayısıyla `thesis-schema.md`, persistence şeması değil; tablo/CSV/XLSX/veritabanı/structured-output için interchange ve presentation şemasıdır. Skill’in “append-only” talebi de kendi JSONL’ini kurma talebi değil, önceki underwriting ve evidence history’nin kaybedilmemesi talebidir [SKILL.md](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/thesis-tracker/SKILL.md:36).

Doğru wrapper:

```text
kanonik olaylar
→ thesis projection
→ mevcut tez snapshot’ı + yeni kanıt
→ thesis-tracker
→ önerilen değerlendirme + yeni artefakt
→ doğrulama/adjudication
→ yeni kanonik olaylar
→ yeniden projection
```

XLSX/CSV çıktıları salt okunur, sürümlü projection artefaktlarıdır. Skill’in bunları yerinde güncellemesine izin verilmemeli. İnsan XLSX’i elle değiştirirse o dosya da otomatik otorite olmaz; değişiklikler açık import/adjudication yoluyla olaylara çevrilir.

## 2. `DASHBOARD_PACK` hangi pack?

Aradığımız iki pack’ten hiçbiri; üçüncü bir şeydir: presentation payload.

[DASHBOARD_PACK.md](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/thesis-tracker/references/DASHBOARD_PACK.md:3) yalnız kullanıcı HTML dashboard/report istediğinde devreye giriyor. `dashboard-builder` renderer’ının beklediği hero, snapshot, modül ve citation biçimini tarif ediyor. Yeni kanıt toplamak veya tracker’ı çalıştırmak için tasarlanmamış.

Üç katman korunmalı:

```text
monitoring_snapshot
  Küçük, deterministik, LLM’siz eşik motorunun girdisi.

thesis_update_pack
  Tracker’ın girdisi: kanonik tez snapshot’ı, yeni evidence,
  mekanik sapmalar, önceki değerlendirme ve eksik kaynaklar.

dashboard_payload
  Kabul edilmiş sonuçların insan-okunur HTML görünümü.
```

Bu nedenle `thesis_tracker.pack_step`, `dashboard` olmamalı; `thesis_update` benzeri gerçek bir veri hazırlama adımı olmalı. Dashboard payload ancak tracker sonucu adjudicate edilip olaylara işlendiğinde projection’dan üretilebilir.

`thesis_update_pack`, skill’in tablo sözleşmesiyle mümkün olduğunca hizalanabilir:

- thesis pillars,
- evidence ledger,
- KPI tracker,
- catalyst calendar,
- action rules,
- decision log,
- sources/open questions.

Ama portfolio/capital alanları V1’de `null` ve `not_applicable_reason: no_capital_policy` olmalıdır; sahte benchmark, position action veya risk/reward üretilmemelidir.

## 3. `retired`, `impaired` ve `changed`

Eklenti kendi içinde bile `retired` konusunda semantik olarak tutarlı değil:

- Workflow sözlüğü onu company-thesis status içine koyuyor [SKILL.md](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/thesis-tracker/SKILL.md:84).
- Şema ise `Retired: position/coverage closed` diyor [thesis-schema.md](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/thesis-tracker/references/thesis-schema.md:35).

Bu yüzden skill enum’u domain enum’u olamaz. Bizim `active/review_required/broken/closed` alanımız da “company thesis health” değil, `thesis_governance_state` olarak yeniden adlandırılmalı. Skill’in zengin sözlüğü ise tarihli bir assessment sınıflandırması olarak saklanmalı.

Önerilen eşleme:

| Skill assessment | Domain etkisi |
|---|---|
| `strengthening`, `intact` | State `active` kalır; yalnız assessment kaydı |
| `untested` | `active`; zorunlu next-proof/review tarihi olmalı |
| `watch` | `active`; daha yakın inceleme önerisi, tek başına `review_required` değil |
| `impaired` | `review_required` geçişi önerir |
| `changed` | `review_required` geçişi önerir; özgün tezin değiştirilmesi ayrıca insan onayı ister |
| `broken` | `broken` geçişi önerir |
| `retired` | Yalnız `closed` önerisi; asla doğrudan geçiş değil |

`retired` gerekçesi yalnız “pozisyon kapandı” ise öneri geçersiz sayılmalıdır; bizim modelimizde `flat` olmak tezi kapatmaz. V1’de capital policy zaten olmadığı için pozisyona dayalı retirement bütünüyle uygulanamaz.

Böylece `impaired/changed` ayrımını kaybetmiyoruz ama ikisini yeni kalıcı state’ler yapmıyoruz. Assessment geçmişinde farklı anlamlarıyla kalıyorlar; operasyonel sonuçları aynı: insan yeniden-underwrite etmeli.

## 4. Tracker çıktısı hangi olaylara dönüşmeli?

Evidence ile assessment kesinlikle ayrılmalı. Aksi hâlde aynı olguyu daha sonra farklı yorumlamak veya reddedilmiş bir değerlendirmeden bağımsız kullanmak mümkün olmaz.

Asgari ayrım:

```text
thesis_evidence_recorded
thesis_assessment_proposed
thesis_assessment_adjudicated
```

Gerekirse adjudication ardından gerçek domain eylemi gelir:

```text
thesis_review_requested
thesis_break_confirmed
thesis_closed
```

`thesis_evidence_recorded`, kaynak olgusunu taşır: evidence ID, source/accession, hash, known_at, period_end ve etkilediği pillar. Tracker’ın yorumundan bağımsızdır ve idempotency anahtarı kaynak kimliğidir.

`thesis_assessment_proposed`, LLM yargısıdır: dayandığı evidence ID’leri, önerilen company assessment, pillar değişimleri, gerekçe, önerilen next review ve artefakt hash’i.

Tracker hiçbir zaman doğrudan `broken` veya `closed` yapamaz. İnsan adjudication’ı şu durumlarda zorunludur:

- `impaired`, `changed`, `broken` veya `retired` önerisi;
- monitoring threshold değiştirme önerisi;
- mekanik sapmanın “önemsiz” diye bastırılması;
- mevcut onaylı monitoring rule’a override;
- lifecycle kapanışı.

`strengthening/intact/untested/watch` değerlendirmeleri, lifecycle state’ini değiştirmiyorsa insan kuyruğuna düşmeden model assessment olarak kaydedilebilir. Fakat “intact” hükmü mekanik bir breach’i reddediyorsa bu artık masum değildir; insan kapısına gider.

Bu kesim haftalık yükü sınırlar: her tracker çalışması insan işi üretmez, yalnız state veya monitoring sözleşmesini etkileyenler üretir.

## 5. Mekanik motor skill şemasını kullanabilir mi?

Doğrudan kullanamaz. Skill şeması doğru kavramları taşıyor:

- pillar,
- baseline/expected path,
- confirm/warning/break thresholds,
- KPI source/unit/period,
- threshold origin ve approval status [thesis-schema.md](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/thesis-tracker/references/thesis-schema.md:10).

Fakat bunlar insan-okunur tablo alanları. Deterministik motor için eksik olanlar:

```text
rule_id ve version
metric_id / veri serisi eşlemesi
operator
typed threshold value
unit ve scale
period basis
source contract
known_at policy
revision/restatement policy
tolerance
missing/stale-data policy
effective_from / expires_at
cadence / next_due
approval status
```

Bu nedenle ayrı kanonik `monitoring_contract` zorunlu. Ancak iki paralel tez şeması kurmamalıyız. İlişki tek yönlü olmalı:

```text
kanonik monitoring_contract
→ thesis-tracker pillar/KPI/action-rule görünümü
```

Tracker yeni eşik önerirse ters yönde otomatik sync yapılmaz:

```text
tracker threshold proposal
→ draft_monitoring_rule
→ yapılandırılmış doğrulama
→ insan onayı
→ monitoring_rule_approved
```

Mekanik motor hiçbir zaman tracker’ın `"FCF margin below 20%"` gibi metinsel hücresini parse ederek çalışmamalı. Onaylı typed rule’dan çalışmalı; skill görünümü bu rule’un insan-okunur yansıması olmalı.

Sonuç olarak bakım yükü “iki şemayı sürekli senkronize etmek” değil, iki dar adapter’dır:

1. Domain projection → `thesis_update_pack`.
2. Tracker proposal → draft assessment/rule olayları.

Bu ayrım skill sürümü değiştiğinde domain modelinin de değişmesini engeller.