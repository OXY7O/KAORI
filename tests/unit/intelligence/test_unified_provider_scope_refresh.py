"""Scoped HTMX responses must not retain a revoked registry (#5229)."""

import pytest
from flask import Flask

from app.intelligence.alert_intelligence import route_utils


@pytest.mark.parametrize(
    ('tab', 'status', 'target'),
    [
        ('active', 'scope_required', 'alert-operations-active-registry'),
        ('active', 'unavailable', 'alert-operations-active-records'),
        ('resolved', 'scope_required', 'alert-operations-provider-history'),
        ('routing', 'ready', 'alert-operations-vault-routing-registry'),
    ],
)
def test_revoked_or_unavailable_fragment_redirects_to_safe_document(monkeypatch, tab, status, target):
    app = Flask(__name__)
    app.add_url_rule('/alerts', endpoint='alert_intelligence.index', view_func=lambda: '')
    monkeypatch.setattr(
        route_utils,
        'get_alert_intelligence_payload',
        lambda _args: {
            'provider_case_mode': True,
            'provider_case_status': status,
            'local_routing': None,
            'domain': 'secrets_pki',
            'selected_provider': '',
            'selected_asset_key': '',
            'tab': tab,
        },
    )
    with app.test_request_context(
        '/alerts?domain=secrets_pki&asset=42',
        headers={'HX-Request': 'true', 'HX-Target': target},
    ):
        response = route_utils.index_response()
        assert response.status_code == 200
        redirect = response.headers['HX-Redirect']
        assert 'domain=secrets_pki' in redirect
        assert 'asset=42' not in redirect
        assert f'tab={tab}' in redirect


def test_whole_workspace_request_renders_blocked_payload_without_redirect(monkeypatch):
    app = Flask(__name__)
    payload = {'provider_case_mode': True, 'provider_case_status': 'scope_required', 'tab': 'active'}
    monkeypatch.setattr(route_utils, 'get_alert_intelligence_payload', lambda _args: payload)
    monkeypatch.setattr(route_utils, 'render_template', lambda name, **_kwargs: name)
    with app.test_request_context(
        '/alerts?tab=active',
        headers={'HX-Request': 'true', 'HX-Target': 'alert-intelligence-page-content'},
    ):
        assert route_utils.index_response() == 'intelligence/partials/_alert_intelligence_page.html'


@pytest.mark.parametrize('query', ['', '?tab=overview&domain=secrets_pki&asset=42', '?tab=invalid'])
@pytest.mark.parametrize('headers', [{}, {'HX-Request': 'true', 'HX-Target': 'alert-intelligence-page-content'}])
def test_overview_ignores_scope_and_uses_read_only_aggregate(monkeypatch, query, headers):
    app = Flask(__name__)
    payload = {'tab': 'overview', 'global_overview': True}
    monkeypatch.setattr(route_utils, 'get_alert_overview_payload', lambda: payload)

    def reject_scoped_read(_args):
        pytest.fail('Overview must not perform a scoped provider read')

    monkeypatch.setattr(route_utils, 'get_alert_intelligence_payload', reject_scoped_read)
    monkeypatch.setattr(route_utils, 'render_template', lambda _name, **kwargs: kwargs['payload'])
    with app.test_request_context('/alerts' + query, headers=headers):
        assert route_utils.index_response() == payload
