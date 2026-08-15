Önce sıkıştırdığın nokta: **(a)’yı savunuyorum, fakat bir düzeltmeyle.**

V1’de `thesis_opened`, “sermaye karşılaştırmasına kabul” değil, **“resmî, kanıt ağırlıklı ve izlenebilir yatırım görüşü oluştu”** demeli. Capital policy yazılana kadar sistem tezleri sıralamaz, ağırlık önermez veya sermaye tahsis etmez.

Ancak insan kendi kararıyla gerçek alım yaparsa işlem sistem dışında bırakılmamalı; teze bağlanarak kaydedilmeli ve uzlaştırılmalı. Sistem bu alımı önermemiş olur ama gerçek pozisyona kör kalmaz. Bu nedenle (b) fazla katı ve operasyonel olarak daha tehlikeli.

Başlık 3’ün ödenmemiş çeki V1’de gerçekten ödenmeyecek; bu açıkça kabul edilmeli. Capital policy gelince sermaye karşılaştırması ayrı bir yetenek olarak eklenir.

## 1. İlk yedi tura göre ne değişti

- **`thesis_opened`:** “Sermaye karşılaştırmasına kabul kapısı” → “Resmî ve izlenmeye başlayan araştırma görüşü”; sermaye uygunluğu future capital policy’nin ayrı hükmü olacak.

- **Beş tez ekseni:** Beş kalıcı eksen → iki otoritatif gerçek ve bir tarihli değerlendirme: sade tez durumu, ayrı portföy exposure gerçeği, süreli aksiyon değerlendirmesi.

- **`wind_down`:** Elle yönetilen lifecycle ekseni → `broken thesis + non-flat exposure` birleşiminden türetilen durum.

- **`actual_exposure`:** Tez ekseni → broker/portföy defterinden gelen ayrı gerçek.

- **`recommended_action` ve `security_readiness`:** Kalıcı tez durumu → belirli tarihli, süresi dolabilen assessment sonuçları.

- **`superseded`:** Gelecekte kullanılacak lifecycle değeri → V1’den çıkarıldı; yeni görüş eski tezin kapanması ve yeni `thesis_id` ile temsil edilecek.

- **Başlık 4 karar 5:** Aylık portföy inşasını `portfolio-risk-management` skill’ine devretme → iptal; skill yalnız açık risk bütçesiyle hedefli tek-pozisyon sizing için kullanılabilir.

- **“Aylık rebalans”:** Aylık yeniden tahsis oturumu → aylık portföy gözden geçirmesi; varsayılan sonuç `no_change`, işlem için yeni kanıt veya açık sermaye kısıtı gerekir.

- **Mandate modeli:** Tek `mandate.json` bütün araştırma ve portföy kararlarını yönetir → `research_mandate` ile henüz yazılmamış `capital_policy` ayrılmalı.

- **`analysis_proposed` / `analysis_reviewed`:** Her analitik çıktı için iki olay → geri çekildi; ara çıktılar immutable artefakt ve makine doğrulamasıyla ilerler, insan adjudication’ı yalnız pitch→tez, izleme sözleşmesi ve para sınırlarında kalır.

- **`analysis_accepted`:** Her workflow için genel kabul olayı → yalnız domain sonucu doğuran kritik kapılarda kullanılan adjudication olayı.

- **Stage 1 sözlüğü:** A/B/C bastırılıp yalnız `nominated/not_advanced` yazılması → skill’in A/B/C/Reject hükmü korunur ama `slice_id/comparison_set_id` ile kapsamlandırılır; nomination bundan türetilir.

- **Tur/dilim mekaniği:** Tam coverage round kapanışı, waived dilimler ve zorunlu Stage 2 → V1’de ertelendi; kayan batch’ler ve kapsamlı değerlendirmeler yeterli.

- **Tez eşiği çıkarımı:** AGY’nin metni doğrudan kanonik mekanik sözleşmeye çevirmesi → AGY yalnız taslak çıkarır; V1’de metinsel koşul + inceleme vadesi zorunlu, kolay metrikler isteğe bağlıdır.

