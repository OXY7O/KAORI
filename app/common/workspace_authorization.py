"""Shared Source Control UAT identity predicate used by navigation and access guards.

This checks only KAORI actor attributes and RBAC. Provider availability and
resource-level enforcement remain the responsibility of Source Control.
"""

from __future__ import annotations


def local_super_admin(user: object) -> bool:
    if not (
        getattr(user, 'is_authenticated', False)
        and getattr(user, 'is_super_admin', False)
        and getattr(user, 'auth_source', None) == 'database'
        and getattr(user, 'is_active', False)
    ):
        return False
    permission = getattr(user, 'has_permission', None)
    return bool(callable(permission) and permission('integrations.manage'))
