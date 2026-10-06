from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.access.users import service


class UserStub:
    def __init__(
        self,
        *,
        user_id: int,
        permissions: set[str] | None = None,
        auth_source: str = 'database',
        is_super_admin: bool = False,
        account_is_active: bool = True,
        deleted_at: datetime | None = None,
        username: str = 'operator',
        role_name: str = 'Viewer',
    ) -> None:
        self.id = user_id
        self.permissions = permissions or set()
        self.auth_source = auth_source
        self.is_super_admin = is_super_admin
        self.account_is_active = account_is_active
        self.deleted_at = deleted_at
        self.username = username
        self.email = f'{username}@example.invalid'
        self.role_record = None
        self.role_id = 1
        self.role_name = role_name
        self.updated_at: datetime | None = None
        self.password_updates: list[str] = []

    def has_permission(self, permission_key: str) -> bool:
        return permission_key in self.permissions

    def set_password(self, password: str) -> None:
        self.password_updates.append(password)


class SessionStub:
    def __init__(self, *, fail_flush: bool = False, fail_commit: bool = False) -> None:
        self.fail_flush = fail_flush
        self.fail_commit = fail_commit
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0

    def flush(self) -> None:
        self.flushes += 1
        if self.fail_flush:
            raise SQLAlchemyError('database unavailable')

    def commit(self) -> None:
        self.commits += 1
        if self.fail_commit:
            raise SQLAlchemyError('commit unavailable')

    def rollback(self) -> None:
        self.rollbacks += 1


def test_user_delete_requires_explicit_delete_permission() -> None:
    actor = UserStub(user_id=1, permissions={'users.manage'})
    target = UserStub(user_id=2)

    allowed, reason = service.can_delete_user(actor, target)  # type: ignore[arg-type]

    assert allowed is False
    assert reason == 'You do not have permission to delete users.'


def test_user_lifecycle_blocks_self_deactivation() -> None:
    actor = UserStub(user_id=1, permissions={'users.activate'})
    target = UserStub(user_id=1)

    allowed, reason = service.can_deactivate_user(actor, target)  # type: ignore[arg-type]

    assert allowed is False
    assert reason == 'You cannot change your own lifecycle status from User Management.'


@pytest.mark.parametrize(
    ('operation', 'permission', 'expected_reason'),
    [
        (
            service.can_deactivate_user,
            'users.activate',
            'The last active Local Database super admin cannot be deactivated.',
        ),
        (
            service.can_delete_user,
            'users.delete',
            'The last active Local Database super admin cannot be deleted.',
        ),
    ],
)
def test_last_local_super_admin_cannot_lose_lifecycle_authority(
    monkeypatch: pytest.MonkeyPatch,
    operation: Any,
    permission: str,
    expected_reason: str,
) -> None:
    actor = UserStub(user_id=1, permissions={permission}, is_super_admin=True, username='break-glass-1')
    target = UserStub(user_id=2, is_super_admin=True, username='break-glass-2')
    monkeypatch.setattr(service, 'is_last_active_local_super_admin', lambda _target: True)

    allowed, reason = operation(actor, target)

    assert allowed is False
    assert reason == expected_reason


def test_external_identity_password_reset_is_rejected() -> None:
    actor = UserStub(user_id=1, permissions={'users.reset_password'})
    target = UserStub(user_id=2, auth_source='oidc', username='federated-user')

    allowed, reason = service.can_reset_user_password(actor, target)  # type: ignore[arg-type]

    assert allowed is False
    assert reason == 'Password reset is only available for database-managed users.'


def test_delete_user_account_soft_deletes_and_records_audit_before_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SessionStub()
    actor = UserStub(user_id=1, permissions={'users.delete'}, username='admin')
    target = UserStub(user_id=2, username='retired-user')
    audit_events: list[dict[str, Any]] = []
    monkeypatch.setattr(service, 'db', type('DBStub', (), {'session': session})())
    monkeypatch.setattr(service, 'record_admin_event', lambda **kwargs: audit_events.append(kwargs))

    service.delete_user_account(actor=actor, user=target)  # type: ignore[arg-type]

    assert target.account_is_active is False
    assert target.deleted_at is not None
    assert target.updated_at == target.deleted_at
    assert target.deleted_at.tzinfo == UTC
    assert session.commits == 1
    assert session.rollbacks == 0
    assert len(audit_events) == 1
    assert audit_events[0]['action'] == 'user.deleted'
    assert audit_events[0]['target'] is target


def test_restore_user_account_keeps_activation_as_separate_admin_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SessionStub()
    actor = UserStub(user_id=1, permissions={'users.activate'}, username='admin')
    target = UserStub(
        user_id=2,
        account_is_active=False,
        deleted_at=datetime(2026, 9, 14, 8, 30, tzinfo=UTC),
        username='restored-user',
    )
    audit_events: list[dict[str, Any]] = []
    monkeypatch.setattr(service, 'db', type('DBStub', (), {'session': session})())
    monkeypatch.setattr(service, 'record_admin_event', lambda **kwargs: audit_events.append(kwargs))

    service.restore_user_account(actor=actor, user=target)  # type: ignore[arg-type]

    assert target.deleted_at is None
    assert target.account_is_active is False
    assert target.updated_at is not None
    assert session.commits == 1
    assert audit_events[0]['action'] == 'user.restored'


def test_created_user_persistence_rolls_back_and_reraises_database_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SessionStub(fail_flush=True)
    actor = UserStub(user_id=1, username='admin')
    target = UserStub(user_id=2, username='new-user')
    audit_events: list[dict[str, Any]] = []
    monkeypatch.setattr(service, 'db', type('DBStub', (), {'session': session})())
    monkeypatch.setattr(service, 'record_admin_event', lambda **kwargs: audit_events.append(kwargs))

    with pytest.raises(SQLAlchemyError, match='database unavailable'):
        service.persist_created_user(actor=actor, user=target)  # type: ignore[arg-type]

    assert session.flushes == 1
    assert session.commits == 0
    assert session.rollbacks == 1
    assert audit_events == []


def test_updated_user_persistence_rolls_back_when_commit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SessionStub(fail_commit=True)
    actor = UserStub(user_id=1, username='admin')
    target = UserStub(user_id=2, username='updated-user')
    audit_events: list[dict[str, Any]] = []
    monkeypatch.setattr(service, 'db', type('DBStub', (), {'session': session})())
    monkeypatch.setattr(service, 'record_admin_event', lambda **kwargs: audit_events.append(kwargs))

    with pytest.raises(SQLAlchemyError, match='commit unavailable'):
        service.persist_updated_user(actor=actor, user=target)  # type: ignore[arg-type]

    assert session.commits == 1
    assert session.rollbacks == 1
    assert len(audit_events) == 1
    assert audit_events[0]['action'] == 'user.updated'
