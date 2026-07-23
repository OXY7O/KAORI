from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

ROOT = Path(__file__).resolve().parents[3]
EXPECTED = {
    'node_modules/alpinejs': '3.15.12',
    'node_modules/htmx.org': '2.0.10',
    'node_modules/lucide': '1.20.0',
    'node_modules/chart.js': '4.5.1',
}


def test_package_lock_contains_exact_runtime_asset_versions() -> None:
    package = json.loads((ROOT / 'package.json').read_text(encoding='utf8'))
    lock = json.loads((ROOT / 'package-lock.json').read_text(encoding='utf8'))

    for lock_key, expected_version in EXPECTED.items():
        package_name = lock_key.removeprefix('node_modules/')
        assert package['devDependencies'][package_name] == expected_version
        assert lock['packages'][lock_key]['version'] == expected_version


def test_bootstrap_command_is_explicit_and_reproducible() -> None:
    package = json.loads((ROOT / 'package.json').read_text(encoding='utf8'))

    assert package['scripts']['bootstrap-frontend'] == (
        'bash ./scripts/bootstrap_frontend_assets.sh'
    )
    bootstrap = (ROOT / 'scripts/bootstrap_frontend_assets.sh').read_text(encoding='utf8')
    assert 'npm ci --no-audit --no-fund' in bootstrap
    assert 'npm install' not in bootstrap
    assert 'npm run prepare-frontend' in bootstrap
    assert './scripts/test_offline_frontend.sh' in bootstrap
