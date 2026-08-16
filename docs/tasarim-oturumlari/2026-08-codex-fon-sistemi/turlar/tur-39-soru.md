Köprü bölümünü olduğu gibi alıyorum. "Broker pozisyonun VARLIĞINDA otoritedir; sistem pozisyonun MEŞRUİYETİNDE otoritedir" cümlesi planlanmamış işlem sorununu tam çözüyor -- gerçeği reddetmeden, policy zincirini de boşa düşürmeden. `validity_contract` (fiyat bandı + ağırlık bandı + downside bütçesi kesişimi), adedin icra anında türetilmesi, fill'lerin ayrı kanonik kayıt olması, reconciliation'ın tek boolean olmaması ve statement importer'ın en yüksek getirili tek yatırım olması -- hepsi net.

Şimdi son büyük parçaya geliyoruz: ARAŞTIRMA İLE SERMAYE ARASINDAKİ GERİ BESLEME. Bu döngü kapanmazsa elimizde birbirine bakan iki ayrı sistem kalır; kapanırsa fon olur.

Burada bence gerçek bir gerilim var ve tasarımın hiçbir yerinde çözülmedi:

Araştırma sermayeyi ÖNCELEMELİ (boru hattı olmadan fırsat çıktığında hazır isim olmaz, hep geç kalınır) ama araştırma kapasitesi sermayeyi TAKİP ETMELİ (asıl korunması gereken şey zaten sahip olduğun paradır). Haftada 6-9 saat var ve bu iki ihtiyaç aynı saatler için yarışıyor.

Sorularım:

(1) ARAŞTIRMA KUYRUĞU NEYE GÖRE SIRALANMALI? Bugüne kadar araştırmayı keşif ritmi belirliyordu (turlar, batch'ler). Fon çerçevesinde bunun yanlış olduğunu düşünüyorum: sıralamayı RİSK ALTINDAKİ SERMAYE belirlemeli. Yani en çok sermaye bağlı olan ve en çok belirsizlik taşıyan isim, hiç sahip olmadığın parlak bir fikirden önce gelir. Ama bu kural tek başına uygulanırsa boru hattı ölür ve fon hiç yeni isim bulamaz. İkisini nasıl dengelersin -- sabit bir kapasite ayrımı mı (ör. saatlerin %70'i mevcut kitap, %30'u keşif), yoksa duruma bağlı bir kural mı?

(2) "INVESTABLE SET" KAVRAMI. Fon çerçevesinde araştırmanın kapsamı daralmalı gibi: sermaye alamayacak bir ismi araştırmak boşa emek. Ama "sermaye alabilir" ne demek -- policy'ye uygun (long-only, adi hisse, ABD), likidite kapasitesi yeterli, gap risk sınıfı kabul edilebilir, ve pozisyon tavanı dolu değilse. Bu bir ön eleme olarak keşif hattının BAŞINA konmalı mı? Eğer öyleyse 87 isimlik evrenin ne kadarı elenir sence, ve bu eleme deterministik yapılabilir mi?

(3) SERMAYE DOLUYKEN KEŞİF ANLAMLI MI? On pozisyon tavanı dolu, nakit yok, replacement hurdle yüksek. Bu durumda yeni isim aramak mantıklı mı? İki görüş var: hayır (nasılsa alamayacaksın, emeği mevcut kitaba harca), ya da evet (hurdle'ı geçecek isim ancak arayarak bulunur ve statüko tembelliğe dönüşür). Ben ikincisinin doğru olduğunu ama YOĞUNLUĞUN azalması gerektiğini düşünüyorum. Sen ne dersin, ve keşif yoğunluğu portföy durumuna göre otomatik ayarlanmalı mı?

(4) TERS YÖNDE: PORTFÖY ARAŞTIRMAYA NE SÖYLER? Bir pozisyon kayıp bütçesinin yarısını yemişse, ya da bir driver'a yoğunlaşma limite yaklaşmışsa, ya da bir tez `review_required` olmuşsa -- bunlar araştırma için birer görev üretir. Yani portföy risk motoru araştırma kuyruğunun en büyük müşterisi olur. Bu görevlerin önceliği tez sağlığı kontrolünden farklı mı olmalı?

(5) VE EN ÖNEMLİSİ: HANGİ ARAŞTIRMA GERÇEKTEN SERMAYE KARARINI DEĞİŞTİRİR? Bir araştırma çalışması, sonucunda hiçbir sermaye kararı değişmeyecekse yapılmamalı. Bu, "karar-değeri" (value of information) testi. Sistem bunu önceden sorabilir mi -- ör. bir iş kalemi açılmadan önce "bu çalışmanın sonucu hangi kararı nasıl değiştirebilir" alanını zorunlu kılmak? Bu fazla bürokratik mi olur, yoksa 6-9 saatlik bir bütçede en gerekli filtre mi?
