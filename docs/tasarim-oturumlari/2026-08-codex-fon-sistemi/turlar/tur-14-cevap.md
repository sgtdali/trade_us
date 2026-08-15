Alıntıyı geri çekmiyorum; atfımı düzeltiyorum. Cümle `SKILL.md` içinde değil, skill paketinin bağlı iş akışı referansında:

> “Kill weak ideas aggressively. A shorter, sharper list is better than a broad undifferentiated screen.”

Kaynak: [idea-generation/references/workflow.md](</C:/Users/tvural.REPKON/.codex/plugins/cache/openai-curated-remote/public-equity-investing/0.1.31/skills/idea-generation/references/workflow.md:78>).

Dolayısıyla dokümana “SKILL.md diyor” yazmak yanlış olur; “idea-generation 0.1.31 paketinin workflow referansı” denmeli. Bu kaynak seçici ve kısa listeyi destekliyor; fakat “en fazla 3” sayısını vermiyor. Üç bizim kapasite/politika kararımızdır. “Nitelikli aday yoksa sıfır finalist” ise metinden yaptığımız, bence sağlam ama yine de açıkça “tasarım çıkarımı” diye etiketlenmesi gereken sonuçtur.

1. Stage 1’de A/B/C’yi bastırmamalıyız

Bu itirazında haklısın. Önceki “Stage 1’de A/B/C yazılmaz” hükmüm fazla sertti. Doğru ayrım şu:

- Skill’in ürettiği A/B/C/Reject korunur.
- Fakat `candidate.bucket` gibi bağlamsız, kanonik bir alana yazılmaz.
- `scope=slice`, `comparison_set_id=slice_id`, `skill_version=0.1.31` taşıyan bir `stage1_assessment` olarak saklanır.
- `nominated_for_selection`, bu değerlendirme ile kapasite politikasından türetilen bir ilerleme sonucudur; modelin yeni analitik sözlüğü değildir.

Böylece “A”nın iki farklı anlamı karışmaz:

```text
Stage 1 A = bu dilim içinde ileri araştırma önceliği
Stage 2 A = bu selection_batch içinde zincire alınacak öncelik
```

İkisi de mutlak ya da evren-geneli hüküm değildir. Çıplak `bucket` alanı yerine her hükmün karşılaştırma kümesini taşıması gerekir.

`Reject` ile `not_advanced` da birleştirilmemeli. İlki analitik hükümdür; ikincisi kapasite veya seçim politikasının sonucudur. B adayı finalist kotası yüzünden `not_advanced` olabilir ama `Reject` edilmiş değildir.

Mekanik ön eleme yalnızca güvenlik türü, asgari veri, likidite veya mandate uygunluğu gibi deterministik uygunluk koşulları için kullanılabilir. Idea-generation’ın nitel araştırma önceliklendirmesinin yerine geçmemeli.

2. “Advance to deeper work” yorumun doğru

Fazla okumuyorsun. Satır 94 açıkça üç ayrımı destekliyor:

```text
idea-generation A
    → daha fazla araştırmaya değer

actionable pitch
    → tez açılabilecek kadar olgun

thesis_opened
    → sermaye karşılaştırmasına kabul
```

Sonuncusu hâlâ alım yetkisi değildir. Gerçek sermaye kararı portföy oturumunun ve insanın alanında kalır. Dolayısıyla sermaye sorusunu pitch’e kadar ertelemek skill’in kendi sınırıyla uyumlu; hatta A’yı “cazip giriş noktası” gibi okumak skill sözleşmesine açıkça aykırı olurdu.

3. Artefakt dizini: önemsiz değil, fakat artık kimlik değil

Kanonik içerik-adresli depo ile insan-okunabilir görünümü birlikte tutmayı savunuyorum.

Kanonik kimlik şöyle olmalı:

```text
artifact_id = sha256:<digest>
media_type
byte_size
source/result rolü
workflow_attempt_id
```

Burada önemli bir nüans var: hash dosyanın byte kimliğidir, iş bağlamının kimliği değildir. Aynı byte dizisi iki ayrı denemede kullanılırsa blob bir tanedir ama `attempt_id + role + artifact_id` bağlantıları ayrıdır.

İnsan görünümü ise örneğin şöyle kalabilir:

```text
companies/NVDA/2026-08-15/pitch/<attempt_id>/result.md
```

Bu yol yeniden adlandırılabilir veya ticker değişince taşınabilir; olayların referansı bozulmaz. Windows’ta sembolik bağlantılar güvenilir olmayabildiği için okunabilir görünüm bir hardlink ya da yeniden üretilebilir kopya olabilir. Kopyaysa otorite değildir; hash’ten yeniden üretilebilen cache sayılmalıdır. Yanında küçük bir manifest bulunması yeterlidir.

