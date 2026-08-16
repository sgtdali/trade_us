# Codex tasarım oturumu — fon işletim sistemi (2026-08-15/16)

Bu klasör, `docs/pei-company-lifecycle-tasarim.md`'nin arkasındaki ham
tartışmayı taşır. Doküman kararları ve gerekçeleri içerir; buradaki kayıt
o kararların **nasıl** varıldığını, hangi iddiaların kodda doğrulandığını
ve hangi önerilerin geri çekildiğini gösterir.

## Oturum künyesi

| | |
|---|---|
| Araç | codex CLI 0.145.0 |
| Model | `gpt-5.6-sol`, reasoning effort `high` |
| Oturum | Tek oturum, `thread_id: 01a006c8-84c4-7180-aacd-7892b97a9d5e` |
| Süreklilik | `codex exec resume` ile 42 tur boyunca aynı bağlam korundu |
| Tarih | 2026-08-15 / 2026-08-16 |
| Karşı taraf | Claude (bu repoda çalışan oturum) |

Tartışma **beş blok** hâlinde yürüdü. Her blok bir öncekinin sonuçlarını
sınadı ve bir kısmını geçersiz kıldı; bu yüzden **son blok önceki
bloklardan üstündür.** Erken turlardaki bir hükmü tek başına alıntılamayın.

| Blok | Turlar | Konu | Sonuç |
|---|---|---|---|
| 1 | 01-07 | Ömür döngüsündeki açık noktalar, ilke seviyesi | 9 kararda revizyon, 3 kod kusuru |
| 2 | 08-17 | Mekanizma: olay şeması, defter, eşikler, insan yüzeyi | Beş eksen üçe indi, Başlık 4 karar 5 iptal, capital policy boşluğu bulundu |
| 3 | 18-32 | Eklentideki 23 skill'in envanteri | Lead+support modeli, 10+1 katalog, "V1 etiketi hak edilmedi" |
| 4 | 33-42 | **Fon yönetim sistemi reframe'i** | Ürün sınırı tersine döndü; araştırma alt sistem oldu |
| 5 | 43-52 | Policy'nin sınanması + somut şema | Dört kanıt katmanı, A0-A4 yetki merdiveni, V0 kesimi (7 tam şema + 3 stub + 1 DDL) |
| 6 | 53-59 | Fon ile eklenti skill sisteminin entegrasyonu | Tek sınır, `capital_input_manifest`, iki aşamalı adjudication, görünürlük matrisi, revize inşa sırası |

## Tur dizini

Her tur iki dosya: `-soru` (Claude'un turu) ve `-cevap` (codex'in turu).

### Blok 1 — ilke seviyesi

| Tur | Konu |
|---|---|
| 01 | Açılış: ömür döngüsünde açıkta kalan noktalar |
| 02 | Tur/dilim kör noktası; zincirin ortasındaki isim |
| 03 | Çift defter, fonlama olayının yokluğu, `retired` belirsizliği |
| 04 | Ödenmemiş sermaye karşılaştırması çeki; supersede; oturum ömrü |
| 05 | Ölçek ve tek kişilik kapasite; defterin O(N²) büyümesi |
| 06 | Onay kapıları; önceliklendirme; YAGNI |
| 07 | Kapanış: uzlaşılan / açık / anlaşılamayan |

### Blok 2 — mekanizma

| Tur | Konu |
|---|---|
| 08 | Olay sözlüğü; `waiting_for_trigger`'ın yanlış modellenmesi |
| 09 | Tur/dilim mekaniği; `analysis_proposed` geri çekildi |
| 10 | Defterin fiziği; git'in kanonik defter olamayacağı; SQLite |
| 11 | Tezin eşikleri; PIT/restatement; izleme sözleşmesi |
| 12 | Kurumsal işlemler, lot, para birimi, manuel idempotency |
| 13 | `portfolio-risk-management` uyuşmazlığı → Başlık 4 karar 5 iptal |
| 14 | Artefakt kimliği; agy çıkarım katmanının fail-open noktaları |
| 15 | İnsan yüzeyi; P0-P4 kuyruğu; haftalık emek tahmini |
| 16 | **Özeleştiri:** "erken kurumsallaşmış"; capital policy boşluğu |
| 17 | Kapanış: ne değişti, V1 dikey dilimi |

### Blok 3 — skill envanteri

| Tur | Konu |
|---|---|
| 18 | 23 skill triyajı; eklentinin lead+support felsefesi |
| 19 | Keşif kümesi; support'un lead amacını ezmesi (kodda doğrulandı) |
| 20 | Değerleme kümesi; `valuation_anchor`; workbook dörtlüsü kapatıldı |
| 21 | Kazanç/olay kümesi; filing döngüsünün işletim döngüsü olması |
| 22 | Kanıt katmanı; `research_case`/episode modeli |
| 23 | Karar kümesi; long-only kısıtı; `initiating-coverage` escalation'a |
| 24 | Tez izleme lifecycle'ı; skill enum'unun domain enum'u olamayacağı |
| 25 | Eleme kümesi; eklentinin `shared/` sözleşmeleri; `contract_manifest` |
| 26 | Pack mimarisi; "monolitik pack + geç budama" |
| 27 | Çıktı sözleşmeleri; üç katmanlı doğrulama; model politikası |
| 28 | Üç ilişki grafiği; katalog şeması v2; `allowed_next` siliniyor |
| 29 | Platform işleri (F1-F18); "skill orkestratörü değil" |
| 30 | *(Geçersiz)* Deneme koşularına özel köprü planı — bkz. not |
| 31 | **Özeleştiri:** triyaj kanıt değil hipotez; gölge vaka kapısı |
| 32 | Kapanış: 23 skill'in tam envanteri |

