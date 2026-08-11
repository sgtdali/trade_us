from ..io import read_json
from ..paths import repo_path
def metric_catalog(): return {m['metric_id']:m for m in read_json(repo_path('config/pipeline/metric-catalog.json'))['metrics']}
