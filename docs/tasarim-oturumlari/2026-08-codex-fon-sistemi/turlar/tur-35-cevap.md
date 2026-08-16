Önce düzeltme: önceki formüldeki `target_weight` adı fazla iddialıydı. Formül nihai hedefi değil, **policy’nin izin verdiği ağırlık bandını ve üst kapasiteyi** hesaplar. Hangi isimlerin portföye gireceği ve bağlayıcı olmayan riskler nedeniyle bu kapasitenin ne kadarının kullanılacağı hâlâ bir karar problemidir.

## 1. Pozisyon başına downside kayıp bütçesi

V0 için savunulabilir başlangıç aralığım:

- **Starter:** 50–75 bp NAV
- **Core:** 75–125 bp NAV
- **Normal merkez:** 100 bp NAV
- **İnsan onaylı hard tavan:** 150 bp NAV

Bu bir piyasa standardı değil, tasarım çıpasıdır. On pozisyonun tamamı tanımlanmış downside senaryosuna aynı anda ulaşırsa 100 bp merkez yaklaşık %10 NAV kaybı üretir. Korelasyon, gap ve rejim stresi için ayrıca daha ağır portföy stress senaryosu gerekir; downside bütçesi gerçek kaybın mutlak tavanı değildir.

Örnek:

```text
downside_capacity_weight =
    allowed_position_loss_bps / absolute_downside_return
```

%25 downside varsayımında:

- 50 bp → %2 ağırlık
- 100 bp → %4 ağırlık
- 150 bp → %6 ağırlık

Downside tahmini zayıfsa bütçe büyütülmez; ağırlık küçültülür veya isim watchlist’te kalır.

## 2. Hedef portföyü kim kurar?

Üç katman vardır:

### Deterministik güvenlik çekirdeği

Şunları hesaplar:

- Mevcut ağırlıklar ve nakit.
- Base/readiness bandı.
- Downside kayıp kapasitesi.
- Tek-isim ve sektör kapasitesi.
- Nakit ve operasyonel kapasite.
- No-trade bandı.
- Limit ihlalleri.
- Verilen hedefin gerektirdiği işlem listesi.

Bunun çıktısı “optimal portföy” değil:

```text
eligible_weight_band
policy_compliant_max_weight
binding_constraints
```

olmalıdır.

### Analitik yargı

Şunları matematik tek başına belirleyemez:

- Downside senaryosunun gerçekten makul olup olmadığı.
- İki tezin aynı gizli faktör riskini taşıyıp taşımadığı.
- Valuation aralığının güvenilirliği.
- Catalyst/path riskinin tarihsel volatiliteden daha önemli olup olmadığı.
- Yeni adayın mevcut pozisyona göre fırsat maliyeti.
- Nitel veri boşluklarının büyüklüğü.
- Policy’nin izin verdiği ağırlığın tamamının kullanılıp kullanılmaması.

### İnsan yetkisi

İnsan:

- Readiness sınıfını ve downside girdisini kabul eder.
- Karşılaştırmalı trade-off’u çözer.
- Nihai hedef portföyü onaylar veya gerekçeli override eder.

Dolayısıyla sonuç:

- Deterministik hesaplayıcı sistemin **güvenlik çekirdeğidir**.
- Hedef portföy bütünüyle deterministik değildir.
- LLM portföy optimizer’ı değildir.
- `portfolio-risk-management`, her pozisyon için zorunlu değildir; qualitative exposure, event-gap, sıra dışı büyüklük veya risk çatışması olduğunda support olabilir.
- Skill policy limitini genişletemez; ancak deterministik tavanın altında daha küçük pozisyon önerebilir.

Tam otomatik hedef portföy isteseydik ortak bir beklenen getiri dağılımı, risk/covariance modeli ve açık optimizasyon amacı gerekirdi. Bugün bunların hiçbiri yok.

## 3. Fırsat maliyeti

V0 için **(ii) replacement hurdle** yaklaşımını savunuyorum; nihai trade-off yalnız hurdle geçildiğinde insana gelir. Bütün investable set’i sahte hassasiyetli tek puana sıralamazdım.

