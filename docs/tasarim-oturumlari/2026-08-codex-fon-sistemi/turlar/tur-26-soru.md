`contract_manifest` fikrini, öncelik sırasını (mandate/ürün sınırı > work-item instructions > orkestratör kontratı > focused skill > plugin varsayılanları), `support-layer-routing-contract`'ın zorunlu olmasını, şemsiyenin `executable: false` runtime policy dependency olmasını, `artifact_mode: internal_analysis` + `forbidden: standalone_html` politikasını ve shared sözleşmelerin üçlü sınıflandırmasını kabul ediyorum. memo-builder'ı koşullu (dönem-sonu sentez, lifecycle yetkisi yok) yapmak da doğru; user-context'in kendi talimatında ordinary workflow'larda çağrılmamasını söylemesi tartışmayı zaten bitiriyor.

Şimdi PACK MİMARİSİNE iniyoruz. Bugünkü durumu çıkardım ve sandığımdan daha zayıf:

us_pei_pack.py'de TASKS diye bir sözlük var ve sekiz anahtarı taşıyor: idea, tearsheet, preview, deepdive, comps, pitch, scenario, initiation. Ama bunların içeriği neredeyse tamamen TALİMAT METNİ -- yani "Use company-tearsheet for {ticker}." gibi. Veri şekillendirmesi tarafında ise yalnız iki dallanma var (`if step == "idea"` ve `if step == "tearsheet"`). Yani pratikte TEK bir büyük pack üretiliyor ve adımlar arasında yalnız talimat değişiyor. NVDA'nın preview pack'i 15.8 KB.

Bu şunu ima ediyor ve doğrulamanı istiyorum: bizim "pack_step" dediğimiz şey aslında bir veri sözleşmesi değil, bir prompt varyantı. Eğer öyleyse, senin bu turlarda tanımladığın üç pack (monitoring_snapshot, thesis_update_pack, dashboard_payload) mevcut mimariye eklenemez -- çünkü onlar gerçekten FARKLI VERİ istiyor, farklı talimat değil.

Sorularım:

(1) TEK BÜYÜK PACK MI, ADIMA ÖZEL PACK MI? Tek pack'in avantajı basitlik ve tutarlılık (her adım aynı gerçeği görür). Dezavantajı: Tur 1'in "ince pack" ihtiyacı, mekanik kontrolün küçük snapshot ihtiyacı ve token maliyeti. Sen hangisini savunursun -- ve eğer adıma özel pack'e geçeceksek, ortak bir çekirdek + adım eklentileri (core + overlay) yapısı mı doğru?

(2) HANGİ PACK'LER GERÇEKTEN GEREKLİ? V1 için çekirdek/koşullu dediğimiz skill'lere bakarak somut liste istiyorum. Benim tahminim: `issuer_baseline` (tearsheet + pitch + deep-dive ortak çekirdeği), `screen_batch` (idea-generation, ince), `valuation` (comps), `event_evidence` (deep-dive, yeni filing merkezli), `monitoring_snapshot` (mekanik, LLM'siz), `thesis_update` (tracker). Altı pack. Eksik/fazla var mı?

(3) PACK'İN TAZELİĞİ VE PROVENANCE'I. 24. turda tearsheet için `structural_as_of` / `financials_known_at,period_end` / `market_as_of` diye üçe ayırmıştık. Bu ayrım tüm pack'lere mi yayılmalı, yoksa yalnız baseline'a mı özgü? Ve pack'in kendisi bir artefakt olarak hash'lenip olaya bağlanmalı mı (bugün `workflow_prepared` pack'i işaret ediyor ama hash yok sanırım)?

(4) PACK KİMİN SÖZLEŞMESİ? Bugün pack'i biz üretiyoruz ve skill'in ne istediğini tahmin ediyoruz. Ama skill'lerin çoğunun kendi girdi beklentisi var (portfolio-risk-management'ta gördük: 11 maddelik girdi listesi). İki yol: (a) her skill için onun beklentisine göre bir adapter yazmak, (b) tek kanonik pack üretip skill'in eksik gördüğünü "missing input" olarak bildirmesine izin vermek. Sen 12. turda kanonik snapshot + skill adapter ayrımını savunmuştun; burada da aynı mı, yoksa pack tarafında farklı mı düşünürsün?

(5) Ve pratik bir soru: 15.8 KB'lik bir pack, Tur 1'de 25 ticker için çalıştırılırsa 400 KB olur. Bu tek bir oturuma sığar ama kalite düşer (dilim-göreceli yargı sorunu). Tur 1 için "ince pack"in içinde ne kalmalı -- ticker başına hangi alanlar gerçekten eleme kararını değiştirir? Bu, dokümanda "ölçülerek ayarlanacak" diye bırakılmış bir kalibrasyon parametresi ama sen skill'in ne istediğini biliyorsun, ilk tahmini verebilirsin.
