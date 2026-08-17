from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask_login import UserMixin

from app import create_app
from app.bootstrap import presentation as bootstrap_presentation
from app.kubernetes.dashboard import routes as dashboard_routes
from app.kubernetes.dashboard.schema import DashboardOverview
from app.extensions import login as login_extension
from app.extensions import login_manager


class DashboardSmokeUser(UserMixin):
    id = 2
    username = 'dashboard-smoke'
    display_label = 'Dashboard Smoke'
    role_name = 'super_admin'
    role_display_name = 'Super Admin'
    timezone = 'UTC'
    timezone_mode = 'manual'
    locale = 'en-US'
    date_format = 'day_month_year'
    time_format = '24h'

    def get_id(self) -> str:
        return 'dashboard-smoke'

    def has_permission(self, permission_key: str) -> bool:
        return permission_key == 'dashboard.view'


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
    monkeypatch.setattr(dashboard_routes, 'get_dashboard_overview', lambda **_kwargs: DashboardOverview())
    monkeypatch.setattr(dashboard_routes, 'get_dashboard_section', lambda *_args, **_kwargs: DashboardOverview())
    monkeypatch.setattr(dashboard_routes, 'has_registered_clusters', lambda: True)
    return create_app('testing')


def test_anonymous_user_is_redirected_before_dashboard_render(app) -> None:
    response = app.test_client().get('/dashboards/kubernetes/')

    assert response.status_code == 302
    assert '/login?next=' in response.headers['Location']


def test_authorized_user_renders_dashboard_and_lazy_section_in_application_shell(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = DashboardSmokeUser()
    monkeypatch.setattr(login_manager, '_user_callback', lambda _user_id: user)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = user.get_id()
        session['_fresh'] = True
        session['auth_source'] = 'database'

    page = client.get('/dashboards/kubernetes/')
    section = client.get('/dashboards/kubernetes/section/capacity_snapshot')
    html = page.get_data(as_text=True)

    assert page.status_code == 200
    assert section.status_code == 200
    assert 'Kubernetes Operations Dashboard' in html
    assert 'Operations Overview' in html
    assert 'Quick Actions' in html
    assert 'Notifications' in html
    assert 'x-data="kaoriNavbar"' in html
    assert 'Capacity Snapshot' in section.get_data(as_text=True)
