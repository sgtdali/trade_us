# Uygulama planı — portföy karar günlüğü

Bu dosya **çalışma listesidir**, tasarım dokümanı değildir.

- **Ne yapılacağı** burada. Kutuları işaretleyin, notları buraya yazın.
- **Nasıl olacağı** [pei-company-lifecycle-tasarim.md](pei-company-lifecycle-tasarim.md)'de.
  Bir görevin ayrıntısı belirsizse önce oraya bakın.
- **Neden öyle olduğu** [tasarım oturumu arşivinde](tasarim-oturumlari/2026-08-codex-fon-sistemi/README.md).
  Bir kararı sorgulamadan önce oraya bakın; büyük ihtimalle tartışılmıştır.

## Bu dosyayı kullanan ajanlara

1. **Sıra bağlayıcıdır.** Fazlar birbirinin üzerine kuruluyor. Bir fazı
   atlayıp ileriye geçmeyin; bağımlılığı `← F1.4` gibi işaretli görevler
   o görev bitmeden başlayamaz.
2. **Kutuyu ancak "bitti tanımı" karşılandığında işaretleyin.** Kod yazılmış
   olması yetmez; her görevin yanında ne zaman bittiği yazılı.
3. **Tasarım dokümanını değiştirmeyin.** Uygulama sırasında tasarımın yanlış
   veya eksik olduğu ortaya çıkarsa: görevi `⚠ TASARIM SORUNU` diye
   işaretleyin, aşağıdaki "Uygulama notları"na yazın ve kullanıcıya sorun.
   Tasarımı tek taraflı değiştirmeyin.
4. **Kapsam dışı listesine uyun.** Tasarım dokümanı Bölüm 12'de bilinçli
   olarak yapılmayacaklar var. "Bir de şunu ekleyeyim" demeyin; gerçekten
   gerekiyorsa önce büyütme tetikleyicisini gösterin.
5. **Her faz sonunda durum tablosunu güncelleyin.**

## Durum

| Faz | Konu | Durum |
|---|---|---|
| F0 | Kullanıcı kararları | ⬜ Başlanmadı — **her şeyi bloklar** |
| F1 | Defter ve manuel muhasebe | ⬜ Başlanmadı |
| F2 | Capital policy ve karar akışı | ⬜ Başlanmadı |
| F3 | Tez lifecycle ve izleme sözleşmesi | ⬜ Başlanmadı |
| F4 | Mekanik kontrol motoru | ⬜ Başlanmadı |
| F5 | Job, dedup, inbox | ⬜ Başlanmadı |
| F6 | İlk otomatik recipe | ⬜ Başlanmadı |
| F7 | `research-cycle` — kendi kendine çalışma | ⬜ Başlanmadı |
| F8 | İkinci dalga tetikleyiciler | ⬜ Başlanmadı |
| F9 | Canlılık ve kalite uyarıları | ⬜ Başlanmadı |
| F10 | Discovery | ⬜ Başlanmadı |

İşaretler: ⬜ başlanmadı · 🔵 sürüyor · ✅ bitti · ⚠ engelli/sorunlu

**Kritik eşik: F7.** Oraya kadar sistem elle sürülür; F7'den sonra kendisi
gözler ve kendisi başlatır.

---

## F0 — Kullanıcı kararları

**Bu faz bitmeden F2 ve sonrası başlayamaz.** F1 (defter, şemalar, DDL)
cevapları beklemeden yapılabilir.

- [ ] **F0.1 Fon perimetresi** — hangi broker hesabı ve nakit bu portföye
  dahil, açılış tarihi ne?
  *Bitti:* `fund_definition` dosyasında `included_accounts` ve `opening_as_of`
  dolu.
- [ ] **F0.2 Raporlama para birimi** — kanonik NAV USD mi TL mi? Diğeri yalnız
  bağlam serisi mi?
  *Bitti:* `base_currency` dolu, gerekçesi bir cümleyle yazılı.
- [ ] **F0.3 Sermaye amacı** — hangi ufukta yönetilecek, öngörülebilir çekim
  ihtiyacı var mı?
  *Bitti:* `capital_horizon` ve `liquidity_need_mode` dolu.
