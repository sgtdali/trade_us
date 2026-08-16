# Public Equity Investing akışı

> **YÜRÜRLÜKTEN KALKTI.** Bu diyagram mevcut kodun akışını gösteriyor
> (idea-generation → bucket → workflow zinciri → tez). Yeni tasarımda bu akış
> yok: keşif hattı sona alındı, workflow zinciri sabit dispatch kurallarına
> dönüştü, tez ayrı bir lifecycle nesnesi oldu ve araya iki aşamalı insan
> adjudication'ı girdi.
>
> Güncel akış: [pei-company-lifecycle-tasarim.md](pei-company-lifecycle-tasarim.md)
> Bölüm 4 (karar akışı), Bölüm 5 (izleme döngüsü), Bölüm 6 (otomatik
> araştırma operasyonu).
>
> Mevcut kodu okuyacaksanız diyagram hâlâ doğru bir tarif; yeni sistem için
> değil.

Portföy öncesi, kurulurken ve kurulduktan sonra. Kaynak:
[docs/pei-workflow.md](pei-workflow.md) Bölüm 2-3,
`scripts/us_pei_pack.py` içindeki `STEP_BLOCKS`, `us/config/mandate.json` ve
eklentinin `skills/company-tearsheet/SKILL.md` dosyası.

Renk kodu: yeşil = bizim deterministik katmanımız, mor = ChatGPT skill'i,
sarı = karar noktası, kırmızı = kayıt, kesikli kahverengi = **henüz
kurulmadı**.

## Faz 0 — veri katmanı, tek komut

Tetik takvim değil **dosyalama**: SEC'de bir şirketin yeni 10-K/10-Q'su
elimizdekinden yeniyse yalnız o şirket yeniden işlenir.

```bash
python scripts/us_pei_pack.py --for idea
```

```mermaid
flowchart LR
    subgraph TAZE["Her koşuda tazelenir"]
        direction TB
        PR["Fiyat defteri<br/>son kapanış"]:::ours
        SEC["SEC keşfi"]:::ours
        CONS["Konsensüs"]:::ours
        EV["Olay takvimi"]:::ours
    end
    SEC --> Q{"SEC'deki rapor<br/>elimizdekinden yeni mi?"}:::dec
    Q -->|evet| RE["O şirketi yeniden işle"]:::ours
    Q -->|hayır| NO["Atla"]:::ours
    RE --> ART
    NO --> ART
    PR --> ART
    CONS --> ART
    EV --> ART
    ART[("Artifact'ler<br/>valuation-results · valuation-inputs<br/>financial · signals")]:::store
    ART --> COV["coverage.json<br/>kaç şirket çıktı, eksik kim"]:::ours
    ART --> PACK["pack.json + instructions.md"]:::ours

    classDef ours fill:#256b62,stroke:#1a4d46,color:#fff
    classDef dec fill:#8a6d1f,stroke:#6b5416,color:#fff
    classDef store fill:#3a4048,stroke:#22262b,color:#fff
```

Kesim, fiyat defterindeki **son kapanmış seans**; klasör adı paketin üretildiği
gün. Pazartesi sabahı üretilen paketin kesimi Cuma'dır.

## Faz 1 — portföyü ilk kez kurmak

A kovasındaki sorular bir zincir değil, her isim için ayrı ayrı sorulan
bağımsız kapılar. Bir isim hiçbirinden geçmeyebilir.

