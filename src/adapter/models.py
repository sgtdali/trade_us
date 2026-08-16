from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class FilingRef:
    cik: str
    accession: str
    form: str
    filing_date: date
    report_date: date
    primary_document: str
    is_amendment: bool = False
    #: SEC "items" for 8-K filings, e.g. ("2.02", "9.01"). Item 2.02 is
    #: "Results of Operations and Financial Condition" -- the earnings release
    #: itself. Without this the typed layer cannot tell an earnings 8-K from any
    #: other 8-K, and an earnings trigger has to fall back on a calendar date,
    #: which is an estimate rather than evidence.
    items: tuple[str, ...] = ()

    @property
    def is_earnings_release(self) -> bool:
        return "2.02" in self.items

    @property
    def accession_compact(self) -> str:
        return self.accession.replace("-", "")

    @property
    def cik_compact(self) -> str:
        return str(int(self.cik))


@dataclass(frozen=True)
class SecFact:
    namespace: str
    concept: str
    value: str
    unit: str | None
    context_id: str
    start_date: date | None
    end_date: date
    dimensions: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    decimals: str | None = None
    is_nil: bool = False

    @property
    def qualified_name(self) -> str:
        return f"{{{self.namespace}}}{self.concept}"

    @property
    def is_instant(self) -> bool:
        return self.start_date is None

    @property
    def duration_days(self) -> int | None:
        if self.start_date is None:
            return None
        return (self.end_date - self.start_date).days + 1
