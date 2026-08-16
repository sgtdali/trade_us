Portföy karşılaştırmasında (iii)’ü savunuyorum; fakat “ilk aylık toplantıya kadar zorunlu bekle” şeklinde değil, “tez açılmadan sermaye karşılaştırması yapılmaz” ilkesi olarak.

Aday A olmuş, tearsheet ve comps tamamlanmış olsa bile pitch öncesinde henüz karar kalitesinde bir security thesis değildir. Dolayısıyla mevcut pozisyonlarla kıyaslanmaması gerçek bir kayıp değil; bilinçli bir epistemik eşiktir. Doğru karşılaştırma “yarı-pişmiş A adayı mı, incumbent mı?” değil, “yeni actionable thesis mi, incumbent mı?” sorusudur.

(i)’yi savunmuyorum; çünkü portföy oturumu bu kez farklı olgunluk seviyelerindeki nesneleri karşılaştırır. Açık tezler falsifier, risk/reward ve action threshold taşırken pitch öncesi aday bunları henüz taşımıyor. Sonuç ya adaya sahte kesinlik vermek ya da portföy oturumunu ikinci bir pitch mekanizmasına çevirmek olur.

(ii)’yi de savunmuyorum. Pitch’e portföyü sokarsak güçlü bir security thesis, sırf mevcut sektör ağırlığı yüksek olduğu için `non-actionable` çıkabilir. Böylece “bu hisse yatırım yapılabilir mi?” ile “benim portföyümde şu anda yer var mı?” yeniden birbirine karışır. Kabul ettiğimiz company/security/action ayrımı tam burada bozulur. Pitch, portföy oturumunun ihtiyaç duyduğu girdileri üretmeli; portföy hükmünü vermemeli.

Benim net sınırım şu:

> `thesis_opened`, sermaye karşılaştırmasına kabul kapısıdır.

Tez açılınca isim otomatik olarak portföy oturumunun gündemine girer. Aylık toplantı normal toplu değerlendirme zamanıdır; fakat yakın katalizör veya yüksek öncelik varsa insan aynı portföy oturumunu daha erken tetikleyebilir. Bu hâlâ gerçek işlemi otomatikleştirmez. Dolayısıyla Başlık 3’ün bedeli Başlık 4 tarafından ödeniyor, ama candidate aşamasında değil, tez açıldığı anda. Tasarımda eksik olan şey bunun açıkça “gecikmeli ve decision-grade karşılaştırma” olarak adlandırılması.

## `superseded` geçişi

Thesis-tracker’ın yeni tez açamaması gerektiğine katılıyorum. Haftalık deviation yolu mevcut tezin eksenlerini güncelleyebilir, `changed`, `broken` veya `re_underwrite` diyebilir; fakat tez açma yetkisi kazanamaz. Aksi hâlde “yalnız actionable pitch tez açar” kapısı gerçekten ikiye bölünür.

Buna rağmen `superseded` değerini atmazdım. Onun normal keşif hattından değil, açık tezin yeniden-underwrite edilmesinden doğması gerekir.

Somut akış şöyle olur: haftalık inceleme mevcut tezin temel yatırım sorusunun değiştiğini saptar ve `re_underwrite` önerir. Bu, yeni tez açmaz; aynı ticker için keşif havuzunun dışında, insan tetiklemeli yeni bir pitch ister. Pitch mevcut tezi ve yeni kanıtı görür. Sonuç yalnız bir güncelleme ise eski thesis_id yaşamaya devam eder. Fakat variant perception, yön, ufuk veya kill criteria gerçekten yeni bir underwriting oluşturuyorsa pitch açıkça “replace existing thesis” hükmü verir.

Bu durumda tek atomik event batch’i üç şeyi yapar:

- Yeni `thesis_opened` olayını üretir.
- Eski tezi `superseded_by=<new_thesis_id>` ile kapatır.
- Açık pozisyon varsa mevcut exposure’ın hangi tez altında izleneceğini açıkça yeniden bağlar.