- [ ] **F0.4 Risk zarfı** — kabul edilebilir portföy drawdown'ı, pozisyon
  başına kayıp bütçesi (çıpa: 100 bp NAV), mutlak tek-isim tavanı.
  *Bitti:* `position_loss_budget_bps_nav`, `max_security_weight_bps`,
  `max_issuer_weight_bps` dolu.
- [ ] **F0.5 Capital policy v0 dosyasını doldur** ← F0.1-F0.4
  *Bitti:* `config/fund/capital-policy.json` tasarım Bölüm 3'teki bütün
  alanları taşıyor; hiçbir alan `null` değil (her biri değer veya `disabled` /
  `unbounded_by_policy` / `not_applicable` / `monitor_only`); varsayılan
  kullanılan her sayı `provisional` işaretli.

---

## F1 — Defter ve manuel muhasebe

Hedef: açılış kitabı ve elle işlem girişi, pozisyon/nakit/NAV replay.

### Şemalar

- [ ] **F1.1 `schemas/fund/common.schema.json`** — UUIDv7, decimalString,
  Money, Currency, UtcInstant, LocalDate, MarketSessionDate, digest, artifact
  ref.
  *Bitti:* Mevcut `valuation-common.schema.json` gelenekleriyle uyumlu
  (pattern tabanlı, `format`'a güvenmiyor); pozitif ve negatif fixture'ları
  geçiyor.
- [ ] **F1.2 `schemas/fund/instrument-master.schema.json`** (stub) —
  `issuer_id` / `security_id` / `listing_id`, güncel ticker, venue, currency.
  *Bitti:* Üç kimlik ayrı; dar ve kapalı; ticker geçmişi ve kurumsal işlem
  ilişkileri **yok**.
- [ ] **F1.3 `schemas/fund/account-event.schema.json`** ← F1.1
  *Bitti:* Tasarım Bölüm 8'deki alanlar; `event_type` kapalı enum
  (`opening_position`, `opening_cash`, `buy`, `sell`, `deposit`, `withdrawal`,
  `dividend`, `fee`, `quantity_adjustment`, `correction`);
  `cost_basis_status` `known`/`unknown`; sentetik opening fill üretmiyor.
- [ ] **F1.4 `schemas/fund/capital-policy.schema.json`** ← F1.1
  *Bitti:* Tasarım Bölüm 3 alan tablosunun tamamı; `null` reddediliyor;
  `readiness_multipliers` serbest map değil kapalı anahtarlı sabit nesne.

### Depolama

- [ ] **F1.5 SQLite DDL ve migration** ← F1.3
  *Bitti:* Tablolar oluşuyor; exact decimal alanlar `TEXT`; `account_event`
  üzerinde UPDATE/DELETE reddeden trigger var; `schema_migrations` tablosu
  sürüm tutuyor.
- [ ] **F1.6 Tek commit kapısı** ← F1.5
  *Bitti:* Bütün yazımlar tek `commit()` fonksiyonundan geçiyor;
  `BEGIN IMMEDIATE` kullanılıyor; iki eşzamanlı süreç testinde olay
  kaybolmuyor; aynı komut iki kez çalıştırıldığında ikinci kayıt oluşmuyor.

### CLI ve projection

- [ ] **F1.7 `fund trade record`** ← F1.6 — elle alım/satım/nakit girişi.
  *Bitti:* Alım, satım, temettü, ücret ve nakit giriş/çıkış kaydedilebiliyor;
  aynı işlemi ikinci kez girmeye çalışınca uyarı çıkıyor.
- [ ] **F1.8 `fund correct`** ← F1.7 — hatalı kaydı düzeltme.
  *Bitti:* Düzeltme yeni bir satır (`corrects_event_id`); eski satır
  değişmiyor; projection düzeltilmiş sonucu veriyor.
- [ ] **F1.9 Pozisyon / nakit / NAV projection'ı** ← F1.7
  *Bitti:* Elle hesaplanan bir fixture ile pozisyon adetleri, nakit, NAV ve
  ağırlıklar birebir eşleşiyor; `cost_basis_status: unknown` olan pozisyonda
  unrealized P&L **hesaplanmıyor**, sıfır gösterilmiyor.
- [ ] **F1.10 Replay ve idempotency testi** ← F1.9
  *Bitti:* Veritabanı silinip olaylardan yeniden kurulunca aynı state çıkıyor;
  aynı açılış kitabı iki kez içeri alınınca pozisyon ve nakit ikiye
  katlanmıyor.
- [ ] **F1.11 Açılış kitabını gir** ← F0.1, F1.10
  *Bitti:* Gerçek pozisyonlar ve nakit girildi; broker ekranıyla adet ve nakit
  karşılaştırıldı; açıklanamayan fark varsa kapatılmadan not edildi.

**F1 bitti sayılır:** Broker kaynaklı açılış kitabı exact para/adetlerle bir
kez kaydedilebiliyor, tekrar çalıştırmada çoğalmıyor, fiyatlandırılıp aynı
pozisyon/nakit/NAV state'i replay edilebiliyor.

---

## F2 — Capital policy ve karar akışı

← F0.5, F1.11

- [ ] **F2.1 `schemas/fund/assessment-record.schema.json`**
  *Bitti:* Tez özeti, readiness (`watchlist`/`starter`/`core`), downside
  senaryosu ve yüzdesi, kanıt tarihi, `review_due`, kaynak artefakt
  referansı, `human_authored` bayrağı ve `derived_from`.
- [ ] **F2.2 `schemas/fund/decision-record.schema.json`**
  *Bitti:* Tasarım Bölüm 8'deki alanlar; `shadow`/`live` ayrımı var;
  immutable.
- [ ] **F2.3 Policy hesaplayıcı** ← F1.4
  *Bitti:* `base_weight`, `readiness_weight`, downside kapasitesi, issuer/
  security/nakit kapasiteleri ve `policy_compliant_max_weight` hesaplanıyor;
  **bağlayıcı kısıt** (`binding_constraint`) doğru raporlanıyor; no-trade
  bandı değerlendiriliyor.
- [ ] **F2.4 `fund assess`** ← F2.1
  *Bitti:* Ekranda pozisyon ağırlığı, nakit, P&L, önerilen işlem ve sermaye
  riski **görünmüyor**; "bu pozisyona sahip olmasaydınız aynı downside'ı kabul
  eder miydiniz" sorusu soruluyor; sonuç `assessment_record` olarak
  dondurulıyor.
- [ ] **F2.5 `fund trade-preview`** ← F2.3, F2.4
  *Bitti:* Tasarım Bölüm 4'teki çıktı formatı üretiliyor; policy dışı işlemde
  policy içi üst sınır hesaplanıyor; üç seçenek (indir / iptal / gerekçeyle
  policy dışı kaydet) çalışıyor; karar `decision_record` olarak dondurulıyor.
- [ ] **F2.6 `fund trade-add`** ← F2.5, F1.7 — kararı gerçekleşmeye bağlama.
  *Bitti:* Kararla `account_event` arasındaki bağ (`decision_id`) kuruluyor.
- [ ] **F2.7 `fund review`** — aylık oturum.
  *Bitti:* NAV, nakit, drawdown, pozisyon tablosu ve uyarılar gösteriliyor;
  `no_change` da bir karar olarak gerekçe koduyla kaydediliyor; çözülmemiş
  adjudication varken `no_change_with_pending_review` işaretleniyor.
- [ ] **F2.8 Property testleri** ← F2.3
  *Bitti:* En az şunlar geçiyor: downside kötüleşirse ilgili tavan artamaz;
  readiness düşerse band genişleyemez; loss budget daralırsa tavan artamaz;
  ağırlıklar + nakit = %100 (tolerans içinde); policy sıkılaşırsa uygun
  portföy kümesi genişleyemez.
- [ ] **F2.9 Golden fixture'lar** ← F2.3
  *Bitti:* 6-8 okunabilir kanonik kitap ve beklenen çıktıları donduruldu
  (tamamen nakit, aşırı yoğun tek pozisyon, dengeli kitap, limitlere yaklaşmış
  kitap, hard-limit ihlalli kitap, split içeren kitap, `cost_basis_unknown`
  içeren kitap).
- [ ] **F2.10 Salt-okunur HTML görünümü** ← F1.9, F2.5
  *Bitti:* NAV, nakit, pozisyonlar, policy tavanları, ihlaller, review-due
  listesi ve son kararlar tek sayfada okunabiliyor; sayfa aynı veriden
  yeniden üretilebiliyor; yazma yolu **yok**.

**F2 bitti sayılır:** Tek bir gölge kararı uçtan uca çalışıyor —
`assess → trade-preview → decision → trade/no_change`.

---

## F3 — Tez lifecycle ve izleme sözleşmesi

← F2.4

- [ ] **F3.1 `schemas/fund/thesis.schema.json`**
  *Bitti:* `thesis_id`, `security_id`, `opened_at`, `thesis_statement`,
  `status` (`active`/`review_required`/`broken`/`closed`),
  `current_assessment_id`, sürümlü `monitoring_contract`, `closed_at` ve
  `close_reason`. Exposure alanı **yok** (o `account_event` projection'ından
  gelir).
- [ ] **F3.2 `monitoring_contract` alt belgesi** ← F3.1
  *Bitti:* `mechanical_rules[]` (rule_id, metric_id, period_basis, test_type,
  operator, threshold) ve `qualitative_checks[]` (check_id, question,
  review_on[], review_due, last_reviewed_at); kapalı sözlükler tasarım Bölüm
  5'teki gibi; tez başına en fazla 5 kural.
- [ ] **F3.3 `fund thesis open`** ← F3.1, F2.4
  *Bitti:* Kabul edilmiş bir assessment'tan tez açılıyor; aynı security için
  ikinci açık tez açılamıyor.
- [ ] **F3.4 Tez durum geçişleri** ← F3.3
  *Bitti:* `active → review_required → active|broken|closed` geçişleri
  çalışıyor; **hiçbir kod yolu tezi otomatik `broken` veya `closed`
  yapamıyor** (test var).
- [ ] **F3.5 Bir gerçek tez yaz** ← F3.2
  *Bitti:* Mevcut pozisyonlardan biri için tez, 1-2 mekanik kural ve 1-2 nitel
  soru elle yazıldı; kuralların metrik kataloğunda karşılığı doğrulandı.

---

## F4 — Mekanik kontrol motoru

← F3.2

- [ ] **F4.1 Metrik binding doğrulaması**
  *Bitti:* Sözleşme aktive edilirken `metric_id`, birim, dönem tipi ve test
  türü `config/pipeline/metric-catalog.json` ile karşılaştırılıyor;
  eşleşmiyorsa sözleşme **aktive edilmiyor**.
- [ ] **F4.2 Kontrol motoru (saf fonksiyon)** ← F4.1
  *Bitti:* Dondurulmuş veri fixture'ında `not_breached` / `breached` /
  `unavailable` üretiyor; katalog veya veri yapısı değiştiyse çalışma anında
  yeniden doğrulayıp `unavailable` veriyor, "değişiklik yok" **vermiyor**.
- [ ] **F4.3 `monitoring_check_record`** ← F4.2
  *Bitti:* Hangi kural, hangi accession/veri sürümü, hangi sonuç kaydediliyor;
  `unavailable` hiçbir yerde "sapma yok" sayılmıyor.
- [ ] **F4.4 Breach → `review_required`** ← F4.3, F3.4
  *Bitti:* Mekanik breach tezi `review_required` yapıyor ve başka hiçbir şey
  yapmıyor.

---

## F5 — Job, dedup, inbox

← F4.4

- [ ] **F5.1 `schemas/fund/research-job-record.schema.json`**
  *Bitti:* Tetikleyici snapshot'ı, `rule_id` + `rule_version`, recipe,
  `attempts[]`, sonuç referansı, hata durumu.
- [ ] **F5.2 Dedup ve cooldown** ← F5.1
  *Bitti:* Aynı `thesis_id + monitoring_contract_version + evidence_accession`
  ikinci kez iş açmıyor; aynı teze ait birden fazla tetikleyici tek işte
  birleşiyor.
- [ ] **F5.3 Retry politikası** ← F5.1
  *Bitti:* Tasarım Bölüm 6'daki hata tablosu uygulanıyor (veri hatası,
  skill/transport hatası, kontrat hatası, geç sonuç); üç başarısız cycle'dan
  sonra otomatik deneme duruyor.
