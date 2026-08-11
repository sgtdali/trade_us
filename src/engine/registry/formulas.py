from ..io import read_json
from ..paths import repo_path
def formulas(): return {f['formula_id']:f for f in read_json(repo_path('config/pipeline/formula-catalog.json'))['formulas']}
