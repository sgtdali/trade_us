## 1. Sistemin tanımı

Bu sistem, tek sahibin kendi sermayesini disiplinli biçimde yönetmek için kurulan bir portföy işletim sistemidir: broker gerçekliğinden pozisyon, nakit ve NAV üretir; capital policy’ye göre risk sınırlarını hesaplar; araştırmayı sermaye ihtiyaçlarına yönlendirir; hedef portföy ve işlem önerileri üretir; gerçekleşen sonuçları performans ve karar kalitesi açısından ölçer. Sistem emir iletmez, işlemi onaylamaz veya icra etmez; insan karar verir ve broker’da uygular. Hukuki fon yönetimi, saklama, vergi danışmanlığı ve mevzuat uyumu kapsam dışıdır.

## 2. Fonun değişmezleri

1. Broker, gerçekleşmiş pozisyon/nakit/fill gerçeğinin; sistem ise bunların policy meşruiyetinin otoritesidir.

2. Her ekonomik hareket ayrı, tipli ve kaynaklı bir kayıt olmalıdır; pozisyon, nakit, maliyet ve NAV mutable tablolardan değil bu kayıtlardan türetilir.

3. Dış nakit akışları yatırım performansından ayrılmadan getiri hesaplanamaz.

4. Her NAV; `as_of`, fiyat, FX, nakit ve reconciliation durumunu taşır; bayat veya uzlaştırılmamış NAV karar kalitesinde sayılamaz.

5. Her sermaye önerisi belirli bir capital-policy sürümüne ve değişmez portföy snapshot’ına bağlıdır; geçmiş kararlar yeni policy ile yeniden yorumlanamaz.

6. Deterministik motor güvenli ağırlık aralığını ve bağlayıcı kısıtları üretir; nihai hedef ağırlığı kendiliğinden seçmiş gibi davranamaz.

7. Capital policy’ye aykırı öneri insan onayıyla sessizce geçerli hâle gelemez; ayrı, gerekçeli ve süreli override gerekir.

8. Sistem emir iletmez; onaylanmış sermaye kararı, işlem niyeti, broker emri ve fill birbirinden ayrı gerçeklerdir.

9. Kanonik gerçek fill’dir; emir miktarı veya onaylanan miktar gerçekleşmiş pozisyon sayılamaz.

10. Plan dışı işlem reddedilemez çünkü gerçektir; fakat `unadjudicated` sayılır ve meşruiyet kurulana kadar yeni risk artırımı bloke edilir.

11. Reconciliation tek boolean değildir; pozisyon, nakit, işlemler, maliyet temeli ve kurumsal işlemler ayrı ayrı uzlaştırılır.

12. Reconciliation farkı geçmişi değiştirerek kapatılamaz; eksik fill, kurumsal işlem veya düzeltme olayı eklenir.

13. Nakit muhasebede birinci sınıf varlık, tahsiste ise meşru residual’dır; fikir yoksa yatırım zorunluluğu yoktur.

14. Loss budget, pozisyon açılmadan önce uygulanan boyutlandırma sınırıdır; stop-loss değildir.

15. Fiyat düşüşü veya portföy drawdown’ı otomatik satış üretemez; inceleme, ekleme dondurması veya yeni sermaye kararı tetikler.

16. Policy sıkılaştırması hemen uygulanabilir; gevşetme sürümlü, gerekçeli ve bekleme süreli olmalıdır.

17. P&L, tez doğruluğu ve karar kalitesi ayrı gerçeklerdir; biri diğerinden türetilemez.

18. Counterfactual yalnızca karar anında dondurulmuş alternatif için ölçülebilir; sonradan seçilmiş kıyas geçersizdir.

19. Performans sonucu capital policy’yi otomatik değiştiremez; yalnızca insan incelemesine sinyal üretir.

20. LLM kaldırıldığında fon daha az açıklayıcı olabilir ama muhasebe, risk, NAV, policy uyumu ve icra gerçekliği daha az doğru olamaz.

