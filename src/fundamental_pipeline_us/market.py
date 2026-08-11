from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fundamental_pipeline.io import read_json, write_json_atomic
from fundamental_pipeline.valuation.catalogs import CatalogRegistry
from fundamental_pipeline.valuation.ingestion.eod.models import EndOfDayFetchRequest
from fundamental_pipeline.valuation.ingestion.eod.providers.yfinance_provider import YFinanceProvider
from fundamental_pipeline.valuation.market.service import generate_market_snapshot
from fundamental_pipeline.valuation.paths import market_snapshot_relative_path

from .errors import CorporateActionUnresolved, FactSelectionError, UsPipelineError
from .models import SecFact


def generate_us_market_snapshot(
    *, workspace: Path, ticker: str, exchange: str, as_of_date: str,
    cutoff_instant: str, accession: str, facts: tuple[SecFact, ...],
    catalog_registry: CatalogRegistry, context_projection: dict[str, Any],
    historical_observation: dict[str, str] | None = None,
    filing_available_at: str | None = None,
) -> Path:
    as_of = date.fromisoformat(as_of_date)
    direct_shares = select_direct_outstanding_shares(facts, as_of=as_of)
    _reject_intervening_corporate_action(
        historical_observation, ticker=ticker, share_date=direct_shares.end_date, as_of=as_of)
    validated_historical = (
        _validate_historical_observation(
            historical_observation, ticker=ticker, as_of=as_of,
            cutoff_instant=cutoff_instant,
        )
        if historical_observation is not None else None
    )
    input_dir = workspace / "data" / "market-inputs" / ticker / as_of_date
    price_manifest_path = input_dir / "yfinance-manifest.json"
    share_manifest_path = input_dir / "sec-share-manifest.json"
    observations_path = input_dir / "observations.json"
    if price_manifest_path.exists() and share_manifest_path.exists() and observations_path.exists():
        existing = read_json(observations_path)
        share_records = [
            item for item in existing.get("observations", [])
            if item.get("instrument_or_pair", "").endswith(":spot_basic_shares_outstanding")
        ]
        price_records = [
            item for item in existing.get("observations", [])
            if item.get("observation_type") == "price"
        ]
        historical_input_matches = (
            validated_historical is None
            or (
                len(price_records) == 1
                and price_records[0].get("value") == validated_historical[1]
                and price_records[0].get("available_at") == validated_historical[2]
                and price_records[0].get("source_record_ref") == validated_historical[3]
            )
        )
        if (
            len(share_records) == 1
            and share_records[0].get("value") == direct_shares.value
            and accession in str(share_records[0].get("source_record_ref", ""))
            and historical_input_matches
        ):
            return _resolve_snapshot_from_inputs(
                workspace=workspace, ticker=ticker, as_of_date=as_of_date,
                cutoff_instant=cutoff_instant, context_projection=context_projection,
                catalog_registry=catalog_registry, price_manifest_path=price_manifest_path,
                share_manifest_path=share_manifest_path, observations_path=observations_path,
            )

    if historical_observation is None:
        price_row = _fetch_latest_close(ticker, as_of)
        retrieved_at = _utc_now()
        if retrieved_at > cutoff_instant:
            raise UsPipelineError("market data retrieval occurred after cutoff_instant")
        price_trade_date = price_row.trade_date
        price_value = price_row.close.value
        price_available_at = retrieved_at
        source_record_ref = f"yfinance:{ticker}:{price_trade_date}:close"
    else:
        price_trade_date, price_value, price_available_at, source_record_ref = validated_historical
        retrieved_at = historical_observation["ledger_frozen_at"]

    share_available_at = filing_available_at or retrieved_at
    if share_available_at > cutoff_instant:
        raise UsPipelineError("SEC share observation was not available at cutoff_instant")

    price_manifest = _manifest(
        ticker=ticker, exchange=exchange, manifest_id=f"{ticker.lower()}-yfinance-eod-v1",
        authority_class="secondary_reference", provider_id="yfinance", dataset_kind="price",
        dataset_id=f"{ticker.lower()}-yfinance-daily-close", evidence_ref="https://finance.yahoo.com/",
        effective_from=price_trade_date,
    )
    share_manifest = _manifest(
        ticker=ticker, exchange=exchange, manifest_id=f"{ticker.lower()}-sec-shares-v1",
        authority_class="issuer_official", provider_id="sec-edgar", dataset_kind="share_count",
        dataset_id=f"{ticker.lower()}-sec-reported-shares", evidence_ref="https://www.sec.gov/edgar/",
        effective_from=direct_shares.end_date.isoformat(),
    )
    price_effective = f"{price_trade_date}T20:00:00Z"
    observations = {
        "observations": [
            {
                "observation_id": f"{ticker.lower()}-close-{price_trade_date}",
                "observation_type": "price", "instrument_or_pair": ticker,
                "value": price_value, "unit": "USD", "currency": "USD",
                "price_mode": "official_close", "effective_at": price_effective,
                "published_at": price_available_at, "available_at": price_available_at,
                "source_manifest_id": price_manifest["manifest_id"],
                "source_record_ref": source_record_ref,
                "revision_status": "unknown", "ingested_at": retrieved_at,
            },
            {
                "observation_id": f"{ticker.lower()}-sec-outstanding-{accession}",
                "observation_type": "share_count",
                "instrument_or_pair": f"{ticker}:spot_basic_shares_outstanding",
                "value": direct_shares.value, "unit": "shares",
                "effective_at": f"{direct_shares.end_date.isoformat()}T00:00:00Z",
                "published_at": share_available_at, "available_at": share_available_at,
                "source_manifest_id": share_manifest["manifest_id"],
                "source_record_ref": f"sec:{accession}:{direct_shares.qualified_name}#{direct_shares.context_id}",
                "revision_status": "original", "ingested_at": retrieved_at,
            },
        ]
    }
    write_json_atomic(price_manifest_path, price_manifest)
    write_json_atomic(share_manifest_path, share_manifest)
    write_json_atomic(observations_path, observations)

    return _resolve_snapshot_from_inputs(
        workspace=workspace, ticker=ticker, as_of_date=as_of_date,
        cutoff_instant=cutoff_instant, context_projection=context_projection,
        catalog_registry=catalog_registry, price_manifest_path=price_manifest_path,
        share_manifest_path=share_manifest_path, observations_path=observations_path,
    )


