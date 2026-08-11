from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from .errors import SecDataError
from .models import FilingRef
from .paths import filing_cache_dir
from .sec_client import SecClient


#: Linkbase suffixes that accompany an XBRL instance but never carry facts.
_LINKBASE_SUFFIXES = ("_cal", "_def", "_lab", "_pre", "_ref")


def archive_base_url(filing: FilingRef) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{filing.cik_compact}/{filing.accession_compact}"


def _resolve_facts_document(target: Path, filing: FilingRef) -> Path:
    """Returns the file in an extracted XBRL package that actually carries the
    facts.

    Inline XBRL embeds them in the primary HTML document, and the SEC only
    mandated that presentation in phases -- large accelerated filers for
    fiscal periods ending on or after 2019-06-15, smaller reporting companies
    two years later. Before a filer crossed its phase-in date the package
    contains no HTML at all: the facts live in a separate instance document
    alongside its schema and linkbases (CAG's 2017 10-K ships exactly
    ``cag-20170528.xml`` plus ``.xsd``/``_cal``/``_def``/``_lab``/``_pre``).

    Requiring ``filing.primary_document`` inside the zip therefore rejected
    every pre-phase-in filing. Found 2026-08-04: 19 of 26 historical quarters
    failed on this, across CAG, CELH and BJ, which is not a per-company defect
    but the shape of the archive before inline XBRL.

    The instance is identified structurally rather than by name: it is the
    ``.xml`` sharing the stem of the package's ``.xsd`` and carrying none of
    the linkbase suffixes. Ambiguity fails closed instead of guessing."""
    primary = target / filing.primary_document
    if primary.exists():
        return primary

    schemas = [path for path in target.glob("*.xsd")]
    candidates = [
        path for path in target.glob("*.xml")
        if not any(path.stem.endswith(suffix) for suffix in _LINKBASE_SUFFIXES)
    ]
    if schemas:
        stems = {path.stem for path in schemas}
        matched = [path for path in candidates if path.stem in stems]
        if matched:
            candidates = matched
    if len(candidates) == 1:
        return candidates[0]
    raise SecDataError(
        f"{filing.accession}: package has neither primary document "
        f"{filing.primary_document} nor a single XBRL instance "
        f"(candidates: {sorted(path.name for path in candidates)})"
    )


def facts_document_path(cache_dir: Path, metadata: dict) -> Path:
    """Cache-metadata accessor so callers never rebuild the inline-versus-
    instance decision. Older metadata predates ``facts_document`` and always
    described an inline filing."""
    return cache_dir / (metadata.get("facts_document") or metadata["primary_document"])


def facts_document_paths(cache_dir: Path, metadata: dict) -> tuple[Path, ...]:
    """Every inline document in the package that carries facts, in a stable order.

    An inline XBRL filing is a document SET, not a single file. A filer may put
    the narrative in the primary document and the tagged financial statements in
    a sibling, and both are part of one instance. Reading only the primary then
    yields a filing that parses cleanly and contains almost nothing: CLX's
    fiscal 2025 10-K gives 68 facts from ``clx-20250630.htm`` and its financial
    statements sit in ``clx-20250630_d2.htm``, so all three statements
    normalized empty and every earnings method fell for seventeen of
    twenty-five months (found 2026-08-06).

    Siblings are identified the same structural way the instance is: they share
    the stem of the package's ``.xsd`` and differ only by a suffix. Exhibits do
    not (``fy25clxex21subsidiaries.htm``), so they are never picked up. A
    pre-inline package has a single instance and this returns just that.
    """
    primary = facts_document_path(cache_dir, metadata)
    if metadata.get("facts_document_kind") == "instance" or primary.suffix.lower() not in (".htm", ".html"):
        return (primary,)
    siblings = sorted(
        path for path in cache_dir.glob("*.htm")
        if path != primary and _is_document_set_member(path)
    )
    return (primary, *siblings)


def _is_document_set_member(path: Path) -> bool:
    """Whether an HTML file in the package is a further document of the inline set.

    Name is not enough. Most filers put every exhibit in the same package with
    the same prefix -- ``abbv-20221231xex21.htm``, ``de-20251102xex10d29.htm``,
    ``tgt-20230128xexhibit109.htm`` -- and a prefix rule swept 106 of 923
    packages into "multi-document" when only CLX genuinely is. Handing exhibits
    to Arelle would be slow and would widen the fact set for no reason.

    The distinction is in the markup, not the filename. A further document of
    the set carries tagged values (``ix:nonFraction``/``ix:nonNumeric``) but
    not the header: ``ix:header``, and with it the ``schemaRef``, appears
    exactly once per set and lives in the primary document. An exhibit carries
    no inline markup at all.
    """
    try:
        body = path.read_bytes()
    except OSError:
        return False
    if b"ix:header" in body:
        return False
    return b"ix:nonFraction" in body or b"ix:nonNumeric" in body


