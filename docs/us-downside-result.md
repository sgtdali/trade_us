# Sonuç — muhasebe çöküşü görüyor ama oynaklığın üstüne bir şey eklemiyor

**Ön kayıt:** [us-downside-preregistration.md](us-downside-preregistration.md)
(2026-08-07, hiçbir özellik çöküş göstergesiyle karşılaştırılmadan yazıldı)
**Ölçüm tarihi:** 2026-08-07
**Örneklem:** 1.349 açıklama olayı, 60 şirket, 2020-2026

## Bir cümlede

Çöküşü en iyi ayıran şey **bedava oynaklık** (3,6 kat); muhasebeden yalnız **net
marj** aile eşiğini geçti (2,8 kat); ve **ödeme gücü ailesinin tamamı battı** —
ki ön kayıtta en çok onların çalışmasını beklemiştim.

## Tablo

Çöküş = 63 seansta piyasa-düzeltilmiş getiri ≤ −%20.
**Taban oran: 58/1.349 = %4,3.** Aile eşiği |t| > 2,80 (12 özellik).

| özellik | n | ρ | t | riskli 1/3 | güvenli 1/3 | kat | |
|---|---|---|---|---|---|---|---|
| **V1 −oynaklık** | 1.349 | −0,1360 | **−5,11** | %8,0 | %2,2 | **3,6x** | **geçer** |
| **V2 −maks düşüş** | 1.349 | −0,1256 | **−4,56** | %7,8 | %2,4 | 3,2x | **geçer** |
| **Q1 net marj** | 1.348 | −0,0868 | **−2,99** | %6,9 | %2,4 | **2,8x** | **geçer** |
| S5 faaliyet nakdi / borç | 488 | −0,0718 | −0,89 | %9,9 | %5,6 | 1,8x | |
| S3 nakit / cari yükümlülük | 508 | −0,0586 | −1,26 | %8,9 | %5,3 | 1,7x | |
| Q2 −tahakkuk | 503 | −0,0524 | −0,28 | %7,8 | %4,8 | 1,6x | |
| S1 −net borç / varlık | 500 | −0,0380 | −0,88 | %9,0 | %6,0 | 1,5x | |
| S2 cari oran | 512 | −0,0332 | −0,71 | %7,6 | %4,7 | 1,6x | |
| S4 özkaynak / varlık | 519 | −0,0232 | −0,53 | %7,5 | %5,2 | 1,4x | |
| Q3 −şerefiye+maddi olmayan | 486 | +0,0553 | +1,22 | %5,6 | %8,0 | 0,7x | ters |
| D1 muhasebe bileşiği | 519 | −0,0755 | −1,32 | %9,8 | %5,8 | 1,7x | |
| **D2 muhasebe \| oynaklık çıkarılmış** | 519 | −0,0885 | **−1,64** | %9,8 | %5,2 | 1,9x | **geçmiyor** |

## Asıl soru cevaplandı: hayır

Ön kayıt zorunlu ikinci aşamayı tanımlamıştı: muhasebe bileşiği, **oynaklık
sıralaması çıkarıldıktan sonra** hâlâ ayırıyor mu.

**D2 = −1,64, eşik 2,80. Geçmiyor.**

Karar kuralı 2 uygulandı: muhasebe, bedava oynaklığın söylediğini tekrarlıyor.
Bilanço okumadan, tek satır fiyat verisiyle daha iyi ayrım elde ediliyor
(3,6x'e karşı 1,7x).

## Kendi ekonomik hikâyemi çürüten kısım

Ön kayıtta şu argümanı kurdum:

> *"Finansal tablolar tam olarak bunun için yapıldı. Bilanço bir yükümlülük
> envanteri, nakit akış tablosu bir ödeme gücü ölçüsü."*

**Ödeme gücü ailesinin tamamı (S1-S5) battı.** Net borç, cari oran, nakit
pozisyonu, özkaynak yastığı, nakit akışı/borç — hiçbiri eşiğe yaklaşmadı bile
(|t| 0,53-1,26). Kat oranları 1,4-1,8x, yani gürültü seviyesinde.

Geçen tek muhasebe değişkeni **net marj** ve o bir **kârlılık** ölçüsü, ödeme
gücü ölçüsü değil.

Yani hipotezin arkasındaki ekonomik gerekçe **yanlıştı**. Doğru olan daha basit
bir şey: kâr marjı düşük şirketler daha kırılgan. Bu, bilançonun tasarım
amacıyla ilgili değil.

**Ön kayıtta yazmadığım bir gerekçeyi sonradan uydurmuyorum.** Net marjın neden
çalıştığına dair bir hikâyem yok; ölçüm var, açıklama yok.

## Q1 hakkında dürüst olunması gereken

Net marj aile eşiğini geçti (t = −2,99 > 2,80) ve 2,8 kat ayırıyor. Bu, 12
özellik arasında **aile-düzeltilmiş** bir sonuç, tek test kaçamağı değil.

**Ama oynaklıktan bağımsız olup olmadığı ÖLÇÜLMEDİ.** Ön kayıt ikinci aşamayı
yalnız bileşik (D1) için tanımlamıştı; Q1'in kalıntısı için değil. Şimdi koşup
raporlamak, kuralın harfini sonuca göre genişletmek olur.

Bu, kendi ön kaydımın eksiği ve öyle yazılıyor. Q1'in oynaklıktan bağımsızlığı
**kendi ön kaydını gerektirir** ve örneklem-dışı doğrulanmalıdır.

Not: skor-IC çalışmasında LLM puanı da **2,8 kat** vermişti — aynı sayı. Model
muhtemelen kârlılığı okuyordu.

## Kapsama — ve neden ödeme gücü ailesi zayıf ölçüldü

| aile | n |
|---|---|
| V1, V2, Q1 | 1.348-1.349 |
| S ve Q2, Q3 | 486-519 |

Bilanço kapsaması ~%38: 10-Q karşılaştırma artifact'ları bilinçli olarak bilanço
taşımıyor. Ödeme gücü ailesi bu yüzden üçte bir örneklemde ölçüldü.

**Bu, "ödeme gücü çalışmıyor" sonucunu zayıflatır ama tersine çevirmez:** 500
gözlemde 1,4-1,8x'lik oranlar, 1.349 gözlemde 3,6x veren oynaklığın yanında
küçük kalıyor ve kat oranları örneklem büyüklüğünden bağımsız okunabilir.

## Sınırlar

- **Bu evrende gerçek iflas yok.** Ölçülen şey batma değil sert düşüş. Gerçek
  ödeme gücü krizleri küçük sermayede ve kredi piyasasında olur; bu test onu
  görmez. Ödeme gücü değişkenlerinin burada çalışmaması, orada da
  çalışmayacağı anlamına **gelmez**.
- **Faiz karşılama oranı yok** — `financial_expense` ABD artifact'larında yaygın
  değil. Ödeme gücünün en doğrudan ölçüsü eksik.
- Çöküş taban oranı %4,3; 58 olay. Test güçsüz değil ama uçlarda.
- 2020-2026, ABD büyük sermaye.

## Bunun bugüne eklediği

Bugün on test "daha çok kazandırır mı" diye sordu ve hepsi null çıktı. Bu test
farklı bir soru sordu — "batar mı" — ve **bir şey buldu**: çöküş ayrımı
gerçekten mümkün.

Ama bulunan şey muhasebede değil, **bedava fiyat verisinde**. Ve bu, bugünün
dördüncü kez tekrarlanan desenine bir yenisini ekliyor: elimizdeki en ucuz araç,
en pahalı olanı yeniyor.
