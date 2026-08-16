`reconciliation_required` önerimi geri çekiyorum. İtirazın doğru: bu, reddedilmiş “her çakışmayı insana sor” politikasını başka adla geri getirirdi.

Aktif zincirdeki isim taramaya katılmalı; yeni screen, zincirin state’ini veya rotasını değiştirmeden evidence olarak eklenmeli. Zincir pitch’e kadar yürümeli ve pitch hem önceki araştırmayı hem arada gelen screen sinyallerini tartmalıdır. Bu, ölçek açısından daha iyi.

Tek şartım şu: aynı Codex session’ında devam etmek tek başına yeterli değil. Yeni idea screen başka bir oturumda üretildiği için ticker session’ı onu kendiliğinden bilmez. Resume edilen her sonraki adıma, son adımdan beri oluşmuş ticker olayları açıkça enjekte edilmeli. Pitch’e ulaşılamayan `route_unsupported` zincirlerde screen evidence değerlendirilmeden kalabilir; fakat bu, her screen için insan uzlaştırması gerektirmez—zaten mevcut operasyonel blocker’ın parçasıdır.

## Fonlama olayı

Tamamen katılıyorum ve burada daha keskin bir ayrım yaparım: işlem kaydı bulunmaması “fonlanmamış” demek değildir. Yalnız “sistemde kayıtlı pozisyon yok” demektir.

Gerçek işlemler de aynı `events.jsonl` içinde bulunmalı. Örneğin `portfolio_transaction_recorded` olayı; işlem türü, ticker, `thesis_id`, gerçekleşme zamanı, yön, adet, fiyat, para birimi, masraf ve insan onayını taşımalı. Haricî broker işlem kimliği varsa idempotency anahtarı odur; yoksa kullanıcı tarafından verilen işlem kimliği gerekir. Aynı işlemin ikinci kez girilmesi reddedilir.

Ama bu bile “insan işlemi kaydetmeyi unuttu” problemini çözmez. Dış dünyadaki gerçeği yalnız iç olaylarla kanıtlayamayız. Bunun için ayrıca `portfolio_reconciled` gibi bir olay gerekir: “şu tarih itibarıyla bu hesap/portföy, şu kaynak veya insan teyidiyle uzlaştırıldı.” Böylece sistem üç farklı şey söyleyebilir:

- `open_position`: kayıtlı ve uzlaştırılmış sıfır olmayan pozisyon
- `confirmed_flat_as_of`: belirtilen tarih itibarıyla uzlaştırılmış sıfır pozisyon
- `position_unknown`: defter güncel değil veya hiç uzlaştırılmamış

Aylık rebalans `position_unknown` durumunu “fonlanmamış” diye yorumlamamalı; portföy girdisini güvenilmez saymalıdır. Gerçek para tarafındaki sessiz sapmayı tamamen engellemenin tek yolu broker entegrasyonu veya düzenli insan uzlaştırmasıdır. Salt işlem yokluğundan güvenilir bir negatif sonuç türetilemez.

## Haftalık mekanik kontrol

Burada da senin tarafındayım: her kontrol iz bırakmalı. Yalnız sapma olaylarını kaydedersek “kontrol edildi ve temiz çıktı” ile “üç haftadır hiç çalıştırılmadı” birbirinden ayrılamaz.

Bunu iki seviyede kaydederdim. Önce haftalık run, o anda kontrol edilmesi gereken tezlerin sabit manifestini ve kullanılan veri snapshot’ını taşır. Ardından her tez için bir `thesis_check_completed` olayı oluşur. Sonucu en az şu dört değerden biri olur:

`no_deviation | deviation | indeterminate | data_missing`

`no_deviation` da kalıcı olaydır; `indeterminate` hiçbir zaman sessizce “temiz” sayılmaz. Yalnız `deviation` yeni bir `thesis_tracker` incelemesi tetikler; `data_missing` ise veri boşluğu veya manuel kontrol gereksinimi üretir. Run sonunda beklenen tezlerin kaçının gerçekten kontrol edildiğini gösteren kapanış olayı bulunur. Böylece yarım kalmış haftalık kontrol de görünür olur.

