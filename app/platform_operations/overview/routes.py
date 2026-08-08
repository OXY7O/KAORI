from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import current_user

from app.platform_operations.overview.presentation import build_platform_operations_overview_context
from app.rbac.decorators import any_permission_required

bp = Blueprint('overview', __name__)


@bp.get('/')
@any_permission_required(
    'jobs.view',
    'platform_operations.view_data_lifecycle',
    'kubernetes_secrets.manage_reveal',
)
def index():
    context = build_platform_operations_overview_context(
        can_jobs=current_user.has_permission('jobs.view'),
        can_data_lifecycle=current_user.has_permission('platform_operations.view_data_lifecycle'),
        can_kubernetes_admin=current_user.has_permission('kubernetes_secrets.manage_reveal'),
    )
    return render_template('platform_operations/overview/index.html', platform_overview=context)
