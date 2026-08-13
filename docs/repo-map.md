# Repo haritası

Bu dosya "ne nerede, neden orada" sorusuna tek cevap. Aşağıdaki
tutarsızlıklar tespit edilip 2026-08-13'te düzeltildi; bölüm 3 çözümü
anlatıyor.

Etiketler: **[kaynak]** elle yazılan/tutulan gerçek veri · **[üretilmiş]**
script'lerle yeniden üretilebilir · **[eski]** yeni sistemin yerini aldığı
ama hâlâ referans edilen · **[tutarsız]** aşağıda ayrı bölümde açıklanan bir
sorunu olan.

## Üst düzey

| Yol | Ne | Etiket |
|---|---|---|
| `src/adapter/` | Python iş mantığı — SEC/XBRL çekme, değerleme motoru, PEI orkestratör, portfolio/watchlist | [kaynak] |
| `scripts/` | Çalıştırılabilir giriş noktaları (`us_pei_pack.py`, `us_pei_workflow.py`, `us_pei_record.py`, `us_pei_dashboard_bridge.py`) | [kaynak] |
| `config/` | Şirket tanımları, evren listeleri, değerleme/peer politikaları, workflow kataloğu | [kaynak] |
| `schemas/` | JSON Schema sözleşmeleri (finansal, event, thesis-record, vb.) | [kaynak] |
| `docs/` | Tasarım dokümanları | [kaynak] |
| `tests/` | pytest | [kaynak] |
| `web/` | Next.js paneli | [kaynak] |
| `data/` | Çalışma zamanı verisi — aşağıda detaylı | karışık |
| `pei/` | PEI koşu artefaktları — 2026-08-12'ye kadarki koşular, dondurulmuş | **[eski, donduruldu]** |
| `guidance/` | Rehberlik/guidance defteri | [kaynak] |
| `live/` | Canlı koşu kökü, SEC belge önbelleği | [üretilmiş], gitignore'da |
| `raw-cache/` | SEC ham arşiv önbelleği | [üretilmiş], gitignore'da |

## `data/` altı

| Yol | Ne yazıyor | Git durumu | Not |
|---|---|---|---|
| `data/pei-workflow/events.jsonl` | Tüm sistemin tek otoriter kaydı — append-only olay günlüğü | tracked | Kanonik. |
| `data/pei-workflow/runs/` | Orkestratörün `start-idea`/`prepare` ile ürettiği pack/instructions/result — 2026-08-13'ten itibaren **tek canonical PEI artefakt ağacı** | tracked | `pei/` yerini aldı. |
| `data/pei-workflow/dashboard-scratch/` | Web panelinden yapıştırılan sonuç/draft metinleri | gitignore'da | Panel çalışma alanı; onaylanan kopya `data/pei-workflow/runs/.../result.md`'ye zaten `attach-result` ile yazılıyor. |
| `data/thesis-tracker/<TICKER>/*.jsonl` | Onaylı tez kayıtları, append-only | tracked | Kanonik. |
| `data/consensus/`, `data/events/` | Günlük konsensüs/olay takvimi anlık görüntüleri | gitignore'da | `events.jsonl` bunları kanıt olarak referans etmiyor — tamamen regenerable, `live/` ve `raw-cache/` ile aynı muameleyi görüyor. |
| `data/valuation-history/history.json` | Tarihsel çarpan serisi | tracked | Kanonik. |
| `data/portfolio/portfolio.json` | Portföy pozisyonları | oluşunca tracked | Bilinçli olarak event-log dışı tutuldu — bkz. bölüm 3.2. |
| `data/watchlist/*.json` | İzleme listesi | oluşunca tracked | Aynı karar. |

## Tespit edilen tutarsızlıklar ve çözümleri (2026-08-13)

### 1. İki ayrı PEI artefakt ağacı — çözüldü

- **Eski / elle koşulan:** `pei/<tarih>/<ticker>/<adım>/` — 2026-08-12'ye kadarki olaylar buraya işaret ediyor. **Dondu, yeni yazma yok.** Geçmiş olaylardaki path/hash referansları değişmedi (append-only ilkesi gereği geriye dönük taşınmadı).
- **Yeni / orkestratör:** `data/pei-workflow/runs/<run_id>/work/<work_item_id>/<tarih>/<ticker>/<adım>/` — artık **git'e eklendi**, 2026-08-13'ten itibaren tek canonical ağaç.

`data/pei-workflow/dashboard-scratch/` ayrıca gitignore'a alındı — panelin geçici yapıştırma alanı, kalıcı kanıt zaten `attach-result` ile canonical ağaca kopyalanıyor.

### 2. portfolio/watchlist event-log dışında — bilinçli karar olarak belgelendi

Tam event-sourcing'e taşımak (append-only + projeksiyon) bu ikisi için orantısız bir yeniden tasarım olurdu — `portfolio-risk-management` zaten hiç workflow'a bağlanmamış, mandate dışı bir özellik. Karar: **basit CRUD kalır**, ama artık dosyalar oluştukça git'e alınacak (state sessizce kaybolmasın). Denetim izi gerekirse ayrı bir görev olarak ele alınmalı.

### 3. `generate_draft_events` (pei_workflow.py) — kök neden düzeltildi (2026-08-13)

Regex/tablo ayrıştırıcı (`parse_screen_table`) tamamen kaldırıldı. Idea-generation için taslak çıkarımı artık `agy` (Gemini CLI) ile `--json-schema` üzerinden şemaya zorlanmış gerçek bir LLM çağrısı — bkz. `extract_candidates_via_agy` ve `schemas/pei-idea-screen-extraction.schema.json`, karar gerekçesi [pei-workflow-orchestrator.md](pei-workflow-orchestrator.md) §12 madde 10. Workflow eşlemesi (`suggested_workflow` → `mapped_workflow`) hâlâ deterministik kodda. `validate`/`approve` adımları ayrı, elle tetiklenen kontrol noktaları olarak duruyor.

### 4. `web/src/components/` içinde kaynağı bilinmeyen dosyalar

`header.tsx`, `panel/portfolio.tsx`, `panel/watchlist.tsx`, `api/generate-draft/route.ts` — kullanıcı tarafından oturum dışında eklendi. Fonksiyonel olarak çalışıyor (typecheck/lint temiz), sadece bu dosyada not düşülüyor: gelecekte panele yeni bir sayfa/route eklenirken bu listeye eklenmesi, dokümansız kalmaması gerekiyor.
