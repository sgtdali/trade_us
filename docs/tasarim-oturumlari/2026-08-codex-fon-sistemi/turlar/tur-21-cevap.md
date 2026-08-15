En acil bulgu şu: mevcut altı tetikleyici filing tetikleyicisi değil, tarih alarmı. Kod `today >= due` olduğunda doğrudan `trigger_satisfied` üretiyor ([pei_workflow.py](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/src/adapter/pei_workflow.py:1575)); üstelik tarihler `next_events` içinde Yahoo kaynaklı ve varsayılan olarak `date_confirmed:false` ([us_pei_pack.py](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/scripts/us_pei_pack.py:552)). Dolayısıyla 26 Ağustos’ta CRM/NVDA sonucu gerçekten yayımlanmamış veya tarih değişmiş olsa bile sistem deep-dive’ı hazır hale getirebilir.

`date_due` ile `trigger_satisfied` aynı gerçek değildir:

```text
date_due
→ kaynak yenileme zamanı geldi

earnings_evidence_available
→ release/8-K/10-Q/10-K gerçekten bulundu

trigger_satisfied
→ beklenen kanıt yayımlandı ve trigger koşulunu karşıladı
```

26 Ağustos öncesindeki asgari güvenlik hükmü bu ayrım olmalı.

## 1. Asıl çekirdek döngü filing/olay döngüsü mü?

Evet. Keşif sistemin edinim döngüsü; filing/olay hattı ise işletim döngüsü.

Keşif olmadan başlangıçta izlenecek isim bulunmaz, fakat bir isim araştırmaya veya teze girdikten sonra yeni bilginin baskın kaynağı çeyreklik sonuçlardır. Üstelik bugün zaten altı `watch_until(earnings)` vakası var. Bu nedenle uygulama önceliğini değiştirirdim:

1. Olay/evidence kimliği ve gerçek yayın algılama.
2. Mekanik kontrol ve kaynak snapshot’ı.
3. `watch_until` vakalarının yeniden etkinleşmesi.
4. Açık tezlerin filing-driven güncellenmesi.
5. Sonra yeni keşif turlarının genişletilmesi.

Yani discovery ürünün giriş kapısı olmaya devam eder; fakat ilk tamamlanması gereken üretim döngüsü değildir. Mevcut altı vaka yeterli bootstrap kuyruğunu zaten sağlıyor.

Burada “filing-driven”ı yalnız 10-Q/10-K olarak da daraltmamalıyız. Yayımlanmış earnings release/8-K ilk kanıt olabilir; filing ve transcript daha sonra paketi tamamlayabilir. Takvim yalnız beklenen pencereyi söyler, kanıtın geldiğini değil.

## 2. Yeni çeyrek geldiğinde yetki sırası

Senin üçlü sıralamanda iki LLM çağrısını her tez için zorunlu kılan gereksiz bir tekrar var. Daha ucuz ayrım şu:

```text
Yeni earnings kanıtı
        │
        ▼
Deterministik ingestion + mekanik kontrol
        │
        ├─ Açık tez var ─────────> thesis-tracker lead
        │                            └─ gerekirse deep-dive support
        │
        ├─ Aktif/watch research_case ─> earnings-deep-dive lead
        │
        └─ İkisi de yok ─────────> issuer baseline güncellenir, LLM çağrılmaz
```

Yetki sınırları:

- Mekanik katman: “Ne yayımlandı, hangi dönem, hangi metrik değişti, kayıtlı eşiği geçti mi?” Kanıtı dondurur; yorum ve tez statüsü üretmez.
- Earnings-deep-dive: “Çeyrekte ekonomik olarak ne oldu; beat/miss’in kalitesi ne; guidance, KPI, EPS kalitesi ve transcript ne söylüyor?” Şirket/olay merkezlidir. Tez kaydını değiştiremez.
- Thesis-tracker: “Bu kanıt thesis_id=X’in hangi pillar’ını doğruladı veya bozdu; tez statüsü değişmeli mi; sonraki test ne?” Tez merkezlidir ve append-only lifecycle kaydının sahibidir.

Açık tezlerde tracker çoğu sıradan çeyreği doğrudan mekanik sonuç + kaynak paketiyle işleyebilir. Deep-dive ancak:

- earnings quality karmaşıksa,
- transcript/guidance yorumu belirleyiciyse,
- mekanik sinyaller çelişiyorsa,
- çeyrek önceden “tez için belirleyici olay” diye işaretlenmişse

support olarak çağrılır.

Böylece her açık tez için otomatik iki ağır oturum üretmeyiz. Skill sözleşmelerindeki örtüşme gerçek: deep-dive tez etkisini, tracker da `Post-earnings` modunu sahipleniyor. Lead+support ayrımıyla bu çift sahiplik daraltılmalı.

## 3. Tezsiz adayın earnings tetikleyicisi

Anlamlıdır; bu tam olarak `watch_until(trigger)` hükmüdür. Fakat kapatılmış vakayı yeniden açmak ile ilgisiz yeni vaka yaratmak arasında üçüncü yol gerekli:

```text
research_case_id: RC-NVDA-...
  episode_1:
    terminal_status: watch_until
    trigger_id: EARN-NVDA-...
    closed_at: ...

  episode_2:
    caused_by_trigger_id: EARN-NVDA-...
    prior_episode_id: episode_1
    lead_workflow: earnings_deep_dive
```

Aynı `research_case` kimliği korunur; yeni bir episode açılır. Eski terminal episode yeniden açılmaz, çünkü bu onun tarihsel hükmünü geriye dönük değiştirir. Tamamen yeni bağımsız case de açılmaz, çünkü “hangi soruyu bekliyorduk?” bağı kaybolur.

