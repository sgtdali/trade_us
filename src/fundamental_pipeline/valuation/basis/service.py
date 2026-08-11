"""Valuation-inputs service adapter: loads the exact market snapshot,
constructs FinancialBasis from exact authored periods, invokes the pure
resolver, derives identity, attaches hashes, revalidates, and performs
check/transactional-write behavior
(docs/valuation-t70-05-financial-basis-input-resolver-specification.md
Section 17).
"""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

from ...public.financial_basis import FinancialBasisError, FinancialPeriodRef, build_company_specific_basis, build_financial_basis
from ...public.method_basis import MethodBasisError, build_method_basis
from ..canonical import canonical_bytes
from ..catalogs import CatalogRegistry
from ..errors import ArtifactReferenceError
from ..identity import derive_artifact_id, derive_context_id
from ..paths import valuation_inputs_relative_path
from ..safe_json import read_safe_json
from ..schemas import iter_schema_errors
from ..transaction import TransactionResult, WriteTarget, check_transaction, execute_transaction
from ..validation.findings import Finding, sort_findings
from .input_resolver import ValuationInputRequest, resolve_valuation_inputs


class ValuationInputsGenerationResult:
    def __init__(self, *, findings: tuple[Finding, ...], valuation_inputs: dict[str, Any] | None, transaction: TransactionResult | None):
        self.findings = findings
        self.valuation_inputs = valuation_inputs
        self.transaction = transaction

    @property
    def ok(self) -> bool:
        return not any(f.severity in ("blocker", "error") for f in self.findings)


def generate_valuation_inputs(
    *,
    data_root: Path,
    ticker: str,
    as_of_date: str,
    cutoff_instant: str,
    financial_period_refs: tuple[FinancialPeriodRef, ...],
    market_snapshot_path: Path,
    context_projection: dict[str, Any],
    catalog_registry: CatalogRegistry,
    output_dir: Path,
    check_only: bool = False,
) -> ValuationInputsGenerationResult:
    findings: list[Finding] = []

    if not market_snapshot_path.exists():
        return ValuationInputsGenerationResult(
            findings=(Finding(rule_id="VAL-ID-101", severity="blocker", scope="bundle", reason_code="identity.resource_missing", message=f"missing market snapshot: {market_snapshot_path.name}"),),
            valuation_inputs=None, transaction=None,
        )
    snapshot = read_safe_json(market_snapshot_path, label=market_snapshot_path.name)
    if not isinstance(snapshot, dict):
        return ValuationInputsGenerationResult(
            findings=(Finding(rule_id="VAL-ID-103", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message="market snapshot root must be a JSON object"),),
            valuation_inputs=None, transaction=None,
        )
    schema_errors = list(iter_schema_errors("market-snapshot", snapshot))
    if schema_errors:
        for error in schema_errors:
            pointer = "/" + "/".join(str(p) for p in error.path)
            findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="error", scope="artifact", json_pointer=pointer, message=error.message))
        return ValuationInputsGenerationResult(findings=tuple(sort_findings(findings)), valuation_inputs=None, transaction=None)

    snapshot_reference = {
        "artifact_id": snapshot["artifact_id"],
        "artifact_type": "market_snapshot",
        "relative_path": f"data/market/{ticker}/{as_of_date}.json",
    }

    try:
        parsed_as_of = date_type.fromisoformat(as_of_date)
        financial_basis = build_financial_basis(
            data_root=data_root, ticker=ticker, as_of_date=parsed_as_of, financial_period_refs=financial_period_refs,
        )
        company_specific = build_company_specific_basis(
            data_root=data_root, ticker=ticker, as_of_date=parsed_as_of, financial_period_refs=financial_period_refs,
        )
        method_basis = build_method_basis(
            data_root=data_root, ticker=ticker, as_of_date=parsed_as_of, financial_period_refs=financial_period_refs,
        )
    except FinancialBasisError as exc:
        findings.append(Finding(rule_id="VAL-ID-101", severity="blocker", scope="bundle", reason_code="status.required_observation_missing", message=str(exc)))
        return ValuationInputsGenerationResult(findings=tuple(sort_findings(findings)), valuation_inputs=None, transaction=None)
    except MethodBasisError as exc:
        findings.append(Finding(rule_id="VAL-ID-101", severity="blocker", scope="bundle", reason_code="status.required_observation_missing", message=str(exc)))
        return ValuationInputsGenerationResult(findings=tuple(sort_findings(findings)), valuation_inputs=None, transaction=None)

    context_id = derive_context_id(context_projection)

    request = ValuationInputRequest(
        financial_basis=financial_basis,
        market_snapshot=snapshot,
        market_snapshot_reference=snapshot_reference,
        context_id=context_id,
        as_of_date=as_of_date,
        cutoff_instant=cutoff_instant,
        reporting_currency=context_projection["reporting_currency"],
        catalog_registry=catalog_registry,
        company_specific=company_specific,
        method_basis=method_basis,
    )
    result = resolve_valuation_inputs(request, catalog_registry)
    findings.extend(result.findings)
    if result.valuation_inputs is None:
        return ValuationInputsGenerationResult(findings=tuple(sort_findings(findings)), valuation_inputs=None, transaction=None)

    unhashed = dict(result.valuation_inputs)
    artifact_id = derive_artifact_id("valuation_inputs", {"ticker": ticker, "as_of_date": as_of_date, "context_id": context_id})
    unhashed["artifact_id"] = artifact_id

    final_errors = list(iter_schema_errors("valuation-inputs", unhashed))
    if final_errors:
        for error in final_errors:
            pointer = "/" + "/".join(str(p) for p in error.path)
            findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="error", scope="artifact", json_pointer=pointer, message=error.message))
        return ValuationInputsGenerationResult(findings=tuple(sort_findings(findings)), valuation_inputs=None, transaction=None)

    relative_path = valuation_inputs_relative_path(ticker, as_of_date, context_id)
    target = WriteTarget(relative_path=relative_path, content=canonical_bytes(unhashed))

    if check_only:
        transaction_result = check_transaction(output_dir, [target])
    else:
        transaction_result = execute_transaction(output_dir, [target])

    return ValuationInputsGenerationResult(findings=tuple(sort_findings(findings)), valuation_inputs=unhashed, transaction=transaction_result)


