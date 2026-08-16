Dürüst cevap: mevcut yürütme modeliyle bu, 500 isimlik bir sistem değil. `sp500.json` hedef niyetini gösteriyor; bugünkü orkestrasyonun o hedefi taşıdığını göstermiyor.

Yedi başlığın kavramsal tarafının büyük bölümü 500’de ayakta kalır: candidate/tez/portföy ayrımı, ticker-sürekli kimlik, açık tezlerin keşiften çıkarılması, iki aşamalı eleme fikri, `thesis_opened` sermaye kapısı ve beş eksenli tez modeli ölçekten bağımsız olarak doğru. Fakat mevcut operasyon modeli—her adımda üç manuel komut, tek dosyayı baştan yazma, her okumada tam replay ve bütün finalistleri tek Tur 2 oturumuna verme—500’de ayakta kalmaz.

Kabaca söylersem domain tasarımının yüzde 70–80’i kalır; yürütme ve persistence tasarımının ancak yüzde 20–30’u.

## 1. Tur 1’de ticker başına olay gerekli mi?

Hayır. Hatta Tur 1’in gerçek semantiğine daha uygun olan, dilim başına tek toplu olaydır.

Tur 1’de model 25 bağımsız şirket hakkında 25 bağımsız karar vermiyor; 25 şirketi birbirine göre değerlendirip tek bir dilim sıralaması üretiyor. Dolayısıyla doğal domain olayı şudur:

```text
slice_screen_completed
  round_id
  slice_id
  universe_snapshot_id
  finalistler
  finalist_olmayanlar
  ticker_bazlı_gerekçeler
  source_result_hash
  model/config/context kimliği
```

Bu, denetim izini zayıflatmaz. Tam tersine, “bu ticker neden ilerlemedi?” sorusunun cevabını onu doğuran karşılaştırma kümesiyle birlikte korur. Her ticker için ayrı olay yazmak karşılaştırmalı hükmü yapay biçimde parçalar.

Ham model sonucu immutable artefakt olarak kalır; toplu olay onun hash’ini ve yapılandırılmış ticker sonuçlarını taşır. Her ticker sonucu ayrıca deterministik bir alt kimlik alabilir: `slice_event_id:ticker`. Daha sonra tek bir ticker yorumu düzeltilirse bütün dilim yeniden yazılmaz; parent olaya referans veren `slice_item_corrected` eklenir.

Tur 2 de aynı mantıkla tek `round_screen_completed` olayı olabilir. A/B/C sonuçları bireysel candidate projection’larına bu toplu olaydan dağıtılır. Ayrı `candidate_screened` olayları tercih edilirse bile bunlar 40 ayrı commit değil, tek atomik batch olarak yazılmalıdır.

Asıl maliyet event satırı sayısından çok commit sayısıdır. 500 ticker’ı 500 ayrı read-modify-write ile yazmak felaket; 20 dilimi 20 atomik batch ile yazmak makuldür.

## 2. Tek defter ilke mi?

Tek fiziksel dosya ilke değil. İlke, tek mantıksal ve otoritatif olay akışıdır.

Dilimlerin kendi “defterleri” bağımsız otorite olursa çok-defter problemi geri gelir: hangi dilimin hangi sürümü geçerli, üst özet ile alt kayıt çelişirse hangisi kazanır, cross-ledger geçiş atomik mi gibi yeni sorunlar doğar. Bunu savunmam.

Fakat dilimlerin immutable sonuç paketleri olabilir. Bunlar ledger değil, commit edilmemiş transaction bundle veya kaynak artefakttır. Üst olay akışı, onaylandığında bu paketin hash’ini ve sonucunu kaydeder. O andan sonra otorite üst akıştır; dilim paketi kanıttır.

Tek mantıksal ledger fiziksel olarak da tek büyüyen dosyada tutulmak zorunda değildir. Sıralı, immutable segmentlere ayrılabilir:

```text
ledger/
  segment-000001.jsonl
  segment-000002.jsonl
  ...
```

Bütün segmentler monoton sequence numarasıyla tek akışı oluşturur. Tek commit kapısı yeni batch’e sequence aralığı verir ve aynı anda yalnız bir writer çalışır. Böylece “analiz paralel, commit seri” ilkesi korunur.

Projection tarafında da her `status` çağrısında Genesis’ten replay gerekmez. Belirli bir sequence ve ledger hash’ine bağlı, silinebilir bir snapshot tutulabilir. Okuma snapshot’tan başlar ve yalnız sonraki olayları replay eder. Snapshot otorite değildir; silinip tüm segmentlerden yeniden üretilebilir. Şema doğrulaması da normal okumada bütün tarihçeye tekrar uygulanmaz: yeni batch commit anında doğrulanır, tam ledger doğrulaması ayrı bir `verify` operasyonudur.

