## 1. Gerçek kullanım akışı

Örnek için mevcut gölge kitabın NAV’ını 100.000 dolar, nakdini 20.000 dolar varsayalım.

### Aşama A — Araştırma hükmünü dondurma

Kullanıcı önce portföy etkisini görmeden çalışır:

```text
> fund assess NVDA

Tez özeti:
> AI hızlandırıcı talebi ve yazılım ekosistemiyle beklentilerin üzerinde büyüme.

Readiness [starter/core]:
> starter

Downside senaryosu:
> Talep normalleşir, marj daralır ve değerleme 12 aylık kazancın 25 katına iner.

Downside kaybı:
> -30%

Kanıt tarihi:
> 2026-08-16

Yeniden inceleme tarihi:
> 2026-11-30

Bu pozisyona sahip olmasaydınız aynı downside'ı kabul eder miydiniz? [E/H]
> E
```

Sistem `ASM-...` kimlikli immutable bir assessment kaydeder. Bu aşamada mevcut nakit, olası ağırlık veya “kaç hisse alabilirsin?” sonucu gösterilmez.

Codex kullanılmışsa kaynak olarak yalnız artefakt yolu/digest’i eklenir. Readiness ve downside, Codex’in doğrudan sermaye girdisi değil, kullanıcının kabul ettiği hükümdür.

### Aşama B — İşlemi sınama

```text
> fund trade-preview NVDA buy --quantity 50 --price 180 \
    --assessment ASM-...

NVDA — ALIM ÖNİZLEMESİ

Düşünülen işlem        50 × $180 = $9.000
Portföy NAV             $100.000
Nakit                   $20.000 → $11.000
NVDA ağırlığı           %0,00 → %9,00
Pozisyon sayısı         8 → 9

DONDURULMUŞ ARAŞTIRMA
Readiness               starter
Downside                -%30
Kanıt tarihi             2026-08-16
İnceleme tarihi          2026-11-30

POLICY KONTROLÜ
Readiness tavanı         %5,00
Kayıp bütçesi tavanı     %3,33  (100 bp / %30)
Mutlak pozisyon tavanı   %10,00
Bağlayıcı kısıt          kayıp bütçesi

SONUÇ                    POLICY DIŞI
50 hisse                 270 bp downside yükü
Policy içi yaklaşık üst  18 hisse / $3.240 / %3,24

[R] 18 hisseye indir
[C] İptal et
[O] Policy dışı kararı gerekçesiyle kaydet
```

Kullanıcı 18 hisseye indirirse sistem şu bilgileri tek bir immutable `decision_record` içinde dondurur:

- Assessment referansı
- Policy sürümü
- İşlem öncesi portföy ve fiyat
- İlk düşünülen 50 hisse
- Hesaplanan limitler
- Son karar: 18 hisse
- Kullanıcı gerekçesi
- Kararın `shadow` olduğu

Gerçek veya kâğıt üzerinde gerçekleşme sonradan tek komutla girilir:

```text
> fund trade-add --decision DEC-... --quantity 18 --price 181.20
```

### Aylık “hiçbir şey yapma” oturumu

```text
> fund review --as-of 2026-09-30

NAV       $103.420
Nakit     %11,4
Drawdown  -%2,1
Pozisyon  9 / azami 10

Ticker  Ağırlık  Policy max  Readiness  Downside  İnceleme
NVDA      %3,4      %3,33     starter      -%30    2026-11-30
MSFT      %9,1      %9,5      core         -%18    güncel
...
 
UYARILAR
- NVDA ağırlığı tavanın 7 bp üzerinde; no-trade bandı içinde.
- Gecikmiş inceleme yok.
- Hard breach yok.

Bu ay sermaye değişikliği var mı? [E/H]
> H

No-change gerekçesi:
[1] Maddi yeni kanıt yok
[2] Değişiklik no-trade bandı içinde
[3] Araştırma bekleniyor
[4] Serbest metin
> 1
```

Sistem aylık snapshot’ı, policy sonuçlarını ve `no_change` kararını kaydeder. “Hiçbir şey yapmamak” da böylece görünür bir karar olur.

## 2. Arayüz

En doğru başlangıç:

> **Etkileşimli CLI ile yazma, salt-okunur statik HTML ile okuma.**