```mermaid
flowchart TD
    P0["pack.json — 60 şirket<br/><i>--for idea</i>"]:::ours
    P0 --> IG["idea-generation<br/><i>tek koşu, bütün evren</i>"]:::skill
    IG --> BK{"Kova ayrımı<br/>A · B · C · Reject"}:::dec
    BK -->|"B / C / Reject"| PARK[("Kayda geç, portföye girme<br/>elenenler de ölçülür")]:::store
    BK -->|"A kovası — tipik 5-12 isim"| Q1

    Q1{"Elimde güncel<br/>bir taban var mı?"}:::dec
    Q1 -->|"yok / bayat"| TS["company-tearsheet<br/><i>--for tearsheet --only TICKER</i><br/>HÜKÜM YOK, sadece taban"]:::skill
    Q1 -->|güncel| Q2
    TS --> Q2

    Q2{"Bilanço / olay<br/>3 haftadan yakın mı?"}:::dec
    Q2 -->|evet| EP["earnings-preview<br/><i>CSV seti; üretemediğimiz<br/>iki dosya boş başlıkla</i>"]:::skill
    Q2 -->|hayır| Q3
    EP --> Q3

    Q3{"Açık soru fiyat mı?"}:::dec
    Q3 -->|evet| CV["comps-valuation<br/>+ emsal yakınsaması kanıt değil notu"]:::skill
    Q3 -->|hayır| Q4
    CV --> Q4

    Q4{"Tez oluştu mu?"}:::dec
    Q4 -->|evet| LSP["long-short-pitch<br/>yeni ham veri yok"]:::skill
    Q4 -->|hayır| WATCH["İzleme listesi<br/>tez yok, pozisyon yok"]:::skill

    LSP --> SIZE["portfolio-risk-management<br/>pozisyon boyutu · konsantrasyon"]:::todo
    SIZE --> MAND{"Mandate kontrolü<br/>long-only · sadece adi hisse<br/>kaldıraç yok · opsiyon yok"}:::dec
    MAND --> TRACK
    WATCH --> TRACK
    TRACK["thesis-tracker<br/><b>KAYIT yalnız burada</b><br/>her eşik bir sayı + bir tarih"]:::record
    TRACK --> PF[("İlk portföy<br/>pozisyon adedi taramanın sonucu")]:::store

    classDef ours fill:#256b62,stroke:#1a4d46,color:#fff
    classDef skill fill:#66467a,stroke:#4a3159,color:#fff
    classDef dec fill:#8a6d1f,stroke:#6b5416,color:#fff
    classDef record fill:#8e2f2f,stroke:#6d2222,color:#fff
    classDef store fill:#3a4048,stroke:#22262b,color:#fff
    classDef todo fill:#6b5a3a,stroke:#4d4029,color:#fff,stroke-dasharray: 5 4
```

> **Kurulmadı:** `portfolio-risk-management` eklentide var ama hiç koşulmadı ve
> `STEP_BLOCKS`'ta karşılığı olan bir paket adımı yok — "A listesinden
> pozisyona" geçişte bugün otomatik hiçbir şey yok. `thesis-tracker`'ın kayıt
> şeması [pei-workflow.md](pei-workflow.md) Bölüm 5'te tasarlandı, henüz bir kez
> bile kullanılmadı.

## Faz 2 — portföy kurulduktan sonra

Üç ayrı saat: haftalık kontrol, aylık rebalans, ve bunlardan bağımsız olay
tetiklemesi. Mandate'in açık hükmü: ikisi de portföyü değiştirmek **zorunda
değil**.

