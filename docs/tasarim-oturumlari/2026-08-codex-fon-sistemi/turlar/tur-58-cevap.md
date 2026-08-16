Evet: arayüz skill’den önce kurulmalı. Hatta yalnız Adım 8’i ikiye bölmek yetmez; **manuel capital-input yarısı risk motorundan önceye taşınmalıdır.** Aksi hâlde risk motoru, hesaplaması gereken readiness/downside girdilerinin yalnız ileride kurulacak plugin’den gelebileceğini varsayar ve bağımsızlık testi bozulur.

## 1. Revize inşa sırası

| Yeni adım | İçerik |
|---:|---|
| 0 | Fon tanımı, capital policy ve validation spec |
| 1 | Kanonik finansal defter |
| 2 | Açılış kitabı ve broker importer |
| 3 | NAV ve temel performans |
| **4 — yeni** | **Provider-bağımsız capital-input substrate:** manuel authoring, validation, iki aşamalı adjudication, sürümlü bileşenler ve `capital_input_manifest` |
| 5 | Deterministik risk motoru |
| 6 | Portfolio proposal ve karar kapısı |
| 7 | İcra köprüsü ve operasyon yüzeyi |
| 8 | Attribution ve hesap verebilirlik |
| **9 — eski Adım 8’in ikinci yarısı** | `research_work_request`, routing, episode, provenance, görünürlük ve provider-neutral orkestrasyon |
| 10 | İlk skill adapter’ı ve gölge koşu |
| 11 | Pitch–tez–tracker/deep-dive lifecycle’ı |
| 12 | Discovery ve ölçekleme |

“Kötü de olsa fon” eşiğinin anlamı değişmez: icra köprüsü tamamlandığında oluşur. Yalnız numarası 6’dan 7’ye kayar.

## 2. En küçük entegrasyon dilimi

İki aşamada yapılmalı.

### A. Skill’siz sınır testi

Canned fixture veya insan-authored bir `proposed_downside_case`:

```text
proposed_downside_case
→ schema + contract validator
→ Aşama A research adjudication
→ accepted downside_case
→ capital_input_manifest
→ risk engine
→ downside_capacity_weight
```

Bu test plugin olmadan geçmelidir. Böylece skill adapter’ı bozulduğunda domain sınırının çalıştığı bilinir.

### B. İlk gerçek sağlayıcı testi

Senin önerdiğin uçtan uca hat doğru, fakat bir şartla: tek downside case, tek başına nihai `policy_compliant_max_weight` üretemez. Fixture’da tez, readiness ve diğer gerekli girdiler önceden kabul edilmiş olmalı; yalnız downside eksik bırakılmalı. Ayrıca downside kısıtı gerçekten binding olacak şekilde test verisi kurulmalı.

Başarı ölçütü:

> Skill’den gelen öneri kabul edilmeden hiçbir şeyi değiştirmiyor; kabul edildiğinde exact manifest değişiyor ve aynı girdilerle risk motoru aynı yeni tavanı üretiyor.

## 3. İlk hangi skill?

**İlk adapter `comps-valuation` olmalı.**

Neden:

- Dar ve iyi sınırlanmış bir capability üretir: `valuation_anchor`.
- Tez gerektirmez; legacy pozisyon üzerinde çalışabilir.
- Kaynak, peer, dönem, metrik ve sayısal tie-out deterministik olarak ciddi ölçüde doğrulanabilir.
- Lifecycle açmaz veya kapatmaz.
- Pitch/tracker’dan daha ucuz bir yerde pack, provenance, validation ve adjudication hatalarını gösterir.
- Kabul edilen anchor, güncel market snapshot ile capital actionability hesabına girebilir.

Sıra şöyle olmalı:

1. `comps-valuation` — plumbing kanıtı  
2. `long-short-pitch` — ilk yüksek-yetkili/onboarding underwrite  
3. `thesis-tracker` — tez açıldıktan sonra lifecycle  
4. `earnings-deep-dive` — gerçek event-evidence desteği  
5. `company-tearsheet` — gerektiği ölçüde support/yerel deterministik alternatif  
6. `idea-generation` — en son

Tracker/deep-dive’ın ilk olması gerçekten tavuk-yumurta üretir: tracker’ın tezi, deep-dive’ın ise anlamlı bir expectation/thesis bağlamı yoktur. Pitch’i ilk adapter yapmak ise fazla geniştir; entegrasyon tesisatıyla analitik kaliteyi aynı anda debug ettirir.

## 4. `legacy_hold_only` normalleşmesi

`onboarding_underwrite` mantıklıdır; fakat yeni bir sermaye kestirmesi veya ikinci tez açma yolu olmamalıdır. Bu bir **requested capability / pitch execution mode** olur, ayrı skill olmaz.

Amaç tam bir initiation raporu üretmek değil, aynı kanonik minimum nesneleri üretmektir:

- Kısa, test edilebilir thesis
- Ana falsifier’lar
- Downside case
- Savunulabilir asgari valuation anchor
- Driver eşlemesi
- Monitoring contract
- Bilinen veri boşlukları

Kural:

> Sunum genişliği azaltılabilir; kanıt standardı azaltılamaz.

Onboarding underwrite:

- İnsan-authored veya pitch lead tarafından üretilebilir.
- Aynı validation ve iki aşamalı adjudication’dan geçer.
- Ancak kabul edilince tez açar.
- En fazla `starter` readiness verebilir.
- `core` veya risk artırımı için normal karar-grade underwrite gerekir.
- Eksik anchor/downside varsa pozisyon `legacy_hold_only` kalır; otomatik satılmaz ve artırılamaz.

Sekiz pozisyon aynı anda çalışılmaz. Risk altındaki sermaye, yaklaşan event ve mevcut hard-limit yakınlığına göre sırayla onboarding yapılır. Böylece geçici istisna gerçek bir geçiş planına dönüşür.

## 5. Süre tahmini

Fon omurgası ve artefakt deposu hazır kabul edilirse:

| İş | Kısmi zaman tahmini |
|---|---:|
| Manuel capital-input substrate, şemalar, manifest materializer | 1–2 hafta |
| İki aşamalı adjudication yüzeyi ve human-authored lineage | 1–2 hafta |
| Request/routing/episode/kuyruk projection’ı | 1–2 hafta |
| Görünürlük, provenance, session ve regresyon testleri | 1–2 hafta |

Ortak işler örtüştüğü için toplam: **4–7 hafta**.

İlk dar skill adapter’ı:

- `comps-valuation`: **4–7 iş günü**
- İlk pitch/onboarding adapter’ı: ayrıca **1,5–2,5 hafta**
- Tracker veya deep-dive: mevcut ortak altyapıdan sonra yaklaşık **1–2 hafta/adet**

En kritik uygulama kararı şu: önce manuel/hard-coded producer ile sınırı kanıtla; sonra aynı output contract’a plugin’i tak. Plugin’i ilk producer yaparsan, hata çıktığında bunun domain sözleşmesinden mi, orkestrasyondan mı, prompttan mı yoksa skill’den mi geldiğini ayıramazsın.