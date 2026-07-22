from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy.exc import SQLAlchemyError

from app.auth.providers import database


class ColumnStub:
    def __eq__(self, _other):
        return self

    def is_(self, _other):
        return self


class QueryStub:
    def __init__(self, *, user=None, error: Exception | None = None):
        self.user = user
        self.error = error

    def filter(self, *_conditions):
        if self.error is not None:
            raise self.error
        return self

    def first(self):
        return self.user


class UserModelStub:
    username = ColumnStub()
    deleted_at = ColumnStub()
    query = QueryStub()


class UserStub:
    def __init__(self, *, auth_source='database', password_matches=True, active=True):
        self.auth_source = auth_source
        self._password_matches = password_matches
        self.is_active = active

    def check_password(self, _password: str) -> bool:
        return self._password_matches


def _install_user_model(monkeypatch, query: QueryStub) -> None:
    UserModelStub.query = query
    monkeypatch.setattr(database, 'User', UserModelStub)


def test_unknown_user_returns_generic_invalid_credentials(monkeypatch) -> None:
    _install_user_model(monkeypatch, QueryStub(user=None))
    dummy_checks: list[str] = []
    monkeypatch.setattr(database, 'check_password_hash', lambda _hash, password: dummy_checks.append(password) or False)

    result = database.DatabaseAuthProvider().authenticate('missing', 'secret')

    assert result.reason == 'invalid_credentials'
    assert result.user is None
    assert dummy_checks == ['secret']


def test_external_identity_does_not_authenticate_against_local_hash(monkeypatch) -> None:
    user = UserStub(auth_source='ldap')
    _install_user_model(monkeypatch, QueryStub(user=user))
    monkeypatch.setattr(database, 'check_password_hash', lambda *_args: False)

    result = database.DatabaseAuthProvider().authenticate('operator', 'secret')

    assert result.reason == 'invalid_credentials'
    assert result.user is None


def test_inactive_local_user_is_rejected_after_password_verification(monkeypatch) -> None:
    user = UserStub(active=False)
    _install_user_model(monkeypatch, QueryStub(user=user))

    result = database.DatabaseAuthProvider().authenticate('operator', 'secret')

    assert result.reason == 'user_inactive'
    assert result.user is user


def test_database_error_rolls_back_and_returns_normalized_failure(monkeypatch) -> None:
    _install_user_model(monkeypatch, QueryStub(error=SQLAlchemyError('offline')))
    rollbacks: list[bool] = []
    monkeypatch.setattr(database, 'db', SimpleNamespace(session=SimpleNamespace(rollback=lambda: rollbacks.append(True))))

    result = database.DatabaseAuthProvider().authenticate('operator', 'secret')

    assert result.reason == 'database_unavailable'
    assert rollbacks == [True]
