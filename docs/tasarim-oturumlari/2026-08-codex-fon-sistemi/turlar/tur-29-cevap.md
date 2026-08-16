Kısa hüküm: bu artık bir “skill orkestratörü” değil. Skill’leri analitik motor olarak kullanan, fakat doğruluğu ve sürekliliği kendi domain çekirdeğinde sağlayan bir araştırma operasyon platformu. Yazılım işinin kabaca %75–85’i skill çağırmanın dışında kalıyor.

## 1. Hiçbir skill’in sahiplenmediği işler

Boyut varsayımı: tek kişi, haftada 15–20 saat; küçük birkaç gün, orta 1–2 hafta, büyük 3–5 hafta. İşler paralel ve ortak altyapı kullandığı için süreler doğrudan toplanmamalı.

| # | Platform işi | V1 | Boyut | Başlıca bloke ettiği |
|---|---|---:|---:|---|
| F1 | **Domain sözlüğü ve kimlikler:** event/request/attempt/artifact, `security_id`, research case, episode, thesis, comparison set | Zorunlu | Orta | Defter, projection, dispatch, idempotency |
| F2 | **Kanonik SQLite olay defteri:** tek yazarlı transaction, atomik batch, V1 mühürleme/V2 lineage | Zorunlu | Büyük | Güvenilir bütün domain commit’leri |
| F3 | **Projection/read-model katmanı:** case, episode, thesis, monitoring, queue ve batch görünümleri | Zorunlu | Büyük | Dispatch, UI, monitoring ve replay |
| F4 | **Artefakt registry ve staging:** immutable yol, `artifact_id`, hash, schema/media/size, yetim artefakt kurtarma | Zorunlu | Orta | Pack/result bağlama ve crash recovery |
| F5 | **Research-case/episode orkestratörü:** lead kilidi, support bütçesi, request/attempt, retry, seri commit | Zorunlu | Büyük | Bütün skill çalıştırmaları |
| F6 | **Katalog + `contract_manifest`:** pack/output/validator/shared-policy/model sürümlerinin mühürlenmesi | Zorunlu | Küçük–Orta | Tekrarlanabilirlik ve plugin yükseltmeleri |
| F7 | **Pack builder mimarisi:** kanonik snapshot → yedi sürümlü pack recipe | Zorunlu | Büyük | Bütün analitik workflow’lar ve monitoring |
| F8 | **Direct structured sidecar + contract validator:** şema, cross-object invariant, mandate ve provenance kontrolleri | Zorunlu | Büyük | `workflow_completed`, pitch ve tracker güvenilirliği |
| F9 | **Evidence collector:** SEC `items`, 8-K Item 2.02, accession, release/filing kanıt yeterliliği | Zorunlu | Orta | 26 Ağustos deep-dive’ları ve event loop |
| F10 | **Trigger/window yöneticisi:** tahmini/doğrulanmış tarih, expected window, expiry, kanıt bekleme | Zorunlu | Orta | Preview, deep-dive, `watch_until` |
| F11 | **Tez lifecycle/materializer:** tez tanımı, monitoring contract, evidence/assessment/adjudication ayrımı | Zorunlu | Orta–Büyük | Tracker ve mekanik izleme |
| F12 | **Mekanik monitoring motoru:** typed rule değerlendirme, PIT/restate/adjustment semantiği | İlk tezden önce zorunlu | Orta | Sapma üretimi ve tracker dispatch |
| F13 | **Operatör yüzeyi:** P0–P4 kuyruk, pitch/monitoring adjudication, kaynak yan yana görünümü | Minimumu zorunlu | Büyük | Gerçek kullanım; aksi hâlde kapılar törene dönüşür |
| F14 | **Discovery/batch motoru:** snapshot, dilim, tam ticker muhasebesi, `unaccounted_for`, batch kapanışı | Tam V1 için zorunlu | Orta–Büyük | 87 isimlik yeni keşif döngüsü |
| F15 | **Portföy günlüğü ve reconciliation:** fill, broker snapshot, `position_unknown`, minimal split guard | Mevcut V1’e göre zorunlu; ilk kesme adayı | Büyük | Exposure gerçeği ve P0 kuyruğu |
| F16 | **Tutarlılık/kurtarma araçları:** replay kontrolü, orphan taraması, yarım attempt, hash uyuşmazlığı | Minimumu zorunlu | Orta | Güvenilir yeniden başlatma |
| F17 | **Eval/regresyon paketi:** sabit örnekler, plugin sürüm karşılaştırması, contract-pass ve insan-review ölçümü | Minimumu zorunlu | Orta | Plugin upgrade ve prompt değişikliği |
| F18 | **Çalıştırma izolasyonu:** writable staging sınırı, plugin sürüm pinleme, gerçek sandbox kontrolü | Zorunlu | Orta | Güvenli Codex çalıştırması |

