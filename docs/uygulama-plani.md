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
| F0 | Kullanıcı kararları | 🔵 F0.2-F0.5 bitti · F0.1 gerçek hesap bilgisi bekliyor |
| F1 | Defter ve manuel muhasebe | 🔵 Kod bitti (F1.1-F1.10) · F1.11 açılış kitabı bekliyor |
| F2 | Capital policy ve karar akışı | ✅ Bitti |
| F3 | Tez lifecycle ve izleme sözleşmesi | 🔵 F3.1-F3.4 bitti · F3.5 gerçek pozisyon bekliyor |
| F4 | Mekanik kontrol motoru | ✅ Bitti |
| F5 | Job, dedup, inbox | ✅ Bitti |
| F6 | İlk otomatik recipe | ✅ Bitti |
| F7 | `research-cycle` — kendi kendine çalışma | ✅ Bitti — **kritik eşik geçildi** |
| F8 | İkinci dalga tetikleyiciler | ✅ Bitti |
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
  **Açık.** Uydurulmadı; F1.11'de açılış kitabı girilirken gerçek değerlerle
  yazılacak. Hiçbir şeyi bloklamıyor.
- [x] **F0.2 Raporlama para birimi** — kanonik NAV USD mi TL mi? Diğeri yalnız
  bağlam serisi mi?
  *Bitti:* `base_currency` dolu, gerekçesi bir cümleyle yazılı.
  → **USD.** Gerekçe: `config/fund/capital-policy.notes.md`.
- [x] **F0.3 Sermaye amacı** — hangi ufukta yönetilecek, öngörülebilir çekim
  ihtiyacı var mı?
  *Bitti:* `capital_horizon` ve `liquidity_need_mode` dolu.
  → `over_3y` / `none`.
- [x] **F0.4 Risk zarfı** — kabul edilebilir portföy drawdown'ı, pozisyon
  başına kayıp bütçesi (çıpa: 100 bp NAV), mutlak tek-isim tavanı.
  *Bitti:* `position_loss_budget_bps_nav`, `max_security_weight_bps`,
  `max_issuer_weight_bps` dolu.
  → 100 bp / 1000 bp / 1000 bp. Issuer tavanı ayrıca sorulmadı, security
  tavanına eşitlendi ve `provisional` işaretlendi.
- [x] **F0.5 Capital policy v0 dosyasını doldur** ← F0.1-F0.4
  *Bitti:* `config/fund/capital-policy.json` tasarım Bölüm 3'teki bütün
  alanları taşıyor; hiçbir alan `null` değil (her biri değer veya `disabled` /
  `unbounded_by_policy` / `not_applicable` / `monitor_only`); varsayılan
  kullanılan her sayı `provisional` işaretli.
  → 12 alan provisional. `fund policy show` ile görülür.

---

## F1 — Defter ve manuel muhasebe

Hedef: açılış kitabı ve elle işlem girişi, pozisyon/nakit/NAV replay.

### Şemalar

