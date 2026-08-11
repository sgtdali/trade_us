# Ön kayıt — beklenti gerçekleşirse bugünkü fiyat ne anlama geliyor

**Yazılma tarihi:** 2026-08-07
**Durum:** Hiçbir değerleme oranı getiriyle eşleştirilmeden yazıldı.

## Soru

Rolümüz değişiyor. Artık **tahminci değil değerlemeciyiz**:

```
ONCE:  "EPS 7 olacak mi?"          -> konsensusle yarisiyoruz
SIMDI: "EPS 7 OLURSA, 100 ne demek?" -> beklentiyi VERI aliyoruz
```

Şirketin kendi tam yıl yönlendirmesi doğru kabul edilir. Soru, bugünkü fiyatın
o beklentiye göre nerede durduğudur.

## Neden konsensüs değil yönlendirme

Analist konsensüsünün tarihsel vintage'ı yok ve satın alınmadan elde edilemiyor
([us-expectation-price-divergence-preregistration.md](us-expectation-price-divergence-preregistration.md)).
Şirketin kendi yönlendirmesi elimizdeki en iyi ileri beklenti vekilidir ve
zincirin yukarısındadır — konsensüs zaten ona bakarak kuruluyor.

## Neden mutlak "adil değer" değil, kesitsel sıralama

"Olması gereken fiyat" bir iskonto oranı, terminal büyüme ve marj varsayımı
gerektirir; WACC'de 50 baz puanlık fark adil değeri ~%20 oynatır. Bu, sahte
hassasiyettir.

Aynı ekonomik soru varsayımsız sorulabilir: **aynı anda bütün evreni beklentiye
göre sırala.** "Bu hisse %30 ucuz" değil, "bu hisse beklentisine göre evrenin en
ucuz onda birinde".

## ÖNSEL: kendi yasamız bu testin NULL çıkacağını söylüyor

İki bağımsız ölçümde bulundu
([us-earnings-surprise-result.md](us-earnings-surprise-result.md),
[us-guidance-forecast-result.md](us-guidance-forecast-result.md)):

| | tahmin edilebilir kısım | kalıntı |
|---|---|---|
| EPS sürprizi | +%0,39 | +%2,26 |
| yönlendirme değişimi | +%1,38 | +%6,85 |

**Yönlendirme, tanımı gereği tahmin edilebilir kısımdır** — profesyonel
ekstrapolasyonun kendisi. Kendi yasamıza göre ona dayalı bir değerleme sıralaması
sıfır vermeli.

Ayrıca geriye dönük versiyonu zaten ölçüldü ve null çıktı: kazanç getirisi
ρ −0,0234.

**Bu test bu yüzden değerli:** iki gözlem bir düzenlilik, üçüncüsü ya doğrular
ya kırar. **Pozitif sonuç, negatiften daha bilgilendiricidir** — yasamızın
yanlış ya da eksik olduğunu gösterir.

## Değişkenler — veri görülmeden sabit

Her açıklama anında, o anda bilinen değerlerle:

| # | değişken | tanım |
|---|---|---|
| **F1** | ileri kazanç getirisi | yönlendirme orta noktası / fiyat |
| **F2** | geriye dönük kazanç getirisi | TTM düzeltilmiş EPS / fiyat |
| **F3** | ileri − geri farkı | (yönlendirme − TTM) / fiyat |
| **F4** | ima edilen getiri | F1 + büyüme, `büyüme = yönlendirme / TTM − 1` |

F2 karşılaştırma tabanıdır ve null çıkması beklenir.

F3, kullanıcının sorusunun en doğrudan hâli: **şirketin geleceği geçmişinden ne
kadar farklı, ve o fark fiyatta mı.**

F4, "bu fiyatı ödersem beklenti gerçekleşirse ne kazanırım" sorusunun
varsayımsız yaklaşığıdır — iskonto oranı seçilmez.

Hepsinin işareti **pozitif** varsayılır (yüksek getiri / ucuz → yüksek sonraki
getiri). İşaretler burada sabittir ve sonuç görüldükten sonra çevrilmez.

## Ufuk — birincil 63 seans, ve gerekçesi önceden

Bugüne kadarki testlerimiz 21 seans kullandı. **Değerleme sinyalleri yavaştır**
ve 21 seansta ölçüp "yok" demek zayıf bir sonuç olurdu. Bu yüzden:

- **Birincil: 63 seans** (~bir çeyrek). Çeyreklik olaylarla pencereler
  neredeyse örtüşmeden döşenir, yani bağımsız gözlem kaybı azdır.
- **İkincil, karar vermez: 21 seans.** Diğer testlerle karşılaştırılabilirlik
  için.

Bu tercih **sonuç görülmeden** yapıldı ve gerekçesi ekonomiktir, sonuca
bakılarak değil.

## İstatistik

Havuzlanmış Spearman, açıklama takvim çeyreğine göre kümelenmiş permütasyon,
10.000 tekrar. Çoklu test: 4 değişken üzerinde **max |t|** aile düzeltmesi.

**Ekonomik eşik:** üst-alt üçte bir farkı, çift yönlü %0,20'nin altındaysa
sonuç pratik olarak ölüdür.

**Nokta-zaman kontrolü zorunlu:** her gözlem için `giriş − yönlendirme tarihi`
yazdırılacak ([olcum-metodolojisi.md](olcum-metodolojisi.md) 0j).

## Karar kuralı

1. **Herhangi bir değişken aile eşiğini geçer ve fark > %0,20** → beklentiye
   göre değerleme sıralıyor. **Zorunlu sonraki adım: ayrıştırma** — bu
   sıralamanın tahmin edilebilir kısmı mı kalıntısı mı ödüyor. O yapılmadan
   sonuç eksiktir.
2. **Hiçbiri geçmez** → yasamızın üçüncü doğrulaması. Beklentiye dayalı
   değerleme, beklenti kamuya açık olduğu için fiyatlanmıştır.
3. **F2 geçer ama F1 geçmezse** → beklenmedik bir sonuçtur ve olduğu gibi
   raporlanır; geriye dönük değerleme daha önce null çıkmıştı.

## Önceden reddedilenler

- Ufuk taraması yok: yalnız 63 ve 21, ikincisi karar vermez.
- Mutlak adil değer hesaplanmaz; iskonto oranı seçilmez.
- Eşik/kesme noktası aranmaz; ham sıralama.
- Sektör, büyüklük, dönem kırılımı yok.
- Uç dilimler ayrı test edilip ana sonuç yerine konmaz.
- Negatif sonuç, değişken tanımı değiştirilerek yeniden koşulmaz.

## Güç, şimdiden

Örneklem ~200 gözlem bekleniyor (yönlendirme + TTM gerçekleşen + fiyat
kesişimi). SE ≈ 0,07, **ayırt edilebilir en küçük etki ρ ≈ 0,14** ve aile
düzeltmesiyle daha yüksek. Negatif sonuç "bundan küçük" diye okunacak, "yok"
diye değil.
