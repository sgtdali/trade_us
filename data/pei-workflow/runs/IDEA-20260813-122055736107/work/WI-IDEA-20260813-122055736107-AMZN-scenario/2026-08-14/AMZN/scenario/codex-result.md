## AMZN — Senaryo ve Duyarlılık (14 Ağustos 2026)

**PM duruşu: Bekle / kanıt ara.** Mevcut $265,13 fiyatı, +1Y konsensüs EPS’i $10,44 üzerinden yaklaşık **25,4x ileri F/K** ima ediyor. Bu nedenle yukarı yönlü getiri, yalnızca AWS/AI büyümesinin sürmesinden değil, bunun EPS revizyonuna dönüşmesinden veya çarpanın genişlemesinden gelmeli.

Paket sayısal girdileri birincil kaynaktır: [pack.json](C:\Users\tvural.REPKON\Desktop\ProjelerY\trade_us\data\pei-workflow\runs\IDEA-20260813-122055736107\work\WI-IDEA-20260813-122055736107-AMZN-scenario\2026-08-14\AMZN\scenario\pack.json). Fiyat/çarpan ve konsensüs as-of tarihi **13 Ağustos 2026**’dır. Aşağıdaki hesaplar kaynak-türetilmiş girdilerden mekanik olarak üretilmiştir; seçilen senaryo çarpanları analist varsayımıdır ve çalışma **model-doğrulanmış değildir**.

### Ana yatırım hükmü

- Pozitif taraf: AWS Q2’de %36,7 büyüdü; AI ve çip işlerinin her biri $25 milyarın üzerinde yıllıklaştırılmış gelir hızına ulaştı. Yönetim, AWS talebinin kapasiteyi aştığını vurguladı. [Amazon Q2 sonuçları](https://www.aboutamazon.com/news/company-news/amazon-earnings-q2-2026-report)
- İlk kırılacak sürücü: **serbest nakit akımı / nakit dönüşümü.** Paket YTD FCF’yi -$27,0 milyar, FCF marjını -%7,1 ve capex/revenue’yu %25,8 gösteriyor. Q2 sonrası piyasa tartışması da AI altyapı yatırımının FCF’ye baskısı etrafında; yönetim 2026 capex planını $220 milyara çıkardı. [AP haberi](https://apnews.com/article/amazon-second-quarter-earnings-cloud-b4ce02b4666a35b8975823c5c22072ee)
- Net gelir kalitesi riski: Paket, net kârın faaliyet kârının %81 üzerinde olduğunu ve bunun esasen Anthropic yatırımından gelen faaliyet dışı gelire bağlı olduğunu işaretliyor. Bu nedenle raporlanan **21,1x P/E** ana değerleme çıpası değildir.
- Yukarı yön: Konsensüs ortalama hedefi $325,19 (+%22,7). Mevcut 25,4x ileri F/K korunursa bunun için +1Y EPS’in **$12,80’a**, yani mevcut $10,44’e göre **%22,7 yukarı revize** olması gerekir. EPS sabit kalırsa gereken çarpan **31,1x**’tir. Dolayısıyla yukarı potansiyel bugün itibarıyla hem revizyon hem de yeniden değerleme olmadan tam anlamıyla temellendirilemez.

### `valuation_sensitivity`

Paketin EV/EBITDA verisi `unavailable` olduğundan EBITDA ikamesi yapılmadı. Bunun yerine paket içindeki **lease-excl. EV / reported operating income = 31,08x** kullanıldı; net borç $9,56 milyar ve türetilmiş hisse adedi ile mekanik hisse değeri hesaplandı.

| Faaliyet kârı değişimi | 26,0x EV/OI | 31,08x EV/OI | 36,0x EV/OI |
|---|---:|---:|---:|
| -%10 | $199 (-%24,8) | $239 (-%10,0) | $276 (+%4,3) |
| Baz | $222 (-%16,4) | **$265** | $307 (+%15,9) |
| +%10 | $244 (-%8,0) | $292 (+%10,0) | $338 (+%27,5) |

Buradaki asimetrinin mesajı net: Faaliyet kârı %10 büyüse bile mevcut çarpan korunursa değer $292’ye çıkar; $325+ bölgesi için daha güçlü kâr revizyonu veya 36x’e yaklaşan çarpan gerekir.

### `eps_revision_sensitivity`

Baz ileri EPS $10,437; baz ileri F/K 25,4x. Satırlar EPS revizyonunu, sütunlar çarpan varsayımını gösterir.

| +1Y EPS değişimi | 22,0x | 25,4x | 28,0x |
|---|---:|---:|---:|
| -%10 | $207 (-%22,1) | $239 (-%10,0) | $263 (-%0,8) |
| Baz | $230 (-%13,4) | **$265** | $292 (+%10,2) |
| +%10 | $253 (-%4,7) | $292 (+%10,0) | $321 (+%21,2) |

Konsensüs +1Y EPS aralığı ($8,69–$15,04) sabit 25,4x ile sırasıyla **$221–$382** üretir. Bu genişlik, hedefin tek başına “underwriteable” olmadığını gösterir; olasılık ağırlıklı değer hesaplanmadı çünkü bağımsız olasılık/hurdle girdisi yok.

### Tetikleyiciler ve aksiyon kuralları

| Tetikleyici | Eşik / tarih | PM aksiyonu |
|---|---|---|
| Q3 sonuçları | Tahmini, henüz IR tarafından doğrulanmamış tarih: **29 Ekim 2026**; gelir konsensüsü $201,76 milyar | **Bekle / kanıt ara.** Yeni pozisyon ancak sonuç ve ileri EPS revizyonu birlikte teyit ederse değerlendirilmeli. |
| Değerleme marjı | Fiyat **≤$220**, +1Y EPS konsensüsü **≥$10,44** | **Ekle.** İleri F/K yaklaşık 21,1x’e iner; baz EPS korunuyorsa risk/getiri iyileşir. |
| Revizyon teyidi | +1Y EPS **>$10,44** ve fiyat **≤$265** | **Ekle / bas.** Fiyat, revizyonu henüz yansıtmıyorsa yukarı yön daha temellidir. |
| Hedefe koşu | Fiyat **≥$325** fakat +1Y EPS **<$12,80** | **Kırp.** Getiri, EPS yerine çarpan genişlemesine dayanıyor olur. |
| Bozulma | +1Y EPS **≤$8,69** veya 22x ile değerlenen düşük-EPS durumunda fiyat **≈$191** | **Yeniden değerlendir / çık.** Nakit dönüşümü ve yatırım geri dönüşü varsayımı yeniden kurulmalıdır. |

Mandat yalnızca uzun ortaklık sermayesi, opsiyonsuz ve short’suz olduğu için türev hedge önerilmiyor; risk aksiyonu **kırpma veya nakitte bekleme** olmalı.

Ek olay notu: Globalstar için Amazon’un imzaladığı birleşme anlaşması düzenleyici onaylara tabi. Bu senaryoya değer etkisi dahil edilmedi; işlem koşulları ve kapanış etkisi ayrı olay analizi gerektirir. [SEC 8-K / Rule 425](https://www.sec.gov/Archives/edgar/data/1018724/000110465926042891/tm2611746d2_425.htm)