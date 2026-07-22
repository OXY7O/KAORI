from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

ROOT = Path(__file__).resolve().parents[3]


def test_frontend_commands_use_one_canonical_css_entrypoint() -> None:
    package = json.loads((ROOT / 'package.json').read_text(encoding='utf8'))
    scripts = package['scripts']

    assert 'frontend/styles.css' in scripts['build-css']
    assert 'frontend/styles.css' in scripts['watch-css']
    assert 'app/static/css/output.css' in scripts['build-css']
    assert 'app/static/css/output.css' in scripts['watch-css']
    assert not (ROOT / 'frontend/src/input.css').exists()


def test_frontend_build_includes_vendor_and_css() -> None:
    package = json.loads((ROOT / 'package.json').read_text(encoding='utf8'))
    scripts = package['scripts']

    assert scripts['build-frontend'] == 'npm run vendor-assets && npm run build-css'
    assert scripts['verify-frontend'] == 'npm run verify-vendor-assets && npm run verify-css'


def test_production_image_copies_compiled_css_vendor_assets_and_fonts() -> None:
    dockerfile = (ROOT / 'Dockerfile').read_text(encoding='utf8')

    assert 'npm run build-frontend' in dockerfile
    assert 'npm run verify-frontend' in dockerfile
    assert '/build/app/static/css/output.css' in dockerfile
    assert '/build/app/static/vendor' in dockerfile
    assert '/app/app/static/vendor' in dockerfile
    assert '/build/app/static/fonts' in dockerfile
    assert '/app/app/static/fonts' in dockerfile
