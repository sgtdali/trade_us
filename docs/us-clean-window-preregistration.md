# Temiz tarihsel pencere: ABT pilotu (on kayit)

**Yazildi 2026-08-07, sonuclar gorulmeden.** Kosu bu belge commit'lendikten
sonra okunacak.

## Soru

`gemini-3.1-pro-high`'in bilgi kesimi 2024 sonunda. Arama engellenirse
2025-01 sonrasi onun icin **temiz bir tarihsel pencere** olur mu -- yani
ileri yonlu beklemeden gecmise donuk olcum yapabilir miyiz?

Bu soru bugun acildi: `--dangerously-skip-permissions` aramayi sessizce
onayliyordu ve daha once "ezber" sandigim tam isabet bir web aramasiydi
(bkz. [us-llm-contamination-finding.md](us-llm-contamination-finding.md)
geri cekme bolumu). Ayni belgede kosul B, aramanin prompt'la
engellenebildigini ve engellenince modelin **gercekten bilmedigini** gosterdi.

## Bu pilotun OLCEMEYECEGI sey

**Beceri.** ABT'nin 2025-01 sonrasi 6 tahmin noktasi var. Alti gozlem hicbir
IC veya isabet oranini anlamli kilmaz. Guc analizi (metodoloji 6f) bunun icin
yuzlerce kesit ister.

Bu pilot **tek bir sey** icin: arama engellendiginde **kontaminasyon kayboluyor
mu.** Cevap evetse toplu kosu anlamli hale gelir; hayirsa pencere yoktur ve
toplu kosu bosuna olur.

## Veri

ABT tam yil duzeltilmis EPS yonlendirme orta noktalari ve **gerceklesen**
degisim:

| tahmin tarihi | o anki orta nokta | sonraki | gerceklesen degisim |
|---|---|---|---|
| 2025-01-22 | 5,150 | 5,150 | **0,000** |
| 2025-04-16 | 5,150 | 5,150 | **0,000** |
| 2025-07-17 | 5,150 | 5,150 | **0,000** |
| 2025-10-15 | 5,150 | 5,675 | **+0,525** |
| 2026-01-22 | 5,675 | 5,480 | **-0,195** |
| 2026-04-16 | 5,480 | 5,525 | **+0,045** |

## Mekanik taban (once olculur -- metodoloji 2)

**"Her zaman UNCHANGED 0,00"** kuralı:

- tam isabet: **3/6**
- MAE: (0+0+0+0,525+0,195+0,045)/6 = **0,1275**

LLM bu ikisini gecemezse, ne cikarsa ciksin, en aptal kuraldan iyi degildir.

## On kayitli kriter

**Birincil (kontaminasyon detektoru).** Tam isabet, **yalnizca sifir olmayan
uc noktada** (+0,525 / -0,195 / +0,045). Sifir noktalarinda isabet bilgi
tasimaz -- taban zaten oraya 0,00 diyor.

- `|hata| < 0,005` = tam isabet sayilir.
- Temiz bir modelde beklenti **0/3**. Bu degerler surekli; ucunden birine bile
  virgul sonrasi tam isabet, ezber degil **bakma** isaretidir (metodoloji 8a).
- **1/3 veya daha fazlasi → pencere YOKTUR**, toplu kosu yapilmaz.

**Ikincil (kiyas).** Arama serbest kosu ayni 6 noktada kosuluyor. Beklenti:
serbest kosuda sifir-olmayan noktalarda tam isabet **var**, yasakli kosuda
**yok.** Iki kosul arasindaki bu fark, aramanin katkisini dogrudan olcer ve
ayni zamanda yasagin **calistiginin** kanitidir.

**Yasak calismiyorsa.** Yasakli kosuda da tam isabet cikarsa iki ihtimal var:
ya prompt yasagi tutmuyor (model yine ariyor), ya da gercekten ezber. Ikisini
ayirmak icin modelin `TOOLS_USED` beyani ve cevabin icerigi okunur -- ama bu
durumda **her iki ihtimalde de** pencere kullanilamaz, cunku ayrimi guvenilir
sekilde yapamayiz.

## Beyan alanının sinirinin farkindayiz

Yasakli kosuda modelden `TOOLS_USED YES/NO` beyani isteniyor. Bu **kendi
beyani** ve zayif bir kanittir; dogrudan sorguda dogru cevap verdigi
gorulduu icin sifir degeri yok, ama tek basina delil sayilmayacak. Karar
her zaman **tam isabet oranina** dayanir.

## Sonrasi

Kriter gecerse: pencere acik demektir ve toplu kosu (S&P 500, 2025-01 sonrasi,
sirket basina 5-6 nokta -> birkac bin gozlem) anlamli olur. O kosu **ayri bir
on kayitla** kurulur; bu belge onun yerine gecmez.

Kriter gecmezse: ileri yonlu defter tek yol olarak kalir ve Ekim'de puanlanir.
