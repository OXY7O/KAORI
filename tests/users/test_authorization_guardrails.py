from __future__ import annotations

from types import SimpleNamespace

from app.models.rbac import Permission, Role
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
    role = Role(name='admin', display_name='Administrator', is_active=False)
    role.permissions = [Permission(key='users.manage', module='users', action='manage')]
    user.role_record = role

    assert user.has_permission('users.manage') is False


def test_active_persisted_role_uses_assigned_permissions() -> None:
    user = User()
    user.is_super_admin = False
    role = Role(name='custom_operator', display_name='Custom Operator', is_active=True)
    role.permissions = [Permission(key='users.view', module='users', action='view')]
    user.role_record = role

    assert user.has_permission('users.view') is True
    assert user.has_permission('users.manage') is False


def test_super_admin_bypasses_role_state() -> None:
    user = User()
    user.is_super_admin = True
    user.role_record = Role(name='admin', display_name='Administrator', is_active=False)

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


def test_user_without_persisted_role_fails_closed() -> None:
    user = User(username='orphan', email='orphan@example.com')

    assert user.role_record is None
    assert user.has_permission('inventory.view') is False


def test_super_admin_remains_break_glass_without_role_assignment() -> None:
    user = User(
        username='break-glass',
        email='break-glass@example.com',
        is_super_admin=True,
    )

    assert user.role_record is None
    assert user.has_permission('inventory.view') is True
