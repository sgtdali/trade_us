# Portföy karar günlüğü — tasarım

> Dosya adı (`pei-company-lifecycle-tasarim.md`) tarihseldir; içerik
> yenilenmiştir. Bu doküman yalnız **güncel tasarımı** anlatır. Kararların
> nasıl varıldığı, hangi alternatiflerin reddedildiği ve neyin sonradan
> değiştiği repodaki oturum arşivindedir:
> [docs/tasarim-oturumlari/2026-08-codex-fon-sistemi/](tasarim-oturumlari/2026-08-codex-fon-sistemi/README.md)

Durum: tasarım tamamlandı, uygulama başlamadı. Son güncelleme 2026-08-16.

> **Uygulamaya başlayacaksanız** bu doküman "nasıl olacağı"nı anlatır; sırayı
> ve ilerlemeyi [uygulama-plani.md](uygulama-plani.md) takip eder. Görev
> listesi, bağımlılıklar ve "bitti" tanımları oradadır.

---

## 1. Sistem nedir

Tek sahibin ABD hisselerinden oluşan portföyünü disiplinli yönetmek için
kurulan **küçük bir portföy karar günlüğü**. Üç iş yapar:

1. **Muhasebe:** elle girilen alım, satım ve nakit hareketlerinden pozisyon,
   nakit, NAV ve ağırlıkları hesaplar.
2. **Karar disiplini:** düşünülen işlemi capital policy'ye karşı sınar,
   bağlayıcı kısıtı gösterir ve karar anında bilinenleri değiştirilemez
   biçimde dondurur.
3. **Araştırma operasyonu:** yeni filing, fiyat hareketi ve inceleme
   vadelerini kendisi gözler, gerekli araştırma skill'ini kendisi çalıştırır
   ve yorumlanmış sonucu insanın önüne getirir.

**Yapmadıkları.** Emir iletmez. Sermaye kararını vermez. Araştırma hükmünü
kendisi kabul etmez. Tezi kendiliğinden kapatmaz. Portföy optimize etmez,
alternatif portföyler üretmez. Broker muhasebesini taklit etmez.

**Ölçek varsayımları.** Bunlar tasarımın her yerini belirler; değişirlerse
tasarım yeniden değerlendirilmelidir.

| | |
|---|---|
| Kullanıcı | Tek kişi, hem operatör hem karar verici |
| Pozisyon sayısı | 5-10 |
| İşlem sıklığı | Ayda ~1 pozisyon değişikliği, yılda ~12 işlem |
| İşlem girişi | Elle |
| Broker | Tek hesap; ekonomik gerçeğin sahibi, sistem onu kopyalamaz |
| Enstrüman | Yalnız ABD listeli adi hisse; opsiyon, kaldıraç, açığa satış yok |
| Başlangıç modu | Gölge (kararlar kaydedilir, sermaye bağlanmaz) |
| Haftalık işletim | Mevcut kitap 15-25 dk; yeni aday araştırması dahil 25-40 dk |

---

## 2. Değişmezler

Uygulamada ihlal edilmemesi gerekenler.

1. **Broker ekonomik gerçeğin, sistem policy meşruiyetinin otoritesidir.**
   Sistem "kaç hisse var" sorusunu kendi kaydından cevaplar ama broker
   ekranıyla çeliştiğinde broker haklıdır.
2. **Girilmiş satır değiştirilmez.** Hata düzeltmesi `corrects_event_id`
   taşıyan yeni bir kayıttır.
3. **Maliyet bilinmiyorsa sıfır yazılmaz.** `cost_basis_status` `known` veya
   `unknown` olur; unrealized P&L hesaplanamıyorsa hesaplanmaz.
4. **Kayıp bütçesi stop-loss değildir.** Pozisyon açılmadan önce uygulanan
   boyutlandırma sınırıdır.
5. **Fiyat düşüşü otomatik satış üretmez.** İnceleme tetikler.
6. **Makine tezi `broken` veya `closed` yapamaz.** Yalnız `review_required`
   üretir; lifecycle hükmü insana aittir.
7. **`unavailable` asla "sapma yok" sayılmaz.** Veri gelmediyse kontrol
   yapılmamıştır.
8. **`not_breached` "tez sağlıklı" demek değildir.** Yalnız ilgili kuralın
   ihlal edilmediğini söyler.
9. **Araştırma hükmü sermaye etkisi görülmeden yargılanır.** İki ayrı komut,
   iki ayrı ekran.
10. **Skill önerir, insan sermaye girdisini kabul eder.** Skill çıktısı
    doğrudan capital input olamaz.
11. **Otomasyon başarısız olduğunda sistem sessiz kalmaz**, eski veriyi
    yeniymiş gibi kullanmaz ve tez durumunu ilerletmez. Aynı işi sonsuza
    kadar da tekrarlamaz.
12. **Policy gevşetmesi gecikmelidir.** Sıkılaştırma hemen uygulanır;
    gevşetme yeni sürüm, gerekçe ve bekleme süresi ister. Mevcut bir ihlali
    "yok etmek" için limit gevşetilemez.
13. **Emir iletimi yoktur.** Onaylanmış karar, işlem niyeti ve gerçekleşme
    ayrı gerçeklerdir; broker'a giriş insana aittir.

