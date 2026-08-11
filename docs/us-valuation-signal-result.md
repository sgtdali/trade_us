---
status: final
run: 2026-08-05
preregistration: docs/us-valuation-signal-preregistration.md
preregistration_sha256: 4e4a56b4228e6b73e22a77bd61ffc841fd36ab2b (kayit anindaki blob)
verdict: hipotez elendi
---

# Sonuç — ABD Değerleme Sinyali, 3 Aylık Ufuk

Bu belge [ön kaydın](us-valuation-signal-preregistration.md) sonucudur. Ön kayıt
veriye bakılmadan yazılmış ve commit edilmiştir (`64127c7`); dört değişikliğin
dördü de yalnız veri erişilebilirliğinden kaynaklanmış ve **hiçbir getiri veya
sinyal incelenmeden önce** yapılmıştır. Hipotez, birincil sinyal, N, ufuk ve
başarı ölçütü hiçbir noktada değiştirilmemiştir.

## Hüküm: hipotez elendi

> Emsallerine göre düşük değerlemeli şirketler, 3 aylık ufukta yüksek değerlemeli
> olanlardan daha iyi getiri sağlar.

Ön kayıttaki iki koşul da sağlanmadı.

| Ölçüt | Eşik | Sonuç | |
|---|---|---|---|
| Üst-8 eksi alt-8 farkı pozitif | > 0 | **−117,39 puan** | ✗ |
| Yılların çoğunda pozitif | ≥ %60 | **3/7 = %43** | ✗ |

## Birincil sinyal — `val.method.earnings_yield.reported_parent`

```
ust-8 (en yuksek kazanc getirisi = en ucuz)    +96,04%
alt-8 (en dusuk kazanc getirisi = en pahali)  +213,43%
fark                                          -117,39 puan
t                                                -0,89
```

Yön açıktır: en ucuz sekiz şirket, en pahalı sekiz şirketin belirgin biçimde
gerisinde kalmıştır. Bu, hipotezin öngördüğünün tersidir.

Yıl kırılımı (üst-8 eksi alt-8, çeyrek toplamı):

| Yıl | Fark | Çeyrek |
|---|---:|---:|
| 2018 | −12,76% | 3 |
| 2019 | +0,46% | 4 |
| 2020 | −0,66% | 4 |
| 2021 | −16,74% | 4 |
| 2022 | +5,42% | 4 |
| 2023 | −21,86% | 4 |
| 2024 | +3,73% | 3 |

Sonuç tek bir rejime yığılmamıştır: dört yıl negatif, üç yıl hafif pozitif.

## İkincil sinyaller — ön kayıt gereği tamamı raporlanır

| Sinyal | Üst-8 | Alt-8 | Fark | t | Pozitif yıl |
|---|---:|---:|---:|---:|---:|
| `fcf_yield.standard_equity` | +52,92% | +124,73% | −71,81 | −1,30 | 2/6 |
| `price_to_book.parent_equity` | +139,87% | +128,54% | +11,33 | +0,27 | 5/7 |
| `ev_to_ebit.core` | +68,87% | +114,66% | −45,79 | −0,77 | 3/7 |
| `current_ratio` | +163,61% | +111,98% | +51,64 | +0,62 | 3/7 |

Hiçbiri anlamlı değildir. `price_to_book` yedi yılın beşinde pozitiftir fakat
farkı küçük ve t = +0,27'dir. İçlerinden biri birincilden iyi çıksaydı bile bu,
hipotezin doğrulandığı anlamına gelmezdi — ön kayıt bunu açıkça yasaklar.

## `current_ratio`: örnek-dışı testte ayakta kalmadı

Bu metrik, 2025-2026 verisinde 33 test taranarak seçilmiş ve orada 3 aylık ufukta
IC +0,307 vermişti; 15 ayın ilk yarısında seçilip ikinci yarısında denendiğinde de
+3,73 puan taşımıştı. Dokunulmamış 2018-2024 verisinde farkı +51,64 puan ama
t = +0,62 ve yılların yalnız 3/7'sinde pozitif.

Ön kaydın yazılma sebebi tam olarak buydu. Örnek-içi bir tarama, devamlılık testini
geçmiş görünse bile, gerçek örnek-dışı veride ayakta kalmayabiliyor.

## Kapsam

- **27 çeyrek**, 2018-Q2 – 2024-Q4, 23 şirket, her çeyrekte tam kesit.
- 2016-Q1 – 2018-Q1 arası 9 çeyrek üretilemedi. Bu bir kod eksiği değildir:
  evrendeki bazı şirketlerin (özellikle CELH) o dönemdeki filing'lerinde XBRL
  paketi hiç yoktur, çünkü küçük raporlayan şirketler için XBRL o yıllarda zorunlu
  değildi. On dört adaptör düzeltmesinden sonra bu dokuz çeyrek değişmedi
  (bkz. ön kayıt, Değişiklik 4).

## Sınırlar

- 23 şirket tek sektörde ve birbirine yüksek korele; 27 çeyrek nominal gözlem
  verse de etkin bağımsız gözlem sayısı belirgin biçimde daha azdır.
- Evren bugünkü hayatta kalanlardan oluşur (survivorship).
- Beş sinyal test edilmiştir; çoklu karşılaştırma nedeniyle tek bir t>2 sonucu
  keşif sayılmazdı.
- 2018-2024, değer yatırımının geniş çapta geride kaldığı bilinen bir dönemdir.
  Sonuç bu rejimle tutarlıdır ve başka dönemlere veya evrenlere genellenmez.
- Bu test bir strateji üretmemiştir; bir hipotezi elemiştir.

## Sonuç ve karar

Ön kaydın hükmü uygulanır: **hipotez elenmiştir ve LLM karar katmanı bu tez
üzerinde daha fazla çalıştırılmayacaktır.**

Bu, daha önce ölçülenlerle tutarlıdır: 15 aylık walk-forward koşusunda LLM karar
katmanının bir aylık ufukta sinyali bulunamamıştı (`alinmaz` eksi `non-alinmaz`
farkı aylık +%0,01, t = +0,01) ve portföy seçimi kendi havuzundan rastgele
seçmekten ayırt edilememişti (58,9. yüzdelik). Şimdi bu zincirin en alt halkası —
raporun dayandığı değerleme çarpanlarının kendisi — de aynı ufukta sıralama gücü
göstermemiştir.

Yeni bir tez ayrı bir ön kayıtla açılır. Bu belge değiştirilmez.