- **Lot muhasebesi:** Tam lot eşleştirme ve tez bazlı tax-lot defteri → V1’de fill olayları + broker average cost + reconciliation; tax-lot otoritesi broker.

- **Kurumsal işlemler:** İlk günden genel amaçlı corporate-action motoru → V1’de broker uzlaştırması ve split-adjusted veri kontrolü; tam motor gerçek ihtiyaç çıkınca.

- **Artefakt deposu:** Kanonik content-addressed blob deposu + insan görünümü → V1’de immutable dosya, SHA-256, media type ve attempt bağlantısı; çift görünüm ertelendi.

- **İzleme ritmi:** Her açık tez için haftalık sağlık değerlendirmesi → haftalık kuyruk/tamlık kontrolü, filing/event-driven derin inceleme ve kesin azami sessizlik süresi.

- **Override:** Kalıcı olarak kabul edilmiş insan hükmü → canlı para veya sapma bastırıyorsa `valid_until/review_due_at` taşıyan süreli karar.

- **Onay yüzeyi:** JSON/CLI yeterli operasyon yüzeyi → kritik kapılar için kanıt ve farkları yan yana gösteren insan-okunabilir yüzey birinci sınıf gereksinim.

## 2. Kodda/config’te doğrulanmış kusurlar

### Defter ve persistence

- `append_events()` bütün defteri okuyup mevcut+yeni içeriğin tamamını `os.replace` ile yazıyor; iki süreç aynı sürümü okursa son yazan diğerinin olaylarını sessizce kaybediyor.

- Duplicate `event_id` kontrolü yalnız sürecin okuduğu eski sürümü gördüğü için eşzamanlı yazarlara karşı koruma sağlamıyor.

- `events.jsonl` Git’te izleniyor ve geçmişte iki “clean reset” commit’iyle kesilip yeniden başlatılmış; append-only ilkesini Git zorlamıyor.

- `attach_result()` artefaktı ve manifesti defter olayından önce ayrı dosya işlemleriyle yazıyor; çökme yetim artefakt veya eksik manifest/ledger ilişkisi bırakabilir.

- Olayların artefakt referansları path’e bağlı; hash var ama kanonik `artifact_id`, media type ve byte size sözleşmesi eksik.

- V1 olay zarfının `run_id/ticker` merkezli olması round, thesis ve portfolio gibi farklı aggregate’ları doğal biçimde temsil etmiyor.

### Workflow ve projection

- `thesis_opened` üreten hiçbir komut, extractor veya transition yok.

- `check_triggers()` yalnız `state == "waiting"` adayları değerlendiriyor; açık tezlerin eşikleri bu yoldan hiçbir zaman kontrol edilmiyor.

- `thesis_tracker` config’te `pack_step:null`, `required_workflows:["pitch"]`, `allowed_next:[]` ve terminal candidate workflow olarak modellenmiş; thesis_id bazlı tekrar eden lifecycle işi değil.

- `source_interpretation_corrected` aynı olay içinde kaynak düzeltmesi, B→A terfisi ve workflow route değişikliği yapabiliyor; genel amaçlı state yama kanalı olmuş.

- `run_codex_analysis` gerekli önceki artefaktları fiilen context’e katmıyor; `required_context_artifacts` sözleşmesi uygulanmıyor.

- `candidate_screened` bucket’ı comparison-set/slice kimliği taşımıyor; dilim-göreceli hüküm mutlak aday durumu gibi projekte ediliyor.

- `waiting_for_trigger` geçmiş zamanda gerçekleşmiş domain olayı yerine adayın türetilmiş durumunu olay tipi olarak taşıyor.

- Tek `approval.status=approved` alanı deftere yazma yetkisi, analitik kabul ve sermaye onayını ayıramıyor.

### AGY ve yapılandırılmış çıkarım

- 24.000 karakter sınırı metni kesmiyor ama `PeiWorkflowError` ile bütün çıkarımı durduruyor; domain uzunluğu Windows argv taşıma sınırına bağlanmış.

