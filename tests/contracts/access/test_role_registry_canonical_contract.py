"""Role Registry uses the canonical KAORI HTMX filter/footer contract."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_roles_registry_uses_shared_filter_clear_and_footer() -> None:
    registry = _read('app/templates/access/roles/partials/_registry.html')
    shared = _read('app/templates/components/table_registry.html')
    Environment().parse(registry)

    assert 'registry_ui.filter_form(' in registry
    assert 'registry_ui.clear_filters_link(' in registry
    assert 'registry_ui.footer(' in registry
    assert "'role-registry'," in registry
    assert "'role-registry-loading'," in registry
    assert "footer_query.pop('per_page', none)" in registry
    assert "form_id='role-registry-filter-form'" in registry
    for field in ('search', 'role_type', 'state'):
        assert f'name="{field}"' in registry or (field == 'search' and "table_ui.search_field('search'" in registry)
    assert 'pagination_ui.numeric_pages(' not in registry
    assert 'hx-trigger="keyup changed delay' not in registry
    assert 'hx-sync="closest section:replace"' in shared
    assert 'hx-select="#{{ registry_id }}"' in shared
    assert 'data-kaori-canonical-registry-footer' in shared
    assert 'name="{{ per_page_param }}"' in shared
    assert "table_ui.table_classes('min-w-[1080px]')" in registry
