Haklısınız; son üç turda **muhasebenin manuel olması** ile **araştırma operasyonunun manuel olması**nı yanlış biçimde birbirine bağladık. Doğru küçük ürün, manuel işlem girişli fakat otomatik araştırma operasyonlu olmalıdır.

## 1. Küçük orkestrasyon ne yapmalı?

Genel router değil, **kural güdümlü araştırma çalıştırıcısı** gerekir:

```text
Günlük zamanlayıcı
      ↓
SEC / fiyat / takvim / review gözlemcileri
      ↓
Normalize edilmiş tetikleyici
      ↓
Sabit dispatch tablosu
      ↓
Duplicate/cooldown kontrolü
      ↓
Sabit job recipe
      ↓
Skill seri olarak çalışır
      ↓
Şema + kontrat doğrulaması
      ↓
İnsan adjudication kuyruğu
```

Bir kural şunları taşır:

- `rule_id`
- Gözlenen olay
- Security/tez/pozisyon koşulu
- Çalıştırılacak sabit recipe
- Assessment modu
- Duplicate anahtarı
- Cooldown
- En fazla deneme sayısı
- Açık/kapalı durumu

Kural doğrudan tek skill’e veya önceden belirlenmiş kısa bir recipe’ye gider. Dinamik capability resolution, lead seçimi, support bütçesi ve episode routing yoktur.

Örnek V0 tablosu:

| Gözlem | Koşul | Sabit recipe | Mod | Duplicate anahtarı |
|---|---|---|---|---|
| Yeni 10-Q/10-K | Açık tez var | `earnings-deep-dive` | `update_against_prior` | security + accession |
| Earnings release kanıtı geldi | Açık tez veya izlenen aday | `earnings-deep-dive` | Tez varsa update, yoksa de novo | security + reporting period |
| İnceleme vadesi doldu | Açık tez var | `thesis-tracker` | `update_against_prior` | thesis + review date |
| Doğrulanmış earnings penceresi açıldı | Fonlanmış tez var | `earnings-preview` | `update_against_prior` | security + event date |
| Maddi 8-K geldi | Açık tez var | `event-driven-analyzer` | `update_against_prior` | security + accession |
| Fiyat şoku oluştu | Fonlanmış tez var | Kör ilk geçişli thesis review | `independent_then_reconcile` | security + fiyat penceresi |
| Trade-preview istendi ama assessment yok | Security değerlendirilecek | Pitch `onboarding_underwrite` modu | `de_novo` | security + assessment generation |
| Periyodik discovery tarihi geldi | Discovery açık | `idea-generation` | `de_novo` | discovery date |

İlk uygulamada bunların hepsi şart değil; ancak mekanizma bu sabit tablo olmalıdır. Dinamik router değildir.

### Çalıştırma biçimi

Günde bir kez tek komut zamanlanır:

```text
fund research-cycle
```

Bu komut:

1. Verileri tazeler.
2. Yeni gözlemleri çıkarır.
3. Kuralları eşleştirir.
4. Aynı tetikleyiciyi ikinci kez çalıştırmaz.
5. İşleri seri olarak çalıştırır.
6. Başarılı sonuçları adjudication kuyruğuna koyar.
7. Bir kez retry eder; tekrar başarısızsa kullanıcıya gösterir.

Daemon, paralel worker veya kuyruk sunucusu gerekmez. Windows Task Scheduler yeterlidir.

Bu karar eski “her workflow insan tarafından tetiklenir” invariant’ını değiştirir:

> **Aktif ve kullanıcı tarafından önceden onaylanmış bir dispatch kuralı analizi otomatik başlatabilir; araştırma hükmünün kabulü ve sermaye etkisi yine insana aittir.**

## 2. Bugün gerçekten gözlenebilen tetikleyiciler

| Tetikleyici | Bugünkü durum | Gereken ek iş |
|---|---|---|
| Yeni 10-Q/10-K | Güçlü biçimde gözlenebilir | Son görülen accession’ı security bazında saklamak |
| Yeni SEC accession | Gözlenebilir | Observation/dedup kaydı |
| Earnings 8-K Item 2.02 | Ham SEC verisinde mevcut | `items` alanını typed katmana taşımak |
| Earnings kanıtı gerçekten indirildi | Kısmen mevcut | `release_observed` ile `evidence_available` ayrımı |
| Review tarihi doldu | Tam deterministik | Assessment/tezde `review_due` bulunması |
| Fiyat hareketi | Gözlenebilir | Adjusted-close baseline, pencere ve eşik tanımı |
| Earnings tarihi yaklaştı | Tarih gözlenebilir ama güven zayıf | Confirmed/estimated ayrımı ve doğrulama kaynağı |
| Typed KPI eşiği ihlal edildi | Motor destekliyor, veri sözleşmesi eksik | Monitoring contract ve metric mapping |
| Maddi 8-K item kodu | Ham veride gözlenebilir | Item kodunu typed observation’a taşımak |
| Haber veya fiyat hareketinin nedeni | Güvenilir biçimde gözlenemiyor | Ayrı haber/evidence kaynağı gerekir |
| Manuel alım/satım | Tam gözlenebilir | Kullanıcının `trade-add` kaydı yeterli |