- Metin AGY’ye verilmeden Unicode sanitizasyonundan geçiyor ve tanınmayan karakterler `?` olabiliyor; extractor immutable artefaktın birebir metnini görmüyor.

- `call_agy_structured()` dönen nesnenin yalnız `dict` olduğunu kontrol ediyor; çıkarım şemasını yerel olarak yeniden doğrulamayıp AGY’nin `SUCCESS` beyanına güveniyor.

- Idea extraction şeması boş `candidates` dizisine izin veriyor ve sonuç dondurulmuş input ticker listesiyle uzlaştırılmıyor.

- `bucket = c.get("bucket") or "B"` eksik bucket’ı sessizce B’ye çeviriyor.

- `if not raw_ticker: continue` boş ticker’lı adayı hiçbir hata veya `unaccounted_for` kaydı üretmeden atlıyor.

- Pitch extraction şeması `null` alanlara ve boş `kill_criteria` listesine izin verdiği için biçimsel olarak geçerli ama anlamsal olarak boş sonuç ilerleyebilir.

- `result_attached` extraction’dan önce deftere yazılıyor fakat extraction başarısızlığını kaydeden bir olay/durum yok; “bekliyor” ile “başarısız oldu” ayrıştırılamıyor.

### Portfolio ve CLI entegrasyonu

- `portfolio.py` append-only işlem defteri değil, `upsert_position/delete_position` kullanan mutable pozisyon tablosu.

- Portfolio modeli yalnız shares ve average cost taşıyor; para birimi, reconciliation provenance’ı, corporate action ve `position_unknown` yok.

- Bridge’de gerçek `portfolio_transaction_recorded` ve broker reconciliation komutu bulunmuyor; mevcut update/delete işlemleri domain sözleşmesini karşılamıyor.

- Resume komutu için dokümandaki bayrak yerleşimi çalışmıyor; `-C` global olarak `exec`ten önce verilmek zorunda.

- Resume kayıtlı cwd’yi geri yüklemiyor, yeni process cwd’sini kullanıyor; adım artefakt dizini kendiliğinden korunmuyor.

- Bu Windows kurulumunda `-s read-only` güvenilir biçimde uygulanmıyor ve `config.toml` `danger-full-access` taşıyor; sandbox varsayımı güvenlik sınırı sayılamaz.

- `mandate.json` araştırma uygunluğunu tarif ediyor ama sermaye tabanı, kayıp bütçesi, ağırlıklandırma veya yoğunlaşma çıpası içermiyor; bu kod hatası değil, portföy otomasyonunu bloklayan doğrulanmış config boşluğu.

## 3. V1 dikey dilimi

### 0. Ürün sınırını dondur

**Neden önce:** Olay ve durumların anlamı ürünün research ledger mı, allocator mı olduğuna bağlı.

**Bitti:** `thesis_opened` yalnız resmî izlenen görüş olarak tanımlı; sistem capital policy olmadan ağırlık/rebalans öneremiyor, fakat insan işlemlerini kaydedebiliyor.

### 1. Kanonik defteri ve kimlikleri kur

**Neden:** Sonraki bütün özellikler güvenilir replay, idempotency ve tek-yazarlı commit’e dayanıyor.

**Bitti:** V1 JSONL mühürlenmiş; SQLite V2 lineage başlamış; eşzamanlı commit testi olay kaybetmiyor; replay aynı projection’ı üretiyor; event/request/attempt/artifact kimlikleri ayrılmış.

### 2. Tek ticker için workflow yürüt

**Neden:** Discovery ölçeğine geçmeden artefakt, context ve extraction zincirini kanıtlamak gerekir.

**Bitti:** Elle seçilmiş bir ticker fresh session’da eksiksiz context bundle ile pitch’e kadar gidebiliyor; her artefakt hash’li; extraction hatası görünür ve downstream’i durduruyor.

### 3. Pitch adjudication’ı ve sade tezi aç

**Neden:** V1’in asıl domain değeri resmî görüşün güvenilir biçimde oluşmasıdır.