### Blok 4 — fon reframe'i

| Tur | Konu |
|---|---|
| 33 | **Reframe:** fon yönetim sistemi; aggregate root değişimi |
| 34 | Capital policy v0; readiness merdiveni; nakit; no-trade bandı |
| 35 | Hedef portföyü kim kurar; replacement hurdle; `portfolio_proposal` |
| 36 | Performans ve attribution; süreç×sonuç matrisi; counterfactual |
| 37 | Risk; üç kaldıraç; driver registry; drawdown; stop-loss |
| 38 | İcra köprüsü; broker otoritesi vs sistem meşruiyeti; reconciliation |
| 39 | Araştırma↔sermaye geri beslemesi; R0-R5; VOI kapısı |
| 40 | Yeni inşa sırası; ölen / değişen / ayakta kalan kararlar |
| 41 | Skill envanteri fon çerçevesinde; C1-C18; fon tarafında LLM |
| 42 | Kapanış: sistemin tanımı, fon değişmezleri, ilk hafta |

### Blok 5 — sınama ve şema

| Tur | Konu |
|---|---|
| 43 | Backtest neden geçersiz; dört ayrı sınama türü |
| 44 | Monotonluk özellikleri; fixture mimarisi; `policy_validation_spec`'in yeri |
| 45 | Gölge koşu (kör paralel + kâğıt icra); A0-A4 yetki merdiveni |
| 46 | Şema stratejisi: dört temsil, para/zaman/kimlik/sürümleme kararları |
| 47 | Kimlik üçlüsü; `opening_account_state_asserted`; muhasebe olay ailesi; lot |
| 48 | `capital_policy` şeması ve doldurulabilir draft; `operating_authority`; `config` vs `data` |
| 49 | `portfolio_risk_snapshot` ve `portfolio_proposal` şemaları; binding constraint |
| 50 | Olay zarfı; SQLite depolama; tek yazarlı commit kapısı |
| 51 | **V0 kesimi:** 7 tam şema + 3 stub + 1 DDL |
| 52 | Kapanış: özet, önceki turlarla daraltmalar, yarın ne yapılacak |

### Blok 6 — fon ↔ skill entegrasyonu

| Tur | Konu |
|---|---|
| 53 | Temas yüzeyleri; beş entegrasyon değil tek sınır |
| 54 | `capital_input_manifest`; bayatlama; açılış kitabı; eksik girdi × aksiyon matrisi |
| 55 | `research_work_request`; routing; dedup; iptal; kullanıcı yüzeyi |
| 56 | Görünürlük matrisi; assessment modları; sermaye tutarının modele gösterilmemesi |
| 57 | İki aşamalı adjudication; çöp çıktı; fiyat-tez çelişkisi; törensel onay |
| 58 | Revize inşa sırası; en küçük entegrasyon dilimi; ilk adapter `comps-valuation` |
| 59 | Kapanış: sınırın tek sayfalık tarifi |

## Okurken dikkat

**Tur 30 geçersizdir.** O tur, repodaki mevcut koşulara (ve o koşulardan
doğan tarihli tetikleyicilere) özel bir geçiş planı üretti. Kullanıcı
2026-08-16'da bu koşuların deneme amaçlı olduğunu ve korunacak değer
taşımadığını belirtti; plan kapsam dışı kaldı. Aynı turda doğrulanan
**mekanizma kusurları** (tarih tetikleyicisinin kanıt beklememesi, kanıt
gözlem katmanının yokluğu) geçerliliğini korur ve dokümana işlenmiştir.

**Blok 1-3 araştırma-merkezli okunur.** Blok 4 ürün sınırını tersine
çevirdi: sistem bir araştırma defteri değil, araştırmayı alt sistem olarak
kullanan bir portföy işletim sistemidir. Blok 1-3'teki "V1", "ürün sınırı"
ve "kapsam dışı" ifadeleri bu ışıkta okunmalıdır. Hangi kararın öldüğü,
hangisinin ayakta kaldığı **tur 40**'ta madde madde listelidir.

**Kod referansları o günkü hâle aittir.** Turlarda satır numarasıyla
verilen bulgular 2026-08-15/16 tarihli çalışma ağacına göredir. Kod
değiştikçe satır numaraları kayar; bulgunun kendisi
`docs/pei-company-lifecycle-tasarim.md`'nin "Açık işler" bölümünde
izlenir.

**Ham JSON olay akışları taşınmadı.** Her koşunun `--json` çıktısı
(oturum kimliği, item olayları, token kullanımı) taşıma artefaktıdır ve
içerik taşımaz; yalnız `thread_id` yukarıda kayıtlıdır.
