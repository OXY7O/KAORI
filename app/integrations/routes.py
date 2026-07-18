from flask import Blueprint, render_template, request
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
    context = build_prometheus_page(
        compatibility=request.args.get('compatibility', '').strip(),
        environment=request.args.get('environment', '').strip(),
        readiness=request.args.get('readiness', '').strip(),
        page=request.args.get('page', 1, type=int),
        per_page=request.args.get('per_page', 5, type=int),
    )
    if request.headers.get('HX-Request') == 'true':
        return render_template('integrations/prometheus/partials/_inventory_content.html', **context)
    return render_template('integrations/prometheus.html', **context)


@integrations_bp.get('/alertmanager')
@permission_required('settings.manage_integrations')
def alertmanager() -> ResponseReturnValue:
    context = build_alertmanager_page(
        query=request.args.get('q', '').strip(),
        readiness=request.args.get('readiness', '').strip(),
        deployment_type=request.args.get('deployment_type', '').strip(),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    if request.headers.get('HX-Request') == 'true':
        return render_template('integrations/alertmanager/partials/_inventory_card.html', **context)
    return render_template('integrations/alertmanager.html', **context)

