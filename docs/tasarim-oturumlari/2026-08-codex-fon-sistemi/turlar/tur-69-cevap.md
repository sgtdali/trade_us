## 1. Güncel nesne modeli

YAGNI sınırıyla toplam beş domain nesnesi, iki kalıcı operasyon kaydı yeterlidir.

| Nesne | Tür | Kalıcı mı? | Şema? | İşlev |
|---|---|---:|---:|---|
| `capital_policy` | Domain | Evet | Evet | Boyutlandırma ve işlem kuralları |
| `thesis` | Domain | Evet | Evet | Kalıcı tez kimliği, lifecycle durumu ve geçerli `monitoring_contract` |
| `assessment_record` | Domain | Evet | Evet | Tezin insan tarafından kabul edilmiş tarihli değerlendirmesi |
| `decision_record` | Domain | Evet | Evet | Al/azalt/tut/no-change kararını ve karar anındaki girdileri dondurur |
| `account_event` | Domain | Evet | Evet | Elle girilmiş alım, satım ve nakit hareketi |
| `monitoring_check_record` | Operasyonel kanıt | Evet | Evet | Hangi kuralın hangi veriyle ne sonuç verdiğini kaydeder |
| `research_job_record` | Operasyonel iş | Evet | Evet | Tetikleyici, dispatch kuralı, recipe, denemeler, sonuç ve hata durumunu taşır |

`monitoring_contract`, ayrı lifecycle nesnesi değil, `thesis` içindeki sürümlü bir alt belgedir. Eski sürümleri assessment ve check kayıtlarında referanslandığı için korunur.

Ayrı nesne yapılmayacaklar:

| Kavram | Temsil |
|---|---|
| Kuyruk öğesi | `research_job_record` ve açık assessment’lardan türetilen projection |
| Gözlem/trigger | `research_job_record.trigger_snapshot` veya `monitoring_check_record` içinde |
| İş denemesi | `research_job_record.attempts` içinde küçük dizi; ayrı attempt nesnesi yok |
| Skill sonucu | İçerik-adresli artefakt; job yalnızca referansını taşır |
| Mevcut pozisyon/NAV | `account_event` projection’ı |
| Watermark | Basit SQLite state satırı; JSON Schema gerekmez |
| Cycle çalışması | Küçük operasyon tablosu; DDL yeterli, JSON Schema gerekmez |
| Dispatch kuralı | Kodun sahip olduğu kapalı tablo |
| `capital_input_manifest` | Yok; küçük sistemde kabul edilmiş assessment ve decision record bu görevi üstlenir |

Dolayısıyla yeni otomasyon, nesne sayısını kontrolden çıkarmıyor: **7 şemalı kayıt + watermark/cycle için iki basit operasyon tablosu**.

## 2. Dispatch ve monitoring kurallarının yeri

### Dispatch

V0’da dispatch kuralları kullanıcı tarafından yazılabilen genel bir config dili olmamalı. **Kod içinde tipli ve kapalı bir tablo** olmalı:

```text
rule_id
observer_event_type
eligibility_predicate
assessment_mode
recipe
dedup_key_builder
cooldown
enabled_by_default
rule_version
```

Örneğin:

```text
new_relevant_filing + active_thesis
→ deep_dive_then_tracker
→ update_against_prior
```

Bunun nedeni sadece kolaylık değil: dispatch kuralı otomatik LLM çağrısı, maliyet ve iş üretme yetkisi veriyor. Keyfî config’e açılırsa farkında olmadan küçük bir kural dili ve yetki sistemi kurmuş oluruz.

Kullanıcı config’i yalnızca kapalı rule ID’leri için şunları değiştirebilir:

- `enabled`
- fiyat hareketi eşiği
- cooldown
- takvim aralığı

Predicate, recipe ve dedup semantiği kodda kalır. Her job, kullanılan `rule_id` ve `rule_version` değerini kopyalar.

### Monitoring

Monitoring kuralları teze özgü domain verisidir; `thesis.monitoring_contract` içinde yaşar.

Doğrulama iki kez yapılır:

1. **Yazım/aktivasyon anında:** `metric_id`, birim, dönem tipi ve test türü katalogla eşleşmiyorsa sözleşme aktive edilmez.
2. **Çalışma anında:** katalog veya veri yapısı sonradan değişmişse savunmacı yeniden doğrulama yapılır; uyumsuzluk `unavailable` üretir, “değişiklik yok” üretmez.

Metrik eşlemesi runtime’da tahmin edilmez. Yeni eşleme veya anlam değişikliği yeni `monitoring_contract_version` gerektirir. Serbest formül yok; yalnızca kapalı test türleri kullanılır.

## 3. Güncellenmiş süre tahmini

Önceki 8–12 iş günü artık geçerli değil; o rakam otomatik orkestrasyon ve gerçek tez takibi içermiyordu.

Gerçekçi tahmin:

- **Tek tez + yeni filing için kendi kendine çalışan ilk dikey dilim:** 12–16 odaklı iş günü.
- **8 tezi güvenilir biçimde işleten sürüm:** 20–28 iş günü.
- **Tek kişi, kısmi zaman:** yaklaşık 5–8 takvim haftası.

Kabaca dağılım:

| İş | Süre |
|---|---:|
| Manuel hesap/karar günlüğü ve projection | 5–8 gün |
| Thesis, assessment ve monitoring contract | 3–5 gün |
| Metrik bağlama ve mekanik kontrol motoru | 3–5 gün |
| Job durumu, dedup, retry, watermark | 3–4 gün |
| Tek filing recipe’si ve adjudication inbox | 3–5 gün |
| Scheduler, HTML görünüm ve hata senaryoları | 3–4 gün |

Bunlar tamamen sıfırdan yazılmıyor.

**Mevcut koddan uyarlanabilecekler:**

- SEC filing keşfi ve accession takibi
- `live_refresh`
- XBRL/normalize/PIT hattı
- metric catalog
- fiyat ve market snapshot’ları
- Codex hazırlama/çalıştırma/artefakt mekanizması
- `evaluate_trigger`, `check_triggers` ve trigger yenileme fikri
- mevcut JSON Schema doğrulama altyapısı

**Yeni yazılacaklar:**

- thesis ve assessment lifecycle’ı
- monitoring contract aktivasyonu
- katalogla metric binding doğrulaması
- mekanik check kayıtları
- thesis-aware gözlemciler
- `research_job` durum makinesi, dedup ve sınırlı retry
- sabit dispatch tablosu ve recipe yürütücüsü
- deep-dive/tracker sonuçlarının makine-okunur contract’ları
- Q0/Q1/Q2 inbox ve iki aşamalı adjudication
- cycle heartbeat, catch-up ve Task Scheduler kurulumu

Mevcut `check_triggers` doğrudan yeniden kullanılamaz; candidate’ın `waiting` durumuna bağlı bugünkü sınırı kaldırılıp tez/pozisyon odaklı gözlemcilere ayrılması gerekir. Bu nedenle “kod zaten var” süreyi azaltır, fakat otomasyonun doğruluğunu hazır hâle getirmez.

## 4. Yeni inşa sırası

1. **Küçük ürün sınırını ve sabit dispatch tablosunu dondur.**  
   Yalnızca ilk filing kuralı ve gerekli durum sözlükleri tanımlanır.

2. **Manuel hesap günlüğünü kur.**  
   `account_event`, pozisyon, nakit ve NAV replay edilir.

3. **Manuel karar akışını kur.**  
   `capital_policy`, `assessment_record`, `decision_record`, `fund assess` ve `fund trade-preview` çalışır.

4. **Thesis lifecycle’ını ekle.**  
   Tez açılır, assessment bağlanır, `active/review_required/broken/closed` geçişleri insan yetkisinde işler.

5. **Monitoring contract yazımını ve aktivasyon doğrulamasını ekle.**  
   Bir tez için 1–2 mekanik kural ve 1–2 nitel soru katalogla doğrulanabilir.

6. **Mekanik kontrol motorunu saf fonksiyon olarak kur.**  
   Dondurulmuş veri fixture’ında `not_breached/breached/unavailable` üretir; `breached` yalnızca `review_required` doğurur.

7. **Job kaydı, dedup, retry ve inbox’ı kur.**  
   Henüz otomatik gözlemci olmadan elle verilen bir kanıt, recipe’yi uçtan uca çalıştırır.

8. **Tek gerçek otomasyon dilimini bağla.**  
   Yeni ilgili 10-Q/10-K → monitoring check → deep-dive → tracker → Q1 adjudication.

9. **`fund research-cycle` ve Task Scheduler’ı etkinleştir.**  
   Watermark, catch-up, tek retry, heartbeat ve Q0 hata görünürlüğü eklenir.

**Bu adımın sonunda sistem gerçekten kendi kendine çalışıyor sayılır:** kullanıcı filing’i hatırlamaz veya skill’i seçmez; sabah yalnızca sonucu yargılar.

10. **İkinci dalga tetikleyicileri ekle.**  
    Sırasıyla `review_due`, fiyat şoku, earnings evidence ve doğrulanmış earnings window eklenir.

11. **Sekiz tezle gölge işletim yap ve kalibre et.**  
    Yanlış alarm, iş yükü, yinelenen job, başarısız route ve adjudication süresi ölçülür.

12. **Discovery/onboarding otomasyonunu en son bağla.**  
    Mevcut kitabın izlenmesi güvenilir olmadan yeni aday üretimi otomatikleştirilmez.

Kritik eşik Adım 9’dur. Adım 8’de otomasyon elle başlatıldığında çalışır; Adım 9’dan sonra zamanı ve kanıtı kendisi gözleyip işi kendisi başlatır.