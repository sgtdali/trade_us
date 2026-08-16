"""The mechanical check engine and its binding to the metric catalog.

Two things this file is really testing: that a rule which cannot be evaluated
says so instead of passing, and that a breach does exactly one thing.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from adapter.fund import cli, metrics, monitoring, store, thesis as thesis_module
from adapter.fund.monitoring import BREACHED, NOT_BREACHED, UNAVAILABLE, Observation


@pytest.fixture(scope="module")
def catalog():
    return metrics.load_catalog()


def rule(**overrides):
    document = {
        "rule_id": "gross_margin_floor",
        "metric_id": "gross_margin",
        "period_basis": "ttm",
        "test_type": "absolute_value",
        "operator": "lt",
        "threshold": "0.55",
    }
    document.update(overrides)
    return document


def observation(**overrides):
    document = {
        "metric_id": "gross_margin",
        "period_basis": "ttm",
        "status": "available",
        "value": "0.62",
        "unit": "percent",
        "as_of": "2026-08-15",
        "source_accession": "0001045810-26-000123",
    }
    document.update(overrides)
    return Observation.from_document(document)


# ------------------------------------------------------------- binding

def test_a_rule_binds_to_a_real_metric(catalog):
    metrics.check_binding(rule(), catalog)


def test_an_unknown_metric_does_not_bind(catalog):
    with pytest.raises(metrics.MetricBindingError, match="no metric"):
        metrics.check_binding(rule(metric_id="vibes"), catalog)


def test_the_error_says_to_leave_it_qualitative(catalog):
    with pytest.raises(metrics.MetricBindingError, match="stays qualitative"):
        metrics.check_binding(rule(metric_id="management_credibility"), catalog)


def test_an_absolute_threshold_against_a_change_basis_does_not_bind(catalog):
    """Comparing a level to a delta measures nothing, and looks fine."""
    with pytest.raises(metrics.MetricBindingError, match="needs a level period basis"):
        metrics.check_binding(rule(period_basis="latest_quarter_yoy"), catalog)


def test_a_change_test_against_a_level_basis_does_not_bind(catalog):
    with pytest.raises(metrics.MetricBindingError, match="needs a change period basis"):
        metrics.check_binding(
            rule(test_type="basis_point_change", period_basis="ttm", threshold="-300"), catalog)


def test_basis_points_only_apply_to_a_rate(catalog):
    with pytest.raises(metrics.MetricBindingError, match="only apply to a rate"):
        metrics.check_binding(
            rule(metric_id="free_cash_flow", test_type="basis_point_change",
                 period_basis="latest_quarter_yoy", threshold="-300"), catalog)


def test_a_percentage_change_of_a_percentage_is_refused(catalog):
    with pytest.raises(metrics.MetricBindingError, match="already a rate"):
        metrics.check_binding(
            rule(test_type="percentage_change", period_basis="latest_quarter_yoy"), catalog)


def test_a_percentage_change_of_a_magnitude_binds(catalog):
    metrics.check_binding(
        rule(metric_id="free_cash_flow", test_type="percentage_change",
             period_basis="latest_quarter_yoy", threshold="-0.2"), catalog)


def test_contract_binding_reports_every_problem_at_once(catalog):
    contract = {"mechanical_rules": [rule(metric_id="vibes"),
                                     rule(rule_id="second", period_basis="latest_quarter_yoy")]}
    assert len(metrics.check_contract(contract, catalog)) == 2


# ------------------------------------------------------------- evaluation

def test_a_rule_that_holds_is_not_breached(catalog):
    outcome = monitoring.evaluate_rule(rule(), observation(value="0.62"), catalog)
    assert outcome.result == NOT_BREACHED
    assert outcome.observed_value == Decimal("0.62")


def test_a_rule_that_is_crossed_is_breached(catalog):
    outcome = monitoring.evaluate_rule(rule(), observation(value="0.51"), catalog)
    assert outcome.result == BREACHED
    assert outcome.is_breach


@pytest.mark.parametrize("operator,value,expected", [
    ("lt", "0.54", BREACHED), ("lt", "0.55", NOT_BREACHED), ("lt", "0.56", NOT_BREACHED),
    ("lte", "0.55", BREACHED), ("lte", "0.56", NOT_BREACHED),
    ("gt", "0.56", BREACHED), ("gt", "0.55", NOT_BREACHED),
    ("gte", "0.55", BREACHED), ("gte", "0.54", NOT_BREACHED),
])
def test_the_operators_are_exact_at_the_boundary(catalog, operator, value, expected):
    outcome = monitoring.evaluate_rule(rule(operator=operator), observation(value=value), catalog)
    assert outcome.result == expected


def test_a_missing_observation_is_unavailable_not_passing(catalog):
    outcome = monitoring.evaluate_rule(rule(), None, catalog)
    assert outcome.result == UNAVAILABLE
    assert outcome.reason == "no_observation"
    assert not outcome.counted_as_checked


def test_an_unavailable_observation_carries_its_reason_through(catalog):
    outcome = monitoring.evaluate_rule(
        rule(), observation(status="unavailable", value=None,
                            reason="segment disclosure changed"), catalog)
    assert outcome.result == UNAVAILABLE
    assert "segment disclosure changed" in outcome.detail


def test_a_value_in_the_wrong_unit_is_unavailable(catalog):
    outcome = monitoring.evaluate_rule(rule(), observation(unit="million_usd"), catalog)
    assert outcome.result == UNAVAILABLE
    assert outcome.reason == "unit_mismatch"


def test_catalog_drift_produces_unavailable_never_no_change(catalog):
    """The rule bound six months ago; the catalog has moved since."""
    drifted = dict(catalog)
    drifted.pop("gross_margin")
    outcome = monitoring.evaluate_rule(rule(), observation(), drifted)
    assert outcome.result == UNAVAILABLE
    assert outcome.reason == "catalog_drift"


def test_stale_evidence_is_unavailable(catalog):
    outcome = monitoring.evaluate_rule(
        rule(), observation(as_of="2025-01-01"), catalog,
        max_evidence_age_days=180, as_of="2026-08-16")
    assert outcome.result == UNAVAILABLE
    assert outcome.reason == "stale_evidence"


def test_fresh_evidence_passes_the_age_check(catalog):
    outcome = monitoring.evaluate_rule(
        rule(), observation(as_of="2026-08-01"), catalog,
        max_evidence_age_days=180, as_of="2026-08-16")
    assert outcome.counted_as_checked


def test_every_unavailable_reason_is_from_the_closed_set(catalog):
    outcomes = [
        monitoring.evaluate_rule(rule(), None, catalog),
        monitoring.evaluate_rule(rule(), observation(unit="million_usd"), catalog),
        monitoring.evaluate_rule(rule(), observation(status="unavailable", value=None), catalog),
    ]
    for outcome in outcomes:
        assert outcome.reason in monitoring.UNAVAILABLE_REASONS


def test_a_contract_evaluates_every_rule(catalog):
    contract = {"mechanical_rules": [
        rule(),
        rule(rule_id="fcf_growth", metric_id="free_cash_flow", test_type="percentage_change",
             period_basis="latest_quarter_yoy", operator="lt", threshold="-0.2"),
    ]}
    outcomes = monitoring.evaluate_contract(contract, [observation()], catalog)
    assert [o.result for o in outcomes] == [NOT_BREACHED, UNAVAILABLE]
    assert "1 not breached, 1 unavailable" == monitoring.summarise(outcomes)


# ---------------------------------------------------------------- records

def test_a_record_of_an_evaluated_rule_carries_its_value(catalog):
    outcome = monitoring.evaluate_rule(rule(), observation(value="0.51"), catalog)
    record = monitoring.build_record(outcome, rule(), thesis_id="THS-0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e6f",
                                     contract_version=1, evaluated_for="new_periodic_filing")
    from adapter.fund import schemas

    assert schemas.schema_errors(record, schemas.MONITORING_CHECK_RECORD) == []
    assert record["observed_value"] == "0.51"
    assert record["contract_version"] == 1
    assert "unavailable_reason" not in record


def test_a_record_of_an_unavailable_rule_carries_no_value(catalog):
    from adapter.fund import schemas

    outcome = monitoring.evaluate_rule(rule(), None, catalog)
    record = monitoring.build_record(outcome, rule(), thesis_id="THS-0192f8a1-2b3c-7d4e-8f90-1a2b3c4d5e6f",
                                     contract_version=1, evaluated_for="review_due")
    assert schemas.schema_errors(record, schemas.MONITORING_CHECK_RECORD) == []
    assert record["unavailable_reason"] == "no_observation"
    assert "observed_value" not in record


def test_the_binding_signature_changes_when_the_catalog_does(catalog):
    before = metrics.binding_signature(rule(), catalog)
    drifted = json.loads(json.dumps({k: v for k, v in catalog.items()}))
    drifted["gross_margin"]["allowed_units"] = ["ratio"]
    assert metrics.binding_signature(rule(), drifted) != before


# ------------------------------------------------------------------- CLI

@pytest.fixture()
def fund(tmp_path):
    prefix = ["--ledger", str(tmp_path / "ledger.sqlite3"),
              "--instruments", str(tmp_path / "instruments.json")]

    def run(*argv: str) -> int:
        return cli.main(prefix + list(argv))

    run.tmp_path = tmp_path  # type: ignore[attr-defined]
    run("init")
    run("instrument", "add", "--ticker", "NVDA", "--name", "NVIDIA Corporation")
    run("assess", "NVDA", "--summary", "Pricing power holds",
        "--readiness", "starter", "--downside", "-0.30",
        "--downside-scenario", "Competition compresses the margin",
        "--evidence-date", "2026-08-16", "--review-due", "2026-11-15",
        "--as-of", "2026-08-16")
    run("thesis", "open", "NVDA", "--as-of", "2026-08-16")
    return run


def write_contract(tmp_path, rules=None):
    path = tmp_path / "contract.json"
    path.write_text(json.dumps({
        "version": 1,
        "effective_from": "2026-08-16",
        "mechanical_rules": rules if rules is not None else [rule()],
        "qualitative_checks": [],
    }), encoding="utf-8")
    return str(path)


def write_observations(tmp_path, entries):
    path = tmp_path / "observations.json"
    path.write_text(json.dumps({"observations": entries}), encoding="utf-8")
    return str(path)


def only_thesis(fund):
    ledger = store.open_ledger(path=fund.tmp_path / "ledger.sqlite3")
    return next(iter(thesis_module.project(ledger.thesis_events()).values()))


def test_a_contract_that_does_not_bind_is_not_activated(fund, tmp_path, capsys):
    thesis_id = only_thesis(fund).thesis_id
    path = write_contract(tmp_path, [rule(metric_id="vibes")])
    capsys.readouterr()
    assert fund("thesis", "contract", thesis_id, "--from", path) == 2
    assert "does not bind to the metric catalog" in capsys.readouterr().err
    assert "monitoring_contract" not in only_thesis(fund).document


def test_a_clean_check_reports_what_it_does_not_mean(fund, tmp_path, capsys):
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", write_contract(tmp_path))
    observations = write_observations(tmp_path, [{
        "metric_id": "gross_margin", "period_basis": "ttm", "status": "available",
        "value": "0.62", "unit": "percent", "as_of": "2026-08-15",
    }])

    capsys.readouterr()
    assert fund("check", thesis_id, "--observations", observations,
                "--as-of", "2026-08-20") == 0
    output = capsys.readouterr().out
    assert "not the same as the thesis being healthy" in output
    assert only_thesis(fund).status == thesis_module.ACTIVE


def test_a_breach_moves_the_thesis_to_review_required_and_stops(fund, tmp_path, capsys):
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", write_contract(tmp_path))
    observations = write_observations(tmp_path, [{
        "metric_id": "gross_margin", "period_basis": "ttm", "status": "available",
        "value": "0.51", "unit": "percent", "as_of": "2026-11-01",
    }])

    capsys.readouterr()
    assert fund("check", thesis_id, "--observations", observations,
                "--evaluated-for", "new_periodic_filing",
                "--accession", "0001045810-26-000123", "--as-of", "2026-11-05") == 0
    output = capsys.readouterr().out
    assert "BREACHED" in output
    assert "thesis -> review_required" in output
    assert "your judgement, not the rule's" in output

    history = only_thesis(fund)
    assert history.status == thesis_module.REVIEW_REQUIRED
    # And nothing else: the machine did not touch anything but the status.
    assert history.document["status"] != thesis_module.BROKEN


def test_the_machine_transition_is_recorded_as_machine_authored(fund, tmp_path):
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", write_contract(tmp_path))
    fund("check", thesis_id, "--observations", write_observations(tmp_path, [{
        "metric_id": "gross_margin", "period_basis": "ttm", "status": "available",
        "value": "0.51", "unit": "percent", "as_of": "2026-11-01",
    }]), "--as-of", "2026-11-05")

    transition = only_thesis(fund).transitions[-1]
    assert transition["actor"] == "machine"
    assert "mechanical breach" in transition["reason"]


def test_an_unavailable_check_says_it_did_not_run(fund, tmp_path, capsys):
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", write_contract(tmp_path))
    capsys.readouterr()
    fund("check", thesis_id, "--observations", write_observations(tmp_path, []),
         "--as-of", "2026-11-05")
    output = capsys.readouterr().out
    assert "UNAVAILABLE" in output
    assert "an unavailable check is not a passed check" in output
    assert only_thesis(fund).status == thesis_module.ACTIVE


def test_the_same_filing_cannot_be_checked_twice(fund, tmp_path, capsys):
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", write_contract(tmp_path))
    observations = write_observations(tmp_path, [{
        "metric_id": "gross_margin", "period_basis": "ttm", "status": "available",
        "value": "0.62", "unit": "percent", "as_of": "2026-11-01",
    }])
    args = ("check", thesis_id, "--observations", observations,
            "--accession", "0001045810-26-000123", "--as-of", "2026-11-05")
    assert fund(*args) == 0
    capsys.readouterr()
    assert fund(*args) == 2
    assert "already recorded for this evidence" in capsys.readouterr().err


def test_a_second_breach_does_not_re_transition(fund, tmp_path, capsys):
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", write_contract(tmp_path))
    breach = [{"metric_id": "gross_margin", "period_basis": "ttm", "status": "available",
               "value": "0.51", "unit": "percent", "as_of": "2026-11-01"}]
    fund("check", thesis_id, "--observations", write_observations(tmp_path, breach),
         "--accession", "acc-1", "--as-of", "2026-11-05")

    capsys.readouterr()
    fund("check", thesis_id, "--observations", write_observations(tmp_path, breach),
         "--accession", "acc-2", "--as-of", "2026-11-06")
    assert "already review_required" in capsys.readouterr().out


def test_checks_are_listed_with_their_contract_version(fund, tmp_path, capsys):
    thesis_id = only_thesis(fund).thesis_id
    fund("thesis", "contract", thesis_id, "--from", write_contract(tmp_path))
    fund("check", thesis_id, "--observations", write_observations(tmp_path, [{
        "metric_id": "gross_margin", "period_basis": "ttm", "status": "available",
        "value": "0.62", "unit": "percent", "as_of": "2026-11-01",
    }]), "--as-of", "2026-11-05")

    capsys.readouterr()
    assert fund("checks", "--thesis", thesis_id) == 0
    output = capsys.readouterr().out
    assert "gross_margin_floor" in output
    assert "not_breached" in output


def test_checking_a_thesis_with_no_contract_is_refused(fund, tmp_path, capsys):
    thesis_id = only_thesis(fund).thesis_id
    capsys.readouterr()
    assert fund("check", thesis_id,
                "--observations", write_observations(tmp_path, [])) == 2
    assert "no monitoring contract" in capsys.readouterr().err
