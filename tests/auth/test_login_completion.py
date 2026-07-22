from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.auth import routes
from app.auth.results import AuthResult


def _app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'
    app.add_url_rule('/', endpoint='welcome.index', view_func=lambda: 'ok')
    return app


def test_successful_login_commits_metadata_before_establishing_session(monkeypatch) -> None:
    events: list[object] = []
    user = SimpleNamespace(
        last_login_at=None,
        last_login_ip=None,
        last_auth_source=None,
        is_super_admin=False,
    )
    monkeypatch.setattr(
        routes,
        'db',
        SimpleNamespace(session=SimpleNamespace(commit=lambda: events.append('commit'), rollback=lambda: events.append('rollback'))),
    )
    monkeypatch.setattr(
        routes,
        'establish_authenticated_session',
        lambda _user, **kwargs: events.append(('session', kwargs)),
    )

    with _app().test_request_context('/auth/login', environ_base={'REMOTE_ADDR': '10.0.0.5'}):
        response = routes._complete_successful_login(
            AuthResult(True, 'success', source='ldap', user=user),
            remember_requested=True,
        )

    assert events[0] == 'commit'
    assert events[1] == ('session', {'source': 'ldap', 'remember_requested': True})
    assert user.last_login_ip == '10.0.0.5'
    assert user.last_auth_source == 'ldap'
    assert response.status_code == 302


def test_login_metadata_commit_failure_rolls_back_without_creating_session(monkeypatch) -> None:
    events: list[str] = []
    user = SimpleNamespace(
        last_login_at=None,
        last_login_ip=None,
        last_auth_source=None,
        is_super_admin=False,
    )

    def fail_commit() -> None:
        events.append('commit')
        raise SQLAlchemyError('offline')

    monkeypatch.setattr(
        routes,
        'db',
        SimpleNamespace(session=SimpleNamespace(commit=fail_commit, rollback=lambda: events.append('rollback'))),
    )
    monkeypatch.setattr(
        routes,
        'establish_authenticated_session',
        lambda *_args, **_kwargs: events.append('session'),
    )

    with _app().test_request_context('/auth/login'):
        with pytest.raises(SQLAlchemyError):
            routes._complete_successful_login(AuthResult(True, 'success', user=user))

    assert events == ['commit', 'rollback']
