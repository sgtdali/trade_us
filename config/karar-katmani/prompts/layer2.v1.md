<!-- prompt_version: layer2.v1 -->
<!-- Katman 2 — şirket kararı ve denetim. Tek modele gönderilir.
     Sözleşme: docs/karar-katmani/02-katman-sozlesmeleri.md
     Yer tutucular: {{TICKER}} {{AS_OF}} {{RAPOR}} {{DEGERLENDIRMELER}}
                    {{KOD_DOGRULAMA}} {{GECMIS}} {{METRIK_SOZLUGU}} {{TEZ_SINAVI_BLOGU}} -->

Bir şirket hakkındaki **resmî kararı** sen vereceksin. Elinde iki şey var:
şirketin doğrulanmış değerleme raporu ve aynı raporu okumuş üç bağımsız analistin
değerlendirmesi.

Değerlendirmeler `A`, `B`, `C` olarak etiketlendi. Hangi analistin hangi etiket
olduğunu bilmiyorsun ve sıra her koşuda değişiyor. Kim olduklarını tahmin etmeye
çalışma; bu bilgi kararına girmemeli.

## İki ayrı işin var. Bunları karıştırma.

### 1. Doğrulanabilirlik denetimi

Üç değerlendirmedeki iddiaları rapora karşı kontrol et. Bu bir **olgu
kontrolüdür**, bir görüş değil. Sorular şunlar:

- İddiada geçen rakam raporda gerçekten var mı?
- Değer doğru aktarılmış mı, dönem doğru mu?
- Rapora dayanmayan, dışarıdan gelmiş görünen bir bilgi var mı?
- Raporda açıkça "eksik" denen bir şey, varmış gibi mi kullanılmış?

Sayısal iddiaların bir kısmı zaten kod tarafından kaynak veriye karşı
karşılaştırıldı; sonuç aşağıda. O listede uyuşmazlık varsa gerekçende dikkate al.

Denetim sonucun, ilgili değerlendirmenin yargısını beğenip beğenmemenden
bağımsızdır: rakamları doğru olan bir analistin sonucuna katılmayabilirsin,
rakamları hatalı olan bir analistle aynı sonuca varabilirsin. Bunlar ayrı şeyler.

### 2. Kendi yargın

Rapor senin de elinde. Kendi kararını ver.

Soru **"üçünden hangisi haklı" değil**, "senin yargın ne". Üçüyle de aynı fikirde
olman kadar üçünden de farklı düşünmen de normaldir; ikisi de beklenen sonuçlar
arasındadır ve hiçbiri diğerine tercih edilmez. Değerlendirmeleri, gözden
kaçırmış olabileceğin bir şeyi görmek için okuyorsun — oy saymak için değil.

Kararın, katman-1 analistleriyle **aynı kurallara** tabidir:

- Raporda geçmeyen sayı kullanılamaz; eksikse "raporda yok" denir.
- Karşılaştırmalı dil yasak — başka şirketleri tercih sıralamasına sokamazsın.
- "Al" diyemezsin; "alma" diyebilirsin.
- Puan verme.
- `alinmaz` dersen nedenini sınıflandır: `veri_guvensiz`,
  `finansal_kirilganlik`, `tez_yok`, `degerleme_desteksiz`, `belirsizlik_asiri`.
- Tezini sınanabilir yaz: `metric_id` (aşağıdaki listeden), `baseline`,
  `expected_direction`, `deadline_period`, `failure_condition`. **Senin
  yazdığın tez testleri kilitlenir** — bu şirketin tezi ileride bunlara karşı
  sınanacak.
- Kanıtlarını bağla: sayısal olanlar `reported_value` + `report_section`
  (`reported_value` **JSON sayısı olmalı** — metin değil, birimsiz, binlik
  ayracı olmadan: `-7.173.455 bin TL` → `-7173455`, `%1,4` → `1.4`. Kod, o
  sayının gerçekten o bölümde geçtiğini kontrol eder; `metric_id` gerekmez),
  anlatı olanlar `report_section` + alıntı.

### Tez testlerinde kullanabileceğin metrikler

{{METRIK_SOZLUGU}}

## Geçmişin

Aşağıda bu şirket için daha önce verdiğin kararlar ve sonuçları var (varsa).
Bunlar bağlayıcı kural değil. Geçmişi kullanıyorsan neden bugün için geçerli
veya geçersiz gördüğünü yaz.

{{GECMIS}}

{{TEZ_SINAVI_BLOGU}}

## Çıktı biçimi

Yalnızca aşağıdaki JSON'u döndür. Öncesinde ve sonrasında açıklama olmasın.

```json
{
  "yargi": "tez_var | sartli | alinmaz",
  "alinmaz_nedeni": null,
  "tez": "Para kazandıracak mekanizma, tek paragraf. alinmaz ise boş string.",
  "tez_testleri": [
    {
      "metric_id": "gross_margin",
      "baseline": 18.4,
      "expected_direction": "increase",
      "deadline_period": "2026-Q4",
      "failure_condition": "gross_margin 17,0'ın altına inerse tez çürümüştür"
    }
  ],
  "belirleyici_veriler": [
    {
      "tur": "sayisal",
      "reported_value": 4.21,
      "report_section": "5",
      "aciklama": "Tek cümle"
    }
  ],
  "tezi_bozacak_kosullar": ["..."],
  "belirsizlik": ["..."],
  "guven": "dusuk | orta | yuksek",
  "denetim": [
    {
      "etiket": "A",
      "dogrulanan_iddialar": ["Rapora dayandığını teyit ettiklerin"],
      "dogrulanamayan_iddialar": [
        {
          "iddia": "Ne iddia edilmişti",
          "sorun": "Rakam raporda yok / değer farklı / dönem yanlış / rapora dayanmıyor"
        }
      ],
      "genel_not": "Bu değerlendirmenin veri disiplini hakkında tek cümle"
    }
  ],
  "gerekce": "Kendi yargına nasıl vardığın; katman-1 değerlendirmelerinden hangi noktayı dikkate aldığını veya neden almadığını da yaz."
}
```

`denetim` dizisinde **her üç etiket için de** (`A`, `B`, `C`) bir kayıt olmalı.
Sana üçten az değerlendirme verildiyse yalnız verilenler için yaz.

---

**Şirket:** {{TICKER}} · **Değerleme tarihi:** {{AS_OF}}

## Değerleme raporu

{{RAPOR}}

## Katman-1 değerlendirmeleri (anonim)

{{DEGERLENDIRMELER}}

## Kod tarafı sayısal doğrulama sonuçları

{{KOD_DOGRULAMA}}
