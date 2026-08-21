from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]

TEMPLATES = (
    'app/templates/components/details/_detail_content.html',
    'app/templates/components/technical_metadata_collection.html',
    'app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html',
)

CONTRACT_TESTS = (
    'tests/contracts/kubernetes/test_node_detail_balanced_inspector_v8_contract.py',
    'tests/contracts/kubernetes/test_node_detail_natural_height_contract.py',
    'tests/contracts/kubernetes/test_node_inventory_standard_contract.py',
    'tests/contracts/kubernetes/test_inventory_detail_modal_v2_contract.py',
    'tests/contracts/kubernetes/test_inventory_detail_fact_sheet_v4_contract.py',
    'tests/contracts/kubernetes/test_inventory_expanded_detail_style_contract.py',
    'tests/contracts/kubernetes/test_inventory_horizontal_bands_v6_contract.py',
    'tests/contracts/kubernetes/test_inventory_resource_profile_v5_contract.py',
    'tests/contracts/kubernetes/test_inventory_node_styling_guide_contract.py',
    'tests/contracts/kubernetes/test_inventory_network_styling_guide_contract.py',
)


def run(*args: str) -> None:
    print(f"\n$ {' '.join(args)}")
    subprocess.run(args, cwd=ROOT, check=True)


def parse_templates() -> None:
    environment = Environment()
    for relative in TEMPLATES:
        source = (ROOT / relative).read_text(encoding='utf-8')
        environment.parse(source)
        print(f'Jinja parse OK: {relative}')


def main() -> int:
    parse_templates()
    run(sys.executable, 'scripts/verify_node_inventory_standard.py')
    run(sys.executable, 'scripts/verify_ui_style.py')
    run(sys.executable, '-m', 'pytest', '-q', *CONTRACT_TESTS)
    print('\nPASS: Node Inventory modal V9 redesign verified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
