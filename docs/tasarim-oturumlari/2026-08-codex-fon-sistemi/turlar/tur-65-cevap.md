## 1. Üç turun özeti

Gerçek ölçek netleşti: 5–10 pozisyon, yılda yaklaşık 12 işlem, manuel giriş ve başlangıçta gölge kullanım. Bu nedenle broker importer, ayrıntılı reconciliation, execution lifecycle ve genel fon platformu çöktü. Buna karşılık yazılım fikri güçlendi: kullanıcıya hesap tablosu yerine, policy hesaplayan ve karar anını immutable biçimde donduran küçük bir uygulama değer katıyor. Aktif ürün artık dört nesneden oluşan manuel portföy karar günlüğüdür: `assessment_record`, `decision_record`, `account_event`, `capital_policy`. Araştırma otomasyonu yerine kullanıcı Codex sonucunu okuyup kabul ettiği hükmü `fund assess` ile girer; iki aşamalı adjudication mimari değil kullanıcı akışı olarak korunur.

## 2. Dokümanın yeni sınıflandırması

Belgenin başına şu aktif ürün tanımı konmalı:

> **Aktif ürün: 5–10 pozisyonlu, düşük işlem sıklıklı bir gölge kitap için manuel girdili portföy karar günlüğü. Hedef platform mimarisi yalnız ihtiyaç tetiklenirse başvurulacak tasarım referansıdır.**

Belgenin adı da “Portföy işletim sistemi” yerine en azından **“Portföy karar günlüğü ve hedef işletim sistemi referansı”** olarak daraltılmalı.

| Bölüm | Yeni etiket | Hüküm |
|---|---|---|
| Sistem tanımı ve insanın sermaye yetkisi | `AKTİF` | Sistem kararları sınar ve kaydeder; emir iletmez. Ürün kapsamı “işletim sistemi”nden “karar günlüğü”ne daralır. |
| Capital policy v0 | `AKTİF` | Yalnız kullanılan minimal alanlar aktif; geniş on bir bölümlü şema referanstır. |
| Boyutlandırma, kayıp bütçesi, no-trade bandı | `AKTİF` | `fund trade-preview` hesaplarının çekirdeğidir. |
| Risk motoru | `AKTİF` + `REFERANS` | Pozisyon ağırlığı, kayıp bütçesi ve hard-limit kontrolleri aktif; driver/korelasyon/scenario katmanı referans. |
| Portfolio proposal | `GEÇERSİZ` / `REFERANS` | Çok seçenekli tam proposal nesnesi yapılmayacak; tek işlem önizlemesi ve kullanıcının kararı yeterli. |
| İcra köprüsü | `AKTİF` + `GEÇERSİZ` | Manuel `trade-add` aktif; order observation, partial-fill lifecycle, VWAP ve broker importer geçersiz. |
| Broker importer ve reconciliation motoru | `GEÇERSİZ` | Yerine ara sıra yapılan manuel kontrol gelir. |
| Pozisyon/nakit/NAV projection’ı | `AKTİF` | Manuel account-event’lerden türetilir. |
| Performans | `TETİKLEYİCİYLE AKTİFLEŞİR` | Basit NAV/P&L görünümü aktif olabilir; TWR/MWR ayrıntısı gerçek ihtiyaçla gelir. |
| Attribution ve counterfactual | `REFERANS` | Karar verisi şimdi saklanır; analiz motoru yeterli örnek oluşunca düşünülür. |
| Risk-driver registry ve korelasyon | `REFERANS` | Somut yoğunlaşma problemi gözlenmeden yapılmaz. |
| A0–A4 yetki merdiveni | `REFERANS` | V0 yalnız `shadow` durumunu bilir; diğer yetkiler gerçek otomasyon gelirse değerlendirilir. |
| Policy validation paketi | `TETİKLEYİCİYLE AKTİFLEŞİR` | Formüllerin birkaç property/golden testi aktif; tam replay ve yetki paketi referans. |
| Skill envanteri ve 10+1 katalog | `REFERANS` | Skill’ler şimdilik kullanıcı tarafından doğrudan çalıştırılır. |
| Lead/support, routing ve episode modeli | `REFERANS` | Otomatik araştırma hacmi manuel yöntemi aşarsa etkinleşebilir. |
| Fon–skill entegrasyon sınırı | `AKTİF` + `REFERANS` | “Skill sermaye otoritesi değildir” aktif; request/router/manifests altyapısı referans. |
| `capital_input_manifest` | `GEÇERSİZ` | `decision_record`, assessment/policy/fiyat referanslarıyla küçük manifest işlevini görür. |
| İki aşamalı adjudication | `AKTİF` | `fund assess` ve `fund trade-preview` ayrımı olarak uygulanır; ayrı platform kurulmaz. |
| Eski 7+3+1 şema kesimi | `GEÇERSİZ` | Yerine dört küçük şema ve tek DDL gelir. |
| Event envelope ve genel event-store tasarımı | `REFERANS` | V0’da dar `account_event` kimliği ve SQLite transaction’ı yeterlidir. |
| 11/13 adımlı fon-önce inşa sırası | `GEÇERSİZ` | Yerine aşağıdaki küçük ürün sırası geçer. |
| 20 fon + 10 araştırma değişmezi | `AKTİF` / `REFERANS` diye ayrılmalı | Yalnız küçük üründe gerçek hata önleyenler aktif kalır. |
| 65 turluk karar günlüğü | `REFERANS` | Gerekçeleri korur; uygulama talimatı değildir. |

