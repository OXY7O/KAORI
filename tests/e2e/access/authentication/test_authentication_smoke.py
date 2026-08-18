from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import url_for

from app import create_app
from app.access.authentication import routes as auth_routes
from app.bootstrap import presentation as bootstrap_presentation


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        auth_routes,
        'check_authentication_database_readiness',
        lambda: SimpleNamespace(ready=True, setup_required=False, missing_tables=()),
    )
    monkeypatch.setattr(auth_routes, 'enabled_sso_providers', lambda: [])
    monkeypatch.setattr(bootstrap_presentation, 'pop_operational_feedback', lambda: None)
    return create_app('testing')


def test_login_smoke_renders_real_auth_blueprint_and_static_runtime(app) -> None:
    with app.test_request_context():
        login_url = url_for('auth.login')
    response = app.test_client().get(login_url)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'KAORI sign in' in html
    assert 'js/auth_login.js' in html
    assert 'js/operational_toasts.js' in html
    assert 'data-password-toggle' in html
    assert 'auth-theme-toggle' in html


def test_login_smoke_fails_closed_to_database_setup_surface(app, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        auth_routes,
        'check_authentication_database_readiness',
        lambda: SimpleNamespace(ready=False, setup_required=True, missing_tables=('users', 'roles')),
    )

    with app.test_request_context():
        login_url = url_for('auth.login')
    response = app.test_client().get(login_url)
    html = response.get_data(as_text=True)

    assert response.status_code == 503
    assert 'Database Setup Required' in html
    assert 'bash scripts/init_db.sh --bootstrap-admin' in html
    assert 'users' in html
    assert 'roles' in html
