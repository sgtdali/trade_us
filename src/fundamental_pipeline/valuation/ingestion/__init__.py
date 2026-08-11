"""Provider-neutral market-data *ingestion* namespace.

Deliberately separate from :mod:`fundamental_pipeline.valuation.market`,
which remains the pure, network-free T70 resolver boundary. Nothing under
``fundamental_pipeline.valuation.market.*`` may import from this package,
and nothing here writes a T70 ``market_snapshot`` artifact -- bridging an
approved ingested EOD close into a T70 observation is a separate, later,
explicitly authorized task.
"""

from __future__ import annotations