Mekanik kontrolü doğrudan `thesis_tracker.pack_step` içine sıkıştırmazdım. Tracker derin yorum sahibidir; haftalık mekanik karşılaştırma ayrı, daha küçük bir monitoring snapshot kullanmalı. Tez açılırken her ölçülebilir eşik normalize bir metrik kimliğine ve veri kaynağına bağlanır. Haftalık süreç, bütün açık tezlerin ihtiyaç duyduğu metrikleri `market.py`, `live_pack.py`, `point_in_time.py` gibi mevcut kaynaklardan tek snapshot’a toplar; her kontrol olayı bu snapshot’ın hash’ini ve as-of tarihlerini referanslar.

`thesis_tracker` için pack ancak sapma sonrası derin inceleme açıldığında üretilir. Böylece sessiz haftalarda LLM çalışmaz ama denetim izi eksiksiz kalır.

## Tez, geçerlilik, tavsiye ve pozisyon

Bu dört gerçeği dört boolean olarak saklamazdım. Üç temel gerçeklik ekseni, PEI’nin mevcut iki yargı ekseni ve bir türetilmiş izleme kuralı kullanırdım:

| Eksen | Değerler |
|---|---|
| `thesis_lifecycle` | `active`, `wind_down`, `closed`, `superseded` |
| `company_thesis_status` | `untested`, `strengthening`, `intact`, `watch`, `impaired`, `broken`, `changed` |
| `security_readiness` | `ready`, `conditional`, `re_underwrite`, `not_decision_grade` |
| `recommended_action` | `add`, `press`, `hold`, `trim`, `exit`, `hedge`, `wait_for_proof`, `re_underwrite` |
| `actual_exposure` | `long`, `short`, `flat`, `unknown`; adet ve uzlaştırma tarihiyle |

`monitoring_required` bağımsız yazılabilir bir state olmaz. Şu kuralla türetilir:

> Tez `active/wind_down` ise veya gerçek exposure sıfır değilse izleme zorunludur. Exposure bilinmiyorsa izleme zorunlu ve portföy kararı blokludur.

`retired` kelimesini şirket tezinin geçerlilik ekseninden çıkarırdım. Bu, lifecycle’ın `closed` projection etiketi olabilir. Çünkü “tez intact iken idari nedenle kapatıldı” ile “tez broken olduğu için kapatıldı” bilgisini kaybetmemeliyiz.

Birinci somut hâl şöyle görünür:

```text
thesis_lifecycle      = wind_down
company_thesis_status = broken
security_readiness    = re_underwrite veya not_decision_grade
recommended_action    = exit
actual_exposure       = long
monitoring_required   = true
```

Tez kırılması otomatik olarak `closed` yapmaz. Önce `wind_down` olur; insan satana kadar risk ve çıkış uygulaması izlenir. Uzlaştırılmış exposure sıfıra geldiğinde `wind_down → closed` geçişi yapılabilir.

İkinci hâl ise:

```text
thesis_lifecycle      = active
company_thesis_status = intact
recommended_action    = koşula göre wait_for_proof/add/hold
actual_exposure       = flat
monitoring_required   = true
```

İnsanın tamamen satması tezi otomatik kapatmaz. Yoğunlaşma, likidite, vergi veya göreli fırsat nedeniyle sıfırlanmış ama hâlâ geçerli bir tez, fonlanmamış açık tez olarak aylık rebalansta yeniden değerlendirilebilir.

Temel yasaklar da bunlardan çıkıyor:

`closed` veya `superseded` tez yeniden açılamaz; yeni görüş yeni `thesis_id` gerektirir. Kapalı teze bağlı yeni alış yapılamaz. `broken` tezde `add/press` önerisi bulunamaz. `wind_down → closed`, normal koşulda yalnız uzlaştırılmış exposure `flat` olduğunda mümkündür. `closed/superseded` ve sıfır olmayan exposure birlikte bulunursa sistem bunu normal durum değil, açık bir bütünlük ihlali veya zorunlu override olarak göstermelidir. Son olarak, yalnız işlem kaydı bulunmamasından `flat` türetmek yasaktır; bunun için başlangıç teyidi veya portföy uzlaştırması gerekir.

Bu modelde “tez kırıldı” entelektüel hüküm, “exit önerildi” PM hükmü, “satıldı” gerçek-dünya olayı, “izleme bitti” ise ancak bunların uygun birleşiminden türeyen sonuç olur. Tek `retired` kelimesinin taşıyamadığı ayrım tam olarak bu.