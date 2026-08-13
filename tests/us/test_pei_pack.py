import json
import hashlib
from datetime import date
from pathlib import Path

import pytest

from scripts.us_pei_pack import (
    align_subset_coverage,
    attach_tearsheet_context,
    finalize_current_valuation,
    flag_special_situations,
    peer_block,
    resolve_live_month,
    set_live_decision_date,
)
from adapter.live_refresh import (
    latest_filing_dates,
    live_month_name,
    refresh_live_price_ledger,
    refresh_live_sec_discovery_ledger,
    synchronize_live_universe,
    write_live_coverage,
)
from adapter.point_in_time import MonthPlan
from adapter.live_pack import _price_and_cap, _valuation
from engine.valuation.ingestion.eod.models import ProviderSeries


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _price_row(trade_date: str, close: str) -> dict:
    available = lambda value: {"status": "available", "value": value}
    return {
        "trade_date": trade_date,
        "open": available(close), "high": available(close),
        "low": available(close), "close": available(close),
        "adjusted_close": available(close), "volume": available("100"),
        "dividend": available("0"), "stock_split": available("0"),
    }


def test_transaction_forms_do_not_claim_a_transaction_is_pending(tmp_path):
    _write_json(
        tmp_path / "ledger" / "sec-discovery.json",
        {"submissions": {"VZ": {"relative_path": "ledger/VZ.json"}}},
    )
    _write_json(
        tmp_path / "ledger" / "VZ.json",
        {"filings": {"recent": {
            "form": ["S-4", "8-K"],
            "filingDate": ["2025-10-02", "2026-01-20"],
            "items": ["", "2.01"],
        }}},
    )
    pack = {
        "cutoff_instant": "2026-08-07T23:59:59Z",
        "companies": [{"ticker": "VZ", "fundamentals": {}}],
    }

    flag_special_situations(pack, tmp_path)

    company = pack["companies"][0]
    assert "pending_transaction" not in company
    history = company["transaction_filing_history"]
    assert history["current_transaction_status"] == (
        "not determined from filing-form history"
    )
    assert history["verification_required"] is True


def test_attach_tearsheet_context_uses_existing_workspace_artifacts(tmp_path):
    source_id = "sec-0000320193-test"
    period = "2026-Q3"
    provenance = {
        "source_file": "raw/sec-filings/AAPL/test.json",
        "source_type": "sec_inline_xbrl",
        "source_id": source_id,
        "sheet": "income_statement",
        "cell_or_range": "Revenue",
    }
    _write_json(
        tmp_path / "data" / "financial" / "AAPL" / f"{period}.json",
        {
            "period": period,
            "period_start": "2025-09-28",
            "period_end": "2026-06-27",
            "period_type": "quarterly",
            "currency": "USD",
            "scale": "million",
            "accounting_basis": "US_GAAP",
            "audit_status": "unaudited",
            "publication_date": "2026-07-31",
            "source_revision": "test",
            "income_statement": [
                {
                    "metric_id": "revenue_total",
                    "name": "Revenue",
                    "value": 100,
                    "unit": "million_usd",
                    "period": period,
                    "data_type": "direct",
                    "status": "available",
                    "provenance": provenance,
                }
            ],
            "balance_sheet": [],
            "cash_flow_statement": [
                {
                    "metric_id": "cf_share_repurchases",
                    "name": "Share Repurchases",
                    "value": -10,
                    "unit": "million_usd",
                    "period": period,
                    "data_type": "direct",
                    "status": "available",
                    "provenance": {**provenance, "sheet": "cash_flow_statement"},
                }
            ],
        },
    )
    _write_json(
        tmp_path / "data" / "risks" / "AAPL" / f"{period}.json",
        {
            "analysis_status": "available",
            "as_of": "2026-07-31",
            "risks": [
                {
                    "risk_id": "competition",
                    "category": "market",
                    "title": "Competition",
                    "description": "Competition may affect results.",
                    "direction": "negative",
                    "severity": "medium",
                    "evidence": [{"source_id": f"{source_id}-risk-factors"}],
                }
            ],
        },
    )
    _write_json(
        tmp_path / "data" / "source-manifests" / "AAPL.json",
        {
            "sources": [
                {
                    "source_id": source_id,
                    "path": "raw/sec-filings/AAPL/test.json",
                    "source_type": "sec_inline_xbrl",
                    "publication_date": "2026-07-31",
                    "periods_covered": [period],
                    "sha256": "financial-hash",
                },
                {
                    "source_id": f"{source_id}-risk-factors",
                    "path": "raw/sec-filings/AAPL/test-risk-factors.txt",
                    "source_type": "sec_filing_text",
                    "publication_date": "2026-07-31",
                    "periods_covered": [],
                    "sha256": "risk-hash",
                },
            ]
        },
    )
    _write_json(
        tmp_path / "ledger" / "sec-discovery.json",
        {
            "submissions": {
                "AAPL": {
                    "relative_path": "ledger/sec-discovery-payloads/CIK0000320193.json"
                }
            }
        },
    )
    _write_json(
        tmp_path / "ledger" / "sec-discovery-payloads" / "CIK0000320193.json",
        {
            "cik": "0000320193",
            "name": "Apple Inc.",
            "exchanges": ["Nasdaq"],
            "sic": "3571",
            "sicDescription": "Electronic Computers",
            "fiscalYearEnd": "0926",
            "addresses": {"business": {"city": "CUPERTINO", "stateOrCountry": "CA"}},
        },
    )
    pack = {
        "companies": [
            {
                "ticker": "AAPL",
                "period_label": period,
                "price_reconciliation": {"multiples_price_as_of": "2026-08-07"},
                "consensus_estimates": {
                    "status": "available",
                    "as_of": "2026-08-11",
                    "source": "test consensus",
                },
                "latest_earnings_release": {
                    "status": "available",
                    "filing_date": "2026-07-30",
                    "accession": "0000320193-release",
                    "source_id": "sec-0000320193-release",
                    "text_sha256": "release-hash",
                    "excerpts": ["Revenue increased."],
                },
            }
        ]
    }

    attach_tearsheet_context(pack, tmp_path)

    company = pack["companies"][0]
    assert company["identity"]["legal_name"] == "Apple Inc."
    assert company["identity"]["fiscal_year_end"] == "0926"
    assert company["business_profile"]["status"] == "partial"
    assert company["reported_financials"]["metrics"][0]["source"] == source_id
    assert company["reported_financials"]["metrics"][0]["evidence"] == "fact_source_reported"
    assert company["capital_allocation"]["share_repurchases"]["value"] == -10
    assert company["risk_factors"]["risks"][0]["risk_id"] == "competition"
    assert "sec-0000320193-release" in {item["source_id"] for item in company["sources"]}
    assert "short_interest_and_borrow" in {
        item["field"] for item in company["evidence_gaps"]
    }