- [x] **F1.1 `schemas/fund/common.schema.json`** — UUIDv7, decimalString,
  Money, Currency, UtcInstant, LocalDate, MarketSessionDate, digest, artifact
  ref.
  *Bitti:* Mevcut `valuation-common.schema.json` gelenekleriyle uyumlu
  (pattern tabanlı, `format`'a güvenmiyor); pozitif ve negatif fixture'ları
  geçiyor.
- [x] **F1.2 `schemas/fund/instrument-master.schema.json`** (stub) —
  `issuer_id` / `security_id` / `listing_id`, güncel ticker, venue, currency.
  *Bitti:* Üç kimlik ayrı; dar ve kapalı; ticker geçmişi ve kurumsal işlem
  ilişkileri **yok**.
- [x] **F1.3 `schemas/fund/account-event.schema.json`** ← F1.1
  *Bitti:* Tasarım Bölüm 8'deki alanlar; `event_type` kapalı enum
  (`opening_position`, `opening_cash`, `buy`, `sell`, `deposit`, `withdrawal`,
  `dividend`, `fee`, `quantity_adjustment`, `correction`);
  `cost_basis_status` `known`/`unknown`; sentetik opening fill üretmiyor.
- [x] **F1.4 `schemas/fund/capital-policy.schema.json`** ← F1.1
  *Bitti:* Tasarım Bölüm 3 alan tablosunun tamamı; `null` reddediliyor;
  `readiness_multipliers` serbest map değil kapalı anahtarlı sabit nesne.

### Depolama

- [x] **F1.5 SQLite DDL ve migration** ← F1.3
  *Bitti:* Tablolar oluşuyor; exact decimal alanlar `TEXT`; `account_event`
  üzerinde UPDATE/DELETE reddeden trigger var; `schema_migrations` tablosu
  sürüm tutuyor.
- [x] **F1.6 Tek commit kapısı** ← F1.5
  *Bitti:* Bütün yazımlar tek `commit()` fonksiyonundan geçiyor;
  `BEGIN IMMEDIATE` kullanılıyor; iki eşzamanlı süreç testinde olay
  kaybolmuyor; aynı komut iki kez çalıştırıldığında ikinci kayıt oluşmuyor.

### CLI ve projection

- [x] **F1.7 `fund trade record`** ← F1.6 — elle alım/satım/nakit girişi.
  *Bitti:* Alım, satım, temettü, ücret ve nakit giriş/çıkış kaydedilebiliyor;
  aynı işlemi ikinci kez girmeye çalışınca uyarı çıkıyor.
- [x] **F1.8 `fund correct`** ← F1.7 — hatalı kaydı düzeltme.
  *Bitti:* Düzeltme yeni bir satır (`corrects_event_id`); eski satır
  değişmiyor; projection düzeltilmiş sonucu veriyor.
- [x] **F1.9 Pozisyon / nakit / NAV projection'ı** ← F1.7
  *Bitti:* Elle hesaplanan bir fixture ile pozisyon adetleri, nakit, NAV ve
  ağırlıklar birebir eşleşiyor; `cost_basis_status: unknown` olan pozisyonda
  unrealized P&L **hesaplanmıyor**, sıfır gösterilmiyor.
- [x] **F1.10 Replay ve idempotency testi** ← F1.9
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

- [x] **F2.1 `schemas/fund/assessment-record.schema.json`**
  *Bitti:* Tez özeti, readiness (`watchlist`/`starter`/`core`), downside
  senaryosu ve yüzdesi, kanıt tarihi, `review_due`, kaynak artefakt
  referansı, `human_authored` bayrağı ve `derived_from`.
- [x] **F2.2 `schemas/fund/decision-record.schema.json`**
  *Bitti:* Tasarım Bölüm 8'deki alanlar; `shadow`/`live` ayrımı var;
  immutable.
- [x] **F2.3 Policy hesaplayıcı** ← F1.4
  *Bitti:* `base_weight`, `readiness_weight`, downside kapasitesi, issuer/
  security/nakit kapasiteleri ve `policy_compliant_max_weight` hesaplanıyor;
  **bağlayıcı kısıt** (`binding_constraint`) doğru raporlanıyor; no-trade
  bandı değerlendiriliyor.
- [x] **F2.4 `fund assess`** ← F2.1
  *Bitti:* Ekranda pozisyon ağırlığı, nakit, P&L, önerilen işlem ve sermaye
  riski **görünmüyor**; "bu pozisyona sahip olmasaydınız aynı downside'ı kabul
  eder miydiniz" sorusu soruluyor; sonuç `assessment_record` olarak
  dondurulıyor.
- [x] **F2.5 `fund trade-preview`** ← F2.3, F2.4
  *Bitti:* Tasarım Bölüm 4'teki çıktı formatı üretiliyor; policy dışı işlemde
  policy içi üst sınır hesaplanıyor; üç seçenek (indir / iptal / gerekçeyle
  policy dışı kaydet) çalışıyor; karar `decision_record` olarak dondurulıyor.
- [x] **F2.6 `fund trade-add`** ← F2.5, F1.7 — kararı gerçekleşmeye bağlama.
  *Bitti:* Kararla `account_event` arasındaki bağ (`decision_id`) kuruluyor.
- [x] **F2.7 `fund review`** — aylık oturum.
  *Bitti:* NAV, nakit, drawdown, pozisyon tablosu ve uyarılar gösteriliyor;
  `no_change` da bir karar olarak gerekçe koduyla kaydediliyor; çözülmemiş
  adjudication varken `no_change_with_pending_review` işaretleniyor.
- [x] **F2.8 Property testleri** ← F2.3
  *Bitti:* En az şunlar geçiyor: downside kötüleşirse ilgili tavan artamaz;
  readiness düşerse band genişleyemez; loss budget daralırsa tavan artamaz;
  ağırlıklar + nakit = %100 (tolerans içinde); policy sıkılaşırsa uygun
  portföy kümesi genişleyemez.
- [x] **F2.9 Golden fixture'lar** ← F2.3
  *Bitti:* 6-8 okunabilir kanonik kitap ve beklenen çıktıları donduruldu
  (tamamen nakit, aşırı yoğun tek pozisyon, dengeli kitap, limitlere yaklaşmış
  kitap, hard-limit ihlalli kitap, split içeren kitap, `cost_basis_unknown`
  içeren kitap).
- [x] **F2.10 Salt-okunur HTML görünümü** ← F1.9, F2.5
  *Bitti:* NAV, nakit, pozisyonlar, policy tavanları, ihlaller, review-due
  listesi ve son kararlar tek sayfada okunabiliyor; sayfa aynı veriden
  yeniden üretilebiliyor; yazma yolu **yok**.

**F2 bitti sayılır:** Tek bir gölge kararı uçtan uca çalışıyor —
`assess → trade-preview → decision → trade/no_change`.

---

## F3 — Tez lifecycle ve izleme sözleşmesi

← F2.4

- [x] **F3.1 `schemas/fund/thesis.schema.json`**
  *Bitti:* `thesis_id`, `security_id`, `opened_at`, `thesis_statement`,
  `status` (`active`/`review_required`/`broken`/`closed`),
  `current_assessment_id`, sürümlü `monitoring_contract`, `closed_at` ve
  `close_reason`. Exposure alanı **yok** (o `account_event` projection'ından
  gelir).
- [x] **F3.2 `monitoring_contract` alt belgesi** ← F3.1
  *Bitti:* `mechanical_rules[]` (rule_id, metric_id, period_basis, test_type,
  operator, threshold) ve `qualitative_checks[]` (check_id, question,
  review_on[], review_due, last_reviewed_at); kapalı sözlükler tasarım Bölüm
  5'teki gibi; tez başına en fazla 5 kural.
- [x] **F3.3 `fund thesis open`** ← F3.1, F2.4
  *Bitti:* Kabul edilmiş bir assessment'tan tez açılıyor; aynı security için
  ikinci açık tez açılamıyor.
- [x] **F3.4 Tez durum geçişleri** ← F3.3
  *Bitti:* `active → review_required → active|broken|closed` geçişleri
  çalışıyor; **hiçbir kod yolu tezi otomatik `broken` veya `closed`
  yapamıyor** (test var).
- [ ] **F3.5 Bir gerçek tez yaz** ← F3.2
  *Bitti:* Mevcut pozisyonlardan biri için tez, 1-2 mekanik kural ve 1-2 nitel
  soru elle yazıldı; kuralların metrik kataloğunda karşılığı doğrulandı.

---

## F4 — Mekanik kontrol motoru

← F3.2

- [x] **F4.1 Metrik binding doğrulaması**
  *Bitti:* Sözleşme aktive edilirken `metric_id`, birim, dönem tipi ve test
  türü `config/pipeline/metric-catalog.json` ile karşılaştırılıyor;
  eşleşmiyorsa sözleşme **aktive edilmiyor**.
- [x] **F4.2 Kontrol motoru (saf fonksiyon)** ← F4.1
  *Bitti:* Dondurulmuş veri fixture'ında `not_breached` / `breached` /
  `unavailable` üretiyor; katalog veya veri yapısı değiştiyse çalışma anında
  yeniden doğrulayıp `unavailable` veriyor, "değişiklik yok" **vermiyor**.
- [x] **F4.3 `monitoring_check_record`** ← F4.2
  *Bitti:* Hangi kural, hangi accession/veri sürümü, hangi sonuç kaydediliyor;
  `unavailable` hiçbir yerde "sapma yok" sayılmıyor.
- [x] **F4.4 Breach → `review_required`** ← F4.3, F3.4
  *Bitti:* Mekanik breach tezi `review_required` yapıyor ve başka hiçbir şey
  yapmıyor.

---

## F5 — Job, dedup, inbox

← F4.4

- [x] **F5.1 `schemas/fund/research-job-record.schema.json`**
  *Bitti:* Tetikleyici snapshot'ı, `rule_id` + `rule_version`, recipe,
  `attempts[]`, sonuç referansı, hata durumu.
- [x] **F5.2 Dedup ve cooldown** ← F5.1
  *Bitti:* Aynı `thesis_id + monitoring_contract_version + evidence_accession`
  ikinci kez iş açmıyor; aynı teze ait birden fazla tetikleyici tek işte
  birleşiyor.
- [x] **F5.3 Retry politikası** ← F5.1
  *Bitti:* Tasarım Bölüm 6'daki hata tablosu uygulanıyor (veri hatası,
  skill/transport hatası, kontrat hatası, geç sonuç); üç başarısız cycle'dan
  sonra otomatik deneme duruyor.
