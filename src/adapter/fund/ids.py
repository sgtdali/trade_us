"""Record identifiers.

UUIDv7, because identifiers that sort by creation time make an append-only
ledger far easier to read, page and debug than random v4 ones. Python's stdlib
grows ``uuid.uuid7`` in 3.14; this runs on 3.11+, so it is built here.

Every user-facing id carries a three-letter prefix. It costs four characters
and buys the guarantee that a decision id can never be silently accepted where
an assessment id was meant -- at a CLI where these get copied and pasted, that
is worth more than the brevity.
"""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Final

ACCOUNT_EVENT: Final = "EVT"
ASSESSMENT: Final = "ASM"
DECISION: Final = "DEC"
THESIS: Final = "THS"
MONITORING_CHECK: Final = "CHK"
RESEARCH_JOB: Final = "JOB"

PREFIXES: Final = frozenset({ACCOUNT_EVENT, ASSESSMENT, DECISION, THESIS, MONITORING_CHECK, RESEARCH_JOB})

_UUID7_RE: Final = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

_lock = threading.Lock()
_last_ms = -1
_counter = 0


def _next_timestamp_and_counter() -> tuple[int, int]:
    """Milliseconds since the epoch plus a within-millisecond counter.

    Two ids minted in the same millisecond must still sort in creation order,
    so the 12 ``rand_a`` bits hold a counter rather than noise. It reseeds
    randomly at each new millisecond so the sequence stays unguessable.
    """
    global _last_ms, _counter
    with _lock:
        now_ms = time.time_ns() // 1_000_000
        if now_ms == _last_ms:
            _counter += 1
            if _counter > 0xFFF:
                # More than 4096 ids in one millisecond: wait for the clock.
                while now_ms <= _last_ms:
                    now_ms = time.time_ns() // 1_000_000
                _last_ms = now_ms
                _counter = int.from_bytes(os.urandom(2), "big") & 0x0FF
        else:
            if now_ms < _last_ms:
                # Clock stepped backwards; never emit a decreasing timestamp.
                now_ms = _last_ms
                _counter += 1
            else:
                _last_ms = now_ms
                _counter = int.from_bytes(os.urandom(2), "big") & 0x0FF
        return now_ms, _counter & 0xFFF


def uuid7() -> str:
    timestamp_ms, counter = _next_timestamp_and_counter()
    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)

    time_hex = f"{timestamp_ms & ((1 << 48) - 1):012x}"
    ver_and_rand_a = 0x7000 | counter
    variant_and_rand_b = (0b10 << 62) | rand_b

    return (
        f"{time_hex[:8]}-{time_hex[8:12]}-{ver_and_rand_a:04x}-"
        f"{(variant_and_rand_b >> 48) & 0xFFFF:04x}-"
        f"{variant_and_rand_b & 0xFFFFFFFFFFFF:012x}"
    )


def new_id(prefix: str) -> str:
    if prefix not in PREFIXES:
        raise ValueError(f"unknown id prefix: {prefix!r}")
    return f"{prefix}-{uuid7()}"


def is_valid(identifier: str, prefix: str | None = None) -> bool:
    head, _, tail = identifier.partition("-")
    if head not in PREFIXES or (prefix is not None and head != prefix):
        return False
    return bool(_UUID7_RE.match(tail))


def prefix_of(identifier: str) -> str:
    head = identifier.partition("-")[0]
    if head not in PREFIXES:
        raise ValueError(f"not a fund identifier: {identifier!r}")
    return head
