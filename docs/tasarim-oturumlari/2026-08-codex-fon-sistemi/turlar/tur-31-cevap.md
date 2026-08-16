Bence eleştirin haklı: on üç turda doğru bir hedef mimari çizdik, fakat onu henüz hak edilmemiş biçimde “V1” diye adlandırdık. Bugün yapılması gereken platform inşası değil, mevcut hattın güvenli bir araştırma tezgâhına dönüştürülmesidir.

## 1. Triyaj kanıt değil, hipotez

Skill metinlerini okumak üç şeyi kanıtlar: skill hangi sorunun sahibi olduğunu iddia ediyor, hangi girdileri bekliyor ve hangi çıktıyı vaat ediyor. Şunları kanıtlamaz:

- Bizim verimizle kaliteli çalıştığını,
- insanın kullanabileceği çıktı verdiğini,
- başka skill’lerle birleştiğinde hata büyütmediğini,
- haftalık kapasiteye uyduğunu,
- aynı vakada tutarlı ve tekrarlanabilir olduğunu.

En pahalı yanlış çıkabilecek karar, **`long-short-pitch`in çekirdek ve tek tez-açıcı analitik adım olmasıdır**. Çünkü bütün V1 değeri `pitch → adjudication → thesis_opened → monitoring` hattına dayanıyor ve pitch prodüksiyonda bir kez bile çalışmadı. Pitch kötü çıkarsa yalnız bir adapter değil; tez sözleşmesi, izleme sözleşmesi, insan kapısı ve tracker girdisi birlikte yanlış tasarlanmış olur.

Bunu erken anlamanın yolu entegrasyon değil, üç vakalık gölge koşudur:

- Biri görece basit ve yerleşik şirket,
- biri NVDA gibi beklenti/opsiyonellik ağırlıklı şirket,
- biri veri veya segment yapısı zor şirket.

Her vakada mevcut artefaktlarla pitch elle çalıştırılır; deftere yazılmaz. Şunlar ölçülür: karar sözlüğüne uyum, valuation anchor’ın gerçekten desteklenmesi, falsifier kalitesi, eksik kanıtı dürüstçe `blocked` sayabilme, ikinci koşuda temel hükmün kararlılığı ve insanın düzeltmek için harcadığı süre. Üç vakadan ikisinde ağır yeniden yazım gerekiyorsa pitch çekirdek değildir; yalnızca değiştirilebilir bir sağlayıcı adayıdır.

Tracker da aynı testi bir tarihsel filing üzerinde geçmeli. Ancak tracker’ın başarısızlığı daha ucuzdur: domain modeli doğru tutulduysa tracker başka prompt veya insan değerlendirmesiyle değiştirilebilir. Pitch başarısızlığı daha yapısaldır.

## 2. Support çağrısı teknik olarak nasıl gerçekleşir?

Lead kendi oturumunun içinde başka Codex çağrısı yapmamalı. Bu hem gizli maliyet hem de denetlenemeyen iç içe orkestrasyon üretir.

Doğru mekanizma şu:

1. Lead, yapılandırılmış bir `support_request_proposed` döndürür: ihtiyaç duyulan yetenek, cevaplanacak dar soru, mevcut artefakt referansları ve neden mevcut kanıtın yetmediği.
2. Lead denemesi biter; episode `awaiting_support` olur.
3. Orkestratör öneriyi izin listesi, bütçe ve döngü kurallarına karşı doğrular.
4. İzin verilen ilk support için ayrı `workflow_request_id` ve `attempt_id` açılır; support taze oturumda çalışır.
5. Doğrulanan support çıktısı vakaya provisional evidence olarak bağlanır.
6. Lead, yeni bir attempt olarak bu artefakt eklenmiş context bundle ile yeniden çalışır.

Dolayısıyla lead’in “atama” yetkisi gerçekte **ihtiyaç bildirme yetkisidir**; yürütme yetkisi orkestratördedir. İlk sürümde bunu genel bir motor yapmak da gereksizdir: yalnız pitch için en fazla bir otomatik support, support’un başka support isteyememesi ve başarısız support sonrası `blocked` zorunluluğu yeterlidir.

## 3. Yeniden erken kurumsallaştık

Evet. Sekiz bölümlü katalog ve yedi pack sözleşmesi hedef mimari için makul, fakat ilk çalışan sürüm için ağır.

Şimdi gerçekten gerekenler:

