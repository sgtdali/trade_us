Zarf ve depolama net. Özellikle şunlar kalıcı: tek primary subject + `related_refs`; `authority_basis`'in ayrık nesne olması (her olayda authority ref taşımak yerine); `sequence`'ın domain zarfında değil storage metadata'sında olması; batch'te `pending/committed` durumu TUTULMAMASI (transaction başarılıysa batch vardır, değilse hiç yoktur); `BEGIN IMMEDIATE` + unique constraint'lerin dosya kilidinden daha basit ve daha doğru olması; ve "WAL correctness sağlamaz, transaction ve constraint'ler sağlar" düzeltmesi. Yedi maddelik altyapı kabul testi de doğrudan uygulanabilir.

Şimdi kritik bir soru: BU KADAR YÜZEYİN NE KADARI GERÇEKTEN İLK SÜRÜMDE GEREKLİ?

Son beş turda çok şey tanımladık: ~30 şema, dört governance belgesi, risk snapshot'ın onlarca alanı, proposal'ın seçenek yapısı, icra zinciri, validation spec. Sen 16. ve 31. turlarda iki kez "erken kurumsallaştık" dedin ve haklıydın. Şimdi aynı riski şema tarafında taşıyoruz.

O yüzden bu turda kesme yapmanı istiyorum:

(1) İLK ÇALIŞAN DİLİM İÇİN ASGARİ ŞEMA SETİ. Hedef şu: kullanıcı açılış kitabını içeri alabiliyor, pozisyon ve nakit projection'ı çalışıyor, NAV hesaplanıyor, ve bunlar replay edilebiliyor. Bu kadarı için hangi şemalar ZORUNLU? Hangileri stub olarak (yalnız kimlik + birkaç alan) başlayabilir? Hangileri hiç yazılmadan devam edilebilir?

Bunu üç kovaya ayır: **şimdi tam yazılacak**, **stub olarak yazılacak** (alan eklemesi geriye uyumlu olacak şekilde), **hiç yazılmayacak**.

(2) BÜYÜK ŞEMALARIN KÜÇÜK BAŞLANGICI. `portfolio_risk_snapshot` ve `portfolio_proposal` çok geniş çıktı. Bunların V0 hâli ne olmalı -- tam şemanın hangi alt kümesi? Örneğin risk snapshot'ta `causal_driver_exposures` ve `scenario_results` V0'da gerekli mi, yoksa yalnız pozisyon/nakit/limit yeterli mi? Ve proposal'da alternatifler V0'da olmalı mı, yoksa önce yalnız `status_quo` + `primary` mi?

Geriye uyumluluk açısından şuna dikkat et: sonradan alan EKLEMEK ucuz, ama bir alanı sonradan ZORUNLU yapmak veya anlamını değiştirmek pahalı. Yani V0'da hangi alanları şimdi doğru koymak zorundayız, hangileri sonra eklenebilir?

(3) ŞEMA YAZMANIN KENDİSİ NE KADAR SÜRER? Bu turlarda tanımladıklarımızın hepsini JSON Schema olarak yazmak kaç günlük iş? Ve bunun ne kadarı Claude/codex ile hızlanır, ne kadarı hızlanmaz? (Örneğin şema yazmak hızlanır ama hangi alanın gerçekten gerekli olduğuna karar vermek hızlanmaz.)

(4) VE DÜRÜST BİR SORU: bu şema seti fazla mı? Tek operatörlü bir sistem için `binding_state` altı değerli enum, `constraint_type` on bir değerli enum, `related_refs` ilişki tipleri... Bunların hangileri gerçek bir hatayı önlüyor, hangileri sadece iyi mimari hissi veriyor? Kesecek olsan neyi keserdin?
