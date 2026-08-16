Araştırma kuyruğunu yalnız keşif ritmiyle sürmek artık yanlış. Fon bağlamında araştırmanın amacı “şirket hakkında daha çok şey bilmek” değil, **sermaye kararındaki maddi belirsizliği azaltmaktır**.

Ancak sermaye ağırlığı tek öncelik olursa mevcut kitap bütün zamanı emer. Doğru çözüm, tek skordan ziyade sermaye-öncelikli sınıflar ve discovery için korunan asgari kapasitedir.

## 1. Araştırma kuyruğunun sıralaması

Önce toplam 6–9 saatten icra/reconciliation gibi zorunlu operasyon süresi çıkarılmalı. Yüzde paylaşımı kalan araştırma bütçesine uygulanmalıdır.

Önerdiğim leksikografik sıra:

| Öncelik | Araştırma türü | Örnek |
|---|---|---|
| R0 | Sermaye gerçeği bilinmiyor | Position/cash uyuşmazlığına kaynak araştırması |
| R1 | Fonlanmış sermayede acil kayıp riski | `broken` tez, hard limit, drawdown re-underwrite |
| R2 | Fonlanmış pozisyonda yakın karar | Earnings, `review_required`, kayıp bütçesi kullanımı, driver yoğunlaşması |
| R3 | Açık portfolio proposal’ı bloklayan soru | Replacement karşılaştırması, downside/valuation boşluğu |
| R4 | Investable fakat fonlanmamış challenger | Mevcut en zayıf pozisyonla karşılaştırılabilecek aday |
| R5 | Yeni discovery | Evren taraması ve erken fikir üretimi |

Aynı sınıf içinde bağlayıcı ölçüler:

- Risk altındaki sermaye, bp NAV.
- Karar son tarihi.
- Belirsizliğin maddiliği.
- Çalışmanın kararı değiştirme ihtimali.
- Tahmini insan/model süresi.
- Kanıtın bayatlama tarihi.

Tek bir matematiksel priority score üretmezdim; ağırlıklar keyfî olur. Bunlar sınıf içi sıralama ve insan görünürlüğü sağlar.

### Kapasite paylaşımı

Sabit %70/%30 tek başına yeterli değildir. **Korunan taban + durum modu** daha doğru:

| Portföy modu | Kitap/karar araştırması | Discovery | Koşul |
|---|---:|---:|---|
| `defensive` | %100 | %0 geçici | R0/R1 açık, drawdown freeze veya bozuk tez |
| `book_maintenance` | %80 | %20 | Kitap dolu, nakit düşük, büyük açık sorun yok |
| `balanced` | %70 | %30 | Normal işletim |
| `deployment` | %50 | %50 | Yüksek nakit, boş pozisyon kapasitesi veya zayıf incumbents |

Discovery, R0/R1 nedeniyle en fazla iki ardışık hafta tamamen preempt edilebilir. Sonrasında en az bir küçük discovery bloğu veya açık bir insan kararı gerekir. Böylece acil sermaye korunur ama pipeline sessizce ölmez.

Bu oranlar toplam saatlerin değil, operasyon sonrasında kalan araştırma kapasitesinin oranıdır.

## 2. Investable set

Tek bir “investable” etiketi fazla bulanık. Dört ayrı küme gerekir:

```text
universe
→ policy_eligible_universe
→ underwritten_investable_set
→ capital_actionable_now
→ funded_portfolio
```

### `policy_eligible_universe`

Deterministik ön eleme:

- ABD listeli.
- Adi hisse.
- Long’a uygun.
- Yasak araç değil.
- Kimlik güvenilir.
- En küçük ekonomik pozisyon için likidite yeterli.
- Tanımlı gap/tail sınırında sıfırdan büyük feasible weight üretilebiliyor.
- Gerekli asgari veri kaynakları mevcut veya edinilebilir.

### `underwritten_investable_set`

Araştırma sonrasında:

- Kabul edilmiş aktif tez.
- Destekli valuation anchor.
- Downside/gap sınıfı.
- Monitoring contract.
- Readiness en az `starter`.
- `eligible_weight_band` sıfırdan büyük.

### `capital_actionable_now`

Ayrıca:

- Nakit veya replacement kaynağı var.
- Position/driver/sector limitleri izin veriyor.
- Proposal girdileri taze.
- Execution validity üretilebiliyor.

Pozisyon tavanının dolu olması bir ismi investable set’ten çıkarmaz. Yalnız `capital_actionable_now` olmasını replacement kararına bağlar.

Mevcut 87 isim zaten ABD common equity ve oldukça likit olduğu için deterministik ilk elemenin büyük bir hacim azaltması beklenmemeli. Muhtemelen yalnız birkaç isim veya hiçbiri elenir; bunu ölçmeden oran uydurmamak gerekir. Bu filtrenin amacı iş yükünü dramatik azaltmak değil, sermaye alamayacak bir nesneye pahalı araştırma başlatılmasını engellemektir.

Gap riski gibi yargı gerektiren alanlar bilinmiyorsa isim sessizce elenmez:

```text
eligibility_status: needs_gap_classification
```

olur.

## 3. Portföy doluyken discovery

Discovery devam etmelidir; aksi hâlde statüko avantajı zamanla statüko dokunulmazlığına dönüşür.

Fakat yoğunluğu azalmalıdır:

- Bütün 87 ismi sürekli taramak yerine küçük challenger batch’leri.
- Yaklaşan maddi olaylar veya belirgin valuation değişiklikleri.
- Mevcut driver yoğunlaşmasını azaltabilecek isimler.
- En zayıf incumbent’a gerçek alternatif olabilecek adaylar.
- Bayat watchlist kayıtlarının seyrek yenilenmesi.

