from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates/inventory'
RESOURCE_NAMES = ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')
DETAIL_PARTIALS = {
    'nodes': '_node_detail_content.html',
    'namespaces': '_namespace_detail_content.html',
    'configuration': '_configuration_detail_content.html',
    'workloads': '_workload_detail_content.html',
    'pods': '_pod_detail_content.html',
    'services': '_service_detail_content.html',
    'ingresses': '_ingress_detail_content.html',
    'storage': '_storage_detail_content.html',
}


def test_inventory_templates_parse_as_jinja_without_page_local_inline_handlers() -> None:
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


def test_inventory_pages_use_canonical_hero_table_pagination_and_detail_disclosure_components() -> None:
    overview = (TEMPLATES / 'overview/partials/_hero.html').read_text(encoding='utf-8')
    topology = (TEMPLATES / 'topology/partials/_hero.html').read_text(encoding='utf-8')

    assert 'page_hero.context_card(' in overview
    assert 'page_hero.context_status_badge(' in topology

    for resource in RESOURCE_NAMES:
        hero = (TEMPLATES / resource / 'partials/_hero.html').read_text(encoding='utf-8')
        table = (TEMPLATES / resource / 'partials/_table_content.html').read_text(encoding='utf-8')
        assert 'components/page_hero.html' in hero
        assert 'page_hero.context_card(' in hero
        assert 'components/table.html' in table
        assert 'components/pagination.html' in table
        assert 'components/resource_detail_modal.html' in table
        assert 'detail_button(' in table

        detail_source = (TEMPLATES / resource / 'partials' / DETAIL_PARTIALS[resource]).read_text(
            encoding='utf-8'
        )
        assert 'detail.header_badge_row()' in detail_source
        assert 'self-start sm:self-auto' not in detail_source
