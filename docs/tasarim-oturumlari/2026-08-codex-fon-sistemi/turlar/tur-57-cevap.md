Ana karar: adjudication tek ekranlı “kabul et” işlemi olmamalı. **Önce araştırma hükmü sermaye sonucundan bağımsız yargılanmalı, sonra bu kabulün portföy etkisi gösterilmelidir.** Aksi hâlde kullanıcı, kabul edeceği downside’ın kendisini satışa zorlayacağını görüp analitik hükmü yumuşatabilir.

## 1. Adjudication pratiği

### Aşama A — Araştırma hükmü

Kullanıcı şunları görür:

- Önerilen downside senaryosunun causal zinciri
- Temel varsayımlar, dönemler, birimler ve para birimi
- Her önemli sayı için kaynak referansı
- Mevcut kabul edilmiş case ile alan bazında fark
- Yeni, çelişkili ve eksik kanıtlar
- Thesis falsifier’larıyla bağlantı
- Validator sonuçları
- `independent_then_reconcile` kullanıldıysa bağımsız sonuç ile önceki case arasındaki fark

Bu aşamada şunları görmez:

- Pozisyon ağırlığı ve P&L
- Ortalama maliyet
- Önerilen trade
- Downside kabul edilirse oluşacak hedef ağırlık
- `capital_at_risk`
- Skill/model kimliğini otorite rozeti gibi öne çıkaran bilgi

Skill/model provenance’ı audit panelinde bulunabilir; karar ekranının merkezinde olmamalıdır.

Kullanıcının cevapladığı asgari sorular:

1. Senaryo şirkette nasıl gerçekleşiyor; yalnız keyfî bir fiyat düşüşü mü?
2. Ana varsayımların hangileri kanıt, hangileri yargı?
3. Senaryo tezin hangi iddiasını veya falsifier’ını zorluyor?
4. Maddi bir gap/tail riski dışarıda bırakılmış mı?
5. Bu pozisyona sahip olmasaydım aynı senaryoyu kabul eder miydim?
6. Hangi yeni kanıt bu case’i geçersiz kılar?

### Aşama B — Sermaye etkisi

Araştırma hükmü kaydedildikten sonra sistem yeni downside kapasitesini, eligible bandı, bağlayıcı kısıtları ve olası proposal etkisini gösterir. Bu ikinci karar, capital action onayıdır; birinci hükmü geriye dönük değiştiremez.

Gerçekçi süreler:

- Dar ve maddi olmayan güncelleme: **5–10 dakika**
- Yeni downside case: **20–30 dakika**
- Maddi varsayım değişikliği: **15–30 dakika**
- Kaynak çatışması veya karmaşık senaryo: **30 dakikayı geçiyorsa defer/reject**

Onlarca haftalık adjudication kabul edilebilir değildir. Sistem normal haftada birkaç maddi hüküm üretecek kadar dar tutulmalıdır.

### İnsan sayıyı değiştirirse

`%25 → %35` mevcut önerinin üzerine yazılmaz.

- Model olgusal hata yaptıysa: öneri **reject** edilir; doğru kaynakla yeni case oluşturulur.
- İnsan bilinçli olarak daha muhafazakâr yargı kullanıyorsa: `human_authored_downside_case` üretilir; model artefaktına `derived_from` ile bağlanır, değişen alanlar ve gerekçe kaydedilir.
- Yeni insan case’i aynı şema ve validator’dan geçer.

Bu bir policy override değildir. Override, geçerli bir girdiye rağmen policy sınırını aşmaktır; analitik hükmü yeniden yazmak başka bir şeydir.

## 2. Skill şema-valid çöp döndürürse

Üç kalite katmanı ayrılmalı:

| Katman | Kim yakalar? |
|---|---|
| Şema, zorunlu alan, enum, aralık | JSON Schema |
| Kaynak varlığı, dönem/birim, sayısal tie-out, security/peer kimliği, citation lineage | Deterministik validator |
| Peer setinin anlamlılığı, senaryonun causal makullüğü, teze ilgisi, maddi risklerin eksikliği | İnsan adjudication’ı |

Deterministik olarak “bu sayı gerçekten kaynakta var mı?” kontrol edilebilir. “Bu peer ekonomik olarak doğru mu?” veya “bu downside dünyayı makul temsil ediyor mu?” tamamen deterministik çözülemez. İkinci model yardımcı challenger olabilir ama hakem sayılamaz.

Her sonuç için bir kalite kaydı tutulmalı:

- Contract pass/fail
- Evidence-integrity hataları
- Accept/reject/defer sonucu
- Maddi insan revizyonu sayısı
- Adjudication süresi
- Retry/support sayısı ve maliyeti
- Sonradan bulunan olgusal hata
- Downstream invalidation

