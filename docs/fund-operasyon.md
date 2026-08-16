# Portföy karar günlüğü — operasyon

Bu doküman **sistemi nasıl çalıştıracağını** anlatır. Tasarım
[pei-company-lifecycle-tasarim.md](pei-company-lifecycle-tasarim.md)'de,
yapılacak işler [uygulama-plani.md](uygulama-plani.md)'de.

Komut: `fund`. Kurulu değilse `python -m adapter.fund.cli` (PYTHONPATH=src).

---

## Günlük ritim

| Ne zaman | Komut | Süre |
|---|---|---|
| Her gece (otomatik) | `fund research-cycle` | — |
| Sabah | `fund status` | 30 sn |
| İş varsa | `fund adjudicate <job_id>` | 10-30 dk |
| Ayda bir | `fund review --price ...` | 20-40 dk |

`fund inbox` günlük kuyruktur, `fund review` aylık sermaye oturumudur.
**Aynı şey değiller.** Inbox araştırma hükmü ister; review sermaye kararı.

---

## İlk kurulum

```bash
fund init
```

Defteri oluşturur, `config/fund/instrument-master.json` yoksa yazar, capital
policy'yi doğrular.

### 1. Hisseleri tanıt

```bash
fund instrument add --ticker NVDA --name "NVIDIA Corporation" --cik 0001045810
```

`--cik` **gerekli**: gece döngüsü SEC'i onunla tarıyor. İki hisse sınıfı için
ikincisinde `--issuer iss:alphabet --share-class C` verin — aynı ihraççıya
bağlanırlar ve issuer tavanını **birlikte** doldururlar.

### 2. Açılış kitabını gir

```bash
fund open cash --amount 100000 --date 2026-08-01
fund open position --security NVDA --quantity 100 --unit-cost 90 --date 2026-08-01
fund open position --security GOOGL --quantity 50 --date 2026-08-01   # maliyet bilinmiyor
```

`--unit-cost` vermezseniz maliyet `unknown` kaydedilir ve o pozisyon için P&L
**hiç hesaplanmaz**. Sıfır yazmak %100 hayalî kâr üretirdi.

Girdikten sonra broker ekranıyla karşılaştırın. Açıklanamayan fark varsa
kapatmadan not edin — sistem sizin kaydınızı otoriter sayar ama broker haklıdır.

### 3. Gece döngüsünü kur

```bash
fund schedule --at 03:30
```

Yazdırdığı `schtasks` komutunu çalıştırın, sonra Task Scheduler'da görevi açıp
**"Run task as soon as possible after a scheduled start is missed"** kutusunu
işaretleyin. Bu olmadan gece kapalı kalan bilgisayar o günü tamamen atlar.

Kurduktan sonra `fund status` ile gerçekten çalıştığını doğrulayın. Sessizce
durmuş bir zamanlanmış görev, sakin bir piyasadan ayırt edilemez.

---

## Bir pozisyon açmak

İki aşama, iki ekran. Sıra bağlayıcı.

```bash
# 1. Araştırma hükmü -- ekranda hiçbir sermaye rakamı yok
fund assess NVDA \
  --summary "Veri merkezi talebi 2027'ye kadar arzı aşıyor" \
  --readiness starter \
  --downside -0.30 \
  --downside-scenario "Hyperscaler capex duraklar, çarpan 25x'e sıkışır" \
  --evidence-date 2026-08-16 --review-due 2026-11-15

# 2. Sermaye sonucu
fund trade-preview NVDA buy --quantity 50 --price 180 --mark GOOGL=200
```

Önizleme tek başına **hiçbir şey kaydetmez**. Kararı dondurmak için:

```bash
fund trade-preview NVDA buy --quantity 50 --price 180 \
  --decide reduce --rationale "Kayıp bütçesi bağlıyor"
```

Dört seçenek: `accept` (policy içindeyse), `reduce` (policy içi boyuta in),
`cancel`, `outside-policy` (`--reason-code` zorunlu).

Emir broker'da gerçekleştikten sonra:

```bash
fund trade-add --decision DEC-... --quantity 18 --price 181.20 --fee 1
```

Kararlar varsayılan olarak **shadow** modda. Canlıya geçmek için `--live` — ama
en az iki aylık döngü ve bir olay vakası görülmeden geçmeyin (uygulama planı S1).

---

## Tez açmak ve izlemeye almak

