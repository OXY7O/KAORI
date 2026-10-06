from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask_login import UserMixin

from app import create_app
from app.analytics import routes as analytics_routes
from app.bootstrap import presentation as bootstrap_presentation
from app.extensions import login as login_extension
from app.extensions import login_manager
from app.kubernetes.analytics.overview.schema import build_empty_overview_payload


class AnalyticsSmokeUser(UserMixin):
    id = 86
    username = 'analytics-smoke'
    display_label = 'Analytics Smoke'
    role_name = 'analytics_test'
    role_display_name = 'Analytics Test'
    timezone = 'UTC'
    timezone_mode = 'manual'
    locale = 'en-US'
    date_format = 'day_month_year'
    time_format = '24h'

    def get_id(self) -> str:
        return 'analytics-smoke'

    def has_permission(self, permission_key: str) -> bool:
        return permission_key in {'analytics.view', 'clusters.manage'}


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


def _overview_payload() -> dict[str, object]:
    payload = build_empty_overview_payload()
    payload['clusters'] = [{'id': 'cluster-analytics', 'name': 'Analytics Cluster', 'environment': 'test'}]
    payload['selected_cluster'] = payload['clusters'][0]
    payload['selected_cluster_id'] = 'cluster-analytics'
    payload['selected_time_range'] = '24h'
    return payload


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
    monkeypatch.setattr(analytics_routes, 'get_analytics_overview', lambda **_kwargs: _overview_payload())
    return create_app('testing')


def test_anonymous_user_is_redirected_before_analytics_render(app) -> None:
    response = app.test_client().get('/analytics/')
    assert response.status_code == 302
    assert '/login?next=' in response.headers['Location']


def test_authorized_user_renders_analytics_overview_in_global_shell(app, monkeypatch: pytest.MonkeyPatch) -> None:
    user = AnalyticsSmokeUser()
    monkeypatch.setattr(login_manager, '_user_callback', lambda _user_id: user)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = user.get_id()
        session['_fresh'] = True
        session['auth_source'] = 'database'

    response = client.get('/analytics/?cluster_id=cluster-analytics&time_range=24h')
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Analytics Overview' in html
    assert 'Analytics Overview Workspace' in html
    assert 'data-analytics-tabset-id="overview-content"' in html
    assert 'Quick Actions' in html and 'Notifications' in html
    assert 'x-data="kaoriNavbar"' in html