```mermaid
flowchart TD
    PF[("Mevcut portföy<br/>+ thesis-tracker satırları")]:::store
    PF --> W["HAFTALIK kontrol"]:::clock
    PF --> M["AYLIK rebalans"]:::clock
    PF --> E["OLAY tetikli"]:::clock

    W --> WQ{"Eşik aşıldı mı?<br/>kill criteria tetiklendi mi?"}:::dec
    WQ -->|hayır| HOLD["Tut — değişiklik yok<br/><i>geçerli sonuç</i>"]:::skill
    WQ -->|evet| REV["thesis-tracker güncelle<br/>hangi eksende bozuldu"]:::record
    REV --> EXIT{"Tez öldü mü?"}:::dec
    EXIT -->|evet| SELL["Pozisyonu kapat<br/>gerekçeyi kaydet"]:::record
    EXIT -->|hayır| HOLD

    M --> FRESH["us_pei_pack.py --for idea"]:::ours
    FRESH --> IG2["idea-generation<br/>yeni A kovası"]:::skill
    IG2 --> CMP{"Yeni A listesi ile<br/>mevcut portföyü karşılaştır"}:::dec
    CMP -->|"portföyde yok, A'da var"| NEW["Yeni aday<br/>→ Faz 1'in isim döngüsü"]:::skill
    CMP -->|"portföyde var, A'da yok"| DOWN{"Tez hâlâ ayakta mı?"}:::dec
    CMP -->|"ikisinde de var"| KEEP["Tut, tracker'ı güncelle"]:::record
    DOWN -->|evet| KEEP
    DOWN -->|hayır| SELL

    E --> EQ{"Tuttuğum bir isimde<br/>bilanço 3 haftadan yakın mı?"}:::dec
    EQ -->|evet| EP2["earnings-preview<br/>beklenti çıtası + falsifier"]:::skill
    EP2 --> PRINT["Bilanço açıklandı"]:::clock
    PRINT --> RETS["company-tearsheet TAZELE<br/><i>taban artık bayat</i>"]:::skill
    RETS --> REV

    NEW --> TRACK2
    KEEP --> TRACK2
    SELL --> TRACK2
    HOLD --> TRACK2
    TRACK2["thesis-tracker<br/>changelog + kanıt satırı"]:::record
    TRACK2 --> PF

    classDef ours fill:#256b62,stroke:#1a4d46,color:#fff
    classDef skill fill:#66467a,stroke:#4a3159,color:#fff
    classDef dec fill:#8a6d1f,stroke:#6b5416,color:#fff
    classDef record fill:#8e2f2f,stroke:#6d2222,color:#fff
    classDef store fill:#3a4048,stroke:#22262b,color:#fff
    classDef clock fill:#2f4858,stroke:#1d2e39,color:#fff
```

> **Mandate'in kayıtlı gerilimi:** eklentinin varsayılan ufku 3-18 ay, bu
> mandate aylık rebalans yapıyor. Ölçüldü: aylık kararlar ortalama **46 gün
> eski** veriye dayanıyor ve şirket-aylarının **%32'sinde** karardan sonraki 30
> gün içinde yeni bir 10-Q/10-K geliyor. Alternatif, takvimi değil
> **dosyalamayı** tetik almak; `next_events` tarihleri paketin içinde.

## Hangi adım hangi bloğu görüyor

`--for` değeri paketin içeriğini değiştirir. Ölçüldü: ORCL tearsheet'inde
`sector_peers` paketin %36'sıydı ve çıktıda yalnız "bu emsal grubu heterojen"
denip reddedilmek için kullanıldı.

| Blok | idea | tearsheet | preview | comps | deepdive | pitch |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| net_debt | ● | ● | ● | ● | ● | ● |
| special_situations | ● | ● | ● | ● | ● | ● |
| earnings_quality_flags | ● | ● | ● | ● | ● | ● |
| next_events | ● | ● | ● | – | ● | ● |
| roic | ● | ● | – | ● | ● | ● |
| own_valuation_history | ● | ● | – | ● | – | ● |
| deterministic_signals | ● | – | ● | – | ● | ● |
| sector_peers | – | – | – | ● | – | ● |
| quarterly_series | – | – | – | – | ● | – |
| pre_print_consensus | – | – | – | – | ● | – |

## Bugün gerçekten ne çalışıyor

- **Çalışıyor:** veri katmanı tek komutta; kapsama ROIC 49/60, net borç 58/60,
  konsensüs ve sinyaller 60/60.
- **Bir kez koşuldu:** `idea-generation` (evren) ve `company-tearsheet` (ORCL).
- **Paket adımı var, hiç koşulmadı:** `preview`, `comps`, `deepdive`, `pitch`.
- **Hiç yok:** `thesis-tracker` kaydı ve `portfolio-risk-management`.
- **Belirsiz bırakılmış:** pozisyon adedi (taramanın sonucu) ve benchmark (yok —
  sonuçlar aktif ağırlık çerçevesinde yorumlanmamalı).