- [x] **F5.4 Q0/Q1/Q2 kuyruk projection'ı** ← F5.1
  *Bitti:* Üç sınıf doğru dolduruluyor; Q1 sıralaması tasarımdaki gibi;
  kuyruk ayrı bir defter değil, job ve açık assessment'lardan türetiliyor.
- [x] **F5.5 `fund inbox`** ← F5.4
  *Bitti:* Sessiz haftada "işlem gerekmiyor" özeti; iş varsa neden/son
  tarih/tahmini süre gösteriliyor.
- [x] **F5.6 `fund adjudicate <job_id>`** ← F5.5
  *Bitti:* Tasarım Bölüm 7'deki ekran; sermaye etkisi **görünmüyor**; toplu
  onay yok; `Accept` varsayılan değil; üç kapalı soru soruluyor; maddi
  değişiklikte gerekçe zorunlu; `Reject` ve `Human-authored replacement`
  yolları çalışıyor; incelemeden geçiş `acknowledged_without_full_adjudication`
  olarak kaydediliyor.

---

## F6 — İlk otomatik recipe

← F5.6

- [x] **F6.1 SEC accession gözlemcisi** — security başına son görülen
  accession watermark'ı.
  *Bitti:* Yeni 10-Q/10-K deterministik olarak tespit ediliyor; aynı filing
  ikinci kez tetikleyici üretmiyor.
