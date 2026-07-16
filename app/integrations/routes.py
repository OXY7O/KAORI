from flask import Blueprint, render_template
from flask.typing import ResponseReturnValue

from app.integrations.service import build_alertmanager_page, build_integrations_overview, build_prometheus_page
from app.rbac.decorators import permission_required

integrations_bp = Blueprint('integrations', __name__, url_prefix='/integrations')

@integrations_bp.get('/')
@permission_required('settings.manage_integrations')
def overview() -> ResponseReturnValue:
    return render_template('integrations/overview.html', **build_integrations_overview())


@integrations_bp.get('/prometheus')
@permission_required('settings.manage_integrations')
def prometheus() -> ResponseReturnValue:
    return render_template('integrations/prometheus.html', **build_prometheus_page())


@integrations_bp.get('/alertmanager')
@permission_required('settings.manage_integrations')
def alertmanager() -> ResponseReturnValue:
    return render_template('integrations/alertmanager.html', **build_alertmanager_page())

