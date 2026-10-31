"""Scoped Dev Container Source Control UAT authorization (#2742).

Not a substitute for #724 resource-scoped authorization. No ordinary RBAC
user can browse or manually refresh arbitrary GitHub App installations.
This UAT boundary follows provider admission without a separate toggle.
The production resource-scope policy must eventually replace it.
"""

from __future__ import annotations

from flask import abort
from flask_login import current_user

from app.common.workspace_authorization import local_super_admin
from app.integrations.provider_matrix import provider_kind


def uat_enabled() -> bool:
    return provider_kind('source_control', 'github').available


def require_uat_access() -> None:
    if not uat_enabled():
        abort(404)
    if not local_super_admin(current_user):
        abort(403)