- [x] **F6.2 Dispatch tablosu (tek kural)** ← F6.1
  *Bitti:* "Yeni ilgili filing + açık tez → `deep-dive → tracker`,
  `update_against_prior`" kuralı kodda tipli ve kapalı; `rule_version` var.
- [x] **F6.3 Nitel soruların pack'e enjeksiyonu** ← F3.2
  *Bitti:* Tezin vadesi gelmiş nitel soruları deep-dive pack'ine açıkça
  giriyor; skill'in kendiliğinden bakacağı varsayılmıyor.
- [x] **F6.4 Skill çıktısı sözleşmeleri** ← F6.2
  *Bitti:* `deep-dive` ve `tracker` çıktıları için makine-okunur sidecar
  şemaları var; şema veya kontrat geçmezse sonuç adjudication'a
  **sunulmuyor**.
- [x] **F6.5 Görünürlük kontrolü** ← F6.2
  *Bitti:* Pack'te pozisyon ağırlığı, nakit, P&L, ortalama maliyet ve sermaye
  riski **bulunmadığı** testle doğrulandı.
- [x] **F6.6 Elle tetiklemeli uçtan uca test** ← F6.4
  *Bitti:* Elle verilen bir filing kanıtı → mekanik kontrol → deep-dive →
  tracker → Q1 inbox → adjudication → yeni assessment → tez durumu zinciri
  çalışıyor.

---

## F7 — `research-cycle` (kritik eşik)

← F6.6

- [x] **F7.1 `fund research-cycle` komutu**
  *Bitti:* Veriyi tazeliyor, gözlemleri çıkarıyor, kuralları eşleştiriyor,
  dedup uyguluyor, işleri **seri** çalıştırıyor, doğruluyor, kuyruğa koyuyor.
- [x] **F7.2 Watermark ve catch-up** ← F7.1
  *Bitti:* Bilgisayar birkaç gün kapalı kalsa bile aradaki filing kaybolmuyor;
  cycle son watermark'tan devam ediyor.
- [x] **F7.3 Task Scheduler kurulumu** ← F7.1
  *Bitti:* Gecelik çalışıyor; `StartWhenAvailable` açık; kurulum adımları
  yazılı.
- [x] **F7.4 Heartbeat ve sabah durum özeti** ← F7.1
  *Bitti:* Son cycle zamanı ve sonucu görünüyor; başarısız cycle sessiz
  kalmıyor; Q0 uyarısı doğuyor.

**F7 bitti sayılır — sistem kendi kendine çalışıyor:** kullanıcı filing'i
hatırlamıyor, skill seçmiyor; sabah yalnız sonucu yargılıyor.

---

## F8 — İkinci dalga tetikleyiciler

