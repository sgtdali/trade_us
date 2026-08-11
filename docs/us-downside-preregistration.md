# Ön kayıt — muhasebe, çöküşü önceden görüyor mu

**Yazılma tarihi:** 2026-08-07
**Durum:** Hiçbir özellik çöküş göstergesiyle karşılaştırılmadan yazıldı. Çöküş
taban oranı da hesaplanmadı.

## Neden bu, ve neden bugünkü hiçbir testin kapsamadığı yer

Bugün on testte aynı soruyu sorduk: **"bu hisse daha çok kazandırır mı?"** Hepsi
null çıktı ve sebebi ölçüldü — tahmin edilebilen fiyatta.

Bu farklı bir soru: **"bu şirket batar mı?"**

Gerekçesi ekonomik, sonradan uydurulmuş değil. **Finansal tablolar tam olarak
bunun için yapıldı.** Bilanço bir yükümlülük envanteri, nakit akış tablosu bir
ödeme gücü ölçüsü. "Bu şirket büyüyecek mi, talep artacak mı" sorusunu
cevaplamak için tasarlanmadılar — ödeme gücünü göstermek için tasarlandılar.

Bugüne kadar aracı yapılmadığı iş için kullandık.

Ayrıca elimizde bir ipucu var ve hiç takip edilmedi: skor-IC çalışmasında düşük
puanlı şirketler **2,8 kat daha sık çöktü** (ay düzeyinde permütasyonla anlamlı)
ama **ortalama getirileri daha yüksekti**. Yani araç getiri sıralamasında
başarısız, risk ayrımında çalışıyor olabilir.

## ASIL SORU — ve önseli aleyhte

Aynı çalışmada bir şey daha ölçülmüştü: **bedava oynaklık çöküşleri daha iyi
ayırdı** (27'ye karşı 18), ve puan ile oynaklığın korelasyonu yalnız −0,066'ydı.

Dolayısıyla bu testin asıl sorusu **"muhasebe çöküşü görüyor mu"** değil:

> **Muhasebe, bedava oynaklığın ÜSTÜNE bir şey ekliyor mu?**

Oynaklık tek başına daha iyiyse, temel analiz bu iş için de gereksizdir. Önsel
aleyhtedir ve bu şimdi yazılıyor.

## Hedef

**Çöküş = önümüzdeki 63 seansta piyasa-düzeltilmiş getiri ≤ −%20.**

- İkincil, karar vermez: ≤ −%30.
- Ölçüm anı: her Item 2.02 açıklaması. Giriş tepkiden iki seans sonra.
- Taban oran (kaç olayda çöküş var) **sonuçla birlikte raporlanacak**; çok
  düşükse test güçsüzdür ve öyle yazılacak.

## Özellikler — veri görülmeden sabit

Hepsi o tarihte bilinen son bilanço/gelir tablosundan. İşaretler **çöküş
olasılığını AZALTACAK** yönde sabitlenmiştir (yani yüksek değer = daha güvenli).

### Ödeme gücü (muhasebenin asıl işi)

| # | özellik | mantık |
|---|---|---|
| S1 | −net borç / toplam varlık | Borçsuz şirket batmaz |
| S2 | cari oran (cari varlık / cari yükümlülük) | Kısa vadeli ödeme gücü |
| S3 | nakit / cari yükümlülük | En sert likidite ölçüsü |
| S4 | özkaynak / toplam varlık | Zarar yastığı |
| S5 | faaliyet nakit akışı / toplam borç | Borcu kaç yılda kapatır |

### Kâr kalitesi

| # | özellik | mantık |
|---|---|---|
| Q1 | net marj | Zarar yastığı, gelir tablosu tarafı |
| Q2 | −tahakkuk | Kâr nakde dönüyor mu |
| Q3 | −(şerefiye + maddi olmayan) / varlık | Değer düşüşü riski taşıyan varlık payı |

### Bedava kontrol — asıl rakip

| # | özellik | |
|---|---|---|
| V1 | −oynaklık (120 seans) | **Bu testin gerçek rakibi** |
| V2 | −son 12 ayın maksimum düşüşü | Fiyattan, bedava |

### Bileşik

| # | |
|---|---|
| D1 | S ve Q ailelerinin rank ortalaması (V hariç) — **yalnız muhasebe** |

Ağırlıklar eşit, işaretler yukarıda sabit, sonuç görüldükten sonra
değiştirilmez.

## İstatistik

Çöküş göstergesi ikili (0/1). Spearman(özellik, gösterge) kullanılır — ikili
hedefte bu rank-biserial korelasyondur ve AUC ile tekdüze ilişkilidir, yani
bugüne kadarki çerçeveyle **doğrudan karşılaştırılabilir** kalır.

Açıklama takvim çeyreğine göre kümelenmiş permütasyon, 10.000 tekrar.
**t, null'ın merkezine göre** ([olcum-metodolojisi.md](olcum-metodolojisi.md)
0d-2). Çoklu test: 11 özellik üzerinde max |t| aile düzeltmesi.

