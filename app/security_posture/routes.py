"""Cross-domain Security Posture workspace: read-only, permission-gated."""

from __future__ import annotations

from flask import Blueprint, render_template, request
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.access.rbac.decorators import permission_required
from app.dashboards.common.operational import normalize_operational_tab
from app.security_posture.presentation import build_security_posture

security_posture_bp = Blueprint('security_posture', __name__, url_prefix='/security')


@security_posture_bp.get('/')
@permission_required('security_posture.view')
def overview() -> ResponseReturnValue:
    posture = build_security_posture(can_view_registry=current_user.has_permission('artifact_registry.view'))
    return render_template(
        'security_posture/overview.html',
        posture=posture,
        active_tab=normalize_operational_tab(request.args.get('tab')),
        can_view_intelligence=current_user.has_permission('intelligence.view'),
        can_view_reports=current_user.has_permission('reports.view'),
        can_manage_integrations=current_user.has_permission('integrations.manage'),
    )


@security_posture_bp.get('/findings')
@permission_required('security_posture.view')
def findings() -> ResponseReturnValue:
    posture = build_security_posture(
        can_view_registry=current_user.has_permission('artifact_registry.view'),
        search=request.args.get('q', '', type=str),
        severity=request.args.get('severity', '', type=str),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    return render_template('security_posture/findings.html', posture=posture)
