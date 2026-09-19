from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import create_app
from app.bootstrap import presentation as bootstrap_presentation
from app.extensions import login as login_extension
from app.settings import routes as settings_routes


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
        'can_manage_clusters': False,
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


@pytest.mark.parametrize(
    ('path', 'guard_dependency'),
    [
        ('/settings/general', 'TimezonePreferenceForm'),
        ('/settings/account', 'ChangePasswordForm'),
    ],
)
def test_anonymous_settings_routes_redirect_before_route_dependencies(
    app,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    guard_dependency: str,
) -> None:
    def unexpected_route_dependency(*_args, **_kwargs):
        raise AssertionError(f'{guard_dependency} must not run before login authorization')

    monkeypatch.setattr(settings_routes, guard_dependency, unexpected_route_dependency)

    response = app.test_client().get(path, follow_redirects=False)

    assert response.status_code == 302
    location = response.headers['Location']
    assert '/login' in location
    assert 'next=' in location
