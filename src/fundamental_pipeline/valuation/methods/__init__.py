"""T71 method engine: safe closed-AST formula compiler and exact numeric
primitives (T71-A scope only).

Public surface for this PR:

* :func:`fundamental_pipeline.valuation.methods.compiler.compile_method_catalog`
* :mod:`fundamental_pipeline.valuation.methods.models` --
  :class:`~.models.CompiledMethodPlan` / :class:`~.models.CompiledMethodRegistry`
* :mod:`fundamental_pipeline.valuation.methods.ast` -- the closed AST vocabulary
* :mod:`fundamental_pipeline.valuation.methods.guards` -- the guard-plan model
* :mod:`fundamental_pipeline.valuation.methods.numeric` -- exact rational/Decimal primitives
* :mod:`fundamental_pipeline.valuation.methods.units` -- unit inference/compatibility

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
