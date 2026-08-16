Tespitin yönü doğru, ama teknik olarak küçük bir düzeltme var: mevcut `pack_step` yalnızca prompt varyantı değil. Sistem önce büyük bir üst-küme pack kuruyor, sonra `STEP_BLOCKS` ile bazı alanları en sonda siliyor; yalnız tearsheet için ayrıca gerçek veri zenginleştirmesi yapıyor. Yani bugünkü yapı “adım sözleşmesi” değil, “monolitik pack + geç budama”. Üstelik çıkarılacak alanların hesaplama maliyeti de çoktan ödenmiş oluyor.

## 1. Tek büyük pack mi, adıma özel pack mi?

Adıma özel, sürümlü pack’leri savunuyorum; fakat hepsi aynı kanonik veri ürünlerinden kurulmalı:

**kanonik snapshot’lar → pack recipe/adapter → adıma özel materialized pack**

“Her adım aynı gerçeği görsün” hedefi, her adıma aynı JSON’u vermekle değil, hepsini aynı snapshot kimliklerinden üretmekle sağlanır. Böylece pitch ile deep-dive aynı finansal gerçeğe dayanır ama ilgisiz bağlamı taşımak zorunda kalmaz.

`core + overlay` doğru model, fakat core küçük olmalı:

- security ve issuer kimliği
- mandate/product-boundary referansı
- knowledge cutoff
- source registry ve snapshot kimlikleri
- veri eksikliği/provenance özeti

Finansallar, konsensus, olaylar ve değerleme “her ihtimale karşı core”a doldurulmamalı; bunlar isimlendirilmiş overlay’ler olmalı. Aksi hâlde yeni monolit yalnızca daha düzenli bir monolit olur.

Asıl kusur `pop()` ile geç budamak. Pack recipe, yalnız ihtiyacı olan veri üreticilerini baştan çağırmalı.

## 2. V1’de gerekli pack’ler

Altılı listen neredeyse doğru, fakat karar adımı için bir pack eksik. Ben yedi sözleşme tanımlardım:

1. `screen_batch.v1`  
   Idea-generation için; `stage: coverage | selection` taşıyabilir. Evren/dilim kimliği ve karşılaştırma kümesi zorunludur.

2. `baseline_analysis.v1`  
   Company-tearsheet için şirket kimliği, iş modeli, temel finansal yapı ve güncel veri boşlukları.

3. `valuation_analysis.v1`  
   Comps için peer adayları, karşılaştırılabilir metrikler, dönem/provenance ve piyasa fiyatlaması.

4. `earnings_update.v1`  
   Deep-dive için yeni yayınlanan kanıt, önceki beklenti çıpası, önceki dönem ve ilk piyasa tepkisi. `event_evidence` bunun ham veri ürünü olabilir; skill’e giden pack daha fazlasını taşır.

5. `pitch_decision.v1`  
   Senin listende eksik. Baseline, onaylı `valuation_anchor`, vaka sorusu, önceki araştırma artefaktları ve mandate’i bir araya getiren karar zarfıdır. Pitch’e yalnız `issuer_baseline` vermek yine “önceki işlerin üstüne inşa et” şartını karşılamaz.

6. `monitoring_snapshot.v1`  
   LLM pack’i değil, mekanik motorun küçük ve typed girdisi. Yalnız onaylı monitoring rule’ların ihtiyaç duyduğu değerleri taşır.

7. `thesis_update.v1`  
   Tracker için mevcut tez sürümü, yeni evidence, mekanik kontrol sonuçları, açık nitel koşullar ve önceki adjudication’lar.

`dashboard_payload` sekizinci analitik pack değildir; bunlardan türetilen presentation payload’dur. Memo için ileride dönem-sonu bir pack eklenebilir ama V1 çekirdeği değildir.

Buradaki önemli adlandırma ayrımı şu: `issuer_snapshot`, `valuation_snapshot`, `event_evidence_bundle` kanonik veri ürünleridir; yukarıdakiler ise belirli bir işi yaptırmak için materialize edilen pack sözleşmeleridir.

## 3. Tazelik ve provenance

Üç zaman ekseni yalnız baseline’a özgü değil; bütün pack mimarisinin kuralı olmalı. Fakat her pack üç alanın hepsini taşımak zorunda değil. Zaman bilgisi bölümün veri türüne göre zorunlu olmalı:

- Yapısal bilgi: `structural_as_of`
- Finansal bilgi: `period_end`, `published_at`, `known_at`, accession/source
- Piyasa verisi: `market_as_of`, seans ve kaynak
- Konsensus: `consensus_as_of`, provider/snapshot kimliği
- Olay kanıtı: `event_time`, `observed_at`, certainty/date status, accession
- Pack’in kendisi: `built_at`, `knowledge_cutoff`

