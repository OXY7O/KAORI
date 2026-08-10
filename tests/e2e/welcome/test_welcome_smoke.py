from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask_login import UserMixin

from app import create_app
from app.bootstrap import presentation as bootstrap_presentation
from app.extensions import login as login_extension
from app.extensions import login_manager


class SmokeUser(UserMixin):
    id = 1
    username = 'welcome-smoke'
    display_label = 'Welcome Smoke'
    role_name = 'super_admin'
    role_display_name = 'Super Admin'
    timezone = 'UTC'
    timezone_mode = 'manual'
    locale = 'en-US'
    date_format = 'day_month_year'
    time_format = '24h'

    def get_id(self) -> str:
        return 'welcome-smoke'

    def has_permission(self, _permission_key: str) -> bool:
        return True


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
        'is_kubernetes_scope': False,
        'is_blocked': False,
        'has_clusters': False,
        'cluster_count': 0,
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


def test_anonymous_user_is_redirected_to_login_before_welcome_render(app) -> None:
    client = app.test_client()

    response = client.get('/welcome')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login?next=/welcome')


def test_authenticated_user_can_render_welcome_with_global_application_shell(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = SmokeUser()
    monkeypatch.setattr(login_manager, '_user_callback', lambda _user_id: user)

    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = user.get_id()
        session['_fresh'] = True
        session['auth_source'] = 'database'

    welcome_response = client.get('/welcome')
    root_response = client.get('/')
    html = welcome_response.get_data(as_text=True)

    assert welcome_response.status_code == 200
    assert root_response.status_code == 200
    assert 'Welcome to KAORI' in html
    assert 'Welcome to KAORI' in root_response.get_data(as_text=True)
    assert 'Choose a Workspace' in html
    assert 'Quick Actions' in html
    assert 'Notifications' in html
    assert 'Account Settings' in html
    assert 'x-data="kaoriNavbar"' in html
