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

Gündem kullanıcı tarafından onaylandı (2026-08-14). Başlık 0-4 karara
bağlandı; sırada Başlık 5 var. Henüz hiçbir karar koda dökülmedi --
tasarım tamamlanmadan uygulamaya geçilmeyecek.

Başlık 3'te tarama hattı saf keşfe ayrıldığı için açık tezleri besleyen
tek kaynak portföy/tez oturumu oldu; Başlık 4 bunu haftalık mekanik
kontrol + gerekirse derin oturum olarak karşıladı.

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

### Başlık 2 — Çoklu / kademeli kohortlar (2026-08-15)

Somut senaryo: T0'da "Tech sektörü" taraması NVDA'yı A'ya koyup zinciri
yürütüyor; T15'te "Genel piyasa" taraması aynı ticker'ı bu sefer B'ye
koyuyor. Bugünkü kodda bu iki koşu birbirinden habersiz iki ayrı candidate
üretiyor ve iş kuyruğunda NVDA için ikinci, sıfırdan bir zincir beliriyor.

**Kararlar:**

1. **Candidate anahtarı `run_id:ticker` yerine sadece `ticker`.** Bir
   ticker = tek kayıt. Hangi olayın hangi koşudan geldiği zaten her
   event'in kendi `run_id`'sinde duruyor, denetim izi kaybolmuyor. Bu
   yeniden icat değil, `pei-workflow-orchestrator.md` Bölüm 6'daki onaylı
   ticker-sürekli kimlik ilkesine geri dönüş.
   *Reddedilen alternatif:* bir ticker'ın birden fazla paralel araştırma
   ipliği (sektör taraması vs. genel tarama ayrı ayrı ilerler) taşıması --
   sonunda tek tez ve tek portföy pozisyonu olacağı için iplikleri
   birleştirme problemi doğuruyor, karşılığı olmayan karmaşıklık.

2. **Kademe kuralı: yeni screen aktif işi kesmez.** `thesis_opened`
   durumundaki bir isim yeni bir taramadan doğrudan etkilenmez. Diğer tüm
   durumlar (`ready` / `waiting` / `blocked` / `deprioritized` /
   `completed`) yeni screen ile serbestçe güncellenir.
   *Reddedilen alternatifler:* "en son tarama koşulsuz kazanır" (ilerlemiş
   işi geri sarar), "her çakışma insana sorulur" (haftalık taramada el işi
   biriktirir).

3. **`in_progress` için özel davranış tanımlanmadı.** Tüm akış insan
   tetiklemeli ve seri (`cmd_start_idea` / `cmd_prepare` / `cmd_run_codex`
   / `cmd_attach_result`, `scripts/us_pei_dashboard_bridge.py`); bir iş
   sürerken yeni tarama başlatmak pratikte olmuyor. Kod bunu engellemiyor
   ama fail-closed bir guard eklenmedi -- bilerek yarım bırakılmış bloklu
   bir işin başka taramaları kilitlememesi için. Disiplinle çözülür.

4. **Bayatlama, bucket/setup değişimine bağlı.** Yeni screen aynı bucket +
   aynı setup diyorsa `completed_workflows` korunur, zincir kaldığı yerden
   devam eder. Bucket veya setup değiştiyse eski analiz artık farklı bir
   soruyu cevaplıyor demektir -- ilgili adımlar bayat sayılır ve
   `_first_missing_prerequisite` onları yeniden çalıştırır.
   Gerekçe: sinyal zaten screen'in kendisinde, ayrı bir gün-sayısı
   konfigürasyonu gerekmiyor.
   *Reddedilen alternatifler:* workflow başına tazelik penceresi (her adım
   için gün sayısı kararlaştırma yükü), her screen'in zinciri sıfırlaması
   (haftalık taramada hiçbir zincir bitmez), bayatlamanın hiç olmaması
   (bugünkü davranış -- 2 ay eski tearsheet üzerine pitch yazılabiliyor).

