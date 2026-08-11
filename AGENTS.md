# trade_us

ABD hisseleri için canlı karar/PEI (Public Equity Investing) akışı: SEC
XBRL'den değerleme motoruna, oradan günlük `pack.json`/CSV üretimine kadar
tek hat. `fundamentaltrading` reposunun ABD hattından 2026-08-11'de ayrıldı.

## Önce buraya bak

- [docs/pei-workflow.md](docs/pei-workflow.md) — PEI adım adım akış, hangi
  skill'e ne veriliyor, kayıt şeması.
- [docs/pei-akis-diyagram.md](docs/pei-akis-diyagram.md) — aynı akışın
  diyagramı, bugün gerçekten çalışan/çalışmayan kısımların durumu.
- [docs/us-market-pipeline.md](docs/us-market-pipeline.md) — SEC pipeline
  tasarımı, veri akışı, karar günlüğü.

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
