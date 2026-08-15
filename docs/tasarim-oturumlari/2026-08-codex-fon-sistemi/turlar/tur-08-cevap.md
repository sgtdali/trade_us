Temel sorun 21 tip olması değil; listede üç farklı şeyin karışması:

1. Süreçte gerçekten olanlar: `workflow_prepared`, `result_attached`.
2. Bir analiz hakkındaki kabul kararı: `analysis_accepted`.
3. Domain sonucu: bucket değişmesi, tez açılması, pozisyon işlemi.

Önce bunları ayırmak gerekiyor.

Ayrıca mevcut ortak event zarfı artık kullanılamaz. Her olayda zorunlu `run_id` ve `ticker` istemek; `round_closed`, `monitoring_run_closed` ve portföy uzlaştırmasına sahte kimlikler koydurur. V2 zarfında en az `sequence`, `batch_id`, `subject_type/id`, opsiyonel ticker/run/round/thesis kimlikleri, `causation_id`, `occurred_at`, `recorded_at` ve ledger’a yazma yetkisi bulunmalı. Mevcut 57 V1 olay değiştirilmez; projector onları yeni iç modele uyarlamalı.

## 1. `candidate_screened` yaşamalı mı?

Yeni olay olarak ölmesini savunuyorum.

Tur 2 tek karşılaştırmalı hüküm üretiyorsa A/B/C sonuçları `round_screen` analizinin toplu kabul edilmiş sonucudur. Candidate projection’ları buradan türetilir. Bu nedenle:

- `candidate_screened` yeni V2 olaylarında üretilmez.
- Mevcut 12 olay legacy olarak okunmaya devam eder.
- Projection’daki “NVDA’nın son bucket’ı A” satırı olay değildir.
- Toplu olaydan tekrar bireysel `candidate_screened` olayları üretmek aynı gerçeği iki kez kaydetmek olur.

Toplu sonuçta her ticker için stabil bir `outcome_id` bulunabilir. Sonradan düzeltme gerekiyorsa parent analiz ve `outcome_id` referans alınır.

Daha da sade biçimde, `slice_screen_completed` ve `round_screen_completed` yerine ortak bir analiz yaşam döngüsü kullanılabilir:

```text
analysis_proposed
  analysis_kind = slice_screen | round_screen | tearsheet | comps | pitch | ...
analysis_reviewed
  decision = accepted | rejected
```

Böylece screen proposal’ı toplu payload taşır; bucket projection’ı yalnız kabul edilmiş `round_screen` sonucundan çıkar. “Completed” kelimesini kullanmazdım, çünkü modelin bitirmesi ile insanın kabul etmesini yine karıştırıyor.

## 2. `analysis_accepted` ayrı olay mı?

Ayrı olay olmalı; fakat `analysis_accepted` ve `analysis_rejected` diye iki tip değil, tek:

```text
analysis_reviewed
  analysis_id
  decision = accepted | rejected
  reviewer
  reviewed_at
  reason
  accepted_outcome
```

`accepted_outcome`, insanın aynen veya düzenleyerek kabul ettiği kanonik yapılandırılmış sonuçtur. Böylece proposal sonradan değiştirilmez; insan düzeltme yaptıysa kabul edilmiş hüküm review olayında açıkça görünür.

“Kabul edilmemiş completed kalıcı hâle gelir” problem değil; gerçek bir durumdur: model çalıştı ama hükmü kabul edilmedi. Sorun, buna `workflow_completed` demektir.

Doğru sıra:

```text
workflow_prepared
result_attached
analysis_proposed
analysis_reviewed
```

Bunların her biri ayrı bir gerçektir:

- `result_attached`: Ham çıktı repo’ya alındı ve hash’lendi.
- `analysis_proposed`: Ham çıktıdan yapılandırılmış analitik hüküm çıkarıldı.
- `analysis_reviewed`: İnsan veya izinli makine politikası bu hükmü kabul/reddetti.

Kabul sonucunun domain etkileri aynı atomik batch’e eklenir:

```text
analysis_reviewed(accepted)
workflow_requested(next)
```

veya:

```text
analysis_reviewed(accepted actionable_candidate)
thesis_opened
```

Dolayısıyla mevcut `workflow_completed` yeni modelde ölür. “Workflow analitik olarak tamamlandı” durumu, kabul edilmiş review’dan türetilir. Mevcut 11 legacy `workflow_completed`, projector tarafından “proposal + legacy acceptance” gibi yorumlanır.

`result_attached` ile `workflow_completed` bugün ayrı olmakta haklı; biri artefakt alımı, diğeri semantik sonuç olmaya çalışıyor. Yanlış olan ayrılık değil, `workflow_completed`ın aynı anda extraction, kabul, rota seçimi ve candidate geçişi taşıması.

## 3. `thesis_axes_updated` nasıl çözülür?

Bu tipi kaldırırım. Beş eksenin aynı sahibi yok:

| Gerçek | Olay sahibi |
|---|---|
| Yeni kanıt | `thesis_evidence_recorded` |
| Company status, security readiness, recommended action | `thesis_assessment_recorded` |
| Lifecycle | `thesis_opened`, `thesis_wind_down_started`, `thesis_closed`, ileride `thesis_superseded` |
| Actual exposure | `portfolio_transaction_recorded`, `portfolio_reconciled` |
| Monitoring required | Projection |

