"""One login generation per identity, independent of browser/SSO provider (#3121)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from flask import Flask, session
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication import audit, services, session as auth_session
from app.models import User


class GenerationStore:
    def __init__(self, *, issued: int | None = 2, fail: bool = False) -> None:
        self.issued = issued
        self.fail = fail
        self.statements: list[Any] = []
        self.commits = 0
        self.rollbacks = 0
        self.events: list[str] = []

    def execute(self, statement: Any) -> SimpleNamespace:
        self.events.append('execute')
        self.statements.append(statement)
        if self.fail:
            raise SQLAlchemyError('simulated commit boundary failure')
        return SimpleNamespace(scalar_one_or_none=lambda: self.issued)

    def commit(self) -> None:
        self.commits += 1
        self.events.append('commit')

    def rollback(self) -> None:
        self.rollbacks += 1
        self.events.append('rollback')


def test_login_generation_is_atomic_database_update_with_exact_returning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = GenerationStore(issued=8)
    monkeypatch.setattr(services.db, 'session', store)
    actor = User(id=41, auth_source='database', auth_session_version=7)

    issued = services.record_successful_authentication(actor, source='database', client_ip='192.0.2.8')

    assert issued == 8
    assert store.commits == 1 and store.rollbacks == 0
    assert store.events == ['execute', 'commit']
    statement = str(store.statements[0]).lower()
    assert statement.startswith('update users')
    assert 'coalesce(' in statement and 'auth_session_version' in statement
    assert 'returning users.auth_session_version' in statement
    assert 'users.is_active' in statement and 'users.deleted_at' in statement
    assert 'lower(users.auth_source)' in statement


def test_failed_or_stale_login_admission_never_commits_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = GenerationStore(issued=None)
    monkeypatch.setattr(services.db, 'session', store)

    with pytest.raises(auth_session.AuthSessionError):
        services.record_successful_authentication(
            User(id=42, auth_source='ldap'), source='ldap', client_ip=None
        )
    assert store.commits == 0
    assert store.rollbacks == 1


def test_database_failure_rolls_back_generation_issuance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = GenerationStore(fail=True)
    monkeypatch.setattr(services.db, 'session', store)

    with pytest.raises(SQLAlchemyError):
        services.record_successful_authentication(
            User(id=43, auth_source='database'), source='database', client_ip=None
        )
    assert store.commits == 0
    assert store.rollbacks == 1


def test_browser_and_remember_cookie_use_issued_version_not_later_orm_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = Flask(__name__)
    app.secret_key = 'test-only-not-a-credential'
    actor = User(id=44, auth_source='ldap', auth_session_version=10)

    def login_stub(user: User, *, remember: bool, fresh: bool) -> bool:
        assert fresh and remember
        # Emulate an ORM refresh that observes a *later* concurrent login.
        session['_user_id'] = user.get_id()
        session['_remember'] = 'set'
        return True

    monkeypatch.setattr(auth_session, 'login_user', login_stub)
    with app.test_request_context('/auth/login', method='POST'):
        authenticated = auth_session.establish_authenticated_session(
            actor, source='ldap', remember_requested=True, issued_session_version=9
        )
        assert authenticated is True
        assert session['_user_id'] == '44:9'
        assert session['_remember'] == 'set'
        assert session['auth_source'] == 'ldap'
        assert len(session['auth_session_ref']) == 32
        assert auth_session.parse_authenticated_user_identifier(session['_user_id']) == (44, 9)
        # The authoritative user generation is 10, so the old login is no
        # longer admissible on the next Flask-Login load.
        assert session['_user_id'] != actor.get_id()


def test_super_admin_remember_me_stays_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = Flask(__name__)
    app.secret_key = 'test-only-not-a-credential'
    actor = User(id=45, auth_source='database', auth_session_version=12, is_super_admin=True)

    def login_stub(user: User, *, remember: bool, fresh: bool) -> bool:
        assert not remember and fresh
        session['_user_id'] = user.get_id()
        return True

    monkeypatch.setattr(auth_session, 'login_user', login_stub)
    with app.test_request_context('/auth/login', method='POST'):
        assert not auth_session.establish_authenticated_session(
            actor, source='database', remember_requested=True, issued_session_version=12
        )
        assert session['_user_id'] == '45:12'


def test_audit_correlation_is_only_an_opaque_non_credential_reference() -> None:
    app = Flask(__name__)
    app.secret_key = 'test-only-not-a-credential'
    with app.test_request_context('/auth/login'):
        session['auth_session_ref'] = 'a' * 32
        assert audit._audit_session_reference() == 'a' * 32
        session['auth_session_ref'] = 'cookie-or-user-controlled-string'
        assert audit._audit_session_reference() is None
        session.pop('auth_session_ref')
        assert audit._audit_session_reference() is None


def test_authentication_audit_correlates_only_actual_authenticated_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = Flask(__name__)
    app.secret_key = 'test-only-not-a-credential'
    committed: list[Any] = []

    class StubAuditStore:
        def add(self, record: Any) -> None:
            committed.append(record)

        def commit(self) -> None:
            pass

        def rollback(self) -> None:
            raise AssertionError('No database rollback expected.')

    class AuditRecord:
        pass

    def actor_snapshot(user: User | None = None) -> SimpleNamespace:
        key = f'user:{user.id}' if user is not None else 'unauthenticated'
        return SimpleNamespace(key=key, label=key, as_json=lambda: {'actor': key})

    monkeypatch.setattr(audit.db, 'session', StubAuditStore())
    monkeypatch.setattr(audit, 'Notification', AuditRecord)
    monkeypatch.setattr(audit, 'event_category_key', lambda value: value)
    monkeypatch.setattr(audit, '_provider_label', lambda value: 'Local Database')
    monkeypatch.setattr(audit, 'actor_snapshot_for_user', actor_snapshot)
    monkeypatch.setattr(audit, 'unauthenticated_actor_snapshot', actor_snapshot)
    monkeypatch.setattr(audit, 'redact_operational_text', lambda value, **kwargs: value)
    monkeypatch.setattr(audit, 'redact_operational_metadata', lambda value: value)
    actor = User(id=46, username='kaori-uat-user', auth_source='database')

    with app.test_request_context('/auth/login', method='POST'):
        session['auth_session_ref'] = 'b' * 32
        audit.record_authentication_activity(
            action='login', username=actor.username, source='database',
            result='success', reason='success', user=actor,
        )
        assert committed[-1].actor_key == 'user:46'
        assert committed[-1].metadata_json['session_reference'] == 'b' * 32
        assert committed[-1].metadata_json['session_policy'] == 'single_active_login_generation'

        audit.record_authentication_activity(
            action='logout', username=actor.username, source='database',
            result='success', reason='user_initiated', user=actor,
        )
        assert committed[-1].metadata_json['session_reference'] == 'b' * 32
        assert committed[-1].metadata_json['session_policy'] is None

        # Even a failed attempt targeting the same User never becomes the
        # account's authenticated actor or inherits its login reference.
        audit.record_authentication_activity(
            action='login', username=actor.username, source='database',
            result='failed', reason='invalid_credentials', user=actor,
        )
        assert committed[-1].actor_key == 'unauthenticated'
        assert committed[-1].metadata_json['session_reference'] is None