def test_finalize_current_valuation_refreshes_equity_and_enterprise_value_multiples():
    pack = {
        "companies": [
            {
                "ticker": "TEST",
                "closing_price_usd": 100.0,
                "market_cap_usd_m": 1_000.0,
                "valuation": {
                    "Price / Earnings": 20.0,
                    "Earnings Yield": 5.0,
                    "Lease-Exclusive Enterprise Value / Reported Operating Income": 11.0,
                },
                "price_refresh": {
                    "status": "available",
                    "price_now": 110.0,
                    "price_as_of": "2026-08-11",
                    "price_at_cutoff": 100.0,
                    "cutoff_price_as_of": "2026-08-07",
                    "market_cap_now_usd_m": 1_100.0,
                    "valuation_at_price_now": {
                        "Price / Earnings": 22.0,
                        "Earnings Yield": 4.5455,
                    },
                    "not_rescaled": [
                        "Lease-Exclusive Enterprise Value / Reported Operating Income"
                    ],
                },
                "net_debt": {
                    "status": "derived",
                    "net_debt": 100.0,
                    "may_be_only_part_of_the_debt": False,
                },
                "own_valuation_history": {
                    "status": "available",
                    "span": ["2021-01-29", "2026-07-31"],
                    "methods": {
                        "Earnings Yield": {
                            "last_value": 0.05,
                            "latest_sits": "between its 25th percentile and median",
                            "p25": 0.04,
                            "median": 0.06,
                            "p75": 0.08,
                        },
                        "Lease-Exclusive Enterprise Value / Reported Operating Income": {
                            "last_value": 11.0,
                            "latest_sits": "between its 25th percentile and median",
                            "p25": 10.0,
                            "median": 13.0,
                            "p75": 16.0,
                        },
                    },
                },
            }
        ]
    }

    updated, missing = finalize_current_valuation(pack)

    company = pack["companies"][0]
    assert updated == 1
    assert missing == []
    assert company["market_at_cutoff"]["price_usd"] == 100.0
    assert company["closing_price_usd"] == 110.0
    assert company["market_cap_usd_m"] == 1_100.0
    assert company["valuation_at_cutoff"]["Price / Earnings"] == 20.0
    assert company["valuation"]["Price / Earnings"] == 22.0
    assert company["valuation"]["Earnings Yield"] == 4.5455
    assert company["valuation"][
        "Lease-Exclusive Enterprise Value / Reported Operating Income"
    ] == 12.0
    assert company["valuation_as_of"] == "2026-08-11"
    assert company["price_refresh"]["not_rescaled"] == []
    history = company["own_valuation_history"]
    assert history["history_through"] == "2026-07-31"
    assert history["current_valuation_as_of"] == "2026-08-11"
    assert history["methods"]["Earnings Yield"]["current_value"] == 0.045455
    assert history["methods"]["Earnings Yield"]["current_sits"] == (
        "between its 25th percentile and median"
    )
    assert history["methods"][
        "Lease-Exclusive Enterprise Value / Reported Operating Income"
    ]["current_sits"] == "between its 25th percentile and median"