Kalite, yalnız skill adına göre değil şu route üzerinden ölçülür:

```text
plugin_version
+ skill_digest
+ model
+ execution_role
+ requested_capability
```

Uydurulmuş kaynak veya yasak sermaye hükmü tek seferde route’u quarantine edebilir. Analitik zayıflıkta ise önceki gölge-kapısı geçerlidir: üç vakanın ikisinde maddi yeniden yazım gerekiyorsa route production için uygun değildir.

## 3. Araştırma ile fiyat çelişirse

Sistem çelişkiyi göstermeli fakat fiyatı tez hakemi yapmamalıdır.

İki ayrı divergence sinyali yeterli:

- `thesis_deteriorating_market_favorable`
- `thesis_intact_market_adverse`

Tracker’ın ilk analitik geçişi fiyat/P&L görmeden yapılır. Ardından ayrı bir market overlay, tez hükmüyle fiyat sonucunu yan yana getirir.

- Tez broken, fiyat yükseliyor: broken hükmü değişmez; governance/wind-down incelemesi devam eder.
- Tez intact, fiyat %40 düşmüş: tez otomatik bozulmaz; fakat drawdown policy’si zorunlu re-underwrite ve risk artırımı dondurması üretir.

Küçük ayrışma yalnız görünür sinyal olabilir. Drawdown, gap veya materiality eşiğini aşan ayrışma zorunlu review açar. Review tamamlanmadan ekleme dondurması kalkmaz.

## 4. Bayat adjudication ve kilitlenme

Kitabın bayatladıkça yeni risk alamaması **doğru güvenlik davranışıdır**. Muhasebe, NAV, hard-limit trim ve exit çalışmaya devam ettiği için teknik deadlock değildir; araştırma kapasitesinin pozisyon sayısını taşıyamadığını gösteren operasyonel tıkanmadır.

“Olduğu gibi uzat” yalnız şu kısa-form incelemeyle mümkün olmalı:

```text
reaffirmed_case_ref
reviewed_evidence_window
reviewed_evidence_refs
material_events_checked
conclusion: no_material_change
reviewer
next_review_due
```

Bu yeni bir adjudication sürümüdür; eski kaydın tarihini değiştirmez. Hiç kanıt bakmadan yapılan `administrative_extension` karar-kritik girdilerde yasaktır.

Ek sınırlar:

- Yeni filing veya earnings varsa “değişiklik yok” tıklaması yetmez; kanıt incelenmelidir.
- Monitoring contract `max_consecutive_reaffirmations` taşıyabilir.
- Belirli sayıda kısa reaffirmation’dan sonra tam refresh gerekir.
- Kuyruk yaşlandıkça öncelik yükselir.
- Bütün kitap stale oluyorsa doğru çözüm süreleri sahte biçimde uzatmak değil; pozisyon sayısını, araştırma derinliğini veya kadansı kapasiteye uydurmaktır.

## 5. İnsan her şeyi onaylıyorsa

Törensel onay kesin olarak ispatlanamaz, fakat güçlü sinyaller üretilebilir:

- Olağandışı kısa adjudication süreleri
- Sürekli %100 kabul oranı
- Hiç reject/defer/revision olmaması
- Aynı gerekçenin tekrar kullanılması
- Kaynak panelinin hiç açılmaması
- Karmaşıklıktan bağımsız aynı sürede karar verilmesi
- Toplu ve art arda onaylar
- Sonradan sık düzeltme veya invalidation çıkması

Bunlar tek tek hüküm değildir; birlikte `adjudication_integrity_review_required` sinyali üretir.

Yüzeyde şu korumalar olmalı:

- “Approve all” yok.
- Accept varsayılan seçenek değil.
- Kullanıcı en azından binding varsayımı ve case’i bozacak kanıtı seçer/yazar.
- Yüksek-reliance case’lerde bir cümlelik karar gerekçesi zorunludur.
- Şüpheli paternde sistem yeni risk artırma yetkisini geçici olarak daraltabilir ve derin review isteyebilir.

Kullanıcı inceleme yapmadan yine de devam etmek isterse sistem gerçeği çarpıtmamalıdır. Kayıt:

```text
acknowledged_without_full_adjudication
```

veya süreli policy override olur; `human_adjudicated` sayılmaz, readiness’i yükseltmez ve normal capital input kapısını karşılamaz.

En önemli sınır şu: **Kullanıcı kendi parasında istediğini yapabilir; sistem bunu “disiplinli adjudication yapıldı” diye yalanlayamaz.**