---

## 3. Capital policy

Sermaye kararlarının çalıştırılabilir kural kümesi. Güncel NAV, nakit,
pozisyon ve fiyatlar policy'ye **yazılmaz** — onlar girdidir.

`null` bir politika değildir. Her alan ya gerçek bir değer ya açık bir hüküm
taşır: `disabled`, `unbounded_by_policy`, `not_applicable`, `monitor_only`.

### Alanlar

| Bölüm | Alan | Başlangıç değeri |
|---|---|---|
| Kimlik | `policy_version`, `effective_from`, `owner` | — |
| Amaç | `objective: absolute_return` | — |
| | `underwriting_horizon_months` | 3-18 |
| | `portfolio_review_cadence` | `monthly` |
| | `change_required_at_review` | `false` |
| Uygunluk | `direction` / `security_types` / `listing_countries` | `long_only` / `us_listed_common_equity` / `US` |
| | `shorting` / `leverage` / `derivatives` | `disabled` |
| Nakit | `full_investment_required` | `false` |
| | `role` | `legitimate_residual` |
| | `operational_floor_bps_nav` | 200 |
| | `target` / `ceiling` | `disabled` / `unbounded_by_policy` |
| Kapasite | `max_active_positions` | 10 |
| | `minimum_active_positions` | `disabled` |
| Yoğunlaşma | `max_security_weight_bps` | **kullanıcı kararı** |
| | `max_issuer_weight_bps` | **kullanıcı kararı** |
| | `sector_weight_limit` | `monitor_only` |
| Boyutlandırma | `readiness_multipliers` | `watchlist 0` / `starter 0.5` / `core 1.0` / `exceptional disabled` |
| | `min_economic_position` | `disabled` |
| | `unknown_downside_treatment` | `ineligible_for_new_risk` |
| Risk | `position_loss_budget_bps_nav` | **kullanıcı kararı** (çıpa: 100) |
| | `drawdown_response_ladder` | −%10 uyarı / −%15 ekleme dondur / −%20 tam yeniden inceleme |
| | `automatic_liquidation` | `disabled` |
| İşlem | `no_trade_band` | `max(100 bp mutlak, hedef ağırlığın %20'si)` |
| | `band_bypass_reasons` | `thesis_broken`, `hard_limit_breach`, `position_legitimacy_failure` |
| | `price_tolerance_increase_risk_bps` | 250 |
| | `manual_execution_required` | `true` |
| Ölçüm | `base_currency` | **kullanıcı kararı** |
| | `nav_cut` / `price_basis` | ABD kapanışı / promoted EOD close |
| | `benchmark_mode` / `hurdle_mode` | `disabled` |
| | `missing_input_behavior` | `fail_closed` |
| Yönetişim | `loosening_cooling_off_days` | 7 |
| | `scheduled_review_cadence` | `quarterly` |
| | `retroactive_changes` | `disabled` |

Başlangıç değerlerinin çoğu **provisional**'dır: optimal oldukları için
değil, gerçek veriyle kalibre edilebilir çıpalar oldukları için seçildiler.
Her provisional alan policy içinde işaretlenir.

### Boyutlandırma

```
base_weight       = deployable_capital_fraction / max_active_positions
readiness_weight  = base_weight × readiness_multiplier

policy_compliant_max_weight = min(
    readiness_weight,
    downside_capacity,          # loss_budget_bps / |downside_return|
    max_security_weight,
    issuer_capacity,
    cash_capacity )
```

Kısıtlardan hangisinin bağladığı (`binding_constraint`) her önizlemede
gösterilir — "neden bu kadar" sorusunun cevabı odur.

**Readiness conviction değildir.** Skill'in "yüksek güven" demesi daha büyük
pozisyon üretmez. Sınıf yalnız typed kanıttan türer: kabul edilmiş aktif tez,
tanımlı downside, onaylı izleme sözleşmesi, maddi veri boşluğu yok. Ve
readiness çarpanı hiçbir hard limiti genişletemez.

**Nakit** muhasebede birinci sınıf varlık, tahsiste meşru residual. Beş uygun
isim varsa ağırlıkları %100'e normalize edilmez; boş kapasite nakitte kalır.

**No-trade bandı** aylık ritim ile 3-18 aylık ufuk arasındaki gerilimi çözer:

```
band_half_width = max(absolute_bps, relative_bps × target_weight)
trade_candidate = |current_weight − target_weight| > band_half_width
```

*Aylık ritim yeniden karar verme ritmidir, yeniden işlem yapma ritmi
değildir.*

---

## 4. Karar akışı

İki ayrı komut, iki ayrı ekran. Ayrımın amacı: kullanıcı kabul edeceği
downside'ın kendisini satışa zorlayacağını görüp analitik hükmü yumuşatmasın.

### Aşama 1 — araştırma hükmü

```bash
fund assess NVDA
```

Ekranda: tez özeti, readiness (`starter`/`core`), downside senaryosu ve
yüzdesi, kanıt tarihi, yeniden inceleme tarihi. Otomatik çalışmış bir skill
varsa önerileri doldurulmuş gelir, kaynaklarıyla birlikte.

Ekranda **olmayanlar**: pozisyon ağırlığı, nakit, P&L, ortalama maliyet,
önerilen işlem, sermaye riski.

