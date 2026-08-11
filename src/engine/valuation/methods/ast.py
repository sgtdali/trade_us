"""The closed, typed method-formula AST (docs/valuation-t71-02-formula-ast-catalog-compilation-specification.md
Section 3).

This is a small, closed expression tree over bound operands and
catalog-owned constants. There is no comparison, branch, loop, lookup,
function call, attribute access, string interpolation, file access, or
dynamic operator node -- :func:`parse_ast` fails closed on anything outside
this exact eight-node vocabulary, and there is no ``eval``/``exec``/dynamic
import anywhere in this module or its callers.

This vocabulary is deliberately isolated from the AST-like ``{"op": ...}``
shapes already used by the T70 capital-basis catalog
(``engine.valuation.catalogs._CAPITAL_BASIS_ENTRIES``): the two
are structurally similar but are different, independently-versioned
contracts, and this module never reads or writes a capital-basis entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Union

from ..errors import FormulaCompileError

ALLOWED_OPERATORS = frozenset({"operand", "constant", "add", "subtract", "multiply", "divide", "negate", "scale_convert"})

#: Resource bounds enforced *before* recursion, per node, so a malicious or
#: corrupt catalog entry cannot cause runaway recursion or an
#: exponential-blowup traversal (including one built from JSON-shared/
#: aliased container objects: because every occurrence of a node -- aliased
#: or not -- is counted, a shared/aliased subtree costs as much as a fully
#: expanded one and hits this bound just as fast).
DEFAULT_MAX_DEPTH = 16
DEFAULT_MAX_NODES = 64


@dataclass(frozen=True)
class OperandNode:
    symbol: str


@dataclass(frozen=True)
class ConstantNode:
    value: str  # canonical decimal string
    unit: str


@dataclass(frozen=True)
class AddNode:
    args: tuple["MethodExpr", ...]


@dataclass(frozen=True)
class SubtractNode:
    left: "MethodExpr"
    right: "MethodExpr"


@dataclass(frozen=True)
class MultiplyNode:
    args: tuple["MethodExpr", ...]


@dataclass(frozen=True)
class DivideNode:
    numerator: "MethodExpr"
    denominator: "MethodExpr"


@dataclass(frozen=True)
class NegateNode:
    arg: "MethodExpr"


@dataclass(frozen=True)
class ScaleConvertNode:
    arg: "MethodExpr"
    from_scale: str
    to_scale: str


MethodExpr = Union[OperandNode, ConstantNode, AddNode, SubtractNode, MultiplyNode, DivideNode, NegateNode, ScaleConvertNode]


@dataclass(frozen=True)
class _ParseState:
    max_depth: int
    max_nodes: int
    node_count: int = field(default=0)


def parse_ast(raw: Any, *, max_depth: int = DEFAULT_MAX_DEPTH, max_nodes: int = DEFAULT_MAX_NODES) -> MethodExpr:
    """Safely parse a plain-JSON-shaped ``raw`` node tree into the closed
    :data:`MethodExpr` vocabulary. Raises :class:`FormulaCompileError`
    (never a raw ``KeyError``/``TypeError``/``RecursionError``) on any
    unknown operator, malformed node shape, or bound violation. Never
    imports, evaluates, or executes anything -- this is pure, side-effect
    free data parsing."""
    counter = [0]
    return _parse_node(raw, depth=0, max_depth=max_depth, max_nodes=max_nodes, counter=counter, path="$")


def _bump(counter: list[int], max_nodes: int, path: str) -> None:
    counter[0] += 1
    if counter[0] > max_nodes:
        raise FormulaCompileError(f"AST node count exceeds max_nodes={max_nodes} at or before {path}")


def _parse_node(raw: Any, *, depth: int, max_depth: int, max_nodes: int, counter: list[int], path: str) -> MethodExpr:
    if depth > max_depth:
        raise FormulaCompileError(f"AST nesting depth exceeds max_depth={max_depth} at {path}")
    _bump(counter, max_nodes, path)

    if not isinstance(raw, Mapping):
        raise FormulaCompileError(f"{path}: AST node must be an object, got {type(raw).__name__}")

    op = raw.get("op")
    if op not in ALLOWED_OPERATORS:
        raise FormulaCompileError(f"{path}: unknown or disallowed AST operator: {op!r}")

    def child(key: str) -> MethodExpr:
        if key not in raw:
            raise FormulaCompileError(f"{path}: '{op}' node missing required field {key!r}")
        return _parse_node(raw[key], depth=depth + 1, max_depth=max_depth, max_nodes=max_nodes, counter=counter, path=f"{path}.{key}")

    def child_list(key: str) -> tuple[MethodExpr, ...]:
        if key not in raw:
            raise FormulaCompileError(f"{path}: '{op}' node missing required field {key!r}")
        items = raw[key]
        if not isinstance(items, (list, tuple)) or len(items) < 2:
            raise FormulaCompileError(f"{path}.{key}: '{op}' requires an array of at least two nodes")
        return tuple(
            _parse_node(item, depth=depth + 1, max_depth=max_depth, max_nodes=max_nodes, counter=counter, path=f"{path}.{key}[{i}]")
            for i, item in enumerate(items)
        )

    if op == "operand":
        symbol = raw.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            raise FormulaCompileError(f"{path}: 'operand' node requires a non-empty string 'symbol'")
        return OperandNode(symbol=symbol)

    if op == "constant":
        value = raw.get("value")
        unit = raw.get("unit")
        if not isinstance(value, str) or not value:
            raise FormulaCompileError(f"{path}: 'constant' node requires a non-empty decimal string 'value'")
        if not isinstance(unit, str) or not unit:
            raise FormulaCompileError(f"{path}: 'constant' node requires a non-empty string 'unit'")
        from ..canonical import normalize_decimal
        from ..errors import CanonicalizationError

        try:
            canonical = normalize_decimal(value)
        except CanonicalizationError as exc:
            raise FormulaCompileError(f"{path}: 'constant' node value is not a valid canonical decimal: {exc}") from exc
        if canonical != value:
            # A catalog-owned constant must already be spelled in canonical
            # form (docs/valuation-t71-02-*.md Section 16: "Constants must
            # pass decimal grammar"): "1.0", "01", and "1e3" are all valid
            # *values* that normalize_decimal() can canonicalize, but they
            # are not themselves canonical spellings, so they are rejected
            # here rather than silently renormalized.
            raise FormulaCompileError(f"{path}: 'constant' node value {value!r} is not in canonical decimal form (expected {canonical!r})")
        return ConstantNode(value=value, unit=unit)

    if op == "add":
        return AddNode(args=child_list("args"))

    if op == "subtract":
        return SubtractNode(left=child("left"), right=child("right"))

    if op == "multiply":
        return MultiplyNode(args=child_list("args"))

    if op == "divide":
        return DivideNode(numerator=child("numerator"), denominator=child("denominator"))

    if op == "negate":
        return NegateNode(arg=child("arg"))

    if op == "scale_convert":
        from_scale = raw.get("from_scale")
        to_scale = raw.get("to_scale")
        if not isinstance(from_scale, str) or not from_scale:
            raise FormulaCompileError(f"{path}: 'scale_convert' node requires a non-empty string 'from_scale'")
        if not isinstance(to_scale, str) or not to_scale:
            raise FormulaCompileError(f"{path}: 'scale_convert' node requires a non-empty string 'to_scale'")
        return ScaleConvertNode(arg=child("arg"), from_scale=from_scale, to_scale=to_scale)

    raise FormulaCompileError(f"{path}: unreachable -- unhandled allowed operator {op!r}")  # pragma: no cover


def iter_operand_symbols(node: MethodExpr) -> "list[str]":
    """Return every ``operand`` symbol referenced anywhere in ``node``, in
    left-to-right traversal order (may contain duplicates -- a symbol used
    twice is not a compile error by itself)."""
    symbols: list[str] = []
    _walk_operands(node, symbols)
    return symbols


def _walk_operands(node: MethodExpr, out: list[str]) -> None:
    if isinstance(node, OperandNode):
        out.append(node.symbol)
    elif isinstance(node, ConstantNode):
        return
    elif isinstance(node, (AddNode, MultiplyNode)):
        for arg in node.args:
            _walk_operands(arg, out)
    elif isinstance(node, SubtractNode):
        _walk_operands(node.left, out)
        _walk_operands(node.right, out)
    elif isinstance(node, DivideNode):
        _walk_operands(node.numerator, out)
        _walk_operands(node.denominator, out)
    elif isinstance(node, NegateNode):
        _walk_operands(node.arg, out)
    elif isinstance(node, ScaleConvertNode):
        _walk_operands(node.arg, out)
    else:  # pragma: no cover - exhaustive by construction of parse_ast
        raise FormulaCompileError(f"unknown AST node type during traversal: {type(node).__name__}")


def divide_nodes(node: MethodExpr) -> "list[DivideNode]":
    """Return every :class:`DivideNode` anywhere in ``node``, used by the
    compiler's guard-coverage check (every division must have a preceding
    ``denominator_nonzero`` guard on its exact denominator symbol)."""
    found: list[DivideNode] = []
    _walk_divides(node, found)
    return found


def _walk_divides(node: MethodExpr, out: list[DivideNode]) -> None:
    if isinstance(node, DivideNode):
        out.append(node)
        _walk_divides(node.numerator, out)
        _walk_divides(node.denominator, out)
    elif isinstance(node, (AddNode, MultiplyNode)):
        for arg in node.args:
            _walk_divides(arg, out)
    elif isinstance(node, SubtractNode):
        _walk_divides(node.left, out)
        _walk_divides(node.right, out)
    elif isinstance(node, NegateNode):
        _walk_divides(node.arg, out)
    elif isinstance(node, ScaleConvertNode):
        _walk_divides(node.arg, out)