`watch_until` şu alanları taşımadan geçerli sayılmamalı:

- trigger kimliği ve beklenen kanıt;
- kanıt geldiğinde cevaplanacak araştırma sorusu;
- `not_before` veya event window;
- tarih kesinliği;
- trigger expiry/cancellation politikası;
- yeni episode’un varsayılan lead’i.

Mevcut altı waiting kaydı bu anlamda eksik ama kurtarılabilir. Özellikle tarih geldiğinde doğrudan deep-dive istemek yerine önce evidence refresh yapılmalı.

## 4. Preview ve deep-dive birlikte gerekli mi?

Falsifiability teşhisine katılıyorum; fakat çekirdek olması gereken şey full `earnings-preview` skill’i değil, sonuç öncesi dondurulmuş beklenti snapshot’ıdır.

Full preview skill’i varsayılan olarak kapsamlı, ağır bir hero rapor üretmek istiyor: expectation bar, KPI geçmişi, senaryolar, guidance credibility, call questions ve HTML çıktı ([earnings-preview](/C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/earnings-preview/SKILL.md:30)). Her açık tez için her çeyrek bunu üretmek 5–7 saat sınırını bozar ve tez sözleşmesindeki mevcut falsifier’ları tekrarlar.

Çekirdek olan daha dar sözleşme:

```text
pre_event_expectation_snapshot
  event_id
  thesis_id veya research_case_id
  frozen_at
  consensus/guide as_of
  3-5 thesis-linked KPI expectation
  confirm condition
  warning condition
  break condition
  unresolved question
  source_refs
```

Bunun sonucu:

- Açık tezlerde bu kısa snapshot ÇEKİRDEK; hindsight bias’ı önler.
- Tezsiz `watch_until` adayında aynı işi trigger contract zaten yapar; ayrıca full preview çoğunlukla gereksizdir.
- Full earnings-preview KOŞULLU kalır: beklenti barı karmaşıksa, kaynaklar çatışıyorsa veya sonuç belirleyici bir tez sınavıysa.
- Earnings-deep-dive sonuç sonrası event analysis için ÇEKİRDEK YETENEK, fakat her filing’de zorunlu çağrı değildir.

Bugünkü CRM/NVDA/NFLX/PEP preview’leri tamamen değersiz değil; frozen expectation üretmiş olmaları kıymetli. Ancak bunu yapmak için full preview artefaktı şart değildi.

## 5. Catalyst-calendar

Deterministik `next_events` ile catalyst-calendar aynı şey değil:

- `next_events`: beklenen earnings/dividend tarihleri ve kaynak durumu.
- Catalyst-calendar: tarih güveni, tez ilişkisi, etki, hazırlık işi, owner, karar baskısı ve earnings dışı düzenleyici/klinik/investor-day olayları.

Dolayısıyla skill sıfır değer katmıyor diyemeyiz. Fakat V1’de rutin calendar workflow’u olmamalı. Doğru sınıflandırma:

> `catalyst-calendar`: KOŞULLU; yalnız açık tez veya watch case birden fazla earnings-dışı, tarih-duyarlı katalizöre sahipse.

Kanonik trigger registry ve takvim mekaniği bizim deterministik katmanımızda kalır. Catalyst-calendar hiçbir zaman ikinci takvim otoritesi olmaz; yalnız kanonik registry’ye eklenmek üzere `catalyst_proposal` üretir. Tek bir earnings tarihi için çağrılması gereksizdir.

## 6. Economic-impact-report

Skill’in gerçek subject’i ticker veya tez değil, belirli bir dış olaydır:

```text
subject:
  type: external_event
  id: EVT-TARIFF-...

scope:
  universe_snapshot_id: ...
  sectors: [...]
  affected_security_ids: [...]
```

“Tema”yı subject yapmazdım; tema kimliği ve sınırı belirsizdir. Skill zaten genel tema değil, belirli politika değişikliği/makro şok/endüstri olayı → equity transmission map üretmek için yazılmış.

Fakat V1’de bunun yeri yok:

- otomatik dış olay ingestion’ı yok;
- bir olaydan N şirkete one-to-many etki üretir;
- mevcut ticker/thesis lifecycle’ının dışında ayrı bir lead workflow’dur;
- tek operatörün kapasitesini kolayca tüketir;
- çıktısındaki portföy eylem dili capital-policy sınırına yine çarpar.

Bu nedenle `economic-impact-report`: **V1’de GEREKSİZ**. Kullanıcı özel olarak bir şok analizi isterse lifecycle dışında ad hoc çalıştırılabilir; bunun ihtimali için V1 olay şemasına şimdiden `external_event` eklemek YAGNI olur.

## Net triyaj

| Skill | V1 hükmü |
|---|---|
| earnings-preview | KOŞULLU; çekirdek olan full skill değil pre-event expectation snapshot |
| earnings-deep-dive | ÇEKİRDEK YETENEK; watch-case post-print lead’i, tezlerde koşullu support |
| thesis-tracker | ÇEKİRDEK LIFECYCLE; açık tezde filing update lead’i |
| catalyst-calendar | KOŞULLU; kanonik olmayan öneri katmanı, ikinci takvim değil |
| economic-impact-report | GEREKSİZ |

En acil tasarım düzeltmesi skill seçimi değil: `date_due` geldiğinde trigger’ı “sağlandı” saymayı bırakmak. Şu an CRM ve NVDA için 26 Ağustos’ta yapılması gereken şey deep-dive çalıştırmak değil, önce gerçek earnings kanıtının yayımlandığını doğrulamaktır.