Kitap dolu ve sağlıklıysa discovery’nin amacı “on birinci pozisyon eklemek” değil, **mevcut onuncu pozisyonun hâlâ sermayeyi hak edip etmediğini sınayacak opsiyonellik üretmektir**.

Yoğunluk otomatik olarak portföy state’inden türetilebilir:

- Nakit yüksek veya boş slot varsa artır.
- `broken/review_required` incumbent varsa artır.
- Replacement adayı yoksa korunan minimumu sürdür.
- R0/R1 olayları varsa geçici durdur.
- Drawdown incelemesi tamamlanmadan yeni discovery’yi sermaye proposal’ına çevirmeyi blokla.

Discovery’nin otomatik ayarlanması araştırma sonucunu değil, yalnız bütçe tahsisini belirler; insan isterse modu gerekçeli değiştirebilir.

## 4. Portföyün araştırmaya ürettiği görevler

Evet, risk motoru araştırma kuyruğunun en büyük müşterilerinden biri olur. Ancak risk-güdümlü araştırma ile rutin tez izleme aynı şey değildir.

- **Tez monitoring:** “Yeni kanıt, önceden yazılmış beklenti veya falsifier’dan saptı mı?”
- **Risk-güdümlü araştırma:** “Bu sermaye exposure’ı nedeniyle hangi karar şimdi yeniden ele alınmalı?”

Örnek risk araştırma görevleri:

| Portföy sinyali | Araştırma sorusu | Muhtemel sermaye etkisi |
|---|---|---|
| Kayıp bütçesinin yarısı kullanıldı | Hareket tez kaynaklı mı, driver mı, gürültü mü? | Add freeze, tut, küçült veya re-underwrite |
| Driver yoğunlaşması review eşiğinde | Pozisyonlar gerçekten aynı causal driver’a mı bağlı? | Ağırlıkları azalt veya farklı challenger ara |
| `review_required` tez | Hangi kanıt governance state’i çözer? | Target band değişebilir |
| Likidite varsayımı bozuldu | Çıkış kapasitesi stres altında yeterli mi? | Max weight düşer |
| Yeni nakit geldi | Hangi mevcut tez starter/core sermayeyi hak ediyor? | Cash deployment |
| Hard limit yaklaşıyor | Hangi pozisyon en düşük fırsat maliyetiyle azaltılabilir? | Trim/replacement |

Her görev şunları taşımalı:

```text
originating_risk_event
capital_at_risk_bps
decision_to_inform
decision_deadline
question
possible_capital_effects
required_evidence
```

Bir risk olayı `thesis_tracker`ı çağırabilir; fakat tracker hedef ağırlık vermez. Tracker’ın assessment’ı risk motoruna döner, motor weight bandını yeniden hesaplar, gerekirse portfolio proposal doğar.

## 5. Karar-değeri testi

Bu filtre fazla bürokratik değil; 6–9 saatlik bütçede zorunludur. Fakat şu cümleyi düzeltmek gerekir:

> Araştırma sonucunda sermaye kararının gerçekten değişmesi şart değildir; araştırma başlamadan önce makul sonuçlardan en az birinin kararı değiştirebilmesi gerekir.

“No change” de değerli olabilir: belirsizlik çözülmüş ve mevcut tahsis yeniden doğrulanmış olabilir. Çalışmanın başarı ölçütü işlem üretmek değildir.

Her pahalı research work item şu küçük sözleşmeyi taşımalı:

```text
decision_object:
decision_deadline:
current_uncertainty:
possible_findings:
capital_effect_by_finding:
capital_at_risk_or_potential:
required_evidence:
estimated_effort:
stop_condition:
expires_at:
```

Örnek:

```text
decision_object: NVDA target band
current_uncertainty: AI capex talebi backlog'a dönüşüyor mu?
possible_findings:
  confirmed: core band korunabilir
  mixed: add freeze
  contradicted: review_required / trim proposal
capital_at_risk: 82 bp downside budget
estimated_effort: 45 dakika
```

Discovery için karar nesnesi doğrudan alım olmak zorunda değildir:

```text
decision_object:
  reject
  watch_until
  promote_to_underwriting
```

### Hafif VOI kapısı

Kesin olasılık ve parasal expected value hesaplamazdım. Üç ordinal alan yeterli:

- `decision_impact`: none / low / medium / high / critical
- `decision_changeability`: none / possible / likely
- `effort`: small / medium / large

Kurallar:

- `decision_impact:none` → çalışma açılmaz.
- Kararı değiştirecek hiçbir sonuç dalı yok → çalışma açılmaz.
- `high/critical` + yakın deadline → kitap önceliği.
- Discovery’de düşük yakın etki kabul edilir ama yalnız korunan discovery bütçesinden harcanır.
- Zorunlu policy monitoring’i VOI testinden muaf değildir; onun decision object’i “mevcut tahsisi sürdürmek güvenli mi?”dir.

Ucuz deterministik veri yenilemeleri için tam sözleşme gerekmeyebilir. LLM kullanan veya anlamlı insan süresi isteyen her işte zorunlu olmalıdır.

## Kapalı döngü

```text
portfolio/risk state
→ sermaye etkili araştırma sorusu
→ kanıt + assessment
→ insan adjudication’ı
→ readiness/downside/driver güncellemesi
→ deterministik weight bandı
→ replacement/proposal
→ insan onayı + icra
→ performance/risk sonucu
→ yeni araştırma ve calibration sinyali
```

Net ilke:

> **Araştırmanın önceliğini merak değil risk altındaki sermaye belirler; discovery ise bugünkü sermayeyi korumak için değil, yarının fırsat maliyetini görünür tutmak için korunan bir bütçe alır.**