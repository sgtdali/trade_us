"""forbidden language and exact method reporting validators for valuation reports."""

from __future__ import annotations

import re
from typing import Any

from .semantic_catalog import display_unit_for_method

# Fail-closed Turkish forbidden language patterns (target prices, buy/sell/hold commands, recommendation words)
FORBIDDEN_PATTERNS = [
    re.compile(r"hedef\s+fiyat", re.IGNORECASE),
    re.compile(r"hedef\s+değer", re.IGNORECASE),
    re.compile(r"hedef\s+deger", re.IGNORECASE),
    re.compile(r"tavsiye", re.IGNORECASE),
    re.compile(r"öneri", re.IGNORECASE),
    re.compile(r"oneri", re.IGNORECASE),
    re.compile(r"\b(al|sat|tut)\b", re.IGNORECASE),
]

# Signatures of a broken render (a wrong variable formatted, a None/null that
# slipped through unformatted, or the old "%-" bare-dash placeholder bug).
# `%[-−](?!\d)` deliberately excludes a real negative percentage like
# "%-7,5" -- only a percent sign followed by a dash with no digit after it
# (e.g. "%-)" or "%- ") is a broken placeholder, not a legitimate value.
BROKEN_RENDER_PATTERNS = [
    re.compile(r"\bn/a\b", re.IGNORECASE),
    re.compile(r"\bNone\b"),
    re.compile(r"\bnull\b"),
    re.compile(r"%[-−](?!\d)"),
]


def validate_report_content(report_text: str, current_results: dict[str, Any]) -> list[str]:
    """Validate report content against forbidden language rules and ensure all methods are honestly reported.
    Returns a list of error strings; an empty list indicates validation success.
    """
    errors: list[str] = []

    # 1. Check forbidden language
    for pattern in FORBIDDEN_PATTERNS:
        match = pattern.search(report_text)
        if match:
            errors.append(
                f"Yasaklı dil kullanımı tespit edildi (T75-06): '{match.group()}' (Desen: {pattern.pattern})"
            )

    # 1b. Check for broken-render signatures (wrong variable formatted as a
    # date/id instead of a number, an unformatted None/null, or the old bare
    # "%-" placeholder). Any of these leaking into the report means a
    # formatting helper failed silently instead of raising -- fail closed
    # rather than publish it.
    for pattern in BROKEN_RENDER_PATTERNS:
        match = pattern.search(report_text)
        if match:
            errors.append(
                f"Bozuk render tespit edildi: '{match.group()}' (Desen: {pattern.pattern}) — "
                "bir formatlama fonksiyonu sessizce başarısız olmuş olabilir."
            )

    # 2. Check method reporting: every method in results must be mentioned by ID or family ID
    method_results = current_results.get("method_results", [])
    for method in method_results:
        method_id = method.get("method_id", "")
        family_id = method.get("economic_family_id", "")

        # To ensure the method isn't hidden, its ID or family ID must appear in the report
        if method_id not in report_text and family_id not in report_text:
            errors.append(
                f"Değerleme yöntemi raporda sunulmadı/gizlendi: {method_id} (Family: {family_id})"
            )

        # 3. Every available method must have a display unit in the reporting
        # semantic catalog. A missing entry previously fell back silently to
        # a bare ratio (a 19.5% yield rendered as "0,2"); this must fail the
        # report rather than repeat that silently for a new method.
        canonical = method.get("canonical_value") or {}
        if canonical.get("status") == "available" and display_unit_for_method(method_id) is None:
            errors.append(
                f"method_id {method_id!r} has no entry in "
                "config/valuation/reporting/labels.json (display_units) "
                "(T76 semantic metadata layer) — add one before this method can be reported."
            )

    return errors