← F7.4. Sırayla ekleyin, her birini ayrı doğrulayın.

- [x] **F8.1 Review vadesi tetikleyicisi** → `tracker`
  *Bitti:* Yeni kanıt olmasa bile `review_due` dolunca tracker çalışıyor.
- [x] **F8.2 Fiyat şoku tetikleyicisi** → kör ilk geçişli review
  *Bitti:* Adjusted-close baseline ve eşik tanımlı; `independent_then_reconcile`
  modu çalışıyor (ilk geçişte önceki hüküm ve pozisyon **gösterilmiyor**).
- [x] **F8.3 `FilingRef`'e SEC `items` alanı** — Item 2.02 tespiti için.
  *Bitti:* Ham submissions'taki `items` typed katmana taşındı;
  `earnings_release` gözlemi çalışıyor.
- [x] **F8.4 `date_due` düzeltmesi** — tarih tetikleyicisi kanıt beklesin.
  *Bitti:* Tarih tek başına `trigger_satisfied` **üretmiyor**; yalnız kanıt
  kontrolü vadesi doğuruyor; `release_observed` ile `evidence_available`
  ayrımı var. *(Mevcut `evaluate_trigger` bunu yapmıyor — tasarım Bölüm 6.)*
- [x] **F8.5 `check_triggers` yerine tez-odaklı gözlemciler**
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

### 2026-08-16 — F1.3 `account_event` alan sözleşmesi

Tasarım Bölüm 8 alanları **birleşim** olarak listeliyor; şema bunları event
tipine göre koşullu hale getirdi. Üç yerde bilinçli somutlaştırma yapıldı:

1. **`currency` üst düzeyde yok.** Her parasal alan kendi `{amount, currency}`
   nesnesini taşıyor — tasarımın kendi tip kuralı bu. Üst düzeyde ikinci bir
   currency alanı iki kaynak yaratırdı.
2. **`cash_amount` işaretsiz büyüklüktür**, yönü `event_type` belirler.
   Gerekçe: CLI'ya "5000 çektim" yazan biri eksi işareti düşünmüyor ve
   append-only bir defterde işaret hatası pahalı.
3. **`buy`/`sell` `cash_amount` taşımıyor.** `quantity × price` zaten nakit
   etkisi; ikisini birlikte saklamak tutarsızlık davetiyesi. Komisyon ayrı
   `fee` alanında.

`correction` tipi **saf iptal** olarak modellendi (hiç olmaması gereken kayıt).
Bir değeri düzeltmek ise `corrects_event_id` taşıyan **yeni tipli bir olay**.
İkisi de "yeni satır, eski satır değişmez" kuralına uyuyor.

### 2026-08-16 — F1.1 boolean `false` alt-şeması kullanılmadı

Yasaklı alanlar `{"not": {}}` (`common.schema.json#/$defs/forbidden`) ile
yazıldı. `"cash_amount": false` yazınca jsonschema hata yolunu **ve** alan
adını düşürüyor; kullanıcı "False schema does not allow {...}" görüyor, hangi
alanın yanlış olduğunu göremiyor. `{"not": {}}` yolu koruyor.

### 2026-08-16 — F1.5 kimlik biçimi

Kimlikler `EVT-<uuid7>` gibi önekli. Tasarım "UUIDv7" diyor, CLI örnekleri
`ASM-...` / `DEC-...` gösteriyor; ikisi birleştirildi. Dört karakter maliyeti
var, karşılığında bir decision id'nin assessment beklenen yere sessizce
geçmesi imkânsız hale geliyor.

Menkul kıymet kimlikleri okunabilir slug: `iss:alphabet` / `sec:googl` /
`lst:xnas-googl`. V0'da elle bakıldıkları için opak UUID yerine bu seçildi.

### 2026-08-16 — F1.9 `realized_pnl_complete` kapsamı

Maliyeti bilinmeyen bir pozisyonu **tutmak** kitabın realized P&L toplamını
bozmuyor; yalnız o hisseler **satılınca** toplam hesaplanamaz oluyor. İlk
uygulamada açılışta bayrak düşürülüyordu, daraltıldı.

### 2026-08-16 — F1.6 mükerrer kontrolü iki katmanlı

- **Sert:** `opening_position` security başına bir kez, `opening_cash` para
  birimi başına bir kez (partial unique index). Açılış kitabının iki kez
  içeri alınmasını imkânsız kılıyor. Düzeltmeler muaf (`corrects_event_id`
  taşıyorlar).
