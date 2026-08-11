"""The valuation namespace.

Dependency direction is one-way: this package (and its ``validation``
subpackage) may import only ``fundamental_pipeline.public`` from the rest
of ``fundamental_pipeline`` -- never signals, summaries, reports,
templates, generated-output readers, or private company-type/sector
modules, and never the reverse (no module outside this namespace imports
``fundamental_pipeline.valuation``). See
``tests/unit/valuation/test_import_boundaries.py``.

Importing this package (or ``fundamental_pipeline.valuation.cli``) never
reads production data, contacts a network, inspects environment
credentials, or writes files.
"""
