from dataclasses import dataclass


@dataclass(frozen=True)
class CompanyTypeModule:
    """Static description of a company-type analysis module.

    ``implementation_status`` mirrors ``config/pipeline/company-types.json``
    at authoring time for documentation purposes; the registry
    (:mod:`fundamental_pipeline.registry.company_types`) always treats the
    JSON config as the single source of truth for whether a module is
    actually callable, so this field is never read to make that decision.
    """

    module_id: str
    implementation_status: str
    supported_period_types: tuple[str, ...]
    derived_formula_ids: tuple[str, ...]