def cache_filing(client: SecClient, workspace: Path, filing: FilingRef) -> Path:
    target = filing_cache_dir(workspace, filing.cik, filing.accession)
    metadata_path = target / "cache-metadata.json"
    primary_path = target / filing.primary_document
    if metadata_path.exists():
        # Keyed on the facts document rather than the primary one: a
        # pre-inline package legitimately has no primary HTML, and checking
        # for it would re-download the filing on every call.
        cached = json.loads(metadata_path.read_text(encoding="utf-8"))
        if facts_document_path(target, cached).exists():
            if not primary_path.exists():
                # Entry predates the separate primary-document fetch below.
                # Repair it in place instead of re-downloading the package.
                _write_bytes_atomic(primary_path, client.get_bytes(
                    f"{archive_base_url(filing)}/{filing.primary_document}"))
            return target

    index_url = f"{archive_base_url(filing)}/index.json"
    index = client.get_json(index_url)
    items = index.get("directory", {}).get("item", [])
    zip_names = [item.get("name") for item in items if isinstance(item, dict) and str(item.get("name", "")).endswith("-xbrl.zip")]
    if len(zip_names) != 1:
        raise SecDataError(f"expected one XBRL zip for {filing.accession}, found {zip_names}")
    zip_url = f"{archive_base_url(filing)}/{zip_names[0]}"
    payload = client.get_bytes(zip_url)
    digest = hashlib.sha256(payload).hexdigest()

    target.mkdir(parents=True, exist_ok=True)
    _extract_zip_atomically(payload, target)
    facts_document = _resolve_facts_document(target, filing)
    if not primary_path.exists():
        # Pre-inline packages ship no HTML, but the primary document still
        # exists as its own file in the same EDGAR directory. Downstream text
        # adapters (Item 1A risk extraction) read it, so fetch it rather than
        # letting the whole company fail on a missing narrative section.
        document_url = f"{archive_base_url(filing)}/{filing.primary_document}"
        _write_bytes_atomic(primary_path, client.get_bytes(document_url))

    metadata = {
        "schema_version": 1,
        "cik": filing.cik,
        "accession": filing.accession,
        "form": filing.form,
        "filing_date": filing.filing_date.isoformat(),
        "report_date": filing.report_date.isoformat(),
        "primary_document": filing.primary_document,
        "facts_document": facts_document.name,
        "facts_document_kind": "inline" if facts_document == primary_path else "instance",
        "index_url": index_url,
        "xbrl_zip_url": zip_url,
        "xbrl_zip_sha256": digest,
    }
    _write_json_atomic(metadata_path, metadata)
    return target


def cache_filing_html_documents(
    client: SecClient, workspace: Path, filing: FilingRef,
) -> Path:
    """Cache the primary document and HTML exhibits for a non-XBRL workflow."""
    target = filing_cache_dir(workspace, filing.cik, filing.accession)
    metadata_path = target / "cache-metadata.json"
    primary_path = target / filing.primary_document
    if metadata_path.exists() and primary_path.exists():
        return target
    index_url = f"{archive_base_url(filing)}/index.json"
    index = client.get_json(index_url)
    items = index.get("directory", {}).get("item", [])
    names = sorted({
        str(item.get("name")) for item in items
        if isinstance(item, dict)
        and str(item.get("name", "")).lower().endswith((".htm", ".html"))
        and "/" not in str(item.get("name", ""))
        and "\\" not in str(item.get("name", ""))
    })
    if filing.primary_document not in names:
        names.append(filing.primary_document)
    target.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for name in sorted(set(names)):
        payload = client.get_bytes(f"{archive_base_url(filing)}/{name}")
        _write_bytes_atomic(target / name, payload)
        hashes[name] = hashlib.sha256(payload).hexdigest()
    if not primary_path.exists():
        raise SecDataError(f"filing cache did not contain primary document {filing.primary_document}")
    _write_json_atomic(metadata_path, {
        "schema_version": 1,
        "cik": filing.cik,
        "accession": filing.accession,
        "form": filing.form,
        "filing_date": filing.filing_date.isoformat(),
        "report_date": filing.report_date.isoformat(),
        "primary_document": filing.primary_document,
        "index_url": index_url,
        "html_sha256": hashes,
    })
    return target


def _extract_zip_atomically(payload: bytes, target: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for member in archive.infolist():
            path = PurePosixPath(member.filename)
            if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
                raise SecDataError(f"unsafe or nested XBRL zip member: {member.filename!r}")
            if member.is_dir():
                continue
            destination = target / path.name
            with archive.open(member) as source:
                data = source.read()
            _write_bytes_atomic(destination, data)


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _write_json_atomic(path: Path, value: dict) -> None:
    _write_bytes_atomic(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
