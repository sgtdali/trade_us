Devam ediyoruz. Önce on turun sonunda ne olduğunu anlatayım, sonra yeni ve uzun bir konuya gireceğiz.

NE OLDU: Kullanıcı on turun özetini aldı ve "dokümanı en doğru şekilde hallet" dedi. İkinci turu üstüne eklemek dokümanı üç katmanlı arkeolojiye çevireceği için yapıyı değiştirdim: karar günlüğü tarihsel kayıt olarak kaldı (gerekçeler ve reddedilen alternatifler silinmedi), ama en başa "Geçerli tasarım" diye tek bir doğruluk bölümü koydum -- çelişki olursa o kazanıyor. Doküman 1086 -> 1640 satır.

Geçerli tasarım bölümünde şunlar var: ürün sınırı (V1 = araştırma/izleme defteri, sermaye tahsis sistemi değil, çünkü capital policy yok), on değişmez, üç eksenli tez modeli, dokuz adımlık V1 planı (her adımın "bitti" tanımıyla), P0-P4 operatör kuyruğu, insan kapısının kaldığı dört yer, haftalık emek tahmini, ve V1'de açıkça yapılmayacaklar listesi. Başlık 4 karar 5'e İPTAL notu düştüm, Başlık 4 karar 1'e mandate'in known_tension uyarısını işledim, beş eksenli tabloya sadeleştirme notu koydum. Kod kusurlarını dört gruba ayırıp satır referanslarıyla tablo hâline getirdim; senin doğrulamadığım beş iddianı da ayrıca "doğrulanmamış" diye işaretledim. Açık işlere sekiz madde eklendi, başında capital_policy var.

ŞİMDİ YENİ KONU: SKILL ENVANTERİ. Kullanıcı bunun için on beş tur istiyor.

Eklentide (public-equity-investing 0.1.31) tam 23 skill var:
catalyst-calendar, company-tearsheet, comps-valuation, dcf-model-builder, deck-report-qc, earnings-deep-dive, earnings-preview, economic-impact-report, equity-model-update, event-driven-analyzer, financials-normalizer, idea-generation, initiating-coverage, long-short-pitch, meeting-prep, memo-builder, model-audit-tieout, portfolio-risk-management, public-equity-investing (şemsiye), scenario-sensitivity-generator, thesis-tracker, three-statement-model-builder, user-context.

Bizim config/pei-workflows.json'da ise yalnız SEKİZ tanesi var: tearsheet, earnings_preview, earnings_deep_dive, comps, pitch, thesis_tracker, scenario, initiating_coverage.

On beş turda şunu kararlaştıracağız, tüm detaylarıyla: hangi skill'e gerçekten ihtiyacımız var, ihtiyaç varsa NEREDE ve NASIL kullanılacak, sistemle entegrasyonu ne (pack_step, required_workflows, allowed_next, result_contract, model/effort, hangi insan kapısına tabi), ve skill'ler arasındaki ilişkiler ne. Gereksiz olanlara yoğunlaşmayacağız -- onları eleyip geçeceğiz.

Ama başlamadan önce, senin eklentiyi okurken gördüğün ve benim de fark ettiğim bir şeyi masaya koymak istiyorum, çünkü bütün bu envanter tartışmasının çerçevesini o belirliyor:

shared/plugin-routing-map.json'da eklentinin KENDİ yönlendirme felsefesi yazılı: "Route broad prompts by listed-equity investor workflow before choosing an individual skill. Pick one lead skill that owns the first real investment judgment or hero artifact, then call support skills only for the workstreams the lead skill assigns." Yani eklenti "bir LEAD skill vardır, o ilk gerçek yatırım hükmünün sahibidir, destek skill'lerini o atar" diyor. Ayrıca bir artifact hiyerarşisi var: önce hero insan çıktısı, sonra companion workbook/rapor, en son support JSON/CSV/log.

Bizim mimarimiz ise bunun tersi: sabit, doğrusal bir zincir (tearsheet -> comps -> pitch -> ...) ve her adım eşit ağırlıkta bir "workflow". Yani biz eklentinin destek/lead ayrımını düzleştirmişiz.

İlk turda senden şunu istiyorum:

(1) Bu iki modelin (bizim doğrusal zincir vs eklentinin lead+support) gerçekten çelişip çelişmediğini söyle. Bizim zincirimiz eklentinin niyetini bozuyor mu, yoksa bizimki orkestrasyon katmanı olduğu için meşru bir sadeleştirme mi? Eğer çelişiyorsa, envanteri hangi modele göre yapacağımızı ŞİMDİ kararlaştırmalıyız, yoksa on beş tur boyunca yanlış soru sorarız.

(2) 23 skill için ilk kaba triyaj yap. Ölçüt şu olmalı -- ve bu ölçütü sıkı tut: V1 bir ARAŞTIRMA VE İZLEME DEFTERİ; capital policy yok, benchmark yok, tek operatör, haftada 5-7 saat, 87 isim, long-only, opsiyon/kaldıraç/açığa satış yok, aylık gözden geçirme varsayılanı no_change. Bu sisteme göre her skill için üç kovadan biri: ÇEKİRDEK (V1'de mutlaka lazım), KOŞULLU (belirli bir durum doğarsa lazım, koşulu yaz), GEREKSİZ (bu sistemde hiç yeri yok, tek cümle gerekçe).

Gereksizleri tek cümleyle geçip çekirdek ve koşullulara odaklanacağız. Kaba triyajı ver, sonraki turlarda kümeler hâlinde derine ineceğiz.
