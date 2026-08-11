from datetime import date

import pytest

from adapter.discovery import list_filings, resolve_cik
from adapter.errors import SecDataError


class _Client:
    def __init__(self, responses):
        self.responses = responses

    def get_json(self, url):
        return self.responses[url]


def test_resolve_cik_zero_pads_and_matches_exact_ticker():
    url = "https://www.sec.gov/files/company_tickers.json"
    client = _Client({url: {"0": {"ticker": "KO", "cik_str": 21344}}})
    assert resolve_cik(client, "KO") == "0000021344"


def test_list_filings_applies_point_in_time_cutoff():
    url = "https://data.sec.gov/submissions/CIK0000021344.json"
    recent = {
        "accessionNumber": ["0000000000-26-000001", "0000000000-26-000002", "0000000000-26-000003"],
        "form": ["10-K", "10-Q", "8-K"],
        "filingDate": ["2026-02-20", "2026-04-30", "2026-03-01"],
        "reportDate": ["2025-12-31", "2026-03-31", "2026-02-28"],
        "primaryDocument": ["annual.htm", "quarter.htm", "event.htm"],
    }
    filings = list_filings(_Client({url: {"filings": {"recent": recent}}}), "0000021344", as_of=date(2026, 3, 1))
    assert [item.form for item in filings] == ["10-K"]


def test_mismatched_submission_columns_fail_closed():
    url = "https://data.sec.gov/submissions/CIK0000021344.json"
    recent = {
        "accessionNumber": ["0000000000-26-000001"],
        "form": ["10-K", "10-Q"],
        "filingDate": ["2026-02-20"],
        "reportDate": ["2025-12-31"],
        "primaryDocument": ["annual.htm"],
    }
    with pytest.raises(SecDataError, match="column lengths"):
        list_filings(_Client({url: {"filings": {"recent": recent}}}), "0000021344", as_of=date(2026, 3, 1))
