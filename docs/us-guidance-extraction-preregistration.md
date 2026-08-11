# Ön kayıt — LLM yönlendirme çıkarımı

**Yazılma tarihi:** 2026-08-06
**Durum:** Hiçbir LLM çağrısı yapılmadan yazıldı. Mekanik taban ölçüldü ve
aşağıda; LLM tarafından tek bir belge okunmadı.

## Neden bu, ve neden tahmin değil

[us-earnings-surprise-result.md](us-earnings-surprise-result.md) şunu gösterdi:
açıklama günü çeyreğin oynaklığının %12,6'sını taşıyor (63 seansın biri için 8
kat yoğunlaşma) ama EPS sürprizi o günün hareketinin ancak **~%4'ünü**
açıklıyor. Kalanı aynı belgede aynı anda çıkan gelir, marj, segment, yönetim
yorumu ve **gelecek dönem yönlendirmesi**.

Yönlendirmeyi sinyal olarak test edebilmek için önce onu **güvenilir biçimde
çıkarabilmek** gerekiyor. Mekanik çıkarım denendi ve başarısız oldu; bu test o
adımı LLM'e devretmenin işe yarayıp yaramadığını ölçer. **Tahmin sorusu bu
belgenin konusu değildir** ve bu test geçilmeden sorulmayacaktır: yanlış
çıkarılmış bir yönlendirmeyle kurulan her sinyal baştan çöptür.

## Mekanik taban (ölçüldü, LLM'siz)

1.420 Item 2.02 8-K'sı üzerinde cümle seviyesinde regex: bir cümle hem
yönlendirme fiili hem EPS terimi taşıyorsa içindeki dolar değerleri aday.

| | |
|---|---|
| sayı çıkarılabilen bildirim | 514 / 1.420 (**%36,2**) |
| aday cümlesi olan bildirim | 916 / 1.420 (%64,5) |
| hiç EPS yönlendirmesi vermeyen şirket | **18 / 60** |

### Zincir testi — objektif doğruluk ölçütü

Revizyonlar "**from** ESKİ **to** YENİ" kalıbıyla yazılır. Yani bir sonraki
çeyreğin "eskiden şu kadardı" ifadesi, bu çeyrekte çıkardığımız değerin doğru
olup olmadığını **piyasa verisi olmadan** söyler.

Yalnız gerçekten ardışık çeyrekler (75-110 gün arası), 85 test edilebilir çift:

| | |
|---|---|
| uyan | 7 |
| uymayan | 78 |
| **mekanik isabet** | **%8,2** |

Hatalar teşhisi veriyor — aynı basın bülteni dört ayrı EPS yönlendirmesi
içeriyor (GAAP × düzeltilmiş, çeyreklik × yıllık) ve regex hangisinin hangisi
olduğunu ayırt edemiyor:

| çıkarılan | doğrusu | karışan |
|---|---|---|
| ABBV 6,69-6,89 | 12,32-12,52 | GAAP ↔ düzeltilmiş |
| ABT 0,69-0,73 | 3,30-3,40 | çeyreklik ↔ yıllık |
| ABT 1,05-1,09 | 5,05-5,25 | ikisi birden |

İlk denememde ayrıca sistematik bir hata vardı: revizyon cümlesinde **ilk**
aralığı alıyordum, o da her zaman bir **önceki** çeyreğin yönlendirmesi.
Düzeltildi (sondaki alınır); yukarıdaki %8,2 düzeltilmiş hâlin sonucudur.

## Hipotez

Bir LLM, aday cümleler arasından **tam yıl, düzeltilmiş, seyreltilmiş EPS
yönlendirmesini** mekanik kuraldan belirgin biçimde daha doğru seçer.

Bu, projede LLM'in mekanik tabana karşı **yapısal avantajı olan ilk görev**:
sayı çıkarmak değil, dört benzer sayı arasından doğru olanı ayırt etmek — yani
okuduğunu anlama.

## Ölçüt ve karar kuralı

**Ana ölçüt: zincir testi isabeti.** Aynı 85 ardışık çift, aynı hesap. Piyasa
verisi kullanılmaz, dolayısıyla getiri üzerinde ayar yapma imkânı yoktur.

1. **İsabet ≥ %70** → çıkarım güvenilir. Yönlendirme defteri kurulur ve sinyal
   sorusuna geçilir (kendi ön kaydıyla).
2. **İsabet %30-70** → kısmi. Yalnız LLM'in kendi belirttiği yüksek-güven alt
   kümesi kullanılır ve o alt kümenin isabeti ayrıca raporlanır; geçmezse (1)
   sayılmaz.
3. **İsabet < %30** → LLM birincil belgeden güvenilir çıkarım yapamıyor.
   **Yönlendirme kolu kapanır.** Prompt varyasyonuyla kurtarma denenmez —
   skor-IC'de tutarlılığın 0,960 çıkması, sorunun prompt tasarımı olmadığını
   zaten göstermişti.

Eşikler sonuç görülmeden sabittir. %70 keyfi değil: %8,2'lik taban ile
kullanılabilirlik arasında, tek bir yanlış çıkarımın çeyreklik bir revizyon
sinyalini ters çevirmeye yeteceği düşünülerek seçildi.

## Kapsama, ayrı raporlanır

İsabet, **çıkarım yapılan** bildirimler üzerinden hesaplanır. Kapsama
(kaç bildirimde cevap üretildiği) ayrı bir sayıdır ve karar tetiklemez.

