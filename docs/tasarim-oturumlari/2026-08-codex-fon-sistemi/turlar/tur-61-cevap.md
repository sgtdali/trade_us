## 1. Gerçek alternatif

Daha sert hükmüm şu: **Bugün iki haftalık özel yazılım çekirdeği bile henüz hak edilmiş değil.** Doğru başlangıç büyük ihtimalle broker + disiplinli hesap tablosu + yazılı capital policy’dir.

Broker zaten şunlarda otorite:

- Gerçek pozisyon ve nakit
- Fill geçmişi
- Temettü, ücret ve kurumsal işlemler
- Güncel NAV ve gerçekleşmiş P&L
- Vergi lotları ve maliyet temeli — broker’a göre değişmekle birlikte

Hesap tablosunun eklemesi gereken şey broker’ın bilmediği karar katmanıdır:

- Bu pozisyon neden tutuluyor?
- Readiness ve downside nedir?
- Policy’ye göre azami ağırlık nedir?
- Hangi falsifier veya olay yeniden inceleme doğurur?
- İşlem no-trade bandını neden geçti?
- Son karar neydi ve ne değişti?
- Hangi inceleme gecikti?

Bunları cevaplamak için event store veya projection motoru gerekmiyor. Dört-beş sayfalı bir çalışma kitabı yeter:

1. Capital policy
2. Broker’dan alınan güncel portföy snapshot’ı
3. Pozisyon/tez/downside/review kayıtları
4. İşlem ve karar günlüğü
5. Aylık performans ve dış nakit akışları

Broker ekstreleri de değişmeden arşivlenir. İlk aşamada broker muhasebe gerçeğinin, tablo ise karar disiplininin otoritesi olur.

## 2. Gerçek hatalar ve tasarımın ürettiği korkular

### Bu ölçekte gerçekten olacaklar

- Hesap tablosunun broker’dan geri kalması
- Kısmi fill’in yanlış adetle kaydedilmesi
- Nakit girişi, temettü veya ücretin unutulması
- Split sonrası fiyat eşiği veya hisse adedinin yanlış yorumlanması
- USD performansı ile TL sonucunun karıştırılması
- Bayat tez/downside ile pozisyon artırılması
- Pozisyon boyutunun tutarlı bir kurala dayanmaması
- Aylık bakışın gereksiz işleme dönüşmesi
- İnceleme tarihinin unutulması
- Sonradan karar gerekçesinin yeniden yazılması

Bunların çoğu broker export’u, birkaç kontrol formülü ve karar günlüğüyle yakalanabilir.

### Büyük ölçüde kurumsal ölçekten veya kendi mimarimizden gelenler

- Birden fazla eşzamanlı writer ve karmaşık commit kapısı
- Global/stream sequence ve genel batch semantiği
- Çok broker/custodian uzlaşması
- Genel amaçlı lot eşleştirme motoru
- Resmî tahakkuk esaslı günlük NAV
- A0–A4’ün tamamı
- Çok aktörlü approval/authority modeli
- Genel lead/support router ve route-kalite altyapısı
- Çok sayıda freshness, visibility ve binding durumu
- Otomatik importer yokken idempotent import problemi

Burada rahatsız edici bir gerçek var: **Bağımsız muhasebe defteri kurmak, broker ile sistem arasında yeni bir uyuşmazlık sınıfı yaratır; reconciliation da kısmen bizim yarattığımız bu sorunu çözer.** Tek broker ve düşük işlem sıklığında bu maliyet henüz haklı olmayabilir.

## 3. Yüzde iddiasının düzeltilmesi

Önceki “%25–30 özellik, %70 değer” hesabım yanlış karşılaştırma tabanı kullandı. İki haftalık sistemi tam hedef mimariyle karşılaştırdım; gerçek alternatif broker + Excel’di.

İlk yılın pratik değeri açısından daha dürüst tahmin:

- Broker tek başına: yaklaşık **%50–60**
- Broker + iyi capital policy + disiplinli tablo: **%80–90**
- Özel iki haftalık çekirdek: tabloya göre yalnızca **5–15 yüzde puan** ek değer
- Tam hedef mimari: kalan ölçeklenebilirlik, otomasyon ve denetim değerini getirir; fakat bakım yükü nedeniyle teorik değerinin tamamı gerçekleşmeyebilir

Dolayısıyla özel yazılımın marjinal değeri bugün düşündüğümüzden çok daha düşüktür. Önce hangi sorunun broker + tabloyla cevaplanamadığı gözlenmelidir.

## 4. “İki hafta” tahmininin düzeltilmesi

İki hafta ancak şu koşullarda mümkündü:

- Tam zamanlı çalışma
- Bilinen ve temiz broker export formatı
- Alanı bilen geliştirici
- Dar kapsam
- UI ve edge-case desteği olmaması

Gerçek koşullarda daha dürüst süre:

- Capital policy + çalışma kitabı: **1–3 gün**
- Read-only broker importu ve basit raporlama prototipi: **2–4 takvim haftası**
- Güvenilir ledger, replay, reconciliation ve testler: **6–10 hafta**
- Kurumsal işlemler ve broker tuhaflıklarıyla sürekli kullanılabilir hâl: **10–14 hafta**

Claude/Codex şema ve kod yazımını hızlandırır; broker verisini anlamayı, muhasebe kararlarını ve gerçek veride hata ayıklamayı aynı oranda hızlandırmaz.

Evet, bu düzeltme kararı değiştiriyor: **6–10 haftalık özel çekirdeğe, ancak hesap tablosuyla yaşanmış somut bir sorun varsa girilmelidir.**

## 5. Asıl değer tasarım süreci olabilir mi?

Evet; bu romantik değil, ciddi bir ihtimal. Hatta bugün itibarıyla muhtemelen gerçekleşmiş değerin çoğu yazılımda değil, şu zihinsel sözleşmelerde:

- Aylık inceleme işlem zorunluluğu değildir.
- Nakit meşru bir residual’dır.
- Conviction sıfatı sermaye miktarına çevrilmez.
- Kaybı önceden bütçelemek stop-loss değildir.
- Tez sağlığı ile P&L aynı gerçek değildir.
- Statüko replacement kararında avantaj taşır.
- Araştırma girdisi sermaye etkisi görülmeden yargılanmalıdır.
- Policy piyasa düşünce sessizce gevşetilmemelidir.

Fakat bunun bir sınaması var: Bu kavramlar sekiz-on iki hafta boyunca gerçek karar günlüğünde uygulanmıyorsa, tasarım öğrenme değil entelektüel tüketim olmuştur. Yazılım bu disiplini kolaylaştırabilir ama yaratamaz.

Benim bugünkü tavsiyem:

**Özel fon yazılımını şimdilik durdur; broker + capital policy + disiplinli çalışma kitabıyla 8–12 haftalık gerçek işletim yap.** Bu sürede her tekrarlanan el işini, cevaplanamayan soruyu, hatayı ve harcanan dakikayı kaydet. Ancak en az bir somut eşik oluşursa kod yaz:

- Haftalık uzlaşma 30 dakikayı aşıyor
- Aynı veri üç farklı yere tekrar giriliyor
- En az iki gerçek hata veya ramak kala yaşanıyor
- Karar anındaki portföyü yeniden kuramıyorsun
- Tablo policy ihlallerini güvenilir biçimde yakalayamıyor
- Araştırma çıktısını sermaye kararına bağlamak sürdürülemez hâle geliyor

Böylece yazılım, tasarımın heyecanından değil, gözlenmiş acıdan doğar. Bu tek kişi için çok daha sağlıklı bir yatırım sırasıdır.