`thesis_assessment_recorded`, bir tablo patch’i değil, “şu tarih itibarıyla tez hakkında yeni bir yatırım değerlendirmesi kayda alındı” domain olayıdır. Üç analitik eksenin tam snapshot’ını, önceki assessment kimliğini, dayandığı evidence ID’lerini ve gerekçeyi taşır:

```text
company_thesis_status
security_readiness
recommended_action
basis_evidence_ids
prior_assessment_id
reason
```

Yalnız bir eksen değişse bile üçü birlikte kaydedilir; böylece `broken + add` gibi yasak kombinasyonlar atomik doğrulanabilir.

Bir assessment `broken + exit` sonucuna varırsa aynı batch’te ayrıca `thesis_wind_down_started` yazılır. Exposure ise bu olaydan değişmez; insan satana kadar portföy defteri `long/short` göstermeye devam eder.

Bu ayrım thesis-tracker sözleşmesiyle de uyumlu: evidence ledger, company status, security readiness ve position action zaten ayrı anlamlara sahip.

## Mevcut sekiz tipin hükmü

| Mevcut tip | Hüküm |
|---|---|
| `idea_run_started` | Legacy; yeni modelde daha kapsamlı `round_started` alır. |
| `result_attached` | Yaşar; tercihen `analysis_result_attached` diye netleştirilir. |
| `candidate_screened` | Yeni üretimde ölür; legacy uyumluluk için okunur. |
| `workflow_prepared` | Yaşar; immutable pack ve context bundle kimliğini taşımalıdır. |
| `workflow_completed` | Yanlış modellenmiş; `analysis_proposed + analysis_reviewed` ile değiştirilir. |
| `waiting_for_trigger` | Yanlış modellenmiş; bu bir olay değil türetilmiş durumdur. |
| `source_interpretation_corrected` | Fazla genel ve bugün yanlış amaçlarla kullanılıyor; B terfisi correction değildir. |
| `manual_review_required` | Gerçek bir iş talebidir; `manual_review_requested` adı daha doğru, candidate state’ini otomatik `blocked` yapmamalıdır. |

`waiting_for_trigger` yerine gerçek olay `trigger_registered` olmalı. Bir subject üzerinde karşılanmamış ve iptal edilmemiş trigger varsa “waiting” projection’dan çıkar:

```text
trigger_registered
trigger_satisfied
trigger_cancelled
```

`trigger_satisfied` yalnız “eşik karşılandı” gerçeğini taşır. Sonucu ayrı olaydır:

```text
trigger_satisfied
workflow_requested
```

veya:

```text
trigger_satisfied
manual_review_requested
```

`source_interpretation_corrected` ise B→A terfisinde kesinlikle kullanılmamalı. Bunun gerçek domain eylemi `promotion_evaluated` olur ve sonucu `resolved/unresolved/indeterminate` taşır. Literal bir kaynak yorumunun düzeltilmesi için dar anlamlı `evidence_interpretation_corrected` korunabilir; evrensel JSON patch olayına dönüştürülmemeli.

## Kaba listenin başka eksikleri

- `workflow_requested` geri gelmeli. Kabul edilmiş analizin `next_workflow` alanından gizlice queue üretmek yerine sonraki iş isteği açık olay olmalı.
- `monitoring_run_started` gerekli. Yalnız `monitoring_run_closed` varsa hangi tezlerin kontrol edilmesinin beklendiğini bilemeyiz.
- Partial tur için mevcut dört discovery tipi yeterli değil; Tur 1 girdisinin kapatıldığı an ile bütün turun kapandığı an ayrılmalı. `round_stage1_closed` benzeri bir sınır gerekebilir.
- Yanlış portföy işlemini append-only düzeltmek için `portfolio_transaction_recorded` payload’ı `reversal_of` taşıyabilmeli; ayrıca ayrı bir “transaction updated” olayı gerekmiyor.
- `analysis_rejected` ayrı tip olmamalı; `analysis_reviewed.decision` yeterli.

Benim önerdiğim çekirdek sözlük bu nedenle yaklaşık şöyle olur:

```text
round_started
round_stage1_closed       # kesin politika hâlâ açık
round_closed

workflow_requested
workflow_prepared
result_attached
analysis_proposed
analysis_reviewed

thesis_opened
thesis_evidence_recorded
thesis_assessment_recorded
thesis_wind_down_started
thesis_closed
thesis_superseded         # şemada rezerv, mekanizma YAGNI

monitoring_run_started
thesis_check_completed
monitoring_run_closed

portfolio_transaction_recorded
portfolio_reconciled

trigger_registered
trigger_satisfied
trigger_cancelled
manual_review_requested
promotion_evaluated
evidence_interpretation_corrected
```

Slice ve Tur 2 sonuçları `analysis_proposed.analysis_kind` içinde yaşadığı için ayrıca `slice_screen_completed`, `round_screen_completed` ve `candidate_screened` gerekmiyor.

Son hükmüm: event-type sayısını azaltmak hedef olmamalı. Asıl test şu olmalı:

> Olay geçmiş zamanda olmuş tek bir gerçeği mi anlatıyor, yoksa bir tablonun state’ini mi tarif ediyor?

`waiting_for_trigger` ve `thesis_axes_updated` ikinci grupta; `trigger_registered` ve `thesis_assessment_recorded` birinci grupta. Bu ayrım yapılınca projection’ın ne olduğu da kendiliğinden netleşiyor.