- [ ] **F5.4 Q0/Q1/Q2 kuyruk projection'ı** ← F5.1
  *Bitti:* Üç sınıf doğru dolduruluyor; Q1 sıralaması tasarımdaki gibi;
  kuyruk ayrı bir defter değil, job ve açık assessment'lardan türetiliyor.
- [ ] **F5.5 `fund inbox`** ← F5.4
  *Bitti:* Sessiz haftada "işlem gerekmiyor" özeti; iş varsa neden/son
  tarih/tahmini süre gösteriliyor.
- [ ] **F5.6 `fund adjudicate <job_id>`** ← F5.5
  *Bitti:* Tasarım Bölüm 7'deki ekran; sermaye etkisi **görünmüyor**; toplu
  onay yok; `Accept` varsayılan değil; üç kapalı soru soruluyor; maddi
  değişiklikte gerekçe zorunlu; `Reject` ve `Human-authored replacement`
  yolları çalışıyor; incelemeden geçiş `acknowledged_without_full_adjudication`
  olarak kaydediliyor.

---

## F6 — İlk otomatik recipe

← F5.6

- [ ] **F6.1 SEC accession gözlemcisi** — security başına son görülen
  accession watermark'ı.
  *Bitti:* Yeni 10-Q/10-K deterministik olarak tespit ediliyor; aynı filing
  ikinci kez tetikleyici üretmiyor.
