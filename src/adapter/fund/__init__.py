"""Portfolio decision journal.

A small system that keeps one person's US equity book honest: it does the
accounting from hand-entered events, tests a contemplated trade against the
capital policy, and runs the research operation that watches for new evidence.

It does not route orders, does not decide, and cannot close a thesis. See
docs/pei-company-lifecycle-tasarim.md for the design and
docs/uygulama-plani.md for what is built so far.

Built alongside the existing PEI orchestrator in adapter.pei_workflow, not on
top of it. Nothing migrates.
"""

from .errors import FundError

__all__ = ["FundError"]
