"""Valuation-only canonical JSON byte writer and Decimal normalization.

This is a dedicated writer for the valuation namespace. It is deliberately
separate from, and must never replace or be reused by,
:func:`fundamental_pipeline.generation.canonical_json`, which remains the
protected pretty-printed, insertion-order fundamental serializer.

Byte contract (see docs/valuation-t70-03-canonical-writer-identity-reference-specification.md):

1. UTF-8, no BOM.
2. Unicode strings normalized to NFC (keys and values).
3. Object keys normalized before ordering.
4. Object keys ordered by Unicode code point.
5. Duplicate keys after NFC normalization are errors.
6. Arrays preserve semantic order (never recursively sorted).
7. No insignificant whitespace; separators are ``,`` and ``:``.
8. Exactly one trailing LF; no CRLF.
9. Lowercase JSON ``true``/``false``/``null``.
10. Domain decimals are canonical strings, never binary floats.
11. NaN, infinity, and negative zero are rejected.
12. No ambient Decimal context may change the output.

Only JSON-native types (``dict``, ``list``, ``str``, ``bool``, ``int``,
``None``) are accepted by :func:`canonical_bytes`. Domain decimal values
must already have been converted to canonical strings via
:func:`normalize_decimal` before being placed into the structure -- this
function never silently coerces a ``float`` or ``Decimal`` for the caller.
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from .errors import CanonicalizationError

_JSON_SCALAR_TYPES = (str, bool, int, type(None))


def _canonicalize(value: Any, *, _path: str = "$") -> Any:
    if isinstance(value, bool):
        return value
    if value is None:
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise CanonicalizationError(f"{_path}: binary float is not a valid canonical value: {value!r}")
    if isinstance(value, Decimal):
        raise CanonicalizationError(
            f"{_path}: raw Decimal is not a valid canonical value; call normalize_decimal() first"
        )
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise CanonicalizationError(f"{_path}: object key must be a string, got {type(raw_key).__name__}")
            key = unicodedata.normalize("NFC", raw_key)
            if key in normalized:
                raise CanonicalizationError(f"{_path}: duplicate object key after NFC normalization: {key!r}")
            normalized[key] = _canonicalize(item, _path=f"{_path}.{key}")
        return dict(sorted(normalized.items(), key=lambda kv: kv[0]))
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item, _path=f"{_path}[{i}]") for i, item in enumerate(value)]
    raise CanonicalizationError(f"{_path}: unsupported type for canonicalization: {type(value).__name__}")


def canonical_text(value: Any) -> str:
    """Render ``value`` (already restricted to JSON-native types, with
    domain decimals pre-normalized to strings) as canonical JSON text
    followed by exactly one trailing LF. Never mutates ``value``."""
    canonicalized = _canonicalize(value)
    body = json.dumps(canonicalized, ensure_ascii=False, sort_keys=False, separators=(",", ":"))
    return body + "\n"


def canonical_bytes(value: Any) -> bytes:
    """UTF-8-encode :func:`canonical_text`."""
    return canonical_text(value).encode("utf-8")


def normalize_decimal(value: Decimal | int | str) -> str:
    """Normalize a domain decimal value to its canonical string form.

    Accepts a :class:`decimal.Decimal`, an ``int``, or a decimal-looking
    string (which may use exponent notation, leading zeros, or unnecessary
    trailing zeros on input). Never accepts ``float`` -- a binary float
    input is always a :class:`CanonicalizationError`, never a silent
    best-effort conversion. Rejects NaN, +/-Infinity, and negative zero.
    """
    if isinstance(value, bool):
        raise CanonicalizationError(f"boolean is not a valid decimal value: {value!r}")
    if isinstance(value, float):
        raise CanonicalizationError(f"binary float is not a valid decimal input: {value!r}")
    if isinstance(value, int):
        decimal_value = Decimal(value)
    elif isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, str):
        try:
            decimal_value = Decimal(value)
        except InvalidOperation as exc:
            raise CanonicalizationError(f"invalid decimal string: {value!r}") from exc
    else:
        raise CanonicalizationError(f"unsupported decimal input type: {type(value).__name__}")

    if not decimal_value.is_finite():
        raise CanonicalizationError(f"NaN/Infinity is not a valid decimal value: {value!r}")
    if decimal_value.is_zero() and decimal_value.is_signed():
        raise CanonicalizationError(f"negative zero is not a valid decimal value: {value!r}")

    sign, digits, exponent = decimal_value.as_tuple()
    if not isinstance(exponent, int):
        # as_tuple() exponent can be 'n'/'N'/'F' for special values; already
        # excluded by is_finite() above, but guard defensively.
        raise CanonicalizationError(f"non-finite decimal exponent: {value!r}")

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
