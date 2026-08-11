# Ön kayıt — yönlendirme değişimi önceden tahmin edilebilir mi (mekanik taban)

**Yazılma tarihi:** 2026-08-06
**Durum:** Hiçbir tahmin hesaplanmadan yazıldı. Gerçekleşen düzeltilmiş EPS
çıkarımı arka planda üretimdeydi ve hiçbir özellik hedefle karşılaştırılmamıştı.

## Neden

[us-guidance-signal-result.md](us-guidance-signal-result.md) yönlendirme
değişiminin açıklama günü hareketini açıkladığını ölçtü (ρ +0,414, üst-alt
%6,45, bandın dışında). Ama o ölçüm **eş zamanlı** — yönlendirme, tepkiyi
ölçtüğümüz pencerenin içinde açıklanıyor. Para için önceden tahmin gerekiyor.

Bu belge **yalnızca mekanik tabanı** ön kayda geçirir. LLM yoktur ve bu
bilinçlidir: bugün iki kez, mekanik kontrol LLM'i yakaladı ya da geçti. Taban
kurulmadan LLM'in kattığı şey ölçülemez.

## Hedef değişken

`(sonraki çeyrekte açıklanan yönlendirme orta noktası − bu çeyrekte açıklanan
orta nokta) / hisse fiyatı`. Aynı mali yıl şartı; yıl değişince karşılaştırma
yapılmaz. Sinyal testindeki tanımın birebir aynısı.

## Özellikler — veri görülmeden sabitlendi, hepsi raporlanacak

Hepsi kesim anında (bir sonraki açıklamadan önce) bilinebilir.

| # | özellik | mantık |
|---|---|---|
| 1 | **koşu hızı farkı** — yıl-başından-bugüne gerçekleşen düzeltilmiş EPS / (yönlendirme orta noktası × geçen çeyrek oranı) − 1 | Şirket kendi yolunun önündeyse yukarı revize eder |
| 2 | **son yönlendirme değişimi** | Alışkanlık: sandbagging yapan şirket üst üste yükseltir |
| 3 | **son 4 değişimin ortalaması** | Aynı alışkanlığın daha durağan hâli |
| 4 | **aralık genişliği / orta nokta** | Geniş aralık belirsizlik demek |
| 5 | **aralık genişliğindeki değişim** | Daraltmak güven, genişletmek tereddüt |
| 6 | **yönlendirmenin yaşı** (kaç çeyrektir değişmemiş) | Uzun süre dokunulmamış yönlendirme revizyona yaklaşır |
| 7 | **bileşik sıra skoru** — 1-6'nın rank ortalaması, işaretler önceden yukarıdaki mantığa göre sabitlenmiştir | Tek bir taban rakamı |

Özellik seçimi **yapılmayacak**: hangisinin işe yaradığına bakıp bileşiği ona
göre kurmak, tam olarak ölçmeye çalıştığımız şeyi yok eder. 7 numaranın işaret
ve ağırlıkları (eşit) burada sabittir.

**1 numara mevcut olmayabilir.** Gerçekleşen düzeltilmiş EPS ayrı bir çıkarım
koşusundan geliyor; kapsama yetersiz kalırsa 1 numara düşer ve bu, sonuçla
birlikte raporlanır — sessizce çıkarılmaz.

## İstatistik

Havuzlanmış Spearman (özellik ↔ gerçekleşen yönlendirme değişimi), açıklama
takvim çeyreğine göre kümelenmiş permütasyon, 10.000 tekrar. Çoklu test için
7 özellik üzerinde **max |t|** aile düzeltmesi — mekanik taramada kullanılan
çerçevenin aynısı.

**Getiri kullanılmaz.** Bu test tamamen tahmin doğruluğu üzerinedir; piyasa
verisi girmediği için sonucu kayıran bir ayar yapmak mümkün değildir.

## Karar kuralı

1. **Bileşik skor aile eşiğini geçerse** → yönlendirme değişimi mekanik olarak
   tahmin edilebilir. Sonraki adım **ikiye ayrılır** ve ikisi de gereklidir:
   (a) bu tahminin **kalıntısı** getiriyi sıralıyor mu — çünkü tahmin edilebilen
   kısım muhtemelen zaten fiyattadır (EPS sürprizinde tam olarak bu oldu);
   (b) LLM bu tabanın üstüne bir şey ekliyor mu.
2. **Geçmezse** → yönlendirme değişimi geçmiş yönlendirme ve kâr verisinden
   tahmin edilemiyor. LLM'e geçmek için gerekçe **güçlenir**, zayıflamaz: geriye
   kalan bilgi mekanik olmayan yerdedir (dil, çeyrek arası bildirimler, dış
   değişkenler). Ama bu, LLM'in başaracağı anlamına gelmez ve öyle
   yazılmayacaktır.
3. **Tek tek özellikler geçip bileşik geçmezse** → bileşiğin ağırlıkları
   sonradan ayarlanmaz. Sonuç olduğu gibi raporlanır.

## Önceden reddedilenler

- Özellik seçimi, ağırlık optimizasyonu, eşik arama yok.
- Alt dönem veya sektör kırılımı yok.
- Negatif sonuç prompt/model değiştirilerek kurtarılmaz (LLM zaten yok).
- Kapsama düşük çıkarsa bu bir sonuçtur; eksik özellik telafi edilmez.
- "Şirket başına model" kurulmaz; 58 şirket için tek havuzlanmış ölçüm.
