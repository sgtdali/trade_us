## 1. Altı turun özeti

Kullanıcının itirazı haklıydı: manuel işlem girişi kolay olduğu için araştırma operasyonunu ve tez takibini de insana bırakmak yanlış bir genellemeydi. Yeni sistem, genel router yerine önceden onaylanmış sabit dispatch kurallarıyla kanıtı gözler, gerekli skill recipe’sini otomatik çalıştırır ve sonucu insanın önüne getirir. Her tez artık kalıcı bir lifecycle nesnesi, assessment tarihli fotoğrafı, monitoring contract ise 1–2 mekanik ve 1–2 nitel koşul taşıyan sürümlü alt belgedir. Makine tezi takip eder ve `review_required` üretebilir; `broken/closed` hükmü ile sermaye kararı insanda kalır. Discovery de kapsam dışı değildir: mevcut kitabın otomatik izlenmesi kanıtlandıktan sonra aynı dispatch mekanizmasına eklenir.

## 2. Etiket değişiklikleri

### `AKTİF`e taşınanlar

- **Otomatik skill orkestrasyonu:** Genel router biçiminde değil; gözlemci → sabit dispatch kuralı → kapalı recipe → validator → inbox akışı olarak aktiftir.
- **Tez lifecycle’ının küçük çekirdeği:** `thesis`, tarihli `assessment_record`, `active/review_required/broken/closed`, sürümlü `monitoring_contract` ve insan adjudication’ı aktiftir.
- **Otomatik tez takibi:** Yeni kanıtta mekanik kontrol, nitel soruların pack’e enjeksiyonu, `monitoring_coverage: healthy/degraded/blind` ve körlükte risk artırımının bloklanması aktiftir.
- **Seçilmiş skill adapter’ları:** Önce deep-dive/tracker izleme recipe’si, ardından düşük frekanslı idea-generation discovery recipe’si aktiftir.

### `REFERANS`ta kalanlar

- Tam **23 skill envanteri ve 10+1 genel katalog**; yalnız kullanılan küçük alt küme uygulanacaktır.
- **Lead/support router, research case/episode ve support bütçeleri**; sabit dispatch tablosu bunların yerini alır.
- **A0–A4 merdiveni**; başlangıçta yalnız `shadow` ve `live_manual_execution` ayrımı vardır.
- **Risk-driver registry**; gerçek yoğunlaşma problemi tekrarlandığında etkinleşir.
- Tez lifecycle’ının provenance, genel capability resolution ve çok katmanlı manifest gibi kurumsal uzantıları.

## 3. Yeni tek sayfa

### Ürün

Sistem, 5–10 hisselik tek kişilik portföyde işlemleri elle kaydeden, capital policy’yi hesaplayan, karar anını donduran, filing/fiyat/vade olaylarını otomatik izleyen ve gerekli araştırma skill’lerini kendisi çalıştıran küçük bir portföy karar günlüğüdür. Sistem araştırmayı ve takibi yürütür; araştırma hükmünü kabul etmez, tezi kendiliğinden kapatmaz, sermaye kararını vermez ve emir iletmez.

### Kalıcı domain nesneleri

1. `capital_policy` — boyutlandırma ve işlem kuralları  
2. `account_event` — elle girilen alım, satım ve nakit hareketi  
3. `thesis` — kalıcı tez, lifecycle durumu ve monitoring contract  
4. `assessment_record` — insan tarafından kabul edilmiş tarihli tez değerlendirmesi  
5. `decision_record` — al/azalt/tut/no-change kararı ve karar anındaki girdiler  

İç operasyon için ayrıca `monitoring_check_record` ve `research_job_record` tutulur. Kuyruk, trigger ve attempt ayrı domain nesnesi değildir.

### Temel komutlar

```text
fund trade record
fund thesis open
fund assess
fund trade-preview
fund inbox
fund adjudicate <job_id>
fund review
fund research-cycle
```

`fund research-cycle` her gece Task Scheduler tarafından çalıştırılır. `fund inbox` otomatik iş ve hata kuyruğudur; `fund review` aylık sermaye karar oturumudur.

### Otomatik akış

```text
SEC/fiyat/vade gözlemi
        ↓
kapalı dispatch kuralı
        ↓
dedup + cooldown
        ↓
deep-dive / tracker gibi sabit recipe
        ↓
contract validation
        ↓
Q0/Q1/Q2 inbox
        ↓
iki aşamalı insan adjudication’ı
        ↓
assessment_record
        ↓
trade-preview / aylık karar
```

İnsan ilk aşamada araştırma hükmünü, ağırlık ve P&L etkisini görmeden değerlendirir; ikinci aşamada kabul edilen hükmün portföy etkisini görür.

### İnşa sırası

1. SQLite, beş domain nesnesi ve manuel işlem/NAV projection’ı  
2. Capital policy, assessment ve trade-preview  
3. Thesis lifecycle ve monitoring contract  
4. Metrik eşleme doğrulaması ve mekanik kontrol motoru  
5. Research job, dedup, retry ve Q0/Q1/Q2 inbox  
6. Tek filing recipe’si: deep-dive → tracker → adjudication  
7. `fund research-cycle`, watermark, heartbeat ve Task Scheduler  
8. Review vadesi, fiyat şoku ve earnings tetikleyicileri  
9. Monitoring canlılığı ve adjudication kalite uyarıları  
10. Düşük frekanslı otomatik discovery  

**Adım 7’den sonra sistem kendi kendine çalışan ilk sürümdür.**

### Şimdi yapılmayacaklar

- Broker importer ve çok eksenli reconciliation motoru
- Genel capability router, lead/support ve episode mimarisi
- Keyfî kullanıcı tanımlı dispatch dili
- Otomatik `broken/closed` veya otomatik emir
- Çok seçenekli portföy optimizasyonu
- `capital_input_manifest`
- Tam A0–A4 yetki merdiveni
- Attribution ve counterfactual motoru
- Risk-driver registry

### Büyütme tetikleyicileri

- İkinci broker veya belirgin işlem hacmi → importer/reconciliation
- Sabit recipe’lerin cevaplayamadığı tekrar eden işler → sınırlı routing
- 6–12 aylık karar geçmişi → attribution/counterfactual
- Tekrarlayan ortak sürücü yoğunlaşması → risk-driver registry
- Shadow/live ayrımının yetersiz kalması → daha ince yetki merdiveni
- Yılda 12’den fazla alarm veya tekrarlayan `blind` durum → yeni özellik değil, monitoring kalibrasyonu

## 4. Son söz

**Otomasyona hatırlama, gözleme ve çalıştırma işini ver; araştırma hükmünü ve sermaye yetkisini verme.**