Kod tarafındaki somut durum:

- `evaluate_trigger()` bugün `date_due`, `event_window`, `new_filing` ve `metric_condition` biliyor; fakat `date_due`, tarih kesinliğini okumuyor. [pei_workflow.py](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/src/adapter/pei_workflow.py:1575)
- `check_triggers()` yalnız `state == "waiting"` adayları tarıyor; açık tezleri veya pozisyonları taramıyor. Bu nedenle doğrudan yeniden kullanılamaz. [pei_workflow.py](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/src/adapter/pei_workflow.py:1599)
- Pack, earnings tarihini açıkça `date_confirmed: false` diye işaretliyor. [us_pei_pack.py](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/scripts/us_pei_pack.py:543)
- SEC’in `items` kolonu ham payload’da okunuyor fakat `FilingRef` bunu taşımıyor. [us_pei_pack.py](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/scripts/us_pei_pack.py:867), [models.py](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/src/adapter/models.py:8)
- SEC discovery ledger’ını tazeleyecek kod mevcut. [live_refresh.py](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/src/adapter/live_refresh.py:158)
- `check-triggers` bugün bridge üzerinden elle çağrılan bir komut; arka planda zamanlanmış çalışma yok. [us_pei_dashboard_bridge.py](C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/scripts/us_pei_dashboard_bridge.py:201)

Dolayısıyla ilk güvenilir gözlem kümesi şudur:

1. Yeni SEC filing/accession
2. Review vadesi
3. Adjusted fiyat hareketi
4. Manuel pozisyon/işlem olayı

Earnings Item 2.02 ve doğrulanmış earnings takvimi küçük ek iş ister. KPI eşikleri ise tez izleme sözleşmesiyle birlikte ele alınmalıdır.

## 3. İnsan nerede kalır?

Doğru sınır kullanıcının söylediği gibidir:

> **Sistem gözler, tetikler ve çalıştırır; insan araştırma hükmünü kabul eder, değiştirir veya reddeder.**

Kullanıcının önüne boş `fund assess` formu gelmez:

```text
NVDA — YENİ 10-Q İNCELEMESİ

Skill önerisi:
Readiness       core → starter
Downside        -%24 → -%32
Tez durumu      review_required

Dayanak:
- Veri merkezi büyümesi beklentinin altında
- Brüt marj 180 bp geriledi
- Yeni dönem guidance aşağı çekildi

Kaynaklar:
[filing ve ilgili pasajlar]

[Accept] [Reject] [Human-authored replacement] [Defer]
```

Sessizce sayı düzenlemek yoktur:

- Olgusal hata varsa sonuç reddedilir.
- Kullanıcı farklı bir yargıya sahipse ayrı `human_authored_assessment` oluşturur.
- Kabul edilen assessment ancak bundan sonra `trade-preview` içinde sermaye etkisiyle gösterilir.

### İki aşamalı adjudication bozuluyor mu?

Hayır. İki aşamanın amacı insanın modeli görmesini engellemek değildi; **araştırma hükmünü sermaye sonucundan ayırmaktı.**

Akış şöyle kalır:

```text
Skill sonucu
    ↓
Aşama 1: Kaynak, mantık, readiness ve downside yargısı
         Pozisyon ağırlığı/P&L/işlem etkisi gizli
    ↓
Kabul edilmiş assessment
    ↓
Aşama 2: trade-preview ve portföy etkisi
```

Skill çıktısının insanı çerçevelemesi tamamen yok edilemez. Bunu assessment modlarıyla sınırlarız:

- **Yeni isim/onboarding:** `de_novo`
- **Rutin filing veya review güncellemesi:** `update_against_prior`
- **Maddi tez kırılması, fiyat–tez ayrışması veya karar-kritik yeniden underwrite:** `independent_then_reconcile`

Son modda ilk analiz portföy ağırlığını, P&L’i ve mümkünse mevcut hükmü görmeden yapılır; ardından eski assessment ile farklar ayrıca uzlaştırılır.

## Son hüküm

Küçük sistemin otomasyonu şu değildir:

> “Hangi skill uygun olabilir?” diye genel bir ajan ağı kurmak.

Şudur:

> **Sekiz açık pozisyon için gözlenebilir birkaç olayı izle, önceden yazılmış 5–8 sabit kuralla doğru recipe’yi otomatik ve seri çalıştır, yalnız sonucu insana getir.**

Muhasebe manuel olabilir. Araştırma operasyonunun hafızası ve takvimi manuel olmamalıdır.