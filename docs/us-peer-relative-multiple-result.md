# Emsale gore carpan iskontosu: sonuc

**Kriter [on kayitta](us-peer-relative-multiple-preregistration.md), kosu
baslamadan commit'lendi (bc92154). Burada sadece uygulandi.**

60 sirket, 31 kesit (1 ay), 2021-09 .. 2026-06. LLM yok.

## Pozitif kontrol

Gerceklesen ileri getiri sinyal olarak verildiginde **ortalama IC +1,0000**,
uc ufkun ucunde de. Tarih hizalamasi, isaret ve siralama saglam; sonuclar
okunabilir.

## Birincil sonuc (kazanc getirisi, emsale gore, 1 ay)

| | deger |
|---|---|
| ortalama IC | **-0,0125** |
| null merkezi | -0,0005 |
| t (null merkezine gore) | **-0,49** |
| %95 ust sinir | **+0,0373** |

Aile istatistigi **max\|t\| = 1,43**, 8 test icin gereken ~2,7'nin cok altinda.
Uc ufkun hicbirinde hicbir sinyal esigi gecmiyor (3 ayda 2,53'e cikiyor ama
**isaret negatif** ve o ufukta kesitler ortusuyor -- on kayit bunu bastan
isaretlemisti).

## Esas soru: sektor-notrlestirme bilgi katiyor mu?

comps-valuation'in tum iddiasi bu adim. S (emsal ici) eksi M (mutlak):

| sinyal | 1 ay | 3 ay | 6 ay |
|---|---|---|---|
| kazanc getirisi | -0,009 | -0,017 | -0,027 |
| FCF getirisi | +0,007 | +0,011 | +0,012 |
| PD/DD | -0,004 | +0,004 | +0,007 |
| FD/FVOK | -0,015 | -0,029 | -0,056 |

Farklar kucuk ve **isareti tutarsiz**. Iki sinyalde S sistematik olarak daha
kotu, birinde daha iyi, birinde karisik. Sektor-notrlestirmenin bilgi kattigina
dair bir iz yok.

Yani: **emsale gore iskonto, mutlak carpandan fazla bir sey soylemiyor** -- ve
mutlak carpan zaten [daha once](us-valuation-signal-preregistration.md) null
cikmisti.

## Bu sonucun SOYLEMEDIGI sey

**"Emsale gore ucuzluk ise yaramaz" demiyor.** On kayitta yazildigi gibi 31
kesitle saptanabilir en kucuk etki |IC| ~ 0,05 ve gercek degerleme
sinyallerinin bandi 0,02-0,05. Birincil sinyalin ust siniri **+0,037**.

Dogru cumle: **0,04'un uzerinde bir etki bu veride yok; altini bu N ayirt
edemez.**

Ayrica ADBE hakkinda bir sey soylemiyor. Olculen sey tek bir sirket degil,
"emsalinden ucuz olan daha cok kazandirir" adiminin **genel** olarak veride
gorunup gorunmedigi.

## Ama memo icin soyledigi bir sey var

ADBE memosunun +%23 base yukarisi tamamen carpanin 12,5x olmasi gerektigi
varsayimindan geliyordu ve 12,5x emsal medyanindan turetilmisti. O adim -- emsal
medyanina yakinsama -- bu veride olculebilir bir getiri farki uretmiyor.

Memonun **falsifiable** kismi (ARR %9,5/%10,5, Firefly QoQ, conversion
esikleri) bu testin kapsaminda degil ve gecerliligini koruyor. Kirilan sey o
esiklerden **fiyata** giden koprü: "ARR ≥%10,5 ⇒ carpan 14x" adimi iddia
edilmis, olculmemis; ve olcmeye calistigimizda emsal-yakinsamasinin kendisi
bos cikiyor.

## Kapsam muhasebesi

- 1 ay: 31 kesit. `ic-2024-v1:2026-08` dustu (islem 2026-08-04, fiyat kapsami
  2026-08-05'te bitiyor -- ileri fiyat yok).
- 3 ve 6 ay: 30 kesit. `2026-06` de dustu.
- Her kullanilan kesitte **60/60 sirket** ileri fiyata sahip.
- Sektor eslesmesi 60/60: staples 24, saglik 12, sanayi 12, teknoloji 12.
- Doldurma yapilmadi; kapsam disi tarih icin en yakin fiyat **kullanilmadi**
  (bu proje bir kez tam bu hatayi yapmisti).

## Sonraki adim olmayan sey

On kayit soyle diyordu: IC pozitif cikarsa bir sonraki adim ust-alt sepet farki
olur. **Cikmadi**, dolayisiyla o adim yapilmiyor.
