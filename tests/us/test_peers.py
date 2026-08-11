import json
from collections import Counter
from pathlib import Path

from fundamental_pipeline.valuation.comparison.build_peer_observations import build_observations
from fundamental_pipeline_us.peers import _single_result_path


def test_every_peer_universe_member_has_a_company_and_a_price_symbol():
    """Uc kaynak ayni kumeyi tanimlamali: emsal evrenleri, sirket konfigleri ve
    fiyat saglayici eslemesi.

    Ucu de elle tutuluyor ve birbirinden ayri dosyalarda; biri unutulunca hata
    gec ve dolayli cikiyor. Fiyat eslemesi eksik kalan bir ticker sessizce
    yerel-ayara turetilmis bir sembole dusuyordu (`AAPL.IS`), 404 aliyor ve
    ancak sonra duz sembole geri donuyordu -- calisiyor gorunen ama her cagride
    bosa istek yapan bir yol."""
    root = Path(__file__).resolve().parents[2]
    universe_root = root / "config" / "valuation" / "comparison" / "peer-universes"
    companies = {path.stem for path in (root / "config" / "companies").glob("*.json")}
    provider = json.loads((
        root / "config" / "market-data" / "providers" / "yfinance.json"
    ).read_text(encoding="utf-8"))
    provider_tickers = {row["internal_ticker"] for row in provider["ticker_mappings"]}

    members: set[str] = set()
    for path in sorted(universe_root.glob("*.json")):
        universe = json.loads(path.read_text(encoding="utf-8"))
        cohort_sizes = Counter(
            tuple(row["classification_refs"]) for row in universe["members"]
        )
        # Cohort tavani 2; bir cohort tek uyeliyse o tavan anlamsizdir.
        assert min(cohort_sizes.values()) >= 2, f"{path.name}: tek uyeli cohort"
        for row in universe["members"]:
            assert row["ticker"] not in members, f"{row['ticker']} iki evrende"
            members.add(row["ticker"])

    assert members == companies == provider_tickers


def test_build_peer_observations_accepts_isolated_us_root(tmp_path: Path):
    root = tmp_path / "us"
    universe_path = root / "universe.json"
    universe_path.parent.mkdir(parents=True)
    universe_path.write_text(json.dumps({
        "universe_id": "consumer_staples_us",
        "members": [{"member_id": "ko", "ticker": "KO"}],
    }), encoding="utf-8")
    derived_path = root / "data" / "financial" / "KO" / "2026-Q2-derived-ratios.json"
    derived_path.parent.mkdir(parents=True)
    derived_path.write_text(json.dumps({
        "period": "2026-Q2",
        "margins": [{"metric_id": "gross_margin", "value": 61.5, "status": "available", "formula_id": "gross_margin"}],
    }), encoding="utf-8")

    artifact = build_observations(
        universe_path, "gross_margin", "2026-08-03",
        root=root, currency="USD", accounting_basis="US_GAAP",
    )

    assert artifact["currency"] == "USD"
    assert artifact["accounting_basis"] == "US_GAAP"
    assert artifact["observations"][0]["value"]["value"] == "61.5"
    assert artifact["observations"][0]["provenance_refs"][0]["relative_path"].startswith("data/financial/KO/")


def test_build_peer_observations_canonicalizes_trailing_zero(tmp_path: Path):
    root = tmp_path / "us"
    universe_path = root / "universe.json"
    universe_path.parent.mkdir(parents=True)
    universe_path.write_text(json.dumps({
        "universe_id": "consumer_staples_us",
        "members": [{"member_id": "cl", "ticker": "CL"}],
    }), encoding="utf-8")
    derived_path = root / "data" / "financial" / "CL" / "2026-Q2-derived-ratios.json"
    derived_path.parent.mkdir(parents=True)
    derived_path.write_text(json.dumps({
        "period": "2026-Q2",
        "margins": [{"metric_id": "net_margin", "value": 3.0, "status": "available", "formula_id": "net_margin"}],
    }), encoding="utf-8")

    artifact = build_observations(
        universe_path, "net_margin", "2026-08-03", root=root,
        currency="USD", accounting_basis="US_GAAP",
    )

    assert artifact["observations"][0]["value"]["value"] == "3"


def test_multiple_same_date_contexts_select_latest_cutoff(tmp_path: Path):
    root = tmp_path / "us"
    universe_path = root / "universe.json"
    universe_path.parent.mkdir(parents=True)
    universe_path.write_text(json.dumps({
        "universe_id": "consumer_staples_us",
        "members": [{"member_id": "ko", "ticker": "KO"}],
    }), encoding="utf-8")
    for context_id, cutoff, value in (
        ("ctx-z-older", "2026-08-03T12:00:00Z", "0.03"),
        ("ctx-a-newer", "2026-08-04T12:00:00Z", "0.04"),
    ):
        path = root / "data" / "valuation-results" / "KO" / "2026-08-03" / context_id / "current.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "artifact_id": context_id,
            "temporal_context": {"valuation_cutoff_at": cutoff},
            "method_results": [{
                "method_id": "val.method.earnings_yield.reported_parent",
                "canonical_value": {"status": "available", "value": value},
                "formula_ref": {"formula_id": "earnings-yield"},
            }],
        }), encoding="utf-8")

    artifact = build_observations(
        universe_path, "val.method.earnings_yield.reported_parent", "2026-08-03",
        root=root, currency="USD", accounting_basis="US_GAAP",
    )

    assert artifact["observations"][0]["value"]["value"] == "0.04"
    assert _single_result_path(root, "KO", "2026-08-03").parent.name == "ctx-a-newer"