- **Yumuşak:** `content_digest` üzerinden. Aynı ekonomik içerik ikinci kez
  girilirse reddediliyor; gerçekten tekrar eden bir işlemse
  `--allow-duplicate` gerekiyor. Digest `event_id`, `recorded_at` ve `note`
  alanlarını dışlıyor.

### 2026-08-16 — F2.3 readiness tavanı tasarımdaki örnekten farklı

Tasarım Bölüm 4'teki önizleme örneği "Readiness tavanı %5,00" diyor; kod
**%4,90** üretiyor. Kod doğru: tasarımın kendi formülü
`base_weight = deployable_capital_fraction / max_active_positions` ve
deployable = 1 − 200 bp operasyonel taban = 0,98. 0,98/10 × 0,5 = %4,9.
Örnekteki %5 yuvarlanmış. Bağlayıcı kısıt, tavan (%3,33) ve policy içi miktar
(18 hisse / $3.240) örnekle **birebir** aynı.

### 2026-08-16 — F2.5 preview'da iki farklı "fiyat"

`--price` işlem fiyatı, `--mark` kitabın geri kalanını değerlemek için piyasa
fiyatı. Tek bayrakta birleştirmek, portföyü "ödemeyi umduğun fiyattan"
değerlemenin sessiz bir yolu olurdu.

### 2026-08-16 — F2.5 karar dondurmak açık tercih ister

`fund trade-preview` tek başına **hiçbir şey kaydetmez**. Karar ancak
`--decide accept|reduce|cancel|outside-policy` ile donuyor. Önizleme
önizlemedir; bakmakla karar vermek arasındaki farkı defterin görmesi gerekiyor.

### 2026-08-16 — F2.7 drawdown için NAV geçmişi eklendi

Drawdown bir geçmiş ister, projection ise geçmiş uyduramaz: fiyat serisi
olmadan geçen ayki NAV bilinemez. `nav_snapshot` tablosu (migration 3) eklendi;
`fund review` her çalıştığında o günün markını yazıyor ve zirve dürüstçe
"izleme başladığından beri" olarak tanımlanıyor. İlk review "bir zirve için
ikinci review gerekiyor" diyor.

### 2026-08-16 — F4.1 bağlama kuralları kataloğun ötesine geçti

Tasarım "metric_id, birim, dönem tipi katalogla eşleşmiyorsa aktive edilmez"
diyor. Kod üç ek tutarlılık kuralı uyguluyor, çünkü bunlar sessizce yanlış
sonuç üretiyordu:

1. `absolute_value` yalnız **seviye** dönemleriyle (`ttm`, `latest_fy`).
   Bir eşiği yıllık değişimle karşılaştırmak seviyeyi delta ile ölçmek demek —
   hiçbir şey ölçmez ve doğru görünür.
2. `percentage_change` / `basis_point_change` yalnız **değişim** dönemleriyle.
3. `basis_point_change` yalnız oran birimli metriklerde; `percentage_change`
   ise oran birimli metriklerde **reddediliyor** (yüzdenin yüzde değişimi
   belirsiz — orada bp kullanılmalı).

Katalogda `revenue` ve `net_debt_to_ebitda` **yok** (203 metrik var ama bu
ikisi farklı adlarla). Kural yazarken `fund thesis contract` zaten reddediyor.

### 2026-08-16 — F4.2 çalışma anı yeniden doğrulaması

Bağlama iki kez kontrol ediliyor: aktivasyonda (bağlamazsa sözleşme **aktive
edilmiyor**) ve her değerlendirmede. İkincisi asıl olan — katalog yaşayan bir
dosya ve altı ay önce bağlanan bir kural bugün bağlamayabilir. O durumda sonuç
`unavailable`, asla `not_breached`. Yeniden adlandırılmış bir metrik "tez
sağlıklı" demez, "artık sandığımız şeyi ölçmüyoruz" der.

Her kayda `binding_signature` yazılıyor (metrik, birimler, veri tipi, dönem);
sonraki bir katalog değişikliği karşılaştırmayla görünür oluyor.

### 2026-08-16 — F5.1 job'lar sürümlü satırlar olarak saklanıyor

Job durumu değişiyor (pending → running → awaiting_adjudication → adjudicated),
ama `commit()` yalnız insert yapıyor. Çözüm: her yazım yeni bir **revizyon**
satırı, güncel job en yüksek revizyon. Tek yazma kapısı korunuyor, deneme
geçmişi sessizce değiştirilemiyor ve "üçüncü hatadan önce bu job neye
benziyordu" sorusu cevaplanabilir kalıyor.

