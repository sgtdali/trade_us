GOOGL örneği `financials-normalizer`ı normal akışa sokmuyor; daha önemli bir şeyi gösteriyor: idea-generation bir skill adıyla aslında bir yetenek ihtiyacı tarif etmiş. “Yatırım kazançlarını ayır, karşılaştırılabilir EPS/FCF üret” diyor. Orkestratör bunu doğrudan skill çağrısı olarak değil, `normalization_gap` olarak okumalı; önce deterministik hattın bu ihtiyacı karşılayıp karşılamadığına bakmalı.

Idea-generation repo’nun yerel normalizasyon kapasitesini bilmiyor ve eklentinin kendi sözlüğündeki en yakın etiketi seçiyor. Dolayısıyla tek GOOGL önerisi “LLM normalizer rutin çalışmalı” kanıtı değil. Aynı ihtiyaç çok sayıda şirkette tekrarlanır ve deterministik hat karşılamazsa sonuç yine skill’i rutinleştirmek değil, deterministik hattın kapsamını genişletmektir. Skill ancak bir defalık, kanonik olmayan `normalization_proposal` üretir.

## 1. `valuation_anchor` sözleşmesi

Önce bir ayrım eklemeliyiz: her değerleme çıpası aynı yetkiye sahip değildir.

```text
valuation_anchor
  anchor_id
  status
  decision_use
  method
  subject/security
  price_basis
  denominator
  reference_basis
  implied_expectations
  valuation_output
  method_rationale
  limitations
  provenance
  freshness
```

Alanlar şöyle olmalı:

- `status`: `supported | screen_grade | not_supported`
- `decision_use`: `diagnostic_only | decision_support`
- `method`: `comps | own_range | implied_expectations | sotp`
- `price_basis`: security kimliği, fiyat, para birimi, `market_as_of`
- `denominator`: metrik tanımı, GAAP/adjusted niteliği, değer, birim, dönem, `period_end`, forecast/actual ayrımı, kaynak
- `reference_basis`:
  - comps ise peer-set kimliği/sürümü, Core/Secondary/Excluded üyeleri ve gerekçeleri;
  - own-range ise tarih aralığı, gözlem sayısı ve rejim kırıkları;
  - SOTP ise parçalar ve her parçanın yöntemi
- `observed_valuation`: mevcut multiple/yield veya EV bridge
- `implied_expectations`: piyasa fiyatının hangi büyüme, marj, EPS, FCF ya da çarpan varsayımını gerektirdiği; ufuk ve çözüm yöntemi
- `valuation_output`: ima edilen değer aralığı varsa aralık; tek nokta zorunlu değil
- `method_rationale`: bu şirket için neden savunulabilir olduğu
- `limitations`: karşılaştırılabilirlik, veri, çevrim, net borç, SBC, segment ve tahmin eksikleri
- `provenance`: kaynak artefakt kimlikleri
- `freshness`: market, consensus ve finansal veri için ayrı as-of damgaları

`scenario`yu bağımsız `method` yapmazdım. Scenario bir çıpa üretmez; mevcut bir çıpaya `base_anchor_id` ile bağlanan overlay’dir. Yalnız kaynaklı başarı/başarısızlık değerleri bulunan ayrık olay analizleri istisna olabilir.

`valuation_not_supported` hem result contract hem doğrulama konusu olmalı:

- Result contract, analistin dürüstçe `not_supported` diyebilmesine izin verir; bu geçerli bir analitik sonuçtur.
- Doğrulayıcı, `supported` denmişse yönteme özgü zorunlu alanları arar.
- `supported` denmiş ama alanlar eksikse sonuç `not_supported`a sessizce düşürülmez; bu `valuation_contract_invalid` olur.
- `actionable_candidate` için en az bir `decision_support + supported` çıpa gerekir. `screen_grade + diagnostic_only`, yalnız “ne fiyatlanıyor?” tartışmasını besler.

## 2. AMZN ve META senaryoları sağlam mı?

Hükmüm: temelsiz değiller, fakat değerleme değil; doğru etiketlenmiş ince bir implied-expectations egzersizi.

Pack, bir workbook modeli vermemiş ama geçici bir baz sağlamış:

