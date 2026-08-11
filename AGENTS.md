# trade_us

ABD hisseleri için canlı karar/PEI (Public Equity Investing) akışı: SEC
XBRL'den değerleme motoruna, oradan günlük `pack.json`/CSV üretimine kadar
tek hat. `fundamentaltrading` reposunun ABD hattından 2026-08-11'de ayrıldı.

## Bu repo NE DEĞİL

- **Backtest yok.** Walk-forward simülasyon, dondurulmuş kesim kökleri
  (`ic-2021-v1`, `ic-2024-v1` tarzı), portföy-performans hesabı bilinçli
  olarak taşınmadı. `src/fundamental_pipeline_us/point_in_time.py`,
  backtest.py'nin yalnız canlı akışın kullandığı "belirli bir kesim anını
  dondur" fonksiyonlarını taşıyor — walk-forward'a özel kısım kalmadı.
- **BIST yok.** `src/fundamental_pipeline` altındaki motor, `fundamentaltrading`
  reposundan **kopyalandı**, bağımlı değil. İki repo arasında hiçbir
  bağlantı yok — motorda bir düzeltme yapılırsa iki yere de elle taşınması
  gerekir, otomatik yansımaz.
- **Araştırma/ölçüm yok.** Preregistration/result çiftleri (skor-IC,
  overreaction, mekanik tarama, vb.) ve onları üreten scriptler
  (`us_score_ic_*`, `us_overreaction.py`, `us_mechanical_families.py`,
  `us_guidance_*forecast*` gibi) `fundamentaltrading`'de kaldı — hem
  dondurulmuş backtest köklerine bağımlıydı hem de PEI/canlı akışın parçası
  değil. `docs/` yalnız üç dosya taşıyor: `pei-workflow.md`,
  `pei-akis-diyagram.md`, `us-market-pipeline.md`.

## Önce buraya bak

- [docs/pei-workflow.md](docs/pei-workflow.md) — PEI adım adım akış, hangi
  skill'e ne veriliyor, kayıt şeması.
- [docs/pei-akis-diyagram.md](docs/pei-akis-diyagram.md) — aynı akışın
  diyagramı, bugün gerçekten çalışan/çalışmayan kısımların durumu.
- [docs/us-market-pipeline.md](docs/us-market-pipeline.md) — SEC pipeline
  tasarımı, veri akışı, karar günlüğü.

## Kodlama Ajanı Verimlilik İlkesi

- Sadece görevle ilgili dosyaları oku; `us/raw-cache/`, `us/live/` (git dışı,
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
