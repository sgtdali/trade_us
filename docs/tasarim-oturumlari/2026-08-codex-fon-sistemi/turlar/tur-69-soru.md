Üç hafta tarifi ve Q0/Q1/Q2 kuyruğu tam istediğim netlikte. Özellikle: sessiz haftada `no_change` kaydı üretilmemesi (o aylık review'ın işi); `fund inbox` ile `fund review`'ın ayrı olması; `no_change_with_pending_review` ayrımı; ve gece hatası politikası -- "veri gelmezse 'değişmedi' sayılmaz, `unavailable` olur". "Otomasyon başarısız olduğunda sistem sessiz kalmaz, eski veriyi yeniymiş gibi kullanmaz ve tez durumunu ilerletmez; aynı işi sonsuza kadar da tekrarlamaz" cümlesi kalıcı.

Süre bütçesini de dürüstçe düzelttiğin için iyi oldu: 10-15 dk yalnız sessiz hafta içindi; gerçek ortalama mevcut kitap için 15-25 dk/hafta, yeni aday araştırması dahil 25-40 dk. Bu hâlâ makul.

Üç tur kaldı. Şimdi NESNE MODELİ VE SÜRE.

(1) NESNE MODELİ ŞU AN NE? 65. turda dört nesne vardı; 67. turda `thesis` eklendi (beş oldu) ve `monitoring_contract` onun sürümlü alt belgesi oldu. Ama son iki turda başka şeyler de belirdi: gözlem/watermark durumu (son görülen accession, son fiyat snapshot'ı), work item / job kayıtları (hangi kural tetikledi, hangi recipe çalıştı, sonuç ne), dispatch kuralları, mekanik kontrol sonuçları.

Bunların hangileri gerçekten kalıcı nesne, hangileri yalnız kod içi durum veya log? Tam listeyi ver ve her biri için "şema gerekir mi" de. Ben şunu tahmin ediyorum: kalıcı olması gerekenler beş domain nesnesi + mekanik kontrol sonuçları + iş kaydı; watermark'lar ise basit bir durum tablosu, şema gerekmez.

(2) DISPATCH KURALLARI NEREDE YAŞAR? Kod içinde sabit bir tablo mu, yoksa config dosyası mı? Config olursa kullanıcı kural ekleyebilir ama o zaman kuralların kendisi doğrulanmalı ve sürümlenmeli. Kod olursa değiştirmek için kod değişikliği gerekir -- ki tek kişilik sistemde bu belki sorun değil. Hangisi?

Ve aynı soru monitoring kuralları için: onlar tezin içinde (yani veri), ama `metric_id` katalogla eşleşmeli. Bu eşlemeyi kim doğruluyor -- kural yazılırken mi, çalışma anında mı?

(3) SÜRE. 65. turda "5-8 iş günü CLI, 8-12 iş günü güvenilir" demiştik ama o orkestrasyonsuz ve tez izlemesizdi. Şimdi ekledik: gözlemciler (SEC accession, fiyat, review vadesi), dispatch tablosu, cycle çalıştırıcısı, mekanik kural motoru, monitoring contract, thesis lifecycle, adjudication kuyruğu, hata toparlama. Yeni tahmin ne?

Ve şunu da söyle: bunun ne kadarı MEVCUT koddan geliyor? Repoda `check_triggers`, `evaluate_trigger`, `live_refresh`, normalize hattı, metric catalog zaten var. Sıfırdan yazılacak olan ne, uyarlanacak olan ne?

(4) VE SIRALAMA: bu genişlemiş ürünü hangi sırayla inşa etmeli? 65. turdaki dokuz adımlık sıra artık eksik. Yeni sıra ne, ve hangi adımdan sonra sistem gerçekten "kendi kendine çalışıyor" hâle gelir?
