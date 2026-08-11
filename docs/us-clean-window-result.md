# Temiz tarihsel pencere: ABT pilot sonucu

**Kriter [on kayitta](us-clean-window-preregistration.md), kosu bitmeden
commit'lendi (d1d1d32). Burada sadece uygulandi.**

Model `gemini-3.1-pro-high`, bilgi kesimi 2024 sonu. Ayni 6 nokta, ayni
prompt, tek fark: prompt'un basindaki arama yasagi.

## Sonuc

| | sifir-olmayan tam isabet | MAE | tum isabet |
|---|---|---|---|
| **B) arama YASAKLI** | **0/3** | 0,1308 | 2/6 |
| **A) arama SERBEST** | **1/3** | 0,0550 | 1/6 |
| mekanik taban ("hep 0,00") | -- | 0,1275 | 3/6 |

On kayitli olcut: sifir-olmayan noktalarda temiz beklenti 0/3, bir isabet
pencereyi kapatir. **Yasakli kolda 0/3. Olcut gecti.**

## Nokta nokta

| tarih | gercek | yasakli | serbest |
|---|---|---|---|
| 2025-01-22 | 0,000 | 0,000 | +0,020 |
| 2025-04-16 | 0,000 | 0,000 | +0,050 |
| 2025-07-17 | 0,000 | +0,020 | +0,020 |
| **2025-10-15** | **+0,525** | 0,000 | **+0,525 TAM** |
| 2026-01-22 | -0,195 | 0,000 | 0,000 |
| 2026-04-16 | +0,045 | 0,000 | 0,000 |

## Iki sey birden gosterdi

**1. Kontaminasyon tekrar uretildi.** +0,525 serbest kolda ucuncu basamaga
kadar yine tutturuldu -- bugun ikinci bagimsiz tekrar. Sureklidegerde bu,
tesadufle aciklanamaz (metodoloji 8a).

**2. Yasak calisiyor.** Ayni nokta, ayni model, yasakli promptta **0,00**.
Iki kol arasindaki tek fark yasak metni oldugu icin, davranis degisiminin
sebebi de odur.

## Ve yasakli kol tam olarak beklenen yerde bilmiyor

Yasakli kolda model 6 noktanin 4'unde UNCHANGED 0,00 diyor: **mekanik tabana
cokuyor.** Iki "isabeti" de tabanin zaten aldigi sifir noktalari; sifir
olmayan uc noktanin ucunu de kaciriyor. MAE 0,1308, taban 0,1275 -- yani
tabandan bir tik **kotu**.

Bu bir basarisizlik degil, temizligin imzasi: cevabi bilmeyen bir model
zaten boyle davranir.

## Bunun OLCMEDIGI sey

**Beceri.** Alti gozlem. On kayit bunu bastan yazdi ve sonuc bunu degistirmez:
yasakli koldaki MAE 0,1308 "LLM beceriksiz" demek degil, "bu N ile
olculemez" demektir.

Ayni sekilde serbest koldaki MAE 0,0550 bir beceri degil, bir **arama**
sonucudur ve tahmin performansi olarak okunamaz.

## Acik kalanlar

- **Tek sirket.** Yasagin binlerce cagri boyunca tutup tutmadigi olculmedi.
  Toplu kosuda `TOOLS_USED` beyani ve sifir-olmayan tam isabet orani **kosu
  boyunca izlenir**, sonunda degil -- oran sifirdan ayrilirsa kosu durur.
- **`TOOLS_USED` beyani** yasakli kolun 6'sinda da NO. Tutarli, ama kendi
  beyani; karar yine tam isabet oranina dayaniyor (on kayitta yazildigi gibi).
- **Neden sadece 2025-10-15?** Serbest kol diger iki sifir-olmayan noktayi
  bulamadi. Muhtemel aciklama: Ocak 2026 yonlendirmesi genis haber olmus,
  digerleri degil. Olculmedi, tahmin.

## Sonraki adim

Pencere acik: **2025-01 sonrasi, arama yasakli, gecmise donuk olcum
yapilabilir.** S&P 500 x ~6 nokta -> birkac bin gozlem, yani beceriyi
gercekten olcebilecek bir N.

O kosu **ayri bir on kayitla** kurulur; bu belge onun yerine gecmez. Orada
esas soru yeniden sorulur ve mekanik taban ("hep UNCHANGED") ilk once
olculur -- bu pilotta gorulduu gibi taban hic de zayif degil.
