## 1. Orta yol var mı?

Evet. Önceki “yazılım yazma” ifadem fazla sertti. Daha doğru tavsiye:

> **Yeni bir muhasebe sistemi kurma; mevcut altyapıyı broker verisinin salt-okunur analiz katmanı olarak kullan.**

Yetki ayrımı şöyle olmalı:

- **Broker:** Pozisyon, nakit, fill, temettü ve ücretlerin ekonomik otoritesi.
- **Hesap tablosu:** Capital policy, tez/downside, inceleme ve karar günlüğünün otoritesi.
- **Mevcut yazılım:** Broker export’unu okur; normalize edilmiş snapshot, bağımsız NAV kontrolü, ağırlıklar ve policy ihlalleri üretir. Ekonomik gerçeği değiştiremez.
- **Repo:** Ham broker export’larını, policy sürümlerini ve karar kayıtlarını arşivler.

Bu model iki sistem tuzağına düşmez; çünkü iki ayrı yazma otoritesi yoktur. Yazılımda elle pozisyon/fill düzenlenmeye başlanırsa tuzak doğar.

Kullanıcının sistem inşa etmekten keyif alması da meşru bir faydadır. Ancak “maker projesi” ile “sermaye otoritesi” ayrılmalıdır: kod yazılabilir, fakat doğrulanmadan gerçek sermaye kararını yönetme yetkisi kazanmaz.

## 2. Hesap tablosunun riskleri

Tablo tam immutability sağlayamaz; ama bu ölçekte yeterli bir **kurcalanabilirlik izi** sağlayabilir:

- Tek kanonik dosya tutulur; e-posta kopyaları ve `final-v2-son.xlsx` türevleri yasaktır.
- Ham broker export’ları tarihli ve değiştirilmeden arşivlenir.
- Geçmiş karar satırları değiştirilmez; düzeltme yeni satırla yapılır.
- Her karar `decision_id`, zaman, ilgili broker snapshot’ı, policy sürümü, gerekçe ve beklenen inceleme tarihini taşır.
- “Güncel görünüm” karar günlüğünden ayrı bir sayfadır.
- Formül hücreleri kilitlenir; Excel structured table ve named formula kullanılır.
- Kontrol hücreleri bulunur: ağırlıklar + nakit = %100, hesaplanan NAV broker NAV’ına bağlanır, uzlaşma farkı görünür olur.
- Her aylık kapanışta workbook ve temel tablolar CSV/PDF olarak dondurulur; Git geçmişi ek denetim izi sağlar.

Bu, event-sourced defter kadar güçlü değildir. Ancak broker zaten ekonomik geçmişi koruduğu için kabul edilebilir kayıp, esas olarak karar geçmişinin kurcalanabilirliğidir. Gerçek hayatta geçmiş kararları yeniden kuramama veya formül bozulması yaşanırsa, özel kayıt sistemine geçiş hak edilmiş olur.

## 3. 3298 satırlık dokümanın kaderi

Doküman artık tek bir şey değildir:

1. **Anayasa:** Para doğruluğu, yetki sınırları, broker otoritesi, capital policy ve araştırma-sermaye ayrımı gibi değişmezler.
2. **Seçenek kataloğu:** Gerçek ihtiyaç doğarsa kullanılabilecek ledger, orkestrasyon, attribution ve skill mimarileri.
3. **Tarihsel kayıt:** Neden belirli alternatiflerin düşünüldüğünü ve reddedildiğini anlatan karar günlüğü.
4. **Spekülasyon:** Henüz gerçek kullanımla doğrulanmamış enum’lar, şemalar ve genel platform mekanizmaları.

Dördüncü kategori açıkça normatif olmaktan çıkarılmalıdır. “Sonra yapılacak” bile denmemeli; **“ihtiyaç gözlenirse yeniden değerlendirilecek”** denmelidir.

Kullanıcı dokümanı baştan sona işletim talimatı olarak okumamalı. En başında tek sayfalık aktif profil bulunmalı; bölümler şu etiketlerden birini taşımalı:

- `AKTİF`
- `TETİKLEYİCİYLE AKTİFLEŞİR`
- `REFERANS`
- `GEÇERSİZ / TARİHSEL`

Normatif aktif bölüm muhtemelen toplam dokümanın küçük bir kısmıdır. Geri kalanın korunması sunk-cost nedeniyle uygulanacağı anlamına gelmez.

# Tek sayfalık giriş kapısı

## Şimdi ne yapıyoruz?

**Amaç:** Tek sahibin ABD hisselerinden oluşan sermayesini disiplinli yönetmek; hukuki fon, otomatik emir sistemi veya genel amaçlı yatırım platformu kurmak değil.

### Otoriteler

- Broker: ekonomik gerçek
- Capital policy: sermaye kuralları
- Karar günlüğü: neden ve niyet
- Yazılım: salt-okunur analiz ve kontrol
- Skill/LLM: danışman; hiçbir zaman sermaye otoritesi değil

### Şimdi yap

1. Fon perimetresi, baz para birimi, sermaye amacı ve risk zarfını cevapla.
2. Capital policy’yi bir sayfada dondur.
3. Broker export’unu ve aylık statement’ları değişmeden arşivle.
4. Karar günlüğü ve güncel pozisyon inceleme tablosu kur.
5. İsteniyorsa mevcut altyapıyla yalnız `broker export → snapshot → NAV/policy kontrolü` salt-okunur dilimini geliştir.
6. Bu düzeni 8–12 hafta gerçek kararlarla işlet.

### Şimdi yapma

- Bağımsız muhasebe defteri
- Genel skill orkestratörü
- Tam olay/şema kataloğu
- Otomatik tahsis veya emir üretimi
- Counterfactual ve karar-attribution motoru
- A0–A4’ün tamamı
- Çok alternatifli proposal sistemi

### Her karar için kaydet

- O anda ne biliyordum?
- Hangi policy sürümü geçerliydi?
- Ne yapmayı düşündüm ve neden?
- Hangi sonuç fikrimi değiştirebilirdi?
- Ne zaman tekrar bakacağım?

### Şu durumlardan biri olursa yazılıma genişle

- Uzlaşma haftada 30 dakikayı geçiyor.
- Aynı veri üç yerde yeniden giriliyor.
- İki gerçek hata veya ramak kala yaşanıyor.
- Eski bir kararın girdileri yeniden kurulamıyor.
- Tablo policy ihlalini kaçırıyor.
- Birden fazla hesap/broker ortaya çıkıyor.
- Araştırma girdilerinin takibi sürdürülemiyor.

### Başarı ölçütü

Sekiz-on iki hafta sonunda:

- Her sermaye kararının önceden yazılmış gerekçesi var.
- Aylık snapshot broker’a bağlanıyor.
- Policy ihlalleri görünür.
- Geçmiş kararlar yeniden kurulabiliyor.
- Sistem haftalık hayatı kolaylaştırıyor; kendisi ayrı bir iş hâline gelmiyor.

Son hükmüm şu: **Önce fon işletimini davranış olarak kur; yazılım yalnız tekrar eden acıyı ortadan kaldırmak için büyüsün.** Tasarımın en kolay yanlış anlaşılacak yeri, bütün ayrıntıların yapılacak iş sanılmasıdır. Bunlar yükümlülük değil, ihtiyaç doğduğunda başvurulacak seçeneklerdir.