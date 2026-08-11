from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import UsPipelineError


VALID_JUDGMENTS = {"tez_var", "sartli", "alinmaz"}
VALID_REASONS = {
    "veri_guvensiz", "finansal_kirilganlik", "tez_yok",
    "degerleme_desteksiz", "belirsizlik_asiri",
}
VALID_CONFIDENCE = {"dusuk", "orta", "yuksek"}
VALID_DIRECTIONS = {"increase", "decrease", "stay_above", "stay_below"}
CONFIDENCE_ALIASES = {
    "low": "dusuk", "low confidence": "dusuk",
    "medium": "orta", "medium confidence": "orta", "moderate": "orta",
    "moderate confidence": "orta",
    "high": "yuksek", "high confidence": "yuksek",
}
_DEADLINE_RE = re.compile(r"^20\d{2}-(?:Q[1-4]|FY)$")
_SECTION_RE = re.compile(r"^##\s+(\d+)\.", re.MULTILINE)
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])[-+]?\$?\d[\d,]*(?:\.\d+)?%?")


def _read(path: Path) -> str:
    if not path.is_file():
        raise UsPipelineError(f"required file not found: {path}")
    return path.read_text(encoding="utf-8")


def _strip_comment_blocks(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()


def _render(template: str, replacements: dict[str, str]) -> str:
    rendered = _strip_comment_blocks(template)
    for key, value in replacements.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    unresolved = sorted(set(re.findall(r"{{([A-Z_]+)}}", rendered)))
    if unresolved:
        raise UsPipelineError(f"unresolved prompt placeholders: {unresolved}")
    return rendered.strip() + "\n"


def _period_sort_key(payload: dict[str, Any], path: Path) -> tuple[str, str]:
    return str(payload.get("period_end") or ""), path.name


def _metric_dictionary(workspace: Path, ticker: str) -> tuple[dict[str, float], str]:
    candidates: list[tuple[dict[str, Any], Path]] = []
    for direct_path in (workspace / "data" / "financial" / ticker).glob("*.json"):
        if direct_path.name.endswith("-derived-ratios.json"):
            continue
        payload = json.loads(_read(direct_path))
        derived_path = direct_path.with_name(direct_path.stem + "-derived-ratios.json")
        if derived_path.is_file():
            candidates.append((payload, derived_path))
    if not candidates:
        raise UsPipelineError(f"{ticker}: no derived-ratio period found")
    for _, path in sorted(
        candidates, key=lambda item: _period_sort_key(item[0], item[1]), reverse=True,
    ):
        payload = json.loads(_read(path))
        metrics: dict[str, float] = {}
        lines = []
        for group in payload.values():
            if not isinstance(group, list):
                continue
            for item in group:
                if not isinstance(item, dict) or isinstance(item.get("value"), bool):
                    continue
                value = item.get("value")
                metric_id = item.get("metric_id")
                if not metric_id or not isinstance(value, (int, float)):
                    continue
                metrics[str(metric_id)] = float(value)
                description = str(item.get("formula_description") or "").strip()
                lines.append(
                    f"- `{metric_id}`: {value} {item.get('unit', '')}; "
                    f"period {item.get('period', payload.get('period', 'unknown'))}. {description}"
                )
        if metrics:
            return metrics, "\n".join(lines)
    raise UsPipelineError(f"{ticker}: no derived-ratio period contains numeric metrics")


def _history(workspace: Path, ticker: str, as_of: str) -> str:
    root = workspace / "data" / "decisions" / ticker
    records = []
    if root.is_dir():
        for period_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            if period_dir.name >= as_of:
                continue
            path = period_dir / "decision.json"
            if not path.is_file():
                path = period_dir / "layer2-direct.json"
            if not path.is_file():
                path = period_dir / "layer2.json"
            if path.is_file():
                records.append(json.loads(_read(path)))
    return json.dumps(records, ensure_ascii=False, indent=2) if records else "No prior official decision."


def _extract_last_json(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    matches: list[tuple[int, int, dict[str, Any]]] = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, consumed = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            matches.append((index + consumed, index, value))
    if not matches:
        raise UsPipelineError("LLM output did not contain a valid JSON object")
    # The final complete object reaches furthest into stdout. For nested objects
    # with the same end position, prefer the earliest opening brace.
    return max(matches, key=lambda item: (item[0], -item[1]))[2]


def _sections(report: str) -> dict[str, str]:
    matches = list(_SECTION_RE.finditer(report))
    result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(report)
        result[match.group(1)] = report[match.start():end]
    return result


def _section_number(value: Any) -> str:
    match = re.search(r"\d+", str(value))
    return match.group(0) if match else ""


def _numbers(text: str) -> list[float]:
    values = []
    for token in _NUMBER_RE.findall(text):
        cleaned = token.replace("$", "").replace("%", "").replace(",", "")
        try:
            values.append(float(cleaned))
        except ValueError:
            pass
    return values


def _negative_value_expressed_in_words(text: str, expected: float) -> bool:
    if expected >= 0:
        return False
    magnitude = re.escape(f"{abs(expected):g}")
    return re.search(
        rf"\b(?:down|declined|fell|decreased|contracted)\s+(?:by\s+)?{magnitude}(?:0*)%?\b",
        text,
        flags=re.IGNORECASE,
    ) is not None


def _numeric_evidence_checks(payload: dict[str, Any], report: str) -> list[dict[str, Any]]:
    sections = _sections(report)
    checks = []
    for index, evidence in enumerate(payload.get("belirleyici_veriler", [])):
        if not isinstance(evidence, dict) or evidence.get("tur") != "sayisal":
            continue
        value = evidence.get("reported_value")
        section = _section_number(evidence.get("report_section"))
        valid_type = isinstance(value, (int, float)) and not isinstance(value, bool)
        found = False
        if valid_type and section in sections:
            expected = float(value)
            found = any(abs(candidate - expected) <= max(1e-6, abs(expected) * 1e-6)
                        for candidate in _numbers(sections[section]))
            if not found:
                found = _negative_value_expressed_in_words(sections[section], expected)
        checks.append({
            "evidence_index": index,
            "reported_value": value,
            "report_section": section,
            "status": "verified" if found else "not_verified",
            "reason": None if found else "numeric value not found at the displayed scale in the cited section",
        })
    return checks


def _validate_decision(payload: dict[str, Any], metrics: dict[str, float]) -> None:
    errors = []
    judgment = payload.get("yargi")
    if judgment not in VALID_JUDGMENTS:
        errors.append("invalid yargi")
    reason = payload.get("alinmaz_nedeni")
    if judgment == "alinmaz" and reason not in VALID_REASONS:
        errors.append("alinmaz requires a valid alinmaz_nedeni")
    if judgment != "alinmaz" and reason is not None:
        errors.append("alinmaz_nedeni must be null unless yargi is alinmaz")
    if payload.get("guven") not in VALID_CONFIDENCE:
        errors.append(f"invalid guven {payload.get('guven')!r}")
    evidence = payload.get("belirleyici_veriler")
    if not isinstance(evidence, list) or not 3 <= len(evidence) <= 5:
        errors.append("belirleyici_veriler must contain 3-5 items")
    tests = payload.get("tez_testleri")
    if not isinstance(tests, list):
        errors.append("tez_testleri must be an array")
        tests = []
    if judgment == "alinmaz" and tests:
        errors.append("alinmaz must not contain thesis tests")
    for index, test in enumerate(tests):
        if not isinstance(test, dict):
            errors.append(f"tez_testleri[{index}] must be an object")
            continue
        metric_id = test.get("metric_id")
        if metric_id not in metrics:
            errors.append(f"tez_testleri[{index}] uses unknown metric_id {metric_id!r}")
        baseline = test.get("baseline")
        if not isinstance(baseline, (int, float)) or isinstance(baseline, bool):
            errors.append(f"tez_testleri[{index}] baseline must be numeric")
        elif metric_id in metrics and abs(float(baseline) - metrics[metric_id]) > max(1e-6, abs(metrics[metric_id]) * 1e-6):
            errors.append(f"tez_testleri[{index}] baseline does not match the metric dictionary")
        if test.get("expected_direction") not in VALID_DIRECTIONS:
            errors.append(f"tez_testleri[{index}] has invalid expected_direction")
        if not _DEADLINE_RE.fullmatch(str(test.get("deadline_period", ""))):
            errors.append(f"tez_testleri[{index}] has invalid deadline_period")
        if not str(test.get("failure_condition") or "").strip():
            errors.append(f"tez_testleri[{index}] has empty failure_condition")
    if errors:
        raise UsPipelineError("; ".join(errors))


def _canonicalize_contract_enums(payload: dict[str, Any]) -> dict[str, Any]:
    normalizations = []
    confidence = payload.get("guven")
    normalized_confidence = confidence.strip().casefold() if isinstance(confidence, str) else confidence
    if normalized_confidence in VALID_CONFIDENCE and normalized_confidence != confidence:
        payload["guven"] = normalized_confidence
        normalizations.append({
            "field": "guven", "from": confidence, "to": payload["guven"],
            "reason": "lossless case-and-whitespace normalization",
        })
    elif normalized_confidence in CONFIDENCE_ALIASES:
        payload["guven"] = CONFIDENCE_ALIASES[normalized_confidence]
        normalizations.append({
            "field": "guven", "from": confidence, "to": payload["guven"],
            "reason": "lossless English-to-canonical enum mapping",
        })
    if normalizations:
        payload["contract_normalizations"] = normalizations
    return payload


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_sha(repo_root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True,
        capture_output=True, check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _write_new(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise UsPipelineError(f"immutable decision already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _call_codex_direct(
    *, prompt: str, schema_path: Path, timeout_seconds: int,
) -> tuple[dict[str, Any], str]:
    if shutil.which("codex.cmd") is None:
        raise UsPipelineError("required CLI is unavailable: codex.cmd")
    with tempfile.TemporaryDirectory(prefix="us-direct-decision-") as temp_dir:
        temp_root = Path(temp_dir)
        output_path = temp_root / "final.json"
        try:
            completed = subprocess.run(
                [
                    "codex.cmd", "exec", "--model", "gpt-5.6-sol",
                    "-c", 'model_reasoning_effort="high"',
                    "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral",
                    "--ignore-user-config",
                    "--output-schema", str(schema_path.resolve()),
                    "--output-last-message", str(output_path),
                ],
                cwd=temp_root, input=prompt, text=True, encoding="utf-8",
                errors="replace", capture_output=True, timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            # subprocess.TimeoutExpired derives from SubprocessError, NOT from
            # OSError or TimeoutError, so callers that retry on those never saw
            # it and a single slow call killed a whole run (2026-08-04, v4
            # portfolio month 2025-01). Re-raise on this module's own error
            # boundary so the transient-failure retries actually cover it.
            raise UsPipelineError(
                f"codex-sol did not respond within {timeout_seconds} seconds"
            ) from exc
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout)[-3000:]
            raise UsPipelineError(f"codex-sol exited {completed.returncode}: {tail}")
        if not output_path.is_file():
            raise UsPipelineError("codex-sol did not write its final response")
        payload = _extract_last_json(_read(output_path))
    return _canonicalize_contract_enums(payload), completed.stderr


def _validate_direct_decision(payload: dict[str, Any], metrics: dict[str, float]) -> None:
    _validate_decision(payload, metrics)
    if not str(payload.get("gerekce") or "").strip():
        raise UsPipelineError("direct decision gerekce is required")


def run_decisions(
    *, workspace: Path, as_of: str, tickers: list[str], max_workers: int = 3,
    timeout_seconds: int = 900,
    report_paths: dict[str, Path] | None = None,
    decision_paths: dict[str, Path] | None = None,
    metric_inputs: dict[str, tuple[dict[str, float], str]] | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    repo_root = workspace.parent
    prompt_root = workspace / "config" / "karar-katmani" / "prompts"
    schema_path = workspace / "config" / "karar-katmani" / "schemas" / "direct-decision.v1.schema.json"
    template = _read(prompt_root / "direct.v1.en.md")
    json.loads(_read(schema_path))

    def run_one(ticker: str) -> tuple[str, Path]:
        target = (
            decision_paths[ticker] if decision_paths is not None
            else workspace / "data" / "decisions" / ticker / as_of / "decision.json"
        )
        if target.exists():
            return ticker, target
        report_path = (
            report_paths[ticker] if report_paths is not None
            else workspace / "reports" / "valuation" / ticker / f"{as_of}-valuation-analysis.md"
        )
        report = _read(report_path)
        metrics, metric_text = (
            metric_inputs[ticker] if metric_inputs is not None
            else _metric_dictionary(workspace, ticker)
        )
        prompt = _render(template, {
            "TICKER": ticker, "AS_OF": as_of, "REPORT": report,
            "METRIC_DICTIONARY": metric_text,
        })
        payload, stderr = _call_codex_direct(
            prompt=prompt, schema_path=schema_path, timeout_seconds=timeout_seconds,
        )
        _validate_direct_decision(payload, metrics)
        checks = _numeric_evidence_checks(payload, report)
        payload["decision_mode"] = "direct_report_single_model"
        payload["validation"] = {"numeric_evidence": checks}
        payload["provenance"] = {
            "decision_stage": "single", "role": "official_company_decision", "market": "US",
            "ticker": ticker, "as_of": as_of,
            "model_key": "codex", "model_id": "gpt-5.6-sol",
            "reasoning_effort": "high", "prompt_version": "us-direct.v1",
            "prompt_sha256": _sha256(prompt), "report_sha256": _sha256(report),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo_commit_sha": _git_sha(repo_root),
            "source_boundary": "valuation_report_only",
            "stderr_tail": stderr[-500:] if stderr else "",
        }
        _write_new(target, payload)
        return ticker, target

    paths: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_one, ticker): ticker for ticker in tickers}
        for future in as_completed(futures):
            ticker, path = future.result()
            paths[ticker] = str(path)
    return {"tickers": tickers, "as_of": as_of, "model": "gpt-5.6-sol", "reasoning_effort": "high", "decisions": paths}


def _first_sentence(text: str) -> str:
    stripped = " ".join(text.split())
    match = re.match(r".*?[.!?](?:\s|$)", stripped)
    return match.group(0).strip() if match else stripped


def _validate_portfolio_decision(
    payload: dict[str, Any], *, candidate_tickers: set[str], rejected_tickers: set[str],
) -> None:
    errors = []
    positions = payload.get("pozisyonlar")
    if not isinstance(positions, list) or len(positions) > 2:
        errors.append("pozisyonlar must be an array with at most two positions")
        positions = []
    selected = []
    for index, position in enumerate(positions):
        if not isinstance(position, dict):
            errors.append(f"pozisyonlar[{index}] must be an object")
            continue
        ticker = position.get("ticker")
        selected.append(ticker)
        if ticker not in candidate_tickers:
            errors.append(f"pozisyonlar[{index}] ticker {ticker!r} is not a full candidate")
        if position.get("agirlik") != 0.5:
            errors.append(f"pozisyonlar[{index}] weight must equal 0.5")
        if position.get("karar") != "ekle":
            errors.append(f"pozisyonlar[{index}] karar must equal ekle")
    if len(selected) != len(set(selected)):
        errors.append("portfolio contains duplicate tickers")
    expected_cash = 1.0 - 0.5 * len(positions)
    cash = payload.get("nakit_orani")
    if not isinstance(cash, (int, float)) or abs(float(cash) - expected_cash) > 1e-9:
        errors.append(f"nakit_orani must equal {expected_cash}")
    if expected_cash > 0 and not str(payload.get("nakit_gerekcesi") or "").strip():
        errors.append("cash allocation requires nakit_gerekcesi")
    candidate_rejections = payload.get("reddedilen_adaylar")
    rejected_candidate_tickers = {
        item.get("ticker") for item in candidate_rejections if isinstance(item, dict)
    } if isinstance(candidate_rejections, list) else set()
    expected_candidate_rejections = candidate_tickers - set(selected)
    if rejected_candidate_tickers != expected_candidate_rejections:
        errors.append(
            "reddedilen_adaylar must contain every unselected full candidate exactly once"
        )
    objections = payload.get("itiraz_edilen_elemeler")
    objection_tickers = {
        item.get("ticker") for item in objections if isinstance(item, dict)
    } if isinstance(objections, list) else set()
    if not objection_tickers <= rejected_tickers:
        errors.append("itiraz_edilen_elemeler contains a ticker not in rejected summaries")
    if payload.get("guven") not in VALID_CONFIDENCE:
        errors.append("invalid portfolio guven")
    if not str(payload.get("portfoy_gerekcesi") or "").strip():
        errors.append("portfoy_gerekcesi is required")
    if errors:
        raise UsPipelineError("; ".join(errors))


def run_portfolio_decision(
    *, workspace: Path, as_of: str, tickers: list[str], timeout_seconds: int = 900,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    repo_root = workspace.parent
    target = workspace / "data" / "portfolio" / as_of / "decision.json"
    if target.exists():
        return {"as_of": as_of, "portfolio_decision": str(target), "status": "existing"}
    prompt_root = workspace / "config" / "karar-katmani" / "prompts"
    schema_path = workspace / "config" / "karar-katmani" / "schemas" / "portfolio-decision.v1.schema.json"
    template = _read(prompt_root / "portfolio.v1.en.md")
    json.loads(_read(schema_path))

    full_candidates: dict[str, dict[str, Any]] = {}
    rejected_summaries = []
    input_hashes = {}
    for ticker in tickers:
        path = workspace / "data" / "decisions" / ticker / as_of / "decision.json"
        text = _read(path)
        input_hashes[ticker] = _sha256(text)
        decision = json.loads(text)
        if decision.get("yargi") == "alinmaz":
            rejected_summaries.append({
                "ticker": ticker,
                "alinmaz_nedeni": decision.get("alinmaz_nedeni"),
                "ozet": _first_sentence(str(decision.get("gerekce") or "")),
            })
        else:
            full_candidates[ticker] = {
                key: value for key, value in decision.items()
                if key not in {"provenance", "validation", "contract_normalizations"}
            }
    if not full_candidates:
        raise UsPipelineError("portfolio decision requires at least one full candidate")
    prompt = _render(template, {
        "AS_OF": as_of,
        "CANDIDATES": json.dumps(full_candidates, ensure_ascii=False, indent=2),
        "REJECTED_SUMMARIES": json.dumps(rejected_summaries, ensure_ascii=False, indent=2),
    })
    payload, stderr = _call_codex_direct(
        prompt=prompt, schema_path=schema_path, timeout_seconds=timeout_seconds,
    )
    _validate_portfolio_decision(
        payload, candidate_tickers=set(full_candidates),
        rejected_tickers={item["ticker"] for item in rejected_summaries},
    )
    payload["devir_orani"] = sum(float(item["agirlik"]) for item in payload["pozisyonlar"])
    payload["provenance"] = {
        "decision_stage": "portfolio", "market": "US", "as_of": as_of,
        "model_key": "codex", "model_id": "gpt-5.6-sol",
        "reasoning_effort": "high", "prompt_version": "us-portfolio.v1",
        "prompt_sha256": _sha256(prompt), "company_decision_sha256": input_hashes,
        "full_candidate_tickers": sorted(full_candidates),
        "rejected_summary_tickers": sorted(item["ticker"] for item in rejected_summaries),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_commit_sha": _git_sha(repo_root),
        "source_boundary": "canonical_company_decisions_only",
        "stderr_tail": stderr[-500:] if stderr else "",
    }
    _write_new(target, payload)
    return {"as_of": as_of, "portfolio_decision": str(target), "status": "generated"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m fundamental_pipeline_us.decisions")
    parser.add_argument("--workspace", default="us")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_decisions(
            workspace=Path(args.workspace), as_of=args.as_of,
            tickers=[ticker.upper() for ticker in args.tickers],
            max_workers=args.max_workers, timeout_seconds=args.timeout_seconds,
        )
    except (UsPipelineError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