Kapanış sorusu: *"Bu pozisyona sahip olmasaydınız aynı downside'ı kabul eder
miydiniz?"*

Sonuç `assessment_record` olarak dondurulur. Sessizce sayı düzeltmek yoktur:
olgusal hata varsa öneri **reddedilir**; kullanıcı farklı yargıdaysa
`human_authored` bir assessment üretilir ve model artefaktına `derived_from`
ile bağlanır.

### Aşama 2 — işlem önizlemesi

```bash
fund trade-preview NVDA buy --quantity 50 --price 180 --assessment ASM-...
```

```
NVDA — ALIM ÖNİZLEMESİ

Düşünülen işlem      50 × $180 = $9.000
NAV                  $100.000
Nakit                $20.000 → $11.000
NVDA ağırlığı        %0,00 → %9,00
Pozisyon sayısı      8 → 9

DONDURULMUŞ ARAŞTIRMA
Readiness            starter
Downside             −%30
Kanıt tarihi         2026-08-16

POLICY KONTROLÜ
Readiness tavanı     %5,00
Kayıp bütçesi tavanı %3,33   (100 bp / %30)
Mutlak tavan         %10,00
Bağlayıcı kısıt      kayıp bütçesi

SONUÇ                POLICY DIŞI
Policy içi üst sınır ~18 hisse / $3.240 / %3,24

[R] 18 hisseye indir   [C] İptal   [O] Gerekçesiyle policy dışı kaydet
```

Karar `decision_record` olarak dondurulur: assessment referansı, policy
sürümü, işlem öncesi portföy, ilk düşünülen miktar, hesaplanan limitler, son
karar, gerekçe, `shadow` veya `live` işareti.

Gerçekleşme sonradan girilir:

```bash
fund trade-add --decision DEC-... --quantity 18 --price 181.20
```

### Aylık oturum

```bash
fund review --as-of 2026-09-30
```

NAV, nakit oranı, drawdown, pozisyon sayısı; her pozisyon için ağırlık,
policy tavanı, readiness, downside, inceleme durumu; uyarılar. Sonunda "bu ay
sermaye değişikliği var mı" sorusu — **hayır da bir karardır** ve gerekçe
koduyla kaydedilir. Çözülmemiş adjudication varken verilen `no_change`,
`no_change_with_pending_review` olarak işaretlenir.

---

## 5. Tez ve izleme

**`thesis` kalıcı nesnedir; `assessment_record` onun tarihli fotoğrafıdır.**
Bir tez ömrü boyunca birden çok assessment alır.

```
THS-NVDA-01
  ├── ASM-001  açılış
  ├── ASM-002  Q2 filing sonrası
  ├── ASM-003  review_due
  └── ASM-004  Q3 filing sonrası
```

Tez durumu: `active` · `review_required` · `broken` · `closed`.
Gerçek exposure tezin alanı değildir; `account_event` projection'ından gelir.
Üç gerçek ayrı durur: tezin governance durumu, gerçek pozisyon, tarihli
değerlendirme geçmişi.

### Monitoring contract

Tezin sürümlü alt belgesi. Tez başına **1-2 mekanik kural + 1-2 nitel soru**;
normal 3 kural, tavan 5.

```
monitoring_contract
  version, effective_from

  mechanical_rules[]
    rule_id, metric_id, period_basis, test_type, operator, threshold

  qualitative_checks[]
    check_id, question, review_on[], review_due, last_reviewed_at
```

Kapalı sözlükler:

- `period_basis`: `latest_quarter_yoy` · `latest_quarter_qoq` · `ttm` ·
  `latest_fy` · `change_from_baseline`
- `test_type`: `absolute_value` · `percentage_change` · `basis_point_change`
- Kontrol sonucu: `not_breached` · `breached` · `unavailable`
- `review_on`: `new_periodic_filing` · `earnings_release` · `material_8k` ·
  `review_due`

Birim, kaynak sözleşmesi ve provenance metrik kataloğundan gelir; sözleşmede
tekrarlanmaz. Serbest formül yoktur.

**Metrik bağlama iki kez doğrulanır:** sözleşme aktive edilirken (`metric_id`,
birim, dönem tipi katalogla eşleşmiyorsa aktive edilmez) ve çalışma anında
(katalog sonradan değiştiyse `unavailable` üretilir, "değişiklik yok"
üretilmez). Katalogda güvenilir karşılığı olmayan koşul mekanik yapılmaya
zorlanmaz — nitel kalır.

Eşik değiştirmek yeni sözleşme sürümü ve gerekçe ister; eski sürüm silinmez
ve eski kontrol sonuçları eski kuralla korunur.

### İzleme döngüsü

Finansal kurallar haftalık değil, **yeni ilgili veri geldiğinde** çalışır.

```
yeni filing / earnings kanıtı / review vadesi
              ↓
      normalize finansallar güncellenir
              ↓
      mekanik kurallar değerlendirilir
              ↓
   ┌──────────┴──────────┐
sapma yok            breach veya vadesi gelmiş nitel soru
   │                     ↓
kısa kontrol         thesis = review_required
kaydı                    ↓
                    sabit recipe: deep-dive → tracker
                         ↓
                    provisional assessment
                         ↓
                    insan adjudication
                         ↓
                    yeni assessment + tez durumu
```