def _resolve_snapshot_from_inputs(
    *, workspace: Path, ticker: str, as_of_date: str, cutoff_instant: str,
    context_projection: dict[str, Any], catalog_registry: CatalogRegistry,
    price_manifest_path: Path, share_manifest_path: Path, observations_path: Path,
) -> Path:
    result = generate_market_snapshot(
        manifest_path=price_manifest_path, observations_path=observations_path,
        ticker=ticker, as_of_date=as_of_date, cutoff_instant=cutoff_instant,
        context_projection=context_projection, catalog_registry=catalog_registry,
        output_dir=workspace, additional_manifest_paths=(share_manifest_path,),
    )
    if not result.ok or result.snapshot is None:
        detail = "; ".join(f"{finding.rule_id}: {finding.message}" for finding in result.findings)
        raise UsPipelineError(f"market snapshot generation failed: {detail}")
    return workspace / market_snapshot_relative_path(ticker, as_of_date)


def select_direct_outstanding_shares(facts: tuple[SecFact, ...], *, as_of: date) -> SecFact:
    candidates = [
        fact for fact in facts
        if fact.concept == "EntityCommonStockSharesOutstanding"
        and fact.namespace.startswith("http://xbrl.sec.gov/dei/")
        and not fact.dimensions and not fact.is_nil and fact.unit == "shares"
        and fact.is_instant and fact.end_date <= as_of
    ]
    if not candidates:
        return _combine_common_stock_classes(facts, as_of=as_of)
    latest_date = max(fact.end_date for fact in candidates)
    latest = [fact for fact in candidates if fact.end_date == latest_date]
    values = {fact.value for fact in latest}
    if len(values) != 1:
        raise FactSelectionError(f"conflicting direct outstanding-share facts at {latest_date}: {sorted(values)}")
    selected = sorted(latest, key=lambda fact: fact.context_id)[0]
    try:
        share_count = Decimal(selected.value)
    except InvalidOperation as exc:
        raise FactSelectionError("SEC direct outstanding-share fact must be numeric") from exc
    if share_count <= 0 or share_count != share_count.to_integral_value():
        raise FactSelectionError("SEC direct outstanding-share fact must be positive")
    return selected


#: Kapak sayfasi hisse adedinin sinif bazinda bildirildigi eksenler.
_CLASS_OF_STOCK_AXES = ("StatementClassOfStockAxis", "ClassOfStockAxis")