def validate_valuation_inputs(
    *,
    artifact_path: Path,
    catalog_registry: CatalogRegistry,
    resolve_dependencies: bool = False,
    root: Path | None = None,
) -> list[Finding]:
    """Independently recompute and verify a committed valuation-inputs
    artifact's schema and market-cap/net-debt/EV reconciliation. Never
    trusts a stored value merely because it is schema-valid.

    When ``resolve_dependencies`` is set, also loads the artifact
    referenced by ``market_snapshot_ref`` from ``root`` (required in that
    case) and verifies the exact-reference fields
    (``artifact_type``/``artifact_id``/``relative_path``)
    against the real dependency artifact -- a reference whose fields are
    individually well-formed but do not actually match the artifact they
    claim to identify (a forged or stale dependency) is rejected even
    though the artifact under validation remains independently
    schema-valid and self-hash-consistent.
    """
    if resolve_dependencies and root is None:
        raise ArtifactReferenceError("--resolve-dependencies requires an explicit --root")
    findings: list[Finding] = []
    if not artifact_path.exists():
        return [Finding(rule_id="VAL-ID-101", severity="blocker", scope="bundle", reason_code="identity.resource_missing", message=f"missing artifact: {artifact_path.name}")]

    try:
        artifact = read_safe_json(artifact_path, label=artifact_path.name)
    except Exception as exc:  # noqa: BLE001
        return [Finding(rule_id="VAL-ID-102", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message=str(exc))]

    if not isinstance(artifact, dict):
        return [Finding(rule_id="VAL-ID-103", severity="blocker", scope="bundle", reason_code="identity.malformed_json", message="artifact root must be a JSON object")]

    for error in iter_schema_errors("valuation-inputs", artifact):
        pointer = "/" + "/".join(str(p) for p in error.path)
        findings.append(Finding(rule_id="VAL-SCHEMA-001", severity="error", scope="artifact", json_pointer=pointer, message=error.message))
    if findings:
        return sort_findings(findings)

    identity = artifact.get("input_identity", {})
    expected_artifact_id = derive_artifact_id("valuation_inputs", {
        "ticker": identity.get("ticker", ""), "as_of_date": artifact.get("temporal_context", {}).get("as_of_date", ""), "context_id": identity.get("context_id", ""),
    })
    if artifact.get("artifact_id") != expected_artifact_id:
        findings.append(Finding(rule_id="VAL-ID-004", severity="blocker", scope="artifact", reason_code="identity.reference_invalid", message="recomputed artifact_id does not match stored artifact_id"))

    if resolve_dependencies:
        findings.extend(_verify_market_snapshot_dependency(artifact.get("market_snapshot_ref", {}), root=root))

    from decimal import Decimal
    ledger = {c["component_id"]: c for c in artifact.get("capital_structure_ledger", [])}
    for ev in artifact.get("ev_basis_family", []):
        if ev.get("status") != "available":
            continue

        # A lease-inclusive basis that is "available" while any of its own
        # lease-inclusive-scoped components is NOT "available" is exactly
        # the "missing represented as zero" forgery signature: the ledger
        # component being skipped from the sum (below) would otherwise let
        # a self-consistent forged EV (matching the ex-lease total, as if
        # the missing lease were silently zero) pass a pure arithmetic
        # recomputation. This is checked independently of the arithmetic
        # check so it cannot be defeated by also forging the ledger to
        # "agree" with a forged total.
        if ev["basis_type"] == "lease_inclusive":
            lease_components = [c for c in ledger.values() if c.get("lease_scope") == "lease_inclusive"]
            unresolved_lease = [c for c in lease_components if c.get("status") != "available"]
            if unresolved_lease:
                findings.append(Finding(
                    rule_id="VAL-ACC-007", severity="blocker", scope="artifact", reason_code="capital.lease_double_count",
                    message=f"{ev['ev_basis_id']}: lease_inclusive basis is 'available' but component(s) "
                            f"{sorted(c['component_id'] for c in unresolved_lease)} are not -- missing lease "
                            "data can never be silently treated as zero",
                ))
                continue

        try:
            # Canonical market-cap values can carry more than Decimal's
            # process-default 28 significant digits.  Recompute under the
            # governed arithmetic precision so a valid generated bridge is
            # not rejected merely because validation rounded an intermediate.
            with localcontext() as context:
                context.prec = 60
                # The EV ledger is denominated in the valuation reporting
                # currency.  ``native_total_market_cap`` can legitimately be
                # a different currency when a spot FX conversion is used.
                market_cap = ledger[ev["market_cap_ref"]]["amount"]
                expected = Decimal(market_cap["value"])
                for component in ledger.values():
                    if component["status"] != "available":
                        continue
                    if component["component_type"] == "ordinary_equity_market_cap":
                        continue
                    if ev["basis_type"] == "lease_exclusive" and component["lease_scope"] == "lease_inclusive":
                        continue
                    amount = Decimal(component["amount"]["value"])
                    expected = expected + amount if component["sign_in_bridge"] == "add" else expected - amount
            if Decimal(ev["enterprise_value"]["value"]) != expected:
                findings.append(Finding(rule_id="VAL-ACC-010", severity="blocker", scope="artifact", reason_code="capital.ev_bridge_reconciliation_failed", message=f"{ev['ev_basis_id']}: enterprise_value does not recompute from the capital ledger"))
        except (KeyError, TypeError):
            findings.append(Finding(rule_id="VAL-ACC-010", severity="blocker", scope="artifact", reason_code="capital.ev_bridge_reconciliation_failed", message=f"{ev.get('ev_basis_id')}: cannot recompute enterprise_value from the stored ledger"))

    return sort_findings(findings)


