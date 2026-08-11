"""The method-formula catalog compiler (docs/valuation-t71-02-formula-ast-catalog-compilation-specification.md
Section 5).

``compile_method_catalog`` runs, in deterministic order, for every entry in
the ``valuation.formulas.methods`` catalog:

    lock/hash/lifecycle verification (via CatalogRegistry.select_entry)
    -> required-field / meta-contract shape check
    -> unique symbol-table construction
    -> AST allowlist and resource-limit checks (methods.ast.parse_ast)
    -> operand declaration/use checks
    -> ordered guard coverage checks (methods.guards)
    -> unit/scale inference (methods.units)
    -> output-type validation
    -> method/family/variant consistency (economic family must be one of
       the shared, T71-approved family vocabulary -- this is also what
       keeps a would-be scenario/DCF formula from silently compiling under
       T71 current capability)
    -> status/reason mapping validation
    -> immutable compiled method plan

A compile failure raises :class:`~fundamental_pipeline.valuation.errors.MethodCatalogError`
or :class:`~fundamental_pipeline.valuation.errors.FormulaCompileError` (never
a raw ``KeyError``/``TypeError``) and blocks the whole catalog compile --
this module produces no partial/best-effort registry.

This module performs no operand binding and no evaluation: it never reads a
``valuation-inputs`` artifact and never touches the filesystem or network.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..catalogs import CatalogRegistry
from ..errors import MethodCatalogError
from .ast import iter_operand_symbols, parse_ast
from .guards import check_division_guarded, check_guard_targets_declared, parse_guard_plan
from .models import CompiledMethodPlan, CompiledMethodRegistry, OperandDeclaration
from .units import check_unit_equation

METHOD_CATALOG_ID = "valuation.formulas.methods"
SHARED_CATALOG_ID = "valuation.catalogs.shared"

_REQUIRED_BODY_FIELDS = (
    "method_id", "economic_family_id", "variant_dimensions", "operand_declarations",
    "guard_plan", "expression_ast", "unit_equation", "output_semantics",
    "sign_policy", "arithmetic_context_ref", "display_policy_ref", "reason_mapping",
)

_ALLOWED_REQUIREDNESS = frozenset({"required", "conditional", "optional_diagnostic"})
_ALLOWED_ALLOWED_SIGN = frozenset({"positive", "nonnegative", "signed"})


def _shared_vocab(shared_catalog: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    entries = shared_catalog.get("entries", ())
    return {entry["entry_id"]: entry for entry in entries}


def _parse_operand_declarations(raw: Any) -> tuple[OperandDeclaration, ...]:
    if not isinstance(raw, (list, tuple)) or not raw:
        raise MethodCatalogError("operand_declarations must be a non-empty array")
    seen: set[str] = set()
    declarations: list[OperandDeclaration] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise MethodCatalogError(f"operand_declarations[{index}] must be an object")
        operand_id = item.get("operand_id")
        if not isinstance(operand_id, str) or not operand_id:
            raise MethodCatalogError(f"operand_declarations[{index}] missing non-empty operand_id")
        if operand_id in seen:
            raise MethodCatalogError(f"operand_declarations declares duplicate operand_id: {operand_id!r}")
        seen.add(operand_id)
        requiredness = item.get("requiredness")
        if requiredness not in _ALLOWED_REQUIREDNESS:
            raise MethodCatalogError(f"operand_declarations[{index}] has unknown requiredness: {requiredness!r}")
        unit_family = item.get("unit_family")
        if not isinstance(unit_family, str) or not unit_family:
            raise MethodCatalogError(f"operand_declarations[{index}] missing non-empty unit_family")
        allowed_sign = item.get("allowed_sign")
        if allowed_sign not in _ALLOWED_ALLOWED_SIGN:
            raise MethodCatalogError(f"operand_declarations[{index}] has unknown allowed_sign: {allowed_sign!r}")
        declarations.append(OperandDeclaration(
            operand_id=operand_id, requiredness=requiredness, unit_family=unit_family,
            allowed_sign=allowed_sign, claim_rule=item.get("claim_rule"), period_rule=item.get("period_rule"),
        ))
    return tuple(declarations)


def _compile_one_entry(entry: Mapping[str, Any], *, shared_vocab: Mapping[str, Mapping[str, Any]]) -> CompiledMethodPlan:
    formula_id = entry["entry_id"]
    formula_version = entry["entry_version"]
    body = entry.get("body")
    if not isinstance(body, Mapping):
        raise MethodCatalogError(f"{formula_id}: catalog entry has no 'body' object")

    missing = [f for f in _REQUIRED_BODY_FIELDS if f not in body]
    if missing:
        raise MethodCatalogError(f"{formula_id}: body missing required meta-contract field(s): {sorted(missing)}")

    operand_declarations = _parse_operand_declarations(body["operand_declarations"])
    declared_symbols = [decl.operand_id for decl in operand_declarations]

    expr = parse_ast(body["expression_ast"])

    referenced = iter_operand_symbols(expr)
    referenced_set = set(referenced)
    declared_set = set(declared_symbols)
    undeclared = referenced_set - declared_set
    if undeclared:
        raise MethodCatalogError(f"{formula_id}: AST references undeclared operand symbol(s): {sorted(undeclared)}")
    unused = declared_set - referenced_set
    if unused:
        raise MethodCatalogError(f"{formula_id}: declared operand(s) never referenced by the AST (T71 has no guard-only operands yet): {sorted(unused)}")

    guard_plan = parse_guard_plan(body["guard_plan"])
    check_guard_targets_declared(guard_plan, declared_symbols)
    check_division_guarded(expr, guard_plan)

    operand_units = {decl.operand_id: decl.unit_family for decl in operand_declarations}
    output_semantics = body["output_semantics"]
    if not isinstance(output_semantics, Mapping) or "unit" not in output_semantics:
        raise MethodCatalogError(f"{formula_id}: output_semantics must declare a 'unit'")
    check_unit_equation(expr, operand_units=operand_units, declared_output_unit=output_semantics["unit"])

    economic_family_id = body["economic_family_id"]
    family_vocab_entry = shared_vocab.get("shared.vocab.economic_family")
    if family_vocab_entry is None:
        raise MethodCatalogError("shared catalog is missing 'shared.vocab.economic_family'")
    if economic_family_id not in family_vocab_entry["body"]["values"]:
        raise MethodCatalogError(
            f"{formula_id}: economic_family_id {economic_family_id!r} is not a member of the T71-approved "
            "family vocabulary (this also blocks any not-yet-approved scenario/DCF family from compiling)"
        )

    arithmetic_context_ref = body["arithmetic_context_ref"]
    if arithmetic_context_ref not in shared_vocab:
        raise MethodCatalogError(f"{formula_id}: arithmetic_context_ref {arithmetic_context_ref!r} does not resolve in the shared catalog")
    display_policy_ref = body["display_policy_ref"]
    if display_policy_ref not in shared_vocab:
        raise MethodCatalogError(f"{formula_id}: display_policy_ref {display_policy_ref!r} does not resolve in the shared catalog")

    availability_status_entry = shared_vocab.get("shared.vocab.availability_status")
    method_reason_entry = shared_vocab.get("shared.reason_codes.method")
    if availability_status_entry is None or method_reason_entry is None:
        raise MethodCatalogError("shared catalog is missing 'shared.vocab.availability_status' or 'shared.reason_codes.method'")
    allowed_statuses = set(availability_status_entry["body"]["values"])
    allowed_reason_codes = {code["code"] for code in method_reason_entry["body"]["codes"]}
    reason_mapping = body["reason_mapping"]
    if not isinstance(reason_mapping, (list, tuple)) or not reason_mapping:
        raise MethodCatalogError(f"{formula_id}: reason_mapping must be a non-empty array")
    for index, row in enumerate(reason_mapping):
        if not isinstance(row, Mapping):
            raise MethodCatalogError(f"{formula_id}: reason_mapping[{index}] must be an object")
        status = row.get("status")
        reason_code = row.get("reason_code")
        if status not in allowed_statuses:
            raise MethodCatalogError(f"{formula_id}: reason_mapping[{index}] has unknown status: {status!r}")
        if reason_code not in allowed_reason_codes:
            raise MethodCatalogError(f"{formula_id}: reason_mapping[{index}] has unknown reason_code: {reason_code!r}")

    return CompiledMethodPlan(
        formula_id=formula_id,
        formula_version=formula_version,
        method_id=body["method_id"],
        economic_family_id=economic_family_id,
        variant_dimensions=dict(body["variant_dimensions"]),
        operand_declarations=operand_declarations,
        guard_plan=guard_plan,
        expression=expr,
        unit_equation=dict(body["unit_equation"]),
        output_semantics=dict(output_semantics),
        sign_policy=dict(body["sign_policy"]),
        arithmetic_context_ref=arithmetic_context_ref,
        display_policy_ref=display_policy_ref,
        reason_mapping=tuple(dict(row) for row in reason_mapping),
        source_contract_refs=tuple(entry.get("source_contract_refs", ())),
    )


def compile_method_catalog(catalog_registry: CatalogRegistry, *, mode: str = "generation") -> CompiledMethodRegistry:
    """Compile every entry of the ``valuation.formulas.methods`` catalog
    against the shared catalog's vocabulary. Pure function of
    ``catalog_registry``'s already-verified in-memory state -- performs no
    filesystem or network access itself (that already happened, if at all,
    when the caller built ``catalog_registry`` via
    :func:`fundamental_pipeline.valuation.catalogs.load_catalog_registry`)."""
    formulas_catalog = catalog_registry.catalog(METHOD_CATALOG_ID)
    shared_catalog = catalog_registry.catalog(SHARED_CATALOG_ID)
    shared_vocab = _shared_vocab(shared_catalog)

    entries = formulas_catalog.get("entries", ())
    if not entries:
        raise MethodCatalogError(f"{METHOD_CATALOG_ID} has no entries to compile")

    seen_ids: set[str] = set()
    plans: dict[str, CompiledMethodPlan] = {}
    for entry in entries:
        formula_id = entry["entry_id"]
        if formula_id in seen_ids:
            raise MethodCatalogError(f"duplicate formula_id in {METHOD_CATALOG_ID}: {formula_id!r}")
        seen_ids.add(formula_id)

        # Verifies lock/hash/lifecycle usability (draft is never selectable;
        # retired is replay-only; deprecated warns in generation mode) --
        # raises CatalogError (a ValuationError sibling of MethodCatalogError)
        # on an unusable lifecycle state, never silently compiles a
        # retired/draft entry.
        catalog_registry.select_entry(METHOD_CATALOG_ID, formula_id, mode=mode)

        plans[formula_id] = _compile_one_entry(entry, shared_vocab=shared_vocab)

    return CompiledMethodRegistry(plans_by_formula_id=plans)
