valuation_anchor sözleşmesini, scenario'nun overlay olmasını (`base_case_ref` zorunlu, base'in epistemik seviyesini yükseltemez) ve dört workbook skill'inin V1 dışı kalmasını kabul ediyorum. `terminal_status: blocked, reason: model_required_outside_v1` bence dürüst bir sınır -- ve "en tehlikeli seçenek comps'ta durmak değil, comps seviyesindeki kanıtla DCF kesinliği taklit etmektir" cümlesi bu kararın gerekçesi olarak dokümana girecek. AMZN/META senaryolarının screen_grade/diagnostic_only olarak yeniden sınıflanması ve o Add/Trim/Exit eşiklerinin V1'de üretilmemesi gerektiği de doğru.

Şimdi KAZANÇ/OLAY KÜMESİNE geçiyoruz ve bu küme hipotetik değil -- sistemde şu anda canlı bekleyen iş var. waiting_for_trigger olaylarını açtım:

  CRM  -> earnings_deep_dive, 2026-08-26
  NVDA -> earnings_deep_dive, 2026-08-26
  PEP  -> earnings_deep_dive, 2026-10-08
  NFLX -> earnings_deep_dive, 2026-10-20
  META -> earnings_deep_dive, 2026-10-28
  AMZN -> earnings_deep_dive, 2026-10-29

Bugün 2026-08-16. Yani CRM ve NVDA on gün sonra ateşliyor ve V1 makinesinin hiçbir parçası yok. Bu, kümeyi tartışırken aklımızda tutmamız gereken somut bir gerçek.

Beş sorum var:

(1) BU KÜME ASLINDA ÇEKİRDEK DÖNGÜ OLABİLİR Mİ? Sen earnings-preview'i koşullu, earnings-deep-dive'ı çekirdek yaptın. Ama mandate'in kendi ölçümüne bak: "aylık kararlar ortalama 46 günlük veriye dayanıyor ve şirket-aylarının %32'sinde karardan sonraki 30 gün içinde yeni bir 10-Q/10-K geliyor". Yani bu sistemde bilginin baskın kaynağı dosyalama olayları. Long-only, aylık kadanslı, benchmark'sız bir sistemde asıl döngü keşif değil, DOSYALAMA olabilir: her çeyrek yeni veri gelir, tezler ona göre yaşar veya ölür. Eğer bu doğruysa, V1 planındaki adım sıralaması (önce keşif zinciri, sonra izleme) yanlış öncelikte olabilir -- izleme/olay hattı önce gelmeli. Katılıyor musun, yoksa keşif olmadan izlenecek tez de olmaz mı?

(2) BİR DOSYALAMA GELDİĞİNDE TAM OLARAK NE ÇALIŞIR? Bu, entegrasyonun en somut sorusu ve şu an üç aday var: mekanik eşik kontrolü (bizim kodumuz), earnings-deep-dive (skill), thesis-tracker (skill). Üçü de "yeni çeyrek geldi" olayına tepki verebilir. Sıralama ve yetki ne olmalı? Benim düşüncem: mekanik kontrol her zaman çalışır (ucuz, LLM'siz), deep-dive yalnız açık tezi olan veya aktif research_case'i olan isimlerde çalışır, tracker ise deep-dive'ın çıktısını tez kaydına işler. Ama o zaman deep-dive ile tracker arasında iş bölümü bulanıklaşıyor: ikisi de "bu yeni bilgi tezi nasıl etkiliyor" diyor. Sınırı nereye koyarsın?

(3) TEZİ OLMAYAN İSİMDE KAZANÇ NE İŞE YARAR? Bugünkü altı tetikleyicinin hiçbirinde tez yok (zaten sistemde hiç tez yok). Yani bu tetikleyiciler "tezsiz bir aday için çeyrek sonucunu bekle" diyor. Bu anlamlı mı? Bir aday için kazanç beklemek, aslında Başlık 1'deki B kovası mantığı (tetikleyici bekleyen isim). Ama şimdi lead+support modelinde bunun karşılığı ne -- `watch_until(trigger)` terminal hükmü mü? Eğer öyleyse, tetikleyici geldiğinde vaka yeniden mi açılır, yoksa yeni bir vaka mı doğar?

(4) earnings-preview ve earnings-deep-dive AYNI ANDA GEREKLİ Mİ? Prodüksiyonda dördü preview çalışmış, hiçbiri deep-dive'a ulaşmamış (hepsi tetikleyicide bekliyor). Preview "sonuç öncesi kurulum", deep-dive "sonuç sonrası okuma". Tek operatörlü bir sistemde ikisini de çalıştırmak çeyrek başına iki ağır oturum demek. Preview'in gerçekten değer kattığı durum ne -- yalnızca pozisyon varken mi (yani "sonuçtan önce ne bekliyorum" yazıp sonra kendimi denetlemek), yoksa tezsiz adaylarda da mı? Ben preview'in asıl değerinin FALSIFIABILITY olduğunu düşünüyorum: sonuçtan önce yazılmış beklenti, sonradan tezi dürüstçe değerlendirmenin tek yolu. Eğer öyleyse preview açık tezler için ÇEKİRDEK, adaylar için gereksiz olur. Katılıyor musun?

(5) catalyst-calendar ve economic-impact-report. İkisi de bizim modelimize zor oturuyor: catalyst-calendar repo'nun zaten ürettiği `next_events` ile çakışıyor gibi (bugünkü tetikleyiciler de oradan geliyor), economic-impact-report ise tek ticker'a değil ÇOK ismi aynı anda etkileyen bir mekanizmaya bakıyor -- yani subject'i ne ticker ne tez, bir tema. Bizim `subject_type` şemamızda bunun karşılığı yok. İkisi için de net söyle: catalyst-calendar deterministik `next_events` üretimimizin üstüne ne katıyor (hiçbir şey katmıyorsa gereksizdir), ve economic-impact-report'un subject'i ne olmalı -- yoksa V1'de hiç yeri yok mu?
