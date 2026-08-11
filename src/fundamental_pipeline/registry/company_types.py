from ..errors import ConfigError, UnimplementedModuleError
from ..io import read_json
from ..modules.company_types import standard_corporate
from ..modules.company_types.base import CompanyTypeModule
from ..paths import repo_path

_MODULES: dict[str, CompanyTypeModule] = {
    m.module_id: m
    for m in (standard_corporate.MODULE,)
}


def get_company_type(company_type_id: str) -> dict:
    """Return the ``config/pipeline/company-types.json`` entry (the
    authoritative source for implementation status)."""
    for item in read_json(repo_path("config/pipeline/company-types.json"))["company_types"]:
        if item["id"] == company_type_id:
            return item
    raise ConfigError(f"Unknown company_type: {company_type_id}")


def get_company_type_module(company_type_id: str) -> CompanyTypeModule:
    """Return the Python module object (formula ids, supported period
    types) for a company type. Does not check implementation status; call
    :func:`assert_implemented` first if that matters."""
    get_company_type(company_type_id)  # validates the id is registered at all
    module = _MODULES.get(company_type_id)
    if module is None:
        raise ConfigError(f"company_type {company_type_id!r} is registered but has no Python module")
    return module


def assert_implemented(company_type_id: str) -> None:
    item = get_company_type(company_type_id)
    if item["status"] != "implemented":
        raise UnimplementedModuleError(
            f"Company-type module {company_type_id!r} is registered but not implemented"
        )
