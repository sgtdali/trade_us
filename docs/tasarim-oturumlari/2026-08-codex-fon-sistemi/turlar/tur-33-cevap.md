Evet, bu düzeltme ürün sınırını kökten değiştiriyor. “Capital policy yok, dolayısıyla portföy yönetimini kapsam dışına alalım” sonucu yanlıştı. Doğru sonuç: **capital policy yokluğu ürünün sınırı değil, ürünün ilk tasarım problemidir.**

Bir varsayımı açık koyuyorum: “fon”u şimdilik tek bir sermaye havuzunu yöneten, long-only, insan icralı bir strateji olarak yorumluyorum. Dış yatırımcılı hukuki bir fon kastediliyorsa katılma payı, giriş/çıkış, ücret, resmi NAV, saklama, denetim ve uyum ayrı bir sistem katmanı gerektirir.

## A. Araştırma sistemi ile fon yönetim sistemi arasındaki fark

Bu, araştırma sisteminin üzerine portföy modülü eklemek değildir. Sistemin aggregate root’u değişir:

- Araştırma sisteminin merkezinde `research_case/thesis` vardır.
- Fon yönetim sisteminin merkezinde `fund/portfolio` ve onun zaman içindeki sermaye durumu vardır.
- Araştırma, portföy kararının girdilerinden yalnızca biridir.

Temel döngü de değişir:

`mevcut portföy → fırsat/tez seti → hedef portföy → insan onayı → işlem önerileri → insan icrası → fill/reconciliation → NAV/risk/performance → yeni karar`

Bugünkü tasarım ise ağırlıkla:

`keşif → araştırma → pitch → tez → izleme`

döngüsünü kuruyor. İlk döngü ikincisini kapsar; tersi doğru değildir.

| Birinci sınıf nesne | Fon sistemindeki anlamı | Bugünkü tasarım |
|---|---|---|
| `fund/account` | Sermayenin ve karar yetkisinin sınırı | Yok |
| `capital_policy` | Amaç, risk bütçesi, nakit, yoğunlaşma ve işlem kuralları | Yok |
| `security_master` | Ticker’dan bağımsız menkul kıymet kimliği | Kısmi |
| `cash_and_flows` | Nakit, temettü, ücret, para girişi/çıkışı, FX | Yok |
| `transaction/fill` | Gerçekleşmiş alım/satımın değişmez kaydı | Tasarlanmış ama kısmi |
| `position/lot` | Gerçek sahiplik ve maliyet temeli | Kısmi |
| `valuation/NAV_snapshot` | Portföyün belirli anda ne ettiği | Yok |
| `risk_exposure/limit` | Yoğunlaşma, sektör, faktör, likidite, drawdown | Yok |
| `portfolio_proposal/target` | Mevcut portföyden hedef portföye sermaye kararı | Yok |
| `order_proposal` | Onaylı hedefin uygulanabilir işlem listesi | Yok |
| `performance/attribution` | Getiri, katkı, zarar ve karar kalitesi | Yok |
| `research_case/thesis/evidence` | Menkul kıymet hakkındaki araştırma görüşü | Güçlü |
| `reconciliation/corporate_action` | İç kayıt ile broker/saklama gerçeğini uzlaştırma | Kısmi |

On üç ana nesnenin sekizi tamamen yok, dördü kısmi, yalnız araştırma/tez tarafı güçlü. Dolayısıyla bugünkü sistem fon sisteminin çekirdeği değil; onun araştırma alt sisteminin ayrıntılı bir taslağıdır.

## B. Bugünkü tasarımın yapısal olarak yanlış tarafları

Senin üç tespitin doğru. Üzerlerine şunları eklerim:

1. **Tez yanlış aggregate root oldu.**  
   Fonun kararı “NVDA tezi geçerli mi?” değil, “mevcut nakit ve diğer pozisyonlar varken NVDA’ya ne kadar sermaye ayrılmalı?”dır.

2. **Portföy kararı için nesne yok.**  
   Ticker bazlı `add/hold/trim/exit`, hedef ağırlıkları toplamı, nakit kullanımı, turnover ve diğer isimlerden finansmanı açıklamaz.

