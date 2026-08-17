from __future__ import annotations

from flask import Blueprint, render_template

from app.access.overview.presentation import build_access_overview
from app.rbac.decorators import any_permission_required

bp = Blueprint('overview', __name__)


@bp.get('/')
@any_permission_required(
    'users.view',
    'users.manage',
    'identity_providers.view',
    'roles.view',
    'settings.view_operational_activity',
)
def index():
    return render_template(
        'access/overview/index.html',
        access_overview=build_access_overview(),
    )