def test_resolve_live_month_rejects_an_older_cutoff(tmp_path):
    _write_json(tmp_path / "run-config.json", {"universe": ["AAPL"]})
    for folder, cutoff in (
        ("2026-07-31", "2026-07-31"),
        ("2026-08-07", "2026-08-07"),
    ):
        _write_json(
            tmp_path / "months" / folder / "cutoff.json",
            {"cutoff_date": cutoff},
        )
        _write_json(
            tmp_path / "months" / folder / "coverage.json",
            {"covered": 1, "universe": 1, "missing": [], "skipped": {}},
        )
        valuation = (
            tmp_path / "data" / "valuation-results" / "AAPL" / cutoff /
            "ctx-test" / "current.json"
        )
        _write_json(valuation, {"method_results": []})

    assert resolve_live_month(tmp_path, None) == "2026-08-07"
    assert resolve_live_month(tmp_path, "2026-08-07") == "2026-08-07"
    with pytest.raises(SystemExit, match="live pack eski kesitten uretilmez"):
        resolve_live_month(tmp_path, "2026-07-31")


def test_resolve_live_month_accepts_latest_partial_coverage(tmp_path):
    _write_json(tmp_path / "run-config.json", {"universe": ["AAPL", "RDDT"]})
    _write_json(
        tmp_path / "months" / "2026-08-07" / "cutoff.json",
        {"cutoff_date": "2026-08-07"},
    )
    _write_json(
        tmp_path / "months" / "2026-08-07" / "coverage.json",
        {"covered": 1, "universe": 2, "missing": ["RDDT"],
         "skipped": {"RDDT": "financial validation failed"}},
    )

    assert resolve_live_month(tmp_path, None) == "2026-08-07"


def test_latest_live_snapshot_uses_cutoff_instant_not_hash_suffix(tmp_path):
    _write_json(tmp_path / "run-config.json", {"universe": ["AAPL"]})
    for folder, instant in (
        ("2026-08-12-ffffffff", "2026-08-12T10:00:00Z"),
        ("2026-08-12-00000000", "2026-08-12T12:00:00Z"),
    ):
        _write_json(tmp_path / "months" / folder / "cutoff.json", {
            "cutoff_date": "2026-08-11", "cutoff_instant": instant,
        })
        _write_json(tmp_path / "months" / folder / "coverage.json", {
            "covered": 1, "universe": 1, "missing": [], "skipped": {},
        })

    assert resolve_live_month(tmp_path, None) == "2026-08-12-00000000"


def test_live_decision_date_is_pack_build_date_not_financial_cutoff():
    pack = {
        "decision_date": "2026-08-07",
        "execution_date": "2026-08-07",
        "cutoff_instant": "2026-08-07T23:59:59Z",
    }

    set_live_decision_date(pack, "2026-08-12")

    assert pack["decision_date"] == "2026-08-12"
    assert pack["execution_date"] == "2026-08-07"
    assert pack["cutoff_instant"] == "2026-08-07T23:59:59Z"


def test_subset_coverage_reports_pack_members_and_preserves_source_count():
    pack = {
        "companies": [{"ticker": "AAPL"}, {"ticker": "VZ"}],
        "universe_coverage": {
            "configured_count": 87,
            "included_count": 87,
            "missing_financial_artifacts": ["RDDT", "VZ"],
        },
    }

    align_subset_coverage(pack, {"AAPL", "VZ"})

    assert pack["universe_coverage"] == {
        "configured_count": 87,
        "source_included_count": 87,
        "included_count": 2,
        "missing_financial_artifacts": ["VZ"],
    }


