"""The AnalysisContext: everything a pipeline stage needs, loaded once and
passed explicitly. No pipeline stage reads a file directly; they all read
from this context, so every stage can be pointed at fixture data instead of
the production repository tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError
from .io import read_json
from .modules.company_types.base import CompanyTypeModule
from .modules.sectors.base import SectorModule
from .paths import repo_path, safe_ticker
from .periods import Period, parse_period
from .registry.companies import load_company
from .registry.company_types import assert_implemented, get_company_type_module
from .registry.sector_modules import get_sector_module_module


@dataclass
class AnalysisContext:
    ticker: str
    period_id: str
    period: Period
    company_config: dict
    company_type_module: CompanyTypeModule
    sector_module: SectorModule
    source_manifest: dict | None
    direct_financials: dict | None
    historical_series: dict | None
    financial_operational_data: dict | None
    operational_data: dict | None
    authored_risks: dict | None
    data_root: Path | None = None
    config_root: Path | None = None

    @property
    def company_type(self) -> str:
        return self.company_type_module.module_id

    @property
    def sector_module_id(self) -> str:
        return self.sector_module.module_id


def _maybe_read(*parts: str, root: Path | None = None):
    p = repo_path(*parts, root=root)
    return read_json(p) if p.exists() else None


def build_context(
    ticker: str,
    period_id: str,
    allow_inactive: bool = False,
    data_root: Path | None = None,
    config_root: Path | None = None,
) -> AnalysisContext:
    """Load an :class:`AnalysisContext`.

    Company-specific data (config/companies, data/source-manifests,
    data/financial, data/financial-operational, data/financial-series,
    data/operational, data/risks) is read from ``data_root`` when given,
    defaulting to the real repository root. Shared pipeline configuration
    (``config/pipeline``, ``config/taxonomies``) always resolves against the
    real repository, since it is versioned infrastructure the fixture is
    meant to exercise for real, not something a fixture should shadow.

    ``config_root`` overrides where ``config/companies`` specifically is
    read from when it needs to differ from ``data_root`` (e.g. a run root
    that holds its own generated data but has no reason to keep a private
    copy of the shared company registry). Defaults to ``data_root``.
    """
    ticker = safe_ticker(ticker)
    company_config = load_company(
        ticker, allow_inactive=allow_inactive, data_root=data_root, config_root=config_root,
    )
    company_type_id = company_config["pipeline"]["company_type"]
    sector_module_id = company_config["pipeline"]["sector_module"]
    assert_implemented(company_type_id)
    company_type_module = get_company_type_module(company_type_id)
    sector_module = get_sector_module_module(sector_module_id)
    if company_type_module.module_id not in sector_module.compatible_company_types:
        raise ConfigError(
            f"sector_module {sector_module_id!r} is not compatible with company_type {company_type_id!r}"
        )

    period = parse_period(period_id)

    return AnalysisContext(
        ticker=ticker,
        period_id=period_id,
        period=period,
        company_config=company_config,
        company_type_module=company_type_module,
        sector_module=sector_module,
        source_manifest=_maybe_read("data", "source-manifests", f"{ticker}.json", root=data_root),
        direct_financials=_maybe_read("data", "financial", ticker, f"{period_id}.json", root=data_root),
        historical_series=_first_existing_series(ticker, data_root),
        financial_operational_data=_maybe_read("data", "financial-operational", ticker, f"{period_id}.json", root=data_root),
        operational_data=_maybe_read("data", "operational", ticker, f"{period_id}.json", root=data_root),
        authored_risks=_maybe_read("data", "risks", ticker, f"{period_id}.json", root=data_root),
        data_root=data_root,
        config_root=config_root,
    )


def _first_existing_series(ticker: str, data_root: Path | None):
    series_dir = repo_path("data", "financial-series", ticker, root=data_root)
    if not series_dir.exists():
        return None
    files = sorted(series_dir.glob("*.json"))
    if not files:
        return None
    # A ticker may in principle have more than one series file (e.g. split
    # by currency); production data today has exactly one, so load it.
    return read_json(files[0])
