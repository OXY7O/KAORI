from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask_login import UserMixin

from app import create_app
from app.bootstrap import presentation as bootstrap_presentation
from app.extensions import login as login_extension
from app.extensions import login_manager
from app.kubernetes.governance.tls_certificates import routes as tls_routes


class GovernanceRouteUser(UserMixin):
    id = 41
    username = 'governance-route-test'
    display_label = 'Governance Route Test'
    role_name = 'governance_test'
    role_display_name = 'Governance Test'
    timezone = 'UTC'
    timezone_mode = 'manual'
    locale = 'en-US'
    date_format = 'day_month_year'
    time_format = '24h'

    def __init__(self, permissions: set[str]) -> None:
        self.permissions = permissions

    def get_id(self) -> str:
        return 'governance-route-test'

    def has_permission(self, permission_key: str) -> bool:
        return permission_key in self.permissions


def _empty_navigation_context() -> dict[str, object]:
    return {
        'items': [],
        'history_items': [],
        'attention_items': [],
        'active_jobs': [],
        'active_count': 0,
        'attention_count': 0,
        'unread_count': 0,
        'total_count': 0,
        'display_limit': 8,
        'job_display_limit': 6,
    }


def _cluster_context() -> dict[str, object]:
    return {
        'show_banner': False,
        'is_kubernetes_scope': True,
        'is_blocked': False,
        'has_clusters': True,
        'cluster_count': 1,
        'can_manage_clusters': True,
        'database_ready': True,
    }


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        login_extension,
        'check_authentication_database_readiness',
        lambda: SimpleNamespace(ready=True),
    )
    monkeypatch.setattr(bootstrap_presentation, 'build_cluster_onboarding_context', _cluster_context)
    monkeypatch.setattr(
        bootstrap_presentation,
        'get_navigation_notification_context',
        lambda **_kwargs: _empty_navigation_context(),
    )
    monkeypatch.setattr(bootstrap_presentation, 'pop_operational_feedback', lambda: None)
    return create_app('testing')


def _client_for_user(app, monkeypatch: pytest.MonkeyPatch, user: GovernanceRouteUser):
    monkeypatch.setattr(login_manager, '_user_callback', lambda _user_id: user)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = user.get_id()
        session['_fresh'] = True
        session['auth_source'] = 'database'
    return client


def test_unauthorized_tls_htmx_read_is_denied_before_cluster_probe(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(app, monkeypatch, GovernanceRouteUser(set()))

    def unexpected_cluster_probe() -> bool:
        raise AssertionError('cluster readiness must not run before tls_certificates.view')

    monkeypatch.setattr(tls_routes, 'has_registered_clusters', unexpected_cluster_probe)
    response = client.get('/governance/tls-certificates', headers={'HX-Request': 'true'})
    assert response.status_code == 403


def test_authorized_clusterless_tls_htmx_read_returns_onboarding_before_page_query(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(app, monkeypatch, GovernanceRouteUser({'tls_certificates.view'}))
    monkeypatch.setattr(tls_routes, 'has_registered_clusters', lambda: False)

    def unexpected_page_query(_args):
        raise AssertionError('clusterless blocker must run before TLS governance page reads')

    monkeypatch.setattr(tls_routes, 'get_tls_certificate_page', unexpected_page_query)
    response = client.get('/governance/tls-certificates', headers={'HX-Request': 'true'})
    assert response.status_code == 200
    assert 'Connect Your First Kubernetes Cluster' in response.get_data(as_text=True)


def test_tls_sync_status_requires_sync_permission_before_cluster_probe(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(app, monkeypatch, GovernanceRouteUser({'tls_certificates.view'}))

    def unexpected_cluster_probe() -> bool:
        raise AssertionError('cluster readiness must not run before tls_certificates.sync')

    monkeypatch.setattr(tls_routes, 'has_registered_clusters', unexpected_cluster_probe)
    response = client.get('/governance/tls-certificates/sync/job-1/status', headers={'HX-Request': 'true'})
    assert response.status_code == 403
