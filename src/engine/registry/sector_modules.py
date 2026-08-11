from ..errors import ConfigError
from ..io import read_json
from ..modules.sectors import generic
from ..modules.sectors.base import SectorModule
from ..paths import repo_path

_MODULES: dict[str, SectorModule] = {m.module_id: m for m in (generic.MODULE,)}


def get_sector_module(sector_module_id: str) -> dict:
    """Return the ``config/taxonomies/sector-modules.json`` entry."""
    for item in read_json(repo_path("config/taxonomies/sector-modules.json"))["values"]:
        if item["id"] == sector_module_id:
            return item
    raise ConfigError(f"Unknown sector_module: {sector_module_id}")


def get_sector_module_module(sector_module_id: str) -> SectorModule:
    get_sector_module(sector_module_id)  # validates the id is registered at all
    module = _MODULES.get(sector_module_id)
    if module is None:
        raise ConfigError(f"sector_module {sector_module_id!r} is registered but has no Python module")
    return module
