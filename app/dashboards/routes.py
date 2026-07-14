from __future__ import annotations

from flask import Blueprint, redirect, request, url_for
from flask_login import login_required

from app.rbac.decorators import permission_required

# Endpoint-compatible redirects for code and bookmarks that still reference the
# original mixed ``dashboard`` blueprint. New code must use ``welcome`` or
# ``kubernetes_dashboard`` directly.
dashboard_compat_bp = Blueprint('dashboard', __name__)


@dashboard_compat_bp.route('/')
@permission_required('dashboard.view')
def index():
    return redirect(url_for('kubernetes_dashboard.index', **request.args), code=302)


@dashboard_compat_bp.route('/dashboard/section/<string:section>')
@permission_required('dashboard.view')
def section(section: str):
    return redirect(
        url_for('kubernetes_dashboard.section', section=section, **request.args),
        code=307,
    )


@dashboard_compat_bp.route('/dashboard/welcome')
@login_required
def welcome():
    return redirect(url_for('welcome.index'), code=302)
