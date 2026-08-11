import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest

from fundamental_pipeline_us.cache import cache_filing, _resolve_facts_document, facts_document_path
from fundamental_pipeline_us.errors import SecDataError
from fundamental_pipeline_us.models import FilingRef


def _zip_bytes(name="issuer.htm", content=b"filing"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, content)
    return buffer.getvalue()


class _Client:
    def __init__(self, payload):
        self.payload = payload

    def get_json(self, _url):
        return {"directory": {"item": [{"name": "filing-xbrl.zip"}]}}

    def get_bytes(self, _url):
        return self.payload


def _filing():
    return FilingRef(
        cik="0000021344",
        accession="0000000000-26-000001",
        form="10-K",
        filing_date=date(2026, 2, 20),
        report_date=date(2025, 12, 31),
        primary_document="issuer.htm",
    )


def test_cache_filing_extracts_and_records_hash(tmp_path):
    target = cache_filing(_Client(_zip_bytes()), tmp_path, _filing())
    assert (target / "issuer.htm").read_bytes() == b"filing"
    metadata = json.loads((target / "cache-metadata.json").read_text(encoding="utf-8"))
    assert metadata["accession"] == "0000000000-26-000001"
    assert len(metadata["xbrl_zip_sha256"]) == 64


def test_cache_rejects_zip_traversal(tmp_path):
    with pytest.raises(SecDataError, match="unsafe"):
        cache_filing(_Client(_zip_bytes("../escape.htm")), tmp_path, _filing())


def _cag_filing(primary: str = "cag-2017x10k.htm") -> FilingRef:
    return FilingRef(
        cik="0000023217", accession="0001628280-17-007184", form="10-K",
        filing_date=date(2017, 7, 20), report_date=date(2017, 5, 28),
        primary_document=primary,
    )


def test_inline_package_resolves_to_the_primary_document(tmp_path: Path):
    (tmp_path / "cag-2017x10k.htm").write_text("<html/>", encoding="utf-8")
    (tmp_path / "cag-20170528.xsd").write_text("<xsd/>", encoding="utf-8")
    assert _resolve_facts_document(tmp_path, _cag_filing()).name == "cag-2017x10k.htm"


def test_pre_inline_package_resolves_to_the_instance_document(tmp_path: Path):
    """The SEC phased inline XBRL in between 2019 and 2021. Before a filer
    crossed its phase-in date the package contains no HTML at all, so keying
    on the primary document rejected every historical filing -- 19 of 26
    quarters in the 2018-2024 run failed this way."""
    (tmp_path / "cag-20170528.xml").write_text("<xbrl/>", encoding="utf-8")
    (tmp_path / "cag-20170528.xsd").write_text("<xsd/>", encoding="utf-8")
    for suffix in ("_cal", "_def", "_lab", "_pre"):
        (tmp_path / f"cag-20170528{suffix}.xml").write_text("<link/>", encoding="utf-8")

    assert _resolve_facts_document(tmp_path, _cag_filing()).name == "cag-20170528.xml"


def test_ambiguous_package_fails_closed(tmp_path: Path):
    (tmp_path / "one-20170528.xml").write_text("<xbrl/>", encoding="utf-8")
    (tmp_path / "two-20170528.xml").write_text("<xbrl/>", encoding="utf-8")
    with pytest.raises(SecDataError, match="single XBRL instance"):
        _resolve_facts_document(tmp_path, _cag_filing())


def test_metadata_without_facts_document_is_treated_as_inline(tmp_path: Path):
    """Cache entries written before this field existed always described an
    inline filing."""
    assert facts_document_path(tmp_path, {"primary_document": "x.htm"}).name == "x.htm"
    assert facts_document_path(tmp_path, {
        "primary_document": "x.htm", "facts_document": "x-2017.xml",
    }).name == "x-2017.xml"


def test_fact_cache_round_trips_and_invalidates(tmp_path: Path, monkeypatch):
    """The cache must return exactly what the parser returned, and must
    invalidate when the parser changes -- a stale artifact silently reused is
    how a wrong diagnosis gets made."""
    from datetime import date as _date
    from fundamental_pipeline_us import fact_cache
    from fundamental_pipeline_us.models import SecFact

    document = tmp_path / "doc.htm"
    document.write_text("<html/>", encoding="utf-8")
    produced = (
        SecFact(namespace="ns", concept="Revenues", value="1", unit="USD",
                context_id="c1", start_date=_date(2024, 1, 1), end_date=_date(2024, 12, 31),
                dimensions=(("axis", "member"),), decimals="-6", is_nil=False),
        SecFact(namespace="ns", concept="Assets", value="2", unit="USD", context_id="c2",
                start_date=None, end_date=_date(2024, 12, 31)),
    )
    calls = []

    def fake_load(path):
        calls.append(path)
        return produced

    monkeypatch.setattr("fundamental_pipeline_us.xbrl.load_facts", fake_load)
    root = tmp_path / "cache"

    assert fact_cache.load_facts_cached(document, root) == produced
    assert fact_cache.load_facts_cached(document, root) == produced
    assert len(calls) == 1, "second call must be served from cache"

    # A changed parser fingerprint must not reuse the stored entry.
    monkeypatch.setattr(fact_cache, "_PARSER_FINGERPRINT", "different")
    assert fact_cache.load_facts_cached(document, root) == produced
    assert len(calls) == 2


def test_fact_cache_discards_a_corrupt_entry(tmp_path: Path, monkeypatch):
    from datetime import date as _date
    from fundamental_pipeline_us import fact_cache
    from fundamental_pipeline_us.models import SecFact

    document = tmp_path / "doc.htm"
    document.write_text("<html/>", encoding="utf-8")
    produced = (SecFact(namespace="ns", concept="Assets", value="2", unit="USD",
                        context_id="c", start_date=None, end_date=_date(2024, 12, 31)),)
    monkeypatch.setattr("fundamental_pipeline_us.xbrl.load_facts", lambda path: produced)
    root = tmp_path / "cache"
    fact_cache.load_facts_cached(document, root)
    next(root.iterdir()).write_text("{ bozuk", encoding="utf-8")
    assert fact_cache.load_facts_cached(document, root) == produced