## 3. Kullanıcının cevaplaması gerekenler

### A. Olmadan başlanamayacaklar

1. **Fon perimetresi:** Hangi broker hesapları ve nakit bakiyeleri bu havuza dahildir, açılış tarihi nedir?  
   Cevapsızsa açılış portföyü ve NAV kurulamaz.

2. **Raporlama para birimi:** Kanonik NAV USD mi, TL mi; diğeri yalnızca bağlam serisi mi olacak?  
   Cevapsızsa performans ve risk tek bir ölçüm tabanında hesaplanamaz.

3. **Sermaye amacı ve kullanım ihtiyacı:** Para hangi ufukta yönetilecek ve öngörülebilir çekim/rezerv ihtiyacı var mı?  
   Cevapsızsa deployable capital ve asgari nakit belirlenemez.

4. **Risk zarfı:** Kabul edilebilir portföy drawdown’ı, pozisyon başına loss budget ve mutlak tek-isim tavanı nedir?  
   Cevapsızsa güvenli pozisyon büyüklüğü veya proposal üretilemez.

### B. Varsayılan çıpayla başlayabilecekler

- Azami aktif pozisyon: **10**
- Readiness eğimi: **starter 0,5×; core 1,0×; exceptional başlangıçta kapalı**
- Operasyonel nakit tabanı: **%2**
- No-trade bandı: **maksimum(1 yüzde puan, hedef ağırlığın %20’si)**
- Proposal fiyat toleransı: **initiate/add için %2–3**
- Drawdown inceleme eşikleri: **-%10 uyarı, -%15 ekleme dondurma, -%20 tam yeniden inceleme**
- Driver yoğunluğu: başlangıçta **soft review**, hard limit değil
- Policy gevşetme bekleme süresi: **30 gün veya sonraki üç aylık policy incelemesi**
- Likidite varsayımı: aylık yeniden ölçülür; non-binding olduğu sürece yalnız izlenir
- Aylık portföy incelemesi: varsayılan **no_change**

Bunlar optimal oldukları için değil, ilk gerçek verilerle kalibre edilebilir başlangıç çıpaları oldukları için kullanılabilir.

## 4. İlk hafta

1. Fon perimetresini, raporlama para birimini, sermaye amacını ve risk zarfını karara bağla.

2. Broker’dan açılış tarihine ait pozisyon, nakit ve mümkünse tam işlem ekstresini değişmeden dışa aktar.

3. Capital Policy v0’ı sürümlü biçimde doldur; varsayılan kullanılan her sayıyı açıkça “provisional” işaretle.

4. Açılış portföyünü elle çıkar ve broker ile pozisyon/nakit bazında uzlaştır; açıklanamayan farkları kapatmadan listele.

5. Kodlamadan önce mevcut portföy üzerinde manuel bir prova yap: NAV, ağırlıklar, loss budget, hard limitler ve varsayılan `no_change` proposal’ı hesaplanabiliyor mu?

İlk haftanın önceliği kod değil, policy ve broker gerçeğidir. Bilinmeyen veri üzerinde yazılan muhasebe modeli yeniden yazılır.

## 5. Kalan uyarım

En büyük tehlike LLM halüsinasyonu değil, deterministik görünen kuralların sahte kesinlik üretmesidir. Capital Policy v0 kanıtlanmış bir yatırım sistemi değil, açık varsayımlardan oluşan ilk anayasadır; matematik onu tutarlı yapar, doğru yapmaz.

Bu nedenle sistem ilk günden bütün sermaye üzerinde “otorite kazanmış” sayılmamalıdır. En az bir tam broker-ekstre uzlaştırması ve iki gölge proposal döngüsü görülmeden, mevcut portföyü sırf yeni sistem öyle hesapladı diye topluca yeniden kurmak tehlikelidir. İlk canlı yetki kademeli olmalıdır: önce gerçeği doğru kaydet, sonra kararları gölgede üret, en son küçük ve geri döndürülebilir sermaye değişiklikleriyle güven kazan.