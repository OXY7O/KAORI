"""User Directory retains canonical filters/pagination and distinct HTMX response owners."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_user_directory_uses_shared_registry_interactions() -> None:
    filters = source('app/templates/access/users/partials/_filters.html')
    directory = source('app/templates/access/users/partials/_directory.html')
    table = source('app/templates/access/users/partials/_table.html')
    shared = source('app/templates/components/table_registry.html')
    for template in (filters, directory, table):
        Environment().parse(template)

    assert 'registry_ui.filter_form(' in filters
    assert "form_id='users-filter-form'" in filters
    assert "'user-directory'," in filters
    assert "'users-refresh-indicator'," in filters
    assert 'name="per_page"' not in filters
    for selected in ('search', 'status', 'auth_source', 'role_id'):
        assert f'name="{selected}"' in filters or selected == 'search' and "search_field('search'," in filters

    assert 'id="user-directory"' in directory
    assert 'registry_ui.clear_filters_link(' in directory
    assert 'registry_ui.clear_filters_action(' not in directory
    assert 'registry_ui.footer(' in table
    assert "footer_query.pop('per_page', none)" in table
    assert 'users-pagination-form' not in table
    assert 'pagination_ui.numeric_pages(' not in table
    assert 'expandable.static_detail_row(' in table
    assert 'hx-sync="closest section:replace"' in shared
    assert 'hx-select="#{{ registry_id }}"' in shared


def test_user_directory_html_targets_cannot_replace_summary_or_hero() -> None:
    page = source('app/templates/access/users/partials/_content.html')
    route = source('app/access/users/routes.py')
    assert "partials/_summary_cards.html" in page
    assert "partials/_directory.html" in page
    assert "request.headers.get('HX-Target') == 'user-directory'" in route
    assert "render_template('access/users/partials/_directory.html', **payload)" in route
    assert "render_template('access/users/partials/_content.html', **payload)" in route
    assert "render_template('access/users/index.html', **payload)" in route
    assert "request.headers.get('HX-History-Restore-Request') != 'true'" in route
    assert "hero_oob=True" in route
    assert "toast_oob=True" in route
