from pathlib import Path

from ..io import read_json
from ..paths import repo_path, safe_ticker
from ..errors import ConfigError

def load_company(ticker: str, allow_inactive: bool = False, data_root: Path | None = None) -> dict:
    ticker = safe_ticker(ticker)
    data = read_json(repo_path('config', 'companies', f'{ticker}.json', root=data_root))
    if data.get('ticker')!=ticker: raise ConfigError('Ticker mismatch in company configuration')
    if data.get('schema_version',1)>1: raise ConfigError('Unsupported company schema_version')
    if not data.get('is_active',True) and not allow_inactive: raise ConfigError('Company is inactive')
    return data
