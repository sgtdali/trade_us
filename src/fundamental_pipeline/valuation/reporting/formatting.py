"""Valuation-specific decimal and locale formatting with final-stage half-even rounding.

This module only formats numbers/status strings it is handed -- it does not
decide *what* unit or status a method/reason_code maps to. That mapping
lives in ``config/valuation/reporting/*.json``, read via
:mod:`fundamental_pipeline.valuation.reporting.semantic_catalog`. See
AGENTS.md's "Değerleme Raporu Sunum Semantiği" section before adding a new
display/label heuristic here.
"""

from __future__ import annotations

import decimal
from decimal import Decimal
from typing import Any

from .semantic_catalog import status_label_for_reason_codes

_VALUATION_UNIT_SUFFIX = {
    "percent": "%",
    "ratio": "",
    "multiple": "x",
    "million_usd": " milyon USD",
    "million_try": " milyon TRY",
    "TRY": " TRY",
    "USD": " USD",
    "shares": " adet",
    "million_units": " milyon",
}


def to_decimal(val: Any) -> Decimal | None:
    """Safely convert any numeric value or string to a Decimal without losing precision."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    try:
        if isinstance(val, float):
            return Decimal(str(val))
        return Decimal(val)
    except (ValueError, decimal.InvalidOperation):
        return None


def fmt_decimal_tr(val: Any, decimals: int = 1) -> str:
    """Format a numeric value as a Turkish-locale decimal string (e.g., 1.234,56).
    Enforces final-stage half-even rounding using Decimal.
    """
    dec = to_decimal(val)
    if dec is None:
        return "n/a"

    # Quantize to specified decimals using half-even rounding
    if decimals > 0:
        q_str = "1." + "0" * decimals
    else:
        q_str = "1"
    rounded = dec.quantize(Decimal(q_str), rounding=decimal.ROUND_HALF_EVEN)

    # Format the magnitude and reapply the sign separately: a value like
    # -0.72 rounds to an integer part of "-0", which `int("-0")` collapses
    # to a plain 0, silently dropping the negative sign for any rounded
    # magnitude below 1.
    is_negative = rounded < 0
    magnitude = -rounded if is_negative else rounded

    s = f"{magnitude:f}"
    if "." in s:
        integer_part, frac_part = s.split(".")
    else:
        integer_part, frac_part = s, ""

    try:
        int_val = int(integer_part)
        formatted_int = f"{int_val:,}".replace(",", ".")
    except ValueError:
        formatted_int = integer_part

    result = f"{formatted_int},{frac_part}" if decimals > 0 else formatted_int
    return f"-{result}" if is_negative else result


def fmt_valuation_amount(amount_dict: dict[str, Any] | None, decimals: int | None = None) -> str:
    """Format a valuation amount dictionary (e.g., as found in ledger or EV components).
    Handles unavailable/status states gracefully.
    """
    if amount_dict is None:
        return "veri yok"

    status = amount_dict.get("status", "available")
    if status == "unavailable":
        reasons = amount_dict.get("reason_codes", [])
        if reasons:
            return status_label_for_reason_codes(reasons)
        return "veri yok"

    val = amount_dict.get("value")
    if val is None:
        return "veri yok"

    currency = amount_dict.get("currency", "")
    places = decimals
    if places is None:
        dec_val = to_decimal(val)
        if dec_val is not None and dec_val != 0 and abs(dec_val) < 1:
            places = 4
        else:
            places = 1
    formatted_number = fmt_decimal_tr(val, places)

    if currency:
        suffix = _VALUATION_UNIT_SUFFIX.get(currency, f" {currency}")
        return f"{formatted_number}{suffix}"
    return formatted_number


def fmt_valuation_metric(metric: dict[str, Any] | None, decimals: int | None = None, *, pre_scaled_percent: bool = False) -> str:
    """Format a valuation metric value based on its unit and semantics.

    Args:
        pre_scaled_percent: When True, percent values are assumed to already
            be in percentage form (e.g. -7.5 for -7.5%). When False (default),
            percent values are decimal fractions multiplied by 100
            (e.g. 0.154 → 15.4%).
    """
    if metric is None:
        return "veri yok"

    status = metric.get("status", "available")
    if status == "unavailable":
        reasons = metric.get("reason_codes", [])
        if reasons:
            return status_label_for_reason_codes(reasons)
        return "veri yok"

    val = metric.get("value")
    if val is None:
        return "veri yok"

    unit = metric.get("unit", "")
    places = decimals if decimals is not None else (2 if unit in ("percent", "ratio") else 1)

    dec_val = to_decimal(val)
    if dec_val is None:
        return "veri yok"

    if unit == "percent" and not pre_scaled_percent:
        dec_val = dec_val * Decimal("100")

    formatted_number = fmt_decimal_tr(dec_val, places)

    if unit == "percent":
        if formatted_number.startswith("-"):
            return f"-%{formatted_number[1:]}"
        elif formatted_number.startswith("+"):
            return f"+%{formatted_number[1:]}"
        return f"%{formatted_number}"
    if unit == "multiple":
        return f"{formatted_number}x"

    suffix = _VALUATION_UNIT_SUFFIX.get(unit, f" {unit}")
    return f"{formatted_number}{suffix}"
