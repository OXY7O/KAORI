from __future__ import annotations

from flask import Blueprint, render_template, request

from app.access.permissions.presentation import (
    build_permission_catalog_context,
    build_permission_detail_context,
    normalize_permission_filters,
)
from app.access.rbac.decorators import permission_required

bp = Blueprint('permissions', __name__)


@bp.get('/')
@permission_required('roles.view')
def index():
    filters = normalize_permission_filters(request.args.to_dict())
    payload = build_permission_catalog_context(filters)
    if request.headers.get('HX-Request') == 'true':
        return render_template('access/permissions/partials/_workspace.html', **payload)
    return render_template('access/permissions/index.html', **payload)


@bp.get('/<string:permission_key>/details')
@permission_required('roles.view')
def modal_details(permission_key: str):
    payload = build_permission_detail_context(permission_key)
    if payload is None:
        return 'Permission details unavailable.', 404
    return render_template('access/permissions/partials/_permission_detail.html', **payload)