def _class_member(dimensions: tuple[tuple[str, str], ...]) -> str | None:
    """Tek eksenli, hisse-sinifi boyutlu bir fact'in uye adi; degilse None."""
    if len(dimensions) != 1:
        return None
    axis, member = dimensions[0]
    if axis.rsplit("}", 1)[-1] not in _CLASS_OF_STOCK_AXES:
        return None
    return member.rsplit("}", 1)[-1]


def _combine_common_stock_classes(facts: tuple[SecFact, ...], *, as_of: date) -> SecFact:
    """Cok sinifli ihraccilarda kapak sayfasi adedini siniflar uzerinden toplar.

    Cift sinifli bir sirket EntityCommonStockSharesOutstanding'i birlesik olarak
    hic bildirmez; her sinif icin ayri, StatementClassOfStockAxis ile
    boyutlanmis bir fact yazar. Boyutsuz fact arayan secici bu yuzden bu
    sirketlerin hicbirini isleyemiyordu -- DELL'e ozel bir tuhaflik degil,
    GOOGL, FOX, BRK gibi butun cift sinifli yapilari disarida birakan bir
    bosluk (2026-08-05'te DELL uzerinde bulundu: A 276.744.341 +
    B 46.490.010 + C 324.873.640, birlesik rakam yok).

    Toplama yalnizca ekonomik hakki ayni olan adi hisse siniflari icin
    dogrudur. Izleme hisseleri (tracking stock) farkli bir varlik grubunun
    sonucuna baglidir ve toplanmamalidir; tanimadigi bir uye gorulurse sessizce
    toplanmaz, hata verilir.
    """
    scoped = [
        fact for fact in facts
        if fact.concept == "EntityCommonStockSharesOutstanding"
        and fact.namespace.startswith("http://xbrl.sec.gov/dei/")
        and fact.dimensions and not fact.is_nil and fact.unit == "shares"
        and fact.is_instant and fact.end_date <= as_of
    ]
    if not scoped:
        raise FactSelectionError("SEC filing has no eligible EntityCommonStockSharesOutstanding fact")
    latest_date = max(fact.end_date for fact in scoped)
    latest = [fact for fact in scoped if fact.end_date == latest_date]

    by_class: dict[str, SecFact] = {}
    for fact in latest:
        member = _class_member(fact.dimensions)
        if member is None:
            raise FactSelectionError(
                "cover-page share counts carry a dimension other than class of stock; "
                f"refusing to combine: {fact.dimensions}"
            )
        if not member.startswith("CommonClass"):
            raise FactSelectionError(
                f"cover-page share class {member!r} is not a plain common class; classes "
                "with a different economic claim must not be summed"
            )
        if member in by_class and by_class[member].value != fact.value:
            raise FactSelectionError(
                f"conflicting cover-page share counts for {member} at {latest_date}: "
                f"{sorted({by_class[member].value, fact.value})}"
            )
        by_class[member] = fact

    total = Decimal(0)
    for fact in by_class.values():
        try:
            value = Decimal(fact.value)
        except InvalidOperation as exc:
            raise FactSelectionError("SEC direct outstanding-share fact must be numeric") from exc
        if value <= 0 or value != value.to_integral_value():
            raise FactSelectionError("SEC direct outstanding-share fact must be positive")
        total += value

    reference = by_class[min(by_class)]
    # Kaynak izi tek bir context'e degil, toplama giren butun context'lere isaret
    # eder: uretilen deger tek bir fact'in kopyasi degil, siniflarin toplamidir.
    combined_context = "+".join(sorted(fact.context_id for fact in by_class.values()))
    return replace(
        reference, value=str(int(total)), dimensions=(), context_id=combined_context
    )


def direct_share_count_as_int(fact: SecFact) -> int:
    value = Decimal(fact.value)
    if value <= 0 or value != value.to_integral_value():
        raise FactSelectionError("SEC direct outstanding-share fact must be a positive whole number")
    return int(value)


def valuation_context_projection(
    ticker: str, as_of_date: str, cutoff_instant: str, financial_periods: tuple[str, ...]
) -> dict[str, Any]:
    return {
        "ticker": ticker, "as_of_date": as_of_date, "cutoff_instant": cutoff_instant,
        "reporting_currency": "USD", "share_count_basis": "spot_basic_shares_outstanding",
        "primary_price_mode": "official_close", "purpose": "current_valuation",
        "financial_period_refs": list(financial_periods),
    }


