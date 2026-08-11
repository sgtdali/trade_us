# Emsale gore carpan iskontosu ileri getiriyi siraliyor mu? (on kayit)

**Yazildi 2026-08-09, sonuclar gorulmeden. Kosu bu belge commit'lendikten
sonra baslar.**

## Nereden cikti

ChatGPT Public Equity Investing eklentisinin ADBE memosu (`raw/chat-exports/
chatgpt_08.08.2026_2.md`) tum yukari yonu tek bir varsayimdan turetiyor:

```
fiyat 265,21 / NTM EPS 25,92 = 10,2x     <- gozlem
base: EPS ~26 x 12,5x = 326              <- +%23
```

EPS neredeyse hic degismiyor; +%23'un tamami carpanin **12,5x olmasi gerektigi**
varsayimindan geliyor. Memo bunu kendisi de yaziyor: bull senaryosundaki degerin
**%85'i multiple expansion.** 12,5x ise emsal medyanindan (ADSK/INTU/CRM, 13,8x)
turetilmis.

Bu, [olcum-metodolojisi.md](olcum-metodolojisi.md) 0j-3'teki tanimlama problemi:
`fiyat = carpan x kazanc`, bir denklem iki bilinmeyen. Emsallerin carpani da
sadece onlarin fiyati. Argumanin ozu "Adobe'nin fiyati yanlis cunku
baskalarinin fiyati farkli."

**Test edilecek sey bu adimin kendisi:** emsale gore ucuz olmak, ileri getiriyi
siraliyor mu?

## Daha once ne test edildi, bu ondan nasil farkli

`docs/us-valuation-signal-preregistration.md` degerleme carpanlarini
**mutlak kesitte** test etti (60 sirket birlikte siralandi). Bu kosu farkli:
carpan **kendi sektor emsal grubu icinde** siralaniyor.

Fark onemsiz degil. Evren staples/saglik/sanayi/teknoloji karisimi; mutlak
siralamayi sektor kompozisyonu domine eder (staples surekli "ucuz", teknoloji
surekli "pahali" gorunur). Emsale gore siralama tam da comps-valuation'in
yaptigi seydir.

Mutlak varyant burada **kontrol olarak birlikte kosulur**, cunku iki varyantin
farki bu kosunun esas sorusudur.

## Veri

Iki donmus point-in-time kosu, ayni 60 sirketlik evren:

| kosu | tam kesit | aralik |
|---|---|---|
| `us/backtests/ic-2021-v1` | 17 | 2021-09 .. 2024-04 |
| `us/backtests/ic-2024-v1` | 15 | 2024-10 .. 2026-08 |

Kesitler bitisik ay degil (aralar var), dolayisiyla **1 aylik ufukta ortusme
yok.**

**Kapsam siniri (onceden kontrol edildi):** `ic-2024-v1`'in son kesiti
2026-08-04, fiyat kapsami 2026-08-05'te bitiyor -> ileri getirisi yok, **duser.**
Daha uzun ufuklarda sondan daha fazla kesit duser. Her ufuk icin kac kesit ve
kac sirket-gozlem kullanildigi sonucta **sayiyla** raporlanir; sessizce
doldurulmaz. (Bu proje bir kez tam bu hatayi yapti: kapsam disi olaylar ilk
seansa cipalanmisti.)

Emsal gruplari `us/config/valuation/comparison/peer-universes/`:
staples 24, saglik 12, sanayi 12, teknoloji 12 = 60.

## Sinyaller

Birincil: `val.method.earnings_yield.reported_parent` (kapsam ~59/60).

Ikincil: `fcf_yield.standard_equity`, `price_to_book.parent_equity`,
`ev_to_ebit.core`.

**Isaret ispati (metodoloji 0b):** kazanc getirisi ve FCF getirisi icin
**yuksek = ucuz**; PD/DD ve FD/FVOK icin **dusuk = ucuz**. Siralama buna gore
cevrilir ve kosu ciktisinda her sinyal icin yon acikca yazdirilir.

Her sinyal iki varyantta:

- **S (emsale gore):** carpan kendi sektor grubu icinde yuzdelik siraya cevrilir
- **M (mutlak):** 60'in tamami icinde yuzdelik siraya cevrilir

## Sonuc degiskeni

Islem tarihinden itibaren ufuk boyunca duzeltilmis acilis fiyati getirisi,
**kesitsel olarak ortalamadan arindirilmis** (esit agirlikli evren getirisi
cikarilir).

Ufuk: **birincil 1 ay.** Ikincil 3 ve 6 ay -- bunlarda kesitler ortusuyor,
t degeri sisebilir ve bu sonucta acikca yazilir.

## Istatistik

Kesit basina Spearman rank IC. Ortalama IC.

**t, kumelenmis permutasyon null'unun MERKEZINE gore** (metodoloji 0d-2).
Karistirma birimi: kesit ici ticker etiketleri, 2000 cekilis. Null sifirda
merkezlenmis varsayilmaz -- bu projede BIST taramasinda tam bu yuzden yanlis
bir t=5,30 uretilmisti.

**Aile duzeltmesi:** 4 carpan x 2 varyant = 8 test. Aile istatistigi
**max |t|** (max |ortalama IC| DEGIL -- o en gurultulu sinyale kalibre olur).

## Pozitif kontrol (metodoloji 5, atlanamaz)

Sinyal olarak **gerceklesen ileri getirinin kendisi** verilir. IC ~ +1
cikmalidir. Cikmazsa tarih hizalamasi, isaret veya siralama bozuktur ve
**kosunun geri kalani okunmaz.**

## Bu testin OLCEMEYECEGI sey (once bu yaziliyor)

31 kesit. sd(IC) ~ 0,14 varsayimiyla SE ~ 0,025; t=2 icin saptanabilir en kucuk
etki **|IC| ~ 0,05**.

Gercek degerleme sinyallerinin literaturdeki IC'si tipik olarak 0,02-0,05.

**Yani bu kosu BUYUK bir etkiyi eleyebilir, kucugunu eleyemez.** Null cikarsa
sonuc "emsale gore ucuzluk ise yaramiyor" degil, **"bu N ile 0,05'ten kucuk bir
etki ayirt edilemez"** diye yazilacaktir. Ust sinir (ortalama + 1,96 x SE)
rapor edilir.

## On kayitli olcut

**Basari:** emsale gore kazanc getirisi (birincil) ortalama IC'si pozitif ve
aile duzeltmesinden sonra %5'te anlamli.

**Esas karsilastirma:** S varyanti M varyantindan **belirgin daha iyi mi?**
Cunku comps-valuation'in tum iddiasi sektor-notrlestirmenin bilgi kattigi.
Ikisi ayni cikarsa sektor-notrlestirme bos is demektir.

**Yorum siniri:** anlamli cikan bir IC bile **para kazandirmayabilir** -- bu
projede tahmin edilebilir kismin fiyatlanmis oldugu iki bagimsiz olcumde
gorulduu. IC pozitif cikarsa bir sonraki adim getiri degil, **islem maliyeti
sonrasi ust-alt sepet farki** olur; bu kosu onu icermiyor.