Dürüst oran: belgenin yalnız yaklaşık **%10–15’i aktif ürün spesifikasyonu** olarak kalıyor. Yaklaşık **%15–20’si tetikleyiciyle etkinleşebilecek seçenek**, geri kalan **%65–75’i referans, tarihsel kayıt veya geçersiz tasarımdır**. Bu bölüm silinmek zorunda değil; fakat backlog diye okunması kesinlikle engellenmelidir.

## 3. Yeni tek sayfa

# Aktif ürün: Manuel Portföy Karar Günlüğü

### Ölçek

- Tek kullanıcı
- 5–10 pozisyon
- Ayda yaklaşık bir pozisyon değişikliği
- Başlangıçta gölge kitap
- İşlemler elle girilir

### Ürün ne yapar?

- Manuel alım, satım, nakit ve basit düzeltmeleri kaydeder.
- Pozisyon, nakit, NAV ve ağırlıkları hesaplar.
- Readiness ve downside değerlendirmesini sermaye etkisinden önce dondurur.
- Düşünülen işlemi capital policy’ye karşı sınar.
- Kayıp bütçesi, azami ağırlık, no-trade bandı ve hard limitleri gösterir.
- Alım/satım kadar `no_change` kararını da kaydeder.
- Karar anında ne bilindiğini sonradan yeniden kurabilir.

### Dört kalıcı nesne

1. `capital_policy`
2. `assessment_record`
3. `decision_record`
4. `account_event`

### Kullanıcı akışı

```text
fund assess
    ↓
Araştırma hükmü portföy etkisi gösterilmeden kaydedilir
    ↓
fund trade-preview
    ↓
İşlemin ağırlık, nakit ve kayıp bütçesi etkisi gösterilir
    ↓
Kullanıcı iptal eder, miktarı değiştirir veya gerekçesiyle karar verir
    ↓
decision_record
    ↓
fund trade-add veya shadow/no_change kaydı
```

### Arayüz

- Yazma: etkileşimli CLI
- Okuma: salt-okunur statik HTML
- Sunucu, web formu, kullanıcı yönetimi veya broker bağlantısı yok

### İnşa sırası

1. Minimal capital policy’yi doldur.
2. Dört küçük şema ve SQLite DDL’yi yaz.
3. Açılış pozisyonları, nakit ve account-event projection’ını çalıştır.
4. `fund assess` akışını kur.
5. `fund trade-preview` ve policy hesaplarını kur.
6. Karar, trade ve `no_change` kayıtlarını ekle.
7. Salt-okunur HTML görünümünü üret.
8. Tek bir NVDA gölge vakasını uçtan uca çalıştır.
9. Sekiz-on iki hafta kullan; yalnız ölçülen acıya göre büyüt.

### Şimdi yapılmayacaklar

- Broker importer
- Reconciliation motoru
- Lot ve vergi motoru
- Order/partial-fill lifecycle
- Otomatik skill orkestrasyonu
- `capital_input_manifest`
- Genel event-store
- Portföy optimizasyonu
- Çok alternatifli proposal
- Attribution/counterfactual motoru
- A0–A4 yetki sistemi
- Düzenlenebilir web uygulaması

### Büyütme tetikleyicileri

Yalnız şu durumlardan biri gerçekleşirse yeni katman eklenir:

- Manuel giriş tekrarlayan hata üretir.
- Haftalık işletim 15–20 dakikayı aşar.
- Geçmiş bir karar yeniden kurulamıyordur.
- Pozisyon veya işlem sayısı belirgin artar.
- Birden fazla hesap/broker gerekir.
- Codex çıktısını elle assessment’a çevirmek sürdürülemez olur.
- Aynı istisna ikinci kez yaşanır ve maddi risk taşır.

Her tetikleyicide yalnız en küçük çözüm eklenir; hedef platform topluca inşa edilmez.

## 4. Son söz

> **Yarın tek bir gerçek gölge kararı uçtan uca çalıştır: `assess → trade-preview → decision → trade/no_change`. Bu akışa doğrudan hizmet etmeyen hiçbir kodu yazma.**