Kararım: `memo-builder` gereksiz değil, koşullu bir dönem-sonu sentez aracıdır; `user-context` ise V1 workflow’larında gerçekten kullanılmamalıdır. Şemsiye skill çalıştırılacak bir workflow değil, sürümlü runtime standardıdır. Plugin’in analitik standartlarına uymalı, kurumsal sunum varsayımlarını ise açıkça override etmeliyiz.

## 1. Eleme kümesi

### `memo-builder`: GEREKSİZ → KOŞULLU

Memo, P0-P4 kuyruğunun veya adjudication ekranının yerini tutamaz:

- Kuyruk “şimdi hangi işi yapmalıyım?” sorusunu cevaplar.
- Karar ekranı “bu öneriyi kabul ediyor muyum?” sorusunu cevaplar.
- Memo “bu dönemde görüşlerimiz neden ve nasıl değişti?” sorusunu cevaplar.

Dolayısıyla memo güvenlik yüzeyi değil, retrospektif sentez yüzeyidir. Skill de kendisini trade construction sahibi değil, formal written synthesis sahibi olarak tanımlıyor [memo-builder](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/memo-builder/SKILL.md:36).

V1’de yeri şöyle daraltılmalı:

```text
role: optional presentation/meta
subject_type: coverage_cycle | review_period
trigger: explicit human request
inputs: yalnız kabul edilmiş olaylar ve projection’lar
authority: hiçbir lifecycle durumunu değiştiremez
allowed_next: yok
```

Örneğin ay veya coverage cycle sonunda tek bir “research-book review” üretilebilir. Sol/high maliyeti nedeniyle otomatik kadans koymazdım; operatör ihtiyaç duyarsa çağırır. Bu nedenle çekirdek değil, koşullu.

### `user-context`: GEREKSİZ, hatta olağan workflow’da yasak

Bu skill mandate enjeksiyon standardı değil. Kendi `$CODEX_HOME/state/...` alanında plugin-local hafıza, onboarding, connector tercihi ve otomasyon ayarı yönetiyor. Kendi talimatı da ordinary workflow’ların onu çağırmamasını açıkça söylüyor [user-context](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/user-context/SKILL.md:8).

Repo’daki kanonik bağlam ayrı kalmalı:

```text
runtime_context:
  mandate_snapshot_ref + hash
  capital_policy_ref | null
  source_policy
  workflow_contract
  artifact_policy
  operator_preferences_ref
```

Bunu her çağrıya repo tarafından sürümlü olarak enjekte etmek doğru. User-context’ın kaynak kategorisi isimlerinden yararlanabiliriz; skill’i çalıştırmak veya onun hafızasını okumak gerekmez.

## 2. Şemsiye ve shared katman

### Mevcut prompt yeterli mi?

Hayır, iyi niyetli ama denetlenebilir değil. Şu an prompt “skill’in referans verdiği shared dosyaları da oku” diyor [pei_workflow.py](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/src/adapter/pei_workflow.py:893). Bunun üç sorunu var:

- Hangi conditional referansların gerçekten okunacağı belirsiz.
- Çalışmadan sonra hangi sözleşmelerin uygulandığını kanıtlayamıyoruz.
- Plugin güncellendiğinde aynı workflow sessizce farklı kurallarla çalışabilir.

Her work item kesin bir `contract_manifest` taşımalı:

```text
plugin_id/version
lead_skill_path + sha256
mandatory_shared_contracts[] + sha256
semantic_references[] + sha256
orchestrator_overrides[]
artifact_policy
support_policy
```

Öncelik sırası da açık olmalı:

```text
mandate ve ürün sınırı
> work-item instructions
> orchestrator kontratı
> focused skill
> plugin shared varsayılanları
```

### `invocation-policy` bize ne söylüyor?

Bu bir analiz sözleşmesi değil, plugin’e giriş kapısıdır. Public-equity niyeti yoksa plugin’i kullanma; varsa lead’i seç ve gerekirse insan-facing artifact politikasını çöz, diyor.

Bizim orchestrator zaten açıkça PEI workflow seçtiği için bu kapı her çağrıda yeniden çalıştırılmak zorunda değil. Katalog/iş talebi oluşturulurken bir kez uygulanması yeterli. Per-run mandatory dosya yapmazdım.

### `support-layer-routing-contract` bize ne söylüyor?

Bu doğrudan zorunlu. Üç önemli hükmü var:

- Support bir owning workflow altında çalışır.
- `owning_workflow`, `decision_impact`, `readiness_effect`, `artifact_role` ve görünürlük durumunu taşır.
- Support yatırım hükmünün sahibi olamaz [support-layer-routing-contract](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/shared/support-layer-routing-contract.md:55).

Bu, bizim lead dondurma kuralımızla tam uyumlu. Hatta bizimki daha güçlü: support lead’i değiştiremez, vakayı kapatamaz ve lifecycle disposition üretemez.

Support kullanılan her episode’da bu kontrat açıkça manifest’e girmeli; yalnız skill’in referans zincirine bırakılmamalı.

### Şemsiye skill’in somut rolü

Orchestrator lead’i zaten seçtiği için şemsiyenin router rolüne çalışma anında ihtiyacımız yok. Faydalı kısmı Cross-Skill Runtime Contract:

