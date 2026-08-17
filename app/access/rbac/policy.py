from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from app.access.rbac.defaults import ACCESS_ADMINISTRATION_PERMISSIONS, DEFAULT_ROLE_DEFINITIONS


class _RoleLike(Protocol):
    name: str
    is_active: bool

    def permission_keys(self) -> set[str]: ...


class _UserLike(Protocol):
    auth_source: str
    is_super_admin: bool
    role_record: _RoleLike | None


def is_local_break_glass(user: _UserLike) -> bool:
    return bool(user.auth_source == 'database' and user.is_super_admin)


def role_is_protected_default(role: _RoleLike | None) -> bool:
    return bool(role and role.name in DEFAULT_ROLE_DEFINITIONS)


def role_is_mutation_protected(role: _RoleLike | None) -> bool:
    return bool(role and (role_is_protected_default(role) or bool(getattr(role, 'is_system', False))))


def role_slug_is_reserved(slug: str | None) -> bool:
    return str(slug or '').strip().lower() in DEFAULT_ROLE_DEFINITIONS


def role_is_access_admin_level(role: _RoleLike | None) -> bool:
    if role is None:
        return False
    return bool(role.permission_keys() & ACCESS_ADMINISTRATION_PERMISSIONS)


def actor_delegable_permission_keys(actor: _UserLike) -> set[str] | None:
    if is_local_break_glass(actor):
        return None
    role = actor.role_record
    if role is None or not role.is_active:
        return set()
    return role.permission_keys() - ACCESS_ADMINISTRATION_PERMISSIONS


def permission_keys_are_delegable_by_actor(actor: _UserLike, permission_keys: Iterable[str]) -> bool:
    selected = set(permission_keys)
    if is_local_break_glass(actor):
        return True
    if selected & ACCESS_ADMINISTRATION_PERMISSIONS:
        return False
    delegable = actor_delegable_permission_keys(actor)
    return bool(delegable is None or selected.issubset(delegable))


def role_is_delegable_by_actor(actor: _UserLike, role: _RoleLike | None) -> bool:
    if role is None or not role.is_active:
        return False
    return permission_keys_are_delegable_by_actor(actor, role.permission_keys())