- [ ] **F6.2 Dispatch tablosu (tek kural)** ← F6.1
  *Bitti:* "Yeni ilgili filing + açık tez → `deep-dive → tracker`,
  `update_against_prior`" kuralı kodda tipli ve kapalı; `rule_version` var.
- [ ] **F6.3 Nitel soruların pack'e enjeksiyonu** ← F3.2
  *Bitti:* Tezin vadesi gelmiş nitel soruları deep-dive pack'ine açıkça
  giriyor; skill'in kendiliğinden bakacağı varsayılmıyor.
- [ ] **F6.4 Skill çıktısı sözleşmeleri** ← F6.2
  *Bitti:* `deep-dive` ve `tracker` çıktıları için makine-okunur sidecar
  şemaları var; şema veya kontrat geçmezse sonuç adjudication'a
  **sunulmuyor**.
- [ ] **F6.5 Görünürlük kontrolü** ← F6.2
  *Bitti:* Pack'te pozisyon ağırlığı, nakit, P&L, ortalama maliyet ve sermaye
  riski **bulunmadığı** testle doğrulandı.
- [ ] **F6.6 Elle tetiklemeli uçtan uca test** ← F6.4
  *Bitti:* Elle verilen bir filing kanıtı → mekanik kontrol → deep-dive →
  tracker → Q1 inbox → adjudication → yeni assessment → tez durumu zinciri
  çalışıyor.