**Nitel sorular pack'e açıkça enjekte edilir.** Deep-dive'ın onlara
kendiliğinden bakacağı varsayılmaz. Yeni kanıt gelmese bile `review_due`
dolunca tracker çalışır.

### İzleme canlılığı

Bir kural sessizce ateşlememeye başlarsa tez izlenmiyor demektir ama sistem
"sorun yok" görünür. Bunu yakalayan mekanizma:

Her aktif tez için `monitoring_coverage`: `healthy` · `degraded` · `blind`

- İlgili filing geldiği hâlde bir kural değerlendirilemediyse → `degraded`
- Aynı kural iki ardışık kanıt döneminde `unavailable` kaldıysa → `blind`
- `blind` tez Q0'a düşer; yeni risk artırımı bloklanır

Aylık review yalnız tez sonucunu değil **izleme kapsamını** da kontrol eder.

---

## 6. Otomatik araştırma operasyonu

Genel bir capability router yoktur. **Kapalı, tipli, kod içinde sabit bir
dispatch tablosu** vardır.

Dispatch kuralının config'e açılmamasının nedeni: kural otomatik LLM çağrısı,
maliyet ve iş üretme yetkisi verir. Keyfî config'e açılırsa farkında olmadan
küçük bir kural dili ve yetki sistemi kurulmuş olur. Kullanıcı yalnız
`enabled`, fiyat eşiği, cooldown ve takvim aralığını değiştirebilir.

### Dispatch tablosu

| Gözlem | Koşul | Recipe | Assessment modu | Dedup anahtarı |
|---|---|---|---|---|
| Yeni 10-Q/10-K | Açık tez var | `deep-dive → tracker` | `update_against_prior` | security + accession |
| Earnings kanıtı geldi | Açık tez veya izlenen aday | `deep-dive → tracker` | tez varsa update, yoksa de novo | security + dönem |
| Review vadesi doldu | Açık tez var | `tracker` | `update_against_prior` | thesis + review date |
| Mekanik breach | Açık tez var | `tracker` | `update_against_prior` | thesis + contract_version + accession |
| Fiyat şoku | Fonlanmış tez var | kör ilk geçişli review | `independent_then_reconcile` | security + fiyat penceresi |
| Assessment yok, preview istendi | Security değerlendirilecek | pitch `onboarding_underwrite` | `de_novo` | security + assessment |
| Periyodik discovery | Discovery açık | `idea-generation` | `de_novo` | discovery date |

Her job kullanılan `rule_id` ve `rule_version`'ı kopyalar.

### Assessment modları

Anchoring'i sınırlayan mekanizma:

- **`de_novo`** — önceki hüküm gösterilmez. Yeni isim, onboarding.
- **`update_against_prior`** — önceki hüküm zorunlu, değişimi ölçmek için.
  Rutin filing ve review güncellemeleri.
- **`independent_then_reconcile`** — ilk analiz önceki hükmü, pozisyonu ve
  P&L'i görmeden yapılır; ikinci geçişte fark açıklanır. Maddi tez kırılması,
  fiyat–tez ayrışması, karar-kritik yeniden underwrite.

### Skill'in gördükleri

| Skill | Kabul edilmiş araştırma state'i | Fonlanmış bilgisi | Ağırlık / P&L |
|---|---|---|---|
| `idea-generation` | Hayır | Hayır | Hayır |
| `company-tearsheet` | Yalnız güncelleme modunda | Hayır | Hayır |
| `comps-valuation` | Yalnız güncelleme modunda | Hayır | Hayır |
| `long-short-pitch` | Baseline, valuation, downside | Hayır | Hayır |
| `earnings-deep-dive` | Önceki beklenti, tez, downside | Hayır | Hayır |
| `thesis-tracker` | Tez, monitoring contract, yeni kanıt, breach sonuçları | Hayır | Hayır |

**Sermaye tutarı hiçbir skill'e gösterilmez.** "82 bp risk altında" demek
analizi iyileştirmez, modeli pozisyonu savunmaya teşvik eder. Sermaye riski
yalnız işin önceliğini ve gerekiyorsa model seviyesini belirler; ciddiyet
`decision_deadline` ile anlatılır.

### Çalıştırma

```bash
fund research-cycle
```

Her gece Windows Task Scheduler ile. Daemon, paralel worker veya kuyruk
sunucusu yoktur. Döngü: veriyi tazele → yeni gözlemleri çıkar → kuralları
eşleştir → dedup → işleri seri çalıştır → doğrula → kuyruğa koy.

Gözlenebilir tetikleyiciler: yeni SEC accession, inceleme vadesi, adjusted
fiyat hareketi, manuel işlem kaydı. Earnings Item 2.02 ve doğrulanmış earnings
takvimi küçük ek iş ister (SEC `items` alanının typed katmana taşınması,
`date_confirmed` ayrımının okunması).

### Hata davranışı