- güncel fiyat,
- FY+1 konsensüs EPS,
- mevcut ileri çarpan,
- bazı faaliyet kârı/EV ve FCF verileri.

Talimat da açıkça modeli olmayan bu girdiler üzerinden sensitivity istemiş: [AMZN instructions](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/runs/IDEA-20260813-122055736107/work/WI-IDEA-20260813-122055736107-AMZN-scenario/2026-08-14/AMZN/scenario/instructions.md:113). Yani scenario skill’i gizlice base case kurmamış; orkestrasyon mevcut piyasa konsensüsünü geçici baz diye sunmuş.

Çıktılar epistemik olarak fena değil:

- AMZN, seçilen çarpanların analist varsayımı olduğunu ve model doğrulaması bulunmadığını açıkça yazıyor: [result.md](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/runs/IDEA-20260813-122055736107/work/WI-IDEA-20260813-122055736107-AMZN-scenario/2026-08-14/AMZN/scenario/result.md:5).
- META da 15x/20x bantlarını varsayım, çıktıyı `screen-grade` ilan ediyor: [result.md](/C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/runs/IDEA-20260813-122055736107/work/WI-IDEA-20260813-122055736107-META-scenario/2026-08-14/META/scenario/result.md:5).
- META, FCF kaynak çelişkisini fark edip FCF değerlemesi üretmemiş; bu doğru davranış.
- İkisi de olasılık ağırlıklı değer uydurmamış.

Ama ciddi sınır şu: 15x/20x, 22x/28x veya 26x/36x bantlarının neden ekonomik olarak savunulabilir olduğu gösterilmiyor. Peer, own-range veya işletme ekonomisi bağı yok. Dolayısıyla tablolar “bu varsayımı koyarsak fiyat ne olur?” sorusunu cevaplıyor; “şirket gerçekten ne eder?” sorusunu değil.

Daha kötüsü, bu ince matematikten `Add/Trim/Exit` eşikleri çıkarılmış. Capital policy bulunmayan V1’de bu yetki zaten olmamalı; ayrıca $220’nin neden alım eşiği olduğu model veya valuation anchor tarafından kanıtlanmıyor.

Bu iki çıktı şöyle yeniden sınıflanmalı:

```text
status: screen_grade
decision_use: diagnostic_only
method: implied_expectations
model_validated: false
```

Yararlı araştırma kanıtıdır; tezi açabilecek karar çıpası değildir.

## 3. Dört workbook skill’i V1 dışında mı?

Evet. Senin sert önerini kabul ediyorum:

- `dcf-model-builder`: V1 DIŞI
- `three-statement-model-builder`: V1 DIŞI
- `equity-model-update`: V1 DIŞI
- `model-audit-tieout`: V1 DIŞI

Bunlar birbirini doğuran bir bakım ekosistemi. İlk workbook üretildiği anda güncelleme, kaynak-hücre eşleme, native recalculation, tie-out, sürüm ve stale-output sorunları başlıyor. Haftada 5–7 saatlik tek operatörün bu bakımın sahibi olması gerçekçi değil. Skill sözleşmeleri de workbook’u yan ürün değil hero artefakt olarak tanımlıyor; örneğin DCF normal yolunda formula-first XLSX zorunlu ([DCF contract](/C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/dcf-model-builder/SKILL.md:28)).

“Model gerekiyorsa tezi açma” bu nedenle fazla sert değil; dürüst bir kapsam sınırı:

```text
terminal_status: blocked
reason: model_required_outside_v1
```

Modelin gerçekten zorunlu olduğu tipik vakalar:

- uzun süre negatif FCF üreten uzun-duration şirketler,
- finansmanı ve yatırım geri dönüşü belirleyici sermaye-yoğun şirketler,
- karmaşık SOTP/konglomera yapıları,
- erken aşama biyoteknoloji/pipeline değerlemeleri,
- normalleştirilmiş çevrim ortası kazancı gerektiren aşırı döngüsel şirketler,
- borç, sulanma veya çalışma sermayesi nedeniyle üç tablonun birlikte hareket ettiği vakalar.

