## 1. Yedi turun özeti

Fon ile skill sistemi tek bir sağlayıcı-bağımsız sınır üzerinden konuşur: fon bir skill istemez, `downside_case.v1` gibi bir karar girdisi ister. Araştırma orkestratörü uygun lead/support akışını çalıştırır; çıkan artefakt doğrulanır ve iki aşamalı insan adjudication’ından geçmeden sermaye girdisi olamaz. Kabul edilmiş tez, readiness, downside, valuation, driver ve monitoring sürümleri karar anında `capital_input_manifest` içinde mühürlenir; deterministik motor yalnız bu kanonik girdiyi görür. Açılış pozisyonları geçici `legacy_hold_only` statüsünde tutulur; araştırma eksikliği risk artışını engeller fakat tek başına satış gerekçesi olmaz. Uygulamada önce manuel producer ile bu sınır kanıtlanacak, ardından aynı sözleşmeye ilk olarak `comps-valuation` adapter’ı bağlanacaktır.

## 2. Fon–skill sınırı

```text
FON TARAFI                                      ARAŞTIRMA TARAFI

Fon olayı / karar ihtiyacı
        │
        ▼
research_work_request ───────────────────────► Router
(domain capability ister)                       │
                                                ▼
                                         research_case / episode
                                                │
                                      lead ─── support
                                                │
                                                ▼
                                         provisional artefakt
                                                │
                          contract + kaynak doğrulaması
                                                │
                                                ▼
                          İNSAN KAPISI — Aşama 1
                    Araştırma hükmü sermaye etkisi
                           gösterilmeden yargılanır
                                                │
                                                ▼
                          Kanonik, sürümlü capital input
                                                │
                                                ▼
capital_input_manifest ◄────────────────────────┘
        │
        ▼
Deterministik risk/proposal motoru
        │
        ▼
İNSAN KAPISI — Aşama 2
Portföy etkisi ve sermaye kararı
```

- Temel nesneler: `research_work_request`, `research_case/episode/attempt`, provisional artefakt, `contract_manifest`, `model_input_manifest`, adjudication olayı, sürümlü capital-input bileşenleri ve mühürlü `capital_input_manifest`.
- Fon hangi cevaba ihtiyaç duyduğunu söyler; hangi skill’in çalışacağına araştırma orkestratörü karar verir.
- Modele gösterilecek fon bağlamı kapalı profillerle belirlenir: `none`, `funded_flag_only`, `position_context`, `portfolio_exposure_context`.
- Sermaye miktarı ve beklenen işlem etkisi araştırma modeline gösterilmez; yalnız öncelik ve assurance seviyesinde kullanılır.
- İnsan her teknik adımı sürmez: işi başlatır, araştırma hükmünü adjudicate eder ve sermaye kararını ayrıca verir.
- Plugin kapatıldığında muhasebe, NAV, policy, risk, proposal, icra ve denetim doğru çalışmaya devam eder; yalnız yeni araştırma üretimi ve güncellemeler kaybedilir.

## 3. Önceki kararlarla tutarlılık

- **Lead + support modeli geçerli:** Fonun `research_work_request` üretmesi yalnız yeni bir talep kaynağıdır; lead seçimi, support çağrıları ve episode yapısı araştırma orkestratöründe kalır.
- **Katalog v2 geçerli ama genişler:** Capability/output contract, görünürlük profili, assessment mode, request/episode referansları ve assurance politikası eklenir; `allowed_next` geri gelmez.
- **İnşa sırası değişti:** Manuel capital-input üretimi ve adjudication, risk motorunun önüne taşındı; sağlayıcı-bağımsız orkestrasyon ve gerçek skill adapter’ları daha sonra gelir. Eski “kötü de olsa fon” eşiği anlam olarak değişmedi, yalnız adım numarası kaydı.
- **`capital_input_manifest` tutarlı:** Dördüncü turdaki “adjudicated capital input” kavramının somut paketidir; yeni bir otorite veya ikinci defter değildir. Bileşenler ve adjudication olayları otoritatiftir, manifest karar anında bunlardan türetilip mühürlenir.
- **LLM’siz fon çekirdeği korunuyor:** Manuel producer yolu, plugin’in zorunlu bağımlılığa dönüşmesini engeller.

## 4. Bugünkü somut adım

Entegrasyon koduna henüz başlanmamalı; önce dört blokaj sorusu cevaplanmalı ve fon omurgası kurulmalıdır. Fakat beklerken şu hazırlık yapılabilir:

1. `research_work_request.v1`, `downside_case.v1`, `adjudication_decision.v1` ve `capital_input_manifest.v1` sınırlarını taslak olarak dondur.
2. Tek bir security için insan tarafından yazılmış downside-case fixture’ı hazırla.
3. Bu fixture’ın doğrulama, iki aşamalı adjudication ve manifest oluşturma kabul kriterlerini yaz.
4. Görünürlük matrisi ile `contract_manifest`/`model_input_manifest` ayrımını kayda geçir.
5. Plugin çağrısı, router veya on workflow’luk katalog uygulamasını fon omurgası ve manuel sınır testi tamamlanana kadar başlatma.

## 5. Son söz

En kolay ve en tehlikeli yanlış anlama, “skill çıktısı fona girdi olur” cümlesidir. Olmaz: yalnız doğrulanmış ve insan tarafından bağımsız biçimde adjudicate edilmiş domain nesneleri fona girdi olabilir. Gelecekte biri `skill result → risk engine` kestirmesi yaparsa bütün güvenlik mimarisi çöker. Entegrasyonun başarı ölçütü plugin’i çağırabilmek değil, plugin’i söktüğünde fonun doğru kalması ve aynı sözleşmeye başka bir producer takılabilmesidir.