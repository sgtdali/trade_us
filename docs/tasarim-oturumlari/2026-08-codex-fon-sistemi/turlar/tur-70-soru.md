Nesne modeli net: 7 şemalı kayıt + iki basit operasyon tablosu. Dispatch kurallarının kodda kapalı tablo olması gerekçesiyle birlikte doğru -- "dispatch kuralı otomatik LLM çağrısı, maliyet ve iş üretme yetkisi veriyor; keyfî config'e açılırsa farkında olmadan küçük bir kural dili ve yetki sistemi kurmuş oluruz." Monitoring'in iki kez doğrulanması (yazım + çalışma anı) ve uyumsuzlukta `unavailable` üretmesi de doğru.

12-16 iş günü ilk dikey dilim, 20-28 iş günü sekiz tezi işleten sürüm, 5-8 takvim haftası. Ve Adım 9'un kritik eşik olması: "Adım 8'de otomasyon elle başlatıldığında çalışır; Adım 9'dan sonra zamanı ve kanıtı kendisi gözleyip işi kendisi başlatır."

İki tur kaldı. Bu turda otomasyonun KENDİ risklerine bakalım, çünkü şimdiye kadar hep faydasını konuştuk.

(1) BU OTOMASYON BİR YIL ÇALIŞTIKTAN SONRA NE BOZULUR? Somut bozulma yolları görüyorum: metrik eşlemeleri (şirket segment yapısını değiştirir, XBRL etiketi değişir, non-GAAP tanımı kayar), plugin sürümü değişir ve skill çıktısı contract'ı bozar, dispatch kuralları bayatlar (bir kural artık hiç ateşlemiyor ya da sürekli ateşliyor ama kimse fark etmiyor), fiyat/veri kaynağı sessizce değişir. Bunların hangisi gerçekten olur ve sistem bunları kendi kendine fark edebilir mi?

Özellikle şu sinsi: **bir monitoring kuralı sessizce hiç ateşlememeye başlarsa** (metrik artık üretilmiyor, `unavailable` dönüyor ama kimse bakmıyor) tez izlenmiyor demektir ama sistem "sorun yok" görünür. Bunu nasıl yakalarız?

(2) İNSAN PASİFLEŞİR Mİ? 57. turda törensel onay riskini konuşmuştuk. Şimdi risk daha büyük: sistem artık önüne doldurulmuş bir hüküm getiriyor ("readiness core → starter, downside -%24 → -%31, tez review_required"). Boş forma bir şey yazmak ile hazır bir öneriyi onaylamak arasında büyük fark var -- ikincisinde insan gerçekten düşünüyor mu, yoksa okuyup [Accept] mi diyor?

Bu, otomasyonun getirdiği en gerçek bedel olabilir: hatırlama yükünü aldık ama yargı kalitesini düşürdük. Bunu ölçmenin veya azaltmanın bir yolu var mı, yoksa kabul edilmesi gereken bir takas mı?

(3) YANLIŞ ALARM ORANI NE OLUR VE NE ZAMAN SORUN OLUR? Tez başına 2-4 mekanik kural, 8 tez, yılda 2-4 filing. Kaç `breached` bekliyoruz ve bunların kaçı gerçekten anlamlı olur? Eğer her çeyrek 3-4 sahte alarm geliyorsa insan kısa sürede hepsini [Accept] etmeye başlar ve mekanizma ölür. Eşikleri baştan doğru koymanın bir yolu var mı, yoksa ilk yıl kalibrasyon dönemi mi sayılmalı?

(4) VE KALAN SINIR: şu an neyi hâlâ otomatikleştirmiyoruz ve bu dürüst mü? Aklımdakiler: discovery/yeni aday üretimi (12. adımda), portfolio proposal (birden fazla seçenek üretme), attribution/counterfactual, A0-A4 yetki merdiveni, capital_input_manifest. Bunların ertelenmesi kullanıcının itiraz ettiği türden bir erteleme mi, yoksa gerçekten sıralama meselesi mi? Her biri için tek cümleyle gerekçe ver -- ve eğer birinde "aslında bu da ertelenmemeli" diyorsan söyle.