Atladığın başlıca işler F1’deki security/case/episode kimlikleri, F5’teki gerçek orkestratör, F16’daki crash recovery ve F17’deki analitik regresyon setiydi.

V1’de **content-addressed blob deposu zorunlu değil**. F4 için immutable insan-okunur yol + `artifact_id` + SHA-256 yeterli. Blob depo hâlâ YAGNI.

Ana bloklama zinciri kabaca:

```text
F1 → F2/F3/F4/F6 → F5 → F7/F8 → F11 → F12/F13
                       F9 → F10 → deep-dive/tracker
F3 + F5 → F14
F1 + F2 + F3 + F13 → F15
```

En kritik teknik yol F1–F8’dir. Bunlar tamamlanmadan daha fazla skill eklemek yalnız daha fazla doğrulanamayan metin üretir.

## 2. Platform mı, orkestratör mü?

Bu sistemin doğru adı bence:

> **Plugin-backed research operations platform**

Skill’ler şunların sahibi:

- yatırım sorusunun analitik yöntemi;
- peer seçimi ve değerleme yorumu;
- earnings-quality muhakemesi;
- variant perception, red-team ve falsifier üretimi;
- yeni kanıtın tez açısından yorumlanması.

Platformun sahibi olduğu şeyler ise daha geniş:

- gerçeklik, kimlik ve zaman;
- hangi kanıtın gerçekten geldiği;
- modelin tam olarak ne gördüğü;
- çıktının sözleşmeyi karşılayıp karşılamadığı;
- hangi domain geçişinin önerildiği ve kimin onayladığı;
- yeniden çalıştırmanın duplicate üretmemesi;
- insanın bugün ne yapması gerektiği.

Yazılım geliştirme açısından skill entegrasyonu toplamın yaklaşık %15–25’i. Fakat kullanıcıya sunulan analitik değerde oran daha yüksek olabilir. Yani skill küçük bir kod parçası, ama önemli bir muhakeme parçası.

Mimari sonuç: domain olaylarında skill adı otorite olmamalı. Skill/provider yalnız provenance olmalı:

```text
Domain core ← sürümlü contract → analysis-provider adapter
                                      ├─ PEI plugin
                                      └─ yerel prompt
```

## 3. Güncellenmiş işletme kapasitesi

Dört aşamalı doğrulama ve monitoring motoru insan yükünü otomatik olarak artırmıyor; doğru kurulursa makine yükünü artırıp insan yükünü azaltıyor. On workflow olması da on workflow’un her hafta çalışacağı anlamına gelmemeli.

10–15 açık tez ve 87 isim için:

| Haftalık iş | Normal hafta |
|---|---:|
| Kuyruk, veri sağlığı, gecikmiş işler | 0,5–1 saat |
| Tez sapmaları ve vadesi gelen nitel incelemeler | 1–2 saat |
| Earnings kanıtı/deep-dive/tracker değerlendirmeleri | 1,5–3 saat |
| En fazla 1–2 aktif research case | 1,5–2,5 saat |
| Discovery’nin haftaya düşen amortize yükü | 0,5–1 saat |
| Minimal reconciliation varsa | 0,5–1 saat |

Yeni tahminim:

- **Normal hafta: 6–9 saat**
- **Yoğun earnings haftası: 10–14 saat**
- **87 ismi her hafta yeniden tarama veya ara çıktıları tek tek onaylama: 15+ saat; tasarım ihlali**

5–7 saat tahmini artık iyimser alt sınır. 6–9 saat daha dürüst.

Bunun çalışması için WIP sınırı şart:

- aynı anda en fazla 2 aktif research case;
- haftada en fazla 2–3 insan nitel tez incelemesi;
- pitch başına en fazla 1 otomatik support;
- discovery sürekli değil, ölçülmüş kadansta;
- `no_deviation` sonuçları insan kuyruğuna düşmez;
- preview her adayda değil, yalnız maddi pre-print ihtiyacında çalışır.

