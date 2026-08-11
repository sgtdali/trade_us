"""T71 method engine: safe closed-AST formula compiler and exact numeric
primitives (T71-A scope only).

Public surface for this PR:

* :func:`engine.valuation.methods.compiler.compile_method_catalog`
* :mod:`engine.valuation.methods.models` --
  :class:`~.models.CompiledMethodPlan` / :class:`~.models.CompiledMethodRegistry`
* :mod:`engine.valuation.methods.ast` -- the closed AST vocabulary
* :mod:`engine.valuation.methods.guards` -- the guard-plan model
* :mod:`engine.valuation.methods.numeric` -- exact rational/Decimal primitives
* :mod:`engine.valuation.methods.units` -- unit inference/compatibility

Applicability routing, operand binding, current-method evaluation, and
result assembly are T71-B scope and do not exist in this package yet.
"""

from __future__ import annotations

from .compiler import compile_method_catalog
from .models import CompiledMethodPlan, CompiledMethodRegistry, OperandDeclaration

__all__ = [
    "compile_method_catalog",
    "CompiledMethodPlan",
    "CompiledMethodRegistry",
    "OperandDeclaration",
]