def _dependency_findings(reason_code: str, message: str) -> list[Finding]:
    """Every market_snapshot_ref dependency failure is reported under both
    T68.2's general lineage-graph rule (``VAL-LIN-002``, "ref/hash
    resolution", all graph refs) and T68.3's market-specific instance of
    the same failure (``VAL-MI-002``, "input /market_snapshot_ref: exact
    accepted snapshot ID+hash resolves") -- the two matrices name the same
    concrete check from a general and a domain-specific angle; neither
    rule ID is invented, both are drawn directly from their owning
    matrices."""
    return [
        Finding(rule_id="VAL-LIN-002", severity="blocker", scope="artifact", reason_code=reason_code, message=message),
        Finding(rule_id="VAL-MI-002", severity="blocker", scope="artifact", reason_code=reason_code, message=message),
    ]


def _verify_market_snapshot_dependency(reference: dict, *, root: Path) -> list[Finding]:
    """Load the artifact ``reference`` claims to identify from ``root`` and
    verify all four exact-reference fields against it. A reference that is
    individually well-formed but does not resolve to a matching real
    artifact is a dependency mismatch -- this is distinct from (and not
    caught by) the referencing artifact's own self-consistency checks
    above."""
    from ..references import safe_relative_path, verify_artifact_reference

    relative_path = reference.get("relative_path")
    if not relative_path:
        return _dependency_findings("identity.reference_invalid", "market_snapshot_ref has no relative_path to resolve")

    try:
        target_path = safe_relative_path(root, relative_path)
    except ArtifactReferenceError as exc:
        return _dependency_findings("identity.reference_invalid", f"market_snapshot_ref relative_path is unsafe: {exc}")

    if not target_path.exists():
        return _dependency_findings("identity.resource_missing", f"market_snapshot_ref target does not exist: {relative_path}")

    try:
        target = read_safe_json(target_path, label=target_path.name)
    except Exception as exc:  # noqa: BLE001
        return _dependency_findings("identity.malformed_json", f"market_snapshot_ref target is not valid JSON: {exc}")

    if not isinstance(target, dict):
        return _dependency_findings("identity.malformed_json", "market_snapshot_ref target root must be a JSON object")

    try:
        verify_artifact_reference(reference, target, relative_path, root=root)
    except ArtifactReferenceError as exc:
        return _dependency_findings("identity.reference_invalid", f"market_snapshot_ref does not match its target artifact: {exc}")

    return []
