Performans katmanını olduğu gibi alıyorum. Üç ayrı gerçeğin ayrılması (para ne yaptı / tezde öngörülen dünya gerçekleşti mi / karar o anda kaliteli miydi), süreç×sonuç matrisi, counterfactual'ın yalnız karar anında dondurulmuşsa izlenmesi, "kaçırdığın kazanç" yerine "kural kalitesi" dili, ve küçük örneklemde önceliğin bütünlük ve süreç uyumunda olması -- hepsi doğru. "P&L hakemdir ama öğretmen değildir" cümlesi de kalıcı.

Benchmark / hurdle / context series üçlemesi de dokümandaki gerilimi çözüyor: mandate benchmark'ı yasaklıyor ama bağlam serisini değil.

Şimdi RİSKE geliyoruz ve burada bence tasarımın fark etmediği yapısal bir kısıt var:

Bu fon long-only, açığa satış yok, opsiyon yok, kaldıraç yok. Yani elimizdeki risk araçları neredeyse tükenmiş durumda. Hedge edemiyoruz, korumalı pozisyon kuramıyoruz. Geriye YALNIZ üç kaldıraç kalıyor: pozisyon büyüklüğü, nakit oranı, ve o şeye hiç sahip olmamak. Bu doğru mu? Eğer doğruysa, "risk yönetimi" bu sistemde aslında "boyutlandırma + nakit + çıkış disiplini"nden ibaret demektir ve ayrı bir risk katmanı kurmak fazlalık olur. Katılıyor musun, yoksa gözden kaçırdığım bir araç var mı?

Bunun üstüne dört soru:

(1) FAKTÖR MODELİ OLMADAN KORELASYON. Sektör tavanı koyduk ama gerçek korelasyon sektör sınırlarını takip etmiyor. Somut örnek: kullanıcının evreninde 87 ismin 31'i teknoloji, ama asıl ortak sürücü "AI capex döngüsü" olabilir ve bu yarı iletken, yazılım, enerji ve sanayi isimlerini aynı anda vurur. Sektör limiti bunu göremez. Faktör modelimiz yok ve kurmak (kovaryans tahmini, faktör yükleri) bu ölçekte gerçekçi değil. O hâlde ortak sürücü riskini nasıl yakalayacağız -- tezlerin kendi `intended_alpha` alanından türetilen bir "driver" etiketi yeterli mi, yoksa bu da elle uydurulmuş bir taksonomi mi olur?

(2) DRAWDOWN'A TEPKİ. Fon %20 düştüğünde ne olmalı? Üç seçenek: hiçbir şey (tezler ayaktaysa tut, drawdown bir sinyal değil), mekanik de-risking (nakde geç), ya da zorunlu inceleme (pozisyon değişmez ama her tez yeniden adjudicate edilir). Klasik hata dipte de-riske etmek; ama "hiçbir şey yapma" da bir kural değil, kural yokluğu. Ben üçüncüsüne meyilliyim ama drawdown eşiğinin ne olacağını ve bunun capital policy'de mi yoksa monitoring'de mi durması gerektiğini bilmiyorum. Sen nasıl kurarsın?

(3) TEK İSİM GAP RİSKİ. Long-only bir kitapta en büyük tek olay riski, bir ismin bir gecede %30-40 düşmesidir (kötü bilanço, muhasebe skandalı, FDA reddi, regülasyon). Kayıp bütçesi bunu "downside senaryosu" ile modellemeye çalışıyor ama gap riski senaryo değil, kuyruk. Bunu ayrıca sınırlamak gerekir mi (ör. "tek isim NAV'ın %X'ini geçemez, downside senaryosu ne derse desin"), yoksa `max_position_weight` zaten bu işi mi görüyor?

(4) LİKİDİTE VE ÖLÇEK. Mandate likidite tabanını "uygulanmıyor" diyor çünkü retail büyüklüğünde pozisyon günlük hacmin binde birinden az. Bu bugün doğru. Ama fon büyürse (kullanıcı sermaye eklerse) bu varsayım bir noktada bozulur ve kimse fark etmez -- çünkü kural "uygulanmıyor" diye yazılmış. Sistem kendi varsayımının geçersizleştiğini nasıl anlar? Bu tür "bugün geçerli ama sonsuza kadar değil" varsayımları için genel bir mekanizma gerekiyor gibi -- policy'de `assumption_valid_while` gibi bir alan mı olmalı?

(5) Ve son olarak: bu sistemde bir "STOP LOSS" kavramı olmalı mı? Temel analiz odaklı, 3-18 ay ufuklu bir kitapta fiyat bazlı stop mantıksız görünüyor (tez fiyata değil işe dayanıyor). Ama kayıp bütçesi de bir tür stop -- yalnız fiyat yerine tez bozulmasına bağlı. İkisi arasındaki farkı net söyle, ve fiyat bazlı bir mekanizmanın hiç yeri var mı?
