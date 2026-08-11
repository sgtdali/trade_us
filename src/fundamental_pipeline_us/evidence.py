"""Market stats and cutoff-safe earnings-release evidence helpers.

Extracted from fundamentaltrading's idea_replay.py: only the three helpers
live_pack.py actually calls (_read_json, _market_stats,
_latest_release_evidence) plus their own dependency closure. The idea-
generation replay machinery (universe pack building, prompt writing, output
validation) was left behind with the rest of the backtest/replay tooling.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from statistics import stdev
from typing import Any

from .point_in_time import MonthPlan, historical_technical_input
from .errors import UsPipelineError

_RELEASE_SIGNAL = re.compile(
    r"(?i)\b(guidance|outlook|expects?|anticipates?|forecasts?|projects?|sees|"
    r"raises?|lowers?|reaffirms?|full[- ]year|headwind|tailwind|demand|backlog|"
    r"orders?|bookings?|pipeline|margin|organic|volume|pricing|capacity|launch)\b"
)
_OPERATING_SIGNAL = re.compile(
    r"(?i)\b(revenue|sales|growth|declin|improv|accelerat|decelerat|segment|"
    r"customer|market share|cash flow|inventory|cost|productivity|restructur)\b"
)
_REVISION_SIGNAL = re.compile(r"(?i)\b(raise[sd]?|lower(?:s|ed)?|reaffirm(?:s|ed)?|narrows?|widens?)\b")
_BOILERPLATE = re.compile(
    r"(?i)(forward-looking statements|risks and uncertainties include|assumes no obligation|"
    r"press contact|investor relations contact|private securities litigation reform act|"
    r"commission file number|pursuant to the requirements)"
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise UsPipelineError(f"required file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _market_stats(run_root: Path, ticker: str, plan: MonthPlan) -> dict[str, float | None]:
    technical = historical_technical_input(run_root=run_root, ticker=ticker, plan=plan)
    bars = technical["daily_bars"]
    closes = [float(bar.close) for bar in bars]

    def trailing_return(sessions: int) -> float | None:
        if len(closes) <= sessions or closes[-sessions - 1] == 0:
            return None
        return round((closes[-1] / closes[-sessions - 1] - 1) * 100, 2)

    daily_returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]
    recent_returns = daily_returns[-252:]
    volatility = round(stdev(recent_returns) * math.sqrt(252) * 100, 2) if len(recent_returns) >= 2 else None
    window = closes[-253:]
    peak = window[0]
    max_drawdown = 0.0
    for value in window:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1)
    avg_dollar_volume = None
    if bars:
        recent = bars[-20:]
        avg_dollar_volume = round(sum(float(bar.close * bar.volume) for bar in recent) / len(recent) / 1_000_000, 2)
    return {
        "return_1m_pct": trailing_return(21),
        "return_3m_pct": trailing_return(63),
        "return_6m_pct": trailing_return(126),
        "return_12m_pct": trailing_return(252),
        "annualized_volatility_pct": volatility,
        "max_drawdown_12m_pct": round(max_drawdown * 100, 2),
        "avg_dollar_volume_20d_usd_m": avg_dollar_volume,
    }


def _release_sentences(text: str, *, limit: int = 10, char_budget: int = 3200) -> list[str]:
    normalized = text.replace("Â", " ")
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\"(])", normalized)
    ranked: list[tuple[int, int, str]] = []
    seen = set()
    for index, sentence in enumerate(sentences):
        sentence = re.sub(r"\s+", " ", sentence).strip()
        key = re.sub(r"\W+", " ", sentence.lower())[:180]
        if not 45 <= len(sentence) <= 650 or key in seen or _BOILERPLATE.search(sentence):
            continue
        score = 0
        score += 5 if _REVISION_SIGNAL.search(sentence) else 0
        score += 4 if _RELEASE_SIGNAL.search(sentence) else 0
        score += 2 if _OPERATING_SIGNAL.search(sentence) else 0
        score += 2 if re.search(r"(?i)\b(said|chief executive|ceo|cfo)\b", sentence) else 0
        score += 1 if re.search(r"[$%]\s?\d|\d(?:\.\d+)?%", sentence) else 0
        if score < 3:
            continue
        seen.add(key)
        ranked.append((score, index, sentence))
    selected = sorted(sorted(ranked, key=lambda item: (-item[0], item[1]))[:limit], key=lambda item: item[1])
    output, used = [], 0
    for _score, _index, sentence in selected:
        if used + len(sentence) > char_budget:
            continue
        output.append(sentence)
        used += len(sentence)
    return output


def _guidance_for_date(guidance_root: Path, ticker: str, filing_date: str, release_text: str) -> dict[str, Any]:
    path = guidance_root / "_answers" / f"{ticker}.txt"
    if not path.is_file():
        return {"status": "unavailable", "reason": "no historical guidance extraction"}
    values: list[tuple[float, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3 or parts[0] != filing_date:
            continue
        try:
            low = float(parts[1].replace("\\", "").replace("$", ""))
            high = float(parts[2].replace("\\", "").replace("$", ""))
        except ValueError:
            continue
        values.append((low, high))
    unique = sorted(set(values))
    if len(unique) != 1:
        # Defterin sozlesmesi dar: YALNIZ tam yil DUZELTILMIS (non-GAAP)
        # seyreltilmis EPS. Sirket gelirle, marjla, yuzdeyle ya da GAAP
        # bazinda yonlendirdiginde satir NONE olur -- rehber yok diye degil,
        # BU BAZDA yok diye.
        reason = ("conflicting extractions" if unique else
                  "no full-year adjusted (non-GAAP) diluted EPS guidance in this "
                  "release. That is the only basis this ledger carries. The "
                  "company may still guide -- on revenue, margins, a percentage, "
                  "or on a GAAP basis -- and such a figure is deliberately not "
                  "carried here, because mixing bases would make the field "
                  "incomparable across companies. Read the release itself if the "
                  "expectation bar matters for this name.")
        return {"status": "unavailable", "reason": reason}
    low, high = unique[0]
    tokens = (f"{low:.2f}", f"{high:.2f}")
    verified = all(token in release_text for token in tokens)
    if not verified:
        return {"status": "unavailable", "reason": "extracted range not found verbatim in selected release"}
    return {
        "status": "available", "metric": "company-defined adjusted diluted EPS guidance",
        "low": low, "high": high, "midpoint": round((low + high) / 2, 4),
        "source_verification": "both range endpoints found verbatim in selected release",
    }


def _latest_release_evidence(guidance_root: Path, ticker: str, cutoff_date: str) -> dict[str, Any]:
    text_root = guidance_root / "_text" / ticker
    candidates = []
    for path in text_root.glob(f"{ticker}_*.txt"):
        match = re.search(r"_(\d{4}-\d{2}-\d{2})\.txt$", path.name)
        if match and match.group(1) <= cutoff_date:
            candidates.append((match.group(1), path))
    if not candidates:
        return {"status": "unavailable", "reason": "no cutoff-safe earnings release text"}
    filing_date, text_path = max(candidates)
    metadata = []
    for path in (guidance_root / ticker).glob("*/filing.json"):
        payload = _read_json(path)
        if payload.get("filing_date") == filing_date and "2.02" in str(payload.get("items") or ""):
            metadata.append(payload)
    if not metadata:
        return {"status": "unavailable", "reason": "release text has no matching Item 2.02 metadata"}
    filing = sorted(metadata, key=lambda item: item["accession"])[-1]
    release_text = text_path.read_text(encoding="utf-8", errors="replace")
    excerpts = _release_sentences(release_text)
    source_id = f"sec-{filing['accession']}"
    return {
        "status": "available", "filing_date": filing_date,
        "accession": filing["accession"], "source_id": source_id,
        "text_sha256": hashlib.sha256(release_text.encode("utf-8")).hexdigest(),
        "guidance": _guidance_for_date(guidance_root, ticker, filing_date, release_text),
        "revision_language_supported": any(_REVISION_SIGNAL.search(item) for item in excerpts),
        "excerpts": excerpts,
    }