On binlerce olay event sourcing için büyük bir hacim değildir. Bugünkü algoritmayla büyüktür, çünkü her yazım O(N), toplam maliyet O(N²). Doğru append/batch/snapshot modeliyle yüz binlerce olay bile bu sistemin asıl darboğazı olmaz.

## 3. İnsan komut sayısı tasarım kısıtı mı?

Kesinlikle evet. “Orkestrasyon sonra otomatikleşir” diyerek tasarım dışına atılamaz; çünkü tek operatör ve insan tetiklemeli çalışma açık sistem varsayımlarıdır.

Burada iki kavramı ayırmak gerekiyor:

> İnsan tetiklemeli olmak, insan tarafından adım adım sürülmek demek değildir.

Bugünkü sistem hem human-triggered hem human-stepped. Ölçeklenmeyen ikinci kısım.

İnsan bir turu, dilimi veya araştırma zincirini yetkilendirdiğinde `prepare → run_codex → attach → extract → validate → commit` mekanik zincirini orkestratör yürütmelidir. İnsan şu kapılarda kalır: turu başlatmak ve bütçesini onaylamak, partial tur kapatmak, desteklenmeyen/indeterminate istisnaları çözmek, portföy hükmünü değerlendirmek, gerçek işlemi yapmak veya kaydetmek ve portföyü uzlaştırmak.

Bir dilim için üç komut değil, bir insan kararı olmalıdır. Tur 1’de 20 dilim varsa ideal yüzey “20 ayrı komut” da değildir: insan universe snapshot’ı ve maliyet sınırı belli bir turu bir kez başlatır; orkestratör dilimleri paralel analiz eder, commit’leri seri yapar. İstenirse sonuçlar dilim başına topluca onaylanır.

Per-ticker zincirlerde insanın her workflow’u ayrı ayrı başlatması korunursa 500 yine yorucu olur. Burada ya bir zincirin belirli bir kapıya kadar otomatik ilerlemesine izin verilmeli ya da aynı anda aktif araştırma zinciri sayısı sert biçimde sınırlandırılmalıdır. Aksi hâlde “10 aday × 5 workflow” yalnız komut problemi olmaktan çıkar; insanın 50 ayrı araştırma çıktısını anlamlandırma problemi olur.

## 500’de başka ne kırılır?

“Bütün dilimler bitsin, bütün finalistler tek Tur 2 oturumuna girsin” hükmü de aynen korunamayabilir. 20 dilimden üçer finalist 60 isim eder. Tam pack ile 60 ismi tek ağır oturumda karşılaştırmak, tasarımın kaçmaya çalıştığı bağlam kalitesi sorununu bir üst katmanda yeniden üretir.

Dolayısıyla iki aşamalı eleme fikri kalır, fakat düz iki aşama muhtemelen hiyerarşik ve üst sınırları olan bir eleme ağacına dönüşür: dilim finalistleri önce sektör/süper-sektör seviyesinde daralır, gerçek global final yalnız bounded bir kümeyi görür. Burada feda edilen şey “bütün finalistlerin tek model çağrısında eksiksiz yan yana görülmesi” iddiasıdır. Kazanılan şey bağlam kalitesi ve öngörülebilir süre olur.

Ağır workflow’lar da sınırsız çalıştırılamaz. `sol/xhigh` pitch, initiating coverage ve portfolio-risk-management yalnız gerçekten karar kapısına ulaşmış az sayıdaki isimde kullanılmalı. B’lerin tamamına tam zincir, her A’ya otomatik 4–5 adım ve her turda yeniden derin analiz uygulanırsa maliyet ve süre patlar. 500 ölçeğinde feda edilmesi gereken şey kapsamlılık değil, her adayın aynı derinlik ve hızla ilerlemesi beklentisidir. Sistem bir öncelik kuyruğu ve aktif-zincir kapasitesi taşımalıdır.

Haftalık tez kontrolü ise evren büyüklüğüyle değil açık tez sayısıyla ölçeklenir. Portföy ve açık tez sayısı makul kalıyorsa 500 isim bu tarafı doğrudan 5,7 kat büyütmez. En büyük yük discovery ve pre-thesis araştırmadadır.

Son hükmüm şu:

Bugünkü biçimiyle 500 isim iddiası gerçekçi değil; sistem 87 isimlik, tek operatörlü bir prototip. Fakat yedi başlıklı lifecycle’ı atmak gerekmiyor. 500’e çıkmak için feda edilmesi gerekenler şunlar: her mekanik adımda insan komutu, ticker başına Tur 1 commit’i, tek fiziksel defteri her seferinde baştan yazma, bütün finalistleri tek oturumda karşılaştırma ve her adayın sınırsız derinleşmesi.

Feda edilmemesi gerekenler ise tek mantıksal gerçeklik kaynağı, append-only geçmiş, insanın gerçek sermaye üzerindeki tek yetkisi ve company/security/portfolio ayrımıdır. Bunlar ölçeğin sorunu değil; ölçeği güvenli tutan kısımlar.