from .base import CompanyTypeModule

MODULE = CompanyTypeModule(
    module_id="holding",
    implementation_status="not_implemented",
    supported_period_types=("annual", "quarterly", "half_year", "nine_month"),
    derived_formula_ids=(),
)
