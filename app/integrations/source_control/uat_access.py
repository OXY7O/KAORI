"""Fail-closed temporary Dev Container Source Control UAT admission (#2742).

Not a substitute for #724 resource-scoped authorization. No ordinary RBAC
user can browse or manually refresh arbitrary GitHub App installations.
The authorized production policy must replace this temporary UAT boundary.
"""

from __future__ import annotations

from flask import abort, current_app
from flask_login import current_user

from app.integrations.provider_matrix import provider_kind


def uat_enabled() -> bool:
    return bool(
        current_app.config.get('SOURCE_CONTROL_GITHUB_UAT_ENABLED', False)
        and provider_kind('source_control', 'github').available
    )


def local_super_admin(user: object) -> bool:
    return bool(
        getattr(user, 'is_authenticated', False)
        and getattr(user, 'is_super_admin', False)
        and getattr(user, 'auth_source', None) == 'database'
        and getattr(user, 'is_active', False)
        and callable(getattr(user, 'has_permission', None))
        and user.has_permission('integrations.manage')
    )


def require_uat_access() -> None:
    if not uat_enabled():
        abort(404)
    if not local_super_admin(current_user):
        abort(403)
