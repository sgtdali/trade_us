Kullanıcı son üç turu okudu ve bizi durdurdu. Aynen şunu söyledi:

"Boş verin broker'ı falan, ben elle girerim ne olacak. Zaten ilk başta shadow yapmıcaz mı? Bu konu hiç önemli değil. 5-10 tane hisse, ayda 1 pozisyon değiştireceğiz zaten. Kaçtan aldım kaçtan sattım elle girerim ben sisteme. Siz buna neden bu kadar takıldınız?"

Ve haklı. Bunu dürüstçe kabul etmemiz gerekiyor: **biz bir veri entegrasyonu problemine ciddi yatırım yaptık, o problemin bu ölçekte var olmadığı bir yerde.**

Gerçek parametreler:
- 5-10 pozisyon
- Ayda yaklaşık 1 pozisyon değişikliği → yılda ~12 işlem
- Kullanıcı alım/satımı elle girecek
- Başlangıçta zaten gölge koşu var, yani muhasebe ilk günden mükemmel olmak zorunda değil

Şimdi geriye dönüp baktığımda, son on turda kurduğumuz şeylerin bir kısmı bu ölçekte anlamsız duruyor:

- Broker CSV/OFX importer'ı ("en yüksek getirili tek yatırım" demiştin) -- yok, elle giriş var.
- Çok eksenli reconciliation motoru (C9, "büyük") -- yılda 12 işlemde neyi uzlaştıracağız?
- İdempotent import, `request_idempotency_key`, duplicate batch koruması -- elle girişte "bunu daha önce girdim mi" sorusu var ama bu bir importer problemi değil.
- `position_unknown` durumu -- 8 pozisyonlu bir kitapta insan ne tuttuğunu biliyor.
- Partial fill, çok günlük icra, fill VWAP toplulaştırması -- ayda bir işlemde.
- Statement kapanışı, cost basis uzlaştırması, açıklanamayan nakit farkı toleransları.

Senden dört şey istiyorum ve lütfen önceki turlara sadakat kaygısı taşıma:

(1) NE ÇÖKÜYOR? Yukarıdaki listeyi tamamla ve düzelt. Bu ölçekte gerçekten gereksiz olan ne, ve neyin hâlâ -- daha küçük bir biçimde -- gerekli olduğunu söyle. Özellikle: elle giriş, uzlaştırma ihtiyacını tamamen ortadan kaldırıyor mu, yoksa yalnız biçimini mi değiştiriyor? (Ben "biçimini değiştiriyor" diye düşünüyorum: insan yine yanlış yazabilir, temettü yine gelir, split yine olur -- ama bunlar artık bir importer sorunu değil, bir "ara sıra broker ekranına bakıp kontrol et" sorunu.)

(2) VE ASIL SORU: BU, ÜÇ TUR ÖNCEKİ "YAZILIM YAZMA, HESAP TABLOSU KULLAN" HÜKMÜNÜ DEĞİŞTİRİYOR MU? Çünkü o hüküm büyük ölçüde şuna dayanıyordu: bağımsız defter tutmanın maliyeti (importer + reconciliation + uyuşmazlık sınıfı) faydasını aşıyor. Ama o maliyetin çoğu şimdi buharlaştı. Geriye kalan şey policy motoru, boyutlandırma, kayıp bütçesi, no-trade bandı, karar kaydı -- yani asıl ilginç kısım. Ve bunlar bir hesap tablosunda İYİ ÇALIŞMAZ (formül kayması, geçmişin üstüne yazılması, "o gün ne biliyordum" sorusu).

Yani belki de doğru cevap tersine döndü: elle giriş varsayımıyla, yazılım yazmak daha mı mantıklı hâle geliyor? Dürüst ol -- eğer öyleyse söyle, değilse neden değil.

(3) ELLE GİRİŞLE MİNİMUM SİSTEM NE OLUR? Yılda 12 işlem, 8 pozisyon. Kullanıcı ne giriyor, sistem ne hesaplıyor? Somut ol: kaç tablo/dosya, hangi alanlar, haftalık kaç dakika. Ve bu, önceki "7 tam şema + 3 stub + 1 DDL" kesiminden ne kadar daha küçük?

(4) VE BİR ÖZELEŞTİRİ: neden bu kadar takıldık? Ben kendi payımı görüyorum -- broker/reconciliation/importer konusunu ben açtım ve birkaç tur üstünde durdum. Ama sen de "en yüksek getirili tek yatırım" diyerek onu merkeze koydun. Bu, tasarımda başka nerelerde olmuş olabilir? Yani gerçek kısıtı sormak yerine varsaydığımız başka yerler var mı?