5. **Artifact dizinleri ticker-merkezli olur.** Per-ticker adımlar
   `data/pei-workflow/runs/<run_id>/work/...` altından çıkıp ticker altında
   toplanır; run dizini yalnız idea-generation çıktısı (evren/kohort
   seviyesi, bir ticker'a ait değil) için kalır. Bir ticker'ın tüm geçmişi
   tek yerde okunur. Göç gerekiyor ama bugün tek gerçek run olduğu için
   ucuz.
   *Açık uçlu detay (uygulama sırasında netleşecek):* aynı ticker aynı
   workflow'u bayatlama sonrası ikinci kez çalıştırabileceği için dizin ve
   iş kalemi kimliği tarih ayırıcı taşımalı (ör.
   `companies/<ticker>/<tarih>-<workflow>/`); `run_id`'nin iş kalemi
   kimliğindeki rolü de buna göre yeniden düşünülmeli.

**Kademe kuralının sonucu (Başlık 0'a bağlanıyor):** Tezi açık bir isim
yeni taramada düşerse (ör. A→C) bu sinyal sessizce olay günlüğüne
gömülmez -- yeni screen teze **evidence** olarak eklenir ve `position`
ekseni `re-underwrite`'a çekilir. Tez ayakta kalır, otomatik iş
tetiklenmez; haftalık kontrolde "tez hâlâ geçerli mi" sorusu bu kayıtla
cevaplanır. thesis-tracker'ın mevcut sözlüğü kullanılıyor, yeni kavram
icat edilmiyor.
*Reddedilen alternatifler:* `manual_review_required` üretmek (candidate
blocked'a düşer, tez durumuyla çelişir), yalnız panelde bir "conflicting
screen" rozeti (tezin kendi kaydında iz bırakmadığı için tez okunduğunda
sinyal kaybolur).

> **SONRADAN GEÇERSİZ KALDI (Başlık 3, 2026-08-15).** Başlık 3'te tezli
> isimlerin tarama hattına hiç girmemesine karar verildi. Tezli bir isim
> hiç screen edilmiyorsa "yeni taramada düşme" olayı da hiç gerçekleşmez
> -- yani bu tetikleyici mekanizmasız kaldı. Karar (yeni kanıt gelince
> `re-underwrite`) hâlâ doğru, ama **tetikleyicisini Başlık 4 (portföyde
> olan tezler) ve Başlık 5 (tezi olup fonlanmamışlar) tanımlamak
> zorunda** -- aksi hâlde açık tezler hiçbir kaynaktan beslenmez.

### Başlık 3 — Kapsama ve kademeli tarama (2026-08-15)

Başlık 3 gündemde "aynı kohortun zaman içinde tekrar taranması" olarak
yazılmıştı; konuşuldukça asıl sorunun **evren büyüdüğünde taramanın nasıl
kademelendirileceği** olduğu ortaya çıktı. Evren bugün 87 isim ama sabit
değil, ileride S&P 500 ölçeğine çıkabilir. Tek bir taramaya 500 isim
verilirse -- pack inceltilse bile -- çıktı kalitesi düşer. Dilimleme
şart. Ama dilimleme "haftada bir dilim" demek değil; aynı gün birkaç
dilim ayrı oturumlarda çalıştırılabilir.

**Ampirik olduğu için burada karara bağlanmayanlar** (config parametresi
olarak dışarı alınacak, ilk turda ölçülüp ayarlanacak; koda gömülmeyecek):
dilim boyutu (bir oturumda kaç ticker) ve pack inceltmesi (ticker başına
hangi alanlar kalır). İkisi de ölçmeden bilinemez.

**Kararlar:**

1. **İki turlu yapı.** Tur 1: dilimler kendi içinde taranır, her dilim
   kendi finalistlerini işaretler (dilim-göreceli yargı). Tur 2: tüm
   dilimlerin finalistleri tek bir oturumda yan yana karşılaştırılır,
   gerçek A/B/C orada belirlenir. Bu, "inceltme" sorusunu da doğal olarak
   çözüyor: Tur 1 ince pack + çok isim, Tur 2 tam pack + az isim.
   *Reddedilen alternatifler:* mutlak eşik (dilimden bağımsız sabit
   kriterler; daha basit ama eşiklerin kendisi tanımsız), göreceli ama
   ikinci tur yok (her dilimin finalisti doğrudan A sayılır -- zayıf
   dilimlerden de A üretir, portföy seviyesinde çöp birikir).

2. **Dilim kriteri: sektör + boyut düzeltmesi.** Sektör birincil kriter,
   çünkü dilim-göreceli yargının anlamlı olması için isimlerin
   karşılaştırılabilir olması gerekiyor ("yazılım şirketleri arasında en
   cazip 3" anlamlı, "bu rastgele 25 arasında en cazip 3" değil). Ama saf
   sektör dilimlemesi işlemiyor: bugünkü evrende technology 31,
   consumer-staples 24, health-care 15, industrials 12,
   communication-services 5 -- 5 isimlik dilimden 3 finalist %60 geçiş
   oranı demek. Bu yüzden büyük sektörler alt-gruplara bölünür, çok
   küçükler komşu sektörle birleştirilir; dilimler hedef boyuta çekilir.

3. **Tarama hattı saf keşiftir; tezli isimler hiç girmez.** Tur 1 ve Tur
   2, yalnızca tezi olmayan isimler için çalışır. Dilimler kurulurken
   tezli isimler evrenden çıkarılır; tez `retired` olunca isim keşif
   havuzuna geri döner.
   Gerekçe: portföy/tez kararı ile araştırma önceliği **farklı sorular**.
   Portföydeki bir isim "daha iyi bir aday çıktı" diye elenmez -- pozisyon
   sayısı artırılabilir, ağırlıklar yeniden dengelenebilir, korelasyon ve
   yoğunlaşma devreye girer. Bu kararı araştırma sıralamasıyla aynı
   oturuma sıkıştırmak ikisini de bozar.
   *Reddedilen alternatifler:* tezli isimlerin Tur 1'i atlayıp doğrudan
   Tur 2'ye girmesi (yeni adaylarla aynı ölçekte görülürlerdi ama Tur 2'ye
   dolaylı bir eleme yetkisi yüklenirdi), tezli isimlerin kendi sektör
   diliminde normal taranması (Tur 1 elemesi dilim-göreceli ve zayıf bir
   sinyal; `re-underwrite` gibi güçlü bir mekanizmayı tetiklemesi yanlış
   alarm üretir).
   **Bedeli, açıkça kabul edildi:** "bu yeni aday mevcut pozisyonumdan
   daha iyi mi" karşılaştırması tarama hattında hiç yapılmaz; o soruyu
   Başlık 4'teki portföy oturumu cevaplamak zorunda.

4. **Tur 2, tüm dilimler bitince tek seferde çalışır.** Bir "tur" = tüm
   evrenin dilimlerinin taranması + sonunda tek bir finalist karşılaştırma
   oturumu. Finalistler tur bitene kadar bekler.
   *Reddedilen alternatif:* periyodik Tur 2 (her gün biriken finalistlerle)
   -- her Tur 2 farklı bir aday kümesiyle karşılaştırma yapardı, yani
   dilim-göreceli sorunun aynısı bir üst katmanda tekrarlanırdı.
   *Kabul edilen bedel:* ilk dilimin finalisti tur uzunluğu kadar bekler.

**Not:** Bu tasarım, gündemdeki orijinal "T0'daki grup T60'ta tekrar mı
taranır" sorusunu kapsıyor -- evren turlar hâlinde sürekli yeniden
taranıyor, hiçbir isim kalıcı olarak unutulmuyor. Bu, **Başlık 1'in 1.
kararını (C kovasına 3 aylık hatırlatıcı) gereksiz kılıyor olabilir**:
C'deki bir isim zaten bir sonraki turda yeniden değerlendirilecek.
Başlık 6 ele alınırken bu madde tekrar gözden geçirilmeli.

### Başlık 4 — Portföy takibi (2026-08-15)

Başlık 3, tarama hattını saf keşfe ayırdığı için açık tezleri besleme
sorumluluğu tamamen buraya düştü. Ayrıca gündemdeki "muhasebe" ile
"portföy seviyesinde karar" ayrımı korunuyor: ilki bizim tuttuğumuz
defter, ikincisi skill'in işi.

**Kararlar:**

1. **Ritim mandate'ten geliyor, icat edilmiyor.** idea-generation
   talimatındaki mandate zaten "Review weekly, rebalance monthly ... 
   neither is obliged to [change the portfolio]" diyor. Buna karşılık iki
   ayrı oturum: **haftalık tez sağlığı** ve **aylık rebalans**. Farklı
   sorular oldukları için ayrı kalıyorlar.
   *Reddedilen alternatifler:* tek haftalık oturum (her hafta tam rebalans
   düşüncesi gereksiz işlem dürtüsü yaratır), olay-güdümlü/takvimsiz
   (mandate'in ritmiyle çelişir, sessiz dönemlerde portföy hiç gözden
   geçirilmez).

2. **Haftalık kontrol iki kademeli: önce mekanik, sonra gerekirse derin.**
   Her açık tezin kayıtlı beklentileri taze veriyle LLM'siz karşılaştırılır;
   yalnız sapma gösterenler için `thesis_tracker` oturumu açılır. Sessiz
   haftalarda hiç LLM çağrısı olmaz. `check_triggers` altyapısı zaten var.
   *Reddedilen alternatifler:* her tez için ayrı oturum (10 tez = haftada
   10 oturum, çoğu "değişen bir şey yok" diyecek), tek toplu oturum (tez
   başına derinlik düşer -- dilim-göreceli sorunun aynısı).
   **Bu, Başlık 2'de mekanizmasız kalan `re-underwrite` tetikleyicisinin
   yaşadığı yerdir.**

3. **Sapma ölçüsü teze özeldir, jenerik değil.** Tez açılırken (pitch
   `actionable_candidate` → `thesis_opened`) `first_rejection`'ın metinsel
   hali agy çıkarımıyla ölçülebilir eşiklere dönüştürülür ve tez kaydına
   yazılır.
   *Reddedilen alternatif:* her tez için aynı jenerik ölçü seti (yeni
   bilanço, fiyat eşiği, revizyon dengesi, değerleme sapması) -- kurmak
   kolay ama tezin asıl bozulma koşulunu yakalamaz.

4. **Ölçülemeyen bozulma koşulu atılmaz, metinsel saklanır.** Pack'te
   karşılığı olmayan koşullar (ör. "hyperscaler capex'i backlog'a
   dönüşmezse") tez kaydında metin olarak kalır ve haftalık oturumda
   "elle kontrol edilecek koşullar" olarak listelenir. Ölçülebilenler
   mekanik kontrole girer.
   *Reddedilen alternatifler:* sert fail-closed (tüm koşullar ölçülebilir
   değilse tez açılmaz -- en değerli nitel tezler tam bu yüzden bloklanır),
   ölçülemeyenleri atmak (tezin asıl gerekçesi kaybolur).

5. **Aylık rebalans mantığı `portfolio-risk-management` skill'ine
   devredilir.** Histerezis, ağırlıklandırma, korelasyon ve yoğunlaşma
   kurallarını kendimiz tanımlamıyoruz; skill zaten bu iş için yazılmış.
   Bizim işimiz orkestrasyon: skill'i kataloğa eklemek, portföy paketini
   üretmek, çıktısını kaydetmek. Repo'nun mevcut deseniyle tutarlı --
   analitik yargı skill'in, akış bizim.
   **Açık iş:** skill kurulu olmadığı için girdi/çıktı sözleşmesi
   bilinmiyor. `config/pei-workflows.json`'a eklenecek `pack_step`,
   `required_workflows` ve `result_contract` alanları ancak skill
   incelendikten sonra doldurulabilir.

6. **Portföy defteri olay tabanlı olur.** Append-only işlem kaydı
   (alım/satım/temettü; tarih, fiyat, adet ve **hangi teze bağlı**);
   mevcut pozisyonlar bundan türetilir. Repo'nun geri kalanıyla aynı desen
   (`events.jsonl`, append-only tez kaydı). Gerekçe: "bu tezle ne zaman
   girdim, ne kazandım" sorusu ancak böyle cevaplanabilir -- tezlerin
   gerçekten işe yarayıp yaramadığını ölçmenin tek yolu bu.
   *Reddedilen alternatifler:* mutable pozisyon tablosu (kapanan pozisyon
   iz bırakmadan siliniyor), olay defteri + türetilmiş önbellek (10-20
   pozisyon ölçeğinde gereksiz).

**Önemli not:** Mevcut `src/adapter/portfolio.py` / `data/portfolio/
portfolio.json` **dummy bir çalışma**; bu tasarımda referans alınmadı.
Gerçek defter yukarıdaki 6. maddeye göre sıfırdan kurulacak.
