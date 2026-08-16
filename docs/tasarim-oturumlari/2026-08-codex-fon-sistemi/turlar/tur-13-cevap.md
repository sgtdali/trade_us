Evet, tespitin doğru ve Başlık 4 karar 5 doğrudan yanlış. Üstelik `docs/pei-workflow.md` içindeki “bir skill’den sahibi olmadığı bir hüküm istenmez” kuralını yine aynı tasarım çiğniyor.

Ben (c)’yi savunuyorum; (b)’nin yalnız mandate doğrulama kısmını alıyor, (a)’yı reddediyorum:

> Aylık portföy-geneli kararın sahibi insandır. Sistem kanonik paketi ve deterministik risk teşhislerini hazırlar. `portfolio-risk-management` yalnız insanın seçtiği tekil pozisyonlarda sizing/hedge derinleşmesi için opsiyonel çağrılır.

Bu yalnız V1 geçici çözümü değil; gerçek bir portföy-construction sahibi eklenene kadar doğru mimaridir.

### Üç alternatif

**(a) Her tez için ayrı sizing çağrısı yanlış.** Çünkü N tane tekil olarak makul karar birlikte uygulanabilir olmayabilir. Her isim portföyün %5’i için uygun görünebilir ama on iki önerinin toplamı nakit, sektör, faktör ve korelasyon sınırlarını aşabilir. Sonuçlar çağrı sırasına bağlı hâle gelir; ilk isimle son isim aynı başlangıç portföyüne bakmış olur. Ortak hedge’ler çift sayılabilir. Bu bir portföy çözümü değil, bağımsız yerel optimumlar listesidir.

**(b) Kısmen doğru.** Mandate’te gerçekten bulunan sert kurallar sistemde deterministik olarak uygulanmalı:

- Tek isim/segment/sector üst sınırı.
- Gross/net veya cash sınırı.
- Likidite/exit-day limiti.
- FX, benchmark ve restricted-list sınırları.
- Uzlaştırılmamış pozisyon veya bayat fiyat blokları.

Fakat bunlar allocator değildir; yalnız geçerlilik sınırlarıdır. Mandate’te olmayan “korelasyon 0,7’yi aşmasın”, “sektör %20 olsun”, “şu histerezisle rebalance et” gibi kuralları bizim icat etmemiz, tam da tasarımın kaçındığı sahte hassasiyettir. Korelasyon matrisi gösterilebilir; eşiği yoksa karar insanındır.

**(c) doğru.** Aylık oturumda sistem:

- Tüm açık tezleri ve beş ekseni,
- lot/exposure ve reconciliation durumunu,
- nakit ve para birimini,
- mandate ihlallerini,
- sektör/faktör/FX yoğunlaşmasını,
- likidite ve yaklaşan katalizörleri

tek pakette gösterir. İnsan global `add/trim/exit/no_change/re-underwrite` karar setini verir. Seçilen bir isimde “ne kadar?” veya “hangi hedge?” sorusu doğarsa `portfolio-risk-management` çağrılır.

Dolayısıyla katalog işi tamamen düşmez ama anlamı değişir: skill aylık rebalansın sahibi olarak değil, `position_sizing|hedge_design|integrated_risk_plan` için opsiyonel alt-workflow olarak eklenir. Aylık insan incelemesi skill entegrasyonunu beklemez.

Dokümandaki “skill tüm açık tezleri görür; giriş/çıkış/ağırlık yargısını verir” cümlesi de silinmeli. Mevcut skill bu hükmü vermiyor.

### Intended alpha / unwanted risk

Burada da haklısın. `long-short-pitch` skill’ini okudum: variant perception, expression, risk/reward, sizing considerations, disconfirmers ve monitoring üretiyor; fakat “intended alpha / exposure to retain / unwanted risk” ayrımını yapılandırılmış zorunlu çıktı olarak istemiyor.

Yani skill’in prose içinde buna değinmesi mümkün, ama repo’nun mevcut `pitch_verdict_thesis_and_rules` result contract’ı bilgiyi güvenilir biçimde saklamıyor. Asıl kayıp burada.