Varsayılan kural:

> Mevcut pozisyon statüko avantajına sahiptir; yeni aday, yalnız “iyi” olduğu için değil, finanse edeceği pozisyondan belirgin biçimde daha iyi olduğu için yer açabilir.

Süreç:

1. Yeni adayın kendi policy-compliant bandı hesaplanır.
2. Nakit yeterliyse ve pozisyon tavanı dolu değilse replacement gerekmez.
3. Bir kısıt bağlayıcıysa olası kaynak pozisyonlar belirlenir.
4. Yeni aday ile en zayıf uygun incumbent arasında `replacement_case` hazırlanır.
5. Aday hurdle’ı geçmiyorsa sonuç otomatik `retain_incumbent`.
6. Hurdle geçiliyor ama trade-off varsa insan karar verir.

Karşılaştırma alanları:

- Readiness sınıfı.
- Valuation anchor ve fiyat tarihi.
- Downside/base/upside getiri aralığı; olasılık ağırlıklı EV şart değil.
- Önerilen ağırlıkta downside kaybı, bp NAV.
- Tez/falsifier kalitesi ve veri tazeliği.
- Catalyst ve beklenen çözülme ufku.
- Portföye eklenen sektör/driver yoğunlaşması.
- Mevcut pozisyonlarla risk örtüşmesi.
- İzleme yükü.
- Turnover, spread/komisyon ve tanımlıysa vergi etkisi.
- Yeni aday alınmazsa ve incumbent tutulursa alternatif maliyet.

`replacement_hurdle` şu biçimde olabilir:

- Aday readiness bakımından daha düşük olamaz.
- Downside kaybı daha kötü olacaksa bunu karşılayan açık bir valuation/reward üstünlüğü gerekir.
- Hard risk veya kapasite durumunu kötüleştiremez.
- İyileşme işlem eşiğini aşmalıdır.
- Veri karşılaştırılamıyorsa sonuç `indeterminate`, işlem yoktur.

Bu, kesin beklenen getiri tahmini gerektirmez. Fakat **insansız ve tamamen otomatik “hangisi?” kararı** istenirse ortak bir expected-return/risk ölçüsü kaçınılmazdır. V0 böyle bir kesinliği taklit etmemelidir.

## 4. `portfolio_proposal` içeriği

### Kimlik ve geçerlilik

- `proposal_id`
- `proposal_version`
- `portfolio_id`
- `generated_at`
- `decision_type`
- `status`
- `valid_until`
- `supersedes_proposal_id`
- `trigger_event_ids`

### Sabitlenmiş girdiler

- `capital_policy_ref`: kimlik, sürüm, hash
- `portfolio_snapshot_ref`: NAV, nakit, pozisyonlar, as-of, hash
- `market_snapshot_ref`: fiyat/FX zamanı ve kaynakları
- `research_snapshot_refs`: tez, readiness, valuation ve downside sürümleri
- `calculator_version`
- `missing_or_stale_inputs`

### Mevcut ve hedef durum

Her security için:

- `security_id`
- `current_quantity`
- `current_weight`
- `eligible_weight_band`
- `policy_compliant_max_weight`
- `proposed_target_weight`
- `target_weight_reason`
- `readiness_class`
- `thesis_ref`
- `valuation_anchor_ref`
- `downside_case_ref`
- `downside_loss_bps_nav`
- `binding_constraints`
- `unused_capacity_reason`

Portföy düzeyinde:

- `current_cash_weight`
- `target_cash_weight`
- `invested_weight`
- `target_position_count`
- sektör ve diğer tanımlı exposure toplamları
- portföy downside/stress özeti

### Geçiş ve işlem etkisi

- `weight_delta`
- `no_trade_band`
- `band_crossed`
- `proposed_trade_notional`
- tahmini adet; yalnız preview
- `estimated_cost`
- `cash_impact`
- `turnover`
- `tax_treatment_status`
- `trade_eligible`
- `trade_block_reason`

