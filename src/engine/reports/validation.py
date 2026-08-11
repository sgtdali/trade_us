"""Structural and content validation for a rendered report."""

from __future__ import annotations

import re

PROHIBITED_PHRASES_TR = [
    "al tavsiyesi", "sat tavsiyesi", "tut tavsiyesi", "alım tavsiyesi", "satım tavsiyesi",
    "hedef fiyat", "değerinin altında", "değerinin üzerinde", "ucuz kalmıştır", "pahalı kalmıştır",
    "satın alınmalı", "satılmalı", "portföye eklenmeli",
]
PROHIBITED_PHRASES_EN = [
    "buy rating", "sell rating", "hold rating", "target price", "undervalued", "overvalued",
    "should be purchased", "should be sold",
]

REQUIRED_SECTION_TITLES = [
    "Yönetici Özeti", "Kullanılan Kaynaklar", "Kapsam ve Kısıtlar", "Temel Riskler",
    "Olumlu Gelişmeler", "Olumsuz Gelişmeler", "Yasal Uyarı",
]


def validate_report(markdown_text: str, ticker: str, period: str, is_aviation: bool) -> list[str]:
    errors: list[str] = []

    if f"# {ticker} {period}" not in markdown_text:
        errors.append(f"Report title does not contain the expected ticker/period header ('# {ticker} {period}').")

    for title in REQUIRED_SECTION_TITLES:
        pattern = r"^#{1,2}\s*\d*\.?\s*" + re.escape(title)
        if not re.search(pattern, markdown_text, re.MULTILINE):
            errors.append(f"Required section heading missing: {title!r}")

    _NEGATION_MARKERS = ("değildir", "içermez", "üretmez", "hesaplanamaz", "yoktur", "dışındadır", "kapsam dışı", "not investment advice", "does not")
    sentences = re.split(r"(?<=[.!?\n])\s+", markdown_text)
    for phrase in PROHIBITED_PHRASES_TR + PROHIBITED_PHRASES_EN:
        for sentence in sentences:
            lowered_sentence = sentence.lower()
            if phrase in lowered_sentence and not any(marker in lowered_sentence for marker in _NEGATION_MARKERS):
                errors.append(f"Prohibited recommendation language found: {phrase!r} in {sentence.strip()!r}")

    lowered = markdown_text.lower()

    if "yatırım tavsiyesi değildir" not in lowered and "not investment advice" not in lowered:
        errors.append("Disclaimer stating the report is not investment advice is missing.")

    aviation_marker = "kapasite ve trafik"
    has_aviation_section = aviation_marker in lowered
    if is_aviation and not has_aviation_section:
        errors.append("Aviation sector module but no aviation-specific report section was rendered.")
    if not is_aviation and has_aviation_section:
        errors.append("Non-aviation company but aviation-specific report section was rendered.")

    return errors
