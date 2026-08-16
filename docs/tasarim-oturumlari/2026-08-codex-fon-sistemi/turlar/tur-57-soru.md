Bu turun iki çıktısı bence kalıcı: (a) görünürlüğün skill adına değil `(skill, execution_role, requested_capability, assessment_mode)` bileşimine bağlı olması ve kapalı overlay profilleri (`none` / `funded_flag_only` / `position_context` / `portfolio_exposure_context`); (b) **sermaye tutarının modele GÖSTERİLMEMESİ, yalnız orkestratörün assurance/öncelik kararını etkilemesi** -- "82 bp sermaye risk altında" demek downside analizini iyileştirmez, modeli pozisyonu savunmaya teşvik eder. Sahiplik yanlılığını böyle kesmek doğru.

Üç assessment modu (`de_novo` / `update_against_prior` / `independent_then_reconcile`) anchoring sorununu çözüyor; `contract_manifest` ile `model_input_manifest`'in AYRI olması ("hangi kurallar uygulandı" vs "model tam olarak ne gördü") da önemliydi. Ve "portföy bağlamı görmüş bir thread daha sonra blind çalıştırılamaz, model bilgiyi unutmuş sayılamaz" kuralı.

Üç tur kaldı. Şimdi SINIRDAKİ HATA MODLARI ve İNSANIN GERÇEKTE NE YAPTIĞI.

(1) ADJUDICATION PRATİKTE NEYE BENZİYOR? Kullanıcı oturuyor, önünde bir `proposed_downside_case` var. Tam olarak neyi yargılıyor ve neyi göremiyor? Somut sor: ekranda ne olmalı, kullanıcı hangi soruları kendine sormalı, ve bu ne kadar sürer? Bir downside case'i kabul etmek 5 dakika mı 30 dakika mı? Çünkü haftada 6-9 saat bütçe var ve bu kapı her sermaye kararının önünde duruyor.

Ve alt soru: kullanıcı "kabul ediyorum ama sayıyı değiştiriyorum" derse ne olur? 27. turda override kurallarını konuşmuştuk (olgusal hatalar override edilemez, reddedilir). Downside case için bu nasıl işliyor -- %25 yerine %35 yazmak bir override mı, yoksa yeni bir insan-kaynaklı downside case mi?

(2) SKILL ÇÖP DÖNDÜRÜRSE. Validator şemayı ve invariant'ları kontrol ediyor, ama şema-valid ve anlamsız bir çıktı mümkün: uydurulmuş bir peer seti, kaynağı olmayan bir sayı, ya da tezle alakasız bir downside senaryosu. Bunu yakalamanın deterministik bir yolu var mı, yoksa tamamen insana mı kalıyor? Ve tekrar eden düşük kalite nasıl görünür olur -- yani "bu skill bu iş için işe yaramıyor" hükmü nereden çıkar?

(3) ARAŞTIRMA KİTABI YALANLARSA. Somut senaryo: tracker "tez bozuldu" diyor ama pozisyon kârda ve fiyat yükseliyor. Ya da tam tersi: tez sağlam diyor ama pozisyon %40 düşmüş. Sistem bu çelişkiyi görüyor mu, göstermeli mi? Ben göstermesi gerektiğini düşünüyorum ama bir hüküm vermemeli -- fiyat tezin hakemi değil. Ama o zaman ne yapıyor: yalnız bir bayrak mı, yoksa zorunlu bir inceleme mi?

(4) BAYAT ADJUDICATION. Bir downside case üç ay önce kabul edildi, o zamandan beri iki çeyrek geçti. Manifest bunu `stale` gösteriyor ve yeni risk bloklanıyor. Ama kullanıcı hiçbir şey yapmıyor -- kuyrukta duruyor ama vakit bulamıyor. Zaman geçtikçe tüm kitap `stale` olur ve sistem hiçbir şey öneremez hâle gelir. Bu bir kilitlenme mi, yoksa doğru davranış mı? Ve eğer kilitlenmeyse çıkış yolu ne -- kullanıcı "bu downside'ı olduğu gibi uzatıyorum" diyebilmeli mi?

(5) VE EN SİNSİ OLANI: İNSAN HER ŞEYİ ONAYLIYORSA. 15. turda "sahte onay kapısı" riskini konuşmuştuk. Adjudication kapısı bu riskin tam merkezinde: kullanıcı yorulunca her `proposed_downside_case`'i tıklayıp geçebilir ve sistem hâlâ "insan adjudicate etti" der. Bunu tespit etmenin bir yolu var mı -- yoksa yalnız kullanıcının kendi disiplinine mi kalıyor?
