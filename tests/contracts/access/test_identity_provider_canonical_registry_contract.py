"""Provider Registry preserves the canonical KAORI HTMX interaction contract."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def test_provider_registry_uses_shared_htmx_controls_and_provider_tab() -> None:
    s = (ROOT / 'app/templates/access/identity_providers/partials/_registry.html').read_text(encoding='utf-8')
    shared = (ROOT / 'app/templates/components/table_registry.html').read_text(encoding='utf-8')
    Environment().parse(s)
    for macro in ('filter_form', 'clear_filters_link', 'footer'):
        assert f'registry_ui.{macro}(' in s
    assert s.count("'identity-provider-registry',") >= 3
    assert s.count("'identity-provider-registry-loading',") >= 3
    assert "form_id='identity-provider-registry-filter-form'" in s
    assert 'name="tab" value="providers"' in s
    assert "query_params={'tab': 'providers'}" in s
    assert "footer_query.pop('per_page', none)" in s
    for name in ('search', 'provider_key', 'state'):
        assert f'name="{name}"' in s
    assert 'registry_ui.clear_filters_action(' not in s
    assert 'pagination_ui.numeric_pages(' not in s
    assert 'hx-trigger="keyup changed delay:' not in s
    assert 'hx-sync="closest section:replace"' in shared
    assert 'hx-select="#{{ registry_id }}"' in shared
    assert 'data-kaori-canonical-registry-footer' in shared


def test_provider_detail_expansion_and_permissions_remain() -> None:
    s = (ROOT / 'app/templates/access/identity_providers/partials/_registry.html').read_text(encoding='utf-8')
    assert "expandable.toggle_button('identity-providers'" in s
    assert 'expandable.static_detail_row(detail_row_id, detail_target_id, 6)' in s
    assert '"access/identity_providers/partials/_provider_detail.html"' in s
    detail = (ROOT / 'app/templates/access/identity_providers/partials/_provider_detail.html').read_text(encoding='utf-8')
    assert "current_user.has_permission('identity_providers.manage')" in detail
    assert "current_user.has_permission('identity_providers.provision')" in detail
    assert 'components/states/_empty_state.html' in s
