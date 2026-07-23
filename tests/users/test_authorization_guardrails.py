from __future__ import annotations

from types import SimpleNamespace

from app.models.user import User
from app.users.service import can_activate_user, can_create_user, can_deactivate_user, can_edit_user


class Actor:
    def __init__(self, permissions: set[str], *, is_super_admin: bool = False) -> None:
        self.id = 1
        self.is_super_admin = is_super_admin
        self._permissions = permissions

    def has_permission(self, permission_key: str) -> bool:
        return permission_key in self._permissions


def target_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=2,
        deleted_at=None,
        is_super_admin=False,
        account_is_active=True,
        role_id=10,
        role_name='viewer',
        auth_source='database',
    )


def test_inactive_persisted_role_revokes_permission() -> None:
    user = User()
    user.is_super_admin = False
    user.role_record = SimpleNamespace(
        is_active=False,
        name='admin',
        permission_keys=lambda: {'users.manage'},
    )

    assert user.has_permission('users.manage') is False


def test_active_persisted_role_uses_assigned_permissions() -> None:
    user = User()
    user.is_super_admin = False
    user.role_record = SimpleNamespace(
        is_active=True,
        name='custom_operator',
        permission_keys=lambda: {'users.view'},
    )

    assert user.has_permission('users.view') is True
    assert user.has_permission('users.manage') is False


def test_super_admin_bypasses_role_state() -> None:
    user = User()
    user.is_super_admin = True
    user.role_record = SimpleNamespace(is_active=False, name='admin')

    assert user.has_permission('users.manage') is True


def test_user_lifecycle_service_rejects_actor_without_required_permissions() -> None:
    actor = Actor(set())
    target = target_user()

    assert can_create_user(actor, requested_role_id=None, requested_is_super_admin=False)[0] is False
    assert can_activate_user(actor, target)[0] is False
    assert can_deactivate_user(actor, target)[0] is False
    assert can_edit_user(
        actor,
        target,
        requested_role_id=target.role_id,
        requested_is_active=True,
        requested_is_super_admin=False,
    )[0] is False
