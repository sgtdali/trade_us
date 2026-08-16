"""The instrument master: turning what a person types into a stable identity.

A person types NVDA. The ledger stores ``sec:nvda``. The two are not the same
kind of thing and the distance between them is the whole point: a ticker is a
label the market reassigns, an identity is what the position is actually in.

Three levels, because collapsing them costs real money later:

* ``issuer``   -- the company. GOOG and GOOGL share one.
* ``security`` -- a share class. Survives a ticker change untouched.
* ``listing``  -- a security on a venue. Delisting closes this, not the security.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import schemas
from .errors import FundError

DEFAULT_RELATIVE_PATH = Path("config") / "fund" / "instrument-master.json"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


class InstrumentError(FundError):
    """A ticker resolved to nothing, or to more than one security."""


def empty(as_of: str) -> dict[str, Any]:
    return {"schema_version": "1.0.0", "as_of": as_of, "issuers": [], "securities": [], "listings": []}


def slug(text: str) -> str:
    cleaned = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    if not cleaned:
        raise InstrumentError(f"cannot build an identifier from {text!r}")
    return cleaned[:63]


def load(path: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    master_path = path or (root or schemas.repo_root()) / DEFAULT_RELATIVE_PATH
    if not master_path.is_file():
        raise InstrumentError(
            f"instrument master not found: {master_path}\n"
            "Add the first security with: fund instrument add --ticker NVDA --name 'NVIDIA Corporation'"
        )
    document = json.loads(master_path.read_text(encoding="utf-8"))
    schemas.validate(document, schemas.INSTRUMENT_MASTER, root)
    return document


def save(document: dict[str, Any], path: Path | None = None, root: Path | None = None) -> Path:
    schemas.validate(document, schemas.INSTRUMENT_MASTER, root)
    master_path = path or (root or schemas.repo_root()) / DEFAULT_RELATIVE_PATH
    master_path.parent.mkdir(parents=True, exist_ok=True)
    master_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return master_path


def securities(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["security_id"]: entry for entry in document["securities"]}


def resolve(document: dict[str, Any], token: str) -> str:
    """Accept either a security id or a ticker, return a security id."""
    if token.startswith("sec:"):
        if token not in securities(document):
            raise InstrumentError(f"unknown security: {token}")
        return token

    wanted = token.upper()
    matches = {
        listing["security_id"]
        for listing in document["listings"]
        if listing["ticker"] == wanted and listing["status"] == "active"
    }
    if not matches:
        raise InstrumentError(
            f"no active listing for ticker {wanted!r}. "
            f"Add it with: fund instrument add --ticker {wanted} --name '...'"
        )
    if len(matches) > 1:
        raise InstrumentError(
            f"ticker {wanted!r} maps to several securities ({', '.join(sorted(matches))}); "
            "use the security id instead"
        )
    return matches.pop()


def ticker_for(document: dict[str, Any], security_id: str) -> str:
    for listing in document["listings"]:
        if listing["security_id"] == security_id and listing["status"] == "active":
            return listing["ticker"]
    return security_id


def issuer_of(document: dict[str, Any], security_id: str) -> str:
    entry = securities(document).get(security_id)
    if entry is None:
        raise InstrumentError(f"unknown security: {security_id}")
    return entry["issuer_id"]


def add_security(
    document: dict[str, Any],
    *,
    ticker: str,
    legal_name: str,
    issuer_id: str | None = None,
    security_id: str | None = None,
    share_class: str | None = None,
    cik: str | None = None,
    mic: str = "XNAS",
    currency: str = "USD",
) -> tuple[dict[str, Any], str]:
    """Register one security and its listing, deriving ids from the ticker.

    Two share classes of one company are registered by passing the same
    ``--issuer`` twice; nothing infers that relationship from names, because a
    wrong guess would silently merge two companies' exposure limits.
    """
    ticker = ticker.upper()
    issuer = issuer_id or f"iss:{slug(ticker)}"
    security = security_id or f"sec:{slug(ticker)}"
    listing = f"lst:{slug(mic)}-{slug(ticker)}"

    if security in securities(document):
        raise InstrumentError(f"{security} is already registered")
    if any(entry["listing_id"] == listing for entry in document["listings"]):
        raise InstrumentError(f"{listing} is already registered")

    if not any(entry["issuer_id"] == issuer for entry in document["issuers"]):
        issuer_entry: dict[str, Any] = {"issuer_id": issuer, "legal_name": legal_name}
        if cik:
            issuer_entry["cik"] = cik
        document["issuers"].append(issuer_entry)

    security_entry: dict[str, Any] = {
        "security_id": security,
        "issuer_id": issuer,
        "security_type": "common_equity",
        "currency": currency,
    }
    if share_class:
        security_entry["share_class"] = share_class
    document["securities"].append(security_entry)

    document["listings"].append({
        "listing_id": listing,
        "security_id": security,
        "mic": mic.upper(),
        "ticker": ticker,
        "status": "active",
    })
    return document, security


def rename_ticker(document: dict[str, Any], security_id: str, new_ticker: str) -> dict[str, Any]:
    """A ticker change edits the listing in place: no identity changed."""
    found = False
    for listing in document["listings"]:
        if listing["security_id"] == security_id and listing["status"] == "active":
            listing["ticker"] = new_ticker.upper()
            found = True
    if not found:
        raise InstrumentError(f"no active listing for {security_id}")
    return document
