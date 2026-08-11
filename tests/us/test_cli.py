import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import fundamental_pipeline_us.cli as cli
from fundamental_pipeline_us.cli import _peer_ready_tickers, build_parser
from fundamental_pipeline_us.errors import UsPipelineError


def _write_universe(workspace: Path, tickers: list[str]) -> None:
    path = (
        workspace / "config" / "valuation" / "comparison" / "peer-universes" /
        "consumer-staples.json"
    )
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"members": [{"ticker": ticker} for ticker in tickers]}),
        encoding="utf-8",
    )


def test_run_company_accepts_peer_enrichment_flag():
    args = build_parser().parse_args([
        "run-company",
        "--ticker", "KO",
        "--as-of", "2026-08-03",
        "--cutoff-instant", "2026-08-03T23:59:59Z",
        "--enrich-peers",
    ])

    assert args.enrich_peers is True


def test_peer_ready_tickers_skip_unprocessed_universe_members(tmp_path: Path):
    workspace = tmp_path / "us"
    _write_universe(workspace, ["KO", "PEP", "ADM"])
    for ticker in ("KO", "ADM"):
        result = (
            workspace / "data" / "valuation-results" / ticker / "2026-08-03" /
            "ctx-test" / "current.json"
        )
        result.parent.mkdir(parents=True)
        result.write_text("{}", encoding="utf-8")

    assert _peer_ready_tickers(
        workspace=workspace,
        as_of_date="2026-08-03",
        required_ticker="ADM",
    ) == ["ADM", "KO"]


def test_peer_ready_tickers_accept_multiple_same_date_contexts(tmp_path: Path):
    workspace = tmp_path / "us"
    _write_universe(workspace, ["KO"])
    for context_id in ("ctx-old", "ctx-new"):
        result = (
            workspace / "data" / "valuation-results" / "KO" / "2026-08-03" /
            context_id / "current.json"
        )
        result.parent.mkdir(parents=True)
        result.write_text("{}", encoding="utf-8")

    assert _peer_ready_tickers(
        workspace=workspace, as_of_date="2026-08-03", required_ticker="KO",
    ) == ["KO"]


def test_peer_ready_tickers_requires_subject_membership(tmp_path: Path):
    workspace = tmp_path / "us"
    _write_universe(workspace, ["KO"])

    with pytest.raises(UsPipelineError, match="add the company"):
        _peer_ready_tickers(
            workspace=workspace,
            as_of_date="2026-08-03",
            required_ticker="ADM",
        )


def test_run_company_wires_peer_enrichment_into_single_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
):
    workspace = tmp_path / "us"
    _write_universe(workspace, ["KO"])
    result_path = (
        workspace / "data" / "valuation-results" / "KO" / "2026-08-03" /
        "ctx-test" / "current.json"
    )
    result_path.parent.mkdir(parents=True)
    result_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(cli, "_client", lambda args: object())
    monkeypatch.setattr(
        "fundamental_pipeline_us.workflow.run_company_workflow",
        lambda **kwargs: {"ticker": kwargs["ticker"]},
    )
    monkeypatch.setattr(
        "fundamental_pipeline_us.peers.generate_us_peer_comparisons",
        lambda **kwargs: {"ticker_count": len(kwargs["tickers"])},
    )
    args = SimpleNamespace(
        workspace=str(workspace), ticker="KO", as_of="2026-08-03",
        cutoff_instant="2026-08-03T23:59:59Z", enrich_peers=True,
    )

    assert cli.cmd_run_company(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"ticker": "KO", "peers": {"ticker_count": 1}}