def test_aapl_peer_framework_keeps_economic_lenses_separate():
    def company(ticker, pe, revenue_growth, roic):
        return {
            "ticker": ticker,
            "latest_period_end": "2026-06-30",
            "financial_publication_date": "2026-07-30",
            "market_data_as_of": "2026-08-11",
            "valuation_as_of": "2026-08-11",
            "closing_price_usd": 100.0,
            "market_cap_usd_m": 1_000.0,
            "valuation": {"Price / Earnings": pe},
            "fundamentals": {
                "revenue_growth": revenue_growth,
                "gross_margin": 50.0,
                "free_cash_flow_margin": 20.0,
            },
            "roic": {"status": "derived", "value_pct": roic},
            "consensus_estimates": {
                "status": "available",
                "as_of": "2026-08-12",
                "revenue_estimate": {"0y": {"growth": 0.10}},
                "earnings_estimate": {
                    "0y": {"growth": 0.12, "numberOfAnalysts": 20}
                },
                "eps_revisions": {
                    "0y": {"upLast30days": 3, "downLast30days": 1}
                },
            },
        }

    companies = [company("AAPL", 30, 8, 40)]
    companies += [
        company("MSFT", 32, 12, 35), company("GOOGL", 24, 11, 28),
        company("DELL", 15, 5, 18), company("HPQ", 9, 2, 14),
        company("NVDA", 40, 30, 60), company("META", 26, 15, 32),
    ]

    result = peer_block({"companies": companies}, "AAPL", {})

    assert result["framework_type"] == "company_specific_multi_lens"
    assert result["single_combined_peer_median"] is False
    assert result["peer_count"] == 6
    groups = {group["group_id"]: group for group in result["groups"]}
    assert groups["platform_services_core"]["medians"]["valuation"][
        "Price / Earnings"
    ] == 28.0
    assert groups["hardware_floor"]["medians"]["valuation"][
        "Price / Earnings"
    ] == 12.0
    assert groups["quality_growth_anchors"]["medians"]["quality"][
        "roic_pct"
    ] == 46.0
    assert groups["platform_services_core"]["members"][0]["as_of"][
        "valuation"
    ] == "2026-08-11"
    assert "medians" not in {
        key: value for key, value in result.items() if key != "groups"
    }


def test_live_universe_sync_adds_new_authored_members(tmp_path):
    _write_json(
        tmp_path / "live" / "current" / "run-config.json",
        {"universe": ["AAPL"], "cohorts": {"AAPL": "TechnologyHardware"}},
    )
    _write_json(
        tmp_path / "config" / "valuation" / "comparison" / "peer-universes" /
        "technology.json",
        {
            "members": [
                {"ticker": "AAPL", "classification_refs": ["MODEL:TechnologyHardware"]},
                {"ticker": "GOOGL", "classification_refs": ["MODEL:TechnologySoftware"]},
                {"ticker": "META", "classification_refs": ["MODEL:TechnologySoftware"]},
            ]
        },
    )

    change = synchronize_live_universe(
        run_root=tmp_path / "live" / "current", repo_root=tmp_path
    )

    config = json.loads(
        (tmp_path / "live" / "current" / "run-config.json").read_text()
    )
    assert change == {"added": ["GOOGL", "META"], "removed": []}
    assert config["universe"] == ["AAPL", "GOOGL", "META"]
    assert config["cohorts"]["META"] == "TechnologySoftware"


def test_live_month_name_versions_changed_immutable_cutoff(tmp_path):
    manifest = tmp_path / "ledger" / "price-ledger.json"
    _write_json(manifest, {"ticker_sha256": {"AAPL": "old", "GOOGL": "new"}})
    _write_json(
        tmp_path / "months" / "2026-08-07" / "cutoff.json",
        {
            "cutoff_date": "2026-08-07",
            "price_ledger_manifest_sha256": "old-manifest-hash",
        },
    )

    name = live_month_name(run_root=tmp_path, cutoff="2026-08-07")

    assert name.startswith("2026-08-07-")
    assert name != "2026-08-07"