**Bitti:** İnsan ham sonuç, çıkarılmış hüküm ve kaynak pasajını aynı yüzeyde görüyor; kabul edilen pitch atomik ve idempotent biçimde tek tez açıyor; reject tez açmıyor.

### 4. Minimum izleme döngüsünü kapat

**Neden:** Açılan ama tekrar bakılamayan tez yalnız arşiv kaydıdır.

**Bitti:** Her açık tez metinsel kill koşulu ve `review_due_at` taşıyor; basit mekanik koşullar çalışabiliyor; kontrol sonucu `no_deviation/deviation/indeterminate/data_missing` olarak kaydoluyor; `no_deviation` sağlık hükmü sayılmıyor.

### 5. Gerçek portföy gerçeğini bağla

**Neden:** Sistem işlem önermese bile gerçek pozisyonu yanlış bilmemeli.

**Bitti:** İnsan fill girebiliyor; broker snapshot’ı uzlaştırılabiliyor; exposure `long/flat/unknown` olarak türetiliyor; uyuşmazlık P0 üretiyor; işlem teze bağlanabiliyor; tax-lot eşleştirme yapılmıyor.

### 6. Kapsamlı keşif batch’ini ekle

**Neden:** Tek ticker lifecycle kanıtlandıktan sonra universe ölçeğine çıkmak daha güvenli.

**Bitti:** Batch input’u donuyor; her ticker A/B/C/Reject veya `unaccounted_for` sonucu alıyor; boş/eksik aday batch kapanmasını engelliyor; değerlendirme `comparison_set_id` taşıyor; sabit finalist kotası doldurulmuyor.

### 7. İnsan yüzeyini operasyonel olarak kapat

**Neden:** Doğru olay modeli, operatör bakmazsa çalışmaz.

**Bitti:** P0–P4 “Bugün” kuyruğu bütün vadeli işleri gösteriyor; kritik kararlar kanıt yanında alınabiliyor; override’lar süreli; normal kullanım JSON incelemeyi gerektirmiyor.

### 8. Bir gerçek uçtan uca prova yap

**Neden:** Teorik lifecycle’ın kullanılabilirliği ancak gerçek kullanım süresi ve hata kurtarmasıyla ölçülür.

**Bitti:** Bir ticker `pitch → thesis → monitoring → insan işlemi → reconciliation` yolunu tamamlıyor; çökme/yeniden deneme duplicate üretmiyor; operatörün haftalık yükü ölçülüyor.

## 4. V1’de açıkça yapılmayacaklar

- **Otomatik portföy inşası veya rebalans:** Capital policy olmadığı için üretilecek ağırlıkların kanonik dayanağı yok.

- **Portfolio-risk-management aylık entegrasyonu:** Skill portföy-geneli allocator değil ve mevcut mandate implementation-ready sizing girdisi sağlamıyor.

- **Benchmark/active-weight/tracking-error analitiği:** Mandate benchmark varsayılmasını açıkça yasaklıyor.

- **Beş eksenli tez state machine’i:** Kavramsal ayrımların çoğu ayrı gerçeklerden veya tarihli assessment’lardan türetilebilir.

- **`superseded` lifecycle’ı:** Onu doğuracak somut mekanizma yok; yeni görüş yeni tez olarak açılabilir.

- **Tam coverage round/Stage 2 kapanış motoru:** 87 isimde kayan batch yeterli; waived/partial/deadlock semantiği henüz kazanım sağlamıyor.

- **Ara workflow’larda insan adjudication’ı:** Tearsheets/comps/preview provisional evidence olarak ilerler; kapı yalnız domain sonucu doğuran yerde kalır.

- **Tam tax-lot eşleştirme:** Vergisel otorite broker’dır; fill ve average cost V1 ihtiyacını karşılar.

- **Genel kurumsal işlem motoru:** Önce broker reconciliation ve split-adjusted veriyle gerçek olay sıklığı görülmeli.

- **Genel amaçlı metric DSL:** Sıfır tez varken bütün olası kill criterion türlerini modellemek erken soyutlamadır.

