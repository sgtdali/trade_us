# Ön kayıt — fiyat neyi ima ediyor: inanmamak mı, düşük değer biçmek mi

**Yazılma tarihi:** 2026-08-07
**Durum:** Hiçbir ima edilen değer hesaplanmadan, hiçbir getiriyle
eşleştirilmeden yazıldı.

## Test edilmemiş iki değişken

[us-forward-valuation-result.md](us-forward-valuation-result.md) beklentiye göre
değerlemeyi test etti ve null çıktı (F1 ρ −0,088, F3 ρ −0,005, hiçbiri aile
eşiğini geçmedi). **O test kesitseldi**, yani "akranlara göre" karşılaştırmasını
örtük olarak zaten yapıyordu.

Yapmadığı iki şey var:

### 1. Şirketin KENDİ tarihine göre konum

Kesitsel sıralama, bir şirketin evrende nerede durduğunu ölçer. Kendi geçmişine
göre nerede durduğunu ölçmez. Bunlar farklı:

```
sirket 8,6x'te islem goruyor
  herkes 8x'teyken        -> normal
  kendi medyani 11,5x iken -> baska bir sey
```

### 2. Sapmanın KAYNAĞI — inanmamak mı, iskonto mu

Asıl yeni olan bu. Bir hisse ucuz görünüyorsa iki farklı sebebi olabilir ve
şimdiye kadar ayırmadık:

```
ima edilen kâr = fiyat / (sirketin KENDI tarihsel medyan carpani)

A) ima edilen kâr <<  yonlendirme  -> piyasa TAHMINE inanmiyor
B) ima edilen kâr ==  yonlendirme  -> inaniyor, ama CARPANI dusuruyor
```

(B)'de piyasa kârı kabul edip **sürdürülebilirliğini** ya da kalitesini
cezalandırıyor olabilir: borç, marj baskısı, capex, risk primi.

Bu ayrım, F1-F4'ün hiçbirinin sorduğu soru değildi — onlar toplam sapmayı
ölçüyordu, bu **sapmanın kaynağını** ayırıyor.

## Değişkenler — veri görülmeden sabit

Her açıklama anında, o anda bilinenle. Panel
[us-forward-valuation-result.md](us-forward-valuation-result.md)'deki 487
olaylık panelin aynısı.

- **ileri çarpan** = fiyat / yönlendirme orta noktası
- **kendi tarihsel medyanı** = o şirketin **bu tarihten ÖNCEKİ** ileri
  çarpanlarının medyanı. En az 4 önceki gözlem şartı; yoksa gözlem düşer.
  Geleceğe bakmamak için medyan yalnız geçmiş gözlemlerden kurulur.
- **ima edilen kâr** = fiyat / kendi tarihsel medyan çarpanı

| # | değişken | tanım | mantık |
|---|---|---|---|
| **I1** | kendi tarihine göre ucuzluk | (tarihsel medyan çarpan − güncel çarpan) / tarihsel medyan | Kendi bandının altında |
| **I2** | inanmama açığı | (yönlendirme − ima edilen kâr) / yönlendirme | Fiyat, yönlendirmenin altında bir kâr fiyatlıyor |
| **I3** | çarpan cezası | −(güncel çarpan − evren medyan çarpanı) / evren medyanı | Kâr kabul ediliyor ama çarpan düşük |
| **I4** | çarpan bandındaki konum | güncel çarpanın kendi geçmiş dağılımındaki yüzdelik dilimi | I1'in dağılıma duyarlı hâli |

İşaretler **pozitif** sabitlenmiştir: yüksek değer = daha ucuz = yüksek sonraki
getiri beklenir.

**I2 ve I3 birlikte okunur.** Aynı toplam sapma, farklı kaynaklardan gelebilir
ve hipotez ikisinin **farklı** sıraladığıdır.

## İstatistik

Havuzlanmış Spearman, açıklama takvim çeyreğine göre kümelenmiş permütasyon,
10.000 tekrar, **t null'ın merkezine göre**
([olcum-metodolojisi.md](olcum-metodolojisi.md) 0d-2). Çoklu test: 4 değişken
üzerinde max |t| aile düzeltmesi.

**Ufuk: 63 seans** (değerleme sinyalleri yavaştır; F testinde de böyleydi).
İkincil, karar vermez: 21 seans.

**Ekonomik eşik:** üst-alt üçte bir farkı çift yönlü %0,20'nin altındaysa
pratik olarak ölüdür.

**Nokta-zaman kontrolü zorunlu:** `giriş − yönlendirme tarihi` ve tarihsel
medyanın **yalnız önceki** gözlemlerden kurulduğu ayrıca raporlanacak.

## ÖNSEL — aleyhte, ve şimdi yazılıyor

Aynı panelde dört değişken zaten null çıktı. Yasa üç kez doğrulandı: tahmin
edilebilen fiyatta. **Kendi tarihine göre konum da kamuya açık bir hesap** —
herkesin yapabildiği bir şey.

Beklentim null. Bu testin değeri, **daha önce hiç ayrılmamış bir ayrımı**
(inanmamak vs iskonto) ölçmesi; sonucun pozitif çıkma ihtimali yüksek olduğu
için değil.

## Karar kuralı

1. **Herhangi bir değişken aile eşiğini geçer ve fark > %0,20** → o değişken
   için ayrıştırma (tahmin edilebilir / kalıntı) **zorunlu**, sonra portföy
   kuralı kendi ön kaydıyla.
2. **I2 geçer, I3 geçmez** → piyasanın tahmine inanmadığı durumlar
   ayırıyor; sürdürülebilirlik cezası ayırmıyor.
3. **I3 geçer, I2 geçmez** → tersi.
4. **Hiçbiri geçmez** → yasanın dördüncü doğrulaması; ayrım gerçek ama
   getiriyle ilişkisiz.

## Önceden reddedilenler

- Eşik/kesme noktası aranmaz.
- "Normal çarpan" olarak sektör ortalaması **kullanılmaz** — sektör tanımı bir
  seçim ve sonucu ona duyarlı kılar. Anchor olarak yalnız (a) şirketin kendi
  geçmişi ve (b) evren medyanı kullanılır, ikisi de tanım gerektirmez.
- Ufuk taraması yok.
- Uç dilimler ayrı test edilip ana sonuç yerine konmaz.
- Ağırlık ya da işaret sonradan değiştirilmez.

## Bilinen sınırlar

- **Tarihsel medyan zayıf**: şirket başına en fazla ~20 çeyrek, çoğunda daha az.
  4 gözlemlik asgari şart düşük ve medyanı gürültülü kılar. Bu, I1 ve I4'ü
  zayıflatır ve kapsama ile birlikte raporlanır.
- 60 şirket, 2020-2026, ABD büyük sermaye.
- Yönlendirme, analist konsensüsünün vekili. Gerçek konsensüs vintage'ı
  2026-08-07'den itibaren birikiyor ama geçmişe dönük yok.
- Bu test **betimleyici iddiayı** test etmiyor. "Fiyatın konsensüse göre nerede
  durduğunu tarif edebiliriz" ayrı bir şeydir ve bu testin sonucundan bağımsız
  olarak doğrudur; burada ölçülen tek şey o tarifin **sonraki getiriyi sıralayıp
  sıralamadığı**.
