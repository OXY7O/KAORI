from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT = ROOT / 'app/templates/components/table_registry.html'
PAGINATION = ROOT / 'app/common/pagination.py'
GENERATED = ROOT / 'app/templates/reports/generated/index.html'
TEMPLATES = ROOT / 'app/templates/reports/report_templates/index.html'
GENERATED_SERVICE = ROOT / 'app/reports/generated/service.py'
TEMPLATE_SERVICE = ROOT / 'app/reports/report_templates/service.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_registry_controls_are_owned_by_one_shared_component() -> None:
    component = read(COMPONENT)

    assert 'KAORI canonical server-backed registry interaction contract' in component
    assert 'data-kaori-canonical-registry-filter' in component
    assert 'data-kaori-canonical-registry-rows' in component
    assert 'data-kaori-canonical-registry-pagination' in component
    assert 'data-kaori-canonical-registry-footer' in component
    assert 'hx-trigger="change, input changed delay:450ms"' in component
    assert 'hx-sync="closest section:replace"' in component
    assert "page_param='page'" in component
    assert "per_page_param='per_page'" in component
    assert '<input type="hidden" name="{{ page_param }}" value="1">' in component
    assert '<input type="hidden" name="{{ per_page_param }}" value="{{ per_page }}">' in component
    assert 'data-kaori-auto-submit' in component
    assert 'pagination_ui.numeric_pages(' in component
    assert 'page_param=page_param' in component
    assert 'name="{{ per_page_param }}"' in component


def test_report_registries_consume_shared_controls_instead_of_copying_htmx_contract() -> None:
    generated = read(GENERATED)
    templates = read(TEMPLATES)

    for source in (generated, templates):
        assert 'components/table_registry.html' in source
        assert 'registry_ui.filter_form(' in source
        assert 'registry_ui.footer(' in source
        assert 'components/pagination.html' not in source
        assert 'hx-trigger="change, input delay:450ms"' not in source
        assert 'data-kaori-auto-submit' not in source

    assert "control_name='generated-reports'" in generated
    assert "control_name='report-templates'" in templates
    assert 'registry_ui.clear_filters_link(' in generated
    assert 'registry_ui.clear_filters_link(' in templates


def test_report_registry_backends_use_canonical_pagination_module() -> None:
    canonical = read(PAGINATION)
    generated = read(GENERATED_SERVICE)
    templates = read(TEMPLATE_SERVICE)

    assert 'PER_PAGE_OPTIONS: tuple[int, ...] = (5, 10, 25, 50)' in canonical
    assert 'def normalize_per_page(' in canonical
    assert 'def build_pagination_window(' in canonical
    assert 'def paginate_select(' in canonical
    assert 'statement.order_by(None).subquery()' in canonical

    assert 'from app.common.pagination import (' in generated
    for symbol in ('PER_PAGE_OPTIONS', 'build_pagination_window', 'normalize_per_page', 'positive_int'):
        assert f'    {symbol},' in generated
    assert 'GENERATED_PER_PAGE_OPTIONS' not in generated
    assert 'def normalize_generated_per_page' not in generated
    assert 'def normalize_generated_page' not in generated
    assert generated.count('build_pagination_window(') >= 2

    assert 'from app.common.pagination import PER_PAGE_OPTIONS, build_pagination_window' in templates
    assert 'def normalize_templates_per_page' not in templates
    assert 'def build_templates_page_window' not in templates
    assert 'def build_templates_page_href' not in templates
    assert 'def parse_positive_int' not in templates
    assert 'build_pagination_window(' in templates
