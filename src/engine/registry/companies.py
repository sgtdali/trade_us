from pathlib import Path

from ..io import read_json
from ..paths import repo_path, safe_ticker
from ..errors import ConfigError

def load_company(
    ticker: str, allow_inactive: bool = False,
    data_root: Path | None = None, config_root: Path | None = None,
) -> dict:
    """`config_root` overrides where `config/companies/{ticker}.json` is read
    from; defaults to `data_root` (the original, single-root behaviour) when
    not given, so callers that never had two roots keep working unchanged."""
    ticker = safe_ticker(ticker)
    root = config_root if config_root is not None else data_root
    data = read_json(repo_path('config', 'companies', f'{ticker}.json', root=root))
    if data.get('ticker')!=ticker: raise ConfigError('Ticker mismatch in company configuration')
    if data.get('schema_version',1)>1: raise ConfigError('Unsupported company schema_version')
    if not data.get('is_active',True) and not allow_inactive: raise ConfigError('Company is inactive')
    return data
