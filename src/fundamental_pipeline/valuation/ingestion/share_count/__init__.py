"""Point-in-time share-count/corporate-action promotion bridge: an
authored share-count ledger, plus governed share-count and corporate-
action market-source manifests and a promotion policy, deterministically
promoted into T70-compatible ``issued_shares``/``treasury_shares``
observations and a governed corporate-action bundle.

Generic, ticker-free contract and engine
(:mod:`models`, :mod:`ledger`, :mod:`validation`, :mod:`policy`,
:mod:`service`). Any single-company onboarding (its own ledger, manifests,
and decision document) lives entirely outside this package -- see
``data/market-input-ledgers/``, ``data/market-source-manifests/``, and
the repository-relative governance document each such onboarding must
author.

Weighted-average EPS shares are explicitly out of scope here -- only the
spot issued/treasury/outstanding concepts this package promotes.
"""

from __future__ import annotations