Ayrıca yorumlanabilir bir sayı: **en riskli üçte birde çöküş oranı ÷ en güvenli
üçte birde çöküş oranı** (yani "2,8 kat" tipi rakam).

## ZORUNLU İKİNCİ AŞAMA — oynaklığın üstüne katkı

Bu adım atlanamaz ve sonucun asıl kısmıdır.

Muhasebe bileşiği (D1) tek başına eşiği geçse bile, **oynaklık sıralaması
çıkarıldıktan sonra** hâlâ ayırıyor mu ölçülür: D1'in V1'e göre kalıntısı
alınır ve çöküş göstergesine karşı ayrıca test edilir.

Gerekçe: bugün üç kez, bir sinyalin tahmin edilebilir bileşeni sıfır kazandırdı.
Burada aynı mantık geçerli — oynaklığın zaten söylediğini muhasebeyle tekrar
söylemek yeni bilgi değildir.

## Karar kuralı

1. **D1 aile eşiğini geçer VE oynaklık kalıntısında da ayırır** → muhasebe
   çöküşü bağımsız olarak görüyor. Sonraki adım: eleme kuralı, kendi ön kaydıyla.
2. **D1 geçer ama kalıntıda ayırmaz** → muhasebe, oynaklığın söylediğini
   tekrarlıyor. Bedava aracı kullan, tablo okuma.
3. **D1 geçmez** → muhasebe çöküşü bu örneklemde ayırt etmiyor.
4. **Yalnız V1/V2 geçer** → beklenen sonuç; oynaklık zaten biliniyordu ve bu
   yeni bir bulgu değildir.

## Önceden reddedilenler

- Eşik taraması yok: yalnız −%20 ve −%30, ikincisi karar vermez.
- Ufuk taraması yok: yalnız 63 seans.
- Sektör, büyüklük, dönem kırılımı yok.
- Bileşiğin ağırlıkları sonradan ayarlanmaz.
- Tek tek geçen özellik seçilip bileşik yerine konmaz.
- Taban oranı düşük çıkarsa telafi edilmez; güçsüzlük olarak raporlanır.

## Bilinen sınırlar, şimdiden

- **Bilanço kapsaması ~%50**: 10-Q karşılaştırma artifact'ları bilinçli olarak
  bilanço taşımıyor, bu yüzden S ailesi Q ailesinden daha az gözlemde
  ölçülecek.
- 60 şirket, 2020-2026, ABD büyük sermaye. **Bu evrende gerçek iflas yok** —
  ölçülen şey batma değil sert düşüş. Gerçek ödeme gücü krizleri küçük sermayede
  ve kredi piyasasında olur; bu test onu görmez.
- `financial_expense` metriği ABD artifact'larında yaygın değil, bu yüzden faiz
  karşılama oranı **yok**. Ödeme gücü ailesinin en doğrudan ölçüsü eksik ve bu
  bir kapsama boşluğudur.