## 4. V1’i kurma süresi

Haftada 15–20 saat, mevcut SEC/XBRL kodu yeniden kullanılarak ve Claude/Codex yardımıyla:

- **Çalışan tek-ticker dikey dilim:** 8–10 takvim haftası
- **Dokümandaki mevcut tam V1:** 16–22 hafta
- **Bir gerçek earnings döngüsüyle sertleşmiş güvenilir V1:** 18–24 hafta

Claude/Codex şema, adapter ve test yazımını hızlandırır; olay anlamını, hata semantiğini, gerçek veriyle doğrulamayı ve operatör yüzeyini aynı oranda hızlandırmaz.

Mevcut tam V1 bence hâlâ fazla büyük. İlk sürümü şu şekilde keserdim:

1. **Portföy defteri ve reconciliation’ı V1.1’e atardım.**  
   V1 açıkça “portföy gerçeğinin sahibi değil” der; yarım portföy takibi yanlış güvenden daha kötüdür.

2. **Yeni discovery/batch motorunu sonraya bırakırdım.**  
   Mevcut shortlist veya elle açılan case’lerle lifecycle kanıtlanabilir.

3. **Preview, scenario, memo ve initiating coverage’ı ilk release’te disabled tutardım.**

4. **Tam web uygulaması yerine yerel statik HTML karar yüzeyi + dar komutlar kurardım.**  
   JSON okumayı kaldırır ama ürün geliştirme projesine dönüşmez.

5. **İlk çalışan skill setini beşe indirirdim:**  
   company-tearsheet, comps, pitch, earnings-deep-dive, thesis-tracker.

Bu kesilmiş V1’in hedefi:

```text
tek ticker
→ baseline
→ valuation anchor
→ pitch
→ insan adjudication
→ tez + monitoring contract
→ earnings evidence
→ deep-dive/tracker
→ governance-state adjudication
```

Bu sürüm yaklaşık **9–12 hafta** içinde gerçekçi. Ardından discovery ve portföy ayrı dikey dilimler olarak eklenebilir.

## 5. Eklentiye bağlı kalmaya değer mi?

Tam bağımlılık olarak hayır; sürümlü ve değiştirilebilir analitik kütüphane olarak şimdilik evet.

Eklentinin somut değeri:

- Pitch’te variant wedge, priced-in, adversarial case ve falsifier disiplinini hazır getiriyor.
- Deep-dive’da GAAP/non-GAAP, EPS quality, guidance, transcript ve estimate-revision ayrımlarını kapsıyor.
- Comps’ta peer rolleri, denominator uyumu, premium/discount mantığı ve desteklenmeyen değerleme sınırlarını taşıyor.
- Tracker’da kanıtı pillar/KPI/catalyst/kill kriterine bağlayan zengin bir düşünme modeli veriyor.
- Kaynak hiyerarşisi, tazelik ve eksik-veri davranışı için çok sayıda edge case barındırıyor.

Maliyeti de gerçek:

- HTML/workbook/portfolio-action/benchmark gibi bize uymayan kurumsal varsayımlar;
- büyük prompt/context yükü;
- plugin sürümü değişince davranış drift’i;
- makine-okunur sidecar yerine insan artefaktına öncelik vermesi;
- bizim override ve adapter katmanını taşımak zorunda olmamız.

Kendi altı promptumuzu yazmak teknik olarak mümkün. Fakat bunu şimdi yapmak V1’e yaklaşık 2–4 hafta daha ekler ve analitik edge-case bakımını tamamen bize geçirir.

Benim önerim:

- 0.1.31’i pinle.
- Domain çekirdeğini plugin’den bağımsız kur.
- İlk V1’de yüksek-yargılı dört/beş skill’i kullan: pitch, deep-dive, tracker, comps ve gerekirse idea-generation.
- Tearsheet ve dar preview’in ileride yerel prompt/deterministik raporla değiştirilmesine açık ol.
- Her workflow için birkaç sabit vaka üzerinde plugin ile yerel ince promptu karşılaştır: contract-pass oranı, olgusal hata, yasak action üretimi, insan adjudication süresi ve maliyet.

Son hüküm:

> Eklentiyi bırakmak için henüz kanıt yok; eklentiyi mimarinin temeli yapmak için de yok.

Onu değiştirilebilir bir analitik sağlayıcı olarak tutmak bugün en ucuz ve en güvenli konum.