- İş, attempt ve artefakt kimliklerinin ayrılması.
- Her koşunun girdilerini ve hash’lerini taşıyan basit bir run manifesti.
- `date_due` güvenlik kilidi.
- Karar-kritik üç çalışma için dar sidecar: deep-dive, pitch, tracker.
- Bu üçü için şema doğrulaması ve birkaç açık semantik kural.
- Pitch ile tracker’ın domain etkisinden önce insan kapısı.
- Pitch’in en fazla bir support isteyebilmesi.
- Mevcut defterde seri commit veya aynı anda ikinci writer’ın engellenmesi.

Sonraya bırakılabilecekler:

- Yedi ayrı, genel amaçlı ve sürümlü pack ailesi.
- Sekiz bölümlü jenerik katalog şeması.
- Rol × reliance model matrisi; başlangıçta workflow başına sabit model yeterli.
- Genel support-policy grafiği ve capability resolver.
- Bağımsız `contract_manifest` sistemi; ilk aşamada run manifestinin alanı olabilir.
- Yeniden kullanılabilir validator kural dili.
- On skill’in tamamının entegrasyonu.
- Tam P0–P4 uygulaması; geçici statik HTML’de üç kuyruk sınıfı yeterlidir.
- Provider-independent adapter framework; önce gerçekten ikinci sağlayıcı ihtiyacı görülmeli.

Dört aşamalı sözlük de kavramsal olarak korunabilir ama dört ayrı altyapı servisi gerektirmez. Bir iş kaydındaki dört zaman/sonuç alanı yeterlidir: süreç bitti mi, kontrat geçti mi, insan hükmetti mi, domain’e yazıldı mı?

## 4. Platform yerine yamalı mevcut sistem

Burada seçimim net: **9–12 haftalık platform inşasını şimdi başlatmaz, mevcut sistemi kademeli güvenlik yamalarıyla kullanırdım.**

Fakat “bugünkü sistem çalışıyor” cümlesini dar anlamda kabul ederim. Sistem analiz artefaktı üretiyor; araştırma lifecycle’ı çalıştırmıyor. On bir adaydan hiçbiri pitch’e ulaşmadı, hiçbir tez açılmadı, comps amacı kayboldu ve bekleyen tetikleyiciler kanıtsız ateşleyebiliyor. Dolayısıyla korunması gereken şey mevcut lifecycle değil, mevcut **analiz üretme kapasitesidir**.

Öncelikli yamalar şunlar olmalı:

1. `date_due` otomatik workflow hazırlayamaz.
2. Eksik ticker sessizce atlanamaz; eksik bucket `B` olamaz.
3. Açılan vakanın lead amacı support sonucu tarafından değiştirilemez; `requested_workflow=comps` kaybolamaz.
4. Deep-dive yapılandırılmış sidecar olmadan domain-complete sayılamaz.
5. Pitch ve tracker üçer gölge koşuda sınanmadan lifecycle’a bağlanamaz.
6. Aynı anda iki ledger writer engellenir.

Bundan sonra iki gerçek earnings döngüsü boyunca artefakt kalitesi, hata oranı, insan süresi ve support ihtiyacı ölçülür. Ölçüm sonunda platform gereksinimleri büyük ihtimalle bugünkü tasarımdan daha küçük çıkar. Çıkmazsa da artık 9–12 haftalık yatırımın dayandığı gerçek kanıt vardır.

Bu seçimin bedeli, birkaç ay boyunca tam tez lifecycle’ının olmamasıdır. Kazancı ise sıfır tezli bir sistem için yanlış soyutlamaları kalıcı veri modeline gömmemektir. Bence doğru takas budur.

## Ek zayıflıklar

Senin dört maddene üç tane eklerim:

- **Başarı ölçütümüz yok.** “Kontrata uydu” ile “yatırım araştırmasına değer kattı” farklıdır; skill başına küçük bir insan puanlama rubriği olmadan model/effort kararları süslü tahmindir.
- **Aynı sağlayıcıdan gelen lead ve support bağımsız kanıt değildir.** Comps ile pitch aynı varsayımı tekrar ederek sahte teyit üretebilir; support’un kaynak ve varsayım farkı görünür olmalıdır.
- **Plugin sürümüne aşırı yapısal bağlanma riski var.** Sağlayıcının bugünkü enum’larını, artefakt hiyerarşisini ve routing dilini domain şemasına kopyalarsak “değiştirilebilir sağlayıcı” iddiamız kâğıt üzerinde kalır.

## Tek tavsiyem

**Platformu şimdi kurmayın; mevcut hattı domain’e yanlış gerçek yazamayan bir araştırma tezgâhına dönüştürün ve pitch–tez–tracker dikey dilimini üç gölge vaka ile kanıtlamadan hiçbir skill mimarisi kararını kalıcılaştırmayın.**