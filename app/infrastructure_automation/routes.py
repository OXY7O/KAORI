"""Read-only Infrastructure Automation control-plane view (#5157)."""

from __future__ import annotations

from flask import Blueprint, abort, render_template, request
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.access.rbac.decorators import permission_required
from app.common.http import htmx_target, is_htmx_request
from app.infrastructure_automation.workspace import build_automation_workspace

bp = Blueprint('infrastructure_automation', __name__)


@bp.get('/')
@permission_required('integrations.manage')
def index() -> ResponseReturnValue:
    """Review canonical source/Plan/Job/Cluster evidence without provider I/O."""
    try:
        context = build_automation_workspace(
            query=request.args.get('q', '').strip(),
            page=request.args.get('page', 1, type=int) or 1,
            per_page=request.args.get('per_page', 5, type=int) or 5,
            connection_id=request.args.get('connection_id', type=int),
            asset_page=request.args.get('asset_page', 1, type=int) or 1,
            can_jobs=bool(current_user.has_permission('jobs.view')),
            can_inventory=bool(current_user.has_permission('inventory.view')),
        )
    except ValueError:
        abort(404)
    template = (
        'infrastructure_automation/_lifecycle_workspace.html'
        if is_htmx_request() and htmx_target() == 'infrastructure-automation-results'
        else 'infrastructure_automation/index.html'
    )
    return render_template(template, **context)
