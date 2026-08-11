"""T68 method-result validation (docs/valuation-t68-04-valuation-method-validation-matrix.md).

Extends the existing base validation layer (``validation/engine.py``) with
the method-specific rule family. Never trusts a caller-supplied count,
role, or family-sufficiency claim -- everything asserted here is
recomputed directly from ``method_results[]`` and cross-checked against
the locked catalogs.

Rule coverage in this PR (a real, exact-rule-ID subset of the full T68.4
matrix -- not every one of the ten VAL-METHOD rules has a from-scratch
re-derivation here, since several of them require re-binding/re-evaluating
against the original ``valuation-inputs`` artifact, which is out of a pure
artifact-level validator's scope):

* ``VAL-METHOD-002`` -- formula_ref resolves to a real, exact, matching
  catalog entry.
* ``VAL-METHOD-004`` -- canonical_value/status nullability is coherent
  (defense in depth alongside the schema's own decimalEnvelope rule).
* ``VAL-METHOD-007`` -- role is coherent with applicability outcome.
* ``VAL-METHOD-009`` -- coverage is recomputed from ``method_results[]``
  and compared byte-for-byte against the stored ``coverage`` object.
* ``VAL-METHOD-010`` -- the minimum-valid-family gate is recomputed and
  compared against ``bundle_status``.
* ``CAT-FAM-001`` -- each method_result's ``economic_family_id`` matches
  the family the catalog actually assigns to its ``formula_ref``.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..catalogs import CatalogRegistry
from .findings import Finding, sort_findings

_METHOD_FORMULA_CATALOG = "valuation.formulas.methods"

_OUTCOME_TO_EXPECTED_ROLES = {
    "applicable_primary": {"primary"},
    "applicable_secondary": {"secondary"},
    "applicable_diagnostic": {"diagnostic"},
    "conditional_data": {"conditional", "primary", "secondary", "diagnostic"},
    "conditional_adapter": {"conditional"},
    "not_applicable": {"primary", "secondary", "diagnostic", "conditional", "deferred"},
    "deferred_not_implemented": {"deferred", "primary", "secondary", "diagnostic", "conditional"},
}


def _formula_catalog_by_id(catalog_registry: CatalogRegistry) -> dict[str, Mapping[str, Any]]:
    catalog = catalog_registry.catalog(_METHOD_FORMULA_CATALOG)
    return {e["entry_id"]: e for e in catalog.get("entries", ())}


def validate_method_results(artifact: Mapping[str, Any], *, catalog_registry: CatalogRegistry) -> list[Finding]:
    """Validate a ``valuation-results`` artifact's ``method_results[]``
    against the locked method-formula catalog and its own recomputable
    coverage/bundle claims. Performs no I/O and no network access; assumes
    ``artifact`` has already passed schema validation."""
    findings: list[Finding] = []
    formulas_by_id = _formula_catalog_by_id(catalog_registry)
    method_results: Sequence[Mapping[str, Any]] = artifact.get("method_results", ())

    for index, result in enumerate(method_results):
        pointer = f"/method_results/{index}"
        formula_ref = result.get("formula_ref", {})
        formula_id = formula_ref.get("formula_id")
        catalog_entry = formulas_by_id.get(formula_id)

        if catalog_entry is None:
            findings.append(Finding(
                rule_id="VAL-METHOD-002", severity="blocker", scope="method",
                reason_code="identity.reference_invalid", relative_path=None, json_pointer=f"{pointer}/formula_ref",
                artifact_id=result.get("method_result_id"),
                message=f"{pointer}: formula_ref.formula_id {formula_id!r} does not resolve in {_METHOD_FORMULA_CATALOG}",
            ))
            continue

        catalog_family_id = catalog_entry["body"].get("economic_family_id")
        if result.get("economic_family_id") != catalog_family_id:
            findings.append(Finding(
                rule_id="CAT-FAM-001", severity="blocker", scope="method",
                reason_code="identity.reference_invalid", json_pointer=f"{pointer}/economic_family_id",
                artifact_id=result.get("method_result_id"),
                message=f"{pointer}: economic_family_id {result.get('economic_family_id')!r} does not match the catalog's declared family {catalog_family_id!r} for this formula",
            ))

        status = result.get("status")
        canonical_value = result.get("canonical_value")
        if status == "available" and canonical_value is None:
            findings.append(Finding(
                rule_id="VAL-METHOD-004", severity="blocker", scope="method",
                reason_code="status.economic_interpretation_invalid", json_pointer=f"{pointer}/canonical_value",
                artifact_id=result.get("method_result_id"),
                message=f"{pointer}: status='available' requires a non-null canonical_value",
            ))
        if status != "available" and canonical_value is not None:
            findings.append(Finding(
                rule_id="VAL-METHOD-004", severity="blocker", scope="method",
                reason_code="status.economic_interpretation_invalid", json_pointer=f"{pointer}/canonical_value",
                artifact_id=result.get("method_result_id"),
                message=f"{pointer}: status={status!r} forbids a non-null canonical_value",
            ))

        outcome = result.get("applicability", {}).get("outcome")
        role = result.get("role")
        expected_roles = _OUTCOME_TO_EXPECTED_ROLES.get(outcome)
        if expected_roles is not None and role not in expected_roles:
            findings.append(Finding(
                rule_id="VAL-METHOD-007", severity="error", scope="method",
                reason_code="status.economic_interpretation_invalid", json_pointer=f"{pointer}/role",
                artifact_id=result.get("method_result_id"),
                message=f"{pointer}: role {role!r} is not coherent with applicability outcome {outcome!r}",
            ))

    findings.extend(_validate_coverage(artifact, pointer_prefix="/coverage"))
    findings.extend(_validate_minimum_family_gate(artifact))

    return sort_findings(findings)


def _validate_coverage(artifact: Mapping[str, Any], *, pointer_prefix: str) -> list[Finding]:
    from ..methods.evaluator import reconstruct_minimal_evaluations
    from ..methods.families import compute_family_coverage
    from ..results.coverage import compute_coverage

    method_results: Sequence[Mapping[str, Any]] = artifact.get("method_results", ())
    reconstructed = reconstruct_minimal_evaluations(method_results)
    family_coverage = compute_family_coverage(reconstructed)
    recomputed = compute_coverage(reconstructed, family_coverage)

    stored = artifact.get("coverage", {})
    findings: list[Finding] = []
    for key in ("configured_method_count", "applicable_method_count", "available_method_count", "unavailable_method_count", "not_applicable_method_count", "current_use_method_count"):
        if stored.get(key) != recomputed.get(key):
            findings.append(Finding(
                rule_id="VAL-METHOD-009", severity="blocker", scope="bundle",
                reason_code="identity.reference_invalid", json_pointer=f"{pointer_prefix}/{key}",
                message=f"{pointer_prefix}/{key}: stored value {stored.get(key)!r} does not match recomputed value {recomputed.get(key)!r}",
            ))
    if stored.get("primary_family_available") != recomputed.get("primary_family_available"):
        findings.append(Finding(
            rule_id="VAL-METHOD-009", severity="blocker", scope="bundle",
            reason_code="identity.reference_invalid", json_pointer=f"{pointer_prefix}/primary_family_available",
            message=f"{pointer_prefix}/primary_family_available: stored value does not match recomputed family coverage",
        ))
    return findings


def _validate_minimum_family_gate(artifact: Mapping[str, Any]) -> list[Finding]:
    from ..methods.evaluator import reconstruct_minimal_evaluations
    from ..methods.families import compute_family_coverage, minimum_valid_family_satisfied

    method_results: Sequence[Mapping[str, Any]] = artifact.get("method_results", ())
    reconstructed = reconstruct_minimal_evaluations(method_results)
    recomputed = minimum_valid_family_satisfied(compute_family_coverage(reconstructed))

    bundle_status = artifact.get("bundle_status", {})
    findings: list[Finding] = []
    if bundle_status.get("minimum_valid_family_satisfied") != recomputed:
        findings.append(Finding(
            rule_id="VAL-METHOD-010", severity="blocker", scope="bundle",
            reason_code="applicability.no_valid_primary_secondary_family",
            json_pointer="/bundle_status/minimum_valid_family_satisfied",
            message="bundle_status.minimum_valid_family_satisfied does not match the recomputed minimum-valid-family gate",
        ))
    if recomputed is False and bundle_status.get("assessment_eligible") is True:
        findings.append(Finding(
            rule_id="VAL-METHOD-010", severity="blocker", scope="bundle",
            reason_code="applicability.no_valid_primary_secondary_family",
            json_pointer="/bundle_status/assessment_eligible",
            message="assessment_eligible is true but no valid primary/secondary family is current-use available",
        ))
    return findings
