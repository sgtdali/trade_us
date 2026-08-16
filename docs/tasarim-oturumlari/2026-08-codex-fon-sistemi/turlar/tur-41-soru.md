Yeni inşa sırasını, "Adım 6'dan sonra kötü de olsa fon" eşiğini, süre tahminlerini (minimum fon omurgası 8-11 hafta, hedef sistem 16-24) ve ölen/değişen/ayakta kalan kararlar listesini olduğu gibi alıyorum. "Yanlış olan bu katmanların varlığı değil, ürünün merkezi sanılmalarıydı" cümlesi kullanıcıya sunacağım özetin omurgası olacak.

Son iki turda skill tarafını fon çerçevesine göre yeniden değerlendirip kapatalım.

(1) 23 SKILL'İN HÜKÜMLERİ DEĞİŞİYOR MU? Geçen tur 6 çekirdek / 3 koşullu / 1 escalation / 12 gereksiz / 1 meta demiştik. Ama o triyaj "araştırma sistemi" ölçütüyle yapılmıştı. Fon çerçevesinde bazı gerekçeler çürüyor gibi:

- `portfolio-risk-management`: zaten koşullu support'a döndü.
- `economic-impact-report`: "tema/makro subject modeli yok" diye gereksiz demiştik. Ama artık bir `risk_driver_registry`miz var ve portföy-geneli driver yoğunlaşmasını ölçüyoruz. Bir makro/politika şokunun birden fazla pozisyonu aynı driver üzerinden vurması artık BİRİNCİ SINIF bir risk sorusu. Bu skill'in subject'i artık var: driver. Hükmü değişiyor mu?
- `catalyst-calendar`: "deterministik next_events yeterli" demiştik. Ama artık karar son tarihleri (`decision_deadline`), olay-güdümlü proposal tetikleyicileri ve R2 öncelik sınıfı var. Katalizör takvimi artık sermaye kararı zamanlamasına bağlı. Değişiyor mu?
- `scenario-sensitivity-generator`: koşullu demiştik. Ama artık her pozisyon için downside senaryosu ZORUNLU (kayıp bütçesi ona dayanıyor). Yani senaryo üretimi artık opsiyonel bir süs değil, sizing'in girdisi. Çekirdek olması gerekmez mi?
- Workbook dörtlüsü (dcf, three-statement, equity-model-update, model-audit): fon çerçevesinde downside senaryosu ve valuation anchor daha kritik hâle geldi. Bu, "model gerekiyorsa tezi açma" kuralını zorlaştırıyor mu?

Her biri için net hüküm ver, ve değişmeyenleri de tek cümleyle teyit et.

(2) FONUN İHTİYACI OLUP HİÇBİR SKILL'İN KARŞILAMADIĞI ŞEYLER. Geçen tur araştırma tarafı için 18 maddelik bir platform işi listesi çıkarmıştın (F1-F18). Şimdi fon tarafı için aynısını istiyorum: portföy/sermaye/risk/performans/icra tarafında hiçbir skill'in yapmadığı, bizim yazmamız gereken işler. Boyut tahminiyle. Ve bu iki listenin (araştırma platformu + fon platformu) toplamının, sistemin gerçek büyüklüğünü ne yaptığını söyle.

(3) Ve bir soru: fon tarafında hiç LLM'e ihtiyaç var mı? Sermaye kararı deterministik motor + insan onayı olarak kurgulandı; risk motoru deterministik; NAV/performans deterministik; icra köprüsü deterministik. Geriye LLM'in yeri olarak yalnız araştırma alt sistemi kalıyor gibi görünüyor. Bu doğru mu, yoksa fon tarafında da LLM'in meşru bir işi var mı (ör. proposal gerekçesini insan diline çevirmek, driver etiketi önermek, uyuşmazlığın nedenini tahmin etmek)? Eğer varsa hangileri, ve hangileri kesinlikle LLM'e verilmemeli?
