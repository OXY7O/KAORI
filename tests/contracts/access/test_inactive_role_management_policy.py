"""Inactive role lifecycle management, without weakening assignment eligibility."""

from types import SimpleNamespace

from app.access.rbac.policy import (
    role_is_delegable_by_actor,
    role_is_manageable_by_actor,
)


def _role(*keys: str, is_active: bool = False):
    return SimpleNamespace(is_active=is_active, permission_keys=lambda: set(keys))


def test_local_database_break_glass_can_manage_inactive_role() -> None:
    actor = SimpleNamespace(auth_source='database', is_super_admin=True, role_record=None)
    inactive = _role('roles.view', 'roles.manage')
    assert role_is_manageable_by_actor(actor, inactive)
    assert not role_is_delegable_by_actor(actor, inactive)
    assert role_is_manageable_by_actor(actor, _role('roles.view', is_active=True))


def test_bounded_manager_can_recover_inactive_role_without_escalation() -> None:
    active_ceiling = _role('roles.manage', 'roles.view', 'users.view', is_active=True)
    actor = SimpleNamespace(auth_source='database', is_super_admin=False, role_record=active_ceiling)
    assert role_is_manageable_by_actor(actor, _role('users.view'))
    assert not role_is_manageable_by_actor(actor, _role('users.manage'))
    assert not role_is_manageable_by_actor(actor, _role('roles.manage'))

    inactive_ceiling = _role('roles.manage', is_active=False)
    actor.role_record = inactive_ceiling
    assert not role_is_manageable_by_actor(actor, _role('users.view'))
    assert not role_is_manageable_by_actor(actor, _role('roles.manage'))


def test_non_database_super_admin_flag_is_not_break_glass() -> None:
    actor = SimpleNamespace(auth_source='oidc', is_super_admin=True, role_record=None)
    assert not role_is_manageable_by_actor(actor, _role('roles.manage'))
    assert not role_is_manageable_by_actor(actor, _role('users.manage'))
