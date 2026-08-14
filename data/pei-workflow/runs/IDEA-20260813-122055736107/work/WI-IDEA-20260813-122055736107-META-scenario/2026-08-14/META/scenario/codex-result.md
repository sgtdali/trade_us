# META — Senaryo ve Sensitivite Notu

**PM duruşu: 28 Ekim 2026’daki tahmini Q3 sonuçlarına kadar `wait for proof`.** Mevcut fiyat ($594.97; 13 Ağustos) FY+1 EPS consensus’ünü ($33.948) yaklaşık **17.53x** ile fiyatlıyor. Bu seviyede baz EPS’ye göre anlamlı bir marj yok; ortalama hedef fiyat olan $754.14’e ulaşmak için ya EPS’nin **%26.8** artarak $43.03’e çıkması ya da çarpanın **22.22x**’e yeniden değerlenmesi gerekir.

Girdi duruşu: fiyat ve consensus, pack’ten türetilmiş kaynak-veridir (13 Ağustos 2026). Tablolardaki matematik türetilmiştir; 15x/20x çarpan bantları analist varsayımıdır. Bu nedenle çıktı **screen-grade**, model-validasyonlu değildir. Olasılık-ağırlıklı değer kullanılmadı.

## İlk kırılacak sürücü

**EPS ve FCF dönüşümü**: gelir değil, AI capex/masrafın marj ve nakit akışına geçişi. Q2’de gelir %28 büyürken masraflar %55 arttı; şirket Q3 için $61–64 milyar gelir, 2026 için $165–169 milyar masraf ve $130–145 milyar capex öngördü. Q2 serbest nakit akışı yalnızca $784 milyondu. [Meta Q2 sonuçları](https://investor.atmeta.com/investor-news/press-release-details/2026/Meta-Reports-Second-Quarter-2026-Results/default.aspx)

Pack’te FY+1 EPS son 30 günde **%2.9**, FY0 EPS ise **%3.2** aşağı revize edildi. Q3 gelir rehberi orta noktası ($62.5 milyar), pack’teki $63.31 milyar çeyreklik consensusun yaklaşık **%1.3** altında. Dolayısıyla yukarı yönün ana kaynağı önce **tahmin revizyonu**, ancak $679 üstü senaryo için ayrıca **çarpan genişlemesi** gerekir.

Pack’in 2026-H1 FCF’i $14.98 milyar iken Meta’nın Q2 açıklaması $13.17 milyar bildiriyor; bu çelişki nedeniyle FCF üzerinden değerleme hedefi üretmedim. [Meta açıklaması](https://investor.atmeta.com/investor-news/press-release-details/2026/Meta-Reports-Second-Quarter-2026-Results/default.aspx)

## `valuation_sensitivity`

FY+1 EPS $33.948 sabit tutulduğunda:

| İleri F/K | İma edilen fiyat | $594.97’ye göre |
|---:|---:|---:|
| 15.0x | $509.22 | -14.4% |
| 17.53x | $594.97 | 0.0% |
| 20.0x | $678.96 | +14.1% |
| 22.22x | $754.14 | +26.8% |

$754.14 ortalama hedef, bugünkü FY+1 EPS üzerinde **22.22x** gerektiriyor. Bu, mevcut ileri çarpandan yaklaşık **%26.7** rerating demek; tek başına “iyi gelir büyümesi” bunu yeterince desteklemez. Marj/FCF dönüşümünün kanıtlanması gerekir.

EBITDA ve güvenilir EV/EBITDA paydası pack’te mevcut değildir; bu nedenle EV/EBITDA sensitivitesi üretilmedi. Net nakit $6.60 milyar, likiditeyi ilk risk olmaktan çıkarıyor; ancak revolver ve covenant verisi bulunmadığından `equity_liquidity_downside` kullanılmadı. Segment KPI verisi de olmadığı için `kpi_driver_sensitivity` tahmin edilmedi.

## `eps_revision_sensitivity`

İma edilen fiyat; FY+1 EPS revizyonu ve F/K değişiminin birlikte etkisi:

| FY+1 EPS değişimi | 15.0x F/K | 17.53x F/K | 20.0x F/K |
|---:|---:|---:|---:|
| -10% | $458.30 (-23.0%) | $535.47 (-10.0%) | $611.06 (+2.7%) |
| -5% | $483.76 (-18.7%) | $565.22 (-5.0%) | $645.01 (+8.4%) |
| Baz | $509.22 (-14.4%) | $594.97 (0.0%) | $678.96 (+14.1%) |
| +5% | $534.68 (-10.1%) | $624.72 (+5.0%) | $712.91 (+19.8%) |
| +10% | $560.14 (-5.9%) | $654.47 (+10.0%) | $746.86 (+25.5%) |

Bu tablo, yukarı yönün yalnızca EPS artışıyla değil, en azından kısmi çarpan toparlanmasıyla anlamlılaştığını gösteriyor. Buna karşılık 17.53x çarpan korunursa %10 EPS kesintisi fiyatı yaklaşık **$535**’e indirir.

## Aksiyon kuralları

| Tetikleyici | Tarih / kaynak | PM aksiyonu |
|---|---|---|
| Q3 geliri en az $62.5 milyar; 2026 capex üst sınırı $145 milyarı aşmıyor; FY+1 EPS $33.95’in altına yeniden çekilmiyor | Tahmini 28 Ekim 2026 sonuçları; IR ile tarih teyit edilmeli | `Add` |
| FY+1 EPS $35.65’e (+%5) çıkar ve 17.53x korunur; ima edilen değer $624.72 | Q3 sonrası consensus güncellemesi | `Press` |
| Fiyat $679’a ulaşır, fakat FY+1 EPS hâlâ $33.95 veya altında kalır | Günlük fiyat ve consensus; en geç aylık yeniden dengeleme | `Trim` — getiri çarpan genişlemesine dayanır |
| FY+1 EPS $30.55 veya altına iner (-%10); 17.53x’te ima edilen değer $535.47 | Q3 sonrası veya sonraki consensus snapshot | `Exit / re-underwrite` |
| 2026 capex rehberi $145 milyarın üzerine çıkar ya da Q3 gelir rehberi orta noktası $61 milyarın altına iner | Şirket sonuçları / IR | `Exit / re-underwrite` |
| Hedge | Sürekli | Mandat yalnızca long-only common equity olduğundan `hedge` uygulanamaz |

Ana doğrulama penceresi Q3 sonuçlarıdır. Meta’nın rehberlik, AI yatırım harcaması ve zayıf kısa vadeli FCF tartışması piyasanın merkezinde kalıyor; bu nedenle fiyat yükselişi kanıtlanmış EPS/FCF dönüşümü olmadan izlenmeli, peşinden gidilmemeli. [AP’nin Q2 piyasa okuması](https://apnews.com/article/meta-earnings-q2-facebook-profit-revenue-ai-bcbc62dde6d2cac724e3b3385fcabeab)