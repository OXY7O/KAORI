from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import url_for

from app import create_app
from app.auth import routes as auth_routes
from app.auth.results import AuthResult
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


def test_login_page_renders_compact_authentication_surface(app) -> None:
    client = app.test_client()
    with app.test_request_context():
        login_url = url_for('auth.login')

    response = client.get(login_url)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Secure Platform Access' in html
    assert 'Welcome Back' in html
    assert 'Remember Me' in html
    assert 'Authentication Activity Is Recorded for Audit' in html
    assert 'auth_login.js' in html


def test_invalid_credentials_return_generic_failure_without_account_disclosure(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit_events: list[tuple[str, str]] = []
    feedback: list[str] = []
    monkeypatch.setattr(
        auth_routes,
        'authenticate',
        lambda _username, _password: AuthResult(False, 'invalid_credentials', source='database'),
    )
    monkeypatch.setattr(
        auth_routes,
        '_record_result',
        lambda username, result: audit_events.append((username, result.reason)),
    )
    monkeypatch.setattr(
        auth_routes,
        'queue_transient_feedback',
        lambda **payload: feedback.append(str(payload['message'])),
    )

    with app.test_request_context():
        login_url = url_for('auth.login')
    response = app.test_client().post(login_url, data={'username': 'admin', 'password': 'wrong-password'})

    assert response.status_code == 200
    assert audit_events == [('admin', 'invalid_credentials')]
    assert feedback
    assert all('provider' not in message.lower() for message in feedback)
    assert all('role' not in message.lower() for message in feedback)


def test_unsafe_next_target_is_not_reflected_into_login_form(app) -> None:
    with app.test_request_context():
        login_url = url_for('auth.login')
    response = app.test_client().get(login_url, query_string={'next': 'https://example.invalid/phish'})
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'https://example.invalid/phish' not in html