---

## F7 — `research-cycle` (kritik eşik)

← F6.6

- [ ] **F7.1 `fund research-cycle` komutu**
  *Bitti:* Veriyi tazeliyor, gözlemleri çıkarıyor, kuralları eşleştiriyor,
  dedup uyguluyor, işleri **seri** çalıştırıyor, doğruluyor, kuyruğa koyuyor.
- [ ] **F7.2 Watermark ve catch-up** ← F7.1
  *Bitti:* Bilgisayar birkaç gün kapalı kalsa bile aradaki filing kaybolmuyor;
  cycle son watermark'tan devam ediyor.
- [ ] **F7.3 Task Scheduler kurulumu** ← F7.1
  *Bitti:* Gecelik çalışıyor; `StartWhenAvailable` açık; kurulum adımları
  yazılı.
- [ ] **F7.4 Heartbeat ve sabah durum özeti** ← F7.1
  *Bitti:* Son cycle zamanı ve sonucu görünüyor; başarısız cycle sessiz
  kalmıyor; Q0 uyarısı doğuyor.

**F7 bitti sayılır — sistem kendi kendine çalışıyor:** kullanıcı filing'i
hatırlamıyor, skill seçmiyor; sabah yalnız sonucu yargılıyor.

---

## F8 — İkinci dalga tetikleyiciler