Teze ilk günden `exposure_intent` eklenmeli:

- `intended_alpha_driver`: Beklenen excess return’ün nedensel kaynağı.
- `exposures_to_retain`: Hedge edilirse tezi yok edecek maruziyetler.
- `known_unwanted_exposures`: Beta, sektör, faiz, FX, commodity, momentum/crowding gibi taşınan ama hedeflenmeyen riskler.
- `must_not_hedge`: Tezle ayrılmaz olduğu için korunmaması gereken exposure.
- `horizon_and_catalyst_link`
- Kaynak pitch, onay ve sürüm bilgisi.

Fakat iki katmanı ayırmak lazım:

- `intended_alpha` ve `exposures_to_retain` tez-yerel ve görece kalıcıdır.
- `unwanted_risk`in bir bölümü dinamiktir; pozisyon büyüklüğü, mevcut portföy ve piyasa rejimiyle değişir. Bu kısım risk değerlendirmesinde yeniden hesaplanır, tezin içine kalıcı gerçek gibi gömülmez.

Bir pitch intended alpha’yı söyleyemiyorsa `actionable_candidate` olmamalı; şirket iyi olabilir ama yatırımın neye oynadığı belli değildir. Buna karşılık bütün unwanted risk’lerin tez açılışında eksiksiz bilinmesini şart koşmazdım. Eksikler açıkça `unknown` kalır ve sizing/hedge kararını `not implementation-ready` yapar.

`exposure_intent` sonradan maddi biçimde değişirse de sıradan alan güncellemesi olamaz. “Eskiden AI capex büyümesine oynuyorduk, artık margin recovery’ye oynuyoruz” yeni kanıt değil, tezin değişmesidir; `changed/re-underwrite` gerektirir.

### Skill uyumu denetimi

| Skill | Tasarımın beklediği | Skill’in gerçekten yaptığı | Hüküm |
|---|---|---|---|
| `portfolio-risk-management` | Portföydeki bütün isimler arasında ağırlık dağıtımı/rebalans | Tek security/pozisyon için sizing, hedge veya birleşik risk planı; portföy yalnız kısıt girdisi | Uyuşmuyor |
| `thesis-tracker` | Haftalık tüm tezleri tarayan mekanik sağlık motoru ve sapma sonrası derin inceleme | Bir tezi/trackeri kanıtla güncelleme, pillar/status/action değerlendirmesi; portfolio-review modunda karar triage’ı | Derin incelemeyle uyuyor, mekanik taramayla uyuşmuyor |
| `idea-generation` | Dilim içi finalist seçimi ve selection-batch içinde A/B/C | Verilen universe/candidate setini araştırma önceliğine göre A/B/C/Reject sınıflandırma | Kullanılabilir ama ek sözleşme şart |

### Thesis-tracker hakkında dürüst hüküm

Skill, sapma sonrasındaki derin tez değerlendirmesi için çok iyi örtüşüyor. Şunları açıkça sahipleniyor:

- Orijinal underwriting’i koruma.
- Kanıt ekleme.
- Pillar ve KPI değerlendirmesi.
- Confirm/warning/break eşikleri.
- Company-thesis status ile security readiness’i ayırma.
- Add/trim/exit/re-underwrite önerisi.
- Append-only changelog.
- Eksik veri varsa `not decision-grade` deme.

Fakat haftalık mekanik taramayı sahiplenmiyor. Bütün açık tezleri LLM’siz dolaşmak, PIT observation’ları eşiklerle karşılaştırmak, qualitative review due tarihlerini izlemek ve monitoring-run coverage kapatmak repo’nun monitoring engine işidir.

Bu nedenle mevcut iki kademeli tasarım doğrudur:

1. Repo mekanik ve zamanlanmış kontrolleri çalıştırır.
2. Breach, indeterminate veya vadesi gelen nitel inceleme varsa tekil `thesis-tracker` çalıştırılır.

Buradaki açık iş “`thesis_tracker.pack_step` haftalık kontrolü beslesin” diye yazılmamalı. İki farklı paket gerekir:

- Küçük, deterministik `monitoring_snapshot`: mekanik motorun girdisi.
- Zengin `thesis_update_pack`: sapma sonrası tracker’ın girdisi.

Daha ciddi uyumsuzluk config’te: `thesis_tracker`, `required_workflows=["pitch"]` olan tek seferlik terminal candidate workflow gibi modellenmiş. Skill ise doğası gereği aynı tez üzerinde tekrar tekrar çalışan append-only update workflow’udur. Candidate zincirinden çıkarılıp `thesis_id` ile anahtarlanan, repeatable bir lifecycle workflow’u olmalı. Pitch yalnız ilk tezin köken kapısıdır; her sonraki tracker koşusunun prerequisite’i değildir.

Bir küçük enum sürtüşmesi de var: skill `retired`ı company-thesis status içinde kullanıyor. Bizim beş eksenli modelimizde closure ayrı lifecycle eksenidir. Adapter, skill çıktısındaki `retired`ı doğrudan company status’a yazmamalı; kapanış önerisi olarak adjudication’a götürmelidir.

### Idea-generation hakkında dürüst hüküm

Skill bir dilim üzerinde çalışabilir; “universe” kullanıcının verdiği aday kümesidir. Sektör, büyüklük, liquidity, data quality ve candidate ranking onun doğal alanında. Fakat iki turlu sistemi kendiliğinden bilmiyor. Orkestratörün şu sınırları koyması gerekir:

- Stage 1’de A/B/C domain bucket’ı yazılmaz; yalnız `nominated_for_selection` / `not_advanced` ve sıralı gerekçe yazılır.
- A/B/C yalnız donmuş `selection_batch` içinde üretilir.
- Her sonuç `comparison_set_id` taşır; başka batch’in A’sıyla mutlak olarak kıyaslanmaz.
- Skill’e portföy pozisyonları verilmez veya portfolio-fit boyutunun bu koşuda hüküm vermeyeceği açıkça söylenir; aksi hâlde saf keşif ilkesi bozulabilir.
- Pre-pitch aday için `thesis_tracker` downstream rotası kabul edilmez. Skill genel olarak tracker’a route edebilir ama repo’nun lifecycle invariant’ı bunu yasaklıyor.

Bir de tasarımdaki finalist “kotası” skill’le çelişiyor. Idea-generation açıkça “zayıf fikirleri agresif öldür, kısa ve keskin liste daha iyidir” diyor. Dolayısıyla dilim başına tam üç finalist değil, **en fazla üç finalist** olmalı. Zayıf dilim sıfır finalist üretebilir.

Bu, önceki yedek-listesi kararımızı da daraltıyor: bir finalist uygunsuz hâle gelirse sıradaki isim yalnız Tur 1’de advance eşiğini gerçekten geçtiyse yedekten alınabilir. Sırf kotayı doldurmak için dördüncü isim ilerletilemez.

### Genelleştirilebilir ders

Kataloğa alınacak her skill için artık şu sözleşme yazılmadan delegasyon yapılmamalı:

- Cevapladığı kesin soru.
- Kararın konusu ve kardinalitesi: ticker mı, tez mi, pozisyon mu, bütün portföy mü?
- Gerekli girdilerin hangi upstream adım tarafından üretildiği.
- Çıktı sözlüğü ve domain event’e nasıl dönüştüğü.
- Tek seferlik mi, repeatable mı?
- Yalnız öneri mi, state geçişi yetkisi var mı?
- Eksik girdide fail/conditional davranışı.
- Başka skill çıktılarıyla birleştirildiğinde ek bir gizli karar gerekip gerekmediği.

Son madde `portfolio-risk-management` hatasını doğrudan yakalardı: N tekil sizing çıktısını birleştirecek gizli portföy kararı kaldığı için delegasyon kapalı değildir.

Özetle: Başlık 4 karar 5 iptal edilmeli; thesis-tracker doğru yerde fakat yanlış lifecycle nesnesine bağlanmış; idea-generation kullanılabilir fakat Stage 1 sözlüğü, finalist üst sınırı ve batch-relative semantiği repo tarafından açıkça sınırlandırılmalı.