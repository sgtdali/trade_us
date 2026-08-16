Ana düzeltme: görünürlük yalnız skill adına göre belirlenemez; **`(skill, execution_role, requested_capability, assessment_mode)`** bileşimine göre belirlenir. Aynı `economic-impact-report` kör driver analizi yaparken portföyü görmez, portföy etkisi overlay’i yaparken sınırlı exposure görebilir.

## 1. Fon görünürlüğü matrisi

| Skill / rol | Kabul edilmiş araştırma state’i | Fonlanmış bilgisi | Ağırlık / sermaye riski | Portföy bağlamı |
|---|---:|---:|---:|---:|
| `idea-generation` | Hayır | Hayır | Hayır | Hayır |
| `company-tearsheet` | Yalnız önceki baseline güncelleniyorsa | Hayır | Hayır | Hayır |
| `comps-valuation` | Önceki anchor yalnız update/challenge modunda | Hayır | Hayır | Hayır |
| `long-short-pitch` | Baseline, valuation, downside ve kanıtlar | Hayır | Hayır | Hayır |
| `earnings-preview` | Tez ve izlenecek beklentiler | Hayır | Hayır | Hayır |
| `earnings-deep-dive` | Önceki expectation, tez, downside, anchor | Hayır | Hayır | Hayır |
| `thesis-tracker` | Tez, monitoring contract, yeni kanıt | Hayır | Hayır | Hayır |
| `scenario-sensitivity` | Base case ve varsayımlar | Hayır | Hayır | Hayır |
| `catalyst-calendar` | İzleme yükümlülükleri | Gerekirse `funded/watchlist` | Hayır | Hayır |
| `economic-impact-report` — driver analizi | Driver hipotezi ve security listesi | Hayır | Hayır | Hayır |
| `economic-impact-report` — portfolio overlay | Mühürlü driver analizi | Evet | Security/driver exposure | Yalnız ilgili cluster |
| `portfolio-risk-management` | Tez, downside ve risk sorusu | Evet | Mevcut ağırlık, önerilen band, risk bütçesi | İlgili limitler ve exposure |
| `memo-builder` | Kabul edilmiş bütün girdiler | Evet | Read-only | Read-only; domain yetkisi yok |
| Model/initiation escalation’ları | Gerekli araştırma artefaktları | Hayır | Hayır | Hayır |

`portfolio-risk-management` bile P&L, ortalama maliyet veya “bu pozisyonda zarardayız” bilgisini varsayılan olarak görmemeli. Bunlar sizing sorusunu cevaplamak için gerekli değildir ve sunk-cost yanlılığı üretir. Vergi veya icra sorusu açıkça bunu gerektirirse ayrı overlay olur.

**Sahiplik yanlılığı gerçek risktir.** Bir deep-dive’a “82 bp sermaye risk altında” demek downside analizini iyileştirmez; modeli pozisyonu savunmaya teşvik eder. Sermaye büyüklüğü orkestratörün öncelik, assurance ve maliyet kararında kullanılır; analitik prompta verilmez. Ciddiyet, `decision_deadline` ve `reliance_class` ile anlatılır.

## 2. Pack’in kuruluşu

Yedi araştırma pack’i korunur; bunların her biri için fon varyantları çoğaltılmaz. Çalışma pack’i üç katmandan bileşir:

```text
research_job_pack
= capability’ye ait araştırma pack’i
+ karar sorusu bağlamı
+ visibility policy’nin izin verdiği opsiyonel fund overlay
```

Fon overlay profilleri kapalı tutulmalı:

- `none`
- `funded_flag_only`
- `position_context`
- `portfolio_exposure_context`

`capital_input_manifest` bütünüyle prompta verilmez. Pack recipe yalnız soruyla ilgili bileşenleri seçer. Örneğin downside refresh:

- thesis version
- ilgili falsifier’lar
- yeni kanıt
- mevcut downside — yalnız assessment mode gerektiriyorsa
- ağırlık, NAV, P&L ve portfolio proposal — verilmez

Anchoring için üç assessment modu yeterli:

- `de_novo`: Önceki hüküm gösterilmez.
- `update_against_prior`: Tracker gibi, değişimi ölçmek için önceki hüküm zorunludur.
- `independent_then_reconcile`: Yeni downside/valuation önce eski sonuç gösterilmeden üretilir; ikinci geçişte mevcut kabul edilmiş nesneyle farkı açıklanır.

Pitch `de_novo`, tracker `update_against_prior`, karar-kritik downside/valuation refresh ise tercihen `independent_then_reconcile` çalışır.

## 3. Contract manifest ve provenance

Mevcut `contract_manifest`e şunlar eklenmeli:

```text
research_work_request_ref
work_episode_id
requested_capability
required_output_contract
execution_role
reliance_class
assessment_mode
fund_visibility_profile
context_redaction_policy_version
model_input_manifest_ref
operating_authority_ref
```

`capital_at_risk` tekrar kopyalanmamalı; request referansından bulunur. Daha önemlisi, request’te bulunması promptta göründüğü anlamına gelmemelidir.

İki ayrı kanıt gerekir:

- `contract_manifest`: hangi kurallar, skill, plugin sürümü ve görünürlük politikası uygulandı?
- `model_input_manifest`: model tam olarak hangi artefaktları ve alanları gördü?

Sonuç artefaktının registry kaydı şunları referanslar:

```text
request_id
episode_id
attempt_id
contract_manifest
model_input_manifest
plugin/skill/model sürümleri
validator_report
```

Adjudicate edilmiş `downside_case` veya `valuation_anchor` bu ayrıntıları içine kopyalamaz. Yalnız:

```text
proposed_by_artifact_ref
accepted_via_adjudication_event_id
```

taşır. Böylece domain nesnesi plugin’den bağımsız kalır; provenance zincirden bulunur.

## 4. Oturum sürekliliği

Varsayılan kural: **her episode taze oturumla başlar**.

Resume yalnız aynı episode içinde kullanılabilir:

- Lead’in support sonrası devamı
- Aynı sorunun teknik retry’ı
- Görünürlük profili ve kontratı değişmeyen devam attempt’i

Şunlar taze oturum zorunlu kılar:

- Yeni sermaye sorusu
- Yeni episode
- `de_novo` veya blind challenger geçişi
- Fon görünürlüğünün artması ya da azalması
- Skill/kontrat/plugin sürümü değişikliği
- Önceki pitch çerçevesinin tracker’a taşınması riski

Özellikle portföy bağlamı görmüş bir thread daha sonra “blind” çalıştırılamaz; model bilgiyi unutmuş sayılamaz. Tracker geçmişi session’dan değil, explicit thesis/evidence bundle’dan alır. Bundle her zaman yeterlidir; resume yalnız episode-içi optimizasyondur.

## 5. Model ve maliyet

`capital_at_risk` doğrudan model seçmemeli. “82 bp → xhigh” gibi bir eşleme yapay kesinlik ve gereksiz maliyet üretir.

Model politikası şu sırayla belirlenmeli:

1. `reliance_class`: screen / research / decision-support / governance-changing
2. Analitik karmaşıklık ve kanıt çatışması
3. Lead veya support rolü
4. Sonucun geri döndürülebilirliği
5. Son olarak sermaye riski ve deadline

Sermaye riski esas olarak bir **assurance tier** yükseltir:

- Daha güçlü model gerekebilir.
- Independent challenger pass gerekebilir.
- Validator daha sertleşir.
- İnsan adjudication’ı daha ayrıntılı olur.
- İş kuyrukta öne çıkar.

Fakat sermaye tutarı modele gösterilmez. Sıradan discovery daha ucuz modelle çalışabilir; fonlanmış pozisyonun downside yenilemesi decision-grade olabilir. Bunun gerekçesi “82 bp büyük” değil, **çıktının sermaye artırma/azaltma kararında kullanılacak olmasıdır**.

Kısacası: fon bağlamı skill’e varsayılan olarak verilmez. Sermaye bilgisi önce orkestratörün önem ve güvence kararını etkiler; yalnız analitik soru gerçekten gerektiriyorsa kontrollü overlay olarak modele açılır.