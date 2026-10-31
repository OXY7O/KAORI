"""Identity Provider disablement revokes previously issued sessions (#2982)."""

from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.access.identity_providers import service
from app.models import User


class StubQuery:
    def __init__(self, *, affected: int = 2, fail_update: bool = False) -> None:
        self.affected = affected
        self.fail_update = fail_update
        self.filters: tuple[Any, ...] = ()
        self.updated: dict[Any, Any] | None = None
        self.sync: object = None
        self.calls = 0

    def filter(self, *expressions: Any) -> 'StubQuery':
        self.filters = expressions
        return self

    def update(self, values: dict[Any, Any], *, synchronize_session: object) -> int:
        self.calls += 1
        self.updated = values
        self.sync = synchronize_session
        if self.fail_update:
            raise SQLAlchemyError('update failed')
        return self.affected


class StubSession:
    def __init__(
        self,
        *,
        was_enabled: bool,
        affected: int = 2,
        fail_update: bool = False,
        fail_commit: bool = False,
    ) -> None:
        self.was_enabled = was_enabled
        self.query_stub = StubQuery(affected=affected, fail_update=fail_update)
        self.fail_commit = fail_commit
        self.lock_query = ''
        self.events: list[str] = []
        self.rollbacks = 0
        self.commits = 0

    def execute(self, statement: Any) -> SimpleNamespace:
        self.events.append('lock')
        self.lock_query = str(statement)
        return SimpleNamespace(scalar_one=lambda: self.was_enabled)

    def refresh(self, provider: SimpleNamespace) -> None:
        self.events.append('refresh')
        provider.enabled = self.was_enabled

    def query(self, model: Any) -> StubQuery:
        self.events.append('query')
        assert model is User
        return self.query_stub

    def commit(self) -> None:
        self.events.append('commit')
        self.commits += 1
        if self.fail_commit:
            raise SQLAlchemyError('commit failed')

    def rollback(self) -> None:
        self.events.append('rollback')
        self.rollbacks += 1


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    was_enabled: bool,
    requested_enabled: bool,
    affected: int = 2,
    fail_update: bool = False,
    fail_commit: bool = False,
) -> tuple[SimpleNamespace, StubSession, SimpleNamespace]:
    provider = SimpleNamespace(id=7, enabled=not was_enabled, provider_key='ldap')
    config = SimpleNamespace(enabled=requested_enabled)
    session = StubSession(
        was_enabled=was_enabled,
        affected=affected,
        fail_update=fail_update,
        fail_commit=fail_commit,
    )
    monkeypatch.setattr(service.db, 'session', session)
    monkeypatch.setattr(service, 'ensure_provider_identity_continuity', lambda *_args: None)
    monkeypatch.setattr(
        service,
        'apply_identity_provider_configuration',
        lambda p, c: setattr(p, 'enabled', c.enabled),
    )
    return provider, session, config


def test_enabled_to_disabled_invalidates_each_linked_external_account_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, session, config = _install(monkeypatch, was_enabled=True, requested_enabled=False, affected=3)

    returned, revoked = service.update_identity_provider(provider, config)

    assert returned is provider
    assert provider.enabled is False
    assert revoked == 3  # Linked accounts, not number of open browser tabs.
    assert session.commits == 1
    assert session.rollbacks == 0
    assert session.query_stub.calls == 1
    assert session.query_stub.sync is False
    assert session.events == ['lock', 'refresh', 'query', 'commit']
    assert 'FOR UPDATE' in session.lock_query
    criteria = ' | '.join(map(str, session.query_stub.filters))
    assert 'users.auth_source' in criteria
    assert 'users.is_super_admin' in criteria
    assert 'users.deleted_at' in criteria
    assert 'external_identity_links.provider_id' in criteria
    assert 'users.id IN' in criteria
    value = next(iter((session.query_stub.updated or {}).values()))
    assert 'greatest(' in str(value).lower()
    assert 'users.auth_session_version' in str(value)


@pytest.mark.parametrize(
    ('previous', 'requested'),
    [(False, False), (False, True), (True, True)],
)
def test_non_disabling_transition_never_revokes_existing_sessions(
    monkeypatch: pytest.MonkeyPatch,
    previous: bool,
    requested: bool,
) -> None:
    provider, session, config = _install(monkeypatch, was_enabled=previous, requested_enabled=requested)

    _, revoked = service.update_identity_provider(provider, config)

    assert revoked == 0
    assert session.query_stub.calls == 0
    assert session.commits == 1
    assert provider.enabled is requested


@pytest.mark.parametrize('phase', ['update', 'commit'])
def test_provider_disable_and_session_revocation_rollback_together_on_sql_failure(
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    provider, session, config = _install(
        monkeypatch,
        was_enabled=True,
        requested_enabled=False,
        fail_update=phase == 'update',
        fail_commit=phase == 'commit',
    )
    with pytest.raises(SQLAlchemyError):
        service.update_identity_provider(provider, config)

    assert session.rollbacks == 1
    assert session.query_stub.calls == 1
    assert session.commits == (1 if phase == 'commit' else 0)


def test_generation_change_revokes_all_old_cookies_even_after_reenable() -> None:
    account = User(id=41, auth_source='ldap', auth_session_version=4)
    previous_cookie = account.get_id()

    account.auth_session_version += 1
    assert previous_cookie == '41:4'
    assert account.get_id() == '41:5'
    # Re-enabling the provider must not decrement the generation or revive 41:4.
    account.auth_session_version = 5
    assert account.get_id() != previous_cookie
