# Sonuç — yönlendirme, açıklama günü hareketini açıklıyor

**Ön kayıt:** [us-guidance-signal-preregistration.md](us-guidance-signal-preregistration.md)
(2026-08-06, hiçbir yönlendirme getiriyle eşleştirilmeden yazıldı)
**Ölçüm tarihi:** 2026-08-06
**Örneklem:** 58 şirket, 209 olay, 22 takvim çeyreği, 2021-2026

## Bir cümlede

Şirketin yeni açıkladığı tam yıl yönlendirmesinin bir önceki çeyreğe göre
değişimi, açıklama günü hareketini **şans bandının belirgin biçimde dışında**
sıralıyor — üst üçte bir, alt üçte biri **%6,45** geçiyor — ve bu, EPS
sürprizinin açıkladığından hem daha büyük hem ondan büyük ölçüde bağımsız.

## Ana test

| | |
|---|---|
| gözlem | 209 (22 takvim çeyreği) |
| Spearman | **+0,4137** |
| şans bandı (10.000 kümelenmiş permütasyon) | −0,1105 .. +0,1084 |
| konum | **band dışında** |
| üst üçte bir − alt üçte bir | **+%6,45** |

Karşılaştırma: [us-earnings-surprise-result.md](us-earnings-surprise-result.md)
EPS sürprizi için +%2,59 ölçmüştü. Yönlendirme değişimi bunun ~2,5 katı.

## İkisi aynı şey değil

Ortak 59 olayda (Alpha Vantage kapsamı EPS sürprizini 21 şirkete sınırlıyor):

| | |
|---|---|
| yönlendirme ↔ EPS sürprizi | **+0,1932** |
| yönlendirme → getiri | +0,2403 |
| EPS sürprizi → getiri | +0,2025 |

Korelasyon 0,19 — büyük ölçüde **bağımsız iki bilgi**. Şirketin geçen çeyrek ne
kazandığı ile gelecek yıl ne bekleddiği farklı şeyler, ve fiyat ikisine de tepki
veriyor.

## Bu para DEĞİLDİR

Yönlendirme, tepkiyi ölçtüğümüz pencerenin **içinde** açıklanıyor. Ölçülen şey
"o gün ne oldu", "önceden ne bilinebilirdi" değil. İşlem yapmak için
yönlendirme değişimini **açıklanmadan önce** tahmin etmek gerekir; bu test onu
ölçmez ve ölçtüğünü iddia etmez.

Değeri şudur: **hangi değişkenin tahmin edilmesi gerektiğini** söyler.
[us-earnings-surprise-result.md](us-earnings-surprise-result.md) sürprizin
tahmin edilebilir kısmının sıfır kazandırdığını göstermişti; bu sonuç, aynı
günde çok daha büyük bir hareketi açıklayan başka bir değişken olduğunu
gösteriyor.

## Çıkarımın güvenilirliği

NotebookLM'in ürettiği 654 aralığın **597'si (%91,3)** kaynak belgede birebir
bulundu. Bu, sayıların uydurulmadığının doğrudan kanıtıdır.

Dışlamadığı şey: aynı belgede birden çok düzeltilmiş EPS yönlendirmesi varsa
(GAAP/düzeltilmiş × çeyreklik/yıllık) yanlış olanın seçilmiş olması. Elle
bakılan 16 belgede (ABT 13, ABBV 3) hepsi doğruydu ama bu sistematik bir ölçüm
değildir.

[us-guidance-extraction-preregistration.md](us-guidance-extraction-preregistration.md)'de
tanımlanan zincir testi **uygulanamadı**: dayandığı "revizyonlar 'eskiden şuydu'
diye yazılır" varsayımı 1.420 bildirimin yalnız 22'sinde (%1,5) geçerli. Orada
raporlanan mekanik taban (%8,2) ve NotebookLM sonucu (%0) bozuk bir dedektörden
geldi — "aynı cümlede iki aralık" revizyon sanılmış, oysa çoğunlukla yan yana
duran GAAP ve düzeltilmiş rakamlar. **Her iki sayı da geri çekilmiştir.**

## Post-hoc yapılanlar — sonuç görüldükten sonra

Bunlar saklanmıyor, çünkü sonucun okunma biçimini değiştirirler.

1. **Örneklem 59'dan 209'a büyütüldü.** İlk koşuda tepki getirileri Alpha
   Vantage'ın açıklama tarihlerinden kuruluyordu ve o yalnız 21 şirketi
   kapsıyordu; 153 çift bu yüzden düşüyordu. 8-K'nın dosyalama tarihi zaten
   açıklama tarihidir ve 58 şirketin hepsinde vardır. İlk koşunun sonucu
   ρ +0,277 idi ve band (+0,023 .. +0,338) dejenereydi — çeyrek başına 2,8 olayda
   kümelenmiş permütasyon neredeyse hiçbir şeyi değiştirmiyor. Düzeltme gerçek
   bir kusuru gideriyor ama **sonuç görüldükten sonra yapıldı**.
2. **Tepki penceresi iki seans.** Açıklamanın seans öncesi mi sonrası mı
   yapıldığı 58 şirket için bilinmiyor (o alan da yalnız Alpha Vantage'da).
   Geniş pencere gürültü ekler, yanlılık eklemez.
3. **Yıl çıkarımı güçlendirildi** (serbest yıl taraması yerine "full-year YYYY"
   / "fiscal YYYY" kalıbı), 212 çiftin düşme sebebi buydu.

## Bilinen sınırlar

- **Tek yöntem, tek prompt, tek model.** Sonuç NotebookLM ve bu prompt içindir.
- **Yönlendirme veren şirketler alt kümesi.** 60 şirketin 18'i hiç EPS
  yönlendirmesi vermiyor; BMY ve MMM NotebookLM'e yüklenemedi (%5,4 belge
  kaybı).
- **Aynı mali yıl kısıtı** 68 çifti eledi ve bu doğrudur (Q4'te yönlendirme yeni
  yıla geçer), ama yıl çıkarımı hâlâ mükemmel değil.
- **Sağlamlık kontrolü yapılmadı.** Pencereyi tek seansa daraltmanın sonucu
  ayakta bırakıp bırakmadığı ölçülmedi.
- 2021-2026, ABD büyük sermaye. Rejim ve evren sınırları önceki belgelerdekiyle
  aynı.

## Bundan sonra

Test edilecek soru artık net ve daha önce ölçtüğümüz her şeyden farklı:

> **Bir şirketin gelecek çeyrekte yönlendirmesini ne kadar değiştireceği,
> açıklanmadan önce tahmin edilebilir mi?**

Bu, EPS sürprizi tahmininden farklı bir sorudur ve ödülü ölçülmüştür (%6,45 /
çeyrek, tam öngörü tavanı). Kendi ön kaydını gerektirir; mekanik taban (geçmiş
yönlendirme değişimlerinin devamı) zorunlu kontrol grubudur — sürprizde tam
olarak o taban, tahmin edilebilir kısmın sıfır kazandırdığını göstermişti.
