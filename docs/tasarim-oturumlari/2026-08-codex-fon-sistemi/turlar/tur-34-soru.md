Aggregate root'un değişmesini, on üç birinci sınıf nesnenin sekizinin hiç olmadığını, "yalnız pozisyon/nakit defteri fon değil broker aynasıdır" ayrımını ve düzeltilmiş icra ilkesini ("sistem emir iletmez ama hedef portföy, sermaye kararı ve işlem önerisi üretebilir") kabul ediyorum. Sıralama önerini de alıyorum.

Açık sorunun cevabı: TEK SAHİBİN KENDİ SERMAYESİ. Dış yatırımcı, katılma payı, ücret, resmi NAV, saklama ve uyum yok. "Fon" burada hukuki bir yapı değil, disiplinli yönetilen tek bir sermaye havuzu anlamında. Bunu varsayarak devam ediyoruz; hukuki fon katmanı kapsam dışı.

Şimdi ilk ve en temel tasarım artefaktına iniyoruz: CAPITAL POLICY v0. Bugüne kadar hep "yok" diye işaret ettik, artık yazacağız.

Bağlam hatırlatması: long-only, yalnız adi hisse, opsiyon/kaldıraç/açığa satış yok, ABD listeli, benchmark yok ve mandate benchmark varsayılmasını açıkça yasaklıyor, pozisyon sayısı "ekran karar verir" diyor, likidite tabanı ölçülüp uygulanmıyor (retail büyüklüğünde pozisyon günlük hacmin binde birinden az), haftalık gözden geçirme + aylık rebalans ritmi var ama `change_required: false`, ve mandate'in kendi yazılı gerilimi var: temel analiz ufku 3-18 ay iken karar ritmi aylık.

Sorularım:

(1) ASGARİ ALAN KÜMESİ NE? Capital policy v0'ın içinde ne olmalı? Bana "her şeyi koy" listesi değil, tek operatörün gerçekten karar verebileceği ve sisteme deterministik kural olarak girebilecek asgari küme lazım. Her alan için: neden gerekli, ve doldurulmazsa sistemin hangi kararı veremez hâle geldiği.

(2) BOYUTLANDIRMA KURALI NE OLMALI? Seçenekler: eşit ağırlık, conviction-ağırlıklı, risk-bazlı (volatilite/drawdown normalize), ya da "taban ağırlık + sınırlı conviction eğimi". Benchmark yok, faktör modeli yok, tek operatör var. Hangisi hem savunulabilir hem uygulanabilir? Ben "taban ağırlık + tavanlı conviction eğimi"ne meyilliyim çünkü eşit ağırlık conviction bilgisini çöpe atıyor, saf conviction ağırlığı ise ölçülemeyen bir şeyi sayısallaştırıyor. Ama conviction'ı neye dayandıracağız -- pitch'in kendi ifadesine mi, yoksa daha sert bir şeye mi?

(3) NAKİT NEDİR? İki felsefe var: nakit artıktır (fikir varsa yatırılır, yoksa bekler) ya da nakit bir pozisyondur (hedef bir aralığı vardır). Bu seçim sistemin karakterini belirliyor: birincisinde "iyi fikir yoksa nakitte kal" meşru, ikincisinde sürekli yatırımda kalma baskısı var. Mandate hangisini ima ediyor sence, ve tek operatörlü bir sistem için hangisi daha az hata üretir?

(4) POZİSYON SAYISI. Mandate "ekran kaç ismin barı geçtiğine karar verir" diyor ve şunu ekliyor: "daha az pozisyon, şansın tek başına sonucu açıkladığı bandı genişletir". Yani kullanıcı bu takası zaten görmüş. Ama bir fon sisteminin bir yerde sınır koyması gerekmez mi -- hem alt (çok az isim = şans) hem üst (çok fazla isim = tek operatör izleyemez, ve 6-9 saatlik haftalık bütçeyi patlatır)? İzleme kapasitesi ile çeşitlendirme arasındaki bu bağı nasıl kurarsın?

(5) İŞLEM EŞİĞİ VE UFUK GERİLİMİ. Bence mandate'in kendi yazdığı gerilimin (3-18 ay ufuk vs aylık ritim) çözümü tam olarak burada: bir HİSTEREZİS/işlem eşiği. Yani "hedef ağırlıktan sapma X'i geçmedikçe işlem yapma" kuralı, aylık bir bakışın aylık bir rotasyona dönüşmesini engeller. Katılıyor musun, ve eğer öyleyse bu eşik neye göre tanımlanmalı -- yüzde puan sapması mı, işlem maliyeti katı mı, yoksa tez durumundaki değişim mi?

(6) Son olarak: capital policy KİM tarafından ve NE SIKLIKLA değiştirilebilir? Bu bir mandate dosyası gibi "kullanıcı belirler" mi, yoksa değişikliği kendisi bir olay ve gerekçe gerektiren bir şey mi? Piyasa düşerken risk limitini gevşetmek klasik hatadır; tasarımın buna karşı bir direnci olmalı mı?
