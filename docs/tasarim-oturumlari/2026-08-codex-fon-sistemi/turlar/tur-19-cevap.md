Gerçek koşu verisi önceki triyajımı kısmen değiştiriyor; fakat asıl mahkûm ettiği şey triyaj değil, mevcut rota mekaniği.

Önce küçük ama önemli bir düzeltme: verdiğin 12/9/6 sayıları workflow çağrısı değil, olaylarda geçen workflow sayıları. Bir tamamlanmış çalışma `workflow_prepared + result_attached + workflow_completed` olmak üzere üç olay üretiyor. Fiilî tamamlanmış işler: 4 earnings-preview, 3 initiating-coverage, 2 tearsheet, 2 scenario. Altı earnings-deep-dive henüz çalışmadı; [events.jsonl’deki altı `waiting_for_trigger`](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/events.jsonl:52) yalnızca geleceğe programlandı.

## 1. Initiating coverage: rota kazası değil, politika kazası

VZ, ADBE ve ABBV için `initiating-coverage` önerisi eşleyicinin uydurması değil. Idea-generation çıktısında üçü için de açıkça yazılmış: [ABBV](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/events.jsonl:4), [ADBE](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/events.jsonl:5), [VZ](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/events.jsonl:14). İlk anda `mapped_workflow=null` olmasının sebebi skill’in katalogda bulunmaması; sonradan katalog eklenince aynı öneriler yeniden eşlenmiş.

Önerinin kendisi de anlamsız değil:

- ABBV için ürün bazlı patent/zirve satış ve risk ayarlı NPV,
- ADBE için AI kohort ekonomisi ve normalleştirilmiş marj,
- VZ için abone ekonomisi ve borç azaltma köprüsü

bir tearsheet’in cevaplayacağı temel profil soruları değil. Skill de kendini “tez-led, model-backed, valuation-aware tam underwrite” olarak tanımlıyor; trade pitch olmadığını ayrıca söylüyor ([initiating-coverage](/C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/initiating-coverage/SKILL.md:38)).

Dolayısıyla önceki `GEREKSİZ` hükmümü geri çekiyorum: `initiating-coverage` **KOŞULLU** olmalı. Koşulu da dar:

> Mevcut issuer baseline + hedefli destek çalışmaları adayın şirket-geneli underwrite sorununu cevaplayamıyorsa ve operatör pahalı bir hero artefaktı bilinçli olarak seçiyorsa.

Hata, skill’in önerilmesi değil; idea-generation’ın danışmanlık niteliğindeki `next workflow` önerisinin otomatik yürütme emri sayılması. ABBV gibi B adayında tam initiation başlatmak özellikle açık bir maliyet kapısı gerektirir.

Earnings-preview ise sık çalışmış olsa da hâlâ koşullu: koşulu yaklaşan sonuç tarihidir. Bir koşulun bu batch’te dört kez gerçekleşmesi onu evrensel ön koşul yapmaz.

## 2. Pitch’e ulaşamama: gerçek arıza GOOGL/MSFT zincirinde görülüyor

Lead+support modeli tek başına yetmez; ayrıca “aktif araştırmaya alınan her vaka terminal bir araştırma hükmüne ulaşır” invariantı gerekir.

GOOGL ve MSFT bunun en temiz kanıtı:

1. Idea-generation ikisini de `comps`a yönlendirmiş: [GOOGL](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/events.jsonl:8), [MSFT](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/events.jsonl:10).
2. `comps.required_workflows=["tearsheet"]` olduğu için sistem comps yerine önce tearsheet hazırlamış; olayda `workflow=tearsheet`, `requested_workflow=comps` açıkça duruyor: [GOOGL](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/events.jsonl:20), [MSFT](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/events.jsonl:21).
3. Tearsheet kendi `next_route`’unda earnings-preview önerince kod “taze öneriyi” asıl `requested_workflow`un önüne geçirmiş ve comps kaybolmuş: [GOOGL](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/events.jsonl:30), [MSFT](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/events.jsonl:31).

Yani destek adımı, kendisini isteyen lead’in amacını ele geçiriyor. Bu tam olarak düz zincirin eklenti modelini bozduğu yer.

Ben şu kuralı koyardım:

> Bir `research_case` açıldığında `lead_workflow` ve amaç sabitlenir; support çıktıları kanıt ve handoff önerisi üretir ama lead’i değiştiremez veya vakayı kapatamaz.

Her A ve aktif araştırmaya alınmış B vakası şu terminal hükümlerden birine ulaşmalı:

- `ready_for_pitch`
- `watch_until(trigger/date)`
- `declined`
- `blocked`

Her adayın mutlaka pitch üretmesi gerekmez. Initiation `watch_until` veya `declined` ile vakayı kapatabilir; `ready_for_pitch` derse yeni pitch lead’i açılır. Tez açma yetkisi yine yalnız adjudicated pitch’te kalır.

## 3. Comps: hükmümü değiştiriyorum

`comps-valuation` V1 için **ÇEKİRDEK YETENEK**, fakat her ticker’da zorunlu çağrı değildir.

Sebep yalnız teorik değil: gerçek koşuda GOOGL ve MSFT için comps açıkça istenmiş, fakat prerequisite tarafından yutulmuş. “Hiç çalışmadı” kullanım eksikliği değil, orkestrasyon hasarı.

Senin temel itirazına da katılıyorum: DCF ve üç-tablo modeli V1 dışında bırakılıyorsa, comps sistemin en ucuz ve tekrar kullanılabilir değerleme çıpasıdır. Pitch skill’i de mevcut fiyatın ne ima ettiğini açıkça istemektedir ([comps sözleşmesi](/C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/comps-valuation/SKILL.md:34)).

