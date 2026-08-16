# trade_us

ABD hisseleri için canlı karar/PEI (Public Equity Investing) akışı: SEC
XBRL'den değerleme motoruna, oradan günlük `pack.json`/CSV üretimine kadar
tek hat. `fundamentaltrading` reposunun ABD hattından 2026-08-11'de ayrıldı.

## Önce buraya bak

- [docs/README.md](docs/README.md) — **hangi doküman yürürlükte, hangisi
  mevcut kodu anlatıyor, hangisi kalktı.** Diğer her şeyden önce bu.
- [docs/uygulama-plani.md](docs/uygulama-plani.md) — yapılacak işler, sıra ve
  bitmiş sayılma koşulları. Uygulamaya başlıyorsanız buradan.
- [docs/pei-company-lifecycle-tasarim.md](docs/pei-company-lifecycle-tasarim.md)
  — hedeflenen sistemin (portföy karar günlüğü) tasarımı.
- [docs/us-market-pipeline.md](docs/us-market-pipeline.md) — SEC pipeline
  tasarımı, veri akışı. Değişmedi, yeni sistem de bunu kullanıyor.

Repoda **iki ayrı sistem** var: bugün çalışan PEI orkestratörü ve yanına
kurulmakta olan portföy karar günlüğü. Hangi dokümanın hangisini anlattığını
karıştırmayın; `docs/README.md` bunu ayırıyor.

## Kodlama Ajanı Verimlilik İlkesi

- Sadece görevle ilgili dosyaları oku; `raw-cache/`, `live/` (git dışı,
  regenerable) rekürsif taranmaz.
- Hedefli test çalıştır (`pytest -q tests/us/...`); tüm suite'i her
  seferinde koşma.
- Gereksiz belge üretme: her küçük görev için ayrı plan/tasarım dosyası
  açma. Sistem başına en fazla bir kanonik spesifikasyon.
- Çalıştırmadığın testleri geçmiş/başarılı olarak beyan etme.

## Ortam

```bash
export SEC_USER_AGENT="trade-us-local/0.1 your-email@example.com"
pip install -e ".[dev]"
python scripts/us_pei_pack.py --for idea
```
