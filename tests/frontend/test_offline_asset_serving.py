from __future__ import annotations

import json
from pathlib import Path

import pytest
from flask import Flask

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = ROOT / 'app' / 'static'
MANIFEST_PATH = STATIC_ROOT / 'vendor' / 'manifest.json'

EXPECTED_SIGNATURES = {
    'alpinejs': b'Alpine',
    'htmx.org': b'htmx',
    'lucide': b'lucide',
    'chart.js': b'Chart',
}


def _static_client():
    app = Flask(
        'kaori-offline-static-test',
        static_folder=str(STATIC_ROOT),
        static_url_path='/static',
    )
    app.config.update(TESTING=True)
    return app.test_client()


def test_pinned_runtime_assets_are_served_by_kaori_static_route() -> None:
    """Validate the actual browser artifacts, not only template text or file names."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf8'))
    client = _static_client()

    assert len(manifest['assets']) == len(EXPECTED_SIGNATURES)

    for asset in manifest['assets']:
        package_name = asset['package']
        relative_static_path = asset['runtime_path'].removeprefix('app/static/')
        response = client.get(f'/static/{relative_static_path}')

        assert response.status_code == 200, package_name
        assert 'javascript' in response.content_type.lower(), package_name
        assert len(response.data) == asset['bytes'], package_name
        assert EXPECTED_SIGNATURES[package_name] in response.data, package_name


def test_compiled_kaori_css_is_served_without_remote_font_imports() -> None:
    client = _static_client()
    response = client.get('/static/css/output.css')

    assert response.status_code == 200
    assert 'text/css' in response.content_type.lower()
    assert response.data
    assert b'fonts.googleapis.com' not in response.data
    assert b'fonts.gstatic.com' not in response.data
