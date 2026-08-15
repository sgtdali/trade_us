Kararım net: tarih yalnızca kontrolü başlatmalı; kanıt accession tabanlı olarak gözlenip artefakt olarak alınmadan tetikleyici tatmin edilmiş sayılmamalı. Araştırma tarafında ise security başına tek açık vaka, vaka içinde ardışık episode’lar olmalı.

1. Kanıtın geldiğini nasıl bileceğiz?

Tek başına hem en erken hem sıfır yanlış-negatifli bir sinyal yok. V1 için en iyi denge iki aşamalı SEC gözlemidir:

- `earnings_release_observed`: Son gözlemden sonra yeni bir SEC accession’ı görülür ve yerli ihraççı için `form=8-K`, `item=2.02` koşulunu karşılar.
- `earnings_evidence_available`: Bu accession’ın asıl belgesi veya earnings exhibit’i başarıyla alınmış, içerik artefaktı hash’lenmiş ve erişilebilir durumdadır.

Birincisi metadata sinyali, ikincisi kullanılabilir kanıttır. Deep-dive ancak ikincisinde açılmalıdır. Repo zaten ham submissions verisindeki Item 2.02’yi doğru ayırıyor [us_pei_pack.py](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/scripts/us_pei_pack.py:1583) ve release kanıtını accession/hash ile tanımlayabiliyor [evidence.py](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/src/adapter/evidence.py:152). Fakat `FilingRef`, SEC’in `items` alanını düşürüyor [models.py](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/src/adapter/models.py:8); doğru bilgi typed gözlem katmanına taşınmıyor.

XBRL’de yeni `period_end`, daha geç gelen `normalized_actuals_available` seviyesidir; ilk deep-dive’ı 10-Q’ya kadar bekletmemelidir. Konsensüs actual yalnızca destekleyici sinyal olmalı, kanonik kanıt değil. İnsan teyidi ise 8-K/6-K/PDF gibi otomatik yolun yakalayamadığı istisnaların fallback’idir.

Dolayısıyla tetikleyici şunu taşımalı:

```text
expected_event
accepted_evidence_kinds
baseline_accession
issuer_filing_regime
expected_window
```

`trigger_satisfied`, bunlardan tanımlanmış asgari kanıt seviyesi karşılandığında üretilmelidir. “Hiç yanlış-negatif” ancak SEC dışı IR sayfaları ve 6-K rejimi de izlenirse yaklaşılabilecek bir hedeftir; yalnız Item 2.02 ile garanti edilemez.

2. Tarih geçti ama kanıt yoksa

`expected_window` önerine katılıyorum. Ancak ±14 gün evrensel gerçek değil, `date_status=estimated` için V1 politika varsayımı olmalı. Doğrulanmış tarihin penceresi daha kısa olabilir.

Akış şöyle olmalı:

```text
scheduled
→ expected_window_open
→ awaiting_evidence
→ satisfied
         ↘ window_expired
```

Her başarısız günlük kontrolde domain olayı yazılmaz. Kontrol denemeleri ayrı operasyonel kayıt olarak `checked_at/result` tutar. Domain defterine yalnız anlamlı geçişler girer:

- pencere açıldı,
- kanıt bulundu,
- pencere kanıtsız kapandı.

`window_expired` bir kez P2 öğesi doğurur. Böylece “bekleniyor” ile “unutuldu” ayrılır ama günlük olay gürültüsü oluşmaz.

3. Research case / episode modeli

Subject ticker değil `security_id` olmalıdır; ayrıca şirket düzeyi bağ için `issuer_id`, okunabilirlik için de o andaki ticker snapshot’ı tutulur. Ticker değişebilir, güvenlik kimliği değişmemelidir.

V1 invariant’ı:

> Bir `security_id` için aynı anda en fazla bir açık `research_case` ve onun içinde en fazla bir aktif episode bulunur.

Yeni sinyaller ikinci vaka açmaz:

- Açık vakaya yeni keşif sonucu gelirse kanıt olarak eklenir.
- Vaka `watch_until` durumundaysa earnings kanıtı aynı vakada yeni episode açar.
- Aktif episode sırasında maddi earnings kanıtı gelirse eski episode `interrupted_by_material_evidence` ile kapanır; yeni earnings episode’u açılır ve eski çalışma support evidence olarak taşınır.
- Vaka daha önce `declined` ile kapanmışsa sonraki tur yeni bir vaka açabilir; eski vaka `prior_case_id` ile bağlanır.

Burada önceki terminolojimizi de düzeltmek gerekiyor: `ready_for_pitch / watch_until / declined / blocked` dört vaka terminali değildir; episode disposition’larıdır.

- `ready_for_pitch`: episode biter, aynı vakada pitch episode’u açılır.
- `watch_until`: vaka kapanmaz, askıya alınır.
- `blocked`: vaka kapanmaz, çözüm bekler.
- `declined`: vaka gerçekten kapanır.

Tez konusunda sana katılıyorum: adjudicated pitch tez açtığında araştırma vakası kapanır, tez ayrı lifecycle nesnesi olarak başlar. Bu iki gerçek tek transaction’da yazılmalıdır:

```text
research_case_closed(outcome=thesis_opened, thesis_id=...)
thesis_opened(origin_case_id=...)
```

4. Dört hükmü kim verir?

Lead skill yalnızca `proposed_disposition` üretir. Lifecycle hükmünü ya açık bir deterministik politika ya da insan verir.

- `ready_for_pitch`: kontrat geçerliyse otomatik kabul edilebilir; yalnız pitch kuyruğuna koyar, çalıştırmayı insan tetikler.
- `watch_until`: cevaplanacak soru, kanıt türü, pencere ve expiry eksiksizse otomatik kabul edilebilir. Eksikse `blocked/manual_review`.
- `blocked`: yalnız kayıtlı, nesnel blocker kodlarında sistem tarafından verilebilir; serbest metinli analitik belirsizlik otomatik blocker olamaz.
- `declined`: mutlaka insan kararı olmalıdır.
- `thesis_opened`: mevcut kararımız gereği yine insan kapısıdır.

Bu kapı her Stage 1 `not_advanced` sonucu için geçerli değildir; yalnız açılmış research case’in kapatılması için geçerlidir. Böylece yüzlerce eleme onayı üretmeyiz.

5. Altı legacy `waiting_for_trigger`

Üç seçenek arasında doğru olan kontrollü göçtür; fakat altısını aynı kalitedeymiş gibi çevirmek yanlış olur.

Önce eski `date_due` tetikleyicileri 26 Ağustos’tan önce `superseded` olarak etkisizleştirilmeli. Ardından V2 kayıtları eski `event_id`’lere açıkça referans vermeli; V1 geçmişi değiştirilmemelidir.

- CRM, NVDA, PEP ve NFLX: earnings-preview çıktılarında expectation bar, KPI ve falsifier soruları var. Bunlar kaynak gösterilerek `watch_until` episode’una taşınabilir.
- META ve AMZN: dayanakları modelsiz, daha önce `diagnostic_only` diye yeniden sınıflandırdığımız scenario çıktılarıdır. Bunları otomatik olarak geçerli watch sözleşmesine yükseltmek doğru olmaz. P2’ye bir kerelik adjudication düşmeli: insan geçerli soruyu tanımlar veya vakayı kapatır.
- Altısında da `date_status=estimated`, kanıt gereksinimi ve pencere açıkça yazılmalı; türetilemeyen alan `legacy_missing` olarak görünür kalmalıdır.

Hepsini iptal etmek mevcut preview’lerdeki değerli önceden yazılmış beklentiyi kaybettirir; legacy bırakmak ise doğruladığımız yanlış otomatik ateşlemeyi korur. Körlemesine `unknown` ile göç etmek de eksik sözleşmeyi geçerliymiş gibi aklar. Kontrollü, provenance’lı göç bu yüzden tek tutarlı yol.