`dedup_key` üzerinde `revision = 1` koşullu unique index: bir dedup anahtarı
ömür boyu bir job açar.

### 2026-08-16 — F5.3 hata sınıfına göre farklı retry bütçesi

Tasarımın hata tablosu sınıfları ayırıyor ama sayı vermiyor. Kod:
`data_source_error` ve `skill_transport_error` 3, `contract_error` 2,
`late_result` 1 deneme. Gerekçe: veri kaynağı genelde bozuk değil geç;
transport hatası geçici; kontrat hatası kendi kendine düzelmez.
`contract_failed` yine de bir onarım denemesine açık (tasarım "bir onarım
denemesi" diyor) — formatlama hatası geçici olabiliyor.

### 2026-08-16 — F5.6 adjudication komutu varsayılansız

`fund adjudicate JOB-...` tek başına **ekranı gösterir, hiçbir şey kaydetmez**.
Beş seçenekten biri açıkça verilmeli. Toplu onay yok: komut tek bir job_id
alıyor, `--all` gibi bir bayrak hiç eklenmedi.

`--reject` hiçbir assessment yazmıyor — öneri sessizce düzeltilmiyor. Farklı
hüküm `--replace` ile ayrı bir `human_authored` kayıt doğuruyor ve
`derived_from` ile öneriye bağlanıyor.

### 2026-08-16 — F6.4 tek sidecar şeması, skill başına değil

Plan `deep-dive` ve `tracker` için ayrı sidecar şemaları istiyordu. Tek
`skill-output.schema.json` yazıldı, skill'e göre koşullu kurallarla:
`thesis-tracker` bir `proposed_assessment` **üretmek zorunda**,
`idea-generation` ise üretmesi **yasak** (tarama aday üretir, sermaye hükmü
değil). İki dosya aynı `findings`/`answers` gövdesini kopyalayacaktı.

Düzyazı serbest kalıyor — şablona sokulmuş bir analiz daha kötü bir analiz.
Sözleşme yalnız sistemin üzerine iş yaptığı yarıya uygulanıyor.

### 2026-08-16 — F6.5 görünürlük kontrolü yapısal

`packs.walk_for_capital_leaks` pack'in **tamamını** gezip yasaklı anahtar
arıyor ve bulursa pack üretilmiyor. Sadece test değil, çalışma anı koruması:
ileride bir snapshot'a eklenen alan kazara pack'e gömülürse orada patlıyor.

Ciddiyet `decision_deadline` ile anlatılıyor — bir tarih, bir tutar değil.
"82 bp risk altında" demek analizi iyileştirmiyor, modele pozisyonu savunma
gerekçesi veriyor.

### 2026-08-16 — F6.1 gözlem sınırı

`fund observe --limit` varsayılan 1. Yirmi yıllık geçmişi olan bir şirkette ilk
koşu seksen iş değil bir iş üretmeli. Sınırın **üstündeki** filing'ler de
`observed_filing`'e yazılıyor, yani bir daha yüzeye çıkmıyorlar.

### 2026-08-16 — skill çalıştırıcı enjekte ediliyor

`recipes.run` bir `executor` alıyor: üretimde codex, testte hazırlanmış
sidecar'lar. Bu dikiş test kolaylığı için değil — **kontrat kontrolü orada
yaşıyor** ve bozuk bir model çıktısıyla kullanıcının hükmü arasındaki tek şey o.

### 2026-08-16 — F7.1 birleştirme kanıt bazında

İlk uygulamada `plan_work` gözlemleri (security, thesis, **gözlem tipi**) ile
gruplayıp birleştiriyordu. Bu, bir haftalık aradan sonra gelen **üç ayrı
filing'i tek işe** katıyordu — tam da catch-up'ın koruması gereken şeyi
bozuyordu. Doğrusu: gruplama **kanıt** bazında (accession / review tarihi /
fiyat penceresi). Bir filing hakkındaki iki sinyal tek okuma; iki farklı filing
iki okuma.

Bir kanıt üzerinde birden çok gözlem varsa iş, en ciddi olanın kuralıyla
açılıyor (`OBSERVATION_PRIORITY`): mekanik breach, onu ortaya çıkaran
filing'den önce gelir.

### 2026-08-16 — F7.4 sessizlik operatör tarihiyle ölçülüyor

Heartbeat "kaç gündür sessiz" hesabını `started_at` (duvar saati) yerine
cycle'ın `as_of`'u ile yapıyor. Tasarım "'bugün' kanonik bir veri alanı
değildir" diyor; geriye dönük çalıştırılan bir cycle iki aylık sessizlik gibi
okunmamalı.

### 2026-08-16 — artifact yolları POSIX

`relative_path` şeması ters bölü kabul etmiyor. Windows'ta üretilen yol
`as_posix()` ile yazılıyor — defter Windows'ta yazılıp başka yerde okunabilir
kalmalı. Repo dışındaki workdir'ler `external/<job_id>/<dosya>` biçiminde.

### 2026-08-16 — F8.2 fiyat şoku için mark serisi

Fiyat şoku bir taban ister, taban bir seri ister. İkinci bir fiyat hattı
kurmak yerine kullanıcının zaten verdiği markları (`fund review --price`,
`fund research-cycle --mark`) `price_mark` tablosunda tutuyoruz. Taban, en az
`window_days` eskiye ait en yakın mark — böylece yavaş sürüklenme sessiz kalıyor,
basamak yakalanıyor.

**Sınır:** seri kullanıcının verdiği kadar sık. Ayda bir review yapılıyorsa şok
tespiti ayda bir. Gerçek EOD hattına bağlamak ayrı bir iş.

### 2026-08-16 — F8.3 `report_date` geri düşüşü yalnız olay formlarında

8-K'lerin çoğunda `reportDate` boş; eski kod bunları düşürüyordu, dolayısıyla
Item 2.02 hiç görünmüyordu. Filing tarihine geri düşüş eklendi **ama yalnız
10-K/10-Q dışındaki formlar için**. Periyodik bir formda yanlış dönem, üzerine
kurulan her karşılaştırmayı kaydırırdı — eski davranış aynen korundu.

### 2026-08-16 — F8.4 tarihten işe giden kod yolu yok

`earnings_evidence` gözlemi yalnız `items` içinde `2.02` olan bir filing'den
doğuyor. Beklenen earnings tarihinden işe giden bir yol **hiç yazılmadı** —
test bunu doğruluyor. Tarih bir tahmindir; tahmine ateşlenen araştırma henüz
var olmayan sayılar üzerine yapılır.

### 2026-08-16 — F8 kullanıcı ayarları

`config/fund/dispatch-tuning.json` (yoksa varsayılan). Değiştirilebilir dört
şey: `enabled`, `cooldown_days`, `price_shock_bps`, `price_shock_window_days`.
Başka bir alan yazılırsa **hata veriyor** — recipe veya assessment modu config'e
açılırsa farkında olmadan bir kural dili kurulmuş olurdu.

### 2026-08-16 — plan dışı eklenenler

`fund` CLI'nın kullanılabilir olması için plana yazılmayan iki şey eklendi:

- `config/fund/instrument-master.json` + `fund instrument add/list` — ticker
  yazıp `security_id` çözebilmek için. F1.2 şemayı istiyordu, dosya ve giriş
  yolu olmadan elle işlem girilemiyordu.
- `fund init`, `fund events`, `fund positions`, `fund policy show` — sırasıyla
  kurulum, defter dökümü, F1.9 projection'ının görüntüsü ve policy denetimi.

---

## Tasarım soruları

Uygulama sırasında tasarımın eksik veya yanlış olduğu ortaya çıkarsa buraya
yazın ve kullanıcıya sorun. Tasarım dokümanını tek taraflı değiştirmeyin.

### 2026-08-16 — F3.4 `active → closed` geçişi yok

Tasarım Bölüm 5 geçişleri `active → review_required → active|broken|closed`
diye tanımlıyor. Kod bunu **birebir** uyguluyor: bir tezi kapatmak için önce
`review_required` işaretlemek gerekiyor.

**Soru:** Pozisyondan tamamen çıkıldığında (hedef fiyata ulaşıldı, hisse
satıldı) tezi kapatmak için önce "inceleme gerekli" demek doğru mu? Bir yandan
tez kapatmak da bir lifecycle hükmü ve aynı kapıdan geçmesi tutarlı; öte yandan
"sattım, bitti" durumunda iki komut gereksiz sürtünme.

`active → closed` eklemek istersen söyle, `thesis.ALLOWED_TRANSITIONS`'a bir
satır. Tek taraflı eklemedim.
