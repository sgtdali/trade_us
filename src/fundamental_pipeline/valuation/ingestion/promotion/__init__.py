"""EOD-close promotion bridge: a validated EOD ingestion bundle, plus a
governed market-source manifest and a promotion policy, deterministically
promoted into a T70-compatible price observation bundle.

Generic, ticker-free contract and engine
(:mod:`models`, :mod:`validation`, :mod:`policy`, :mod:`service`).
Any single-company temporary onboarding (its own manifest, provider
config, and decision document) lives entirely outside this package -- see
``data/market-source-manifests/``, ``config/market-data/providers/``, and
the repository-relative ``docs/temporary-*-internal-valuation-exception.md``
decision document each such onboarding must author.
"""

from __future__ import annotations