Yani Başlık 2 karar 5’in önemi azalmıyor, türü değişiyor: artık referans bütünlüğü kararı değil, insan ergonomisi ve dışa aktarma kararı.

4. AGY: 24.000 karakterde sessizce kesmiyor

Burada varsayımını düzeltmeliyim. Kod metni kesmiyor; sınırı aşınca açıkça hata veriyor: [pei_workflow.py](</C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/src/adapter/pei_workflow.py:993>). `generate_draft_events()` duruyor ve `workflow_completed` taslağı üretilmiyor.

Üstelik `result.md` bundan önce bağlanmış oluyor. Dolayısıyla gerçek ara durum şudur:

```text
ham sonuç mevcut
result_attached yazılmış
yapılandırılmış çıkarım başarısız
domain geçişi yapılmamış
```

Bu veri kaybı değildir ama açıkça modellenmesi gereken bir `structured_extraction_failed` durumudur.

Buna rağmen iki gerçek sessiz bozulma riski var:

- Metin argv’ye verilmeden önce Unicode karakterleri dönüştürülüyor; tanınmayan semboller `?` olabiliyor. Özellikle eşitsizlik veya finansal gösterimlerde anlam değişebilir.
- Şema sözdizimsel biçimi zorlayabiliyor ama anlamsal tamlığı zorlamıyor. Pitch şeması `null` alanlara ve boş `kill_criteria` listesine izin veriyor. Idea şeması da boş `candidates` listesini kabul ediyor ve dondurulmuş girdi evreniyle tamlık karşılaştırması yapılmıyor.

Hatta kodda eksik bucket’ın B’ye çevrilmesi yönünde sessiz varsayılan var: [pei_workflow.py](</C:/Users/tvural.REPKON/Desktop/ProjelerY/trade_us/src/adapter/pei_workflow.py:1261>). Nominal strict şema altında buna ihtiyaç olmamalı; bulunması bile yanlış güvenlik yönünü gösteriyor.

Kısacası mevcut sistem operasyonel hatalarda fail-closed, anlamsal eksikliklerde fail-open.

5. Flash model izleme sözleşmesinin otoritesi olamaz

Mevcut pitch çıkarım şeması zaten yalnızca `kill_criteria: string[]` üretiyor; metric/unit/period/source/operator/tolerance/revision-policy sözleşmesini üretmiyor. Ayrıca prompt “yalnız açıkça yazanı çıkar, yorum ekleme” diyor. Metinsel bir koşulu ölçülebilir kurala dönüştürmek ise çıkarım değil, yorum ve kural yazımıdır.

Bu nedenle katmanları ayırmalıyız:

1. Kaynağa bağlı çıkarım: metin ve kaynak pasajı.
2. Normalize edilmiş izleme kuralı önerisi.
3. Makine doğrulaması: birim, operatör, dönem, veri kaynağı ve tamlık.
4. İnsan adjudication’ı: “Evet, tezimi gerçekten bu koşul bozacak.”

Flash model birinci adımda yeterli olabilir. Daha güçlü model ikinci adımın hata oranını azaltabilir ama insan kapısının yerine geçemez. Çünkü hata tek çalıştırmayı değil, tezin bütün ömrünü zehirliyor.

6. Başarısız veya yarım çıkarım politikası

Fail-closed sınırı ham analizin saklanması değil, aşağı akış domain geçişidir:

- AGY çalışmazsa veya JSON geçersizse ham `result.md` korunur; workflow zinciri ilerlemez.
- Pitch’in kritik alanları eksikse `thesis_opened` üretilemez.
- İnsan elle tamamlayabilir ama bu `manual_extraction` olarak, kendi aktörü ve kaynak pasajlarıyla görünür olmalıdır; model çıktısını sessizce değiştiremez.
- Idea-generation’da dondurulmuş dilimdeki her ticker hesaba katılmalıdır. Çıkarımda bulunmayan ticker `Reject` sayılamaz; `unaccounted_for` olur ve dilimin kapanmasını engeller ya da insan tarafından açıkça waived edilir.
- Eksik alanlara B, boş metin veya başka “güvenli görünen” varsayılanlar konmamalıdır.

Çıkarım denemesinin idempotency anahtarı da en azından şu bileşim olmalı:

```text
source_artifact_hash
+ extraction_schema_version
+ prompt_version
+ model/config version
```

Son olarak 24.000 sınırı domain sınırı yapılmamalı. Doğru çözüm UTF-8 metni komut satırı argümanı yerine dosya veya stdin üzerinden eksiksiz taşımaktır. Keyfî karakter bölme, özellikle pitch ile kill criteria arasındaki bağları koparabileceği için ancak bölüm-hash’leri ve tamlık uzlaştırması olan ayrı bir protokolle kabul edilebilir.