- **AGY’nin monitoring contract otoritesi olması:** LLM yalnız kaynak bağlı taslak üretir; kanonik yorum insan kapısından geçer.

- **Tam restatement/retrospective-breach motoru:** `known_at/period_end` şimdiden saklanabilir, çift tarihli yeniden değerlendirme gerçek vaka çıkınca eklenir.

- **Content-addressed blob deposu ve ikinci okunabilir görünüm:** V1’de immutable yol ve hash yeterli; fiziksel deduplikasyon gerekmiyor.

- **Git’i kanonik olay deposu yapmak:** Merge ve history rewrite domain atomikliğini korumuyor.

- **Uzun ömürlü resume’a doğruluk açısından bağımlılık:** Context bundle fresh session için yeterli olmak zorunda; resume yalnız optimizasyon.

- **Ayrı thesis ledger:** Thesis görünümü global olay defterinden türetilir; ikinci otorite kurulmaz.

- **Otomatik işlem yürütme:** Sistem önerse bile gerçek alım/satım yalnız insan tarafından yapılır.

- **500 isim optimizasyonu:** V1 önce 87 isim ve ölçülen insan kapasitesiyle doğrulanır.

- **Capital policy kısıtları uydurmak:** Benchmark, sektör limiti, pozisyon sayısı veya loss budget kullanıcı kararı olmadan eklenmez.

## 5. Kullanıcıya sorulacak yeni sorular

1. **V1’in resmî sınırı nedir: yalnız araştırma/izleme sistemi mi, yoksa sermaye tahsis desteği de vermeli mi?**  
   Capital policy olmadan güvenle inşa edilebilen ürün araştırma defteridir; allocator isteniyorsa önce yeni bir karar katmanı gerekir.

2. **`thesis_opened` yalnız resmî izlenen görüş mü demeli, yoksa gelecekte ayrıca `capital_eligible` türü ayrı bir portföy hükmü mü isteniyor?**  
   Araştırma kalitesi ile sermaye uygunluğunu aynı olayda birleştirmek önceki karışıklığı yeniden üretir.

3. **Capital policy’nin asgari çıpaları ne olacak: deployable capital, nakit yaklaşımı, tek-isim azami sermaye/kayıp ve sizing ilkesi?**  
   Bunlardan en az biri olmadan pozisyon büyüklüğü veya portföy karşılaştırması belirlenemez.

4. **Aylık gözden geçirmede işlem yapılmasına hangi gerekçeler izin verecek?**  
   Yeni filing/tez değişimi, fiyat-değerleme değişimi, nakit ihtiyacı veya açık risk kısıtı dışında işlem serbest bırakılırsa aylık ritim gereksiz rotasyon üretir.

5. **Portföy muhasebesinde hedef doğruluk nedir: broker average cost ve tez nakit akışları yeterli mi, yoksa vergi lotu düzeyinde attribution gerçekten gerekli mi?**  
   Cevap, V1’in basit reconciliation katmanı mı yoksa ikinci bir broker muhasebesi mi kuracağını belirler.

### İlk beş sorunun yeni durumu

- **Ölçek/kadans:** Hâlâ gerekli, fakat “aylık rebalans sıklığı” yerine coverage cycle süresi, haftalık insan bütçesi ve azami tez sessizliği olarak yeniden sorulmalı.

- **Adjudication granülerliği:** Büyük ölçüde karara bağlandı; ara adımlar otomatik/provisional, insan kapısı pitch→tez, monitoring contract ve para sınırında.

- **Partial tur:** V1 için gereksizleşti; tam round state machine’i yapılmayacağı için ertelendi.

- **Eşzamanlı zincir sayısı:** Mimari sorudan operasyonel WIP limitine dönüştü; ilk gerçek koşulardan sonra ölçülerek belirlenebilir.

- **Uzlaştırma sıklığı:** Hâlâ geçerli; yeni portfolio fidelity sorusunun altında işlem sonrası + periyodik broker reconciliation tercihi olarak cevaplanmalı.