# Ön kayıt — yönlendirme, açıklama günü hareketini açıklıyor mu

**Yazılma tarihi:** 2026-08-06
**Durum:** Hiçbir yönlendirme–getiri eşleştirmesi yapılmadan yazıldı. Çıkarım
koşusu sürüyordu (26/58 cevap); o cevaplardan hiçbiri getiriyle
karşılaştırılmamıştı.

## Neden bu soru

[us-earnings-surprise-result.md](us-earnings-surprise-result.md) iki şey ölçtü:

- Açıklama günü çeyreğin toplam oynaklığının **%12,6'sını** taşıyor — 63 seansın
  biri için 8 kat yoğunlaşma.
- Ama EPS sürprizi o günkü hareketin ancak **~%4'ünü** açıklıyor.

Kalan ~%96, aynı belgede aynı anda çıkan şeyler: gelir, marjlar, segment
detayı, yönetim yorumu ve **gelecek dönem yönlendirmesi**. Bu test onlardan
birini ölçer.

## Neden ayrı bir çıkarım-doğruluğu testi yok

[us-guidance-extraction-preregistration.md](us-guidance-extraction-preregistration.md)
çıkarım doğruluğunu ölçmek için bir zincir testi tanımlamıştı. **O ölçüt bu
külliyatta uygulanamadı**: dayandığı "revizyonlar 'eskiden şuydu' diye yazılır"
varsayımı 1.420 bildirimin yalnız 22'sinde (%1,5) geçerli. Orada verilen
mekanik taban (%8,2) ve NotebookLM sonucu (%0) bozuk bir dedektörden geldi ve
ikisi de geri çekildi.

Ayrı bir doğruluk testi kurmak yerine bu test doğrudan koşulur, çünkü **çıkarım
bozuksa bu test zaten negatif verir.** Pozitif bir sonuç ise çıkarımın en az
kullanılabilir olduğunu gösterir. Tek yönlü bir çıkarım zinciri değil, ama fazla
ölçüm katmanı biriktirmeden asıl soruya gider.

Bunun bedeli önceden kabul ediliyor: **negatif sonuç iki şeyden hangisi olduğunu
ayırmaz** — "yönlendirme fiyatta" mı, "çıkarımımız kötü" mü. Negatif çıkarsa bu
ayrım yapılmamış olarak raporlanır, kapatılmış olarak değil.

## Örneklem

`us/guidance/` — 60 şirket, 1.420 Item 2.02 8-K'sı, 2021-01 → 2026-07.
NotebookLM'e 1.343'ü yüklendi (BMY ve MMM'in tamamı yüklenemedi, %5,4 kayıp).
Getiriler `ic-2021-v1` ve `ic-2024-v1` donmuş fiyat defterlerinden, birleşik
kapsam 2020-05 → 2026-08.

## Tanımlar (önceden sabit)

- **Tepki getirisi:** sürpriz testindeki ile aynı — `reportTime`'a göre hizalanan
  tek seans, evrenin eşit ağırlıklı ortalaması çıkarılmış.
- **Yönlendirme sürprizi:** `(yeni yönlendirme orta noktası − önceki çeyrekte
  açıklanan yönlendirmenin orta noktası) / hisse fiyatı`. Fiyata bölünür çünkü
  kâra bölmek küçük paydada patlar (sürpriz testinde ölçüldü).
- İlk yönlendirme (öncesi olmayan) dışarıda kalır; "yeni yönlendirme" ile
  "yönlendirme değişimi" farklı şeylerdir ve ölçülen ikincisidir.
- Yönlendirme yılı değiştiğinde (Q4 → yeni mali yıl) karşılaştırma yapılmaz.

## Test edilecekler

| # | değişken | karar |
|---|---|---|
| **1** | **yönlendirme sürprizi ↔ tepki getirisi** | **ANA TEST** |
| 2 | EPS sürprizi ↔ tepki getirisi (yeniden) | karşılaştırma tabanı |
| 3 | ikisi birlikte: hangisi diğerinin üstüne bilgi ekliyor | karar vermez |

3, ikisinin sıralamalarından biri diğerinin kalıntısına karşı test edilerek
kurulur — sürpriz testindeki ayrıştırmanın aynısı.

## İstatistik ve karar kuralı

Havuzlanmış Spearman, açıklama takvim çeyreğine göre kümelenmiş permütasyon
(10.000 tekrar), sürpriz testiyle birebir aynı çerçeve.

1. **Yönlendirme sürprizi bandın dışında ve EPS sürprizinden güçlü** →
   yönlendirme, sürprizin ötesinde bilgi taşıyor. Sonraki adım: dil katmanı
   (yönlendirme metnindeki değişim), kendi ön kaydıyla.
2. **Band içinde** → yönlendirmenin **sayısı** fiyatta. Sayısal yönlendirme kolu
   kapanır. Dil hipotezi ayrı kalır ve bu sonuçla elenmiş sayılmaz — çünkü bu
   test sayıyı ölçtü, dili değil.
3. **Band dışında ama EPS sürprizinden zayıf** → bağımsız katkısı 3. testte
   raporlanır, tek başına yeni bir kol açmaz.

## Önceden reddedilenler

- Ufuk taraması yok: yalnız tepki penceresi. Sürpriz testi sürüklenmenin
  olmadığını zaten ölçtü.
- Eşik/kesme noktası aranmaz; ham sıralama.
- Sektör veya alt evren kırılımı yok.
- Kapsama düşük çıkarsa (yönlendirme vermeyen şirketler) bu bir sonuçtur, telafi
  edilmez.
- Negatif sonuç prompt değiştirilerek yeniden koşulmaz.
