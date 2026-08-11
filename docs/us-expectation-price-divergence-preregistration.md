# Ön kayıt — beklenti yukarı gitti ama fiyat takip etmedi, sonra yetişiyor mu

**Yazılma tarihi:** 2026-08-07
**Durum:** Hiçbir sapma hesaplanmadan, hiçbir ileri getiri eşleştirilmeden
yazıldı.

## Hipotez

Bir şirket yıllık yönlendirmesini yukarı çektiğinde fiyat **bunun gerektirdiği
kadar** tepki vermezse, izleyen ay farkı kapatır. Tersi de: yönlendirme
düşerken fiyat düşmediyse, sonra düşer.

Ölçülen değişken **yönlendirme değişimi değil**, fiyatın o değişime verdiği
tepkinin **eksiği ya da fazlası**.

## Neden analist konsensüsü değil, yönlendirme

Doğru vekil analist revizyonu olurdu — beklentinin 30/60/90 gün önceki hâli.
**O veri yok ve satın alınmadan elde edilemiyor:** ücretsiz sağlayıcılar
konsensüsün *bugünkü* hâlini dönem dönem veriyor, *o tarihteki* hâlini
(vintage) değil. Bu bir API arama meselesi değil, veri saklama meselesi.

Şirketin kendi yönlendirmesi elimizdeki en iyi beklenti vekilidir ve zincirin
yukarısındadır: analistler konsensüsü ona bakarak kuruyor.

## Önsel ALEYHTE — ve bunu şimdi yazıyorum

[us-overreaction-result.md](us-overreaction-result.md) bu mekanizmanın **EPS
sürprizine koşullu** hâlini test etti ve **ters sonuç** verdi: ρ +0,0825, bandın
dışında, pozitif. Yani hak ettiğinden az tepki veren hisse az tepki vermeye
devam etti; yetişme değil **devam** görüldü.

Bu test farklı bir koşullandırma kullanıyor (yönlendirme, sürpriz değil) ve
yönlendirme açıklama gününü çok daha iyi açıklıyor (%6,45'e karşı %2,59), yani
kalıntı daha temiz olabilir. Ama **önsel artık nötr değil, aleyhtedir.**

Pozitif bir sonuç, bu aleyhte önselle birlikte okunacak ve tek başına
"mekanizma çalışıyor" diye raporlanmayacak.

## Değişkenler

- **yönlendirme değişimi**: (bu açıklamada verilen tam yıl orta noktası −
  önceki açıklamadaki) / hisse fiyatı. Aynı mali yıl şartı.
- **tepki getirisi**: açıklama seansı ve ertesi (iki seans), evrenin eşit
  ağırlıklı ortalaması çıkarılmış. Açıklamanın seans öncesi/sonrası olduğu
  bilinmediği için pencere iki seans.
- **beklenen tepki**: yönlendirme değişiminin sırasına göre uydurulmuş tepki
  (sıralama bazlı hareketli ortalama, pencere `max(15, n/12)` olarak sabit —
  parametre seçimi yok).
- **SAPMA = tepki − beklenen tepki.** Negatif = fiyat haberin gerektirdiğinden
  az tepki verdi.
- **hedef**: tepki penceresinin **ertesi** seansından +21 seans, piyasa
  düzeltilmiş. Tepkinin kendisi asla dahil değil.

## Nokta-zaman kontrolü (zorunlu)

[olcum-metodolojisi.md](olcum-metodolojisi.md) 0j gereği: her gözlem için
`giriş_tarihi − yönlendirme_tarihi` yazdırılacak ve raporlanacak. Yönlendirme
açıklama anında yayınlanır, giriş iki seans sonrasıdır — yani veri girişte
kamuya açıktır. Bu **gösterilecek**, varsayılmayacak.

Bu kontrol, aynı gün geri çekilen bir tabloda tam olarak bu tuzağın
yakalanmasından sonra eklendi
([us-mechanical-families-result.md](us-mechanical-families-result.md)).

## Test edilecekler

| # | değişken | karar |
|---|---|---|
| **1** | **sapma → sonraki 21 seans** | **ANA TEST** |
| 2 | ham yönlendirme değişimi → sonraki 21 seans | karşılaştırma tabanı |
| 3 | ham tepki getirisi → sonraki 21 seans | karşılaştırma tabanı |

Hipotez doğruysa **1'in işareti NEGATİF** olmalıdır.

2 ve 3 karar vermez; sapmanın ham bileşenlerinden farklı bir şey ölçtüğünü
göstermek içindir.

## İstatistik ve güç

Havuzlanmış Spearman, açıklama takvim çeyreğine göre kümelenmiş permütasyon,
10.000 tekrar.

**Güç, şimdiden:** örneklem ~209 gözlemle sınırlı (aynı mali yıl şartı ve 60
şirketlik fiyat defteri). SE ≈ 0,069, yani **ayırt edilebilir en küçük etki
ρ ≈ 0,14**. Bundan küçük gerçek bir etki bu testte görünmez ve negatif sonuç
öyle okunacak.

**Ekonomik eşik:** alt-üst üçte bir farkı çift yönlü %0,20 işlem maliyetinin
altındaysa sonuç, bandın neresinde olursa olsun pratik olarak ölüdür.

## Karar kuralı

1. **Band dışında ve NEGATİF, fark > %0,20** → uyumsuzluk kapanıyor. Sonraki
   adım: ayrıştırma (sapmanın tahmin edilebilir kısmı var mı) + portföy kuralı,
   kendi ön kaydıyla.
2. **Band içinde** → hipotez düşer.
3. **Band dışında ama POZİTİF** → hipotez düşer ve aşırı tepki testinin
   sonucunu **ikinci kez** doğrular. İşaret çevrilip momentum stratejisi
   kurulmaz.
4. **Band dışında, negatif, fark < %0,20** → istatistiksel var, pratik ölü.

## Önceden reddedilenler

- Ufuk taraması yok: yalnız 21 seans.
- Uç dilimler ayrı test edilip ana sonuç yerine konmaz.
- Eşik/kesme noktası aranmaz.
- Sektör, büyüklük, dönem kırılımı yok.
- Negatif sonuç, "sapma tanımı farklı olmalıydı" denerek yeniden koşulmaz.
- Örneklem sonuç görüldükten sonra genişletilmez; genişletilirse post-hoc
  olarak işaretlenir.
