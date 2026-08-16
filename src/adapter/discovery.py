from __future__ import annotations

from datetime import date

from .errors import SecDataError
from .models import FilingRef
from .paths import validate_cik, validate_ticker
from .sec_client import SecClient


def resolve_cik(client: SecClient, ticker: str) -> str:
    ticker = validate_ticker(ticker)
    payload = client.get_json("https://www.sec.gov/files/company_tickers.json")
    matches = [row for row in payload.values() if isinstance(row, dict) and row.get("ticker", "").upper() == ticker]
    if len(matches) != 1:
        raise SecDataError(f"expected one SEC ticker mapping for {ticker}, found {len(matches)}")
    return f"{int(matches[0]['cik_str']):010d}"


def list_filings(
    client: SecClient,
    cik: str,
    *,
    as_of: date,
    forms: tuple[str, ...] = ("10-K", "10-Q", "10-K/A", "10-Q/A"),
) -> tuple[FilingRef, ...]:
    cik = validate_cik(cik)
    payload = client.get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
    recent = payload.get("filings", {}).get("recent")
    if not isinstance(recent, dict) or not recent.get("accessionNumber"):
        raise SecDataError(f"SEC submissions response has no recent filings for CIK {cik}")

    pages = [recent]
    # The submissions endpoint caps "recent" at roughly a thousand entries and
    # spills everything older into filings.files[], each a separate JSON with
    # the same column layout. Reading only "recent" therefore truncates history
    # by FILING COUNT, not by date, so a company that files often loses its
    # older annual reports first: CHD's 10-K filings before 2022 sit past the
    # cap behind its 8-K and Form 4 traffic, and every historical quarter
    # failed with "eligible 10-Q and 10-K are both required" while quieter
    # filers in the same universe resolved fine (found 2026-08-05).
    for entry in payload.get("filings", {}).get("files", []) or []:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not name:
            continue
        page = client.get_json(f"https://data.sec.gov/submissions/{name}")
        if isinstance(page, dict) and page.get("accessionNumber"):
            pages.append(page)

    result: list[FilingRef] = []
    for page in pages:
        lengths = {len(value) for value in page.values() if isinstance(value, list)}
        if len(lengths) != 1:
            raise SecDataError(f"SEC submissions column lengths disagree for CIK {cik}")
        for index, accession in enumerate(page["accessionNumber"]):
            form = page["form"][index]
            filing_date = date.fromisoformat(page["filingDate"][index])
            report_date_raw = page["reportDate"][index]
            if form not in forms or filing_date > as_of:
                continue
            if not report_date_raw:
                # Event filings (8-K and friends) often carry no period of
                # report; falling back to the filing date keeps them usable as
                # evidence instead of dropping them, which is what an earnings
                # trigger needs. Periodic forms keep the old behaviour exactly:
                # a 10-Q with no period would misalign every comparison built
                # on it, so it is still skipped.
                if form.startswith(("10-K", "10-Q")):
                    continue
                report_date_raw = page["filingDate"][index]
            raw_items = page.get("items", [])
            items = tuple(
                part.strip()
                for part in str(raw_items[index] if index < len(raw_items) else "").split(",")
                if part.strip()
            )
            result.append(FilingRef(
                cik=cik,
                accession=accession,
                form=form,
                filing_date=filing_date,
                report_date=date.fromisoformat(report_date_raw),
                primary_document=page["primaryDocument"][index],
                is_amendment=form.endswith("/A"),
                items=items,
            ))
    return tuple(sorted(result, key=lambda item: (item.filing_date, item.accession), reverse=True))