3. **`thesis_opened` yanlış biçimde sermayeden koparıldı.**  
   Yeni anlamı “investable set’e kabul edilen resmî görüş” olmalı; yine doğrudan alım değildir ama artık sermaye değerlendirmesinin meşru girdisidir.

4. **“Sistem işlem öneremez” sınırı fazla genişledi.**  
   Emir iletmemek doğrudur; hedef portföy, ağırlık ve işlem önerisi üretememek fon yönetim işlevini ortadan kaldırır.

5. **Capital policy eksikliği scope gerekçesi yapıldı.**  
   Araştırma mandate’i ile capital policy ayrımı doğruydu; bundan çıkardığımız ürün sınırı yanlıştı.

6. **Nakit görünmez.**  
   Fon yalnız hisselerden oluşmaz; nakit de pozisyondur ve yeni alımın kaynağını belirler.

7. **NAV ve performans yok.**  
   Gerçekleşmiş/gerçekleşmemiş P&L, temettü, FX, ücret, zaman ağırlıklı getiri ve sermaye akışları olmadan sistem kendi kararlarını değerlendiremez.

8. **Çapraz pozisyon etkisi yok.**  
   İki ayrı iyi tez aynı sektör/faktör riskini taşıyabilir; isimlerin ayrı ayrı iyi olması portföyün iyi olduğu anlamına gelmez.

9. **Fırsat maliyeti modellenmiyor.**  
   Bir isme sermaye vermek başka bir isimden veya nakitten vazgeçmektir; bugünkü araştırma akışında bu karşılaştırmanın sahibi yoktur.

10. **İzleme yalnız tez sağlığına odaklı.**  
    Fon ayrıca nakit ihlali, yoğunlaşma, drawdown, pozisyon büyümesi, veri bayatlığı ve gerçekleşmeyen işlem kararlarını izlemelidir.

11. **Tek gerçeklik kaynağı ilkesi fazla geneldi.**  
    Araştırma ve iç kararlar için sistem otorite olabilir; fills/cash için broker veya saklamacı, fiyat için piyasa veri kaynağı dış otoritedir. Tek defter yerine açık bir source-of-truth matrisi gerekir.

12. **`portfolio-risk-management` yanlış gerekçeyle gereksiz sayıldı.**  
    Artık koşullu olarak gereklidir; fakat hâlâ portföy-geneli allocator değildir. Tek pozisyonu capital policy ve portföy bağlamı altında boyutlandırabilir, bütün hedef portföyü kuramaz.

Ayakta kalan önemli kararlar da var: company/security/action ayrımı, kanıt provenance’ı, security kimliği, insan icrası, idempotency, reconciliation ve tez izleme hâlâ doğrudur. Yıkılması gereken araştırma kalitesi değil, onun sistemin merkezi sayılmasıdır.

## C. Sıralama tersine dönmeli mi?

**Evet, fakat “önce pozisyon tablosu” kadar basit değil. Önce minimum fon dikey dilimi kurulmalı.**

Doğru sıra bence şu:

1. **Fon tanımı ve capital policy v0**

   Amaç/ufuk, baz para birimi, nakit yaklaşımı, uygun araçlar, pozisyon sınırları, yoğunlaşma kuralları, risk/loss bütçesi, turnover eşiği, karar kadansı, değerleme kaynağı ve override yetkisi açıkça tanımlanır. Benchmark zorunlu değildir; benchmark’sız mutlak getiri politikası mümkündür.

2. **Açılış defteri**

   Broker snapshot’ından hesap, nakit, pozisyon, maliyet, para birimi ve as-of bilgisi alınır; `unknown` bırakılan alanlar görünürdür.

3. **Valuation, NAV ve performans omurgası**

   Fiyat/FX kaynaklarıyla günlük veya karar-anı NAV’ı; gerçekleşmiş/gerçekleşmemiş P&L; temettü ve dış nakit akışları deterministik hesaplanır.

