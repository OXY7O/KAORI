from __future__ import annotations

from dataclasses import dataclass

from app.models.user import User


@dataclass(frozen=True)
class UserLifecycleState:
    key: str
    label: str
    mutable: bool


def lifecycle_state(user: User) -> UserLifecycleState:
    if user.deleted_at is not None:
        return UserLifecycleState('deleted', 'Deleted', False)
    if not user.account_is_active:
        return UserLifecycleState('inactive', 'Inactive', True)
    return UserLifecycleState('active', 'Active', True)


def administrative_tier(user: User) -> str:
    if user.is_super_admin:
        return 'super_admin'
    if user.role_name == 'admin':
        return 'admin'
    return 'standard'
