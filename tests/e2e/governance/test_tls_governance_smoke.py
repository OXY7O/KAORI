from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask_login import UserMixin

from app import create_app
from app.bootstrap import presentation as bootstrap_presentation
from app.extensions import login as login_extension
from app.extensions import login_manager
from app.governance.tls_certificates import routes as tls_routes


class GovernanceSmokeUser(UserMixin):
    id = 42
    username = 'governance-smoke'
    display_label = 'Governance Smoke'
    role_name = 'super_admin'
    role_display_name = 'Super Admin'
    timezone = 'UTC'
    timezone_mode = 'manual'
    locale = 'en-US'
    date_format = 'day_month_year'
    time_format = '24h'

    def get_id(self) -> str:
        return 'governance-smoke'

    def has_permission(self, permission_key: str) -> bool:
        return permission_key in {'governance.view', 'tls_certificates.view', 'jobs.view', 'clusters.manage'}


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


def _payload() -> dict[str, object]:
    return {
        'summary': {
            'total': 0,
            'healthy': 0,
            'warning': 0,
            'critical': 0,
            'expired': 0,
            'invalid': 0,
            'unknown': 0,
            'coverage_partial': 0,
            'coverage_uncovered': 0,
            'coverage_not_reported': 0,
            'issuer_count': 0,
        },
        'sync_state': {
            'is_active': False,
            'label': 'Current',
            'tone': 'normal',
            'helper': 'Current snapshot.',
            'automatic_enabled': True,
            'last_success_label': 'Now',
            'next_run_label': 'Later',
            'active_job_public_id': None,
            'progress_message': None,
            'progress_percent': 100,
        },
        'filters': {
            'cluster_id': '',
            'namespace': '',
            'status': 'all',
            'search': '',
        },
        'pagination': {
            'page': 1,
            'per_page': 5,
            'allowed_per_page': (5, 10, 25, 50),
            'start_item': 0,
            'end_item': 0,
            'total_items': 0,
            'total_pages': 1,
            'has_prev': False,
            'prev_page': None,
            'has_next': False,
            'next_page': None,
        },
        'records': [],
        'clusters': [],
        'namespaces': [],
        'status_options': ('all', 'healthy', 'warning', 'critical', 'expired', 'invalid', 'unknown'),
        'validity_policy': {
            'renewal_window_days': 30,
            'critical_window_days': 7,
        },
        'snapshot': {
            'source_label': 'Kubernetes TLS Secrets + Ingresses',
            'status': 'Complete',
            'tone': 'normal',
            'description': 'Worker snapshot.',
            'latest_collected': 'Now',
            'latest_supporting': 'Worker-generated snapshot',
            'scope_label': 'All Clusters',
            'scope_supporting': 'Fleet scope',
            'coverage_label': '0 TLS Secrets',
            'coverage_supporting': 'Collected certificate inventory',
            'coverage_tone': 'normal',
            'exceptions_label': 'No Exceptions',
            'exceptions_supporting': 'No issues detected',
            'exceptions_tone': 'normal',
        },
        'schema_readiness': {'ready': True},
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
    monkeypatch.setattr(tls_routes, 'has_registered_clusters', lambda: True)
    monkeypatch.setattr(tls_routes, 'get_tls_certificate_page', lambda _args: _payload())
    return create_app('testing')


def test_anonymous_user_is_redirected_before_tls_governance_render(app) -> None:
    response = app.test_client().get('/governance/tls-certificates')
    assert response.status_code == 302
    assert '/login?next=' in response.headers['Location']


def test_authorized_user_renders_tls_governance_in_global_application_shell(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = GovernanceSmokeUser()
    monkeypatch.setattr(login_manager, '_user_callback', lambda _user_id: user)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = user.get_id()
        session['_fresh'] = True
        session['auth_source'] = 'database'

    response = client.get('/governance/tls-certificates')
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'TLS Certificate Governance' in html
    assert 'TLS Certificate Registry' in html
    assert 'Quick Actions' in html
    assert 'Notifications' in html
    assert 'x-data="kaoriNavbar"' in html
