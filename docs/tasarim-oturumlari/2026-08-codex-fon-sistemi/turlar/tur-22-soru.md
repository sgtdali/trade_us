Tetikleyici bulgunu doğruladım ve durum senin dediğinden biraz daha kötü, çünkü sistem doğru bilgiyi TAŞIYOR ama kullanmıyor:

  evaluate_trigger, type=date_due için sadece `today >= due` dönüyor (satır 1575-1578).
  NVDA pack'inde ise şu yazıyor: "next_earnings_date": "2026-08-26", "date_confirmed": false,
    "confirmation_note": "Yahoo does not distinguish a company-announced date from an estimate.
     Treat as estimated until the IR page confirms it."
  Ve pei_workflow.py satır 1469 bu bilgiyi tetikleyiciye "date_status": "estimated" olarak yazıyor.

Yani tahmin olduğu tetikleyicinin İÇİNDE yazılı, ama değerlendirme onu hiç okumuyor. On gün sonra sistem, doğrulanmamış bir Yahoo tahminine dayanarak CRM ve NVDA için deep-dive'ı hazır ilan edecek. `date_due` / `earnings_evidence_available` / `trigger_satisfied` üçlü ayrımını kabul ediyorum ve bu bence 26 Ağustos'tan önce yapılması gereken tek şey.

Filing/olay döngüsünün işletim döngüsü, keşfin edinim döngüsü olduğu ayrımını da alıyorum -- V1 planının sırasını buna göre değiştireceğim. Yetki sırası (mekanik → açık tez varsa tracker lead + gerekirse deep-dive support / aktif vaka varsa deep-dive lead / ikisi de yoksa yalnız baseline) net.

Şimdi bu turda iki şeyi somutlaştırmak istiyorum, çünkü ikisi de artık tasarımın merkezine oturdu ama hâlâ havada: TETİKLEYİCİ/KANIT KATMANI ve RESEARCH_CASE modeli.

(1) KANITIN GELDİĞİNİ NASIL BİLECEĞİZ? `earnings_evidence_available` diyorsun ama bunu üretecek bir mekanizmamız yok. Bugün elimizde SEC tarafı güçlü (sec_client.py, xbrl.py, point_in_time.py, accession bazlı cache) ama earnings RELEASE'i genelde 8-K ile geliyor ve asıl sayılar basın bülteninde/sunumda oluyor; 10-Q günler sonra gelebiliyor. Yani "kanıt geldi" tek bir şey değil. Somut sor: V1'de "earnings kanıtı yayımlandı" hükmünü hangi deterministik gözlem verir -- yeni bir 8-K accession'ı mı, XBRL'de yeni bir period_end mi, konsensüs sağlayıcısında actual belirmesi mi, yoksa insanın "evet açıklandı" demesi mi? En ucuz ve yanlış-negatif vermeyen hangisi?

(2) TARİH GEÇTİ AMA KANIT YOK DURUMU. Tahmini tarih geldi, şirket açıklamadı (ya da tarih kaydı). Sistem ne yapmalı: sessizce beklemeye devam mı, yoksa bir şey mi üretmeli? Ben burada sessizliğin tehlikeli olduğunu düşünüyorum -- "bekliyorum" ile "unuttum" ayırt edilemez hâle gelir. Ama her gün "hâlâ yok" olayı yazmak da gürültü. Bir öneri: tetikleyici `expected_window` taşısın (ör. tahmini tarih ± 2 hafta), pencere aşılırsa P2 kuyruk öğesi doğsun. Katılıyor musun, yoksa daha basit bir şey mi var?

(3) RESEARCH_CASE / EPISODE MODELİNİ TAMAMLA. `research_case_id` + episode zinciri fikrini kabul ediyorum. Ama şu sorular açık: (a) research_case'in subject'i ne -- ticker mı, yoksa `security_id` mi (ticker değişimini konuşmuştuk)? (b) Bir ticker'ın aynı anda birden fazla açık research_case'i olabilir mi? Ben olamaz derim (tek açık tez kuralının araştırma tarafındaki karşılığı), ama o zaman "NVDA için hem earnings vakası hem de yeni keşif turundan gelen bir vaka" çakışması nasıl çözülür? (c) research_case ile thesis ilişkisi ne: tez açılınca vaka kapanır mı, yoksa tez vakanın bir sonucu olarak mı yaşar? Ben "vaka kapanır, tez ayrı bir lifecycle nesnesi olarak başlar" diyorum -- vaka araştırma sorusudur, tez ise sürekli bir görüştür. İtirazın?

(4) DÖRT TERMİNAL HÜKMÜ KİM VERİR? `ready_for_pitch / watch_until / declined / blocked` -- bunlar lead skill'in çıktısından mı türetilir, yoksa insanın adjudication'ında mı verilir? Kritik, çünkü `declined` bir ismi bir sonraki keşif turuna kadar dışarıda bırakıyor; `blocked` ise insana iş çıkarıyor. Eğer lead skill kendi kendine `declined` diyebiliyorsa, bir LLM çıktısı bir ismi sessizce eleyebiliyor demektir. Ben en azından `declined`'ın insan kapısına tabi olması gerektiğini düşünüyorum. Sen nasıl kesersin?

(5) Ve son olarak: bugün elimizdeki altı `waiting_for_trigger` kaydını ne yapacağız? Bunlar eksik (senin listendeki alanların çoğu yok: beklenen kanıt, cevaplanacak soru, pencere, kesinlik, expiry). Üç seçenek görüyorum -- V2 göçünde `watch_until` episode'larına çevirmek ve eksik alanları `unknown` bırakmak; ya da altısını iptal edip 26 Ağustos'ta sıfırdan kurmak; ya da hiç dokunmayıp legacy olarak bırakmak. Hangisi?
