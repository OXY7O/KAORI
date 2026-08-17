from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates/kubernetes/analytics'


def test_all_analytics_templates_parse_with_jinja() -> None:
    environment = Environment()
    templates = sorted(TEMPLATES.rglob('*.html'))
    assert len(templates) >= 90
    for template in templates:
        environment.parse(template.read_text(encoding='utf-8'))


def test_analytics_tabs_use_shared_native_contract_without_page_local_handlers() -> None:
    combined = '\n'.join(path.read_text(encoding='utf-8') for path in TEMPLATES.rglob('*.html'))
    overview = (TEMPLATES / 'overview/index.html').read_text(encoding='utf-8')

    assert 'x-show="activeTab' not in combined
    assert 'x-bind:hidden="activeTab' not in combined
    assert ' onclick=' not in combined.lower()
    assert ' onchange=' not in combined.lower()
    assert 'show_badges=false' in overview
    assert 'nowrap=true' in overview
