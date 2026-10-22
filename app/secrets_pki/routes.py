"""Capability-owned operational Overview and bounded Inventory Evidence pages."""

from __future__ import annotations

from flask import Blueprint, render_template, request
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.access.rbac.decorators import permission_required
from app.dashboards.common.operational import normalize_operational_tab
from app.secrets_pki.presentation import build_secrets_pki_operational_summary
from app.secrets_pki.pki_presentation import pki_public_readiness

secrets_pki_bp = Blueprint('secrets_pki', __name__, url_prefix='/secrets-pki')


@secrets_pki_bp.get('/')
@permission_required('secrets_pki.view')
def overview() -> ResponseReturnValue:
    return render_template(
        'secrets_pki/overview.html',
        summary=build_secrets_pki_operational_summary(),
        active_tab=normalize_operational_tab(request.args.get('tab')),
        can_manage_integrations=current_user.has_permission('integrations.manage'),
        can_view_intelligence=current_user.has_permission('intelligence.view'),
        can_view_reports=current_user.has_permission('reports.view'),
    )


@secrets_pki_bp.get('/inventory')
@permission_required('secrets_pki.view')
def inventory() -> ResponseReturnValue:
    return render_template(
        'secrets_pki/inventory.html',
        summary=build_secrets_pki_operational_summary(),
        pki_readiness=pki_public_readiness(),
        can_manage_integrations=current_user.has_permission('integrations.manage'),
        can_execute_inventory=current_user.has_permission('secrets_pki.sync')
        and current_user.has_permission('jobs.execute'),
    )