- kaynak kategorileri ve source honesty,
- güçlü kaynağın zayıf kaynakla sessizce ikame edilmemesi,
- as-of/provenance,
- user-context’ın ordinary workflow’da çalışmaması,
- lead/support sahipliği,
- ortak yatırımcı dili.

Bu nedenle şemsiye katalogda “çekirdek workflow” olmamalı. Doğru sınıfı:

```text
role: runtime policy dependency
executable: false
pack_step: yok
result_contract: yok
```

Routing playbook ve map ise per-run LLM kararı değil, katalog/orkestrasyon tasarım girdisidir. Model bunlardan handoff önerisi çıkarabilir ama lead’i değiştiremez.

## 3. HTML hero artefaktı istiyor muyuz?

Her adımda kesinlikle hayır. `deliverable-intake-policy` yalnız lead’in yeni ve substantive bir insan-facing artefakt ürettiği durumda uygulanıyor [deliverable-intake-policy](C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/shared/deliverable-intake-policy.md:3). Embedded support veya makine tarafından tüketilecek analiz bunun kapsamına girmiyor.

Ancak bunu örtük bırakmamalıyız. Non-interactive çalışmada skill’ler aksi belirtilmezse full HTML’e kayıyor. Her work item açık artefakt politikası taşımalı:

```text
artifact_mode: internal_analysis
required: result.md + structured_result
forbidden: standalone_html, docx, xlsx
```

V1’de önerdiğim ayrım:

| Çalışma | Varsayılan yüzey |
|---|---|
| Tearsheets, comps support, preview, deep-dive support | Markdown + structured sidecar; HTML yok |
| Thesis mekanik kontrolü | Yalnız structured sonuç |
| Tracker’ın olağan güncellemesi | Markdown + structured assessment; ayrı HTML yok |
| Stage 2 batch karşılaştırması | Bir adet HTML triage raporu yararlı olabilir |
| Pitch → tez adjudication | İnsan karar yüzeyi gerekli; HTML veya sistem ekranı |
| P0-P4 kuyruğu | Sistem tarafından üretilen tek ortak UI |
| Dönem-sonu sentez | İnsan isterse memo-builder |
| Kullanıcının açıkça istediği standalone rapor | Skill HTML’i + HTML standardı |

Yani “her skill kendi HTML’ini üretsin” yerine, yapılandırılmış sonuçlar merkezi karar yüzeyine akar. HTML yalnız karşılaştırma veya insan hükmünü gerçekten kolaylaştırdığında üretilir.

`html-artifact-standard`ı tamamen reddetmiyoruz; HTML seçildiyse zorunlu oluyor. Yalnız HTML seçimini plugin’in default’una bırakmıyoruz.

## 4. Shared standartları nasıl sınıflandırırım?

### Zorunlu analitik sözleşmeler

- Focused skill’in `SKILL.md`’si ve semantic output referansları.
- Şemsiyenin Cross-Skill Runtime Contract’ı.
- `pm-judgment-heuristics.md`: variant wedge, priced-in, falsifier, downside ve missing evidence disiplini.
- Support kullanılıyorsa `support-layer-routing-contract.md` ve `equity-research-support-standard.md`.
- Comps/scenario/değerleme varsa `equity-valuation-pm-standard.md`.
- Kaynak önceliği, as-of, provenance ve zayıf kaynak ikamesi kuralları.
- Repo’nun mandate ve ürün-sınırı override’ları.

Bunlar analiz kalitesini doğrudan değiştirir.

### Yalnız belirli bağlamda zorunlu

- `invocation-policy`: vaka/workflow kabul kapısında.
- `plugin-routing-playbook/map`: katalog ve episode planlama zamanında.
- `deliverable-intake-policy`: yeni insan-facing hero artefakt oluşturulurken.
- `final-deliverable-framework`: kullanıcıya bağımsız bir paket teslim edilirken.
- `html-artifact-standard`: HTML gerçekten seçilmişse.
- `workbook-artifact-standard`: XLSX gerçekten seçilmişse; V1’de çoğunlukla devre dışı.
- `memo-builder`: insan dönem-sonu sentezi istediğinde.

### Güvenle override edilecek veya kullanılmayacak olanlar

- Her substantive non-interactive koşuda otomatik polished HTML üretme varsayımı.
- Her adımda `Full working analysis`; derinlik workflow bütçesince belirlenmeli.
- Benchmark, active weight, position action gibi mevcut mandate/V1’de bulunmayan alanların zorunluluğu.
- Plugin-local `user-context`, onboarding ve otomasyon state’i.
- Katalog dışında support çağırma veya support’un kendi support zincirini açması.
- Capital policy yokken add/trim/hedge/sizing hükümleri.
- Dış dolaşım/client/committee readiness ve publication packaging standartları.

Özetle eklentiyi bir kurum olarak taklit etmemeliyiz; onun yatırım muhakemesi ve kanıt disiplinini almalıyız. Sunum bürokrasisi, dağıtım yüzeyleri ve portfolio varsayımları ise bizim ölçeğimize ve ürün sınırımıza göre açıkça daraltılmalı. Bu, skill’leri beklemedikleri girdilerle çalıştırmak değil; shared sözleşmelerin kendi “embedded support” ve “human-facing artifact” ayrımlarını doğru uygulamaktır.