← F7.4. Sırayla ekleyin, her birini ayrı doğrulayın.

- [ ] **F8.1 Review vadesi tetikleyicisi** → `tracker`
  *Bitti:* Yeni kanıt olmasa bile `review_due` dolunca tracker çalışıyor.
- [ ] **F8.2 Fiyat şoku tetikleyicisi** → kör ilk geçişli review
  *Bitti:* Adjusted-close baseline ve eşik tanımlı; `independent_then_reconcile`
  modu çalışıyor (ilk geçişte önceki hüküm ve pozisyon **gösterilmiyor**).
- [ ] **F8.3 `FilingRef`'e SEC `items` alanı** — Item 2.02 tespiti için.
  *Bitti:* Ham submissions'taki `items` typed katmana taşındı;
  `earnings_release` gözlemi çalışıyor.
- [ ] **F8.4 `date_due` düzeltmesi** — tarih tetikleyicisi kanıt beklesin.
  *Bitti:* Tarih tek başına `trigger_satisfied` **üretmiyor**; yalnız kanıt
  kontrolü vadesi doğuruyor; `release_observed` ile `evidence_available`
  ayrımı var. *(Mevcut `evaluate_trigger` bunu yapmıyor — tasarım Bölüm 6.)*
- [ ] **F8.5 `check_triggers` yerine tez-odaklı gözlemciler**
  *Bitti:* Eski `state == "waiting"` filtresine bağlı tarama kaldırıldı; açık
  tezler ve pozisyonlar taranıyor.

---

## F9 — Canlılık ve kalite

← F8.5

- [ ] **F9.1 `monitoring_coverage`**
  *Bitti:* Her aktif tez için `healthy` / `degraded` / `blind` hesaplanıyor;
  ilgili filing geldiği hâlde kural değerlendirilemediyse `degraded`; iki
  ardışık kanıt döneminde `unavailable` ise `blind`; `blind` tez Q0'a düşüyor
  ve yeni risk artırımı bloklanıyor.
- [ ] **F9.2 Dispatch sağlık raporu** ← F7.1
  *Bitti:* Kural bazında `enabled`, `last_observed`, `last_dispatched`,
  `jobs_30d`, `failures_30d` görülebiliyor; hiç ateşlemeyen kural fark
  ediliyor.
- [ ] **F9.3 Adjudication kalite sinyalleri** ← F5.6
  *Bitti:* Değiştirmeden kabul oranı, çok kısa adjudication sayısı, kaynak
  açılmadan verilen kabuller ölçülüyor; eşik aşılınca
  `adjudication_quality_warning` gösteriliyor.
- [ ] **F9.4 Yanlış alarm sayacı** ← F4.3
  *Bitti:* Yıllık `review_required` sayısı ve `measurement_error` /
  `decision_irrelevant_breach` ayrımı raporlanıyor; hedef bant (yılda 4-8)
  aşılınca kalibrasyon uyarısı çıkıyor.

---

## F10 — Discovery

← F9.4. **Mevcut kitabın izlenmesi güvenilir olmadan başlamayın.**

- [ ] **F10.1 Periyodik discovery dispatch kuralı**
  *Bitti:* Düşük frekanslı `idea-generation` aynı sabit dispatch
  mekanizmasıyla çalışıyor; portföy pozisyonları pack'e **girmiyor**.
