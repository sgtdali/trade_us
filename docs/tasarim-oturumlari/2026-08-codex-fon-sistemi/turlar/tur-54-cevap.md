Ana karar: `capital_input_manifest` tek bir mutable “araştırma kaydı” değil, **security başına belirli bir anda geçerli kabul edilmiş araştırma girdilerini bağlayan immutable manifesttir**. Tek bir `valid` bayrağı taşımamalıdır; bileşenlerin kullanılabilirliği ve izin verilen sermaye eylemleri ayrı değerlendirilir.

## 1. Manifest alanları ve bayatlama

Önerilen ana yapı:

```text
capital_input_manifest_id
schema_version
fund_id
security_id
thesis_id
assembled_at
as_of_event_position

component_refs:
  thesis_version
  underwriting_readiness_decision
  downside_case
  valuation_anchor
  risk_driver_exposure_set
  monitoring_contract
  monitoring_status

materialization:
  builder_version
  freshness_ruleset_version
```

Her `component_ref` şunları taşır:

```text
artifact_id
version_id
digest
adjudication_event_id
effective_from
known_at
freshness_state_at_assembly
review_due_at
freshness_reason_codes
```

Kapalı freshness sözlüğü:

- `current`
- `review_due`
- `stale`
- `superseded`
- `invalidated`
- `disputed`
- `missing`

Tek bir `manifest_valid` alanı olmamalı. Manifest kısmen kullanılabilir olabilir: muhasebe ve hard-limit trim için yeterli, yeni risk için yetersiz gibi.

### Fiyat sorununun çözümü

Güncel fiyat `valuation_anchor`ın parçası değildir; fonun `market_snapshot` girdisidir.

- `valuation_anchor`: yöntem, metrik, dönem, peer seti, varsayımlar ve referans fiyat bağlamı.
- `market_snapshot`: bugünkü fiyat.
- `capital_actionability`: ikisinin o anda karşılaştırılmasından türetilir.

Dolayısıyla fiyatın günlük değişmesi readiness’i günlük bozmaz. Yeni filing, maddi guidance değişimi, peer-set değişimi veya anchor’ın açık geçerlilik bandının aşılması `review_due` doğurabilir.

Yeni bir bileşen adjudicate edilirken readiness etkisi kapalı sözlükle kaydedilmelidir:

- `no_readiness_effect`
- `readiness_review_required`
- `readiness_invalidated`

Böylece her veri yenilemesi readiness’i düşürmez; maddi değişiklik de sessiz geçmez.

## 2. Açılış kitabı

Doğru seçenek **(b)**, fakat “grandfathered” mevcut ağırlığın onaylandığı anlamına gelmemeli. Durumun adı daha dürüstçe `legacy_hold_only` veya `legacy_ununderwritten` olmalı.

Bu pozisyonlarda:

- Gerçek adet, nakit, NAV ve tüm hard riskler hesaplanır.
- `policy_compliant_max_weight` sıfır değil, `not_computable` olur.
- Mevcut ağırlık hedef ağırlık sayılmaz.
- Yeni alım ve risk artırımı bloklanır.
- Hard-limit ihlali varsa trim üretilebilir.
- Yalnız araştırma eksik diye otomatik satış üretilmez.
- Sermaye-at-risk büyüklüğüne göre onboarding araştırma işi açılır.

Kullanıcı her pozisyon için ilk gün tam pitch yazmak zorunda değildir. Ancak araştırmasız tutuş normal ve kalıcı bir readiness sınıfı olamaz. Pozisyon ya zamanla underwritten hâle gelir ya da gerekçeli, süreli bir `ununderwritten_hold_exception` altında kalır. İstisnanın süresi dolunca otomatik satış değil, zorunlu insan kararı doğar.

## 3. Eksik girdi × mümkün aksiyon

| Eksik veya kullanılamaz girdi | Statüko seçeneği | Yeni pozisyon / artırma | Hard-limit trim | İsteğe bağlı trim | Replacement hükmü | Exit |
|---|---:|---:|---:|---:|---:|---:|
| Tez yok | Evet, fakat endorsement değil | Bloklu | Evet | İnsan seçeneği | Bloklu | Yalnız insan veya objektif eligibility ihlali |
| Readiness yok | Evet, işaretli | Bloklu | Evet | İnsan seçeneği | Bloklu | Eksiklik tek başına gerekçe değil |
| Downside yok | Evet, işaretli | Bloklu; boyut hesaplanamaz | Evet | İnsan seçeneği | Bloklu | Eksiklik tek başına gerekçe değil |
| Valuation anchor yok/bayat | Evet, `review_required` | Bloklu | Evet | İnsan seçeneği | Bloklu | Eksiklik tek başına gerekçe değil |
| Driver eşlemesi yok | Evet | Policy `monitor_only` ise insan incelemesiyle starter mümkün; aksi hâlde bloklu | Bilinen issuer/sektör limitleri için evet | İnsan seçeneği | Driver-fit önemliyse bloklu | Eksiklik tek başına gerekçe değil |
| Monitoring eksik/gecikmiş | Evet, acil review ile | Bloklu | Evet | İnsan seçeneği | Bloklu | Eksiklik tek başına gerekçe değil |
| Manifest tamamen yok | `legacy_hold_only` | Bloklu | Evet | İnsan seçeneği | Bloklu | Otomatik değil |

Buradaki “statüko” bir **hold tavsiyesi** değildir; yalnızca mevcut gerçekliği değiştirmeyen seçenektir. Araştırma eksikliği riski artırmayı engeller, fakat tek başına zorunlu satış kanıtı oluşturmaz.

## 4. Manifest olay mı, projection mı?

İkisi şu şekilde uzlaştırılır:

1. **Güncel manifest adayı projection’dır.** Projector, o andaki kabul edilmiş bileşenleri ve freshness durumlarını toplar.
2. **Bir risk snapshot’ı veya proposal üretileceğinde mühürlenir.** Exact bileşen referansları, event position, builder sürümü ve değerlendirme zamanı ile immutable/content-addressed artefakt hâline gelir.
3. Proposal bu mühürlü artefaktın `artifact_id + digest` referansını taşır.
4. Sonradan yeni kanıt gelirse eski manifest değiştirilmez; yeni proposal için yeni manifest materialize edilir.

Manifestin materialize edilmesi başlı başına bir domain olayı olmak zorunda değildir. Artefakt deposuna kaydedilir; onu karar açısından anlamlı hâle getiren olay, risk snapshot’ının veya proposal’ın bu artefakta referans vermesidir.

Dolayısıyla çelişki yoktur: **manifestin içeriği türetilir, karar anındaki örneği mühürlenir.** Eski proposal böylece “bugünkü araştırma ne diyor?” sorusunu değil, “o karar verilirken sistem tam olarak ne biliyordu?” sorusunu güvenilir biçimde cevaplar.