Ama doğru hard requirement `comps_completed` değil, şudur:

> Karar niteliğindeki pitch, kaynaklı ve güncel bir `valuation_anchor` taşımalıdır.

Bunu çoğu standart şirkette comps karşılar. Emsal karşılaştırmasının anlamsız olduğu özel durumlarda tarihsel own-range, piyasanın ima ettiği beklenti, senaryo/SOTP veya başka uygun yöntem karşılayabilir. Hiçbiri savunulamıyorsa pitch `valuation_not_supported` demeli ve `actionable_candidate` üretememelidir.

## 4. Idea-generation’ın katalog kimliği

Burada `subject_type` ile `scope` alternatif değil; ikisi farklı işi yapar.

- `subject` işin kimliğini ve yaşam döngüsü sahibini taşır.
- `scope` karşılaştırma sınırını ve provenance’ı taşır.

Örneğin:

```text
subject:
  type: selection_batch
  id: SB-...

parent:
  coverage_cycle_id: CC-...

scope:
  universe_snapshot_id: ...
  member_ids_hash: ...
  as_of: ...
  slice_id: ...

output_cardinality: many
```

Katalog tanımı da `accepted_subject_types: [screen_slice, selection_batch]` diyebilir. Yalnız `scope` kullanmak idempotency ve olay ilişkilendirmesinde “bu çalışma neyin çalışmasıydı?” sorusunu cevapsız bırakır; yalnız `subject_type=batch` kullanmak ise hangi dondurulmuş üyelerin karşılaştırıldığını söylemez.

## 5. Tearsheet ne zaman bayatlar?

Tearsheet için tek bir son kullanma tarihi yanlış olur; artefakt farklı hızlarda eskiyen bileşenlerden oluşuyor:

- Şirket kimliği, iş modeli ve segment yapısı: yeni 10-K, büyük M&A/spin, segment değişikliği veya başka maddi olayla geçersizleşir.
- Finansallar ve KPI’lar: daha yeni 10-Q/10-K/earnings release bilinir olduğunda bayatlar.
- Fiyat, piyasa değeri, EV ve çarpanlar: yalnız kendi `market_as_of` anında geçerlidir.
- Tartışma, katalizör ve risk okuması: yeni maddi kanıt geldiğinde yeniden değerlendirilir.

Bu yüzden yeni fiyat geldi diye bütün tearsheet yeniden çalışmamalı. Kanonik `issuer_baseline`, dayanıklı tearsheet çekirdeği + güncel deterministik finansal snapshot + güncel market snapshot olarak oluşturulmalı. LLM tearsheet ancak yapısal/analitik okuma gerçekten geçersizleştiğinde yeniden çalışmalı.

Dolayısıyla daha önce konuştuğumuz `(workflow, completed_at, data_stamp)` üçlüsü tearsheet için biraz daha ayrıştırılmalı; tek `data_stamp` yerine en azından `structural_as_of`, `financials_known_at/period_end` ve `market_as_of` gerekir.

## 6. Financials-normalizer: otorite konusunda katılıyorum, kapsam sonucunda ayrılıyorum

Deterministik repo hattı kapsadığı bütün alanlarda tek otorite olmalı. LLM normalizer’ın SEC/XBRL değerini değiştirmesi, onunla çatışan ikinci bir “doğru” üretmesi veya kanonik pack’e doğrudan yazması yasak olmalı.

Fakat “deterministik hat otoritedir” sonucu otomatik olarak “skill’in hiçbir işi yoktur” sonucunu vermiyor. Çünkü mevcut deterministic kapsama tam değil. Örneğin [non_gaap.py](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/src/adapter/non_gaap.py:21) bugün esas olarak issuer-reported EBITDA ve net debt seçiyor; skill sözleşmesi ise değişen KPI tanımları, segment köprüleri, consensus/provider export’ları ve karmaşık disclosure karşılaştırmalarını da kapsıyor ([financials-normalizer](/C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/financials-normalizer/SKILL.md:35)).

Bu nedenle nihai sınıflandırmam:

> `financials-normalizer`: **KOŞULLU İSTİSNA DESTEĞİ**, normal otomatik rota değil.

Koşul: kanonik boru hattının kabul etmediği dağınık bir dış kaynak, değişmiş KPI tanımı veya disclosure köprüsü gerçekten gerekiyorsa. Çıktısı `normalization_proposal` olur; kanonik gerçek değildir, insan adjudication’ı olmadan pack’e girmez. Aynı istisna tekrar ediyorsa çözüm skill’i tekrar çağırmak değil, deterministik mapping/producer eklemektir.

Eğer V1 kapsamı açıkça “yalnız deterministik hattın desteklediği veriyle çalış; eksik kalan analiz bloklansın” diye daraltılırsa, o zaman sen haklısın ve skill V1 için `GEREKSİZ` olur. Ben şimdilik bu kadar sert bir ürün sınırının kararlaştırıldığını görmediğim için koşullu tutuyorum.

Kısacası güncellenmiş üç hükmüm: initiating-coverage `GEREKSİZ → KOŞULLU`, comps `KOŞULLU → ÇEKİRDEK YETENEK`, financials-normalizer `KOŞULLU ama yalnız kanonik olmayan istisna şeridi`. En büyük bulgu ise triyajdan bağımsız: mevcut sistem destek adımına lead’in amacını değiştirme yetkisi veriyor; gerçek koşuda comps’u yutan şey tam olarak bu.