Bu iki ayrı uygulama değildir:

- CLI tek yazma yoludur.
- HTML aynı veriden yeniden üretilen projection’dır.
- Sunucu, kullanıcı hesabı, frontend framework veya form tabanlı web uygulaması yoktur.

CLI şu dar komutlardan oluşur:

```text
fund assess
fund trade-preview
fund trade-add
fund cash-add
fund review
fund correct
fund status
fund report
```

Statik HTML’de yalnız şunlar görünür:

- NAV, nakit ve pozisyonlar
- Policy tavanları ve ihlaller
- Review-due listesi
- Son kararlar
- Tek kararın assessment → etki → nihai karar zinciri

Sadece CLI kullanmak mümkün fakat aylık sekiz pozisyonu ve geçmiş kararları okumak yorucu olur. Salt-okunur HTML’nin maliyeti küçüktür ve insan yüzeyine gerçek değer katar.

## 3. Araştırma ve skill’ler

V0’da şunlar çıkar:

- `research_work_request`
- Router ve episode orkestrasyonu
- Lead/support otomasyonu
- Görünürlük matrisi
- `contract_manifest`
- `model_input_manifest`
- `capital_input_manifest`
- Otomatik skill → sermaye girdisi akışı

Kullanıcı araştırmayı mevcut yöntemle yapar:

1. Codex/skill’i isterse ayrı bir oturumda çalıştırır.
2. Result artefaktını okur.
3. `fund assess` içinde kendi kabul ettiği tez, readiness ve downside’ı girer.
4. Artefaktı yalnız kaynak olarak bağlar.

Skill önerir; kullanıcı sermaye girdisini yazar.

`decision_record` içindeki readiness ve downside tek başına yeterli değildir, çünkü iki aşamalı davranış korunacaksa bunların portföy etkisinden önce dondurulması gerekir. Bu nedenle çok küçük bir dördüncü nesne eklenir:

- `assessment_record`
- `decision_record`
- `account_event`
- `capital_policy`

`capital_input_manifest` gerekmez. `decision_record`, kullandığı `assessment_id`, policy sürümü ve fiyat zamanını zaten taşıyarak o kararın küçük manifesti olur.

### İki aşamalı adjudication kalmalı mı?

**Evet, fakat mimari olarak değil, kullanıcı akışı olarak kalmalı.**

İki ayrı komut yeterlidir:

```text
fund assess NVDA
fund trade-preview NVDA ...
```

İlk komut portföy etkisini göstermez. İkinci komut yalnız kaydedilmiş assessment’ı kullanır. Kullanıcının kendi portföyünü tamamen unutması mümkün değildir; amaç mükemmel körlük değil, hükmü gördüğü sermaye sonucuna göre aynı anda eğip bükmesini zorlaştırmaktır.

## 4. Gerçekçi inşa süresi

Mevcut altyapı ve dar kapsamla:

| Parça | Süre |
|---|---:|
| Dört küçük şema + SQLite DDL | 1 gün |
| Manuel account-event girişi ve projection | 1–2 gün |
| Policy hesapları ve hedefli testler | 1–2 gün |
| Assessment ve trade-preview akışı | 1–2 gün |
| Karar/no-change kaydı | 1 gün |
| Salt-okunur HTML rapor | 1–2 gün |
| Gölge veriyle hata düzeltme | 2–3 gün |

**CLI ile kullanılabilir ilk sürüm:** 5–8 odaklı iş günü.  
**HTML, test ve gölge denemesiyle güvenilir sürüm:** 8–12 iş günü.  
Kısmi zamanlı gerçek takvim: yaklaşık **2–4 hafta**.

Şunlar süreyi yeniden haftalara çıkarır:

- Broker importer
- Gerçek ve gölge kitabı aynı anda yönetmek
- Otomatik skill entegrasyonu
- Lot/vergi motoru
- Karmaşık kurumsal işlemler
- Genel policy dili
- Düzenlenebilir web arayüzü
- Çok kullanıcı veya yetki rolleri

Bu küçük ürünün sınırı nettir: **araştırma üretmez, broker’ı taklit etmez ve portföy optimize etmez; kullanıcının düşündüğü işlemi policy’ye karşı sınar ve o anda bilinenleri değiştirilemez bir karar kaydına dönüştürür.**