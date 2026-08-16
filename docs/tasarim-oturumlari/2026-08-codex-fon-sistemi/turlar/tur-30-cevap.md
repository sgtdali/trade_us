Ben **(C)’nin daraltılmış bir biçimini** savunuyorum: V1’i taklit etmeyen, yalnızca yanlış otomatik geçişi durduran ve kanıtı karantinada koruyan bir “26 Ağustos köprüsü”.

(B)’deki gibi sonucu bugünkü deftere `workflow_completed` diye yazmazdım. Deep-dive makinece okunmadığı ve sözleşme doğrulanmadığı hâlde bu olay sahte tamamlanmışlık üretir. (A) ise mevcut preview’lerin en değerli kullanım anını kaçırır.

## 10 günlük plan

1. **Tarih tetikleyicisine emniyet kilidi koy.**

   `date_due`, hiçbir koşulda doğrudan `trigger_satisfied` veya `workflow_ready` üretmemeli. Yalnızca “kanıt kontrolünün zamanı geldi” demeli. `date_status=confirmed` olsa bile tarih, yayının gerçekleştiğinin kanıtı değildir.

2. **Mevcut preview’leri şimdi mühürle.**

   CRM ve NVDA için pack, instructions, result ve mevcut çıkarımın kimlikleri/hash’leri tek bir manifestte referanslanmalı; dosyalar değiştirilmemeli. Manifestte en az `security_id`, dönem, `expectations_known_at`, artefakt hash’leri ve legacy kaynak olayları bulunmalı.

3. **Çok küçük bir kanıt yakalama mekanizması kur.**

   Yeni 8-K accession’ı, Item 2.02 ve ekleri; şirket IR basın bülteni/sunum URL’leri; yayın ve gözlem zamanları; SHA-256 ve media type kaydedilmeli. İki seviye yeterli:

   - `release_observed`: sonuç yayını görüldü.
   - `evidence_available`: karşılaştırma yapmaya yetecek birincil belge indirildi ve dönemi doğrulandı.

   Transcript bekleniyorsa çalışma `release_only` olarak açıkça etiketlenebilir; transcript geldiğinde tamamlama yapılabilir.

4. **Deep-dive’ı elle çalıştır, fakat eski deftere domain sonucu yazma.**

   Girdi, mühürlenmiş preview + yeni kanıt paketi olmalı. Çıktıyla birlikte küçük bir `post_print_bridge.v1` sidecar’ı üretilebilir:

   - preview beklentisi,
   - gerçekleşen değer,
   - karşılaştırılabilirlik sınıfı,
   - kaynak referansı,
   - farkın açıklaması,
   - cevaplanamayan sorular,
   - `release_only | full_post_print` kapsamı.

   Sonuç, sidecar, doğrulama raporu ve manifest `quarantined / not_domain_committed` olarak saklanmalı. `workflow_completed`, tez durumu veya sermaye eylemi yazılmamalı.

5. **V2 göç yolunu baştan tanımla.**

   Bu paket daha sonra V2’ye aktarılırken olayın gerçek `occurred_at` zamanı ile daha sonraki `imported_at` zamanı ayrı tutulmalı. Böylece geçmiş, sonradan V2’de olmuş gibi gösterilmez.

### Takvim

- 16–18 Ağustos: `date_due` kilidi ve testleri.
- 18–20 Ağustos: CRM/NVDA preview manifestleri.
- 20–22 Ağustos: SEC/IR kanıt yakalama ve hashleme.
- 22–24 Ağustos: küçük sidecar sözleşmesi ve validator.
- 24–25 Ağustos: kanıt yok/var senaryolarıyla prova.
- 26 Ağustos: tarih yalnız kontrol kuyruğu doğurur; gerçek yayın görülürse kanıt yakalanır ve manuel çalışma başlatılır.

CRM’nin tarihi hâlâ tahmin olabilir; kanıt gelmezse deep-dive çalışmaz. NVDA tarihi birincil kaynaktan yeniden doğrulansa bile yayın ayrıca gözlenmelidir.

Kesinlikle ertelenmesi gerekenler: V2/SQLite defteri, bütün olay göçü, genel research-case motoru, thesis-tracker entegrasyonu, tam P0–P4 arayüzü, yedi pack builder’ın tamamı ve eski deftere yeni lifecycle semantiği eklemek.

## Mevcut preview’ler karşılaştırmaya yeter mi?

**Evet, kontrollü bir geçmiş-beklenti/gerçekleşen karşılaştırmasına yeter; otomatik tez hükmüne yetmez.**

[CRM preview sonucu](</C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/runs/IDEA-20260813-122055736107/work/WI-IDEA-20260813-122055736107-CRM-earnings_preview/2026-08-14/CRM/preview/result.md>) gelir, EPS, sonraki çeyrek/FY konsensüsü ile Agentforce, cRPO/NNAOV, marj ve nakit dönüşümü sorularını dondurmuş. Fakat şirket guidance’ı eksik ve EPS bazının GAAP/non-GAAP niteliği bazı yerlerde belirsiz.

[NVDA preview sonucu](</C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/data/pei-workflow/runs/IDEA-20260813-122055736107/work/WI-IDEA-20260813-122055736107-NVDA-earnings_preview/2026-08-14/NVDA/preview/result.md>) gelir, EPS, brüt marj, sonraki çeyrek beklentisi, Rubin takvimi ve veri merkezi göstergeleri için güçlü bir ön baskı kaydı taşıyor. Burada da EPS temeli ve bazı nitel KPI’lar otomatik karşılaştırmaya uygun değil.

Bu nedenle her beklenti şu dört sınıftan biriyle karşılanmalı:

- `directly_comparable`
- `comparable_with_basis_caveat`
- `qualitative_assessment`
- `not_available_at_preview`

Yalnız mevcut çıkarım payload’ına güvenilmemeli; `result.md` ve orijinal pack birlikte kullanılmalı. Eski `hold`, `wait_for_proof`, Add/Trim/Exit gibi sermaye dili V1 açısından yetkisiz legacy içerik sayılmalı.

## Yalnız bir şey yapılabilseydi

**`date_due` olayının asla `trigger_satisfied` veya workflow-ready üretmemesini, yalnızca kanıt kontrolü vadesi üretmesini sağlardım.**

Çünkü bu tek değişiklik yanlış bir analizin otomatik olarak hazırlanıp deftere “tamamlanmış gerçek” gibi girmesini engeller; kanıtı daha sonra elle yakalama imkânını ise ortadan kaldırmaz.