4. **Portföy karar nesnesi**

   Mevcut portföy, hedef ağırlıklar, nakit etkisi, risk/limit kontrolleri, turnover ve karar gerekçesi tek sürümlü `portfolio_proposal` içinde bulunur.

5. **İnsan onayı ve icra köprüsü**

   Onaylanan hedef deterministik olarak işlem önerilerine çevrilir; insan broker’da uygular; fills sisteme alınır ve uzlaştırılır.

6. **Araştırma entegrasyonu**

   Pitch/tez, investable set ve beklenen getiri/risk girdisini besler. Araştırma olmadan ilk testte insan tarafından girilen geçici görüşler kullanılabilir.

7. **Tez/olay izleme ve discovery**

   Fon omurgası çalıştıktan sonra tracker, earnings ve idea-generation sermaye döngüsünü besler.

İlk uçtan uca ispat şu olmalı:

`opening snapshot → hedef portföy önerisi → insan onayı → işlem önerisi → insan fill girişi → reconciliation → yeni NAV/performance`

Bu, araştırma plugin’lerinden önce yapılabilir.

“Portföy varsa kötü de olsa fon olur” cümlen ancak capital policy, hedef karar ve performans döngüsü de varsa doğrudur. Yalnız pozisyon/nakit defteri fon değil, broker aynasıdır.

Mevcut deneme koşularının değersiz olduğu düzeltmesi nedeniyle önceki “mevcut hattı koruyarak yamala” tavsiyemi de geri çekiyorum. Legacy tetikleyiciler kapatılabilir; 26 Ağustos köprüsü ancak yeni kanıt hattı için test fixture’ı olarak istenirse yapılmalıdır. Greenfield başlangıcın ilk dikey dilimi artık araştırma değil, minimum fon döngüsüdür.

## D. İnsan icrası ilkesi korunabilir mi?

**Evet; hatta tutarlı ve yaygın bir görev ayrımıdır.** Fon yönetimi ile piyasa icrası aynı iş değildir.

Sınır şöyle konmalı:

| Aşama | Sistem | İnsan |
|---|---|---|
| Mevcut durum | Pozisyon, nakit, NAV, risk ve performansı hesaplar | Uyuşmazlıkları çözer |
| Sermaye kararı | Hedef portföy ve alternatifleri üretir | Öneriyi onaylar, reddeder veya gerekçeli değiştirir |
| İşlem hazırlığı | Hedef farkından önerilen işlem listesini hesaplar | Listeyi kontrol eder |
| Emir icrası | Broker emri göndermez, değiştirmez veya iptal etmez | Broker’da emri girer ve yönetir |
| Gerçekleşme | Fill’leri içeri alır ve uzlaştırır | Eksik/yanlış eşleşmeyi çözer |
| Sonrası | NAV, risk, performans ve attribution’ı yeniler | Yeni sermaye kararını verir/onaylar |

Bu nedenle eski ilke şu şekilde düzeltilmeli:

> **Sistem broker’a otomatik emir iletmez; sistem hedef portföy, sermaye kararı ve uygulanabilir işlem önerisi üretebilir. Gerçek emir gönderimi ve dış dünyadaki icra yalnız insana aittir.**

Durum akışı da açık olmalı:

`portfolio_proposal_generated → human_approved/rejected → trade_list_staged → human_submitted → broker_acknowledged → partial/filled/cancelled → reconciled`

İnsan broker’da öneriden farklı işlem yaparsa bu sessizce mevcut karara yazılmaz; yeni sürüm veya gerekçeli override olur.

Son hükmüm: **Araştırma sistemi artık ürün değil, fon yönetim sisteminin bir alt sistemidir. İlk tasarlanması gereken şey tez lifecycle’ı değil, capital policy ile kapanan muhasebe–karar–icra–performans döngüsüdür.**

Bir sonraki tasarım kararını kökten değiştirecek tek açık soru şudur: “fon”, tek sahibin tek/çok broker hesabını yöneten bir strateji motoru mu, yoksa dış yatırımcıları, katılma payını, ücretleri ve resmi NAV’ı olan hukuki bir fon mu?