V1 bunları yanlış bir mini-modelle çözmeye çalışmamalı; bloklamalı. Bloklanan iyi fikir sayısı zamanla yüksek çıkarsa, V2 model şeridinin gerçek talep kanıtı oluşur. Şu anda bakım sahibimiz olmadığı için workbook üretmemek doğru karar.

## 4. Scenario’yu kim çağırır?

Scenario modelsiz çalışabilir; çünkü kendi sözleşmesi base’in yalnız workbook değil, mevcut bir comps, earnings setup, event case veya thesis olabileceğini söylüyor ([scenario contract](/C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/scenario-sensitivity-generator/SKILL.md:31)).

Ama iki guard gerekir:

1. Her scenario çağrısı `base_case_ref` taşımalı.
2. Base’in epistemik seviyesi scenario tarafından yükseltilememeli.

Örneğin:

```text
base_case_ref: valuation_anchor:AMZN:...
base_case_status: screen_grade
scenario_mode: eps_multiple_sensitivity
output_status: screen_grade
```

Comps → scenario hattı anlamlıdır. Comps “şirket 18x işlem görüyor, benzerleri 14–22x; premium şu nedenle olabilir” der. Scenario bunun üzerine “EPS %10 düşer ve premium 2 tur sıkışırsa ne olur?” diye test yapar. Bu değerli bir support işidir.

Fakat scenario:

- kendi peer kümesini seçemez,
- gerekçesiz çarpan bantlarını fair value gibi sunamaz,
- zayıf base’i karar seviyesine terfi ettiremez,
- V1’de add/trim/exit talimatı üretemez.

Çağıran taraf idea-generation olmamalı. Idea-generation yalnız `scenario_gap` önerebilir. Aktif `research_case` içindeki lead—çoğunlukla pitch—“bu belirsizlik hükmü değiştiriyor” derse scenario support’u açar. Comps da kendi değerleme savını streslemek için isteyebilir; sonuç yine lead’e döner.

## 5. Altı skill aynı hattın ağırlıkları mı?

Tam olarak değil. Aynı soruna dokunuyorlar ama farklı işler yapıyorlar:

| Skill | Sahip olduğu iş | Base üretir mi? | Workbook bağı |
|---|---|---:|---:|
| comps | Referans sınıfı ve relative valuation | Evet | Hayır, report mode mümkün |
| scenario | Mevcut base’i streslemek | Hayır | Hayır |
| DCF | Nakit akımıyla intrinsic valuation | Evet | Evet |
| three-statement | Entegre işletme tahmini | Evet, fakat valuation değil | Evet |
| equity-model-update | Mevcut modeli güncellemek | Hayır | Evet |
| model-audit | Mevcut modeli denetlemek | Hayır | Evet |

Dolayısıyla bunlar tek bir merdivenden çok şu grafiktir:

```text
Deterministik finansallar ──> comps ──> scenario
                         └──> three-statement ──> DCF ──> scenario
Her workbook ──> model-update + model-audit
```

V1 kesimi birinci satırda durmalı:

> Deterministik finansallar → comps report-mode → gerektiğinde scenario overlay → pitch.

## Comps’ta durmanın somut bedeli

Bu karar bedelsiz değil:

- Kötü peer kümesi olan şirketlerde güvenilir fair value üretilemez.
- Bütün sektör pahalıysa relative ucuzluk mutlak koruma sağlamaz.
- Capex’in bugünkü baskısı ile gelecekteki getirisi düzgün modellenemez.
- Nakit akımının zamanı, sulanma, net borç ve terminal ekonomi birlikte çözülemez.
- Sistem olgun, pozitif kazanç/FCF üreten ve emsal bulunabilen şirketlere yapısal olarak eğilim gösterir.
- Biyoteknoloji, karmaşık holding, erken aşama teknoloji ve ağır dönüşüm vakaları daha sık `model_required_outside_v1` olur.

Bence bu kabul edilmesi gereken doğru bedel. V1’in görevi bütün ABD hisselerini değerleyebilmek değil; kapasitesinin yetmediği vakayı güvenilir biçimde tanıyıp bloklayabilmek. En tehlikeli seçenek comps’ta durmak değil, comps seviyesindeki kanıtla DCF kesinliği taklit etmektir.