Bu tur da net. Özellikle: request'in kalıcı bir KARAR İHTİYACI olması (kuyruk öğesi değil, kuyruk ondan türetilen projection); `requested_capability`'nin skill adı değil domain çıktısı istemesi (`downside_case.v1`) ve fonun asla "scenario skill'ini çalıştır" dememesi; `work_equivalence_key` ile iki seviyeli dedup; R sınıfının birinci leksikografik anahtar olup sermaye büyüklüğünün yalnız sınıf İÇİNDE sıralaması; **R0'ın çoğunlukla araştırma işi olmaması** (sermaye gerçeği bilinmiyorsa çözüm skill değil reconciliation -- bunu ben karıştırmıştım); ve iptalin "skill'i değil karar ihtiyacını" iptal etmesi + `quarantined_late_result`.

"İnsan işi başlatır ve hükmü kabul eder; her teknik adımı elle sürmez" -- V0 sınırı olarak alındı.

Şimdi ORKESTRASYON MEKANİĞİNE iniyoruz: bir skill gerçekte nasıl çağrılıyor.

(1) EN KRİTİK SORU: HANGİ SKILL FON DURUMUNU GÖRÜYOR? Burada gerçek bir gerilim var ve daha önce iki farklı yöne karar vermiştik:

- 3. turda pitch'in portföyü GÖRMEMESİ gerektiğine karar verdik: "güçlü bir tez sırf sektör ağırlığı yüksek diye non-actionable çıkabilir; company/security/action ayrımı tam orada bozulur."
- Aynı şekilde idea-generation'a portföy pozisyonları verilmemeli demiştik (saf keşif).
- Ama şimdi fon bir soru soruyor ve soru bazen doğrudan pozisyonla ilgili: "82 bp sermaye riski olan bu pozisyonun downside'ı hâlâ geçerli mi?"

O hâlde her skill için ayrı bir görünürlük kararı gerekiyor gibi. Somut sor: hangi skill fon state'ini görür, hangisi görmez, ve GÖREN için tam olarak ne görür (pozisyon var/yok mu, ağırlık mı, sermaye riski mi, yoksa hiçbir sayı olmadan yalnız "bu fonlanmış bir pozisyon" mu)? Bir görünürlük matrisi istiyorum.

Ve bir alt soru: bir skill'in fonlanmış olduğunu bilmesi yargısını bozar mı (sahiplik yanlılığı -- elimde olduğu için savunma eğilimi), yoksa gerekli bağlam mı (bu bir gerçek pozisyon, ciddiyetle bak)?

(2) PACK NASIL KURULUYOR? 26. turda yedi pack sözleşmesi tanımlamıştık ama hepsi araştırma-merkezliydi. Şimdi fon tarafından tetiklenen bir iş için pack'e fon bağlamı da girmeli mi -- yoksa görünürlük matrisine göre bazılarına hiç girmemeli mi? Ve `capital_input_manifest`'in mevcut hâli pack'e girer mi (yani "şu an elimizdeki downside şu, güncelle" mi diyoruz, yoksa sıfırdan mı sordurmalıyız)? İkisinin farkı büyük: birincisi anchoring riski taşıyor, ikincisi tekrar iş yaptırıyor.

(3) `contract_manifest` VE PROVENANCE. 25. turda her iş kaleminin plugin sürümü, skill yolu + sha256, zorunlu shared sözleşmeler, override'lar ve artefakt politikasını taşıyan bir manifest taşıması gerektiğine karar vermiştik. Fon tarafından tetiklenen işlerde buna ne ekleniyor -- `research_work_request_id`, `capital_at_risk`, görünürlük kararı? Ve sonuç artefaktı fona döndüğünde bu provenance nereye yazılıyor (capital input bileşeninin içine mi, yoksa ayrı mı)?

(4) OTURUM SÜREKLİLİĞİ. `codex exec resume` kararı hâlâ geçerli (bundle zorunlu, resume bonus). Fon tarafından tetiklenen bir iş için oturum ne olmalı: aynı security'nin önceki araştırma oturumu devam mı ediyor, yoksa her sermaye sorusu taze oturum mu? 25. turda "pitch'in ikna çerçevesi yıllarca tez incelemelerine taşınmasın" demiştik. Fon sorusu için de aynısı geçerli mi?

(5) Ve maliyet: fon tetiklemeli bir iş, araştırma tetiklemeli bir işten daha mı pahalı olmalı? Yani 82 bp sermaye riski olan bir soru, sıradan bir keşif işinden daha güçlü modeli hak eder mi -- `capital_at_risk` model seçimine girmeli mi?
