"""Transient database failures must not revoke otherwise valid KAORI sessions (#3396)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask, g, session
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import login as login_extension


@pytest.fixture()
def app() -> Flask:
    app = Flask(__name__)
    app.secret_key = 'authentication-recovery-test-only'
    return app


def test_user_load_pool_error_fails_closed_without_clearing_session(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_db(_user_id: int) -> object:
        raise SQLAlchemyError('simulated pool timeout')

    monkeypatch.setattr(
        login_extension,
        'User',
        SimpleNamespace(query=SimpleNamespace(get=fail_db)),
    )
    monkeypatch.setattr(
        login_extension,
        'check_authentication_database_readiness',
        lambda: pytest.fail('Must not attempt another DB checkout after user-loader failure'),
    )

    with app.test_request_context('/notifications/panel/snapshot'):
        session.update({'_user_id': '11:2', 'auth_source': 'database', '_remember': 'set'})

        assert login_extension.load_user('11:2') is None
        assert g.authentication_database_unavailable is True
        assert session['_user_id'] == '11:2'
        assert session['_remember'] == 'set'

        response = app.make_response(login_extension.handle_unauthorized())

        assert response.status_code == 503
        assert response.headers['Cache-Control'] == 'no-store, max-age=0'
        assert response.headers['Retry-After'] == '5'
        assert session['_user_id'] == '11:2'
        assert session['_remember'] == 'set'


def test_missing_identity_still_revokes_session(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        login_extension,
        'User',
        SimpleNamespace(query=SimpleNamespace(get=lambda _user_id: None)),
    )

    with app.test_request_context('/notifications/panel/snapshot'):
        session.update({'_user_id': '11:2', 'auth_source': 'database', '_remember': 'set'})

        assert login_extension.load_user('11:2') is None
        assert '_user_id' not in session
        assert session['_remember'] == 'clear'
        assert not getattr(g, 'authentication_database_unavailable', False)


def test_valid_identity_can_be_loaded_after_transient_database_recovery(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = SimpleNamespace(
        auth_session_version=2,
        last_auth_source='database',
        auth_source='database',
    )
    available = {'database': False}

    def resolve_user(_user_id: int) -> object:
        if not available['database']:
            raise SQLAlchemyError('simulated temporary database failure')
        return actor

    monkeypatch.setattr(
        login_extension,
        'User',
        SimpleNamespace(query=SimpleNamespace(get=resolve_user)),
    )
    monkeypatch.setattr(login_extension, 'session_admission_reason', lambda _user, source: None)

    with app.test_request_context('/notifications/panel/snapshot'):
        session['_user_id'] = '11:2'
        assert login_extension.load_user('11:2') is None
        assert session['_user_id'] == '11:2'

    available['database'] = True
    with app.test_request_context('/notifications/panel/snapshot'):
        session['_user_id'] = '11:2'
        assert login_extension.load_user('11:2') is actor
        assert session['_user_id'] == '11:2'