Onay sonrasında gerçek `trade_list` ayrı nesne olmalıdır; proposal içinde yalnız işlem önizlemesi bulunur.

### Kontroller ve karar

- Her limit için `pass/fail`, değer, sınır ve kalan kapasite.
- `recommended_action`: `no_change`, `rebalance`, `risk_remediation`, `cash_deployment`, `blocked`.
- Portföy-geneli gerekçe.
- İnsan kararı ve override gerekçesi.
- Proposal’ı geçersiz kılacak koşullar.

### Alternatifler

Evet, proposal alternatif taşımalıdır; fakat sınırlı:

- Her zaman `status_quo`.
- Birincil öneri.
- Yalnız maddi trade-off varsa en fazla bir veya iki alternatif.

Örneğin:

- incumbent’ı tut,
- incumbent’ı çıkarıp challenger’ı al,
- challenger’ı nakitten starter olarak ekle.

Onlarca optimize edilmiş portföy sunmak insan kapısını karar tiyatrosuna çevirir. Alternatifler yalnız gerçek karar çatallarını göstermelidir.

## 5. Proposal’ı ne tetikler?

Takvim bir **review** tetikler; her review proposal üretmez.

### Takvimsel

| Tetikleyici | Sonuç |
|---|---|
| Haftalık izleme | Tez/risk/veri sapması taranır; eşik aşılmazsa proposal yok |
| Aylık sermaye incelemesi | Bütün kitap yeniden hesaplanır; varsayılan `portfolio_review_completed: no_change` |
| Üç aylık policy incelemesi | Policy’nin uygunluğu değerlendirilir; otomatik portföy değişikliği doğurmaz |

Aylık review ancak hedef bandı, replacement durumu veya hard limit değişmişse proposal üretir.

### Olay-güdümlü ve acil

Bunlar takvimi beklemez:

- Fonlanmış tez `broken` veya `closed`.
- Hard issuer/sector/cash/risk limiti ihlali.
- Pozisyonun reconcile edilememesi veya gerçek state’in `unknown` olması.
- Kurumsal işlem nedeniyle miktar/nakit değişmesi.
- Büyük dış nakit girişi veya çıkışı.
- Yeni capital policy sürümünün etkinleşmesi.
- Fill veya iptal sonrası açık proposal’ın state ile uyumsuzlaşması.

`position_unknown` durumunda yeni sermaye proposal’ı üretilmez; önce state düzeltilir.

### Olay-güdümlü fakat ertelenebilir

- Tez `review_required`.
- Yeni adayın replacement hurdle ön-elemesini geçmesi.
- Valuation/downside/readiness değişikliği.
- Fiyat hareketinin no-trade bandını aşması.
- Sektör veya pozisyon ağırlığının limite yaklaşması.
- Nakit ağırlığının review eşiğini aşması.

Bunlar tek tek proposal yağmuru üretmemeli. Aynı karar penceresindeki olaylar birleştirilerek en güncel snapshot üzerinde tek proposal hazırlanmalıdır.

### Proposal invalidasyonu

Aşağıdakiler açık proposal’ı geçersiz kılar ve yeni sürüm gerektirir:

- Policy sürümü değişti.
- Broker fill geldi.
- NAV/fiyat, tanımlı toleransın ötesinde değişti.
- Tez governance state’i değişti.
- Yeni hard limit ihlali oluştu.
- Dayanak artefakt bayatladı veya düzeltildi.

## Net sınır

Hedef portföyün sahibi tek başına LLM veya hesaplayıcı değildir:

```text
Araştırma/LLM
→ adjudicated readiness + downside + valuation

Deterministik hesaplayıcı
→ izin verilen ağırlık bandı + binding constraints

Replacement hurdle
→ değişiklik gerçekten tartışmaya değer mi?

İnsan
→ nihai hedef portföy onayı

Deterministik icra hazırlığı
→ önerilen işlem listesi
```

Böylece LLM sermaye miktarını keyfî belirlemez; matematik de fırsat maliyetini çözmüş gibi davranmaz.