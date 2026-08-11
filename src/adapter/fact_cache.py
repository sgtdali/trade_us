"""Ayristirilmis XBRL fact'lerinin accession bazli onbellegi.

Arelle yavastir cunku dosyayi okumakla kalmaz: taksonomi agacini (DTS) cozer,
sema ve linkbase'leri yukler, context/unit/dimension iliskilerini kurar. Olculdu
(2026-08-05): 3 MB'lik bir 10-K icin ~2,6 saniye, 1,5 MB'lik bir 10-Q icin ~1,7.
Sirket basina iki 10-K ve bir 10-Q islendigi icin bu ~7 saniye eder.

Israf, ayni filing'in tekrar tekrar ayristirilmasidir. Bir filing degismez;
degisen yalniz degerlemenin as_of tarihi ve fiyattir. Olay tabanli kosuda 91
karar gunu x 24 sirket x 3 filing = 6.552 ayristirma yapiliyordu, oysa ortada
~150 farkli filing var: ayni is ortalama 43 kez.

Onbellek anahtarı, ciktiyi belirleyen her seyi kapsar: belgenin kendi
icerik hash'i ve ayristiriciyi tanimlayan kaynak dosyanin hash'i. Ayristirici
degisirse onbellek kendini gecersiz kilar -- bu gece bayat artifact yuzunden
yanlis teshis konuldugu icin bu garanti acikca kurulmustur, sessiz yeniden
kullanim kabul edilmez.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from .models import SecFact

_PARSER_FINGERPRINT: str | None = None


def _parser_fingerprint() -> str:
    """Ayristiricinin kimligi. xbrl.py'nin hangi alanlari cikardigi degisirse
    onbellekteki her kayit gecersizlesir."""
    global _PARSER_FINGERPRINT
    if _PARSER_FINGERPRINT is None:
        source = (Path(__file__).parent / "xbrl.py").read_bytes()
        _PARSER_FINGERPRINT = hashlib.sha256(source).hexdigest()[:16]
    return _PARSER_FINGERPRINT


def _key(document: Path) -> str:
    digest = hashlib.sha256(document.read_bytes()).hexdigest()[:24]
    return f"{digest}-{_parser_fingerprint()}"


def _encode(fact: SecFact) -> list:
    return [
        fact.namespace, fact.concept, fact.value, fact.unit, fact.context_id,
        fact.start_date.isoformat() if fact.start_date else None,
        fact.end_date.isoformat(),
        [list(item) for item in fact.dimensions],
        fact.decimals, fact.is_nil,
    ]


def _decode(row: list) -> SecFact:
    return SecFact(
        namespace=row[0], concept=row[1], value=row[2], unit=row[3], context_id=row[4],
        start_date=date.fromisoformat(row[5]) if row[5] else None,
        end_date=date.fromisoformat(row[6]),
        dimensions=tuple(tuple(item) for item in row[7]),
        decimals=row[8], is_nil=row[9],
    )


def load_facts_for_documents(documents: tuple[Path, ...], cache_root: Path) -> tuple[SecFact, ...]:
    """Bir inline belge KUMESININ fact'leri.

    Belgeler tek tek ayristirilip birlestirilemez: cok belgeli inline XBRL'de
    `ix:header` yalniz bir belgededir ve digerleri tek baslarina sifir fact
    verir. Kume Arelle'e bir butun olarak verilir; onbellek anahtari da bu
    yuzden tek bir belgenin degil, kumedeki HER belgenin icerigini kapsar --
    aksi halde ikinci belge degisince onbellek bunu gormezdi."""
    if len(documents) == 1:
        return load_facts_cached(documents[0], cache_root)

    from .xbrl import load_facts

    digest = hashlib.sha256()
    for document in documents:
        digest.update(hashlib.sha256(document.read_bytes()).digest())
    path = cache_root / f"{digest.hexdigest()[:24]}-{_parser_fingerprint()}.json"
    if path.is_file():
        try:
            return tuple(_decode(row) for row in json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, IndexError, TypeError, ValueError):
            path.unlink(missing_ok=True)
    facts = load_facts(documents)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps([_encode(fact) for fact in facts], separators=(",", ":")), encoding="utf-8"
    )
    temporary.replace(path)
    return facts


def load_facts_cached(document: Path, cache_root: Path) -> tuple[SecFact, ...]:
    """``load_facts`` ile ayni sonucu dondurur, mumkunse onbellekten."""
    from .xbrl import load_facts

    path = cache_root / f"{_key(document)}.json"
    if path.is_file():
        try:
            return tuple(_decode(row) for row in json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, IndexError, TypeError, ValueError):
            path.unlink(missing_ok=True)  # bozuk kayit sessizce kullanilmaz
    facts = load_facts(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps([_encode(fact) for fact in facts], separators=(",", ":")), encoding="utf-8"
    )
    temporary.replace(path)
    return facts