- [ ] **F10.2 Discovery çıktısının sınırı**
  *Bitti:* Sonuç yalnız araştırma adayı üretiyor; sermaye kararı, tez veya
  readiness üretmiyor; aday `onboarding_underwrite` yoluna giriyor.
- [ ] **F10.3 Aday üretim hızının sınırlanması**
  *Bitti:* Aynı anda açık aday sayısı sınırlı; kitap doluyken discovery
  yoğunluğu azalıyor.

---

## Sürekli görevler

Bir fazın parçası değil; süreç boyunca.

- [ ] **S1 Gölge işletim** — F2 bittikten sonra başlar. Her sermaye kararı
  `shadow` olarak kaydedilir. En az iki aylık döngü ve bir olay vakası
  görülmeden `live` moda geçilmez.
- [ ] **S2 Kalibrasyon defteri** — Her `provisional` policy değeri için
  gerçek gözlem biriktirin: kaç kez bağlayıcı oldu, kaç yanlış alarm üretti,
  kullanıcı kaç kez override etti. Üç ayda bir gözden geçirin.
- [ ] **S3 Plugin sürüm sabitleme** — `public-equity-investing` sürümü
  pinlenir; yeni sürüm önce contract fixture'larından geçmeden kullanılmaz.
- [ ] **S4 Haftalık yük ölçümü** — Gerçek harcanan dakikayı kaydedin. Mevcut
  kitap için 15-25 dk/hafta hedefi aşılıyorsa neden aşıldığını yazın.

---

## Bilinen kod sorunları

Mevcut repoda tespit edilmiş, uygulama sırasında karşılaşılacak şeyler.
Hangi fazda ele alınacağı yazılı.

| Sorun | Nerede | Faz |
|---|---|---|
| `evaluate_trigger` `date_due` için tarihin tahmin olduğunu okumuyor; kanıt beklemiyor | `pei_workflow.py` | F8.4 |
| `check_triggers` yalnız `state == "waiting"` adayları tarıyor; açık tezleri görmüyor | `pei_workflow.py` | F8.5 |
| `FilingRef` SEC'in `items` alanını düşürüyor (Item 2.02 tespiti için gerekli) | `models.py` | F8.3 |
| `thesis_tracker` katalogda tek seferlik terminal adım olarak modellenmiş | `config/pei-workflows.json` | F6.2 |
| `bucket = c.get("bucket") or "B"` — eksik bucket sessizce B oluyor | `pei_workflow.py` | F10.1 |
| `if not raw_ticker: continue` — boş ticker sessizce atlanıyor | `pei_workflow.py` | F10.1 |
| agy 24.000 karakter sınırı argv taşıma sınırına bağlı | `pei_workflow.py` | F6.4 (sidecar'a geçilince düşebilir) |
| `codex exec resume` için `-C` global bayrak olarak `exec`'ten önce verilmeli | `pei_workflow.py` | F6.2 |
| `-s read-only` bu Windows kurulumunda uygulanmıyor (`config.toml` `danger-full-access`) | codex config | F6.2 — bilinçli kabul mü, düzeltilecek mi karar verin |

**Eski `data/pei-workflow/events.jsonl` ve `src/adapter/portfolio.py`**: yeni
defter bunların yerini almıyor, **yanına** kuruluyor. Eski koşu verisi deneme
verisidir, göç edilmeyecek. Yeni sistem çalıştıktan sonra eskisinin
kapatılmasına karar verilir.

---

## Uygulama notları

Ajanlar buraya yazar. Her not: tarih, hangi görev, ne bulundu.

<!-- Örnek:
### 2026-08-20 — F1.5
SQLite'ta `TEXT` decimal alanlarda karşılaştırma yaparken dikkat: SQL içinde
`>` operatörü metin sıralaması yapıyor. Filtreleme Python tarafında Decimal
ile yapılmalı.
-->

_(henüz not yok)_

---

## Tasarım soruları

Uygulama sırasında tasarımın eksik veya yanlış olduğu ortaya çıkarsa buraya
yazın ve kullanıcıya sorun. Tasarım dokümanını tek taraflı değiştirmeyin.

_(henüz soru yok)_