Böylece tez açma yetkisi yine yalnız pitch’te kalır. Thesis-tracker yalnız yeniden-pitch talebinin gerekçesini üretir.

`superseded`, “tez zamanla değişti” anlamına gelmemeli; o durumda aynı tezde `changed` kullanılır. Yalnız eski underwriting’in yerine yeni kimlikli bir underwriting geçtiğinde kullanılmalı. Ship of Theseus sorununu önleyen değer budur: yıllarca değiştirilen bir tezin başlangıçtaki tezmiş gibi görünmesini engeller.

## Oturumun ömrü

Burada “araştırma zinciri” ile “Codex session”ı ayırmak gerekiyor. Zincir kalıcı ve olay-kaynaklıdır; session yalnız yürütme optimizasyonudur.

Bir per-ticker session ilk gerçek ticker workflow’uyla başlar ve normalde pitch’in terminal sonucunda ölür: tez açılması, `watchlist`, `pass_for_now` veya `red_team_only`. Tez açıldıktan sonraki haftalık incelemeler eski pitch session’ını resume etmemeli; her deviation ayrı bir thesis-review episode’u ve yeni session olmalı. Aksi hâlde eski pitch’in ikna çerçevesi yıllarca tez incelemelerine taşınır.

Tur değişimi tek başına session’ı öldürmemeli. Yeni screen aynı temel setup’ın yeni bir gözlemiyse session devam edebilir ve event delta enjekte edilir. Fakat setup maddi olarak değiştiyse mantıksal zincir devam etse bile fiziksel session kapatılmalı; yeni session tüm önceki artefaktlar ve yeni setup ile başlatılmalı. Bu ayrım önemli:

> Zinciri sıfırlamadan konuşma bağlamını sıfırlayabiliriz.

Böylece yapılmış tearsheet/comps çöpe gitmez, fakat model eski turun çerçevesine gizlice demirlenmez.

Anchoring’i modelin “kafasında” güvenilir biçimde tespit edemeyiz. Bu yüzden observable bir sözleşmeye çevirmek gerekir. Her adımın context bundle’ı mevcut `setup_id/version`, geçerli bucket, önceki setup’ın durumu ve son adımdan beri gelen olayları taşır. Çıktı da hangi `setup_id` ve `context_snapshot_id` üzerinden hüküm verdiğini belirtir. Eski setup’ı geçerli sanan sonuç doğrulamada reddedilebilir. Maddi setup değişiminde fresh session kullanmak ise asıl korumadır.

## Denetim izi

Olay enjeksiyonu doğru yapılırsa repo ile model bağlamı arasında fark yaratmak zorunda değil. Enjekte edilen bağlam geçici prompt metni olarak oluşturulup kaydedilmezse ilke gerçekten çiğnenir. Çözüm, her çalıştırmadan önce tam bir immutable `context bundle` üretmek ve bunu `workflow_prepared` olayına hash’li kaynak artefaktı olarak bağlamaktır.

Bu bundle en az şunları içermelidir: kullanılan pack, önceki result artefaktları, enjekte edilen event delta, geçerli setup/bucket snapshot’ı, talimatlar ve hangi session’ın resume edildiği. Böylece “model bu adımda ne gördü?” sorusu session servisinden bağımsız cevaplanır.

Yine de dokümandaki “session’a hiç ihtiyaç yok” cümlesini daraltmak gerekir. Resume edilen modelin gizli konuşma belleğini byte-for-byte yeniden üretmek mümkün değildir. Savunulabilir ilke şudur:

> Repo, onaylı kararın kanıtını, modelin açık girdilerini ve olay nedenselliğini anlamak için yeterlidir; aynı model iç durumunu yeniden üretme garantisi vermez.

Daha güçlü test de şu olur: her adımın context bundle’ı fresh session’da çalıştırılmaya yeterli olmalıdır. Resume yalnız kalite/maliyet optimizasyonudur; gerekli bir bilgi kaynağı olamaz. Eğer bir sonuç yalnız eski session’ın gizli hafızası sayesinde anlaşılabiliyorsa, denetim ilkesi zaten ihlal edilmiştir.