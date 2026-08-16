# docs/ — hangi doküman ne işe yarar

Bu klasörde iki ayrı dünyaya ait dokümanlar var: **bugün çalışan sistem** ve
**hedeflenen sistem**. Karıştırılırsa yanlış yöne gidilir. Aşağıdaki tablo
hangisinin hangisi olduğunu söyler.

## Yürürlükte

| Doküman | Ne anlatır |
|---|---|
| [uygulama-plani.md](uygulama-plani.md) | **Ne yapılacak, hangi sırayla, ne zaman bitti sayılır.** Uygulamaya başlayan buradan başlar; ilerleme buraya işlenir. |
| [fund-operasyon.md](fund-operasyon.md) | **Sistemi nasıl çalıştıracağın.** Günlük ritim, kurulum, komutlar, bir şey ters gittiğinde ne yapılacağı. |
| [pei-company-lifecycle-tasarim.md](pei-company-lifecycle-tasarim.md) | **Hedeflenen sistemin tasarımı** — portföy karar günlüğü. Yalnız güncel durum; tarihçe yok. |
| [us-market-pipeline.md](us-market-pipeline.md) | **SEC/XBRL veri boru hattı.** Bugün çalışıyor ve yeni tasarım bunu aynen kullanmaya devam ediyor. Değişmedi. |
| [repo-map.md](repo-map.md) | Ne nerede duruyor. |
| [tasarim-oturumlari/](tasarim-oturumlari/2026-08-codex-fon-sistemi/README.md) | Tasarım kararlarının **neden** öyle olduğu — 71 turluk oturum arşivi. Bir kararı sorgulamadan önce buraya bakın. |

## Mevcut kodu anlatanlar

Bunlar **hedef tasarım değildir**; bugün repoda duran kodun ne yaptığını
anlatırlar. `src/adapter/pei_workflow.py` veya `scripts/us_pei_*.py` üzerinde
çalışıyorsanız gereklidirler.

| Doküman | Durum |
|---|---|
| [pei-workflow-orchestrator.md](pei-workflow-orchestrator.md) | Mevcut orkestratörün tasarımı (2026-08-12). Hedef tasarım bunun yerine geçecek. |
| [pei-workflow.md](pei-workflow.md) | Eklenti skill'lerinin ne istediği ve ne ürettiği. Skill gerçekleri hâlâ geçerli; akış ve kayıt bölümleri değil. |

## Yürürlükten kalktı

| Doküman | Yerine ne geçti |
|---|---|
| [pei-akis-diyagram.md](pei-akis-diyagram.md) | Tasarım Bölüm 4-6 (karar akışı, izleme, otomatik araştırma) |
| [pei-recording.md](pei-recording.md) | Tasarım Bölüm 4 ve 7 (`assessment_record`, iki aşamalı adjudication) |

---

## Nereden başlamalı

**Sistemi kullanacaksanız:** `fund-operasyon.md`.

**Uygulamaya başlıyorsanız:** `uygulama-plani.md` → ilk işaretsiz görev.

**Bir tasarım kararını anlamak istiyorsanız:** `pei-company-lifecycle-tasarim.md`
ilgili bölüm → yetmezse `tasarim-oturumlari/` arşivi.

**Mevcut kodu değiştirecekseniz:** `repo-map.md` → `pei-workflow-orchestrator.md`.

**Veri boru hattına dokunacaksanız:** `us-market-pipeline.md`.