def test_live_price_ledger_advances_existing_ticker_to_new_session(tmp_path):
    _write_json(tmp_path / "run-config.json", {
        "start_date": "2024-01-01", "universe": ["WMT"],
    })
    price_path = tmp_path / "ledger" / "prices" / "WMT.json"
    _write_json(price_path, {
        "schema_version": "1.0.0", "ticker": "WMT", "provider": "yfinance",
        "frozen_at": "2026-08-08T00:00:00Z",
        "rows": [_price_row("2026-08-07", "111")], "warnings": [],
    })
    _write_json(tmp_path / "ledger" / "price-ledger.json", {
        "schema_version": "1.0.0", "frozen_at": "2026-08-08T00:00:00Z",
        "ticker_sha256": {"WMT": _hash(price_path)},
    })

    class Provider:
        def fetch(self, requests):
            request = requests[0]
            return [ProviderSeries.from_dict({
                "internal_ticker": request.internal_ticker,
                "provider_symbol": request.provider_symbol,
                "status": "ok",
                "rows": [_price_row("2026-08-07", "112"),
                         _price_row("2026-08-11", "115")],
                "warnings": [],
            })]

    refresh_live_price_ledger(
        run_root=tmp_path, provider=Provider(), through=date(2026, 8, 12),
    )

    payload = json.loads(price_path.read_text())
    assert [row["trade_date"] for row in payload["rows"]] == [
        "2026-08-07", "2026-08-11",
    ]
    assert payload["rows"][0]["close"]["value"] == "112"
    manifest = json.loads((tmp_path / "ledger" / "price-ledger.json").read_text())
    assert manifest["ticker_sha256"]["WMT"] == _hash(price_path)
    assert manifest["refresh_failures"] == {}


def test_live_sec_discovery_refreshes_existing_company_submission(tmp_path):
    _write_json(tmp_path / "run-config.json", {"universe": ["CRM"]})
    payload_root = tmp_path / "ledger" / "sec-discovery-payloads"
    ticker_path = payload_root / "company_tickers.json"
    crm_path = payload_root / "CIK0001108524.json"
    _write_json(ticker_path, {"0": {"ticker": "CRM", "cik_str": 1108524}})
    _write_json(crm_path, {"filings": {"recent": {
        "form": ["10-Q"], "filingDate": ["2026-08-07"],
    }}})
    _write_json(tmp_path / "ledger" / "sec-discovery.json", {
        "schema_version": "1.0.0",
        "company_tickers": {
            "url": "https://www.sec.gov/files/company_tickers.json",
            "relative_path": "ledger/sec-discovery-payloads/company_tickers.json",
            "sha256": _hash(ticker_path),
        },
        "submissions": {"CRM": {
            "cik": "0001108524",
            "url": "https://data.sec.gov/submissions/CIK0001108524.json",
            "relative_path": "ledger/sec-discovery-payloads/CIK0001108524.json",
            "sha256": _hash(crm_path),
        }},
    })

    class Client:
        def get_json(self, url):
            if url.endswith("company_tickers.json"):
                return {"0": {"ticker": "CRM", "cik_str": 1108524}}
            return {"filings": {"recent": {
                "form": ["10-Q"], "filingDate": ["2026-08-12"],
            }}}

    refresh_live_sec_discovery_ledger(run_root=tmp_path, client=Client())

    assert latest_filing_dates(tmp_path, ["CRM"]) == {"CRM": "2026-08-12"}
    manifest = json.loads((tmp_path / "ledger" / "sec-discovery.json").read_text())
    assert manifest["submissions"]["CRM"]["sha256"] == _hash(crm_path)


def test_live_coverage_uses_reusable_financial_artifacts_not_same_day_valuation(tmp_path):
    _write_json(tmp_path / "run-config.json", {"universe": ["AAPL", "CRM"]})
    (tmp_path / "data" / "financial" / "AAPL").mkdir(parents=True)
    plan = MonthPlan(
        month="2026-08-12-test", decision_date="2026-08-12",
        cutoff_date="2026-08-11", cutoff_instant="2026-08-12T12:00:00Z",
        execution_date="2026-08-11",
    )

    path = write_live_coverage(run_root=tmp_path, plan=plan)

    coverage = json.loads(path.read_text())
    assert coverage["covered"] == 1
    assert coverage["missing"] == ["CRM"]


def test_live_pack_reuses_latest_valuation_anchor_before_information_cutoff(tmp_path):
    _write_json(
        tmp_path / "data" / "valuation-results" / "AAPL" / "2026-08-07" /
        "ctx-test" / "current.json",
        {"method_results": [{
            "method_id": "val.method.pe.reported_parent",
            "canonical_value": {"value": "30"},
        }]},
    )
    _write_json(
        tmp_path / "data" / "valuation-inputs" / "AAPL" / "2026-08-07" /
        "ctx-test.json",
        {
            "price_basis": {"reporting_currency_price": {"value": "100"}},
            "market_cap_basis": {
                "reporting_currency_total_market_cap": {"value": "2000000000"}
            },
        },
    )

    valuation = _valuation(tmp_path, "AAPL", "2026-08-12")
    price, market_cap = _price_and_cap(tmp_path, "AAPL", "2026-08-12")

    assert valuation["Price / Earnings"] == 30.0
    assert price == 100.0
    assert market_cap == 2000.0