Tavan yapısal olarak sınırlı ve bu bir kusur değil: **60 şirketin 18'i hiç EPS
yönlendirmesi vermiyor** (AAPL, COST, NVDA, CAT, MSFT, PEP, DE, AVGO…). Bu
şirket politikasıdır. Azami kapsama ~%70 şirket.

## Girdi ve bilinen kısıt

LLM'e ham belge değil **aday cümleler** gönderilir. Bunun bir bedeli var ve
şimdiden kabul ediliyor: aday filtresi, isabetsiz olan regex'in aynı
filtresidir. LLM *ayırt etme* sorununu çözebilir, *bulamama* sorununu çözemez —
filtre cümleyi hiç görmediyse LLM'e de gitmez. Dolayısıyla bu test **916
bildirimlik tavan** üzerinde çalışır, 1.420 üzerinde değil.

İsabet yüksek ama kapsama düşük çıkarsa doğru okuma "LLM çıkarım yapabiliyor,
filtre dar" olur ve filtreyi genişletmek ayrı bir iştir — bu ön kaydın konusu
değildir.

## Kota — ölçüldü, tahmin değil

Ham belge göndermek pahalı olurdu; aday cümleler ucuz. Fark 20 kattan fazla:

| gönderilen | medyan/bildirim | 1.420 bildirim | puanlama koşusuna oran |
|---|---|---|---|
| ham metin | 48,6 KB (~12,1K token) | ~17 milyon token | yarısı |
| **aday cümleler** | **0,5 KB (~0,1K token)** | **~0,74 milyon token** | **~%2** |

Karşılaştırma: skor-IC koşusu 1.251 çağrı / ~33 milyon token idi.

Bu test 916 bildirim üzerinde çalışacağı için gerçek maliyet daha da düşük.
**Bir çeyreklik puanlama koşusundan ucuz.**

## Ek 1 — girdi kısıtı kalkıyor: NotebookLM (2026-08-06, sonuç görülmeden)

Yukarıdaki "aday cümleler" tasarımı bir kota kısıtından doğmuştu: ham belge
göndermek ~17 milyon token, puanlama koşusunun yarısı. NotebookLM MCP bu
kısıtı ortadan kaldırıyor — belge yüklemesi token bütçesine girmiyor.

**Değişen:**

- Girdi **ham belge metnidir**, aday cümle değil.
- Tavan **1.420 bildirim**, 916 değil. Ana metindeki "filtre cümleyi görmediyse
  LLM'e de gitmez" kısıtı **geçersizdir** ve testi zorlaştırır, kolaylaştırmaz:
  artık modelin bulamaması da bir başarısızlık olarak sayılır.
- Kota artık bağlayıcı kısıt değil; bağlayıcı kısıt **iş hacmi** (1.420 yükleme,
  tarayıcı otomasyonu üzerinden).

**Değişmeyen:** hipotez, zincir testi, eşikler (%70 / %30), mekanik taban
(%8,2), kapsamanın karar tetiklememesi. Eşikler sonuç görülmeden sabitlenmişti
ve **gevşetilmiyor** — girdi zenginleştiği için aynı eşik artık daha yüksek bir
çıta anlamına geliyor, ve bu bilinçlidir.

**Fizibilite denemesi** (ABBV, 3 belge, defter
`ec6f3021-cf4b-4828-8855-44d544d0ebfb`): yükleme belge başına birkaç saniye;
tek sorgu üç belgeyi birden cevapladı.

| tarih | mekanik | NotebookLM | zincirin doğrusu |
|---|---|---|---|
| 2021-02-03 | 6,69-6,89 (GAAP) | **12,32-12,52** | 12,32-12,52 |
| 2021-04-30 | 12,37-12,57 | 12,37-12,57 | ✓ |
| 2022-04-21 | — | **NONE** | belgede "guidance"/"outlook" hiç geçmiyor |

Üçü de doğru; biri mekanik kuralın kanıtlanmış olarak yanıldığı vaka, biri
doğru negatif (olmayan sayı uydurulmadı). **Bu bir sonuç değildir** — n=3, ve
karar yalnız 85 çiftlik zincir testiyle verilir.

**Ölçeğe dair açık soru, şimdiden kayda geçiyor:** tek sorgu 3 belgeyi
cevapladı; şirket başına ~24 belgede aynı sorgunun bozulup bozulmadığı
(kısalma, atlama, karıştırma) bilinmiyor. Cevaplar belge sayısıyla bozuluyorsa
sorgu belge başına bölünür — bu bir tasarım tercihi, sonuç değil, ve zincir
testi hangi biçimde koşulduğundan bağımsızdır.

**Defter kaydı zorunlu.** Şirket başına bir defter, `notebook_id` kalıcı olarak
yazılır; aksi hâlde sonraki oturum aynı 1.420 belgeyi yeniden yükler
(AGENTS.md'deki kural, aynı gerekçe).

## Önceden reddedilenler

- Prompt varyasyonuyla kurtarma yok (bkz. karar kuralı 3).
- Model karşılaştırması yok; tek model, tek prompt.
- Eşik sonradan gevşetilmez.
- "Zincir testi zor bir ölçüt" gerekçesi geçersizdir: revizyon cümlesindeki
  eski değer, doğru cevabın kendisidir; şirketin kendi beyanıdır.
- Bu test getiri ölçmez ve hiçbir getiri sonucu tetiklemez.