def _fetch_latest_close(ticker: str, as_of: date):
    request = EndOfDayFetchRequest(
        internal_ticker=ticker, provider_symbol=ticker,
        start_date_inclusive=(as_of - timedelta(days=14)).isoformat(),
        end_date_exclusive=(as_of + timedelta(days=1)).isoformat(), repair=True,
    )
    series = YFinanceProvider().fetch((request,))[0]
    if series.status != "ok":
        raise UsPipelineError(f"yfinance price fetch failed for {ticker}: {series.error_reason}")
    eligible = [row for row in series.rows if row.trade_date <= as_of.isoformat() and row.close.status == "available"]
    if not eligible:
        raise UsPipelineError(f"yfinance returned no eligible close for {ticker} as of {as_of}")
    return max(eligible, key=lambda row: row.trade_date)


def _manifest(
    *, ticker: str, exchange: str, manifest_id: str, authority_class: str,
    provider_id: str, dataset_kind: str, dataset_id: str, evidence_ref: str,
    effective_from: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0", "manifest_id": manifest_id, "manifest_version": "1.0.0", "ticker": ticker,
        "instrument_identity": {"instrument_id": ticker, "instrument_type": "ordinary_share", "trading_currency": "USD"},
        "source_authority": {"authority_class": authority_class, "provider_id": provider_id},
        "dataset_identity": {"dataset_id": dataset_id, "dataset_kind": dataset_kind},
        "instrument_mapping": {"venue_id": exchange},
        "allowed_use": {"scope": "internal_valuation", "redistribution_allowed": False},
        "license_evidence": {"evidence_ref": evidence_ref},
        "retention_policy": {"policy_id": "local-research-cache"},
        "revision_policy": {"policy_id": "source-revisions-preserved"},
        "lifecycle_status": "active", "effective_from": effective_from,
    }


def _reject_intervening_corporate_action(
    observation: dict[str, Any] | None, *, ticker: str, share_date: date, as_of: date,
) -> None:
    """Refuse a market capitalisation whose share count predates a corporate action.

    The cover-page count is dated: it describes the company on the day of the
    filing that reported it. A split or a spin-off taking effect after that day
    silently invalidates it, and the price on the other side of the event is
    already the adjusted one, so the product of the two is nonsense.

    A true split multiplies the count while a spin-off leaves it unchanged, and
    the price feed records both as a split factor -- NVDA's 10-for-1 and 3M's
    Solventum spin-off are indistinguishable in that column at the as-of date.
    Neither is assumed. The methods that need market capitalisation therefore
    go unavailable for the few months between the event and the next filing,
    which is cheap: eleven company-months of fifteen hundred in the score-IC
    universe (found 2026-08-06, when NVDA's 288 billion market capitalisation
    against an actual 2,880 billion made it the highest-scored company in the
    cross-section).
    """
    if not observation:
        return
    intervening = [
        item for item in observation.get("corporate_actions", [])
        if share_date.isoformat() < item["effective_date"] <= as_of.isoformat()
    ]
    if not intervening:
        return
    detail = ", ".join(f"{item['effective_date']} x{item['factor']}" for item in intervening)
    raise CorporateActionUnresolved(
        f"{ticker}: share count dated {share_date.isoformat()} predates a corporate action "
        f"({detail}); market capitalisation cannot be formed as of {as_of.isoformat()}"
    )


def _validate_historical_observation(
    observation: dict[str, str], *, ticker: str, as_of: date, cutoff_instant: str,
) -> tuple[str, str, str, str]:
    required = {
        "ticker", "trade_date", "close", "available_at", "ledger_frozen_at",
        "ledger_sha256", "source_record_ref",
    }
    missing = required - set(observation)
    if missing:
        raise UsPipelineError(f"historical market observation is missing {sorted(missing)}")
    if observation["ticker"] != ticker:
        raise UsPipelineError("historical market observation ticker mismatch")
    trade_date = date.fromisoformat(observation["trade_date"])
    if trade_date > as_of:
        raise UsPipelineError("historical market observation is from the future")
    if observation["available_at"] > cutoff_instant:
        raise UsPipelineError("historical market observation was not available at cutoff_instant")
    if len(observation["ledger_sha256"]) != 64:
        raise UsPipelineError("historical market observation has an invalid ledger hash")
    if not observation["close"] or float(observation["close"]) <= 0:
        raise UsPipelineError("historical market observation close must be positive")
    return (
        observation["trade_date"], observation["close"],
        observation["available_at"], observation["source_record_ref"],
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