```bash
fund thesis open NVDA
fund thesis contract-template > contract.json     # düzenle
fund thesis contract THS-... --from contract.json
```

Sözleşme **metrik kataloğuna bağlanmazsa aktive edilmez**. Bağlanmayan bir
koşulu mekanik yapmaya zorlamayın — nitel soru olarak bırakın.

Kural sayısı: normal 1-3, tavan 5. Okunmayan bir sözleşme izleme değildir.

Eşik değiştirmek yeni sürüm ve gerekçe ister:

```bash
fund thesis contract THS-... --from contract-v2.json --reason "Marj tabanı mix kaymasından önce konmuştu"
```

---

## Sabah rutini

```bash
fund status
```

Üç şey söyler: döngü çalışıyor mu, ne bekliyor, ne blokluyor.

- **Q0 varsa** yeni risk artırmayın. Veri gerçeği güvenilmez veya bir tez kör.
- **Q1 varsa** `fund adjudicate <job_id>`.
- **Q2** bilgi; eylem gerektirmez.

Adjudication ekranında **sermaye rakamı yoktur** ve bu kasıtlıdır. Beş seçenek:

| Seçenek | Ne zaman |
|---|---|
| `--accept` | Öneriyi kabul ediyorsunuz |
| `--reject --reason` | Olgusal hata var; öneri reddedilir, hiçbir şey yazılmaz |
| `--replace ...` | Farklı hükümdesiniz; kendi kaydınız öneriye bağlanarak yazılır |
| `--defer --reason` | Şimdi değil; Q1'de kalır |
| `--acknowledge` | İncelemeden geçiyorsunuz; **readiness yükseltemez** |

Varsayılan yok. Toplu onay yok. 30 dakikayı geçiyorsa `--defer` veya `--reject`.

---

## Aylık oturum

```bash
fund review --price NVDA=185 --price GOOGL=200 --as-of 2026-09-30
```

NAV, nakit, drawdown, her pozisyonun ağırlığı ve policy tavanı, vadesi gelmiş
incelemeler. Sonunda:

```bash
fund review --price ... --no-change NVDA --rationale "Tez sağlam, sürüklenme bandın içinde"
```

**Hayır da bir karardır** ve kaydedilir. "Baktım ve tuttum" ile "hiç bakmadım"
aynı izi bırakmamalı.

Her review bir NAV markı yazar; drawdown ikinci review'dan itibaren hesaplanır
ve zirve dürüstçe "izleme başladığından beri" olarak tanımlanır.

---

## Görünüm

```bash
fund report --price NVDA=185 --out data/fund/report.html
```

Salt-okunur, tek dosya, dış bağımlılık yok. Yazma yolu **yoktur** — her
değişiklikten sonra yeniden üretin.

---

## Bir şey ters gittiğinde

| Belirti | Ne yapılır |
|---|---|
| `fund status` "not healthy" diyor | `fund jobs --status failed`, sonra hatayı düzeltip `fund run <job>` |
| Job üç kez başarısız, otomatik deneme durmuş | Kök nedeni düzeltin; job Q0'da duruyor, unutulmuyor |
| `contract_failed` | Skill çıktısı şemaya uymadı. Sonuç size **sunulmaz** — bu "analist bir şey söylemedi" ile aynı şey değil |
| Yanlış işlem girdim | `fund correct EVT-... --quantity 18 --note "ekstre 18 diyor"` |
| Hiç olmamış bir işlem girdim | `fund correct EVT-... --void --note "iki kez girilmiş"` |
| NAV "unavailable" | Eksik fiyat var. Kısmi NAV üretilmiyor; fiyatı verin |
| Kural hiç ateşlemiyor | `fund dispatch health` |

Girilmiş satır **hiçbir zaman** düzenlenmez. Düzeltme yeni bir satırdır ve
eskisi olduğu gibi kalır.

---

## Komut listesi

```
fund init                    fund inbox
fund instrument add/list     fund adjudicate <job>
fund open position/cash      fund review
fund trade record            fund report
fund cash record             fund status
fund adjust                  fund research-cycle
fund correct                 fund observe
fund events                  fund run <job>
fund positions               fund job open/result/fail
fund assess                  fund jobs
fund assessments             fund check / checks
fund trade-preview           fund thesis open/list/show/contract/status/close/reviewed
fund trade-add               fund dispatch health
fund decisions               fund policy show
fund schedule
```
