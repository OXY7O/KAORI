#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

python -m compileall -q app migrations tests

if rg -n -i --glob 'app/**' --glob '!app/static/css/output.css' \
  '(compatibility delegate|compatibility fallback|\bfacade\b|\bshim\b|\bwrapper\b|legacy alias|old/migrated|legacy unscoped|kaori.sidebarOpen)' .; then
    echo "ERROR: internal compatibility token ditemukan." >&2
    exit 10
fi

python - <<'PY'
from pathlib import Path
import ast
stdlib = {
    '__future__', 'ast', 'pathlib', 're', 'json', 'textwrap', 'typing',
    'collections', 'datetime', 'importlib', 'sys', 'os', 'dataclasses',
}
safe = []
for path in sorted(Path('tests').rglob('test_*.py')):
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except Exception:
        continue
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split('.')[0])
    if not (roots - stdlib):
        safe.append(str(path))
Path('/tmp/kaori_foundation_static_tests.txt').write_text('\n'.join(safe), encoding='utf-8')
print(f'Static test files: {len(safe)}')
PY

mapfile -t static_tests < /tmp/kaori_foundation_static_tests.txt
pytest -q "${static_tests[@]}"

pytest -q \
  tests/architecture/test_no_internal_compatibility_layers.py \
  tests/architecture/test_foundation_freeze_contract.py \
  tests/inventory/test_inventory_collector_boundary_contract.py \
  tests/inventory/test_inventory_persistence_boundary_contract.py \
  tests/inventory/test_inventory_service_boundary_contract.py \
  tests/inventory/test_inventory_overview_boundary_contract.py \
  tests/integrations/test_integration_cutover_migration_contract.py \
  tests/ui/test_canonical_integration_cutover_ui_contract.py
