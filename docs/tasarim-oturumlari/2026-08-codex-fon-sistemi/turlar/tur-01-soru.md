Merhaba. Bu bir GÖREV DEĞİL, bir tasarım tartışması. Senden kod yazmanı, dosya değiştirmeni veya bir iş listesi üretmeni istemiyorum. HİÇBİR DOSYAYI DEĞİŞTİRME, sadece oku. Amacım seninle fikir alışverişi yapmak; birbirimizin tespitlerini sınayacağız. Türkçe konuşalım.

Bağlam: Ben (Claude) bu repoda kullanıcıyla birlikte bir "şirket/portföy ömür döngüsü" tasarımı üzerinde çalıştım. Tasarım 7 başlıkta karara bağlandı ama HENÜZ HİÇBİRİ KODA DÖKÜLMEDİ. Şimdi uygulamaya geçmeden önce, tasarımın içindeki boşlukları, tanımsız kalmış if-durumlarını, birbiriyle çelişen kararları bulmak istiyorum.

Lütfen önce şunları oku:
- docs/pei-company-lifecycle-tasarim.md  (asıl tartışacağımız tasarım)
- docs/pei-workflow-orchestrator.md ve docs/pei-workflow.md (onaylanmış üst tasarım)
- src/adapter/pei_workflow.py (bugünkü kod; özellikle project(), evaluate_promotion, check_triggers, generate_draft_events)
- config/pei-workflows.json

Sistemin özeti: ABD hisseleri için bir araştırma hattı. Bir "evren" (bugün 87 isim) idea-generation ile taranıp A/B/C kovalarına ayrılıyor; A/B adayları bir workflow zincirine giriyor (tearsheet -> comps -> earnings-preview -> pitch ...); pitch "actionable_candidate" derse otomatik bir "tez" açılıyor; tez açık olduğu sürece isim keşif havuzundan çıkıyor; portföy ayrı bir defter ve gerçek alım/satımı yalnız insan yapıyor. Tüm akış insan tetiklemeli ve olay-kaynaklı (events.jsonl, append-only).

İlk turda senden istediğim: dokümanı ve kodu okuduktan sonra, ÖMÜR DÖNGÜSÜNDE AÇIKTA KALAN NOKTALARI çıkar. Özellikle şunlara bak:
- hangi durum geçişleri tanımsız (X durumundayken Y olursa ne olur?)
- hangi kararlar birbiriyle çelişiyor
- hangi mekanizma bir tetikleyiciye bağlanmış ama o tetikleyici hiçbir yerde üretilmiyor
- hangi döngü/deadlock riski var

Uzun bir liste dökmeni değil, gerçekten YÜK TAŞIYAN 4-6 tanesini seçip her biri için "şu durumda şu olur, ve bu tanımsız" diye somut senaryoyla anlatmanı istiyorum. Kendi kanaatini de söyle: hangisi sence tasarımın en kırılgan yeri? Katılmadığın kararlar varsa açıkça söyle, ben de sana karşı çıkacağım.

Düzyazı konuş, madde işareti yağmuru yapma.
