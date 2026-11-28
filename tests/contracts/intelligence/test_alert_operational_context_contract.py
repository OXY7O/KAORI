"""Visible operational scope filters; Overview remains selector-free."""

from pathlib import Path

import pytest
from flask import Flask
from jinja2 import StrictUndefined

from app.intelligence.alert_intelligence import route_utils

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'
PARTIALS = TEMPLATES / 'intelligence/partials'
TABS = ('active', 'routing', 'templates', 'silences', 'resolved')


def test_context_is_only_in_operational_workspace_after_hero_and_summary() -> None:
    page = (PARTIALS / '_alert_intelligence_page.html').read_text()
    workspace = (PARTIALS / '_alert_intelligence_workspace.html').read_text()
    include = "{% include 'intelligence/partials/_alert_intelligence_context.html' %}"
    assert include not in page
    assert page.index('workspace_tabs.render_navigation(') < page.index('page_hero.shell_classes()')
    assert page.index('page_hero.shell_classes()') < page.index('_alert_intelligence_summary.html')
    assert page.index('_alert_intelligence_summary.html') < page.index('_alert_intelligence_workspace.html')
    assert workspace.count(include) == 1
    assert "{% if payload.tab != 'overview' %}" in workspace
    assert workspace.index("{% if payload.tab != 'overview' %}") < workspace.index(include)


def scope_for(domain='kubernetes', tab='active', asset='asset-123'):
    provider_mode = domain == 'secrets_pki'
    return {
        'tab': tab,
        'domain': domain,
        'domain_label': domain,
        'domain_options': [{'value': domain, 'label': domain}],
        'provider_case_mode': provider_mode,
        'selected_provider': 'vault' if provider_mode else '',
        'provider_label': 'HashiCorp Vault' if provider_mode else '',
        'provider_options': [{'value': 'vault', 'label': 'Vault'}] if provider_mode else [],
        'selected_asset_key': asset,
        'selected_asset_name': 'Selected Asset',
        'assets': [{'value': asset, 'label': 'Selected Asset', 'environment': 'Production'}],
    }


def test_inline_context_render_preserves_scope_and_has_no_dialog() -> None:
    app = Flask(__name__, template_folder=str(TEMPLATES))
    app.add_url_rule('/alerts', 'alert_intelligence.index', lambda: '')
    app.jinja_env.undefined = StrictUndefined
    template = app.jinja_env.get_template('intelligence/partials/_alert_intelligence_context.html')
    with app.test_request_context('/alerts'):
        for domain in ('kubernetes', 'object_storage', 'registry', 'secrets_pki'):
            for tab in TABS:
                payload = scope_for(domain, tab)
                html = template.render(payload=payload)
                assert '<dialog' not in html
                assert 'Change Scope' not in html
                assert html.count('id="alert-intelligence-context-form"') == 1
                assert 'name="domain"' in html
                assert f'name="tab" value="{tab}"' in html
                assert 'name="asset"' in html
                assert 'value="asset-123" selected' in html
                assert ('name="provider"' in html) == (domain == 'secrets_pki')
                assert 'hx-params="tab,domain"' in html
                assert 'hx-target="#alert-intelligence-page-content"' in html
                assert 'name="draft_domain"' in html
                assert 'hx-trigger="change"' in html

        invalid = scope_for('registry', asset='__invalid_registry_scope__')
        html = template.render(payload=invalid)
        assert '<option value="__invalid_registry_scope__"' not in html
        assert 'selected disabled>Select Active Asset' in html


@pytest.mark.parametrize('query', ['tab=active&domain=registry', 'tab=active&domain=secrets_pki&provider=vault'])
def test_scope_parent_change_refreshes_page_without_stale_asset(monkeypatch, query):
    app = Flask(__name__)
    captured = []
    monkeypatch.setattr(
        route_utils, 'get_alert_intelligence_payload', lambda args: captured.append(dict(args)) or {}
    )
    monkeypatch.setattr(route_utils, 'render_template', lambda name, **kwargs: name)
    headers = {'HX-Request': 'true', 'HX-Target': 'alert-intelligence-page-content'}
    with app.test_request_context('/alerts?' + query, headers=headers):
        assert route_utils.index_response() == 'intelligence/partials/_alert_intelligence_page.html'
    assert 'asset' not in captured[0]
    assert 'apply_scope' not in captured[0]


@pytest.mark.parametrize(
    'extra',
    [
        'draft_domain=object_storage&asset=asset-123',
        'draft_domain=kubernetes&asset=revoked',
        'draft_domain=kubernetes&asset=',
    ],
)
def test_apply_rejects_stale_or_unavailable_choice(monkeypatch, extra):
    app = Flask(__name__)
    monkeypatch.setattr(route_utils, 'get_alert_scope_draft', lambda args: scope_for())
    monkeypatch.setattr(
        route_utils, 'get_alert_intelligence_payload', lambda args: pytest.fail('invalid scope read cases')
    )
    with app.test_request_context('/alerts?tab=active&domain=kubernetes&apply_scope=1&' + extra):
        assert route_utils.index_response()[1] == 400


def test_apply_refreshes_full_page_and_pushes_only_canonical_scope(monkeypatch):
    app = Flask(__name__)
    app.add_url_rule('/alerts', 'alert_intelligence.index', lambda: '')
    monkeypatch.setattr(route_utils, 'get_alert_scope_draft', lambda args: scope_for())
    captured = []
    monkeypatch.setattr(route_utils, 'get_alert_intelligence_payload', lambda args: captured.append(dict(args)) or {})
    monkeypatch.setattr(route_utils, 'render_template', lambda name, **kwargs: name)
    headers = {'HX-Request': 'true', 'HX-Target': 'alert-intelligence-page-content'}
    with app.test_request_context(
        '/alerts?tab=active&domain=kubernetes&apply_scope=1&draft_domain=kubernetes&asset=asset-123',
        headers=headers,
    ):
        response = route_utils.index_response()
        assert response.status_code == 200
        assert 'apply_scope' not in response.headers['HX-Push-Url']
        assert 'draft_domain' not in response.headers['HX-Push-Url']
        assert captured == [{'tab': 'active', 'domain': 'kubernetes', 'asset': 'asset-123'}]
