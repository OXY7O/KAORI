from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app' / 'templates'
STATIC = ROOT / 'app' / 'static'

REMOTE_RUNTIME_ATTRIBUTE = re.compile(
    r'<(?:script|link)\b[^>]*(?:src|href)=["\'](?:https?:)?//',
    re.IGNORECASE,
)
REMOTE_CSS_ASSET = re.compile(
    r'(?:@import\s+(?:url\()?\s*["\']?(?:https?:)?//|url\(\s*["\']?(?:https?:)?//)',
    re.IGNORECASE,
)
FORBIDDEN_RUNTIME_HOSTS = (
    'cdn.jsdelivr.net',
    'unpkg.com',
    'cdnjs.cloudflare.com',
    'fonts.googleapis.com',
    'fonts.gstatic.com',
    'cdn.tailwindcss.com',
)


def test_templates_do_not_load_runtime_assets_from_the_internet() -> None:
    violations: list[str] = []

    for path in sorted(TEMPLATES.rglob('*.html')):
        content = path.read_text(encoding='utf8')
        if REMOTE_RUNTIME_ATTRIBUTE.search(content):
            violations.append(str(path.relative_to(ROOT)))

    assert violations == []


def test_css_does_not_import_remote_fonts_or_stylesheets() -> None:
    violations: list[str] = []

    for path in sorted(STATIC.rglob('*.css')):
        content = path.read_text(encoding='utf8')
        if REMOTE_CSS_ASSET.search(content):
            violations.append(str(path.relative_to(ROOT)))

    assert violations == []


def test_known_cdn_hosts_cannot_return_to_active_templates_or_static_code() -> None:
    violations: list[str] = []
    candidates = [*TEMPLATES.rglob('*.html'), *STATIC.rglob('*.js'), *STATIC.rglob('*.css')]

    for path in sorted(candidates):
        content = path.read_text(encoding='utf8').lower()
        matched = [host for host in FORBIDDEN_RUNTIME_HOSTS if host in content]
        if matched:
            violations.append(f"{path.relative_to(ROOT)}: {', '.join(matched)}")

    assert violations == []


def test_runtime_dependencies_are_exactly_pinned() -> None:
    package_json = json.loads((ROOT / 'package.json').read_text(encoding='utf8'))
    dev_dependencies = package_json['devDependencies']

    expected = {
        'alpinejs': '3.15.12',
        'htmx.org': '2.0.10',
        'lucide': '1.20.0',
        'chart.js': '4.5.1',
        '@fontsource-variable/inter': '5.3.0',
    }

    assert {name: dev_dependencies.get(name) for name in expected} == expected
    assert all(not re.search(r'[~^*xX]', version) for version in expected.values())


def test_canonical_layouts_reference_local_vendor_paths() -> None:
    app_layout = (TEMPLATES / 'layouts' / 'app.html').read_text(encoding='utf8')
    auth_layout = (TEMPLATES / 'layouts' / 'auth.html').read_text(encoding='utf8')

    assert "vendor/alpine/alpine.min.js" in app_layout
    assert "vendor/htmx/htmx.min.js" in app_layout
    assert "vendor/lucide/lucide.min.js" in app_layout
    assert "vendor/lucide/lucide.min.js" in auth_layout

    for relative_path in (
        'analytics/top_consumers/index.html',
        'analytics/utilization/index.html',
        'analytics/forecast/index.html',
    ):
        content = (TEMPLATES / relative_path).read_text(encoding='utf8')
        assert "vendor/chartjs/chart.umd.min.js" in content


def test_inter_font_is_self_hosted_from_the_canonical_tailwind_source() -> None:
    source = (ROOT / 'frontend' / 'styles.css').read_text(encoding='utf8')

    assert "font-family: 'Inter Variable'" in source
    assert "../fonts/inter/inter-latin-wght-normal.woff2" in source
    assert "--font-sans: 'Inter Variable', Inter" in source
    assert 'fonts.googleapis.com' not in source
    assert 'fonts.gstatic.com' not in source
