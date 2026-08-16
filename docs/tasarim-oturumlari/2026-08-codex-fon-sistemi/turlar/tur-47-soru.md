Mevcut gelenekleri doğruladım: valuation-common.schema.json zaten `utcInstant` (pattern tabanlı, `format`'a güvenmiyor), `isoDate`, `digest` (`sha256:` önekli), `contextId` taşıyor. Yani senin "pattern + runtime parser birlikte" önerinle repo zaten uyumlu.

Dört temsil ayrımını, "olay şeması otorite değil, kabul edilmiş olay örnekleri ve artefaktları otorite" düzeltmesini, projection'ın ne zaman şema gerektirdiğini, decimal string'i (minor-unit integer'ı reddederek), üç zaman tipini (`UtcInstant` / `LocalDate` / `MarketSessionDate`), "bugün kanonik veri alanı değildir" kuralını, UUIDv7'yi, üç seviyeli kimliği (issuer/security/listing) ve sürümlemenin üç ayrı anlamının (schema/policy/engine) karıştırılmamasını kabul ediyorum. Yazım sırasını da alıyorum.

Şimdi somut alanlara iniyoruz. Bu turda KİMLİK VE MUHASEBE OLAYLARI.

(1) ÜÇ SEVİYELİ KİMLİĞİN GERÇEK HÂLİ. `issuer_id` / `security_id` / `listing_id` ayrımını kabul ettim ama tek operatörlü, yalnız ABD adi hissesi tutan bir sistemde bu üçlü fazla ağır olabilir. Somut sor: bu ayrımın gerçekten işe yaradığı vakalar neler (ticker değişimi, sınıf A/C, spin-off, merger, ADR)? Ve V0'da üçünü de ayrı tablo/şema yapmak mı gerekiyor, yoksa tek `security` kaydı içinde issuer ve listing alanları taşımak yeterli mi -- sonradan ayrıştırmanın maliyeti ne olur?

(2) AÇILIŞ BAKİYESİ ÖZEL BİR SORUN. Kullanıcının hâlihazırda pozisyonları var ve bunların geçmiş işlemleri sistemde yok. Yani ilk kayıt bir işlem değil, bir İDDİA: "1 Eylül itibarıyla şu hesapta şu adet, şu maliyetle vardı, kaynağı şu ekstre." Bu, `fill` ile aynı şey değil -- maliyet temeli broker'dan geliyor ve doğrulanabilir bir işlem geçmişi yok. Bunu nasıl modellemeliyiz: ayrı bir `opening_balance_asserted` olayı mı, yoksa sentetik bir "opening fill" mi? İkisinin de sonuçları var: sentetik fill P&L'i bozar (hangi tarihten itibaren?), ayrı olay ise projection'ın iki farklı kaynağı olduğu anlamına gelir.

Ve devamı: açılış maliyeti bilinmiyorsa ne olur? Bazı pozisyonların maliyeti kayıp olabilir. `cost_basis_unknown` diye bir durum gerekir mi, ve o pozisyon için gerçekleşmiş P&L hesaplanamaz mı?

(3) MUHASEBE OLAY AİLESİ. Somut liste istiyorum: fon omurgasının V0'ında hangi olay tipleri var ve her birinin payload'ında ne var? Benim tahminim: `opening_balance_asserted`, `fill_recorded`, `cash_flow_recorded` (dış para giriş/çıkış), `dividend_recorded`, `fee_recorded`, `interest_recorded`, `corporate_action_applied`, `position_reconciled`, `cash_reconciled`. Dokuz tip. Eksik/fazla ne var, ve hangileri aynı aile dosyasında toplanmalı?

Özellikle şunu netleştir: temettü tek bir olay mı (brüt + stopaj + net), yoksa iki mi (gelir tahakkuku + vergi kesintisi)? Türk mukimi için stopaj var ve bu net nakdi etkiliyor.

(4) POZİSYON VE LOT PROJECTION'I. Bu türetilmiş ama şemalı olacak. İçinde ne var: security başına toplam adet, ortalama maliyet, açık lotlar, para birimi, son uzlaştırma tarihi, ve `position_state` (open / confirmed_flat / unknown / disputed). Lot'ların kendisi projection mı yoksa olay mı? Ben "fill'lerden türetilir, yani projection" diyorum ama satışta lot eşleştirmesi bir KARAR -- ve karar projection'da yaşayamaz. Bu ayrımı nasıl kesersin?

(5) Son olarak: bu şemaların hepsi `schemas/fund/` altında mı olmalı, yoksa mevcut düz `schemas/` yapısına mı eklenmeli? Repo şu an düz; alt klasör açmak tutarsızlık mı yaratır, yoksa 30 yeni dosya düz klasörü boğar mı?