Tek bir üst seviye `as_of` tehlikeli; 16 Ağustos’ta üretilmiş pack’in finansalları Haziran dönemine, konsensüsü 14 Ağustos’a, fiyatı 15 Ağustos seansına ait olabilir. Pack başlığı bunları özetleyebilir ama gerçek provenance bloklarda yaşamalı.

Hash konusunda mevcut kod düşündüğünden daha iyi:

- `workflow_prepared.source_artifacts` içindeki pack referansı `_artifact()` üzerinden SHA-256 taşıyor.
- Pack üretim manifestinde de `pack_sha256` var.

Dolayısıyla olay şimdiden pack’in tam byte’larına bağlanıyor. Eksik olan hash değil; kalıcı `artifact_id`, byte size, media type, pack schema version, source snapshot referansları ve `contract_manifest_hash`. Path yalnız okunabilir konum olmalı, kimlik olmamalı.

Hash ayrıca “veri doğruydu”yu kanıtlamaz; yalnız modelin hangi exact girdiyi gördüğünü kanıtlar.

## 4. Pack sözleşmesinin sahibi kim?

Aynı önceki karardaki gibi: **kanonik snapshot bizim, analitik beklenti skill’in, eşleme adapter’ın**.

İki uç da yanlış:

- Her skill’in kendi veri toplama hattını yazmak aynı gerçeğin 23 farklı yorumunu üretir.
- Tek büyük pack verip “eksikse skill söylesin” demek pahalı çağrıdan sonra geç fark edilen hata ve bağlam gürültüsü üretir.

Doğru sınır:

- Repo kanonik gerçekleri, PIT semantiğini ve provenance’ı sahiplenir.
- Workflow contract `required / optional / forbidden` veri yeteneklerini tanımlar.
- Adapter kanonik snapshot’ları skill’in beklediği biçime dönüştürür.
- Hazırlık aşaması, model çağrısından önce readiness doğrulaması yapar.
- Skill eksik input icat edemez; eksikliği ve karar üzerindeki etkisini bildirebilir.

Adapter’ı her skill adına özel yazmak da gereksiz. Yedi pack rolüne göre adapter yazmak yeterli: screen, baseline, valuation, earnings, decision, monitoring, thesis-update.

## 5. Tur 1 ince pack’i

İlk hedefim ticker başına yaklaşık 1–2 KB, 25 isim için kaynak registry’si hariç yaklaşık 25–50 KB olurdu. 400 KB’yi “sığıyor” diye kabul etmezdim; sorun pencere sınırı değil, karşılaştırmalı dikkatin seyrelmesi.

Batch başlığında bir kez:

- `coverage_cycle_id`, `slice_id`, `comparison_set_id`
- universe snapshot/hash ve kesin üye listesi
- sektör/boyut düzeltme yöntemi
- mandate özeti: long-only, US common stock, benchmark yok, liquidity constraint bağlayıcı değil
- bütün veri kesim tarihleri
- eksik-veri politikası
- bu aşamanın yalnız araştırma önceliği ürettiği uyarısı

Ticker başına:

- `security_id`, ticker, issuer, sektör/endüstri, market-cap kovası
- Şirketin ne yaptığı ve ana ekonomik maruziyeti için 1–2 cümlelik kaynaklı özet
- Son finansal dönem: `period_end`, `known_at`, filing recency
- Küçük kalite/büyüme seti: gelir büyümesi, faaliyet marjı ve değişimi, FCF marjı/dönüşümü, ROIC, net nakit veya kaldıraç bayrağı
- Bir veya iki sektör-uygun ileri değerleme metriği; ham değer, sektör/dilim yüzdeliği ve `as_of`
- Yakın dönem beklenti yönü: gelir/EPS büyümesi ve konsensus revizyon yönü
- En yakın maddi katalizör; tarih doğrulanmış mı tahmini mi
- Earnings quality, restatement, karşılaştırılabilirlik ve stale-data bayrakları
- Aktif research case/thesis nedeniyle eligibility durumu
- Açıkça `missing` olan gerekli alanlar
- Tekrarlanan URL’ler yerine batch düzeyindeki source registry’ye referanslar

Çıkarmam gerekenler:

- Tam finansal tablolar ve uzun çeyreklik seriler
- Ayrıntılı konsensus tabloları
- Peer üye listeleri ve tam comps çalışması
- Uzun valuation history
- Earnings release metni
- Önceki anlatısal result dosyaları
- Portföy/pozisyon bilgisi
- İşlem eşikleri veya Add/Trim/Exit dili
- Bütün filing geçmişi

Idea-generation’ın eleme hükmünü değiştiren şey “şirket hakkında mümkün olan bütün bilgi” değil; maruziyet, kalite, beklenti, yaklaşık fiyatlama, yakın katalizör ve verinin güvenilirliğidir. Tur 1 pack’i bu altı soruyu karşılamalı. Bir isim bunlarla değerlendirilemiyorsa büyük pack’e sessizce genişlemek yerine `insufficient_screen_evidence` üretmelidir. Bu, ince pack’in en önemli güvenlik sınırıdır.