from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[4]
TEMPLATES = ROOT / 'app/templates/kubernetes/governance'


def test_governance_templates_parse_without_page_local_inline_handlers() -> None:
    environment = Environment()
    paths = sorted(TEMPLATES.rglob('*.html'))
    assert paths
    for path in paths:
        source = path.read_text(encoding='utf-8')
        environment.parse(source)
        lowered = source.lower()
        assert ' style=' not in lowered, path
        assert ' onclick=' not in lowered, path
        assert ' onchange=' not in lowered, path


def test_tls_registry_uses_canonical_hero_table_status_pagination_and_modal_contracts() -> None:
    overview = (TEMPLATES / 'overview/index.html').read_text(encoding='utf-8')
    hero = (TEMPLATES / 'tls_certificates/partials/_hero.html').read_text(encoding='utf-8')
    table = (TEMPLATES / 'tls_certificates/partials/_table.html').read_text(encoding='utf-8')
    page = (TEMPLATES / 'tls_certificates/index.html').read_text(encoding='utf-8')

    assert 'page_hero.context_header(' in overview
    assert 'page_hero.context_card(' in hero
    assert 'components/table.html' in table
    assert 'components/table_label.html' in table
    assert 'components/pagination.html' in table
    assert 'components/resource_detail_modal.html' in table
    assert 'detail_button(' in table
    assert 'resource_detail_modal.host(' in page
