from __future__ import annotations

from flask import Blueprint, render_template

from app.access.permissions.presentation import build_permission_catalog_context
from app.rbac.decorators import permission_required

bp = Blueprint('permissions', __name__)


@bp.get('/')
@permission_required('roles.view')
def index():
    return render_template(
        'access/permissions/index.html',
        **build_permission_catalog_context(),
    )