| Durum | Davranış |
|---|---|
| Veri kaynağı hatası | Aynı cycle'da bir retry; başarısızsa `unavailable`, skill çalıştırılmaz; ertesi gece yeniden. İki ardışık başarısızlık → Q0 |
| Skill/transport hatası | Dondurulmuş input ile bir retry; sonraki cycle'da bir kez daha; üç başarısızlıktan sonra otomatik deneme durur |
| Şema/kontrat hatası | Bir onarım denemesi; hâlâ geçersizse adjudication'a sunulmaz, `contract_failed` gösterilir |
| Bilgisayar kapalıydı | `StartWhenAvailable`; watermark'tan devam, aradaki filing kaybolmaz |
| Geç gelen sonuç | Daha yeni kanıt varsa `superseded_result`, otomatik kabul kuyruğuna girmez |

---

## 7. Operatör yüzeyi

**Yazma CLI ile, okuma salt-okunur statik HTML ile.** Sunucu, web formu,
kullanıcı yönetimi yok. HTML aynı veriden yeniden üretilen projection'dır.

```
fund trade record          fund inbox
fund thesis open           fund adjudicate <job_id>
fund assess                fund review
fund trade-preview         fund research-cycle
fund trade-add             fund correct
```

`fund inbox` günlük olay kuyruğudur; `fund review` aylık sermaye
oturumudur — aynı şey değildirler.

### Kuyruk

| Sınıf | İçerik | Sonuç |
|---|---|---|
| **Q0** | Veri gerçeği güvenilmez, döngü art arda başarısız, `blind` tez, gerekli assessment olmadan bekleyen karar | Yeni risk artırımı bloklanabilir |
| **Q1** | Filing/earnings sonucu, mekanik breach, review vadesi, tez durum değişikliği önerisi | Adjudication gerekli |
| **Q2** | Sapmasız kontrol, yaklaşan review, retry ile düzelmiş hata | Bilgi; eylem gerektirmez |

Q1 sıralaması: vadesi geçmiş → fonlanmış tez → mekanik breach/maddi olay →
rutin review → fonlanmamış aday → oluşturulma zamanı.

### Adjudication ekranı

Görünenler: senaryonun causal zinciri, varsayımlar ve birimler, her önemli
sayı için kaynak, önceki kabul edilmiş assessment ile alan bazında fark,
yeni/çelişkili/eksik kanıtlar, mekanik kontrol sonuçları, nitel soru
cevapları, validator sonuçları.

Görünmeyenler: pozisyon ağırlığı, P&L, ortalama maliyet, önerilen işlem,
sermaye riski.

Seçenekler: `Accept` · `Reject` · `Human-authored replacement` · `Defer`.
**Toplu onay yoktur; `Accept` varsayılan seçenek değildir.**

Kullanıcı en az üç kapalı soruya cevap verir: kritik kaynakları kontrol
ettim mi · bu pozisyona sahip olmasaydım aynı downside'ı kabul eder miydim ·
önceki assessment'a göre değişimin ana nedeni ne. Maddi değişiklikte (readiness
değişimi veya downside'da 500 bp üzeri fark) kısa bir gerekçe zorunludur.

Kullanıcı incelemeden geçmek isterse kayıt `acknowledged_without_full_
adjudication` olur — `human_adjudicated` sayılmaz ve readiness yükseltmez.

Süre beklentisi: dar güncelleme 5-10 dk, yeni downside case 20-30 dk, maddi
varsayım değişikliği 15-30 dk. **30 dakikayı geçiyorsa defer veya reject.**

---

## 8. Veri modeli

Beş domain nesnesi, iki operasyon kaydı. Yedi JSON Schema, bir SQLite DDL.

| Nesne | İşlev |
|---|---|
| `capital_policy` | Boyutlandırma ve işlem kuralları |
| `account_event` | Elle girilen alım, satım, nakit hareketi |
| `thesis` | Kalıcı tez, lifecycle durumu, sürümlü `monitoring_contract` |
| `assessment_record` | İnsan tarafından kabul edilmiş tarihli tez değerlendirmesi |
| `decision_record` | Karar ve karar anındaki girdiler |
| `monitoring_check_record` | Hangi kural, hangi veriyle, ne sonuç |
| `research_job_record` | Tetikleyici, dispatch kuralı, recipe, denemeler, sonuç |

