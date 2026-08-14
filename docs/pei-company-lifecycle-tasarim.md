# Şirket / portföy ömür döngüsü tasarımı

Durum: **Gündem belirlendi, tasarım henüz yapılmadı** (brainstorming
devam ediyor).
Başlangıç: 2026-08-14.

## Neden bu doküman var

`src/adapter/pei_workflow.py`'deki `project()` fonksiyonu, her adayı
`run_id:ticker` ikilisiyle anahtarlıyor (satır ~419). Bu yüzden aynı ticker
(ör. ADBE) farklı idea-generation koşularında tarandığında, her koşu
tamamen ayrı, birbirinden habersiz bir "aday" kaydı oluşturuyor.

Kullanıcı düzenli (haftalık olabilir, kesin değil) idea-generation koşuları
planlıyor. Bu durumda aynı ticker zaman içinde defalarca taranacak ve
"güncel durum" sorusu ("ADBE şu an ne durumda?") belirsizleşiyor.

**Önemli bulgu:** `docs/pei-workflow-orchestrator.md` (2026-08-12, "Onaylanmış
tasarım" damgalı) Bölüm 6'da zaten şu ilke var:

> "Yeni idea-generation koşusu eski sonucu silmez. Adayın güncel bucket'i
> en son onaylı screen olayından, geçmişi ise önceki olaylardan okunur."

Yani ticker-sürekli kimlik zaten onaylı tasarımın bir parçası. Kodun
(`run_id:ticker` anahtarlaması) bu tasarımdan saptığı görülüyor -- muhtemelen
şimdiye kadar tek bir gerçek prodüksiyon run'ı olduğu için bu sapma hiç
görünür olmadı. Bu, yeniden icat etmek değil, tasarıma geri dönmek meselesi.

Ama kullanıcının "içime sinmedi" tepkisi bunun ötesinde: sadece anahtar
değişikliği değil, **tüm ömür döngüsünün** (araştırma -> tez -> portföy/
izleme -> unutulma) net tasarlanmamış olması asıl sorun.

## Gündem (7 başlık, sıralı)

Bu sıra kasıtlı: 1-2-3 (araştırma tarafı) netleşmeden 4-5-6 (portföy/izleme
tarafı) konuşulamaz; 0 ise 1-6'nın hepsinin üzerine oturduğu zemin.

### 0. Candidate / Tez / Portföy pozisyonu / İzleme kaydı ilişkisi

Şu an elimizde **dört ayrı veri modeli** var, aralarındaki geçiş tanımsız:

- **candidate** -- idea-generation'dan doğan araştırma durumu
  (`project()`'in ürettiği, bu oturumda üzerinde çok çalıştığımız nesne).
- **thesis** -- `thesis_opened` olayı + kendi üç ekseni (company/security/
  position, bkz. `docs/pei-workflow.md` Bölüm 1b). Şu ana kadar hiç
  kullanılmadı.
- **portföy pozisyonu** -- tamamen ayrı bir JSON dosyasında
  (`adapter/portfolio.py`, `data/portfolio.json` gibi), gerçek hisse
  adedi/maliyet/güncel fiyat.
  taşıyor.
- **izleme listesi kaydı** -- yine ayrı (`adapter/watchlist.py`).

Sorulacak: bir candidate ne zaman "tez" olur? Tez ne zaman "pozisyon" olur?
Pozisyon kapanınca candidate/teze ne olur? İzleme listesi bunların neresinde
duruyor -- candidate'in bir alt-durumu mu, yoksa tamamen bağımsız bir liste
mi?

### 1. T0 akışı -- tekil koşunun ömrü

Bir ticker kümesi idea-generation'dan geçip A/B/C'ye ayrılıyor.

- A ve B için akış "aşağı yukarı" biliniyor (bugün B->A terfi kapısı,
  otomatik tetikleyici mekanizması kuruldu) ama **tüm if-durumlarına sahip
  miyiz belli değil**.
- **C için hiçbir şey yok** -- şu an sadece `deprioritized` deyip
  bırakıyoruz, bir daha hiç dönülmüyor.

Alt not: bugün kurduğumuz B->A otomatik terfi kapısı (`evaluate_promotion`)
ve "iş kuyruğunda aktif" (`in_progress`) durumu, yeniden tarama ile
çakışırsa ne olacak? (Bir isim T45'te terfi etti, T60'ta yeniden taranırsa
yeni tarama bu terfiyi geçersiz kılabilir mi?)

### 2. Çoklu / kademeli kohortlar

T0'da bir grup, T15'te başka bir grup taranırsa, bu iki bağımsız koşu
birbiriyle nasıl ilişkilenecek? Sonunda hepsi TEK bir portföyde
birleşecek. Aynı ticker iki farklı kohortta (ör. bir sektör taraması ve
bir genel piyasa taraması) aynı anda çıkarsa ne olur?

### 3. Aynı kohortun zaman içinde tekrar taranması

T0'daki grup T60'ta tekrar mı taranır, yoksa yalnız C'ler mi yeniden
değerlendirilir? Sonra ne olur?

### 4. Portföy takibi

İki farklı şey birbirine karışmamalı:
- **Muhasebe:** kaç hisse tutuyorum, ne kadar kâr/zarar (bugün
  `adapter/portfolio.py` bunu yapıyor).
- **Portföy seviyesinde karar:** yeni bir A adayını eklemeli miyim, mevcut
  pozisyonlarla ne kadar korele/yoğunlaşmış olurum -- bu
  `portfolio-risk-management` (eklentide var, hiç kurulmamış skill,
  kataloğumuzda yok).

### 5. İzleme listesi takibi

Pozisyon olmayan ama izlenen isimler zaman içinde nasıl takip edilir?

### 6. Ne portföyde ne izlemede olan isimler

Bunlar sonsuza kadar mı unutulacak, yoksa bir geri-değerlendirme
mekanizması mı olacak?

## Durum

Gündem kullanıcı tarafından onaylandı (2026-08-14). Başlık 1 üzerinde
çalışılıyor (brainstorming skill aktif).

## Karar günlüğü

### Başlık 0 — Candidate / Tez / Portföy / İzleme ilişkisi (2026-08-14)

**Karar:** Tez (thesis-tracker) merkezi kavram.

- `pitch` (long-short-pitch) adımı `actionable_candidate` verdiktiyle
  bittiğinde **otomatik** bir tez açılır (thesis-tracker'ın zaten kurulu
  `data/thesis-tracker/<ticker>/<thesis_id>.jsonl` şeması, three-axis:
  company/security/position). Bu, B->A terfi kapısındaki gibi insansız bir
  otomasyon -- ama gerçek sermaye tahsisi değil, yalnız "resmi, kanıt
  ağırlıklı görüş oluştu" demek.
- **Portföy, tezden ayrı, gerçek-dünya defteri.** Tezin `position` ekseni
  (add/press/hold/trim/exit/wait_for_proof/re-underwrite) bir öneri/yargı;
  gerçekten kaç hisse alındığı/hangi fiyattan insanın doğruladığı, ayrı bir
  kayıt (mevcut `portfolio.py` gibi mutable bir defter, ama artık tezle
  çapraz referanslı). Tez "trim" derken hâlâ tam pozisyondaysa bu fark
  görünür bir uyarı olur. Gerekçe: gerçek alım/satımı yalnız insan yapabilir
  (sistem hiçbir zaman otomatik emir vermiyor), o yüzden "tez öneriyor" ile
  "gerçekten yapıldı" ayrı kalmalı.
- **Tez, pozisyon açıldıktan sonra da yaşamaya devam eder** -- tek seferlik
  bir "kapı" değil, pozisyon süresince paralel, sürekli güncellenen bir
  izleme kaydı (append-only, yeni kanıt eklene eklene). Haftalık kontrolde
  "tez hâlâ ayakta mı" sorusu burada cevaplanır (`docs/pei-workflow.md`
  Bölüm 1b'deki three-axis tam bunun için). Pozisyon kapanınca tez
  `retired` olur, silinmez.
- **Watchlist tek ve otomatik.** Deprioritized/rejected/tez-retired
  olmayan her şey (tez öncesi aktif candidate'lar + tezi olup henüz
  fonlanmamış olanlar + portföyde olup tezi hâlâ izlenen isimler) otomatik
  watchlist'te sayılır -- ayrı bir "ekle" adımı yok. Hangi aşamada olduğu
  (tez-öncesi / tez-var-fonlanmamış / portföyde-izleniyor) açıkça
  etiketlenmeli.

**Bunun sonucu, Başlık 6'yı basitleştiriyor:** "ne portföyde ne
izlemede" olan isimler artık yalnızca deprioritized/rejected/tez-retired
olanlar -- yani tanım gereği zaten "aktif olmayan" demek. Başlık 6'nın
gerçek sorusu: bu ölü isimler için periyodik bir yeniden-değerlendirme
mekanizması var mı, yoksa gerçekten kalıcı olarak mı öyle kalıyorlar
(Başlık 3 ile birlikte ele alınacak).

**Değerlendirilen alternatif:** Portföyün tezin position ekseninden
otomatik türetilmesi (ayrı defter yok) -- reddedildi, çünkü gerçek
alım/satım kararını yalnız insan verebilir/uygulayabilir.

### Başlık 1 — T0 akışı: A/B eksik durumlar ve C kovası (2026-08-14)

**Bulgu (koddan doğrulandı):** `project()`'te C kovası (ve tanımsız her
bucket) için hiçbir tetikleyici/hatırlatma mekanizması yok --
`status_reason: "deprioritized until a later screen"` diyor ama "sonraki
tarama" otomatik hiçbir yerde tetiklenmiyor. Bugünkü gerçek veride tek C
adayı: AAPL.

**Kararlar:**

1. **C kovasına hafif, zamanlı bir hatırlatıcı eklenir.** B'nin tetikleyici
   mekanizmasına benzer ama gevşek: **3 ay** sonra `manual_review_required`
   üretilir (C, "bu ekranda ilginç değil" demek, kısa vadeli bir olaya değil
   zamana bağlı bir yeniden-bakış).
2. **Hatırlatıcı tarihi geldiğinde otomatik yeniden tarama YAPILMAZ** --
   yalnız insana işaret edilir (`manual_review_required`). Gerçekten yeniden
   taramayı başlatmak insanın kararı.
3. **`route_unsupported` (bloklu) isimler için ayrı bir hatırlatıcıya gerek
   yok.** Fail-closed davranış zaten doğru; bir isim sonsuza kadar bloklu
   kalabilir. Asıl çözüm hatırlatma değil, **eksik skill'leri (ör.
   equity-model-update, event-driven-analyzer) kataloğa eklemek** --
   ayrı bir aksiyon maddesi, tasarım kararı değil.
4. **Pitch'in 4 kapalı sözlük sonucundan yalnız `actionable_candidate` tez
   açar.** `watchlist` / `pass_for_now` / `red_team_only` hiçbir tez açmaz;
   isim normal candidate durumunda kalır (Başlık 0'a göre zaten otomatik
   watchlist'te sayılır).
5. **(İLK FAZ) Tez açıldıktan sonra otomatik araştırma zinciri DURUR.**
   Başlık 0'da "tez pozisyon süresince sürekli izlenir/beslenir" dedik, ama
   bunun *otomatik* mi elle mi olacağı ayrı bir soru: ilk fazda `thesis_
   opened` sonrası next_workflow kalıcı `None` kalmaya devam eder (bugünkü
   kod davranışı korunur), yeni kanıt toplamak (earnings-deep-dive
   çalıştırmak, teze evidence eklemek) bilinçli bir insan eylemi olur.
   Otomatik besleme (bugün B için kurduğumuz `waiting_for_trigger` gibi)
   sonraki bir fazda değerlendirilebilir -- şimdi YAGNI.

**Not (tasarım kararı değil, ayrı düzeltilecek bug):** `WORKFLOW_MAP`'in
substring-eşleştirmesi, bir adımın metni birden fazla rota önerdiğinde
(ör. ADBE: "önce thesis-tracker, Q3 tarihi teyit edilince earnings-preview")
hangisinin seçileceğini sözlük sırasına göre belirliyor, metindeki asıl
sıraya göre değil -- ayrı bir doğruluk düzeltmesi gerekiyor.

### Ek bulgu -- adımlar arası hafıza (2026-08-14)

**Bulgu (koddan doğrulandı, tasarım kararı değil, düzeltilecek bug):**
`prepare_work_item()` ([pei_workflow.py:1507-1516](../src/adapter/pei_workflow.py))
bir sonraki adımı hazırlarken aynı ticker+run için tamamlanmış önceki
workflow'ların `result.md`'lerini doğru şekilde buluyor ve
`workflow_prepared` olayının `required_context_artifacts` alanına
kaydediyor. Ama `run_codex_analysis()` ([pei_workflow.py:892-916](../src/adapter/pei_workflow.py))
bunu hiç kullanmıyor -- codex'e yalnızca o adımın taze `pack.json` +
`instructions.md`'si veriliyor, önceki adımın çıktısı ne kopyalanıyor ne
referans veriliyor. Bu, `pitch` gibi `required_workflows` tanımlı
adımların kendi talimatındaki ("Build on the earlier result artifacts
supplied with this pack...") beklentiyle çelişiyor.

Kullanıcının asıl noktası daha genel: manuel ChatGPT kullanımında TEK bir
oturum açılıp o ticker için tüm zincir (tearsheet → earnings-preview →
comps → pitch → thesis-tracker) aynı konuşmada yapılıyor -- model
`required_workflows`'ta resmî olarak tanımlı olsun olmasın, o ticker için
o oturumda olan HER ŞEYİ hatırlıyor. Bizim mevcut per-step "taze process"
mimarimiz bunu hiç yakalamıyor.

**Karar: `codex exec resume` ile gerçek oturum sürekliliği kullanılacak.**

- Her `codex exec` çağrısı bir `session id` üretiyor (stdout'ta
  görünüyor, doğrulandı: `-m`/`-c model_reasoning_effort=` resume
  sırasında da geçerli -- yani bir ticker'ın zinciri aynı oturumda devam
  ederken her adım kendi model/effort ayarını (Terra/Sol/Luna tablosu)
  korur, resume bunu bozmaz).
- Bir ticker+run için tamamlanan her adımın `session_id`'si kaydedilir
  (workflow_completed payload'ına yeni bir alan). Sonraki adım, taze bir
  `codex exec` yerine `codex exec resume <session_id> -m <yeni_model> -c
  model_reasoning_effort=<yeni_effort> ...` ile aynı oturumu sürdürür.
- **Denetim izi bundan etkilenmez.** result.md, pack.json ve
  yapılandırılmış event payload'ları (agy çıkarımı) olduğu gibi kaydedilmeye
  devam eder -- session sürekliliği yalnızca LLM'i nasıl SÜRDÜĞÜMÜZÜ
  optimize ediyor, "ne olduğunu" kaydeden şey değişmiyor. Böylece
  `pei-workflow-orchestrator.md`'nin "repo'dan yeniden üretilebilir olmalı"
  ilkesi ihlal edilmiyor -- geçmişi ANLAMAK için session'a hiç ihtiyaç
  yok, yalnız zinciri aynı sadakatte SÜRDÜRMEK için kullanılıyor.
- **`resume` başarısız olursa (oturum bulunamadı/süresi geçti) otomatik
  olarak dosya-bazlı yedek moda geçilir:** taze bir session başlatılır ama
  o ticker+run için tamamlanmış TÜM önceki `result.md`'ler açıkça
  eklenir/referans verilir (yalnız `required_workflows`'ta tanımlı olanlar
  değil). İnsan müdahalesi gerekmez, zincir kopmaz, sadece daha pahalı
  çalışır.
- Bu zincir mekanizması **idea-generation'ı kapsamaz** -- idea-generation
  evren/kohort seviyesinde tek bir koşu, bir ticker'ın "oturumu" değil.
  Zincir, o ticker için ilk gerçek per-ticker adımdan (ör. tearsheet)
  başlar.

## Karar günlüğü

*(Her başlık netleştikçe buraya eklenecek: ne karar verildi, hangi
alternatifler değerlendirildi, neden bu seçildi.)*
