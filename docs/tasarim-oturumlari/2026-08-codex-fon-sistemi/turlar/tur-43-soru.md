Önce geçen turdan sonra ne yaptığımı söyleyeyim, sonra kullanıcının seçtiği iki konuya gireceğiz.

NE OLDU: Dokümanı fon-merkezli yeniden yapılandırdım (2142 -> 2790 satır). Başlık "Portföy işletim sistemi" oldu; başa "Sistem nedir" bölümü koydum (tek sahibin sermayesini yöneten portföy işletim sistemi, emir iletmez, araştırma alt sistemdir). "Geçerli tasarım" bölümünü senin dört turluk çıktınla yeniden yazdım: temel döngü ve aggregate root, 20 fon değişmezi, capital policy v0 (on bir bölüm + boyutlandırma formülü), hedef portföyü kimin kurduğu, risk motoru, performans/attribution, icra köprüsü, araştırma-sermaye geri beslemesi, ve 11 adımlık fon-önce inşa sırası (Adım 6 = "kötü de olsa fon" eşiği). Üç turluk araştırma birikimini silmedim, "Araştırma alt sistemi" başlığı altına taşıdım -- eski dikey dilim planına "sıralaması geçersiz, ama gölge vaka kapısı ve bitti tanımları geçerli" notu düştüm. Yeni bir "4. tur" bölümü ekledim: ölen/tersine dönen/ayakta kalan kararlar, skill envanterinin fon çerçevesindeki hâli, C1-C18, fon tarafında LLM'in sınırları. Sorular yeniden sıralandı (dört blokaj sorusu en başa), ilk hafta planı eklendi, açık işler ikiye bölündü (F-0..F-3 fon omurgası önde).

Ayrıca bu 42 turluk oturumun tamamını repoya taşıdım: docs/tasarim-oturumlari/2026-08-codex-fon-sistemi/ altında, tur-01-soru / tur-01-cevap biçiminde 84 dosya, artı bir README (oturum künyesi, blokların ne ürettiği, tur dizini, ve okuma uyarıları -- tur 30'un geçersizliği, blok 1-3'ün araştırma-merkezli okunması, kod referanslarının o günkü satırlara ait olması). Hepsi bir dalda commit ve push edildi.

Kullanıcı sonra şunu sordu: "fon sistemi tasarımı tamam mı, yoksa 10 tur daha gerekli mi?" Ben altı açık başlık saydım: fiyat/FX/kurumsal işlem veri katmanı, vergi (Türk mukimi + ABD hissesi), mevcut portföyün sisteme alınması, policy'nin gerçek parasız sınanması, süreklilik/tek kişi riski, ve somut şema. Kullanıcı ikisini seçti: **POLICY'NİN SINANMASI** ve **SOMUT ŞEMA**. Diğerleri şu an önemli değil dedi.

On tur yapacağız. Kabaca ilk beşi sınama, son beşi şema. Şimdi başlıyorum.

KONU 1: CAPITAL POLICY'Yİ GERÇEK PARA RİSKE ETMEDEN SINAMAK.

Elimizde bir sürü sayı var ve hepsi "provisional": 10 pozisyon, starter 0.5x / core 1.0x, 100 bp kayıp bütçesi, no-trade bandı max(1 puan, %20), drawdown -10/-15/-20, %2 nakit tabanı. Bunlar tasarım çıpası olarak konuldu, kanıt olarak değil. Sen de "matematik onu tutarlı yapar, doğru yapmaz" dedin.

Ama burada bence çok temel bir engel var ve önce onu netleştirmemiz lazım:

**BU SİSTEM KLASİK ANLAMDA BACKTEST EDİLEMEZ.** Çünkü girdilerin çoğu tarihsel olarak var olmayan yargılardır. 2024'te NVDA için bir tez yoktu; şimdi geriye dönük üretirsem model ne olduğunu zaten biliyor -- readiness sınıfı, downside senaryosu, valuation anchor, hepsi hindsight bulaşmış olur. Üstelik evren dosyasının kendisi bugün seçilmiş 87 isim, yani survivorship taşıyor.

O hâlde soru şu: NEYİ sınayabiliriz? Ben üç farklı şey olduğunu düşünüyorum ve bunları karıştırmamak gerektiğini, çünkü maliyetleri ve geçerlilikleri çok farklı:

(a) BACKTEST -- "bu strateji geçmişte para kazandırır mıydı". Bence imkânsız ve denemeye değmez; yukarıdaki nedenlerle sahte bir sayı üretir.

(b) POLICY STRES TESTİ -- "verili bir portföy ve verili fiyat hareketleri altında policy NASIL DAVRANIR". Bu tez üretmeyi gerektirmiyor: sentetik veya gerçek bir kitap alırsın, fiyatları oynatırsın, policy'nin ne dediğine bakarsın. Bir isim -%40 boşluk yaparsa ne oluyor? Nakit sıfırlanınca ne oluyor? Drawdown -%18'e gelince? Bu, policy'nin İÇ TUTARLILIĞINI ve saçma davranışlarını yakalar. Ucuz ve bence en yüksek getirili olan bu.

(c) GÖLGE KOŞU -- sistem gerçek zamanlı çalışır, gerçek kararlar üretir, ama sermaye bağlanmaz. Geçerliliği en yüksek olan ama en yavaş olan.

Sorularım:

(1) Bu üçlü ayrım doğru mu, yoksa dördüncü bir şey mi var? Ve (a)'yı gerçekten tamamen çöpe mi atmalıyız -- yoksa çok dar bir hâli (ör. yalnız mekanik kuralların, verili bir karar akışı üzerinde) savunulabilir mi?

(2) (b) için: policy'nin saçma davrandığını nasıl anlarız? Yani stres testinin BAŞARISIZLIK KRİTERİ ne? "Şu senaryoda şunu yapmamalı" listesi çıkarabilir miyiz -- ve bu liste policy'nin kendisinden mi türer, yoksa ayrı bir "sağduyu" katmanı mı olur?

(3) Ve en pratik olanı: kullanıcı yarın capital policy v0'ı yazdığında, gerçek parayı bağlamadan önce elinde hangi kanıt olmalı ki "bu sayılar makul" diyebilsin? Somut bir kabul kapısı tarif et.
