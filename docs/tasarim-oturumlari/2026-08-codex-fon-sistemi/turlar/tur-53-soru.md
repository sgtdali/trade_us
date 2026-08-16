Önce dokümantasyonu tamamladım: "Gözden geçirme — 5. tur: sınama ve şema" bölümünü ekledim (dört kanıt katmanı, monotonluk özellikleri, iki aşamalı gölge koşu, A0-A4 merdiveni, şema kararları tablosu, açılış kitabı problemi, olay zarfı, SQLite, ve V0 kesimi). İnşa sırasına "capital policy bütün altyapıyı bloklamaz" daraltmasını işledim; ilk hafta planını "dört soruyu beklerken 2-4. maddeler yapılabilir" diye güncelledim. Doküman 3023 satır. Arşive 43-52. turları ekledim, README'ye 5. bloğu ve tur dizinini yazdım.

Şimdi kullanıcı yeni bir konu açıyor ve uygulama tarafına geçmek istiyor: **FON SİSTEMİ İLE EKLENTİ SKILL SİSTEMİ NASIL ENTEGRE OLACAK.** Nerede, ne, nasıl kullanılacak. Yedi tur.

Bu konu şu an gerçekten açık, çünkü iki tur birbiriyle gerilimde:

- 3. turda (skill envanteri) 10+1 çalıştırılabilir katalog, lead+support modeli, pack/contract/validator mimarisi kurduk -- ama hepsi ARAŞTIRMA-merkezli bir sistem varsayımıyla.
- 4. turda "fonun zorunlu çekirdeğinde hiçbir LLM skill'i yoktur" dedin ve minimum fon döngüsünün LLM'siz çalışabilmesini mimarinin bağımsızlık testi yaptın.

Yani skill'ler artık sistemin merkezinde değil, kenarında. Ama kenarın neresinde, tam olarak nerede temas ediyor -- bunu hiç somutlaştırmadık.

İlk turda temas yüzeyini çıkaralım:

(1) FON SİSTEMİ TAM OLARAK NEREDE BİR SKILL'E DOKUNUR? Benim saydıklarım: (a) yeni bir isim `underwritten_investable_set`e girerken (pitch), (b) açık bir tez yeni kanıt karşısında değerlendirilirken (tracker, deep-dive), (c) bir pozisyonun downside/valuation girdisi güncellenirken (comps, scenario), (d) keşif havuzundan yeni aday üretilirken (idea-generation), (e) risk motoru bir driver yoğunlaşması gördüğünde yorum isterken. Beş temas. Eksik/fazla var mı, ve bunlardan hangisi gerçekten V0'da gerekli?

(2) HER TEMASTA YÖN NE? Bunlardan bazılarında fon skill'i ÇAĞIRIYOR (risk motoru soru soruyor), bazılarında skill'in çıktısı fona GİRDİ oluyor (pitch bir tez üretiyor, fon onu alıyor). Bu iki yön farklı mimari gerektiriyor gibi: birincisi senkron bir istek, ikincisi asenkron bir besleme. Doğru mu, ve ikisini aynı mekanizmayla mı yapmalıyız?

(3) VE EN ÖNEMLİSİ: ARADAKİ SÖZLEŞME NE? Fon sisteminin bir pozisyonu boyutlandırabilmesi için araştırmadan gelmesi gereken şeyler var: readiness sınıfı, downside senaryosu, valuation anchor, driver etiketleri. Bunlar 4. turda "adjudicated capital input" diye adlandırılmıştı. Ama bu tek bir nesne mi, yoksa dört ayrı nesne mi? Ve fon sistemi bunları skill'den mi alıyor, yoksa insan adjudication'ından mı? (Benim anladığım: skill önerir, insan adjudicate eder, fon yalnız adjudicate edilmişi görür. Yani fon ile skill ARASINDA her zaman bir insan kapısı var. Doğru mu?)

(4) Bir de sınır sorusu: fon sistemi hiç skill çağırmadan çalışabilir mi? 4. turda "LLM kaldırıldığında sistem daha az akıllı olabilir ama daha az doğru olamaz" demiştin. Bunu uygulama diline çevir: eğer eklenti tamamen kapatılırsa fon ne kaybeder ve ne kaybetmez? Bu, entegrasyonun ne kadar gevşek olması gerektiğini belirliyor.
