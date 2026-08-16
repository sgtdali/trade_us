İyi liste. Üçüne katılıyorum, birinde seni düzelteceğim, bir de senin hiç dokunmadığın koca bir kör nokta var.

Katıldıklarım ve keskinleştirmek istediğim yer: (1) numaralı çift-defter sorunu bence sandığından daha temel. Bu repoda events.jsonl tek gerçeklik kaynağı; thesis-tracker'ın kendi JSONL'i o zaman ne? Ben "tez defteri events.jsonl'den TÜRETİLİR, kendi başına otorite değildir" demenin tek tutarlı yol olduğunu düşünüyorum -- yoksa iki append-only defter arasında iki-fazlı commit problemi icat etmiş oluruz ki bu ölçekte saçma. Sen "hangisi otoritatif" diye sordun ama cevabını vermedin; senin cevabın ne? Ve idempotency noktan doğru: aynı pitch result'ı iki kez attach edilirse ne olur, bunun anahtarı ne olmalı?

(4) numaran benim de listemdeydi ama sen onu "in_progress anı" olarak dar tuttun. Daha geniş bir hâli var: zincirin ORTASINDAKİ isim. Tez ancak pitch'ten sonra açılıyor; yani tearsheet+comps bitmiş, pitch sırada bekleyen bir isim tez sahibi DEĞİL, dolayısıyla Başlık 3'ün "keşif havuzu = evren − açık tezliler" kuralına göre bir sonraki tura tam yetkiyle girer. Yeni tur onu C yaparsa iki adımlık tamamlanmış iş bayatlar ve çöpe gider. Yani hariç tutma kuralı yanlış eksende: "tezi var mı" değil, "aktif bir araştırma zinciri var mı" diye sormalı. Bunu nasıl görüyorsun -- keşif havuzundan hariç tutma kriterini değiştirmek mi, yoksa zincirdeki isimleri taramaya sokup sonucu farklı işlemek mi?

Seni düzelteceğim yer (5): bucket/setup'ın veri tazeliğini göstermediği doğru, ama "iki ayrı bayatlama ekseni var" demek yerine tek cümleyle söyleyeyim -- completed_workflows'un hangi VERİ DÖNEMİYLE tamamlandığını taşımaması bir tasarım kararı değil, sadece eksik alan. Yani bu senin dediğin gibi kararla çelişki değil, kararın uygulanamaz olması. Fark önemli çünkü çözümü de farklı: karar değiştirmeye gerek yok, completed_workflows'a (workflow, tamamlanma tarihi, pack'in veri damgası) üçlüsünü koymak yeter. Katılıyor musun, yoksa gerçekten bucket/setup kuralının kendisi mi yanlış?

Şimdi kör nokta: Başlık 3'ün TUR/DİLİM yapısına hiç değinmedin, oysa tasarımın en yeni ve koda en az bağlı parçası orası. Benim gördüğüm dört tanımsız durum:

(a) Deadlock: "Tur 2 tüm dilimler bitince tek seferde çalışır." Bir dilim bloklu kalırsa (route_unsupported, ya da insan o dilimi hiç çalıştırmazsa) tur asla kapanmaz ve tüm finalistler süresiz bekler. "Dilim tamamlandı" ve "tur kapandı" kriterleri hiçbir yerde tanımlı değil.

(b) Tur 1'de finalist olamayan ismin bucket'i ne olur? A/B/C yalnız Tur 2'de belirleniyor; eleme Tur 1'de oluyor. O isim C mi aldı, yoksa hiç bucket almadı mı? Bayatlama kuralı "bucket değişti mi"ye bakıyor -- bucket hiç üretilmediyse kural ne diyecek?

(c) route_unsupported bloklu bir isim her turda yeniden değerlendirilecek, yine A olacak, yine aynı yerde bloklanacak. Başlık 6 "kalıcı dışlama yok, istisna yok" dedi. Bu her turda aynı gürültüyü üreten bir kısır döngü.

(d) Başlık 2 karar 3, paralel çalışmaya guard koymamayı "akış seri, pratikte olmuyor" diye gerekçelendirdi. Ama Başlık 3 açıkça "aynı gün birkaç dilim ayrı oturumlarda çalıştırılabilir" diyor. Yani paralellik artık tasarımın kendi parçası; guard'ın gerekçesi çürüdü ve kimse fark etmedi.

Bunlardan hangisi sence gerçekten tehlikeli, hangisi benim fazla kurcalamam? Özellikle (a) için: turu kapatan şey ne olmalı -- her dilimin bitmesi mi, bir zaman aşımı mı, yoksa tur kavramını tamamen mi bırakmalıyız?
