"""Data models and envelope helpers for technical analysis indicators."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


class TechnicalError(Exception):
    """Base exception for technical analysis subsystem."""


@dataclass(frozen=True)
class DailyBar:
    """Immutable daily price bar with exact Decimal fields."""
    trade_date: str
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    adjusted_close: Decimal | None
    volume: Decimal | None


def normalize_decimal(value: Decimal | int | str) -> str:
    """Normalize a domain decimal value to its canonical string form."""
    if isinstance(value, bool):
        raise TechnicalError(f"boolean is not a valid decimal value: {value!r}")
    if isinstance(value, float):
        raise TechnicalError(f"binary float is not a valid decimal input: {value!r}")
    if isinstance(value, int):
        decimal_value = Decimal(value)
    elif isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, str):
        try:
            decimal_value = Decimal(value)
        except InvalidOperation as exc:
            raise TechnicalError(f"invalid decimal string: {value!r}") from exc
    else:
        raise TechnicalError(f"unsupported decimal input type: {type(value).__name__}")

    if not decimal_value.is_finite():
        raise TechnicalError(f"NaN/Infinity is not a valid decimal value: {value!r}")
    if decimal_value.is_zero() and decimal_value.is_signed():
        raise TechnicalError(f"negative zero is not a valid decimal value: {value!r}")

    sign, digits, exponent = decimal_value.as_tuple()
    if not isinstance(exponent, int):
        raise TechnicalError(f"non-finite decimal exponent: {value!r}")

    digits_str = "".join(str(d) for d in digits)
    if exponent >= 0:
        int_part = digits_str + ("0" * exponent)
        frac_part = ""
    else:
        point = len(digits_str) + exponent
        if point <= 0:
            int_part = "0"
            frac_part = ("0" * (-point)) + digits_str
        else:
            int_part = digits_str[:point]
            frac_part = digits_str[point:]

    int_part = int_part.lstrip("0") or "0"
    frac_part = frac_part.rstrip("0")
    text = int_part if not frac_part else f"{int_part}.{frac_part}"

    if sign and text != "0":
        text = "-" + text
    return text


def decimal_envelope_available(value: Decimal | str) -> dict[str, Any]:
    """Build a status='available' envelope for a decimal-valued indicator."""
    val_str = normalize_decimal(value) if isinstance(value, Decimal) else normalize_decimal(str(value))
    return {
        "status": "available",
        "value": val_str,
    }


def decimal_envelope_unavailable(code: str, severity: str = "warning") -> dict[str, Any]:
    """Build a status='unavailable' envelope for a decimal-valued indicator."""
    return {
        "status": "unavailable",
        "reason_codes": [
            {
                "code": code,
                "severity": severity,
            }
        ],
    }


def string_envelope_available(value_str: str) -> dict[str, Any]:
    """Build a status='available' envelope for a string-valued indicator."""
    return {
        "status": "available",
        "value": value_str,
    }


def string_envelope_unavailable(code: str, severity: str = "warning") -> dict[str, Any]:
    """Build a status='unavailable' envelope for a string-valued indicator."""
    return {
        "status": "unavailable",
        "reason_codes": [
            {
                "code": code,
                "severity": severity,
            }
        ],
    }
