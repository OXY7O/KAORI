from __future__ import annotations

from types import SimpleNamespace

from flask import Flask, session

from app.auth import session as auth_session


def _app(*, allow_super_admin_remember: bool = False) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='test-secret',
        AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME=allow_super_admin_remember,
    )
    return app


def test_super_admin_remember_me_is_disabled_by_default(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(auth_session, 'login_user', lambda user, **kwargs: calls.append({'user': user, **kwargs}))
    user = SimpleNamespace(is_super_admin=True)

    with _app().test_request_context('/'):
        session['stale'] = 'value'
        remember = auth_session.establish_authenticated_session(
            user,
            source='database',
            remember_requested=True,
        )

        assert remember is False
        assert 'stale' not in session
        assert session['auth_source'] == 'database'
        assert calls[0]['remember'] is False
        assert calls[0]['fresh'] is True


def test_normal_user_remember_me_is_preserved(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(auth_session, 'login_user', lambda user, **kwargs: calls.append({'user': user, **kwargs}))
    user = SimpleNamespace(is_super_admin=False)

    with _app().test_request_context('/'):
        remember = auth_session.establish_authenticated_session(
            user,
            source='ldap',
            remember_requested=True,
        )

        assert remember is True
        assert session['auth_source'] == 'ldap'
        assert calls[0]['remember'] is True
