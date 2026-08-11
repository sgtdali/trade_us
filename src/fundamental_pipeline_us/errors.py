class UsPipelineError(Exception):
    """Base exception for the US adapter boundary."""


class SecRequestError(UsPipelineError):
    """SEC request failed after bounded retries."""


class SecDataError(UsPipelineError):
    """SEC response or filing content violated an expected contract."""


class FactSelectionError(UsPipelineError):
    """A canonical metric could not be selected without ambiguity."""


class CorporateActionUnresolved(UsPipelineError):
    """A corporate action falls between the filed share count and the as-of date.

    The cover-page share count is a point-in-time figure carrying the date of
    the filing that reported it. When a split or a spin-off takes effect after
    that date but before the valuation date, the filed count no longer
    describes the company and market capitalisation cannot be formed from it.

    The two cases are not distinguishable from filed data at the as-of date --
    a true split multiplies the count, a spin-off leaves it untouched, and the
    price feed encodes both as a split factor -- so neither is assumed. NVDA
    priced its post-split 2024-07-31 close against its pre-split 2,460,000,000
    cover-page count and reported a market capitalisation of 288 billion
    against an actual 2,880 billion, which made its P/E 6.76x instead of about
    67x and put it top of the cross-section (found 2026-08-06).
    """