**Ayrı nesne olmayanlar:** kuyruk öğeleri (job ve açık assessment'lardan
türetilir), gözlem/trigger (job'ın `trigger_snapshot`'ında), iş denemeleri
(job içinde küçük dizi), skill sonucu (içerik-adresli artefakt, job yalnız
referansını taşır), pozisyon/NAV (`account_event` projection'ı), watermark ve
cycle kayıtları (basit SQLite tabloları, şema gerekmez).

### `account_event`

`event_id` · `event_type` (`opening_position`, `opening_cash`, `buy`, `sell`,
`deposit`, `withdrawal`, `dividend`, `fee`, `quantity_adjustment`,
`correction`) · `effective_date` · `security_id` · `quantity` · `price` ·
`cash_amount` · `currency` · `decision_id` · `recorded_at` · `note` ·
`corrects_event_id`

Açılış pozisyonları sentetik "opening fill" olarak **yazılmaz** — olmamış bir
işlem uydurmak sahte tarih, nakit çıkışı ve tutma süresi üretir. Ayrı
`opening_position` tipi kullanılır ve `cost_basis_status` taşır.

### `decision_record`

`decision_id` · `as_of` · `policy_version` · `assessment_id` · security ve
düşünülen işlem · işlem öncesi pozisyon/nakit/NAV · readiness · downside ·
mevcut ve işlem sonrası ağırlık · downside'ın bp NAV etkisi · policy tavanı ·
bağlayıcı kısıt · no-trade bandı sonucu · hard-breach sonuçları · karar ·
gerekçe · `shadow`/`live` · sonraki inceleme tarihi

Bu kayıt "o gün ne biliyordum" sorusunun cevabıdır ve değiştirilmez.

### Tipler

| Tip | Temsil |
|---|---|
| Para | `{amount: decimalString, currency: ISO-4217}` — float yasak |
| Adet | `decimalString`; kesirli hisse desteklenir |
| Oran eşiği | Policy'de bp integer (`100 = %1`); hesaplanan ağırlıklar bp'ye yuvarlanmaz |
| Kesin an | `UtcInstant` (RFC 3339, `Z`) |
| Takvim günü | `LocalDate` — gece yarısı timestamp'ine çevrilmez |
| Borsa günü | `MarketSessionDate` + takvim kimliği |
| Kimlik | UUIDv7 |

SQLite'ta exact decimal alanlar `TEXT` tutulur (`NUMERIC` affinity metni
REAL'a çevirip hassasiyet kaybettirir); hesaplama Python `Decimal` ile
yapılır. "Bugün" kanonik bir veri alanı değildir: scheduler bir
`evaluation_instant` alır, operatör tarihi ve borsa seansı ondan türetilir.

Menkul kıymet kimliği üç seviyelidir — `issuer_id` / `security_id` /
`listing_id`. GOOG ile GOOGL aynı issuer farklı security; ticker değişimi
hiçbirini değiştirmez; delisting listing'i kapatır, security'yi değil. V0'da
tek `instrument-master` belgesinde toplanır, ayrı kullanıcı yüzeyi yoktur.

Yazma tek `commit()` kod yolundan geçer; SQLite `BEGIN IMMEDIATE` ve unique
constraint'ler eşzamanlılığı çözer (dosya kilidi değil). Girilmiş satırlar
üzerinde UPDATE/DELETE reddedilir.

---

## 9. İnşa sırası

| # | Adım | "Bitti" tanımı |
|---:|---|---|
| 1 | SQLite, beş domain nesnesi, manuel işlem ve NAV projection'ı | Açılış kitabı girilebiliyor; pozisyon/nakit/NAV replay ediliyor; aynı girdi iki kez çoğaltmıyor |
| 2 | Capital policy, assessment ve trade-preview | Policy hesapları çalışıyor; bağlayıcı kısıt doğru gösteriliyor; karar dondurluyor |
| 3 | Thesis lifecycle ve monitoring contract | Tez açılıyor, assessment bağlanıyor, durum geçişleri insan yetkisinde |
| 4 | Metrik eşleme doğrulaması ve mekanik kontrol motoru | Dondurulmuş fixture'da `not_breached`/`breached`/`unavailable` üretiyor; breach yalnız `review_required` doğuruyor |
| 5 | Research job, dedup, retry, Q0/Q1/Q2 inbox | Elle verilen bir kanıt recipe'yi uçtan uca çalıştırıyor |
| 6 | Tek filing recipe'si: deep-dive → tracker → adjudication | Yeni 10-Q otomatik olarak yorumlanmış öneriye dönüşüyor |
| 7 | `fund research-cycle`, watermark, heartbeat, Task Scheduler | **Sistem kendi kendine çalışıyor:** kullanıcı filing'i hatırlamıyor, skill seçmiyor; sabah yalnız sonucu yargılıyor |
| 8 | İkinci dalga tetikleyiciler: review vadesi, fiyat şoku, earnings | Dört tetikleyici ailesi de dedup ve cooldown ile çalışıyor |
| 9 | İzleme canlılığı ve adjudication kalite uyarıları | `degraded`/`blind` yakalanıyor; törensel onay sinyalleri ölçülüyor |
| 10 | Düşük frekanslı otomatik discovery | Yeni aday üretimi aynı dispatch mekanizmasıyla; sermaye kararı üretmiyor |

**Kritik eşik Adım 7'dir.** Adım 6'da otomasyon elle başlatılınca çalışır;
Adım 7'den sonra zamanı ve kanıtı kendisi gözleyip işi kendisi başlatır.

Süre: tek tez için kendi kendine çalışan ilk dilim **12-16 odaklı iş günü**;
sekiz tezi güvenilir işleten sürüm **20-28 iş günü**; tek kişi kısmi zamanla
**5-8 takvim haftası**.

Mevcut koddan uyarlanabilecekler: SEC filing keşfi ve accession takibi,
`live_refresh`, XBRL/normalize/PIT hattı, metric catalog, fiyat ve market
snapshot'ları, codex hazırlama/çalıştırma/artefakt mekanizması, JSON Schema
doğrulama altyapısı.

Sıfırdan yazılacaklar: thesis ve assessment lifecycle'ı, monitoring contract
aktivasyonu, katalogla metric binding doğrulaması, mekanik check kayıtları,
tez-odaklı gözlemciler, `research_job` durum makinesi, sabit dispatch tablosu
ve recipe yürütücüsü, deep-dive/tracker sonuçlarının makine-okunur
sözleşmeleri, Q0/Q1/Q2 inbox, cycle heartbeat ve catch-up.

Mevcut `check_triggers` doğrudan kullanılamaz: bugün yalnız `state ==
"waiting"` adayları tarıyor, tezleri ve pozisyonları taramıyor.

---

## 10. Riskler ve kalibrasyon

### İnsanın pasifleşmesi

Otomasyonun en ciddi bedeli. Hazır bir hükmü kabul etmek, bağımsız hüküm
üretmekten bilişsel olarak çok daha kolaydır. Tamamen çözülemez, azaltılır:

- İki aşamalı ekran korunur (sermaye etkisi ilk aşamada gizli)
- Tek tıkla kabul yok; üç kapalı soru
- Maddi değişiklikte gerekçe zorunlu
- Her çeyrek en az bir tez `independent_then_reconcile` modunda değerlendirilir
- Törensel kabul ölçülür: değiştirmeden kabul oranı, çok kısa adjudication
  sayısı, kaynak açılmadan verilen kabuller, sonradan geri alınanlar →
  `adjudication_quality_warning`

### Yanlış alarm bütçesi

8 tez × yılda 2-4 filing × tez başına 1-2 kural ≈ 16-64 kural değerlendirmesi.
Hedef: yılda **4-8 anlamlı `review_required`**, tez başına 0-2. Yılda 12'den
fazla alarm veya bir çeyrekte tezlerin üçte birinden fazlasının alarm vermesi
→ kalibrasyon incelemesi.

İki tür yanlış alarm ayrılır: `measurement_error` (veri/eşleme yanlış → kuralı
tamir et) ve `decision_irrelevant_breach` (eşik aşıldı ama sermaye hükmünü
değiştirmiyor → kuralı gözden geçir).

**Eşikler alarm sayısını azaltmak için optimize edilmez**; tezin önceden
yazılmış falsifier'ından türer. Gürültü azaltma araçları: tolerans/histerezis,
ardışık iki dönem doğrulaması, baseline'a göre anlamlı değişim, kesin dedup,
kopya kuralların birleştirilmesi.

İlk yıl kalibrasyon dönemidir — ama "sonuç hoşuma gitmedi, eşiği değiştirdim"
dönemi değildir. Her değişiklik gerekçeli yeni sözleşme sürümüdür.

### Bir yıl sonra ne bozulur

| Bozulma | Olasılık | Sistem nasıl fark eder |
|---|---|---|
| Metrik/XBRL eşlemesi kayar | Yüksek | Filing geldiği hâlde metrik üretilemiyor; birim/dönem değişimi |
| Skill çıktısı contract'tan sapar | Yüksek | Sürüm sabitleme, şema doğrulama, contract fixture'ları |
| Dispatch kuralı hiç veya aşırı ateşler | Orta-yüksek | Kural bazında `last_dispatched`, `jobs_30d`, `failures_30d` raporu |
| Fiyat/veri kaynağı semantiği değişir | Orta | Kaynak kimliği, timestamp, uç değer kontrolleri |
| Tez sözleşmesi ekonomik olarak bayatlar | Kesin | Teknik doğrulama yakalayamaz; periyodik insan incelemesi gerekir |

Plugin sürümü otomatik yükseltilmez; yeni sürüm önce contract fixture'larından
geçer.

### Doğrulama

Kod yazılırken: mekanik kural motoru ve policy hesapları için birkaç
**property testi** (downside kötüleşirse tavan artamaz; readiness düşerse band
genişleyemez; ağırlıklar + nakit = %100) ve 6-8 **golden fixture** (tamamen
nakit kitap, aşırı yoğun tek pozisyon, dengeli kitap, limitlere yaklaşmış
kitap, hard-limit ihlalli kitap, split içeren kitap).

Klasik strateji backtest'i yapılmaz: tarihsel tez ve readiness girdileri yoktu,
geriye dönük üretmek hindsight bulaştırır.

---

## 11. Kullanıcı kararları

Bunlar olmadan capital policy aktive edilemez, risk hesapları yapılamaz ve
proposal üretilemez. Diğer işler (şemalar, defter, projection, dispatch
tablosu) bu cevapları beklemeden başlayabilir.

1. **Fon perimetresi** — hangi hesap ve nakit bu portföye dahil, açılış tarihi
   ne?
   *Cevapsızsa açılış kitabı ve NAV kurulamaz.*
2. **Raporlama para birimi** — kanonik NAV USD mi TL mi; diğeri yalnız bağlam
   serisi mi?
   *Cevapsızsa performans ve risk tek ölçüm tabanında hesaplanamaz.*
3. **Sermaye amacı** — hangi ufukta yönetilecek, öngörülebilir çekim ihtiyacı
   var mı?
   *Cevapsızsa kullanılabilir sermaye ve nakit tabanı belirlenemez.*
4. **Risk zarfı** — kabul edilebilir portföy drawdown'ı, pozisyon başına kayıp
   bütçesi, mutlak tek-isim tavanı?
   *Cevapsızsa güvenli pozisyon büyüklüğü üretilemez.*

**Kayıp bütçesi çıpası** (piyasa standardı değil, tasarım çıpası): starter
50-75 bp NAV, core 75-125 bp, merkez 100 bp, insan onaylı tavan 150 bp. %25
downside varsayımında 100 bp → %4 ağırlık. On pozisyon aynı anda downside'a
ulaşırsa 100 bp merkez ~%10 NAV kaybı üretir.

---

## 12. Kapsam dışı

Bilinçli olarak yapılmayacaklar. Her biri savunulabilir ama hiçbiri bu ölçekte
doğrulanmış bir ihtiyaç değil.

| Kapsam dışı | Neden |
|---|---|
| Broker CSV/OFX importer ve çok eksenli reconciliation motoru | Yılda 12 işlemde elle giriş yeterli; bağımsız defter kurmak broker ile yeni bir uyuşmazlık sınıfı yaratır |
| Genel capability router, lead/support, research case/episode mimarisi | Sabit dispatch tablosu 8 tez için yeterli |
| Kullanıcı tanımlı dispatch dili | Kural, iş ve maliyet üretme yetkisi verir; kapalı tabloda kalmalı |
| `capital_input_manifest` | Kabul edilmiş assessment + decision record aynı kanıt zincirini daha sade taşır |
| Çok seçenekli portfolio proposal ve portföy optimizasyonu | 8 pozisyonda yapay kesinlik üretir |
| Attribution ve counterfactual motoru | Yeterli karar ve tutma dönemi birikmeden yüzeyin çoğu boş kalır |
| Risk-driver registry ve korelasyon katmanı | Somut yoğunlaşma problemi tekrarlanmadan kurulmaz |
| A0-A4 yetki merdiveni | `shadow` ile `live_manual_execution` ayrımı yeterli |
| Workbook üreten skill'ler (DCF, üç tablo, model-update, audit) | Birbirini doğuran bakım ekosistemi; model gerekiyorsa tez açılmaz |
| Tam tez lifecycle uzantıları (provenance zincirleri, çok katmanlı manifest) | Küçük sözleşme yeterli |
| Otomatik `broken`/`closed` ve otomatik emir | Lifecycle hükmü ve icra insana ait |

### Büyütme tetikleyicileri

Yeni katman ancak şunlardan biri gerçekleşirse eklenir:

- İkinci broker veya belirgin işlem hacmi → importer/reconciliation
- Sabit recipe'lerin cevaplayamadığı tekrar eden işler → sınırlı routing
- 6-12 aylık karar geçmişi birikti → attribution/counterfactual
- Tekrarlayan ortak sürücü yoğunlaşması → risk-driver registry
- `shadow`/`live` ayrımı yetersiz kaldı → daha ince yetki merdiveni
- Yılda 12'den fazla alarm veya tekrarlayan `blind` → yeni özellik değil,
  monitoring kalibrasyonu

Her tetikleyicide **yalnız en küçük çözüm** eklenir.

---

## 13. Skill kullanımı

Eklentideki (public-equity-investing) 23 skill'in bu üründe kullanılanları:

| Skill | Kullanım |
|---|---|
| `earnings-deep-dive` | Yeni filing/earnings kanıtının tez üzerindeki etkisi. İlk otomatik recipe'nin lead'i. |
| `thesis-tracker` | Kanıtı teze göre yorumlar, durum değişikliği **önerir**. Kanonik state'i değiştiremez, yeni tez açamaz. |
| `long-short-pitch` | Yeni tez veya `onboarding_underwrite` modunda mevcut pozisyonun normalleştirilmesi. Tez açabilen tek adım. |
| `comps-valuation` | Valuation anchor gerektiğinde. Dar capability, deterministik doğrulanabilir — ilk bağlanacak adapter. |
| `company-tearsheet` | Issuer baseline eksik veya bayatsa. |
| `idea-generation` | Düşük frekanslı discovery; yalnız araştırma adayı üretir, sermaye kararı üretmez. |

Kalan 17 skill kullanılmaz. Gerekçeleri arşivdeki envanterde (tur 18-32, 41).

**Skill'ler sermaye otoritesi değildir.** Domain nesneleri skill adı taşımaz;
skill ve model kimliği yalnız provenance'ta görünür. Eklenti kaldırılırsa
muhasebe, NAV, policy, risk kontrolleri, karar kaydı ve raporlama çalışmaya
devam eder; kaybedilen yalnız yeni araştırma üretimidir.

---

## 14. İlk hafta

1. Dört blokaj sorusunu cevapla.
2. Capital policy v0'ı doldur; varsayılan kullanılan her sayıyı `provisional`
   işaretle.
3. Mevcut pozisyonları ve nakdi açılış kitabı olarak yaz (maliyeti bilinmeyen
   varsa `cost_basis_status: unknown`).
4. Bir security için elle bir tez ve monitoring contract yaz; mekanik
   kuralların metrik kataloğunda karşılığı olduğunu doğrula.
5. Tek bir gölge kararı uçtan uca çalıştır:
   `assess → trade-preview → decision → trade/no_change`.

> **Bu akışa doğrudan hizmet etmeyen hiçbir kodu yazma.**
>
> **Otomasyona hatırlama, gözleme ve çalıştırma işini ver; araştırma hükmünü
> ve sermaye yetkisini verme.**
