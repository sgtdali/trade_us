Bu tur da tam yerinde. Özellikle: finansal kuralların haftalık değil **yeni ilgili veri geldiğinde** çalışması; metrik eşlemesinin bedava olmadığı ve "katalogda güvenilir karşılığı olmayan koşul mekanik yapılmaya zorlanmamalı, nitel kalmalı" kuralı; nitel soruların pack'e AÇIKÇA enjekte edilmesi (deep-dive'ın kendiliğinden bakacağını varsaymamak -- 11. turdaki kendini yalanlama sorununun gerçek çözümü bu); thesis ile assessment'ın ayrılması (kalıcı lifecycle nesnesi vs tarihli fotoğraf); makinenin tezi otomatik `broken` yapamaması, yalnız `review_required` üretmesi; ve dedup anahtarı `thesis_id + contract_version + evidence_accession`.

"İnsan tezi takip etmez; sistem takip eder, insan hüküm verir" -- kullanıcının istediği çerçeve tam bu.

Şimdi iki otomasyon katmanını (dispatch + monitoring) birleştirip GERÇEK İŞLETİM DÖNGÜSÜNE bakalım. Dört tur kaldı.

(1) BİR HAFTA GERÇEKTE NEYE BENZİYOR? Somut anlat. Pazartesi sabahı kullanıcı bilgisayarı açtı. Geçen hafta boyunca `fund research-cycle` her gece çalıştı. Ne oldu, kullanıcı ne görüyor?

Üç farklı hafta tarif et: (a) hiçbir şey olmayan sessiz hafta, (b) bir tezin filing'i gelen hafta, (c) fiyat şoku + inceleme vadesi + yeni aday aynı haftaya denk gelen yoğun hafta. Her birinde sistem ne yaptı, kuyrukta ne var, insan kaç dakika harcıyor?

(2) SÜRE BÜTÇESİ HÂLÂ TUTUYOR MU? 65. turda "haftada 10-15 dakika" demiştik ama o, otomasyonsuz ve tez izlemesiz versiyondu. Şimdi sistem otomatik çalışıyor ve önümüze yorumlanmış sonuçlar getiriyor -- bu insan yükünü AZALTIYOR mu yoksa ARTIRIYOR mu? Çünkü iki etki ters yönde: sistem hatırlama yükünü alıyor ama daha çok adjudication üretiyor. Dürüst bir tahmin ver.

Ve şuna dikkat: 57. turda adjudication sürelerini konuşmuştuk (dar güncelleme 5-10 dk, yeni downside case 20-30 dk). Yılda 16-32 otomatik review recipe'si diyorsan, bu yılda kaç saat adjudication demek?

(3) KUYRUK NASIL GÖRÜNÜYOR? 15. turda P0-P4 leksikografik kuyruğu konuşmuştuk ama o tam sistem içindi. Bu ölçekte kuyruk ne -- kaç sınıf, nasıl sıralanıyor? Ve `fund review` komutu ile adjudication kuyruğu aynı şey mi, ayrı mı?

(4) VE BİR ŞEY DAHA: sistem gece çalışırken kullanıcı yokken bir şey ters giderse ne olur? Skill hata verdi, veri gelmedi, codex oturumu düştü. Sabah kullanıcı ne görüyor -- ve sistem kendi kendine ne kadar toparlayabilir? (66. turda "bir kez retry, sonra kullanıcıya göster" demiştin; bu yeterli mi?)

Bu turda yalnız işletim döngüsüne odaklan; nesne modeli ve süre tahminini bir sonraki turda ele alacağız.
