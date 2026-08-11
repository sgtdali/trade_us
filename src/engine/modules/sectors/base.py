from dataclasses import dataclass
@dataclass(frozen=True)
class SectorModule:
    module_id:str; display_name:str; implementation_status:str; compatible_company_types:tuple[str,...]; required_kpi_ids:tuple[str,...]
